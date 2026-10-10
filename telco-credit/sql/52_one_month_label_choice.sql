-- ============================================================================
--  WHICH ONE-MONTH LABEL? Measure it, do not argue it.          (Trino/Presto)
--
--  The product became one-month DCB: the subscriber draws during month M, the
--  draw lands on the bill issued for M, and that bill falls due during M+1.
--  Three things have to be settled before the model is re-fitted, and all
--  three are measurements:
--
--   1. WHICH MONTH. A bar in 140407 cannot have been caused by a draw in
--      140407 - it was caused by failing to pay the 140406 bill, before this
--      product existed. 42 therefore labels on 140408 and treats 140407 as the
--      exposure window (DRAW_SKIP = 1). C2 tests whether that was necessary.
--
--   2. WHICH EVENT. The four-month product labelled on a TWO-WAY bar, which
--      follows months of arrears. Over one month it may be too rare to fit.
--      A ONE-WAY bar is the operator's first arrears action. 42 currently
--      uses either (LABEL_EVENT = "any_bar"). C1 gives the rates.
--
--   3. IS IT THICK ENOUGH. A label with too few events cannot train a model
--      whatever its economics. C3 says yes or no against a stated floor.
--
--  SELF-CONTAINED. It rebuilds the screened population from the fact table
--  rather than reading dcb_model, so it runs correctly whether or not 42 has
--  been re-run with the new label.
--
--  Population: revenue at or above 1,050,000 Rial in 2 or more of
--  140401..140406, never one-way barred and never two-way barred in that
--  window - the MODEL cohort exactly.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_label_menu;
CREATE TABLE dwbi_temp40_db.dcb_label_menu WITH (format='PARQUET') AS
WITH feat AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140401), 0) AS r1,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140402), 0) AS r2,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140403), 0) AS r3,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140404), 0) AS r4,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140405), 0) AS r5,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140406), 0) AS r6,
            MAX(IF(sbrp_stat_id = 3, 1, 0))                AS f_oneway,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                AS f_twoway
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140401 AND 140406
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
),
screened AS (
    SELECT  sbrp_id,
            IF(r1>=1050000,1,0) + IF(r2>=1050000,1,0) + IF(r3>=1050000,1,0)
          + IF(r4>=1050000,1,0) + IF(r5>=1050000,1,0) + IF(r6>=1050000,1,0) AS rev_months,
            r1+r2+r3+r4+r5+r6 AS rev_6m
    FROM    feat
    WHERE   IF(r1>=1050000,1,0) + IF(r2>=1050000,1,0) + IF(r3>=1050000,1,0)
          + IF(r4>=1050000,1,0) + IF(r5>=1050000,1,0) + IF(r6>=1050000,1,0) >= 2
      AND   f_oneway = 0
      AND   f_twoway = 0
),
fwd AS (
    -- One row per subscriber, the four months after the feature window, each
    -- event flagged per month. MAX not SUM: a subscriber barred twice in a
    -- month is barred, not barred twice.
    SELECT   sbrp_id,
             MAX(IF(month_key=140407 AND sbrp_stat_id=3, 1, 0)) AS ow_07,
             MAX(IF(month_key=140408 AND sbrp_stat_id=3, 1, 0)) AS ow_08,
             MAX(IF(month_key=140409 AND sbrp_stat_id=3, 1, 0)) AS ow_09,
             MAX(IF(month_key=140410 AND sbrp_stat_id=3, 1, 0)) AS ow_10,
             MAX(IF(month_key=140407 AND sbrp_stat_id=4, 1, 0)) AS tw_07,
             MAX(IF(month_key=140408 AND sbrp_stat_id=4, 1, 0)) AS tw_08,
             MAX(IF(month_key=140409 AND sbrp_stat_id=4, 1, 0)) AS tw_09,
             MAX(IF(month_key=140410 AND sbrp_stat_id=4, 1, 0)) AS tw_10,
             COUNT(DISTINCT month_key)                          AS n_fwd_months
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140407 AND 140410
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT   s.sbrp_id, s.rev_months, s.rev_6m,
         COALESCE(f.ow_07,0) AS ow_07, COALESCE(f.ow_08,0) AS ow_08,
         COALESCE(f.ow_09,0) AS ow_09, COALESCE(f.ow_10,0) AS ow_10,
         COALESCE(f.tw_07,0) AS tw_07, COALESCE(f.tw_08,0) AS tw_08,
         COALESCE(f.tw_09,0) AS tw_09, COALESCE(f.tw_10,0) AS tw_10,
         COALESCE(f.n_fwd_months,0) AS n_fwd_months,
         -- the label 42 now builds: either bar, in 140408 only
         GREATEST(COALESCE(f.ow_08,0), COALESCE(f.tw_08,0))     AS y_chosen,
         -- the label the four-month product used, for comparison
         GREATEST(COALESCE(f.tw_07,0), COALESCE(f.tw_08,0),
                  COALESCE(f.tw_09,0), COALESCE(f.tw_10,0))     AS y_old_4m
FROM     screened s
LEFT JOIN fwd f ON f.sbrp_id = s.sbrp_id;

-- ---------------------------------------------------------------------------
-- C1  EVERY CANDIDATE, SIDE BY SIDE.
--
--     Read down the 140408 column: that is the repayment month and the one the
--     product cares about. Read ACROSS to see how much the choice of event
--     changes the rate.
--
--     The four-month two-way rate on this cohort was 0.5213 pct. A one-month
--     figure anywhere near that would mean the horizon is not really binding.
-- ---------------------------------------------------------------------------
SELECT   'one-way'  AS event,
         100.0 * AVG(CAST(ow_07 AS DOUBLE))                       AS pct_140407,
         100.0 * AVG(CAST(ow_08 AS DOUBLE))                       AS pct_140408,
         100.0 * AVG(CAST(ow_09 AS DOUBLE))                       AS pct_140409,
         100.0 * AVG(CAST(ow_10 AS DOUBLE))                       AS pct_140410
FROM     dwbi_temp40_db.dcb_label_menu
UNION ALL
SELECT   'two-way',
         100.0 * AVG(CAST(tw_07 AS DOUBLE)),
         100.0 * AVG(CAST(tw_08 AS DOUBLE)),
         100.0 * AVG(CAST(tw_09 AS DOUBLE)),
         100.0 * AVG(CAST(tw_10 AS DOUBLE))
FROM     dwbi_temp40_db.dcb_label_menu
UNION ALL
SELECT   'either bar',
         100.0 * AVG(CAST(GREATEST(ow_07, tw_07) AS DOUBLE)),
         100.0 * AVG(CAST(GREATEST(ow_08, tw_08) AS DOUBLE)),
         100.0 * AVG(CAST(GREATEST(ow_09, tw_09) AS DOUBLE)),
         100.0 * AVG(CAST(GREATEST(ow_10, tw_10) AS DOUBLE))
FROM     dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- C2  WAS SKIPPING THE DRAW MONTH NECESSARY? The check that justifies
--     DRAW_SKIP = 1, or overturns it.
--
--     clean_in_07 holds subscribers with no bar of any kind in the draw month.
--     If the 140408 rate among THEM is close to the rate among everyone, the
--     draw month carries little carried-over arrears and labelling on 140407
--     would have been nearly harmless. If it is much lower, then the
--     unconditional 140407 rate is mostly OLD debt, labelling on the draw
--     month would have measured the wrong thing, and DRAW_SKIP = 1 is right.
--
--     contaminated_share says how much of a 140407 label would have been
--     arrears that were already running.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                                 AS n_screened,
         SUM(GREATEST(ow_07, tw_07))                              AS n_barred_in_draw_month,
         100.0 * AVG(CAST(GREATEST(ow_07, tw_07) AS DOUBLE))      AS pct_barred_140407,
         SUM(IF(GREATEST(ow_07, tw_07) = 0, 1, 0))                AS n_clean_in_07,
         100.0 * SUM(IF(GREATEST(ow_07, tw_07) = 0, GREATEST(ow_08, tw_08), 0))
               / NULLIF(SUM(IF(GREATEST(ow_07, tw_07) = 0, 1, 0)), 0)
                                                                  AS pct_140408_given_clean_07,
         100.0 * AVG(CAST(GREATEST(ow_08, tw_08) AS DOUBLE))      AS pct_140408_all,
         100.0 * SUM(IF(GREATEST(ow_07, tw_07) = 1, GREATEST(ow_08, tw_08), 0))
               / NULLIF(SUM(GREATEST(ow_07, tw_07)), 0)           AS pct_140408_given_barred_07
FROM     dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- C3  IS THE CHOSEN LABEL THICK ENOUGH TO FIT ON?
--
--     The four-month label gave 45,361 events in 8.7M rows and produced a
--     usable model. There is no exact floor, but a rule of thumb for a
--     40-feature gradient boosting fit is a few thousand events minimum, and
--     the decile table needs 10 or more expected events in its SAFEST decile
--     to be readable at all - which at a 10 pct decile means roughly 10,000
--     events overall before the safe end becomes judgeable.
--
--     thick_enough is advisory. If it reads 0, widen the event (one-way as
--     well as two-way is already the default) or take two label months before
--     widening the term in the product.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                                 AS n_rows,
         SUM(y_chosen)                                            AS n_events_chosen,
         100.0 * AVG(CAST(y_chosen AS DOUBLE))                    AS pct_chosen,
         SUM(y_old_4m)                                            AS n_events_old_4m,
         100.0 * AVG(CAST(y_old_4m AS DOUBLE))                    AS pct_old_4m,
         CAST(SUM(y_chosen) AS DOUBLE) / NULLIF(SUM(y_old_4m), 0) AS chosen_over_old,
         IF(SUM(y_chosen) >= 10000, 1, 0)                         AS thick_enough,
         SUM(IF(n_fwd_months < 4, 1, 0))                          AS n_partly_observed
FROM     dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- C4  DOES THE NEW LABEL AGREE WITH THE OLD ONE?
--
--     y_chosen should be very close to a SUBSET of y_old_4m: a subscriber
--     barred in 140408 was barred within 140407..140410. The one cell that
--     must be near zero is new=1, old=0 - it would mean a one-way bar in
--     140408 with no two-way bar in the whole four months, which is exactly
--     the population the old label MISSED and the new one catches. A large
--     count there is not an error; it is the reason to prefer the new label.
-- ---------------------------------------------------------------------------
SELECT   y_chosen, y_old_4m,
         COUNT(*)                                       AS n,
         100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()       AS pct_of_cohort,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60            AS med_month_toman,
         AVG(CAST(rev_months AS DOUBLE))                AS avg_rev_months
FROM     dwbi_temp40_db.dcb_label_menu
GROUP BY y_chosen, y_old_4m
ORDER BY y_chosen, y_old_4m;

-- ---------------------------------------------------------------------------
-- C5  DOES THE CHOSEN LABEL STILL SORT BY REVENUE THE WAY THE OLD ONE DID?
--     A sanity check that the shorter horizon has not produced a label driven
--     by something unrelated. rev_months 2 should be riskier than rev_months 6
--     under both labels; if the new one is flat, it is not measuring credit
--     behaviour.
-- ---------------------------------------------------------------------------
SELECT   rev_months,
         COUNT(*)                                       AS n,
         100.0 * AVG(CAST(y_chosen AS DOUBLE))          AS pct_new_1m,
         100.0 * AVG(CAST(y_old_4m AS DOUBLE))          AS pct_old_4m
FROM     dwbi_temp40_db.dcb_label_menu
GROUP BY rev_months
ORDER BY rev_months;

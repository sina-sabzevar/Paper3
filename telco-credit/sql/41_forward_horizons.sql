-- ============================================================================
--  THE FORWARD QUESTION, MEASURED                           (Trino/Presto)
--
--  How many subscribers with revenue over 170,000 Toman carry under a 1 pct
--  chance of a two-way bar over the NEXT 2, 3 and 4 months.
--
--  WHY THIS FILE HAS TO EXIST
--
--  Every rate produced so far is CONTEMPORANEOUS: revenue and bar status come
--  from the same six months. The arithmetic answer available without this
--  query converts a 6-month "ever barred" rate to shorter horizons under a
--  constant monthly hazard, p_n = 1 - (1-p6)^(n/6), which gives:
--
--      revenue cut   6m band    2 months   3 months   4 months
--          6         0.200 pct   0.067      0.100      0.133
--          5+        0.530 pct   0.177      0.266      0.354
--          4+        0.878 pct   0.293      0.440      0.586
--          3+        1.313 pct   0.440      0.659      0.877
--          2+        1.842 pct   0.618      0.925      1.232
--
--  Two reasons that is not good enough to hand an implementation team.
--
--    1. The constant-hazard assumption is untested. If risk is front-loaded -
--       a subscriber who is going to fail does so quickly - the true 2-month
--       rate is HIGHER than the conversion says.
--    2. The screen keeps only subscribers never barred in the window, so
--       their in-window rate is zero by construction. The band rate includes
--       the ones who were barred, which makes it a ceiling rather than an
--       estimate of the screened group.
--
--  THE DESIGN
--
--      FEATURE window   140407..140412   revenue, one-way runs, two-way
--      OUTCOME window   140501..140504   two-way bar, at 2, 3 and 4 months
--
--  No month appears in both. The screen is applied on the feature window and
--  the outcome is measured strictly after it, which is what makes the result
--  a forecast rather than an association.
--
--  Payments are continuous 140301..140506 and the monthly fact covers the
--  same span, so this window pair is available today. 140505 and 140506 are
--  left unused and would extend the outcome to six months.
--
--  Revenue per KPI_v4: SUM(arpu) - SUM(tot_arpu_tax_amt). arpu is 23.8 pct
--  NULL overall and the nulls concentrate in the zero-revenue bucket, so
--  n_arpu_null is carried through and reported.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- F1  THE FEATURE WINDOW. 140407..140412, six months, revenue and bar
--     history. Note 140412 plus one is 140501, not 140413 - the months are
--     written out because Jalali arithmetic does not carry.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_oot;
CREATE TABLE dwbi_temp40_db.dcb_oot WITH (format='PARQUET') AS
WITH feat AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140407), 0)        AS f1,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140408), 0)        AS f2,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140409), 0)        AS f3,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140410), 0)        AS f4,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140411), 0)        AS f5,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140412), 0)        AS f6,
            SUM(IF(arpu IS NULL, 1, 0))                           AS n_arpu_null,
            MAX(IF(month_key = 140407 AND sbrp_stat_id = 3, 1, 0)) AS b1,
            MAX(IF(month_key = 140408 AND sbrp_stat_id = 3, 1, 0)) AS b2,
            MAX(IF(month_key = 140409 AND sbrp_stat_id = 3, 1, 0)) AS b3,
            MAX(IF(month_key = 140410 AND sbrp_stat_id = 3, 1, 0)) AS b4,
            MAX(IF(month_key = 140411 AND sbrp_stat_id = 3, 1, 0)) AS b5,
            MAX(IF(month_key = 140412 AND sbrp_stat_id = 3, 1, 0)) AS b6,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                       AS feat_twoway,
            MAX(IF(sbrp_stat_id IN (8,9), 1, 0))                  AS feat_reclaim,
            MAX(COALESCE(available_credit, 0))                    AS avail_max,
            MAX(COALESCE(age_on_net_months, 0))                   AS tenure_m
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140407, 140408, 140409, 140410, 140411, 140412)
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
),
outc AS (
    -- the OUTCOME window, strictly after the features. Three nested horizons.
    SELECT  sbrp_id,
            MAX(IF(month_key IN (140501, 140502)
                   AND sbrp_stat_id = 4, 1, 0))                   AS tw_2m,
            MAX(IF(month_key IN (140501, 140502, 140503)
                   AND sbrp_stat_id = 4, 1, 0))                   AS tw_3m,
            MAX(IF(month_key IN (140501, 140502, 140503, 140504)
                   AND sbrp_stat_id = 4, 1, 0))                   AS tw_4m,
            COUNT(DISTINCT month_key)                             AS n_out_months
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140501, 140502, 140503, 140504)
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT  f.sbrp_id,
        f.n_arpu_null,
        f.feat_twoway,
        f.feat_reclaim,
        f.avail_max,
        f.tenure_m,
        IF(f.f1 >= 1700000,1,0) + IF(f.f2 >= 1700000,1,0)
      + IF(f.f3 >= 1700000,1,0) + IF(f.f4 >= 1700000,1,0)
      + IF(f.f5 >= 1700000,1,0) + IF(f.f6 >= 1700000,1,0)         AS rev_months,
        GREATEST(6 * (f.b1*f.b2*f.b3*f.b4*f.b5*f.b6),
                 5 * GREATEST(f.b1*f.b2*f.b3*f.b4*f.b5, f.b2*f.b3*f.b4*f.b5*f.b6),
                 4 * GREATEST(f.b1*f.b2*f.b3*f.b4, f.b2*f.b3*f.b4*f.b5,
                              f.b3*f.b4*f.b5*f.b6),
                 3 * GREATEST(f.b1*f.b2*f.b3, f.b2*f.b3*f.b4,
                              f.b3*f.b4*f.b5, f.b4*f.b5*f.b6),
                 2 * GREATEST(f.b1*f.b2, f.b2*f.b3, f.b3*f.b4,
                              f.b4*f.b5, f.b5*f.b6),
                 1 * GREATEST(f.b1, f.b2, f.b3, f.b4, f.b5, f.b6))
                                                                  AS max_oneway_run,
        f.f1 + f.f2 + f.f3 + f.f4 + f.f5 + f.f6                   AS rev_6m,
        -- a subscriber absent from the outcome window cannot be judged. NULL,
        -- not 0 - calling them clean would credit a disappearance as a success.
        o.tw_2m, o.tw_3m, o.tw_4m,
        COALESCE(o.n_out_months, 0)                               AS n_out_months
FROM        feat f
LEFT JOIN   outc o ON o.sbrp_id = f.sbrp_id
;

-- ---------------------------------------------------------------------------
-- F2  THE ANSWER. Forward two-way rate by revenue cut, at each horizon,
--     on the screened population: never one-way barred and never two-way
--     barred in the FEATURE window.
--
--     Subscribers absent from the outcome window are excluded, and the count
--     of them is reported - a disappearance is not a clean record.
-- ---------------------------------------------------------------------------
SELECT  cut                                                    AS rev_cut,
        COUNT(*)                                               AS screened,
        100.0 * SUM(tw_2m) / COUNT(*)                          AS fwd_2m_pct,
        100.0 * SUM(tw_3m) / COUNT(*)                          AS fwd_3m_pct,
        100.0 * SUM(tw_4m) / COUNT(*)                          AS fwd_4m_pct,
        SUM(tw_2m)                                             AS n_bad_2m,
        SUM(tw_3m)                                             AS n_bad_3m,
        SUM(tw_4m)                                             AS n_bad_4m
FROM        dwbi_temp40_db.dcb_oot
CROSS JOIN  UNNEST(ARRAY[2, 3, 4, 5, 6]) AS t (cut)
WHERE       rev_months >= cut
  AND       max_oneway_run = 0
  AND       feat_twoway = 0
  AND       n_out_months > 0
GROUP BY    cut
ORDER BY    cut;

-- ---------------------------------------------------------------------------
-- F3  IS THE HAZARD CONSTANT? The arithmetic answer assumed it was. These
--     are the three horizons side by side on one population, so the shape
--     can be read instead of assumed.
--
--     Under a constant hazard, fwd_3m should be about 1.5x fwd_2m and fwd_4m
--     about 2.0x. Higher ratios mean risk is BACK-loaded and the short-horizon
--     estimates were pessimistic. Lower means FRONT-loaded, and the
--     2-month estimates understated the risk.
-- ---------------------------------------------------------------------------
SELECT  rev_months,
        COUNT(*)                                               AS screened,
        100.0 * SUM(tw_2m) / COUNT(*)                          AS fwd_2m_pct,
        100.0 * SUM(tw_3m) / COUNT(*)                          AS fwd_3m_pct,
        100.0 * SUM(tw_4m) / COUNT(*)                          AS fwd_4m_pct,
        1.0 * SUM(tw_3m) / NULLIF(SUM(tw_2m), 0)               AS ratio_3m_to_2m,
        1.0 * SUM(tw_4m) / NULLIF(SUM(tw_2m), 0)               AS ratio_4m_to_2m
FROM     dwbi_temp40_db.dcb_oot
WHERE    max_oneway_run = 0
  AND    feat_twoway = 0
  AND    n_out_months > 0
GROUP BY rev_months
ORDER BY rev_months;

-- ---------------------------------------------------------------------------
-- F4  HOW MUCH THE SCREEN ITSELF IS WORTH, measured forward. The never-barred
--     condition is what the arithmetic could not price - this gives it.
-- ---------------------------------------------------------------------------
SELECT  'rev 3+, never one-way, never two-way in features'      AS screen,
        COUNT(*)                                               AS n,
        100.0 * SUM(tw_4m) / COUNT(*)                          AS fwd_4m_pct
FROM    dwbi_temp40_db.dcb_oot
WHERE   rev_months >= 3 AND max_oneway_run = 0 AND feat_twoway = 0
  AND   n_out_months > 0
UNION ALL
SELECT  'rev 3+, no bar condition at all', COUNT(*),
        100.0 * SUM(tw_4m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_oot
WHERE   rev_months >= 3 AND n_out_months > 0
UNION ALL
SELECT  'rev 3+, one-way allowed, never two-way', COUNT(*),
        100.0 * SUM(tw_4m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_oot
WHERE   rev_months >= 3 AND feat_twoway = 0 AND n_out_months > 0
UNION ALL
SELECT  'absent from the outcome window (excluded above)', COUNT(*), NULL
FROM    dwbi_temp40_db.dcb_oot
WHERE   rev_months >= 3 AND max_oneway_run = 0 AND feat_twoway = 0
  AND   n_out_months = 0
ORDER BY n DESC;

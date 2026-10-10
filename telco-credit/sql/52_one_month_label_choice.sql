-- ============================================================================
--  WHICH ONE-MONTH LABEL? Measure it, do not argue it.          (Trino/Presto)
--
--  CORRECTED after the product was described properly. DCB credit is a
--  SEPARATE POOL from telco credit: DCB credit cannot buy packages, calls or
--  SMS, and telco credit cannot pay for VOD, bills or other off-net services.
--  A one-way bar restricts TELCO usage, so it is not something a DCB default
--  can cause. The first version of this file labelled on "either bar" and was
--  wrong to.
--
--  WHAT A DCB DEFAULT ACTUALLY LOOKS LIKE. The draw lands on the bill, and the
--  bill must be settled next month. So the event is NOT a service bar - it is
--  AN INVOICE THAT WENT UNPAID. That is measurable directly, from payments
--  against billings, and this file measures it.
--
--  The bars are kept as COMPARISON columns, not as the label. They are the
--  operator's own severe judgement that a subscriber did not pay, so they are
--  the only independent check available on whether a payment-shortfall label
--  is picking out real credit failure or just billing-cycle noise. D3 is that
--  check and it is the reason to trust or discard the whole approach.
--
--  ONE THING THIS CANNOT MEASURE. No subscriber in this data was ever given
--  DCB credit. Every label here is a proxy for "settles what is owed to the
--  operator". How someone behaves with a ring-fenced spending wallet they did
--  not have before is not in the data and will not be until a pilot runs.
--
--  Population: revenue at or above 1,050,000 Rial in 2 or more of
--  140401..140406, never one-way and never two-way barred in that window -
--  the MODEL cohort exactly. Self-contained: rebuilt from the fact tables, so
--  it runs whether or not 42 has been re-run.
--
--  Calendar: features 140401..140406, draw 140407, repayment due 140408.
--  Jalali month 7 and 8 both have 30 days, which the day_key ranges use.
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
    SELECT  sbrp_id, r1+r2+r3+r4+r5+r6 AS rev_6m,
            IF(r1>=1050000,1,0) + IF(r2>=1050000,1,0) + IF(r3>=1050000,1,0)
          + IF(r4>=1050000,1,0) + IF(r5>=1050000,1,0) + IF(r6>=1050000,1,0) AS rev_months
    FROM    feat
    WHERE   IF(r1>=1050000,1,0) + IF(r2>=1050000,1,0) + IF(r3>=1050000,1,0)
          + IF(r4>=1050000,1,0) + IF(r5>=1050000,1,0) + IF(r6>=1050000,1,0) >= 2
      AND   f_oneway = 0
      AND   f_twoway = 0
),
billed AS (
    -- What the operator invoiced. 140407 is the bill that would carry a DCB
    -- draw; the 140401..140406 total is the base the ratio is read against.
    SELECT   sbrp_id,
             COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                      FILTER (WHERE month_key = 140407), 0)                 AS billed_07,
             COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                      FILTER (WHERE month_key BETWEEN 140401 AND 140407), 0) AS billed_cum
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140401 AND 140407
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
paid AS (
    -- What the subscriber actually paid. Daily table, so the months are day
    -- ranges: Jalali 7 and 8 both run to 30.
    SELECT   sbrp_id,
             COALESCE(SUM(COALESCE(pmnt_amt,0))
                      FILTER (WHERE day_key BETWEEN 14040801 AND 14040830), 0) AS paid_08,
             COALESCE(SUM(COALESCE(pmnt_amt,0))
                      FILTER (WHERE day_key BETWEEN 14040701 AND 14040830), 0) AS paid_0708,
             COALESCE(SUM(COALESCE(pmnt_amt,0))
                      FILTER (WHERE day_key BETWEEN 14040101 AND 14040830), 0) AS paid_cum
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14040101 AND 14040830
    GROUP BY sbrp_id
),
bars AS (
    -- NOT the label. The operator's own verdict, used in D3 to check whether a
    -- payment shortfall is real credit failure or billing-cycle noise.
    SELECT   sbrp_id,
             MAX(IF(month_key=140408 AND sbrp_stat_id=3, 1, 0)) AS ow_08,
             MAX(IF(month_key=140408 AND sbrp_stat_id=4, 1, 0)) AS tw_08,
             MAX(IF(month_key IN (140409,140410) AND sbrp_stat_id=3, 1, 0)) AS ow_later,
             MAX(IF(month_key IN (140409,140410) AND sbrp_stat_id=4, 1, 0)) AS tw_later,
             COUNT(DISTINCT month_key)                          AS n_fwd_months
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140408 AND 140410
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT   s.sbrp_id, s.rev_6m, s.rev_months,
         COALESCE(b.billed_07, 0)   AS billed_07,
         COALESCE(b.billed_cum, 0)  AS billed_cum,
         COALESCE(p.paid_08, 0)     AS paid_08,
         COALESCE(p.paid_0708, 0)   AS paid_0708,
         COALESCE(p.paid_cum, 0)    AS paid_cum,
         -- STRICT: did next month's payment cover this month's invoice.
         IF(COALESCE(b.billed_07,0) > 0,
            CAST(COALESCE(p.paid_08,0) AS DOUBLE) / b.billed_07, NULL)   AS cover_strict,
         -- TOLERANT: two months of payment against one invoice, for subscribers
         -- who settle early or late within the cycle.
         IF(COALESCE(b.billed_07,0) > 0,
            CAST(COALESCE(p.paid_0708,0) AS DOUBLE) / b.billed_07, NULL) AS cover_window,
         -- CUMULATIVE: everything billed to 140407 against everything paid to
         -- 140408. Immune to which month a payment lands in, but carries any
         -- opening balance at 140401, which is unknown.
         IF(COALESCE(b.billed_cum,0) > 0,
            CAST(COALESCE(p.paid_cum,0) AS DOUBLE) / b.billed_cum, NULL) AS cover_cum,
         COALESCE(bb.ow_08,0) AS ow_08, COALESCE(bb.tw_08,0) AS tw_08,
         COALESCE(bb.ow_later,0) AS ow_later, COALESCE(bb.tw_later,0) AS tw_later,
         COALESCE(bb.n_fwd_months,0) AS n_fwd_months
FROM        screened s
LEFT JOIN   billed b  ON b.sbrp_id  = s.sbrp_id
LEFT JOIN   paid   p  ON p.sbrp_id  = s.sbrp_id
LEFT JOIN   bars   bb ON bb.sbrp_id = s.sbrp_id;

-- ---------------------------------------------------------------------------
-- D1  WHERE IS THE THRESHOLD? Pick it from the distribution, not from taste.
--
--     pay_to_rev_ratio on this project measured 1.40 and 1.28 - subscribers
--     pay MORE than they are billed, because of top-ups, deposits and carried
--     balances. So the median cover is expected ABOVE 1.0, and "cover < 1.0"
--     would label a large and mostly innocent slice. The interesting region is
--     the LOW tail: p01 to p10.
--
--     n_null_cover counts subscribers billed nothing in 140407. They cannot
--     default on an invoice that does not exist and must be excluded from any
--     rate, not scored as good.
-- ---------------------------------------------------------------------------
SELECT   'cover_strict' AS measure,
         COUNT(cover_strict)                                   AS n_with_bill,
         COUNT(*) - COUNT(cover_strict)                        AS n_null_cover,
         APPROX_PERCENTILE(cover_strict, 0.01)                 AS p01,
         APPROX_PERCENTILE(cover_strict, 0.05)                 AS p05,
         APPROX_PERCENTILE(cover_strict, 0.10)                 AS p10,
         APPROX_PERCENTILE(cover_strict, 0.25)                 AS p25,
         APPROX_PERCENTILE(cover_strict, 0.50)                 AS p50,
         APPROX_PERCENTILE(cover_strict, 0.90)                 AS p90
FROM     dwbi_temp40_db.dcb_label_menu
UNION ALL
SELECT   'cover_window', COUNT(cover_window), COUNT(*) - COUNT(cover_window),
         APPROX_PERCENTILE(cover_window, 0.01), APPROX_PERCENTILE(cover_window, 0.05),
         APPROX_PERCENTILE(cover_window, 0.10), APPROX_PERCENTILE(cover_window, 0.25),
         APPROX_PERCENTILE(cover_window, 0.50), APPROX_PERCENTILE(cover_window, 0.90)
FROM     dwbi_temp40_db.dcb_label_menu
UNION ALL
SELECT   'cover_cum', COUNT(cover_cum), COUNT(*) - COUNT(cover_cum),
         APPROX_PERCENTILE(cover_cum, 0.01), APPROX_PERCENTILE(cover_cum, 0.05),
         APPROX_PERCENTILE(cover_cum, 0.10), APPROX_PERCENTILE(cover_cum, 0.25),
         APPROX_PERCENTILE(cover_cum, 0.50), APPROX_PERCENTILE(cover_cum, 0.90)
FROM     dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- D2  THE RATE AT EACH CANDIDATE CUT, on subscribers who had a bill.
--     Pick the cut that gives a label both economically honest and thick
--     enough to fit - D4 says what thick enough means.
-- ---------------------------------------------------------------------------
SELECT   'cover_strict < 0.10' AS rule, SUM(IF(cover_strict < 0.10, 1, 0)) AS n_bad,
         100.0 * AVG(IF(cover_strict < 0.10, 1e0, 0e0)) AS pct
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_strict IS NOT NULL
UNION ALL SELECT 'cover_strict < 0.25', SUM(IF(cover_strict < 0.25, 1, 0)),
         100.0 * AVG(IF(cover_strict < 0.25, 1e0, 0e0))
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_strict IS NOT NULL
UNION ALL SELECT 'cover_strict < 0.50', SUM(IF(cover_strict < 0.50, 1, 0)),
         100.0 * AVG(IF(cover_strict < 0.50, 1e0, 0e0))
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_strict IS NOT NULL
UNION ALL SELECT 'cover_window < 0.25', SUM(IF(cover_window < 0.25, 1, 0)),
         100.0 * AVG(IF(cover_window < 0.25, 1e0, 0e0))
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_window IS NOT NULL
UNION ALL SELECT 'cover_window < 0.50', SUM(IF(cover_window < 0.50, 1, 0)),
         100.0 * AVG(IF(cover_window < 0.50, 1e0, 0e0))
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_window IS NOT NULL
UNION ALL SELECT 'cover_cum < 0.75', SUM(IF(cover_cum < 0.75, 1, 0)),
         100.0 * AVG(IF(cover_cum < 0.75, 1e0, 0e0))
FROM dwbi_temp40_db.dcb_label_menu WHERE cover_cum IS NOT NULL
UNION ALL SELECT 'two-way bar in 140408 (old style)', SUM(tw_08),
         100.0 * AVG(CAST(tw_08 AS DOUBLE))
FROM dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- D3  THE CHECK THAT DECIDES WHETHER ANY OF THIS IS REAL.
--
--     A payment shortfall is only a credit event if the operator eventually
--     agrees. Group by the shortfall band in the repayment month and read the
--     bar rate in the TWO MONTHS AFTER. If subscribers who underpaid in
--     140408 are barred in 140409-140410 at many times the rate of those who
--     paid, the shortfall is real arrears and the label is sound.
--
--     If the bar rate is FLAT across the bands, the shortfall is billing-cycle
--     noise - people paying on a different rhythm - and a cover-ratio label
--     would train the model on bookkeeping rather than on credit risk. In that
--     case use the two-way bar and accept the thinner event.
-- ---------------------------------------------------------------------------
SELECT   IF(cover_strict IS NULL, 'no bill in 140407',
         IF(cover_strict < 0.10, 'a  under 0.10',
         IF(cover_strict < 0.25, 'b  0.10 - 0.25',
         IF(cover_strict < 0.50, 'c  0.25 - 0.50',
         IF(cover_strict < 1.00, 'd  0.50 - 1.00', 'e  1.00 and over'))))) AS cover_band,
         COUNT(*)                                             AS n,
         100.0 * AVG(CAST(tw_later AS DOUBLE))                AS pct_twoway_140409_10,
         100.0 * AVG(CAST(ow_later AS DOUBLE))                AS pct_oneway_140409_10,
         100.0 * AVG(CAST(GREATEST(ow_later, tw_later) AS DOUBLE)) AS pct_any_bar_later,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60                  AS med_month_toman
FROM     dwbi_temp40_db.dcb_label_menu
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- D4  IS THE LABEL THICK ENOUGH TO FIT ON?
--
--     The four-month two-way label gave 45,361 events in 8.7M rows. The
--     decile table needs 10 or more expected events in its SAFEST decile to be
--     readable, which at a 10 pct decile means roughly 10,000 events overall
--     before the safe end - where the book is drawn - can be judged at all.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                             AS n_rows,
         SUM(IF(cover_strict IS NULL, 1, 0))                  AS n_no_bill,
         SUM(IF(cover_strict < 0.25, 1, 0))                   AS n_unpaid_025,
         SUM(tw_08)                                           AS n_twoway_08,
         IF(SUM(IF(cover_strict < 0.25, 1, 0)) >= 10000, 1, 0) AS unpaid_thick_enough,
         IF(SUM(tw_08) >= 10000, 1, 0)                        AS twoway_thick_enough,
         SUM(IF(n_fwd_months < 3, 1, 0))                      AS n_partly_observed
FROM     dwbi_temp40_db.dcb_label_menu;

-- ---------------------------------------------------------------------------
-- D5  DOES IT SORT BY REVENUE? A label that does not vary with how much a
--     subscriber bills is probably not measuring credit behaviour.
-- ---------------------------------------------------------------------------
SELECT   rev_months,
         COUNT(*)                                             AS n,
         100.0 * AVG(IF(cover_strict < 0.25, 1e0, 0e0))       AS pct_unpaid_025,
         100.0 * AVG(CAST(tw_08 AS DOUBLE))                   AS pct_twoway_08,
         100.0 * AVG(CAST(tw_later AS DOUBLE))                AS pct_twoway_later
FROM     dwbi_temp40_db.dcb_label_menu
GROUP BY rev_months
ORDER BY rev_months;

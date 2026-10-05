-- ============================================================================
--  HOW MANY GOOD DEBTORS ARE IN THE NETWORK                 (Trino/Presto)
--
--  Two matrices over the most recent six months, 140501..140506.
--
--    MATRIX 1   months with payment >= 170,000 Toman   x   longest run of
--               CONSECUTIVE one-way bar months, among subscribers who have
--               NEVER been two-way barred in the window.
--
--    MATRIX 2   the same payment axis   x   two-way barred in the window or
--               not.
--
--  WHY "IN A ROW" AND NOT "HOW MANY MONTHS"
--
--  A subscriber barred in months 1, 3 and 5 has three bar months but never
--  two in a row - they keep brushing the credit ceiling and curing it. A
--  subscriber barred in months 3, 4 and 5 has an escalating episode. Same
--  count, different risk, and only the consecutive run tells them apart.
--
--  The longest run is computed as GREATEST over products of the six monthly
--  flags: a product is the AND of a window, and GREATEST picks the longest
--  window that holds. Checked against all 64 possible six-month patterns -
--  exact for every one, with no window functions needed.
--
--  PAYMENTS USE ALL STATUSES
--
--  bllg_pmnt_stat_id = 2 holds 61.2 pct of payment value and status 1 holds
--  38.7 pct. Filtering to 2, as this project did throughout, discards over a
--  third of the money and dropped the count of subscribers clearing two
--  months from 11,202,782 to 7,623,016.
--
--  ONE LIMITATION, STATED
--
--  Bar status comes from the MONTHLY fact, one snapshot per subscriber-month.
--  A bar that opened and cured inside a single month does not appear. The
--  daily fact would catch those, at 40,000,000 subscribers times 184 days,
--  and it is the right refinement once these matrices say where to look.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- G1  THE PANEL. One row per permanent subscriber, with six payment flags,
--     six one-way flags, the longest consecutive one-way run, and the
--     two-way history.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_matrix;
CREATE TABLE dwbi_temp40_db.dcb_matrix WITH (format='PARQUET') AS
WITH pm AS (
    SELECT   sbrp_id,
             day_key / 100                        AS month_key,
             SUM(COALESCE(pmnt_amt, 0))           AS paid
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14050101 AND 14050631
    GROUP BY sbrp_id, day_key / 100
),
pay AS (
    SELECT  sbrp_id,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140501), 0) AS a1,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140502), 0) AS a2,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140503), 0) AS a3,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140504), 0) AS a4,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140505), 0) AS a5,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140506), 0) AS a6
    FROM    pm
    GROUP BY sbrp_id
),
st AS (
    SELECT  sbrp_id,
            MAX(IF(month_key = 140501 AND sbrp_stat_id = 3, 1, 0)) AS o1,
            MAX(IF(month_key = 140502 AND sbrp_stat_id = 3, 1, 0)) AS o2,
            MAX(IF(month_key = 140503 AND sbrp_stat_id = 3, 1, 0)) AS o3,
            MAX(IF(month_key = 140504 AND sbrp_stat_id = 3, 1, 0)) AS o4,
            MAX(IF(month_key = 140505 AND sbrp_stat_id = 3, 1, 0)) AS o5,
            MAX(IF(month_key = 140506 AND sbrp_stat_id = 3, 1, 0)) AS o6,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                        AS ever_twoway,
            SUM(IF(sbrp_stat_id = 4, 1, 0))                        AS n_twoway_months,
            SUM(IF(sbrp_stat_id = 3, 1, 0))                        AS n_oneway_months,
            MAX(IF(sbrp_stat_id IN (8, 9), 1, 0))                  AS ever_reclaim,
            MAX(COALESCE(available_credit, 0))                     AS avail_max,
            MAX(COALESCE(bill_outstanding_amt, 0))                 AS outst_max,
            MAX(COALESCE(age_on_net_months, 0))                    AS tenure_m,
            MAX(IF(active1_base_flag = 1, 1, 0))                   AS act1_any
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140501, 140502, 140503, 140504, 140505, 140506)
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT  s.sbrp_id,
        s.ever_twoway,
        s.n_twoway_months,
        s.n_oneway_months,
        s.ever_reclaim,
        s.avail_max,
        s.outst_max,
        s.tenure_m,
        s.act1_any,
        -- months with payment at or over 170,000 Toman
        IF(COALESCE(p.a1, 0) >= 1700000, 1, 0)
      + IF(COALESCE(p.a2, 0) >= 1700000, 1, 0)
      + IF(COALESCE(p.a3, 0) >= 1700000, 1, 0)
      + IF(COALESCE(p.a4, 0) >= 1700000, 1, 0)
      + IF(COALESCE(p.a5, 0) >= 1700000, 1, 0)
      + IF(COALESCE(p.a6, 0) >= 1700000, 1, 0)                     AS pay_months,
        -- the longest CONSECUTIVE run of one-way bar months. A product is the
        -- AND of a window; GREATEST picks the longest window that holds.
        -- Verified exact against all 64 possible six-month patterns.
        GREATEST(6 * (s.o1 * s.o2 * s.o3 * s.o4 * s.o5 * s.o6),
                 5 * GREATEST(s.o1 * s.o2 * s.o3 * s.o4 * s.o5,
                              s.o2 * s.o3 * s.o4 * s.o5 * s.o6),
                 4 * GREATEST(s.o1 * s.o2 * s.o3 * s.o4,
                              s.o2 * s.o3 * s.o4 * s.o5,
                              s.o3 * s.o4 * s.o5 * s.o6),
                 3 * GREATEST(s.o1 * s.o2 * s.o3, s.o2 * s.o3 * s.o4,
                              s.o3 * s.o4 * s.o5, s.o4 * s.o5 * s.o6),
                 2 * GREATEST(s.o1 * s.o2, s.o2 * s.o3, s.o3 * s.o4,
                              s.o4 * s.o5, s.o5 * s.o6),
                 1 * GREATEST(s.o1, s.o2, s.o3, s.o4, s.o5, s.o6))
                                                                   AS max_oneway_run,
        COALESCE(p.a1, 0) + COALESCE(p.a2, 0) + COALESCE(p.a3, 0)
      + COALESCE(p.a4, 0) + COALESCE(p.a5, 0) + COALESCE(p.a6, 0)  AS paid_6m,
        GREATEST(COALESCE(p.a1, 0), COALESCE(p.a2, 0), COALESCE(p.a3, 0),
                 COALESCE(p.a4, 0), COALESCE(p.a5, 0), COALESCE(p.a6, 0))
                                                                   AS paid_max_month
FROM        st s
LEFT JOIN   pay p ON p.sbrp_id = s.sbrp_id
;

-- ---------------------------------------------------------------------------
-- G2  MATRIX 1. Payment months against the longest consecutive one-way run,
--     among subscribers NEVER two-way barred in the window.
--
--     The top-left region - high pay_months, zero one-way run - is the
--     potential good-debtor population.
-- ---------------------------------------------------------------------------
SELECT  pay_months,
        COUNT(*)                                              AS total,
        COUNT(*) FILTER (WHERE max_oneway_run = 0)            AS oneway_never,
        COUNT(*) FILTER (WHERE max_oneway_run = 1)            AS oneway_run_1,
        COUNT(*) FILTER (WHERE max_oneway_run = 2)            AS oneway_run_2,
        COUNT(*) FILTER (WHERE max_oneway_run = 3)            AS oneway_run_3,
        COUNT(*) FILTER (WHERE max_oneway_run = 4)            AS oneway_run_4,
        COUNT(*) FILTER (WHERE max_oneway_run = 5)            AS oneway_run_5,
        COUNT(*) FILTER (WHERE max_oneway_run = 6)            AS oneway_run_6
FROM     dwbi_temp40_db.dcb_matrix
WHERE    ever_twoway = 0
GROUP BY pay_months
ORDER BY pay_months;

-- ---------------------------------------------------------------------------
-- G3  MATRIX 2. Payment months against two-way barred or not. Read
--     twoway_pct down the column: if it falls as pay_months rises, payment
--     behaviour is predictive of default, which is the premise of the whole
--     model.
-- ---------------------------------------------------------------------------
SELECT  pay_months,
        COUNT(*)                                              AS total,
        COUNT(*) FILTER (WHERE ever_twoway = 0)               AS never_twoway,
        COUNT(*) FILTER (WHERE ever_twoway = 1)               AS was_twoway,
        100.0 * COUNT(*) FILTER (WHERE ever_twoway = 1)
              / COUNT(*)                                      AS twoway_pct,
        COUNT(*) FILTER (WHERE n_twoway_months >= 2)          AS twoway_2plus_months,
        COUNT(*) FILTER (WHERE ever_reclaim = 1)              AS ever_reclaim
FROM     dwbi_temp40_db.dcb_matrix
GROUP BY pay_months
ORDER BY pay_months;

-- ---------------------------------------------------------------------------
-- G4  HOW THEY PAY. Payment behaviour inside each cell of Matrix 1, so the
--     population is characterised rather than just counted.
-- ---------------------------------------------------------------------------
SELECT  pay_months,
        max_oneway_run,
        COUNT(*)                                              AS n_subs,
        APPROX_PERCENTILE(paid_6m, 0.5)        / 10000         AS med_paid_6m_k,
        APPROX_PERCENTILE(paid_max_month, 0.5) / 10000         AS med_best_month_k,
        APPROX_PERCENTILE(avail_max, 0.5)      / 10000         AS med_avail_k,
        APPROX_PERCENTILE(outst_max, 0.5)      / 10000         AS med_outst_max_k,
        APPROX_PERCENTILE(CAST(tenure_m AS DOUBLE), 0.5)      AS med_tenure_m,
        100.0 * AVG(CAST(act1_any AS DOUBLE))                 AS active1_pct
FROM     dwbi_temp40_db.dcb_matrix
WHERE    ever_twoway = 0
  AND    max_oneway_run <= 3
GROUP BY pay_months, max_oneway_run
ORDER BY pay_months, max_oneway_run;

-- ---------------------------------------------------------------------------
-- G5  THE HEADLINE. Candidate good-debtor populations under tightening
--     rules, each counted against the 3,000,000 target.
-- ---------------------------------------------------------------------------
SELECT  'pay 6 of 6, never one-way, never two-way'      AS rule, COUNT(*) AS n
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months = 6 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'pay 5+ of 6, never one-way, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 5 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'pay 4+ of 6, never one-way, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 4 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'pay 4+ of 6, one-way run <= 1, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 4 AND max_oneway_run <= 1 AND ever_twoway = 0
UNION ALL
SELECT  'pay 3+ of 6, one-way run <= 1, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 3 AND max_oneway_run <= 1 AND ever_twoway = 0
UNION ALL
SELECT  'pay 3+ of 6, one-way run <= 2, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 3 AND max_oneway_run <= 2 AND ever_twoway = 0
UNION ALL
SELECT  'pay 2+ of 6, one-way run <= 2, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix
WHERE   pay_months >= 2 AND max_oneway_run <= 2 AND ever_twoway = 0
ORDER BY n DESC;

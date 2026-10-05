-- ============================================================================
--  THE SAME MATRICES ON REVENUE, AND THE TWO MEASURES COMPARED
--
--  WHY REVENUE IS A DIFFERENT QUESTION, NOT A RE-CUT
--
--  Payment misses cash. Revenue does not. Measured on the same months:
--
--      month    revenue rows   payment rows   payment coverage
--      140503     39,955,930     19,973,435        50 pct
--      140504     39,791,006     19,561,064        49 pct
--      140505     39,863,849     19,889,055        50 pct
--      140506     39,830,450     20,243,591        51 pct
--
--  About 20,000,000 subscribers a month generate value with no payment row
--  at all. That is the cash gap.
--
--  But the two also disagree in the OPPOSITE direction. Payment over 170,000
--  Toman is consistently HIGHER than revenue over 170,000 - 118, 125, 122 and
--  105 pct of it across those four months - because one payment can settle
--  several months of bills, so a monthly payment threshold over-counts where a
--  monthly revenue threshold does not.
--
--  Two independent disagreements pointing opposite ways. Neither measure is a
--  proxy for the other, which is why H6 cross-tabs them rather than assuming
--  one can stand in.
--
--  arpu IS 23.8 PCT NULL  (register item B3)
--
--  Revenue is SUM(arpu) - SUM(tot_arpu_tax_amt) per KPI_v4. Where arpu is
--  missing the tax is zero too - the two zero counts differ by 124 rows out of
--  39,830,450 - so the expression gives 0 rather than minus-the-tax. No
--  clamping is applied; H2 and H3 report the null and negative counts so the
--  effect stays visible instead of being assumed away.
--
--  Window 140501..140506, the same as the payment matrices, so the two sets
--  are directly comparable.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- H1  ONE PANEL, BOTH MEASURES. Revenue and payment months side by side, so a
--     single scan produces the revenue matrices and the comparison.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_matrix_rev;
CREATE TABLE dwbi_temp40_db.dcb_matrix_rev WITH (format='PARQUET') AS
WITH pm AS (
    SELECT   sbrp_id,
             day_key / 100                  AS month_key,
             SUM(COALESCE(pmnt_amt, 0))     AS paid
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14050101 AND 14050631
    GROUP BY sbrp_id, day_key / 100
),
pay AS (
    SELECT  sbrp_id,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140501), 0) AS q1,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140502), 0) AS q2,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140503), 0) AS q3,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140504), 0) AS q4,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140505), 0) AS q5,
            COALESCE(SUM(paid) FILTER (WHERE month_key = 140506), 0) AS q6
    FROM    pm
    GROUP BY sbrp_id
),
st AS (
    SELECT  sbrp_id,
            -- revenue per month, KPI_v4: arpu net of its tax
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140501), 0)         AS r1,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140502), 0)         AS r2,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140503), 0)         AS r3,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140504), 0)         AS r4,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140505), 0)         AS r5,
            COALESCE(SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140506), 0)         AS r6,
            -- how much of the revenue picture is missing, kept visible
            SUM(IF(arpu IS NULL, 1, 0))                            AS n_arpu_null,
            SUM(IF(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0) < 0, 1, 0))
                                                                   AS n_rev_negative,
            -- one-way bar flags, month by month
            MAX(IF(month_key = 140501 AND sbrp_stat_id = 3, 1, 0))  AS o1,
            MAX(IF(month_key = 140502 AND sbrp_stat_id = 3, 1, 0))  AS o2,
            MAX(IF(month_key = 140503 AND sbrp_stat_id = 3, 1, 0))  AS o3,
            MAX(IF(month_key = 140504 AND sbrp_stat_id = 3, 1, 0))  AS o4,
            MAX(IF(month_key = 140505 AND sbrp_stat_id = 3, 1, 0))  AS o5,
            MAX(IF(month_key = 140506 AND sbrp_stat_id = 3, 1, 0))  AS o6,
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
SELECT  s.sbrp_id, s.ever_twoway, s.n_twoway_months, s.n_oneway_months,
        s.ever_reclaim, s.avail_max, s.outst_max, s.tenure_m, s.act1_any,
        s.n_arpu_null, s.n_rev_negative,
        -- months with REVENUE at or over 170,000 Toman
        IF(s.r1 >= 1700000,1,0) + IF(s.r2 >= 1700000,1,0)
      + IF(s.r3 >= 1700000,1,0) + IF(s.r4 >= 1700000,1,0)
      + IF(s.r5 >= 1700000,1,0) + IF(s.r6 >= 1700000,1,0)          AS rev_months,
        -- months with PAYMENT at or over 170,000 Toman, for comparison
        IF(COALESCE(p.q1,0) >= 1700000,1,0) + IF(COALESCE(p.q2,0) >= 1700000,1,0)
      + IF(COALESCE(p.q3,0) >= 1700000,1,0) + IF(COALESCE(p.q4,0) >= 1700000,1,0)
      + IF(COALESCE(p.q5,0) >= 1700000,1,0) + IF(COALESCE(p.q6,0) >= 1700000,1,0)
                                                                   AS pay_months,
        GREATEST(6 * (s.o1*s.o2*s.o3*s.o4*s.o5*s.o6),
                 5 * GREATEST(s.o1*s.o2*s.o3*s.o4*s.o5, s.o2*s.o3*s.o4*s.o5*s.o6),
                 4 * GREATEST(s.o1*s.o2*s.o3*s.o4, s.o2*s.o3*s.o4*s.o5,
                              s.o3*s.o4*s.o5*s.o6),
                 3 * GREATEST(s.o1*s.o2*s.o3, s.o2*s.o3*s.o4,
                              s.o3*s.o4*s.o5, s.o4*s.o5*s.o6),
                 2 * GREATEST(s.o1*s.o2, s.o2*s.o3, s.o3*s.o4,
                              s.o4*s.o5, s.o5*s.o6),
                 1 * GREATEST(s.o1, s.o2, s.o3, s.o4, s.o5, s.o6))
                                                                   AS max_oneway_run,
        s.r1 + s.r2 + s.r3 + s.r4 + s.r5 + s.r6                    AS rev_6m,
        GREATEST(s.r1, s.r2, s.r3, s.r4, s.r5, s.r6)               AS rev_max_month,
        COALESCE(p.q1,0) + COALESCE(p.q2,0) + COALESCE(p.q3,0)
      + COALESCE(p.q4,0) + COALESCE(p.q5,0) + COALESCE(p.q6,0)     AS paid_6m,
        GREATEST(COALESCE(p.q1,0), COALESCE(p.q2,0), COALESCE(p.q3,0),
                 COALESCE(p.q4,0), COALESCE(p.q5,0), COALESCE(p.q6,0))
                                                                   AS paid_max_month
FROM        st s
LEFT JOIN   pay p ON p.sbrp_id = s.sbrp_id
;

-- ---------------------------------------------------------------------------
-- H2  MATRIX 1 ON REVENUE. Revenue months against the longest consecutive
--     one-way run, among subscribers never two-way barred.
-- ---------------------------------------------------------------------------
SELECT  rev_months,
        COUNT(*)                                        AS total,
        COUNT(*) FILTER (WHERE max_oneway_run = 0)      AS oneway_never,
        COUNT(*) FILTER (WHERE max_oneway_run = 1)      AS oneway_run_1,
        COUNT(*) FILTER (WHERE max_oneway_run = 2)      AS oneway_run_2,
        COUNT(*) FILTER (WHERE max_oneway_run = 3)      AS oneway_run_3,
        COUNT(*) FILTER (WHERE max_oneway_run = 4)      AS oneway_run_4,
        COUNT(*) FILTER (WHERE max_oneway_run = 5)      AS oneway_run_5,
        COUNT(*) FILTER (WHERE max_oneway_run = 6)      AS oneway_run_6,
        SUM(n_arpu_null)                                AS arpu_null_months,
        SUM(n_rev_negative)                             AS rev_negative_months
FROM     dwbi_temp40_db.dcb_matrix_rev
WHERE    ever_twoway = 0
GROUP BY rev_months
ORDER BY rev_months;

-- ---------------------------------------------------------------------------
-- H3  MATRIX 2 ON REVENUE. The test that matters: does twoway_pct fall as
--     rev_months rises, the way it fell from 7.0 to 0.4 pct on payment?
-- ---------------------------------------------------------------------------
SELECT  rev_months,
        COUNT(*)                                        AS total,
        COUNT(*) FILTER (WHERE ever_twoway = 0)         AS never_twoway,
        COUNT(*) FILTER (WHERE ever_twoway = 1)         AS was_twoway,
        100.0 * COUNT(*) FILTER (WHERE ever_twoway = 1)
              / COUNT(*)                                AS twoway_pct,
        COUNT(*) FILTER (WHERE n_twoway_months >= 2)    AS twoway_2plus_months,
        COUNT(*) FILTER (WHERE ever_reclaim = 1)        AS ever_reclaim,
        SUM(n_arpu_null)                                AS arpu_null_months
FROM     dwbi_temp40_db.dcb_matrix_rev
GROUP BY rev_months
ORDER BY rev_months;

-- ---------------------------------------------------------------------------
-- H4  HOW THEY EARN. Behaviour per cell, on revenue.
-- ---------------------------------------------------------------------------
SELECT  rev_months,
        max_oneway_run,
        COUNT(*)                                            AS n_subs,
        APPROX_PERCENTILE(rev_6m, 0.5)        / 10000        AS med_rev_6m_k,
        APPROX_PERCENTILE(rev_max_month, 0.5) / 10000        AS med_best_rev_k,
        APPROX_PERCENTILE(paid_6m, 0.5)       / 10000        AS med_paid_6m_k,
        APPROX_PERCENTILE(avail_max, 0.5)     / 10000        AS med_avail_k,
        APPROX_PERCENTILE(outst_max, 0.5)     / 10000        AS med_outst_max_k,
        APPROX_PERCENTILE(CAST(tenure_m AS DOUBLE), 0.5)    AS med_tenure_m,
        100.0 * AVG(CAST(act1_any AS DOUBLE))               AS active1_pct
FROM     dwbi_temp40_db.dcb_matrix_rev
WHERE    ever_twoway = 0
  AND    max_oneway_run <= 3
GROUP BY rev_months, max_oneway_run
ORDER BY rev_months, max_oneway_run;

-- ---------------------------------------------------------------------------
-- H5  THE GOOD-DEBTOR COUNTS ON REVENUE, the same rules as before so the two
--     sets can be put side by side.
-- ---------------------------------------------------------------------------
SELECT  'rev 6 of 6, never one-way, never two-way'       AS rule, COUNT(*) AS n
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months = 6 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'rev 5+ of 6, never one-way, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 5 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'rev 4+ of 6, never one-way, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 4 AND max_oneway_run = 0 AND ever_twoway = 0
UNION ALL
SELECT  'rev 4+ of 6, one-way run <= 1, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 4 AND max_oneway_run <= 1 AND ever_twoway = 0
UNION ALL
SELECT  'rev 3+ of 6, one-way run <= 1, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 3 AND max_oneway_run <= 1 AND ever_twoway = 0
UNION ALL
SELECT  'rev 3+ of 6, one-way run <= 2, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 3 AND max_oneway_run <= 2 AND ever_twoway = 0
UNION ALL
SELECT  'rev 2+ of 6, one-way run <= 2, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 2 AND max_oneway_run <= 2 AND ever_twoway = 0
UNION ALL
SELECT  'BOTH rev 5+ AND pay 5+, never one-way, never two-way', COUNT(*)
FROM    dwbi_temp40_db.dcb_matrix_rev
WHERE   rev_months >= 5 AND pay_months >= 5
  AND   max_oneway_run = 0 AND ever_twoway = 0
ORDER BY n DESC;

-- ---------------------------------------------------------------------------
-- H6  THE TWO MEASURES AGAINST EACH OTHER. The new information: how far
--     revenue and payment disagree per subscriber, and which of the two
--     separates the two-way bar better.
--
--     Read twoway_pct across the grid. If it tracks rev_months down the rows
--     regardless of pay_months, revenue is the stronger axis. If it tracks
--     pay_months across the columns, payment is. If it needs both, the model
--     needs both and that is worth knowing before features are chosen.
-- ---------------------------------------------------------------------------
SELECT  rev_months,
        pay_months,
        COUNT(*)                                        AS n_subs,
        100.0 * COUNT(*) FILTER (WHERE ever_twoway = 1)
              / COUNT(*)                                AS twoway_pct,
        APPROX_PERCENTILE(rev_6m, 0.5)  / 10000         AS med_rev_6m_k,
        APPROX_PERCENTILE(paid_6m, 0.5) / 10000         AS med_paid_6m_k
FROM     dwbi_temp40_db.dcb_matrix_rev
GROUP BY rev_months, pay_months
ORDER BY rev_months, pay_months;

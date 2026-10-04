-- ============================================================================
--  THE NEW QUESTION, ANSWERED BEFORE ANY MODEL IS BUILT      (Trino/Presto)
--
--  Target: find at least 3,000,000 subscribers out of the permanent base who
--  will pay at least 170,000 Toman in EACH of the next 4 months.
--
--  This is a different label from y_severe. y_severe asks "will they go to a
--  two-way bar", which is default. This asks "will they pay the instalment",
--  which is what the product actually needs. A 500,000 Toman loan over 4
--  instalments with a 4 pct fee is 520,000 repaid, 130,000 per month, so a
--  subscriber paying 170,000 per month carries the instalment with about
--  40,000 left for their own usage.
--
--  ASSUMPTION STATED, NOT BURIED: the 170,000 is read as TOTAL monthly
--  payment, not as 130,000 of instalment on top of an unchanged bill. The
--  conservative reading. Say so if it is meant the other way and S3 changes.
--
--  FIVE CANDIDATE LABELS, NOT ONE. WHY.
--
--  "Pays at least 170,000 in EVERY one of the four months" is decided by the
--  subscriber's worst month. That is strict in a way the product is not: the
--  operator needs 520,000 collected over four months, not 130,000 collected
--  in each of four particular months. Someone who pays 50,000 in month one
--  and 250,000 in month two has paid their instalments and the operator is
--  whole. Telco payment is lumpy by nature - packages, cash top-ups, a month
--  away - so a monthly floor punishes ordinary lumpiness as if it were
--  default. This project has already paid for that mistake once: n_late_out
--  >= 2 produced a 36 pct bad rate that turned out to be normal behaviour.
--
--  So S2 carries all five and S3 reports them side by side:
--
--    y_min170    MIN of the four months >= 170,000     strictest
--    y_3of4_170  at least 3 of the 4 months >= 170,000 tolerates one bad month
--    y_avg170    the four-month total >= 680,000       the average reading
--    y_repaid    the four-month total >= 520,000       what the loan needs
--    y_min130    MIN of the four months >= 130,000     instalment, no headroom
--
--  y_repaid is the loosest label that still means the operator got its money,
--  which makes it the honest default. The others are there so the volume each
--  one reaches is a measured number: pick the strictest label that still
--  clears 3,000,000, because every loosening makes a positive prediction mean
--  less.
--
--  WHAT THIS FILE IS FOR
--
--  Before a model is worth building, three numbers decide everything:
--
--    1. How many subscribers pass the stated rule - paid at least 200,000 in
--       each of the last 3 months.
--    2. What share of THOSE go on to pay 170,000 in each of the next 4.
--       That share is the rule's precision, and it is the number any model
--       must beat. If the rule is already at 95 pct, a model adds nothing.
--    3. How many subscribers the rule MISSES who would have paid. Those are
--       what a model is actually for.
--
--  S1 also reports the payment status codes and the population at each filter
--  level, so two open questions get answered from the data instead of assumed:
--  which bllg_pmnt_stat_id values are real payments, and where the permanent
--  base of about 24,000,000 becomes the 11,567,908 the current pipeline scores.
--
--  CALENDAR.  Payments are continuous and complete 140301..140506.
--    T0             = 140503
--    rule window    = 140412, 140501, 140502          (3 months before T0)
--    outcome window = 140503, 140504, 140505, 140506  (4 months from T0)
--  Month 12 of 1404 has 29 days, so the day range is 14041201..14050631.
--  The months are written out one by one. Month arithmetic does not work
--  across a Jalali year end - 140412 plus one is 140501, not 140413.
--
--  A MONTH WITH NO PAYMENT ROW MEANS THEY PAID NOTHING, NOT "UNKNOWN". Each
--  month is COALESCEd to 0 before LEAST() takes the minimum. Letting a
--  missing month arrive as NULL would make LEAST() return NULL and quietly
--  drop that subscriber from both the numerator and the denominator.
--
--  POPULATION GATE, PER KPI_v4 RATHER THAN PER THE OLD PIPELINE.
--
--  KPI_v4 defines Active1 on v_fact_sbrp_mthly_cip as active1_base_flag = 1,
--  and states that with it the sbrp_stat_id condition is no longer needed.
--  The existing pipeline uses sbrp_stat_id = 2 and never references
--  active1_base_flag at all, so it has not been applying the house
--  definition. This file uses active1_base_flag = 1 and reports both counts
--  side by side in S1, so the difference is a measured number rather than a
--  choice made quietly.
--
--  KPI_v4 also defines Active3 as the same conditions held for 3 months,
--  which is exactly the shape of the stated eligibility rule.
--
--  REVENUE, ALSO PER KPI_v4: total revenue is SUM(arpu) - SUM(tot_arpu_tax_amt),
--  with neither active1_base_flag nor sbrp_stat_id applied. The pipeline's
--  rev_3m instead hand-assembles voice, SMS and data revenue columns net of
--  tax and roaming. Both are reported in S1 so the gap is visible before
--  either is trusted.
--
--  NO percent character anywhere. NO CASE expressions.
--  Run S1, then S2, then S3.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S1  DIAGNOSTICS. Run this first - it settles two assumptions.
--
--     (a) Payment rows by status code. The pipeline filters
--         bllg_pmnt_stat_id = 2 for "successful", carried over from an older
--         query and never verified. If other codes also carry real money,
--         every payment feature and the whole new label are understated.
--     (b) The permanent base at each filter level, so the gap between the
--         24,000,000 figure and the 11,567,908 currently scored is visible
--         rather than argued about.
-- ---------------------------------------------------------------------------
SELECT  'payment status' AS what,
        CAST(bllg_pmnt_stat_id AS VARCHAR) AS bucket,
        COUNT(*)                           AS n_rows,
        SUM(COALESCE(pmnt_amt, 0)) / 1e9   AS amount_bn_rial,
        COUNT(DISTINCT sbrp_id)            AS n_subscribers
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14050101 AND 14050631
GROUP BY bllg_pmnt_stat_id
ORDER BY n_rows DESC;

SELECT  'permanent base at 140502' AS what,
        COUNT(*)                                                  AS all_rows,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1)                   AS permanent,
        -- the house definition (KPI_v4 Active1)
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND active1_base_flag = 1)             AS perm_active1,
        -- what the existing pipeline uses instead
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND sbrp_stat_id = 2)                  AS perm_stat2,
        -- the overlap, and each side's exclusive part. If active1_base_flag
        -- and sbrp_stat_id = 2 disagree for a large group, every count this
        -- project has produced is against a population nobody else uses.
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND active1_base_flag = 1
                           AND sbrp_stat_id = 2)                  AS both,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND active1_base_flag = 1
                           AND sbrp_stat_id <> 2)                 AS active1_not_stat2,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND COALESCE(active1_base_flag, 0) <> 1
                           AND sbrp_stat_id = 2)                  AS stat2_not_active1,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND active1_base_flag = 1
                           AND COALESCE(age_on_net_months, 0) >= 12)
                                                                  AS active1_12m,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND sbrp_stat_id IN (3, 4))            AS perm_barred,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND sbrp_stat_id IN (8, 9))            AS perm_reclamation
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140502;

-- The two revenue definitions, on the same rows. KPI_v4: total revenue is
-- arpu net of tot_arpu_tax_amt. The pipeline's floor of 1,000,000 Rial per
-- month was set against its own hand-built sum, so if the two differ the
-- floor is not cutting where it was believed to cut.
SELECT  'revenue definitions, 140502' AS what,
        COUNT(*)                                             AS n,
        SUM(COALESCE(arpu, 0)) / 1e9                         AS arpu_bn,
        SUM(COALESCE(tot_arpu_tax_amt, 0)) / 1e9             AS arpu_tax_bn,
        (SUM(COALESCE(arpu, 0))
         - SUM(COALESCE(tot_arpu_tax_amt, 0))) / 1e9         AS kpi_revenue_bn,
        APPROX_PERCENTILE(COALESCE(arpu, 0)
                          - COALESCE(tot_arpu_tax_amt, 0), 0.5) AS kpi_rev_median,
        COUNT(*) FILTER (WHERE COALESCE(arpu, 0)
                             - COALESCE(tot_arpu_tax_amt, 0) > 1000000)
                                                             AS over_the_1m_floor
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key   = 140502
  AND   sbrp_typ_id = 1;

-- ---------------------------------------------------------------------------
-- S2  BUILD IT. One row per permanent subscriber active the month before T0,
--     with the seven monthly payment totals, the rule minimum and the
--     outcome minimum.
--
--     No revenue floor and no tenure gate here on purpose. The question is
--     "how many of the WHOLE permanent base qualify", so the floors that cut
--     24,000,000 down to 11,567,908 are left out and their effect is measured
--     in S3 instead of assumed.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_paycap;
CREATE TABLE dwbi_temp40_db.dcb_paycap WITH (format='PARQUET') AS
WITH base AS (
    -- KPI_v4 Active1: active1_base_flag = 1, which makes sbrp_stat_id
    -- redundant. Not the pipeline's sbrp_stat_id = 2.
    SELECT  sbrp_id,
            COALESCE(age_on_net_months, 0) AS tenure_m
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key         = 140502
      AND   sbrp_typ_id       = 1
      AND   active1_base_flag = 1
),
act3 AS (
    -- KPI_v4 Active3: the Active1 conditions held in all three months. Kept
    -- as a flag rather than a filter, so S3 can measure what it costs.
    SELECT   sbrp_id
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140412, 140501, 140502)
      AND    sbrp_typ_id       = 1
      AND    active1_base_flag = 1
    GROUP BY sbrp_id
    HAVING   COUNT(DISTINCT month_key) = 3
),
rev AS (
    -- KPI_v4 revenue: arpu net of tot_arpu_tax_amt. Kept as a COLUMN so the
    -- pipeline's 1,000,000 floor can be measured in S3 rather than deciding
    -- the population here.
    SELECT   sbrp_id,
             (SUM(COALESCE(arpu, 0))
              - SUM(COALESCE(tot_arpu_tax_amt, 0))) / 3 AS rev_avg_3m
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140412, 140501, 140502)
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
pm AS (
    SELECT   sbrp_id,
             day_key / 100                    AS month_key,
             SUM(COALESCE(pmnt_amt, 0))       AS paid
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    bllg_pmnt_stat_id = 2
      AND    day_key BETWEEN 14041201 AND 14050631
    GROUP BY sbrp_id, day_key / 100
),
wide AS (
    SELECT  b.sbrp_id,
            b.tenure_m,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140412), 0) AS m1,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140501), 0) AS m2,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140502), 0) AS m3,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140503), 0) AS o1,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140504), 0) AS o2,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140505), 0) AS o3,
            COALESCE(SUM(p.paid) FILTER (WHERE p.month_key = 140506), 0) AS o4
    FROM        base b
    LEFT JOIN   pm p ON p.sbrp_id = b.sbrp_id
    GROUP BY    b.sbrp_id, b.tenure_m
)
SELECT  w.sbrp_id,
        w.tenure_m,
        IF(a3.sbrp_id IS NULL, 0, 1)              AS is_active3,
        COALESCE(r.rev_avg_3m, 0)                 AS rev_avg_3m,
        w.m1, w.m2, w.m3,
        w.o1, w.o2, w.o3, w.o4,
        -- the rule: the WORST of the three months before T0
        LEAST(w.m1, w.m2, w.m3)                   AS min_pre3,
        -- the outcome: the WORST of the four months after T0. The worst month
        -- is what matters - an average lets one big month carry three empty
        -- ones, and an instalment is missed in the month it is missed.
        LEAST(w.o1, w.o2, w.o3, w.o4)             AS min_post4,
        (w.m1 + w.m2 + w.m3) / 3                  AS avg_pre3,
        (w.o1 + w.o2 + w.o3 + w.o4) / 4           AS avg_post4,
        w.o1 + w.o2 + w.o3 + w.o4                 AS sum_post4,
        -- how many of the four months cleared 170,000 Toman
        IF(w.o1 >= 1700000, 1, 0) + IF(w.o2 >= 1700000, 1, 0)
      + IF(w.o3 >= 1700000, 1, 0) + IF(w.o4 >= 1700000, 1, 0)
                                                  AS n_months_over_170k,
        -- the five candidate labels, so S3 compares rather than assumes
        IF(LEAST(w.o1, w.o2, w.o3, w.o4) >= 1700000, 1, 0)      AS y_min170,
        IF(IF(w.o1 >= 1700000, 1, 0) + IF(w.o2 >= 1700000, 1, 0)
         + IF(w.o3 >= 1700000, 1, 0) + IF(w.o4 >= 1700000, 1, 0)
           >= 3, 1, 0)                                          AS y_3of4_170,
        IF(w.o1 + w.o2 + w.o3 + w.o4 >= 6800000, 1, 0)          AS y_avg170,
        IF(w.o1 + w.o2 + w.o3 + w.o4 >= 5200000, 1, 0)          AS y_repaid,
        IF(LEAST(w.o1, w.o2, w.o3, w.o4) >= 1300000, 1, 0)      AS y_min130
FROM    wide w
LEFT JOIN rev  r  ON r.sbrp_id  = w.sbrp_id
LEFT JOIN act3 a3 ON a3.sbrp_id = w.sbrp_id
;

-- ---------------------------------------------------------------------------
-- S3  THE ANSWER. One row per candidate label, so the choice is arithmetic.
--
--     Read `n_positive` against the 3,000,000 target first: any label whose
--     n_positive is below it cannot reach the goal no matter how good the
--     model is, because the people simply are not there.
--
--     Then read `rule_precision_pct` - the share of the stated eligibility
--     rule's population that satisfies the label. That is what a model has
--     to beat. `missed` is the subscribers the rule rejects who satisfy the
--     label anyway, and it is the only place a model can add volume.
--
--     Pick the STRICTEST label that still clears 3,000,000. Every loosening
--     buys volume by making a positive prediction mean less.
-- ---------------------------------------------------------------------------
SELECT  label,
        COUNT(*)                                            AS population,
        SUM(y)                                              AS n_positive,
        100.0 * SUM(y) / COUNT(*)                           AS base_rate_pct,
        COUNT(*) FILTER (WHERE min_pre3 >= 2000000)         AS rule_200k_3m,
        SUM(y) FILTER (WHERE min_pre3 >= 2000000)           AS rule_and_label,
        100.0 * SUM(y) FILTER (WHERE min_pre3 >= 2000000)
              / NULLIF(COUNT(*) FILTER (WHERE min_pre3 >= 2000000), 0)
                                                            AS rule_precision_pct,
        SUM(y) FILTER (WHERE min_pre3 < 2000000)            AS missed,
        100.0 * SUM(y) FILTER (WHERE min_pre3 >= 2000000)
              / NULLIF(SUM(y), 0)                           AS rule_recall_pct
FROM (
    SELECT  min_pre3, 'y_min170'   AS label, y_min170   AS y FROM dwbi_temp40_db.dcb_paycap
    UNION ALL
    SELECT  min_pre3, 'y_3of4_170' AS label, y_3of4_170 AS y FROM dwbi_temp40_db.dcb_paycap
    UNION ALL
    SELECT  min_pre3, 'y_avg170'   AS label, y_avg170   AS y FROM dwbi_temp40_db.dcb_paycap
    UNION ALL
    SELECT  min_pre3, 'y_repaid'   AS label, y_repaid   AS y FROM dwbi_temp40_db.dcb_paycap
    UNION ALL
    SELECT  min_pre3, 'y_min130'   AS label, y_min130   AS y FROM dwbi_temp40_db.dcb_paycap
) u
GROUP BY label
ORDER BY n_positive DESC;

-- How many of the four months each subscriber clears, so the shape of the
-- lumpiness is visible rather than assumed. If most of the base clears 3 or
-- 4 months, y_min170 is not costing much and should be kept. If the mass
-- sits at 2, the monthly floor is what is rejecting them, not their capacity.
SELECT  n_months_over_170k,
        COUNT(*)                                       AS n_subscribers,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()       AS share_pct,
        APPROX_PERCENTILE(sum_post4, 0.5) / 10000      AS median_4m_total_k_toman,
        COUNT(*) FILTER (WHERE sum_post4 >= 5200000)   AS also_repaid_520k
FROM        dwbi_temp40_db.dcb_paycap
GROUP BY    n_months_over_170k
ORDER BY    n_months_over_170k;

-- How the rule threshold trades volume against precision. The stated rule is
-- the 2000000 row. Note what the revenue floor and the tenure gate cost.
SELECT  thr / 10000                                              AS rule_thousand_toman,
        COUNT(*) FILTER (WHERE min_pre3 >= thr)                  AS passes,
        COUNT(*) FILTER (WHERE min_pre3 >= thr
                           AND min_post4 >= 1700000)             AS passes_and_pays,
        100.0 * COUNT(*) FILTER (WHERE min_pre3 >= thr
                                   AND min_post4 >= 1700000)
              / NULLIF(COUNT(*) FILTER (WHERE min_pre3 >= thr), 0)
                                                                 AS precision_pct,
        COUNT(*) FILTER (WHERE min_pre3 >= thr
                           AND rev_avg_3m > 1000000)             AS also_over_rev_floor,
        COUNT(*) FILTER (WHERE min_pre3 >= thr
                           AND tenure_m >= 12)                   AS also_12m_tenure,
        COUNT(*) FILTER (WHERE min_pre3 >= thr
                           AND is_active3 = 1)                   AS also_active3
FROM        dwbi_temp40_db.dcb_paycap
CROSS JOIN  UNNEST(ARRAY[1000000, 1500000, 1700000, 2000000,
                         2500000, 3000000, 4000000]) AS t (thr)
GROUP BY    thr
ORDER BY    thr;

-- Where the payers sit, so the 3,000,000 target can be read off directly.
SELECT  APPROX_PERCENTILE(min_pre3,  0.50) / 10000 AS p50_min_pre3_k_toman,
        APPROX_PERCENTILE(min_pre3,  0.75) / 10000 AS p75_min_pre3_k_toman,
        APPROX_PERCENTILE(min_pre3,  0.90) / 10000 AS p90_min_pre3_k_toman,
        APPROX_PERCENTILE(min_post4, 0.50) / 10000 AS p50_min_post4_k_toman,
        APPROX_PERCENTILE(min_post4, 0.75) / 10000 AS p75_min_post4_k_toman,
        APPROX_PERCENTILE(min_post4, 0.90) / 10000 AS p90_min_post4_k_toman,
        COUNT(*) FILTER (WHERE min_post4 >= 1300000)  AS pays_130k_instalment_only,
        COUNT(*) FILTER (WHERE min_post4 >= 1700000)  AS pays_170k,
        COUNT(*) FILTER (WHERE min_post4 >= 2000000)  AS pays_200k
FROM    dwbi_temp40_db.dcb_paycap;

-- ============================================================================
--  FOUR THINGS, AND WHY EACH ONE                            (Trino/Presto)
--
--  A  column health - which features are actually populated         ~100 rows
--  B  revenue and payment distribution, per month                     ~4 rows
--  C  the months-over-threshold cross-tab, revenue against payment   ~25 rows
--  D  a stratified sample with weights                           ~60,000 rows
--
--  A, B and C are small enough to paste. D is a file.
--
--  NO IDENTITIES LEAVE. D replaces sbrp_id with a truncated hash. It is
--  stable, so rows can be re-identified on your side, and it is one way, so
--  it tells me nothing about who anyone is. I do not need to know.
--
--  WHY A MATTERS MOST
--
--  This project has lost more time to NULLs than to anything else:
--  mc_billed_6m entirely NULL because a bill filter matched zero rows,
--  age_on_net_months NULL for part of the base so a tenure test silently
--  deleted the wrong people, proven_capacity carrying a NaN that turns into a
--  silent rejection, n_payments_6m missing because a column was commented out
--  to get a CREATE TABLE to run. Every one of those was found late, by
--  accident, after it had already changed a result. A is one query that would
--  have caught all four.
--
--  WHY D IS STRATIFIED AND NOT RANDOM
--
--  A uniform sample is almost entirely low-revenue subscribers, because that
--  is where the mass is - and the 3,000,000 we are looking for live in the
--  tail. So the tail is sampled far more heavily and each row carries the
--  weight it stands for, which lets population totals be reconstructed
--  exactly. Without the weight a model trained on this sample would think
--  the base is far richer than it is.
--
--  CALENDAR. Four complete months, 140503..140506, and the three before them
--  for the rule window. Jalali months are written out: 140412 plus one is
--  140501, not 140413.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A  COLUMN HEALTH on the subscriber monthly fact. One row per column that
--    matters, saying how much of it is actually there.
--
--    Read null_pct first. Anything above 0 on a column the model uses needs a
--    decision before the model is built, not after.
-- ---------------------------------------------------------------------------
SELECT  'arpu'                AS col,
        COUNT(*)              AS n_rows,
        COUNT(arpu)           AS n_nonnull,
        100.0 * (COUNT(*) - COUNT(arpu)) / COUNT(*)        AS null_pct,
        COUNT(*) FILTER (WHERE COALESCE(arpu,0) = 0)       AS n_zero,
        APPROX_PERCENTILE(arpu, 0.5)                       AS p50,
        MIN(arpu) AS v_min, MAX(arpu) AS v_max
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'tot_arpu_tax_amt', COUNT(*), COUNT(tot_arpu_tax_amt),
        100.0 * (COUNT(*) - COUNT(tot_arpu_tax_amt)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(tot_arpu_tax_amt,0) = 0),
        APPROX_PERCENTILE(tot_arpu_tax_amt, 0.5),
        MIN(tot_arpu_tax_amt), MAX(tot_arpu_tax_amt)
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'active1_base_flag', COUNT(*), COUNT(active1_base_flag),
        100.0 * (COUNT(*) - COUNT(active1_base_flag)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(active1_base_flag,0) = 0),
        APPROX_PERCENTILE(CAST(active1_base_flag AS DOUBLE), 0.5),
        MIN(CAST(active1_base_flag AS DOUBLE)), MAX(CAST(active1_base_flag AS DOUBLE))
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'age_on_net_months', COUNT(*), COUNT(age_on_net_months),
        100.0 * (COUNT(*) - COUNT(age_on_net_months)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(age_on_net_months,0) = 0),
        APPROX_PERCENTILE(CAST(age_on_net_months AS DOUBLE), 0.5),
        MIN(CAST(age_on_net_months AS DOUBLE)), MAX(CAST(age_on_net_months AS DOUBLE))
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'available_credit', COUNT(*), COUNT(available_credit),
        100.0 * (COUNT(*) - COUNT(available_credit)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(available_credit,0) = 0),
        APPROX_PERCENTILE(available_credit, 0.5),
        MIN(available_credit), MAX(available_credit)
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'debt_scr', COUNT(*), COUNT(debt_scr),
        100.0 * (COUNT(*) - COUNT(debt_scr)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(debt_scr,0) = 0),
        APPROX_PERCENTILE(CAST(debt_scr AS DOUBLE), 0.5),
        MIN(CAST(debt_scr AS DOUBLE)), MAX(CAST(debt_scr AS DOUBLE))
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1
UNION ALL
SELECT  'suspend_scr', COUNT(*), COUNT(suspend_scr),
        100.0 * (COUNT(*) - COUNT(suspend_scr)) / COUNT(*),
        COUNT(*) FILTER (WHERE COALESCE(suspend_scr,0) = 0),
        APPROX_PERCENTILE(CAST(suspend_scr AS DOUBLE), 0.5),
        MIN(CAST(suspend_scr AS DOUBLE)), MAX(CAST(suspend_scr AS DOUBLE))
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506 AND sbrp_typ_id = 1;

-- debt_scr and suspend_scr came back with PSI of 13.9 and 14.4 between the
-- training and scoring windows, which is far too much to be drift. This asks
-- the same question across months: if either is null or constant in one month
-- and populated in another, that is the whole explanation.
SELECT  month_key,
        COUNT(*)                                      AS n,
        COUNT(debt_scr)                               AS debt_scr_nonnull,
        COUNT(DISTINCT debt_scr)                      AS debt_scr_distinct,
        APPROX_PERCENTILE(CAST(debt_scr AS DOUBLE), 0.5)    AS debt_scr_p50,
        COUNT(suspend_scr)                            AS suspend_scr_nonnull,
        COUNT(DISTINCT suspend_scr)                   AS suspend_scr_distinct,
        APPROX_PERCENTILE(CAST(suspend_scr AS DOUBLE), 0.5) AS suspend_scr_p50
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key IN (140409, 140410, 140411, 140412,
                      140501, 140502, 140503, 140504, 140505, 140506)
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;

-- ---------------------------------------------------------------------------
-- B  REVENUE AND PAYMENT DISTRIBUTION, per month. Per month rather than
--    pooled, so a partly loaded month is visible before it is averaged away -
--    an unloaded window is what once reduced the base to 1,371 rows.
-- ---------------------------------------------------------------------------
SELECT  'revenue' AS measure, month_key,
        COUNT(*)                                             AS n,
        APPROX_PERCENTILE(v, 0.10) / 10000                   AS p10_k_toman,
        APPROX_PERCENTILE(v, 0.25) / 10000                   AS p25_k_toman,
        APPROX_PERCENTILE(v, 0.50) / 10000                   AS p50_k_toman,
        APPROX_PERCENTILE(v, 0.75) / 10000                   AS p75_k_toman,
        APPROX_PERCENTILE(v, 0.90) / 10000                   AS p90_k_toman,
        APPROX_PERCENTILE(v, 0.95) / 10000                   AS p95_k_toman,
        APPROX_PERCENTILE(v, 0.99) / 10000                   AS p99_k_toman,
        COUNT(*) FILTER (WHERE v >= 1300000)                 AS n_over_130k,
        COUNT(*) FILTER (WHERE v >= 1700000)                 AS n_over_170k,
        COUNT(*) FILTER (WHERE v >= 2000000)                 AS n_over_200k,
        COUNT(*) FILTER (WHERE v >= 3000000)                 AS n_over_300k
FROM (
    SELECT  month_key,
            COALESCE(arpu, 0) - COALESCE(tot_arpu_tax_amt, 0) AS v
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140503, 140504, 140505, 140506)
      AND   sbrp_typ_id = 1
) r
GROUP BY month_key
UNION ALL
SELECT  'payment', month_key, COUNT(*),
        APPROX_PERCENTILE(v, 0.10) / 10000, APPROX_PERCENTILE(v, 0.25) / 10000,
        APPROX_PERCENTILE(v, 0.50) / 10000, APPROX_PERCENTILE(v, 0.75) / 10000,
        APPROX_PERCENTILE(v, 0.90) / 10000, APPROX_PERCENTILE(v, 0.95) / 10000,
        APPROX_PERCENTILE(v, 0.99) / 10000,
        COUNT(*) FILTER (WHERE v >= 1300000), COUNT(*) FILTER (WHERE v >= 1700000),
        COUNT(*) FILTER (WHERE v >= 2000000), COUNT(*) FILTER (WHERE v >= 3000000)
FROM (
    SELECT   day_key / 100 AS month_key, SUM(COALESCE(pmnt_amt, 0)) AS v
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14050301 AND 14050631
    GROUP BY sbrp_id, day_key / 100
) p
GROUP BY month_key
ORDER BY measure, month_key;

-- the payment status codes, which decide whether the bllg_pmnt_stat_id = 2
-- filter carried through the whole project is right
SELECT  bllg_pmnt_stat_id,
        COUNT(*)                            AS n_rows,
        COUNT(DISTINCT sbrp_id)             AS n_subs,
        SUM(COALESCE(pmnt_amt, 0)) / 1e9    AS amt_bn_rial
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14050301 AND 14050631
GROUP BY bllg_pmnt_stat_id
ORDER BY n_rows DESC;

-- ---------------------------------------------------------------------------
-- C  THE CROSS-TAB. How many of the four months each subscriber clears
--    170,000 Toman on revenue, against how many on payment. Needs 32_'s
--    dcb_revdist table - run that first.
--
--    This is the single most informative table in the whole exercise. The
--    diagonal is where capacity and collection agree. The rows where
--    months_rev is high and months_pay is low are subscribers who can afford
--    the service but have never been billed and collected from at that level,
--    and they are the risk the model exists to sort.
-- ---------------------------------------------------------------------------
SELECT  months_rev,
        months_pay,
        COUNT(*)                                        AS n_subscribers,
        APPROX_PERCENTILE(rev_avg, 0.5) / 10000         AS median_rev_k_toman,
        APPROX_PERCENTILE(pay_avg, 0.5) / 10000         AS median_pay_k_toman
FROM (
    SELECT  IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
          + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0)   AS months_rev,
            IF(q1 >= 1700000,1,0) + IF(q2 >= 1700000,1,0)
          + IF(q3 >= 1700000,1,0) + IF(q4 >= 1700000,1,0)   AS months_pay,
            (r1 + r2 + r3 + r4) / 4                         AS rev_avg,
            (q1 + q2 + q3 + q4) / 4                         AS pay_avg
    FROM    dwbi_temp40_db.dcb_revdist
) t
GROUP BY months_rev, months_pay
ORDER BY months_rev, months_pay;

-- ---------------------------------------------------------------------------
-- D  THE SAMPLE. Stratified on revenue, weighted, identities hashed.
--
--    A FIXED COUNT PER STRATUM, not a fixed rate. Rates were tried first and
--    were a guess: against a 24,000,000 base the ones I picked would have
--    returned about 2,100,000 rows, 36 times the target, because I had no
--    distribution to set them from - which is the same distribution B exists
--    to measure. ROW_NUMBER takes 15,000 from each stratum whatever the
--    shape turns out to be, and the weight is then computed from the real
--    counts rather than assumed.
--
--    sample_weight is how many population subscribers each row stands for, so
--    SUM(sample_weight) reconstructs the population exactly and any rate
--    computed with it is a population rate.
--
--    USE sample_weight IN EVERY AGGREGATE AND EVERY FIT. Without it this
--    sample says the base earns far more than it does, because the tail is
--    deliberately over-represented.
--
--    The draw is MOD on a HASH of sbrp_id, not on sbrp_id itself: an id with
--    structure in its low digits - a prefix, a check digit, an operator code -
--    would make MOD(sbrp_id, n) select a biased slice rather than a random
--    one, and silently.
-- ---------------------------------------------------------------------------
WITH banded AS (
    SELECT  sbrp_id, act1_any, act1_all4,
            r1, r2, r3, r4, q1, q2, q3, q4, q1a, q2a, q3a, q4a,
            IF((r1 + r2 + r3 + r4) / 4 >= 3000000, 4,
               IF((r1 + r2 + r3 + r4) / 4 >= 1700000, 3,
                  IF((r1 + r2 + r3 + r4) / 4 >= 1000000, 2, 1))) AS stratum,
            MOD(ABS(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
                CAST(sbrp_id AS VARCHAR))))), 1000000)           AS draw
    FROM    dwbi_temp40_db.dcb_revdist
),
sized AS (
    SELECT   stratum, COUNT(*) AS stratum_pop
    FROM     banded
    GROUP BY stratum
),
picked AS (
    SELECT  b.*,
            ROW_NUMBER() OVER (PARTITION BY b.stratum ORDER BY b.draw) AS rn
    FROM    banded b
)
SELECT  SUBSTR(TO_HEX(MD5(TO_UTF8(CAST(p.sbrp_id AS VARCHAR)))), 1, 16) AS id_hash,
        p.act1_any,
        p.act1_all4,
        p.r1, p.r2, p.r3, p.r4,
        p.q1, p.q2, p.q3, p.q4,
        p.q1a, p.q2a, p.q3a, p.q4a,
        p.stratum,
        z.stratum_pop,
        -- measured, not assumed: the stratum's real size over the rows taken
        CAST(z.stratum_pop AS DOUBLE)
          / LEAST(15000, z.stratum_pop)                          AS sample_weight
FROM        picked p
INNER JOIN  sized  z ON z.stratum = p.stratum
WHERE       p.rn <= 15000
;

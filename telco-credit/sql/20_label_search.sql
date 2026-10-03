-- ============================================================================
--  FIND A LABEL IN THE 5-15 PCT BAND                       (Trino/Presto)
--
--  THE PROBLEM THE BAD RATES EXPOSED. Nothing lands between 2.2 pct and
--  34.7 pct. The variants are bimodal:
--      y_twoway_2m   1.16      y_severe  2.22      y_strict  1.22
--      y_v2         34.74      y_v1     36.11      y_loose  36.11
--
--  AND WHY. late>=2 gives 36.11 pct, late>=3 gives 34.74 pct, and
--  exactly-one-late is 0.22 pct. So n_late_out is almost never 1 or 2 - whoever
--  is late is late NEARLY EVERY MONTH. The day 24-26 probe is firing on
--  subscribers who habitually settle after the 15th but before month end. For a
--  telco that is ordinary behaviour, not credit deterioration: the enforcement
--  mechanism is the credit ceiling, not the due date, so paying ten days late
--  every month costs the subscriber nothing and says little about a loan.
--
--  max_dpd_out is the better instrument because it measures PERSISTENCE - how
--  long a debt stayed open - rather than whether a cutoff day caught it.
--
--  No re-extraction is needed: every ingredient is already in the dataset.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- L1  how lateness and DPD are actually distributed. This is the shape that
--     decides which threshold can land in the band.
-- ---------------------------------------------------------------------------
SELECT  n_late_out,
        COUNT(*)                                             AS n,
        AVG(max_dpd_out)                                     AS avg_dpd,
        APPROX_PERCENTILE(max_dpd_out, 0.5)                  AS dpd_p50,
        APPROX_PERCENTILE(max_dpd_out, 0.9)                  AS dpd_p90,
        AVG(total_debt_days_out)                             AS avg_debt_days,
        AVG(y_severe)                                        AS rate_twoway
FROM    dwbi_temp40_db.dcb3_dataset_c1
GROUP BY n_late_out
ORDER BY n_late_out;


-- ---------------------------------------------------------------------------
-- L2  THE CANDIDATE GRID. One row. Every count is a candidate bad definition,
--     so read off whichever lands between 5 and 15 pct of 9,241,763.
--     5 pct  =   462,088
--     10 pct =   924,176
--     15 pct = 1,386,264
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                                  AS n_total,
        -- DPD thresholds, the preferred instrument
        COUNT(*) FILTER (WHERE max_dpd_out >= 10)                 AS dpd_10,
        COUNT(*) FILTER (WHERE max_dpd_out >= 15)                 AS dpd_15,
        COUNT(*) FILTER (WHERE max_dpd_out >= 20)                 AS dpd_20,
        COUNT(*) FILTER (WHERE max_dpd_out >= 30)                 AS dpd_30,
        COUNT(*) FILTER (WHERE max_dpd_out >= 45)                 AS dpd_45,
        COUNT(*) FILTER (WHERE max_dpd_out >= 60)                 AS dpd_60,
        COUNT(*) FILTER (WHERE max_dpd_out >= 90)                 AS dpd_90,
        -- chronic lateness, at the high end where the mass actually is
        COUNT(*) FILTER (WHERE n_late_out >= 4)                   AS late_4,
        COUNT(*) FILTER (WHERE n_late_out >= 5)                   AS late_5,
        COUNT(*) FILTER (WHERE n_late_out >= 6)                   AS late_6,
        -- total time in debt across the window
        COUNT(*) FILTER (WHERE total_debt_days_out >= 60)         AS debtdays_60,
        COUNT(*) FILTER (WHERE total_debt_days_out >= 90)         AS debtdays_90,
        COUNT(*) FILTER (WHERE total_debt_days_out >= 120)        AS debtdays_120,
        -- bars
        COUNT(*) FILTER (WHERE twoway_days_out > 0)               AS any_twoway,
        COUNT(*) FILTER (WHERE twoway_months_out >= 2)            AS twoway_2m,
        -- combinations: persistence OR severity
        COUNT(*) FILTER (WHERE max_dpd_out >= 30
                            OR twoway_days_out > 0)               AS dpd30_or_twoway,
        COUNT(*) FILTER (WHERE max_dpd_out >= 45
                            OR twoway_days_out > 0)               AS dpd45_or_twoway,
        COUNT(*) FILTER (WHERE max_dpd_out >= 30 AND n_late_out >= 4)
                                                                  AS dpd30_and_late4,
        COUNT(*) FILTER (WHERE total_debt_days_out >= 90
                            OR twoway_days_out > 0)               AS debt90_or_twoway
FROM    dwbi_temp40_db.dcb3_dataset_c1;


-- ---------------------------------------------------------------------------
-- L3  DOES THE CANDIDATE RANK RISK, or just count habits? A usable label must
--     show a clear gradient against something it was NOT built from.
--     proven_capacity and the ceiling are independent of payment timing, so if
--     the bad rate does not move across their quartiles the label is noise.
--     MOD(...,4) buckets by capacity rank without needing NTILE in a filter.
-- ---------------------------------------------------------------------------
SELECT  cap_q,
        COUNT(*)                                             AS n,
        AVG(IF(max_dpd_out >= 30, 1, 0))                     AS bad_dpd30,
        AVG(IF(max_dpd_out >= 45, 1, 0))                     AS bad_dpd45,
        AVG(y_severe)                                        AS bad_twoway,
        AVG(y_v1)                                            AS bad_v1,
        AVG(proven_capacity)                                 AS avg_capacity,
        AVG(ceiling_utilisation)                             AS avg_ceiling_util
FROM (
    SELECT  max_dpd_out, y_severe, y_v1, proven_capacity, ceiling_utilisation,
            NTILE(4) OVER (ORDER BY proven_capacity)         AS cap_q
    FROM    dwbi_temp40_db.dcb3_dataset_c1
    WHERE   proven_capacity IS NOT NULL
) t
GROUP BY cap_q
ORDER BY cap_q;

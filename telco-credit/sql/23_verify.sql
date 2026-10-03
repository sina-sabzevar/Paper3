-- ============================================================================
--  VERIFY, THEN READ THE RATES                             (Trino/Presto)
--  Three read-only queries. No CREATE TABLE, nothing to edit.
--  Run V1 FIRST and look at it before the others.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- V1  DID THE FAN-OUT FIX WORK. Every per-month counter has an arithmetic
--     ceiling: the outcome window is 6 months, so n_late_out cannot exceed 6
--     and total_debt_days_out cannot exceed the days in the window. Before the
--     fix these read 36 and 927.
--
--     ALL FOUR "impossible" COUNTS MUST BE ZERO. If any is not, a fan-out
--     remains and the bad rates below mean nothing - send V1 alone and stop.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                             AS n_rows,
        COUNT(*) FILTER (WHERE n_late_out > 6)               AS impossible_late,
        COUNT(*) FILTER (WHERE total_debt_days_out > 190)    AS impossible_debtdays,
        COUNT(*) FILTER (WHERE twoway_months_out > 6)        AS impossible_twoway_months,
        COUNT(*) FILTER (WHERE oneway_days_out > 190)        AS impossible_onewaydays,
        MAX(n_late_out)                                      AS max_late,
        MAX(total_debt_days_out)                             AS max_debtdays,
        MAX(twoway_months_out)                               AS max_twoway_months
FROM    dwbi_temp40_db.dcb3_dataset_c1;


-- ---------------------------------------------------------------------------
-- V2  THE BAD RATES, now that the counters are sound.
--     y_severe, y_strict and y_twoway_2m were always sound - they are built on
--     MAX, which duplication does not change - so those three should come back
--     UNCHANGED at 2.22, 1.22 and 1.16 pct. If they moved, something else did
--     too and I need to know.
--     y_v1, y_v2, y_loose and y_twoway_any2m were the broken ones and should
--     all come back LOWER than before.
-- ---------------------------------------------------------------------------
SELECT  AVG(y_twoway_2m)      AS bad_twoway_2m,
        AVG(y_twoway_any2m)   AS bad_twoway_any2m,
        AVG(y_severe)         AS bad_severe,
        AVG(y_strict)         AS bad_strict,
        AVG(y_v1)             AS bad_v1,
        AVG(y_v2)             AS bad_v2,
        AVG(y_loose)          AS bad_loose,
        AVG(indeterminate)    AS indet
FROM    dwbi_temp40_db.dcb3_dataset_c1;


-- ---------------------------------------------------------------------------
-- V3  the lateness distribution, which must now be 0 to 6 and nothing else.
--     This is also the shape that decides whether a label can sit between the
--     1-2 pct variants and the loose ones.
-- ---------------------------------------------------------------------------
SELECT  n_late_out,
        COUNT(*)                        AS n,
        AVG(max_dpd_out)                AS avg_dpd,
        AVG(total_debt_days_out)        AS avg_debt_days,
        AVG(y_severe)                   AS rate_twoway,
        AVG(IF(max_dpd_out >= 30, 1, 0)) AS rate_dpd30
FROM    dwbi_temp40_db.dcb3_dataset_c1
GROUP BY n_late_out
ORDER BY n_late_out;

-- ============================================================================
--  ESCALATION: ONE-WAY BAR STRAIGHT TO TWO-WAY BAR         (Trino/Presto)
--
--  THE LABEL, AND WHY IT IS BETTER THAN THE THREE I BUILT
--
--  A subscriber who reaches status 3 (one-way bar) has been warned: outgoing
--  service is cut and money is owed. What happens next separates two very
--  different stories:
--
--      3 -> 4        warned and never cured. The operator escalated to a
--                    two-way bar without the subscriber returning to active.
--                    This is genuine default.
--
--      3 -> 2 -> 4   cured the one-way bar, came back to active, and was
--                    barred again later in a separate episode. Not the same
--                    thing, and not the same risk.
--
--  This is better than anything I constructed, for three reasons:
--
--    1. It uses the operator's own status ladder, not a threshold I invented.
--       My first label used a ratio against a 44,960 Toman median baseline
--       and fired on noise. My second counted unsettled months and turned out
--       anti-correlated with capacity.
--    2. It is a TRANSITION, not an "ever" count, so it carries no exposure
--       confound. That confound is what broke attempt 2: a heavy user has
--       more months in which to have had one bad one, so "ever failed" rose
--       from 46.9 pct to 56.8 pct as proven capacity rose.
--    3. It is unambiguous. There is nothing to tune.
--
--  WHY DAILY AND NOT MONTHLY
--
--  Monthly gives 30 snapshots. If a subscriber reads 3 in month M and 4 in
--  month M+1, monthly cannot tell whether they went 3->4 directly or
--  3->2->4 inside the gap - which is exactly the distinction being drawn.
--  Daily is required for correctness.
--
--  WHY THE COHORT IS NARROWED FIRST
--
--  40,000,000 subscribers over 913 days is 36 billion rows if the daily fact
--  is a per-day snapshot. The 3->4 pattern can only occur in subscribers who
--  reached 3 or 4 at some point, so E1 finds those from the cheap monthly
--  fact and E2 reads daily history for them alone. Cheaper AND exact.
--
--  Run E0 first. It decides how expensive the rest is.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- E0  WHAT GRAIN IS THE DAILY FACT? A per-subscriber-per-day snapshot, or
--     only rows on days when something changed? That is a 900x difference in
--     cost and it is not worth guessing at.
--
--     If rows_one_day is close to n_subs_one_day and both are near 40,000,000,
--     it is a full daily snapshot. If rows_one_day is small, it is an event
--     log and the whole 30 months can be read directly.
-- ---------------------------------------------------------------------------
SELECT  'one day'   AS scope,
        COUNT(*)                    AS n_rows,
        COUNT(DISTINCT sbrp_id)     AS n_subs,
        COUNT(DISTINCT sbrp_stat_id) AS n_statuses
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key = 14050601
  AND   sbrp_typ_id = 1
UNION ALL
SELECT  'one month',
        COUNT(*),
        COUNT(DISTINCT sbrp_id),
        COUNT(DISTINCT sbrp_stat_id)
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14050601 AND 14050630
  AND   sbrp_typ_id = 1;

-- the status ladder's own distribution, so every code present is known
SELECT  sbrp_stat_id,
        COUNT(*)                 AS n_rows,
        COUNT(DISTINCT sbrp_id)  AS n_subs
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14050601 AND 14050630
  AND   sbrp_typ_id = 1
GROUP BY sbrp_stat_id
ORDER BY n_rows DESC;

-- ---------------------------------------------------------------------------
-- E1  THE COHORT. Subscribers who ever reached a bar in the monthly fact.
--     Everyone else cannot produce the pattern, so they are not read daily.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_barred_cohort;
CREATE TABLE dwbi_temp40_db.dcb_barred_cohort WITH (format='PARQUET') AS
SELECT   sbrp_id,
         MAX(IF(sbrp_stat_id = 3, 1, 0))  AS ever_3,
         MAX(IF(sbrp_stat_id = 4, 1, 0))  AS ever_4,
         COUNT(DISTINCT month_key)        AS n_months
FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE    month_key BETWEEN 140301 AND 140506
  AND    sbrp_typ_id = 1
GROUP BY sbrp_id
HAVING   MAX(IF(sbrp_stat_id IN (3, 4), 1, 0)) = 1
;

-- ---------------------------------------------------------------------------
-- E2  COLLAPSE EACH SUBSCRIBER'S DAILY STATUS INTO RUNS, then read what
--     follows each run. Consecutive identical days become one run, so
--     3,3,3,3,4,4 becomes 3 then 4 and the transition is visible.
--
--     Gaps and islands: a row starts a new run when its status differs from
--     the previous day's, and a running SUM of those markers numbers the runs.
--
--     Status 8 and 9 are reclamation and are excluded from the project
--     everywhere else - but they are KEPT here, because if a subscriber goes
--     3 -> 9 -> 4 then treating that as 3 -> 4 would be wrong. E3 reports
--     every destination out of 3 rather than assuming which ones exist.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_status_runs;
CREATE TABLE dwbi_temp40_db.dcb_status_runs WITH (format='PARQUET') AS
WITH d AS (
    SELECT   dc.sbrp_id,
             dc.day_key,
             dc.sbrp_stat_id
    FROM        dwbi_fact_db.v_fact_sbrp_daily_cip dc
    INNER JOIN  dwbi_temp40_db.dcb_barred_cohort c ON c.sbrp_id = dc.sbrp_id
    WHERE    dc.day_key BETWEEN 14030101 AND 14050631
      AND    dc.sbrp_typ_id = 1
),
marked AS (
    SELECT  sbrp_id, day_key, sbrp_stat_id,
            IF(sbrp_stat_id = LAG(sbrp_stat_id) OVER (PARTITION BY sbrp_id
                                                      ORDER BY day_key),
               0, 1)                                      AS is_new_run
    FROM    d
),
runs AS (
    SELECT  sbrp_id, day_key, sbrp_stat_id,
            SUM(is_new_run) OVER (PARTITION BY sbrp_id ORDER BY day_key
                                  ROWS BETWEEN UNBOUNDED PRECEDING
                                  AND CURRENT ROW)        AS run_id
    FROM    marked
)
SELECT   sbrp_id,
         run_id,
         sbrp_stat_id,
         MIN(day_key)  AS from_day,
         MAX(day_key)  AS to_day,
         COUNT(*)      AS n_days
FROM     runs
GROUP BY sbrp_id, run_id, sbrp_stat_id
;

-- ---------------------------------------------------------------------------
-- E3  THE TRANSITION MATRIX OUT OF STATUS 3. Every destination, counted,
--     rather than only the one being looked for.
-- ---------------------------------------------------------------------------
SELECT  COALESCE(CAST(next_stat AS VARCHAR), 'no next run - still in 3 at the end')
                                                         AS destination_from_3,
        COUNT(*)                                         AS n_transitions,
        COUNT(DISTINCT sbrp_id)                          AS n_subscribers,
        APPROX_PERCENTILE(CAST(n_days AS DOUBLE), 0.5)   AS med_days_in_3,
        APPROX_PERCENTILE(CAST(n_days AS DOUBLE), 0.9)   AS p90_days_in_3
FROM (
    SELECT  sbrp_id, n_days,
            LEAD(sbrp_stat_id) OVER (PARTITION BY sbrp_id ORDER BY run_id) AS next_stat
    FROM    dwbi_temp40_db.dcb_status_runs
) t
WHERE   sbrp_stat_id = 3
GROUP BY next_stat
ORDER BY n_transitions DESC;

-- ---------------------------------------------------------------------------
-- E4  THE LABEL. One row per subscriber in the cohort.
--
--     y_escalated is the headline: at least one run of status 3 followed
--     IMMEDIATELY by status 4. cured_and_rebarred is the contrast case -
--     3 -> 2 somewhere, AND a 4 somewhere, but never 3 -> 4 adjacently.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                              AS cohort,
        SUM(esc)                                              AS n_escalated,
        100.0 * SUM(esc) / COUNT(*)                           AS escalated_pct_of_cohort,
        SUM(cured)                                            AS n_ever_cured,
        SUM(IF(esc = 0 AND had4 = 1, 1, 0))                   AS barred_without_escalation,
        SUM(IF(esc = 1 AND cured = 1, 1, 0))                   AS both_patterns,
        APPROX_PERCENTILE(CAST(days3_before_4 AS DOUBLE), 0.5) AS med_days_in_3_before_4
FROM (
    SELECT  sbrp_id,
            MAX(IF(sbrp_stat_id = 3 AND next_stat = 4, 1, 0))  AS esc,
            MAX(IF(sbrp_stat_id = 3 AND next_stat = 2, 1, 0))  AS cured,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                    AS had4,
            MAX(IF(sbrp_stat_id = 3 AND next_stat = 4, n_days, 0)) AS days3_before_4
    FROM (
        SELECT  sbrp_id, sbrp_stat_id, n_days,
                LEAD(sbrp_stat_id) OVER (PARTITION BY sbrp_id
                                         ORDER BY run_id)      AS next_stat
        FROM    dwbi_temp40_db.dcb_status_runs
    ) r
    GROUP BY sbrp_id
) s;

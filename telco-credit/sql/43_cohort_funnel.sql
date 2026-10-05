-- ============================================================================
--  WHY IS TRAIN SMALLER THAN VALID?                         (Trino/Presto)
--
--  TRAIN at 140301..140306 returned 3,733,333 subscribers against VALID's
--  6,879,803 at 140407..140412 - a 46 pct shortfall on the SAME screen. That
--  needs a cause before anything is fitted on it. The row count is not the
--  worry: 3.7M rows at a 0.95 pct rate is about 35,000 bads, which is ample.
--  The worry is whether it is the same KIND of population that SCORE holds.
--
--  THE HYPOTHESIS. The screen uses a FIXED NOMINAL threshold of 170,000
--  Toman (1,700,000 Rial). Nominal revenue per subscriber rises over time
--  with inflation and tariff changes, so the same nominal bar is a HARSHER
--  screen the further back the window sits. 140301 is roughly twelve months
--  before SCORE. If that is the cause, the early window selects the richer
--  tail, and a model fitted there is fitted on a different population from
--  the one it scores.
--
--  THE ALTERNATIVE. Thin or ramping data coverage in the earliest months -
--  this base has already produced one loading gap, where debt_scr and
--  suspend_scr were all zero in 6 of 10 months and read as a PSI of 13.89.
--
--  These two have DIFFERENT fixes, so guessing is not good enough:
--      inflation       -> move the window later, or deflate the threshold
--      coverage gap    -> the early months are unusable at any threshold
--  D2 and D3 separate them. If revenue levels drift upward smoothly across
--  windows, it is inflation. If the early window is missing subscribers or
--  carries NULL revenue rather than low revenue, it is coverage.
--
--  FOUR WINDOWS. W1 is the window that produced 3,733,333, kept here for
--  comparison; W2 is where TRAIN now sits; W3 is VALID; W4 is SCORE.
--
--      W1  140301..140306      label 140307..140310    the old TRAIN
--      W2  140309..140402      label 140403..140406    the new TRAIN
--      W3  140407..140412      label 140501..140504    VALID
--      W4  140501..140506      no label                SCORE
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_funnel;
CREATE TABLE dwbi_temp40_db.dcb_funnel WITH (format='PARQUET') AS
WITH sm AS (
    -- One row per subscriber per month. Flattened FIRST, before any window
    -- label is attached: aggregating a multi-row-per-key relation after a
    -- join is how this project previously read revenue as 8,000,000 instead
    -- of 2,000,000.
    SELECT   sbrp_id,
             month_key,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS rev,
             MAX(IF(sbrp_stat_id = 3, 1, 0))                      AS ow,
             MAX(IF(sbrp_stat_id = 4, 1, 0))                      AS tw,
             SUM(IF(arpu IS NULL, 1, 0))                          AS n_null,
             COUNT(*)                                             AS n_rows
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140506
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
),
tagged AS (
    -- The window each month belongs to. A month_key can sit in one window's
    -- FEATURE span and another window's LABEL span; those are resolved in
    -- separate CTEs below, so there is no conflict here.
    SELECT  sm.*,
            IF(month_key BETWEEN 140301 AND 140306, 'W1_140301_140306',
            IF(month_key BETWEEN 140309 AND 140402, 'W2_140309_140402',
            IF(month_key BETWEEN 140407 AND 140412, 'W3_140407_140412',
            IF(month_key BETWEEN 140501 AND 140506, 'W4_140501_140506',
               NULL)))) AS win
    FROM    sm
),
fw AS (
    -- Per subscriber, per feature window.
    SELECT   sbrp_id,
             win,
             COUNT(*)                            AS n_months,
             SUM(IF(rev >= 1700000, 1, 0))       AS rev_months,
             MAX(ow)                             AS ow_any,
             MAX(tw)                             AS tw_any,
             SUM(n_null)                         AS n_arpu_null,
             SUM(rev)                            AS rev_total
    FROM     tagged
    WHERE    win IS NOT NULL
    GROUP BY sbrp_id, win
),
lb AS (
    -- Per subscriber, per window's LABEL span. Presence here is what the
    -- cohort's INNER JOIN requires, so it belongs in the funnel.
    --
    -- The window tag is computed in a SUBQUERY so that GROUP BY names a real
    -- column. Trino does not reliably group by a SELECT alias, and repeating
    -- a four-line nested IF in the GROUP BY is how the two copies drift apart.
    SELECT   sbrp_id, win,
             MAX(IF(sbrp_stat_id = 4, 1, 0))     AS y,
             COUNT(DISTINCT month_key)           AS n_label_months
    FROM (
        SELECT  sbrp_id, month_key, sbrp_stat_id,
                IF(month_key BETWEEN 140307 AND 140310, 'W1_140301_140306',
                IF(month_key BETWEEN 140403 AND 140406, 'W2_140309_140402',
                IF(month_key BETWEEN 140501 AND 140504, 'W3_140407_140412',
                   NULL))) AS win
        FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
        WHERE   month_key BETWEEN 140307 AND 140504
          AND   sbrp_typ_id = 1
    ) q
    WHERE    win IS NOT NULL
    GROUP BY sbrp_id, win
)
SELECT      f.sbrp_id,
            f.win,
            f.n_months,
            f.rev_months,
            f.ow_any,
            f.tw_any,
            f.n_arpu_null,
            f.rev_total,
            l.y,
            l.n_label_months
FROM        fw f
LEFT JOIN   lb l ON l.sbrp_id = f.sbrp_id AND l.win = f.win
;

-- ---------------------------------------------------------------------------
-- D1  THE FUNNEL. Where the subscribers are lost, window by window.
--
--     Read ACROSS the row: present -> cleared the revenue bar -> never
--     one-way -> never two-way -> judgeable. If W1 and W3 differ mainly at
--     the "pass_rev" step, the threshold is the cause. If they differ at
--     "present", it is coverage.
-- ---------------------------------------------------------------------------
SELECT  win,
        COUNT(*)                                                 AS present,
        AVG(CAST(n_months AS DOUBLE))                            AS avg_months_seen,
        SUM(IF(rev_months >= 2, 1, 0))                            AS pass_rev,
        SUM(IF(rev_months >= 2 AND ow_any = 0, 1, 0))             AS pass_rev_ow,
        SUM(IF(rev_months >= 2 AND ow_any = 0 AND tw_any = 0, 1, 0))
                                                                 AS screened,
        SUM(IF(rev_months >= 2 AND ow_any = 0 AND tw_any = 0
               AND n_label_months IS NOT NULL, 1, 0))            AS cohort_rows,
        100.0 * SUM(IF(rev_months >= 2, 1, 0)) / COUNT(*)        AS pass_rev_pct
FROM     dwbi_temp40_db.dcb_funnel
GROUP BY win
ORDER BY win;

-- ---------------------------------------------------------------------------
-- D2  IS IT INFLATION OR IS IT COVERAGE?
--
--     Revenue levels per subscriber-month, by window. Inflation looks like a
--     smooth upward march in every percentile from W1 to W4. A coverage gap
--     looks like a similar distribution with fewer subscribers in it, or a
--     spike in the NULL-arpu share rather than genuinely low revenue.
--
--     The 170,000 Toman bar is 1,700,000 Rial. Watch where it falls in each
--     window's distribution - that IS the drift, stated in one number.
-- ---------------------------------------------------------------------------
SELECT  win,
        COUNT(*)                                            AS subs,
        AVG(rev_total / NULLIF(n_months, 0))                AS mean_rev_per_month,
        APPROX_PERCENTILE(rev_total / NULLIF(n_months, 0), 0.25) AS p25,
        APPROX_PERCENTILE(rev_total / NULLIF(n_months, 0), 0.50) AS p50,
        APPROX_PERCENTILE(rev_total / NULLIF(n_months, 0), 0.75) AS p75,
        APPROX_PERCENTILE(rev_total / NULLIF(n_months, 0), 0.90) AS p90,
        -- where the fixed bar sits: the share of subscribers whose average
        -- month clears it
        100.0 * SUM(IF(rev_total / NULLIF(n_months, 0) >= 1700000, 1, 0))
              / COUNT(*)                                    AS pct_avg_month_over_bar,
        -- a coverage gap shows up here, not in the percentiles
        AVG(CAST(n_arpu_null AS DOUBLE))                    AS avg_null_arpu_rows
FROM     dwbi_temp40_db.dcb_funnel
GROUP BY win
ORDER BY win;

-- ---------------------------------------------------------------------------
-- D3  THE EQUALIZING THRESHOLD. What bar in an earlier window admits the
--     same SHARE of subscribers that 1,700,000 Rial admits in W3?
--
--     Read down to the W1 rows for the share at each bar, then find the bar
--     whose share matches W3 at 1,700,000. The ratio of those two bars IS the
--     nominal drift, measured rather than assumed, and it is the number to
--     use if the threshold is ever deflated per window instead of held fixed.
--
--     This is its OWN table rather than a query over the one above. The CTEs
--     in a CREATE TABLE AS statement do not survive it, and the per-month
--     revenue needed to re-test other bars is not in dcb_funnel - only the
--     count at the single fixed bar is. Querying a CTE from a later statement
--     is a mistake this project has already made once.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_funnel_bars;
CREATE TABLE dwbi_temp40_db.dcb_funnel_bars WITH (format='PARQUET') AS
WITH sm AS (
    SELECT   sbrp_id, month_key,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS rev
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140506
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
),
tagged AS (
    SELECT  sbrp_id, rev,
            IF(month_key BETWEEN 140301 AND 140306, 'W1_140301_140306',
            IF(month_key BETWEEN 140309 AND 140402, 'W2_140309_140402',
            IF(month_key BETWEEN 140407 AND 140412, 'W3_140407_140412',
            IF(month_key BETWEEN 140501 AND 140506, 'W4_140501_140506',
               NULL)))) AS win
    FROM    sm
),
per AS (
    -- Months above each candidate bar, per subscriber per window.
    SELECT      t.win, t.sbrp_id, b.bar,
                SUM(IF(t.rev >= b.bar, 1, 0)) AS months_at_bar
    FROM        tagged t
    CROSS JOIN  UNNEST(ARRAY[800000, 1000000, 1200000, 1400000,
                             1700000, 2000000, 2400000]) AS b (bar)
    WHERE       t.win IS NOT NULL
    GROUP BY    t.win, t.sbrp_id, b.bar
)
SELECT   win, bar,
         COUNT(*)                                             AS present,
         SUM(IF(months_at_bar >= 2, 1, 0))                    AS pass_2plus,
         100.0 * SUM(IF(months_at_bar >= 2, 1, 0)) / COUNT(*) AS pass_pct
FROM     per
GROUP BY win, bar
;

SELECT   bar, win, present, pass_2plus, pass_pct
FROM     dwbi_temp40_db.dcb_funnel_bars
ORDER BY bar, win;

-- ---------------------------------------------------------------------------
-- D4  THE ONE NUMBER THIS IS ALL FOR.
--
--     The W1 and W2 pass share at the fixed 1,700,000 bar, against W4's. If
--     W2 is close to W4 and W1 is far from it, moving TRAIN to 140309..140402
--     fixed the problem and nothing further is needed. If W2 is still far
--     from W4, the threshold itself has to be deflated per window, and D3
--     says by how much.
-- ---------------------------------------------------------------------------
SELECT   win,
         pass_pct                                             AS pass_pct_at_fixed_bar,
         pass_pct - (SELECT pass_pct FROM dwbi_temp40_db.dcb_funnel_bars
                     WHERE bar = 1700000 AND win = 'W4_140501_140506')
                                                              AS pp_vs_score,
         pass_2plus
FROM     dwbi_temp40_db.dcb_funnel_bars
WHERE    bar = 1700000
ORDER BY win;

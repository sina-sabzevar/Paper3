-- ============================================================================
--  CANDIDATE LABELS, MEASURED ON THE SAME COHORT         (Trino/Presto)
--
--  WHY THIS EXISTS. The ask was for many more label = 1 subscribers, ideally
--  enough for a balanced dataset. Two facts bear on that:
--
--    1 Balance does not change the ranking. Sweeping the training balance from
--      0.55 pct bads to 50.21 pct bads moved AUC by 0.0005 across five seeds
--      on a fixed test set. What balance DOES change is the level: at 50/50
--      without sample_weight the model predicted 42.49 pct against a true
--      0.55 pct. So rebalancing buys nothing that down-sampling with weights
--      does not already give, correctly.
--
--    2 Only 28,263 two-way bar events exist on this cohort. More bads cannot
--      come from the population - adding already-barred subscribers puts
--      weight on a feature the screen forces to zero in dcb_score, and was
--      measured at -0.0001 AUC. If more events are genuinely wanted, they
--      have to come from a DIFFERENT LABEL.
--
--  So this file prices the label menu. All candidates are measured on the
--  IDENTICAL cohort (140401..140406, production bar) over the IDENTICAL label
--  window (140407..140410), so the only thing that varies is the definition
--  of the event. L1's cohort count must come back 5,100,390 and its two-way
--  rate 0.5541 pct, which reconciles this file against 43_cohort_funnel.sql.
--
--  THE JUDGEMENT THIS INFORMS, which is a business one and not a modelling
--  one: a one-way bar means the subscriber did not pay. For a credit product
--  that is arguably the more relevant event than being fully cut off, and it
--  is far more common. But many one-way bars are cured within days once the
--  subscriber pays, so the raw one-way label would overstate default. The
--  ow_months variants are the middle ground: a bar that recurs across two or
--  three separate months is not a subscriber who simply paid late once.
--
--  Whatever is chosen, the SAME definition must then go into
--  42_model_datasets.sql, and the expected-loss assumptions in the limit
--  tables have to be revisited - a one-way bar does not lose the whole
--  balance, so LGD 100 pct would be far too pessimistic for that label.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_altlabel;
CREATE TABLE dwbi_temp40_db.dcb_altlabel WITH (format='PARQUET') AS
WITH fm AS (
    -- One row per subscriber-month in the FEATURE window. Flattened before
    -- anything else: aggregating a multi-row-per-key relation after a join is
    -- how this project once read revenue as 8,000,000 instead of 2,000,000.
    SELECT   sbrp_id, month_key,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS rev,
             MAX(IF(sbrp_stat_id = 3, 1, 0))                      AS ow,
             MAX(IF(sbrp_stat_id = 4, 1, 0))                      AS tw
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140401,140402,140403,140404,140405,140406)
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
),
feat AS (
    -- The screen, at the PRODUCTION bar so the counts reconcile with 43.
    SELECT   sbrp_id,
             SUM(IF(rev >= 1700000, 1, 0)) AS rev_months,
             MAX(ow)                       AS f_ow,
             MAX(tw)                       AS f_tw
    FROM     fm
    GROUP BY sbrp_id
),
lab AS (
    -- The LABEL window. Every candidate event is derived from these, so they
    -- are all measured on exactly the same rows.
    --
    -- COUNT(DISTINCT IF(cond, month_key, NULL)) counts only the months where
    -- the condition held, because COUNT(DISTINCT ...) ignores NULLs.
    SELECT   sbrp_id,
             MAX(IF(sbrp_stat_id = 4, 1, 0))                       AS l_tw,
             MAX(IF(sbrp_stat_id = 3, 1, 0))                       AS l_ow,
             COUNT(DISTINCT IF(sbrp_stat_id = 3, month_key, NULL)) AS l_ow_months,
             COUNT(DISTINCT IF(sbrp_stat_id = 4, month_key, NULL)) AS l_tw_months,
             COUNT(DISTINCT month_key)                             AS n_label_months
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140407, 140408, 140409, 140410)
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT      f.sbrp_id,
            f.rev_months,
            l.l_tw, l.l_ow, l.l_ow_months, l.l_tw_months, l.n_label_months
FROM        feat f
INNER JOIN  lab  l ON l.sbrp_id = f.sbrp_id
WHERE       f.rev_months >= 2
  AND       f.f_ow = 0
  AND       f.f_tw = 0
;

-- ---------------------------------------------------------------------------
-- L1  THE LABEL MENU. One row. Every rate is on the same denominator.
--
--     CHECK FIRST: cohort_n should be 5,100,390 and pct_twoway 0.5541. Those
--     are 43_cohort_funnel.sql D5's figures for this window, so if they match,
--     this file agrees with 43 and the other columns can be trusted.
--
--     Then read across for how many events each definition yields.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                              AS cohort_n,

        SUM(l_tw)                                             AS n_twoway,
        100.0 * SUM(l_tw) / COUNT(*)                          AS pct_twoway,

        SUM(l_ow)                                             AS n_oneway,
        100.0 * SUM(l_ow) / COUNT(*)                          AS pct_oneway,

        SUM(IF(l_ow = 1 OR l_tw = 1, 1, 0))                   AS n_either,
        100.0 * SUM(IF(l_ow = 1 OR l_tw = 1, 1, 0)) / COUNT(*) AS pct_either,

        SUM(IF(l_ow_months >= 2, 1, 0))                       AS n_oneway_2plus,
        100.0 * SUM(IF(l_ow_months >= 2, 1, 0)) / COUNT(*)    AS pct_oneway_2plus,

        SUM(IF(l_ow_months >= 3, 1, 0))                       AS n_oneway_3plus,
        100.0 * SUM(IF(l_ow_months >= 3, 1, 0)) / COUNT(*)    AS pct_oneway_3plus,

        -- how many bads a 50/50 training set could hold under each definition
        SUM(l_tw)          * 2                                AS balanced_rows_twoway,
        SUM(IF(l_ow_months >= 2, 1, 0)) * 2                   AS balanced_rows_ow2plus,
        SUM(l_ow)          * 2                                AS balanced_rows_oneway
FROM    dwbi_temp40_db.dcb_altlabel;

-- ---------------------------------------------------------------------------
-- L2  IS A ONE-WAY BAR TRANSIENT OR PERSISTENT? The distribution of how many
--     separate months carried one.
--
--     A long tail at 1 month means most one-way bars are a subscriber who
--     paid late once and cured it - weak evidence of default, and a poor
--     label. Mass at 2, 3 and 4 months means recurring non-payment, which is
--     what a credit product actually cares about.
-- ---------------------------------------------------------------------------
SELECT   l_ow_months,
         COUNT(*)                                             AS n,
         100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()             AS pct_of_cohort,
         SUM(l_tw)                                            AS n_also_twoway,
         100.0 * SUM(l_tw) / NULLIF(COUNT(*), 0)              AS pct_also_twoway
FROM     dwbi_temp40_db.dcb_altlabel
GROUP BY l_ow_months
ORDER BY l_ow_months;

-- ---------------------------------------------------------------------------
-- L3  DO THE TWO AGGREGATIONS AGREE? A correctness check, not a finding.
--     Every column must come back 0.
--
--     The flags and the month counts are computed by DIFFERENT aggregates in
--     the lab CTE - MAX(IF(...)) against COUNT(DISTINCT IF(...)) - so making
--     them agree is a real test of both. A subscriber with a one-way month
--     counted must also carry the one-way flag, and vice versa.
--
--     An earlier draft of this block asserted things like
--         l_ow_months >= 3 AND l_ow_months < 2
--     which is a contradiction and therefore always 0 whatever the data says.
--     Two of the five checks could never have failed. Subset relations that
--     hold by construction are not worth asserting; relations between
--     independently computed columns are.
-- ---------------------------------------------------------------------------
SELECT  SUM(IF(l_ow_months >= 1 AND l_ow = 0, 1, 0))     AS ow_months_without_flag,
        SUM(IF(l_ow = 1 AND l_ow_months = 0, 1, 0))      AS ow_flag_without_months,
        SUM(IF(l_tw_months >= 1 AND l_tw = 0, 1, 0))     AS tw_months_without_flag,
        SUM(IF(l_tw = 1 AND l_tw_months = 0, 1, 0))      AS tw_flag_without_months,
        SUM(IF(l_tw_months > n_label_months, 1, 0))      AS tw_months_impossible,
        SUM(IF(l_ow_months > n_label_months, 1, 0))      AS ow_months_impossible,
        SUM(IF(n_label_months < 1 OR n_label_months > 4, 1, 0))
                                                         AS label_months_out_of_range
FROM    dwbi_temp40_db.dcb_altlabel;

-- ---------------------------------------------------------------------------
-- L4  WOULD A SOFTER LABEL STILL SEPARATE? The candidate rates by rev_months
--     inside the cohort.
--
--     The point of a label with more events is a more stable fit, but only if
--     the event is still predictable. If pct_oneway_2plus falls across
--     rev_months the way pct_twoway does, the softer label carries the same
--     signal with eight times the events, which is the best outcome here. If
--     it is flat, the extra events are noise and the two-way label was right.
-- ---------------------------------------------------------------------------
SELECT   rev_months,
         COUNT(*)                                             AS n,
         100.0 * SUM(l_tw) / COUNT(*)                         AS pct_twoway,
         100.0 * SUM(IF(l_ow_months >= 2, 1, 0)) / COUNT(*)   AS pct_oneway_2plus,
         100.0 * SUM(l_ow) / COUNT(*)                         AS pct_oneway
FROM     dwbi_temp40_db.dcb_altlabel
GROUP BY rev_months
ORDER BY rev_months;

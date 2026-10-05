-- ============================================================================
--  THE LABEL, EXPOSURE-NORMALISED, WITH ITS OWN DIRECTION TEST
--
--  TWO LABELS HAVE NOW FAILED ON MEASUREMENT. THIS FILE MAKES THE NEXT ONE
--  PROVE ITSELF BEFORE ANYONE TRUSTS IT.
--
--  Attempt 1, y_spike_fail_2x: fired on 23.9 pct against a 7.0 pct bar rate
--  with 12 pct overlap. Cause - a relative threshold on a 44,960 Toman median
--  baseline fires on absolute noise.
--
--  Attempt 2, failed_material: fired on 29.9 pct - BROADER, not narrower -
--  and its bad rate RISES with the amount a subscriber has proven they can
--  settle: 46.9 pct at 100,000 Toman up to 56.8 pct at 2,000,000. Over the
--  same bands the two-way bar FALLS, 7.8 pct down to 5.6 pct. The bar
--  behaves like a credit signal; attempt 2 behaves like an exposure count,
--  because MAX() over 30 months asks "ever" and a heavy user has more months
--  in which to have had one bad one.
--
--  THE FIX IS A RATE, NOT AN EVER
--
--  unsettled_share = unsettled material months / material months. A
--  subscriber with 1 bad month in 30 is not the same risk as one with 12 in
--  30, and an "ever" label cannot tell them apart. The share can.
--
--  THE DIRECTION TEST IS NOT OPTIONAL
--
--  L3 reports every candidate label's rate across proven-amount bands. A
--  label whose bad rate RISES with demonstrated capacity is measuring
--  exposure and must be rejected, whatever its headline rate looks like.
--  That test is what caught attempt 2, and it caught it only after the label
--  had been written, shipped and run. It runs first now.
--
--  Needs dcb_panel from 35_spike_settlement.sql S1.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- L1  Per subscriber: material months, how many went unsettled, the share,
--     and the largest amount settled. Censored months are excluded from both
--     numerator and denominator - a month whose 3-month window runs past the
--     end of the data is not evidence either way.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_label;
CREATE TABLE dwbi_temp40_db.dcb_label WITH (format='PARQUET') AS
WITH base AS (
    SELECT   sbrp_id,
             APPROX_PERCENTILE(due_approx, 0.5)        AS baseline_due,
             COUNT(*)                                  AS n_months,
             MAX(avail)                                AS avail_max,
             MAX(twoway_bar)                           AS ever_twoway,
             MAX(oneway_bar)                           AS ever_oneway
    FROM     dwbi_temp40_db.dcb_panel
    GROUP BY sbrp_id
),
seq AS (
    SELECT  p.sbrp_id,
            p.due_approx,
            LEAD(p.outst, 2) OVER (PARTITION BY p.sbrp_id
                                   ORDER BY p.month_key)  AS outst_n2,
            b.baseline_due
    FROM        dwbi_temp40_db.dcb_panel p
    INNER JOIN  base b ON b.sbrp_id = p.sbrp_id
),
judged AS (
    -- material AND judgeable only
    SELECT  sbrp_id,
            due_approx,
            IF(baseline_due > 0, due_approx / baseline_due, 0) AS ratio,
            IF(outst_n2 <= 0.10 * due_approx, 1, 0)            AS settled
    FROM    seq
    WHERE   due_approx >= 1000000
      AND   outst_n2 IS NOT NULL
)
SELECT  b.sbrp_id,
        b.n_months,
        b.baseline_due,
        b.avail_max,
        b.ever_twoway,
        b.ever_oneway,
        COUNT(j.due_approx)                                    AS n_material,
        COUNT(j.due_approx) FILTER (WHERE j.settled = 1)       AS n_settled,
        COUNT(j.due_approx) FILTER (WHERE j.settled = 0)       AS n_unsettled,
        -- THE FIX: a rate, not an ever. NULL when there is nothing to judge,
        -- which is honest - a subscriber with no material month has no
        -- settlement record, and 0 would claim a clean one.
        CAST(COUNT(j.due_approx) FILTER (WHERE j.settled = 0) AS DOUBLE)
          / NULLIF(COUNT(j.due_approx), 0)                      AS unsettled_share,
        COALESCE(MAX(j.due_approx) FILTER (WHERE j.settled = 1), 0)
                                                                AS max_settled_amt,
        COALESCE(MAX(j.due_approx), 0)                          AS max_due_seen,
        COALESCE(MAX(j.ratio) FILTER (WHERE j.settled = 1), 0)   AS max_ratio_settled
FROM        base b
LEFT JOIN   judged j ON j.sbrp_id = b.sbrp_id
GROUP BY    b.sbrp_id, b.n_months, b.baseline_due, b.avail_max,
            b.ever_twoway, b.ever_oneway
;

-- ---------------------------------------------------------------------------
-- L2  The candidates and their headline rates. Each requires a minimum of
--     three judgeable material months, because a share computed on one month
--     is either 0 or 1 and carries no information.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                              AS subscribers,
        COUNT(*) FILTER (WHERE n_material >= 3)               AS n_judgeable,
        100.0 * SUM(ever_twoway) / COUNT(*)                   AS bar_pct,
        100.0 * COUNT(*) FILTER (WHERE n_material >= 3
                                   AND unsettled_share >= 0.25)
              / NULLIF(COUNT(*) FILTER (WHERE n_material >= 3), 0) AS share25_pct,
        100.0 * COUNT(*) FILTER (WHERE n_material >= 3
                                   AND unsettled_share >= 0.50)
              / NULLIF(COUNT(*) FILTER (WHERE n_material >= 3), 0) AS share50_pct,
        100.0 * COUNT(*) FILTER (WHERE n_material >= 3
                                   AND unsettled_share >= 0.75)
              / NULLIF(COUNT(*) FILTER (WHERE n_material >= 3), 0) AS share75_pct,
        APPROX_PERCENTILE(unsettled_share, 0.5)               AS med_share,
        APPROX_PERCENTILE(CAST(n_material AS DOUBLE), 0.5)    AS med_n_material
FROM    dwbi_temp40_db.dcb_label;

-- ---------------------------------------------------------------------------
-- L3  THE DIRECTION TEST. Run this before trusting any candidate.
--
--     Each column must FALL as the proven amount rises. A column that rises
--     is measuring exposure, not risk, and is rejected - that is exactly how
--     failed_material was caught, after it had already been shipped.
--
--     ever_twoway is included as the control: it is known to fall correctly
--     (7.8 pct down to 5.6 pct), so if it does not fall here the band
--     definition itself is wrong rather than the candidates.
-- ---------------------------------------------------------------------------
SELECT  amt / 10000                                           AS proven_k_toman,
        COUNT(*)                                              AS n_proved,
        100.0 * AVG(CAST(ever_twoway AS DOUBLE))              AS bar_pct,
        100.0 * COUNT(*) FILTER (WHERE unsettled_share >= 0.25)
              / COUNT(*)                                      AS share25_pct,
        100.0 * COUNT(*) FILTER (WHERE unsettled_share >= 0.50)
              / COUNT(*)                                      AS share50_pct,
        100.0 * COUNT(*) FILTER (WHERE unsettled_share >= 0.75)
              / COUNT(*)                                      AS share75_pct,
        -- the rejected label, carried so the contrast is on one screen
        100.0 * COUNT(*) FILTER (WHERE n_unsettled > 0)
              / COUNT(*)                                      AS ever_failed_pct,
        APPROX_PERCENTILE(unsettled_share, 0.5)               AS med_share
FROM        dwbi_temp40_db.dcb_label
CROSS JOIN  UNNEST(ARRAY[1000000, 2000000, 5000000,
                         8000000, 12000000, 20000000]) AS t (amt)
WHERE       max_settled_amt >= amt
  AND       n_material >= 3
GROUP BY    amt
ORDER BY    amt;

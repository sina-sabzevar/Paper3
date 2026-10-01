-- =====================================================================
--  Label report - run this on the output of 01_build_label.sql
--  Six queries. Run them in order; each answers one decision.
--  Sampling 100k-500k subscribers is plenty - do not run on all 10M.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. THE HEADLINE: bad rate of each candidate label
--     Decision: which variant lands in the 5-15% target band.
-- ---------------------------------------------------------------------
SELECT  COUNT(*)              AS n,
        AVG(y_strict)         AS bad_rate_strict,   -- DPD60 or two-way cut
        AVG(y_v1)             AS bad_rate_v1,       -- + 2 late bills
        AVG(y_v2)             AS bad_rate_v2,       -- + 3 late bills
        AVG(y_loose)          AS bad_rate_loose,    -- late bills alone
        AVG(indeterminate)    AS indeterminate_rate
FROM    label_table;


-- ---------------------------------------------------------------------
-- Q2. Is the label stable across cohorts?
--     A bad rate that moves more than ~3 points between cohorts means
--     something changed (tariff, collections policy, season) and the
--     out-of-time cohort will not behave like the training one.
-- ---------------------------------------------------------------------
SELECT  obs_cohort,
        COUNT(*)      AS n,
        AVG(y_strict) AS bad_strict,
        AVG(y_v1)     AS bad_v1,
        AVG(y_v2)     AS bad_v2
FROM    label_table
GROUP   BY obs_cohort
ORDER   BY obs_cohort;


-- ---------------------------------------------------------------------
-- Q3. What does each rule contribute on its own?
--     If rule2 fires for far more people than rules 1 and 3 together,
--     LATE_DAYS is too loose - raise it before touching anything else.
-- ---------------------------------------------------------------------
SELECT  rule1_dpd60, rule2_late, rule3_susp,
        COUNT(*)                                   AS n,
        COUNT(*) / SUM(COUNT(*)) OVER ()           AS share
FROM    label_table
GROUP   BY 1, 2, 3
ORDER   BY n DESC;


-- ---------------------------------------------------------------------
-- Q4. DPD distribution - set LATE_DAYS and BAD_DPD from data, not opinion
--     Look for where the mass actually sits. If 60% of bills are settled
--     at DPD 1-10, then "late" must be well above 10.
-- ---------------------------------------------------------------------
SELECT  CASE WHEN max_dpd_out =  0                        THEN '00  on time'
             WHEN max_dpd_out <=  7                       THEN '01  1-7'
             WHEN max_dpd_out <= 15                       THEN '02  8-15'
             WHEN max_dpd_out <= 30                       THEN '03  16-30'
             WHEN max_dpd_out <= 45                       THEN '04  31-45'
             WHEN max_dpd_out <= 60                       THEN '05  46-60'
             WHEN max_dpd_out <= 90                       THEN '06  61-90'
             ELSE                                              '07  90+'
        END                                        AS dpd_band,
        COUNT(*)                                   AS n,
        COUNT(*) / SUM(COUNT(*)) OVER ()           AS share,
        SUM(COUNT(*)) OVER (ORDER BY 1)
          / SUM(COUNT(*)) OVER ()                  AS cumulative_share
FROM    label_table
GROUP   BY dpd_band
ORDER   BY dpd_band;


-- ---------------------------------------------------------------------
-- Q5. THE CURE CURVE - the single most important query here
--     "From how many days late does a subscriber stop coming back?"
--     Run over ALL historical subscriber-bills, not just the label window.
--     The DPD band where cure probability collapses is where BAD_DPD belongs.
-- ---------------------------------------------------------------------
WITH bill_dpd AS (
    SELECT  b.subscriber_id,
            b.bill_id,
            b.due_date,
            b.bill_amount,
            st.settle_date,
            -- status 30 days after the due date: how late was it then?
            GREATEST(DATE_DIFF(
                LEAST(COALESCE(st.settle_date, DATE '2099-01-01'),
                      DATE_ADD(b.due_date, INTERVAL 30 DAY)),
                b.due_date, DAY), 0)                       AS dpd_at_30d,
            -- did it EVER settle, and within how long?
            DATE_DIFF(st.settle_date, b.due_date, DAY)     AS days_to_settle
    FROM    billing.bill b                                             -- [RENAME]
    LEFT JOIN ( SELECT  pc.bill_id, MIN(pc.payment_date) AS settle_date
                FROM  ( SELECT bill_id, payment_date,
                               SUM(paid_amount) OVER (PARTITION BY bill_id
                                                      ORDER BY payment_date
                                                      ROWS BETWEEN UNBOUNDED PRECEDING
                                                               AND CURRENT ROW) AS cum_paid
                        FROM   billing.payment ) pc                    -- [RENAME]
                JOIN    billing.bill bb ON bb.bill_id = pc.bill_id
                WHERE   pc.cum_paid >= 0.98 * bb.bill_amount
                GROUP   BY 1 ) st ON st.bill_id = b.bill_id
    WHERE   b.bill_period >= DATE '2024-01-01'       -- [EDIT] your history start
)
SELECT  CASE WHEN dpd_at_30d <= 15 THEN '1  up to 15'
             WHEN dpd_at_30d <= 30 THEN '2  16-30'
             WHEN dpd_at_30d <= 45 THEN '3  31-45'
             WHEN dpd_at_30d <= 60 THEN '4  46-60'
             WHEN dpd_at_30d <= 75 THEN '5  61-75'
             WHEN dpd_at_30d <= 90 THEN '6  76-90'
             ELSE                       '7  90+'
        END                                                    AS dpd_band,
        COUNT(*)                                               AS n_bills,
        -- cure = fully settled within 90 further days
        AVG(CASE WHEN days_to_settle IS NOT NULL
                  AND days_to_settle <= dpd_at_30d + 90
                 THEN 1.0 ELSE 0.0 END)                        AS cure_rate_90d,
        AVG(CASE WHEN days_to_settle IS NULL THEN 1.0 ELSE 0.0 END) AS never_settled
FROM    bill_dpd
GROUP   BY dpd_band
ORDER   BY dpd_band;
--  READ IT LIKE THIS: walk down the bands and find where cure_rate_90d drops
--  below roughly 0.40. That band is the point of no return - set BAD_DPD at
--  its lower edge. If the curve never collapses, your collections process is
--  effective and you can afford a higher BAD_DPD (90 instead of 60).


-- ---------------------------------------------------------------------
-- Q6. Sanity check - how much of the base did we throw away, and why?
--     exclude_reason and short windows are filtered out by 01_build_label;
--     run this against the PRE-filter version to see the damage.
-- ---------------------------------------------------------------------
SELECT  COALESCE(exclude_reason, 'KEPT')   AS reason,
        COUNT(*)                           AS n,
        COUNT(*) / SUM(COUNT(*)) OVER ()   AS share
FROM    label_table_prefilter
GROUP   BY 1
ORDER   BY n DESC;


-- ---------------------------------------------------------------------
-- Q7. Did the previously-suspended recover?
--     Decides whether the 6-12 month group is worth keeping.
--     Run this BEFORE applying any suspension gate, so the groups exist.
--
--     Read it like this:
--       bad rate close to "never suspended"  -> keep them, it is free coverage
--       bad rate 2-3x higher                 -> push the gate out to 12 months
-- ---------------------------------------------------------------------
WITH prior_susp AS (
    SELECT  base.subscriber_id,
            base.obs_cohort,
            MIN(DATE_DIFF(base.t0, sp.suspend_date, MONTH)) AS months_since_twoway,
            COUNT(*)                                        AS n_twoway_prior
    FROM    billing.suspension sp                                     -- [RENAME]
    JOIN    base ON base.subscriber_id = sp.subscriber_id
    WHERE   sp.suspend_type = 'TWO_WAY'                               -- [RENAME]
      AND   sp.reason       = 'NON_PAYMENT'                           -- [RENAME]
      -- strictly BEFORE t0: this is an input, not an outcome
      AND   sp.suspend_date <  base.t0
      AND   sp.suspend_date >= DATE_SUB(base.t0, INTERVAL 12 MONTH)
    GROUP   BY 1, 2
)
SELECT  CASE WHEN ps.months_since_twoway IS NULL THEN '0  never suspended'
             WHEN ps.months_since_twoway <  3    THEN '1  0-3 months ago'
             WHEN ps.months_since_twoway <  6    THEN '2  3-6 months ago'
             WHEN ps.months_since_twoway <  9    THEN '3  6-9 months ago'
             ELSE                                     '4  9-12 months ago'
        END                                             AS recency_group,
        COUNT(*)                                        AS n,
        COUNT(*) / SUM(COUNT(*)) OVER ()                AS share_of_base,
        AVG(l.y_v1)                                     AS bad_rate_v1,
        AVG(l.y_strict)                                 AS bad_rate_strict,
        -- relative risk against the never-suspended group
        AVG(l.y_v1) / NULLIF(MAX(AVG(l.y_v1)) OVER (ORDER BY 1 ROWS
                             BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED PRECEDING), 0)
                                                        AS lift_vs_never
FROM        label_table l
LEFT JOIN   prior_susp ps ON ps.subscriber_id = l.subscriber_id
                         AND ps.obs_cohort    = l.obs_cohort
GROUP   BY recency_group
ORDER   BY recency_group;

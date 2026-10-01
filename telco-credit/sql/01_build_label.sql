-- =====================================================================
--  Label build - spec v1  (see telco-credit/label_spec.md)
--  Telco micro-credit: 4 instalments settled on the monthly bill
--
--  Dialect: written for BigQuery / Hive-style SQL.
--    Oracle   -> DATE_DIFF(a,b,DAY) becomes (a - b);
--                DATE_ADD(d, INTERVAL n MONTH) becomes ADD_MONTHS(d, n)
--    Postgres -> DATE_DIFF(a,b,DAY) becomes (a - b);
--                DATE_ADD(d, INTERVAL n MONTH) becomes (d + n * INTERVAL '1 month')
--
--  >>> RENAME every  schema.table  and column marked  [RENAME]  <<<
-- =====================================================================

-- ---------------------------------------------------------------- params
--   N_BILLS    = 4   bills the instalments land on
--   OBS_MONTHS = 6   calendar months those 4 bills are watched for
--   BAD_DPD    = 60  days past due that counts as "bad"
--   LATE_DAYS  = 15  days past due that counts as "late" for rule 2
--   N_LATE     = 2   late bills that make rule 2 fire

WITH params AS (
    SELECT 4 AS n_bills, 6 AS obs_months,
           60 AS bad_dpd, 15 AS late_days, 2 AS n_late,
           0.98 AS settle_ratio
),

-- ---------------------------------------------------------- observation points
-- Edit this list to match your history depth. Each cohort needs 9 months of
-- feature window BEFORE t0 and 6 months of outcome window AFTER it, so the
-- earliest t0 sits 9 months into your data and the latest 6 months before its end.
cohorts AS (
    SELECT * FROM UNNEST([
        STRUCT('C1' AS obs_cohort, DATE '2024-10-01' AS t0),
        STRUCT('C2',               DATE '2025-01-01'),
        STRUCT('C3',               DATE '2025-04-01')   -- << hold out: never trained on
    ])
),

-- ------------------------------------------------------------------ population
-- Policy gates live here, NOT in the model. Anyone filtered out would also be
-- refused in production, so training on them would pollute the sample.
base AS (
    SELECT  s.subscriber_id,
            c.obs_cohort,
            c.t0,
            DATE_ADD(c.t0, INTERVAL p.obs_months MONTH)              AS window_end,
            DATE_DIFF(c.t0, s.activation_date, MONTH)                AS tenure_months
    FROM        crm.subscriber s          -- [RENAME]
    CROSS JOIN  cohorts c
    CROSS JOIN  params  p
    WHERE   s.sim_type      = 'PERMANENT'            -- [RENAME] postpaid only
      AND   s.customer_type = 'INDIVIDUAL'           -- [RENAME] no corporate / dealer
      AND   s.activation_date <= DATE_SUB(c.t0, INTERVAL 12 MONTH)
),

-- ---------------------------------------------------- payments, cumulated per bill
-- A bill is "settled" on the first date the cumulative payments against it reach
-- settle_ratio of its amount. Payments after window_end are invisible on purpose:
-- at T0 the model could not have known about them.
pay_cum AS (
    SELECT  pm.bill_id,
            pm.payment_date,
            SUM(pm.paid_amount) OVER (PARTITION BY pm.bill_id
                                      ORDER BY pm.payment_date
                                      ROWS BETWEEN UNBOUNDED PRECEDING
                                               AND CURRENT ROW)       AS cum_paid
    FROM    billing.payment pm                                        -- [RENAME]
),

-- --------------------------------------------- the 4 outcome bills, with their DPD
outcome_bills AS (
    SELECT  b.subscriber_id,
            base.obs_cohort,
            b.bill_period,
            b.bill_amount,
            COALESCE(tot.paid_total, 0)                               AS paid_total,
            -- days past due; an unsettled bill is charged its full age at window_end
            GREATEST(
                DATE_DIFF(COALESCE(st.settle_date, base.window_end),
                          b.due_date, DAY),
                0)                                                    AS dpd
    FROM        billing.bill b                                        -- [RENAME]
    JOIN        base   ON base.subscriber_id = b.subscriber_id
    CROSS JOIN  params p
    LEFT JOIN ( SELECT bill_id, SUM(paid_amount) AS paid_total
                FROM   billing.payment
                GROUP  BY 1 )                                    tot ON tot.bill_id = b.bill_id
    LEFT JOIN ( SELECT  pc.bill_id, MIN(pc.payment_date) AS settle_date
                FROM    pay_cum pc
                JOIN    billing.bill bb ON bb.bill_id = pc.bill_id
                JOIN    base bs         ON bs.subscriber_id = bb.subscriber_id
                CROSS JOIN params pp
                WHERE   pc.cum_paid     >= pp.settle_ratio * bb.bill_amount
                  AND   pc.payment_date <= bs.window_end
                GROUP   BY 1 )                                    st ON st.bill_id = b.bill_id
    -- the N_BILLS bills the instalments would land on
    WHERE   b.bill_period >= base.t0
      AND   b.bill_period <  DATE_ADD(base.t0, INTERVAL p.n_bills MONTH)
),

-- ------------------------------------- TWO-WAY suspension only (rule 3)
--  CRITICAL: the mid-cycle one-way cut fires when usage hits the number's credit
--  ceiling. That is consumption behaviour, not delinquency - including it would
--  label your heaviest (and most valuable) subscribers as bad. It is excluded here
--  and extracted as a FEATURE instead, in the feature query.
susp_out AS (
    SELECT  sp.subscriber_id, base.obs_cohort,
            MAX(1) AS had_twoway_susp
    FROM    billing.suspension sp                                     -- [RENAME]
    JOIN    base ON base.subscriber_id = sp.subscriber_id
    WHERE   sp.suspend_date >= base.t0
      AND   sp.suspend_date <  base.window_end
      AND   sp.suspend_type = 'TWO_WAY'            -- [RENAME] NOT the mid-cycle cut
      AND   sp.reason       = 'NON_PAYMENT'        -- [RENAME]
    GROUP BY 1, 2
),

-- ------------------------------------------- rows to drop entirely (not bad, not good)
exclusions AS (
    SELECT subscriber_id, obs_cohort, reason FROM (
        SELECT d.subscriber_id, base.obs_cohort, 'DISPUTE'  AS reason
        FROM billing.dispute d JOIN base ON base.subscriber_id = d.subscriber_id   -- [RENAME]
        WHERE d.open_date < base.window_end AND d.open_date >= base.t0
        UNION ALL
        SELECT s.subscriber_id, base.obs_cohort, 'DECEASED'
        FROM crm.subscriber s JOIN base ON base.subscriber_id = s.subscriber_id
        WHERE s.status_reason = 'DECEASED'                                          -- [RENAME]
        UNION ALL
        SELECT f.subscriber_id, base.obs_cohort, 'FRAUD'
        FROM risk.fraud_case f JOIN base ON base.subscriber_id = f.subscriber_id    -- [RENAME]
        UNION ALL
        -- churned mid-window: the outcome is censored, we never see how it ended
        SELECT s.subscriber_id, base.obs_cohort, 'CHURNED_IN_WINDOW'
        FROM crm.subscriber s JOIN base ON base.subscriber_id = s.subscriber_id
        WHERE s.deactivation_date IS NOT NULL                                       -- [RENAME]
          AND s.deactivation_date < base.window_end
    )
),

-- ------------------------------------------------------- aggregate to one row each
agg AS (
    SELECT  base.subscriber_id,
            base.obs_cohort,
            base.t0,
            base.tenure_months,
            COUNT(ob.bill_period)                                     AS n_bills_seen,
            MAX(ob.dpd)                                               AS max_dpd_out,
            SUM(CASE WHEN ob.dpd > p.late_days THEN 1 ELSE 0 END)     AS n_late_months_out,
            MIN(ob.paid_total / NULLIF(ob.bill_amount, 0))            AS min_pay_ratio_out,
            COALESCE(MAX(sx.had_twoway_susp), 0)                      AS had_twoway_susp,
            MAX(ex.reason)                                            AS exclude_reason
    FROM        base
    CROSS JOIN  params p
    LEFT JOIN   outcome_bills ob ON ob.subscriber_id = base.subscriber_id
                                AND ob.obs_cohort    = base.obs_cohort
    LEFT JOIN   susp_out      sx ON sx.subscriber_id = base.subscriber_id
                                AND sx.obs_cohort    = base.obs_cohort
    LEFT JOIN   exclusions    ex ON ex.subscriber_id = base.subscriber_id
                                AND ex.obs_cohort    = base.obs_cohort
    GROUP BY 1, 2, 3, 4
)

-- ============================== the label table ==============================
SELECT
    a.subscriber_id,
    a.obs_cohort,
    a.t0,
    a.tenure_months,
    a.n_bills_seen,
    a.max_dpd_out,
    a.n_late_months_out,
    a.min_pay_ratio_out,
    a.had_twoway_susp,
    a.exclude_reason,

    -- rule components, kept so the choice between variants can be re-made later
    CASE WHEN a.max_dpd_out       >= p.bad_dpd THEN 1 ELSE 0 END      AS rule1_dpd60,
    CASE WHEN a.n_late_months_out >= p.n_late  THEN 1 ELSE 0 END      AS rule2_late,
    a.had_twoway_susp                                                 AS rule3_susp,

    -- the four candidate labels - pick one AFTER looking at the bad rates
    CASE WHEN a.max_dpd_out >= p.bad_dpd
           OR a.had_twoway_susp = 1                   THEN 1 ELSE 0 END AS y_strict,
    CASE WHEN a.max_dpd_out >= p.bad_dpd
           OR a.n_late_months_out >= p.n_late
           OR a.had_twoway_susp = 1                   THEN 1 ELSE 0 END AS y_v1,
    CASE WHEN a.max_dpd_out >= p.bad_dpd
           OR a.n_late_months_out >= 3
           OR a.had_twoway_susp = 1                   THEN 1 ELSE 0 END AS y_v2,
    CASE WHEN a.n_late_months_out >= p.n_late         THEN 1 ELSE 0 END AS y_loose,

    -- one mild slip: neither good nor bad
    CASE WHEN a.max_dpd_out < p.bad_dpd
          AND a.had_twoway_susp = 0
          AND a.n_late_months_out = 1                 THEN 1 ELSE 0 END AS indeterminate
FROM        agg a
CROSS JOIN  params p
WHERE   a.exclude_reason IS NULL
  AND   a.n_bills_seen = p.n_bills      -- drop anyone without a full outcome window
;

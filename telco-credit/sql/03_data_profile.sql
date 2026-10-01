-- =====================================================================
--  Data profile - five statistics that size the product and the model
--  Run on a 200k-500k random sample unless stated otherwise.
--  Send back the OUTPUT of each; they decide limits, LGD and feasibility.
-- =====================================================================


-- ---------------------------------------------------------------------
-- S1. POPULATION FUNNEL   [highest priority]
--     How many survive each gate? This is the "can we reach 3M loans"
--     question answered directly. Run on the FULL base, not a sample.
-- ---------------------------------------------------------------------
WITH f AS (
    SELECT  s.subscriber_id,
            CASE WHEN s.sim_type = 'PERMANENT'                         THEN 1 ELSE 0 END AS g1_permanent,
            CASE WHEN s.customer_type = 'INDIVIDUAL'                   THEN 1 ELSE 0 END AS g2_individual,
            CASE WHEN s.status = 'ACTIVE'                              THEN 1 ELSE 0 END AS g3_active,
            CASE WHEN DATE_DIFF(CURRENT_DATE(), s.activation_date, MONTH) >= 12
                                                                       THEN 1 ELSE 0 END AS g4_tenure12,
            CASE WHEN b.avg_pay_3m >= 100000                           THEN 1 ELSE 0 END AS g5_pay100k,
            CASE WHEN COALESCE(d.current_debt_days, 0) = 0             THEN 1 ELSE 0 END AS g6_no_debt,
            CASE WHEN COALESCE(sp.n_twoway_6m, 0) = 0                  THEN 1 ELSE 0 END AS g7_no_recent_cut
    FROM        crm.subscriber s                                       -- [RENAME]
    LEFT JOIN   agg.billing_3m   b  ON b.subscriber_id  = s.subscriber_id   -- [RENAME]
    LEFT JOIN   billing.debt     d  ON d.subscriber_id  = s.subscriber_id   -- [RENAME]
    LEFT JOIN ( SELECT subscriber_id, COUNT(*) AS n_twoway_6m
                FROM   billing.suspension
                WHERE  suspend_type = 'TWO_WAY' AND reason = 'NON_PAYMENT'
                  AND  suspend_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
                GROUP  BY 1 )        sp ON sp.subscriber_id = s.subscriber_id
)
SELECT  COUNT(*)                                                                      AS step0_all,
        SUM(g1_permanent)                                                             AS step1_permanent,
        SUM(g1_permanent*g2_individual)                                               AS step2_individual,
        SUM(g1_permanent*g2_individual*g3_active)                                     AS step3_active,
        SUM(g1_permanent*g2_individual*g3_active*g4_tenure12)                         AS step4_tenure,
        SUM(g1_permanent*g2_individual*g3_active*g4_tenure12*g5_pay100k)              AS step5_pay100k,
        SUM(g1_permanent*g2_individual*g3_active*g4_tenure12*g5_pay100k*g6_no_debt)   AS step6_clean,
        SUM(g1_permanent*g2_individual*g3_active*g4_tenure12*g5_pay100k*g6_no_debt*g7_no_recent_cut)
                                                                                      AS step7_final
FROM    f;
--  ALSO RUN IT with g5 at 50k and 150k. If the 100k gate is what stands between
--  you and 3M loans, lowering it costs less risk than loosening the score cutoff:
--  a small clean customer is a better risk than a large messy one.


-- ---------------------------------------------------------------------
-- S2. PROVEN PAYMENT CAPACITY   [sizes every limit, and total disbursement]
--     P = largest bill the subscriber has actually settled on time.
--     The whole limit engine is anchored on this distribution.
-- ---------------------------------------------------------------------
WITH settled AS (
    SELECT  b.subscriber_id, b.bill_period, b.bill_amount,
            DATE_DIFF(st.settle_date, b.due_date, DAY) AS dpd
    FROM    billing.bill b                                             -- [RENAME]
    JOIN  ( SELECT  pc.bill_id, MIN(pc.payment_date) AS settle_date
            FROM  ( SELECT bill_id, payment_date,
                           SUM(paid_amount) OVER (PARTITION BY bill_id ORDER BY payment_date
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_paid
                    FROM   billing.payment ) pc
            JOIN    billing.bill bb ON bb.bill_id = pc.bill_id
            WHERE   pc.cum_paid >= 0.98 * bb.bill_amount
            GROUP   BY 1 ) st ON st.bill_id = b.bill_id
    WHERE   b.bill_period >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
),
cap AS (
    SELECT  subscriber_id,
            MAX(CASE WHEN dpd <= 0 THEN bill_amount END) AS proven_capacity,
            AVG(bill_amount)                             AS avg_bill,
            COUNT(CASE WHEN dpd <= 0 THEN 1 END)         AS n_ontime_months
    FROM    settled GROUP BY 1
)
SELECT  COUNT(*)                                                     AS n,
        AVG(CASE WHEN proven_capacity IS NULL THEN 1.0 ELSE 0 END)   AS pct_never_ontime,
        APPROX_QUANTILES(proven_capacity, 10)                        AS proven_capacity_deciles,
        APPROX_QUANTILES(avg_bill, 10)                               AS avg_bill_deciles,
        APPROX_QUANTILES(proven_capacity / NULLIF(avg_bill,0), 10)   AS headroom_ratio_deciles,
        AVG(n_ontime_months)                                         AS avg_ontime_months
FROM    cap;
--  headroom_ratio = proven capacity / average bill. This single number decides how
--  much room there is above a subscriber's normal bill, and therefore the limit.


-- ---------------------------------------------------------------------
-- S3. RECOVERY CURVE -> LGD   [the number I refuse to guess for you]
--     Of accounts that reached a two-way cut, how much is eventually
--     recovered, and how fast? LGD = 1 - recovery.
-- ---------------------------------------------------------------------
WITH cut AS (
    SELECT  sp.subscriber_id,
            MIN(sp.suspend_date)  AS cut_date,
            MAX(sp.debt_amount)   AS debt_at_cut                      -- [RENAME]
    FROM    billing.suspension sp
    WHERE   sp.suspend_type = 'TWO_WAY' AND sp.reason = 'NON_PAYMENT'
      AND   sp.suspend_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 24 MONTH)
                                AND DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    GROUP   BY 1
),
rec AS (
    SELECT  c.subscriber_id, c.debt_at_cut,
            SUM(CASE WHEN p.payment_date <= DATE_ADD(c.cut_date, INTERVAL  30 DAY) THEN p.paid_amount ELSE 0 END) AS r30,
            SUM(CASE WHEN p.payment_date <= DATE_ADD(c.cut_date, INTERVAL  90 DAY) THEN p.paid_amount ELSE 0 END) AS r90,
            SUM(CASE WHEN p.payment_date <= DATE_ADD(c.cut_date, INTERVAL 180 DAY) THEN p.paid_amount ELSE 0 END) AS r180,
            SUM(CASE WHEN p.payment_date <= DATE_ADD(c.cut_date, INTERVAL 365 DAY) THEN p.paid_amount ELSE 0 END) AS r365
    FROM    cut c
    LEFT JOIN billing.payment p ON p.subscriber_id = c.subscriber_id
                               AND p.payment_date >= c.cut_date
    GROUP   BY 1, 2
)
SELECT  COUNT(*)                                               AS n_cut_accounts,
        AVG(debt_at_cut)                                       AS avg_debt_at_cut,
        AVG(LEAST(r30  / NULLIF(debt_at_cut,0), 1))            AS recovery_30d,
        AVG(LEAST(r90  / NULLIF(debt_at_cut,0), 1))            AS recovery_90d,
        AVG(LEAST(r180 / NULLIF(debt_at_cut,0), 1))            AS recovery_180d,
        AVG(LEAST(r365 / NULLIF(debt_at_cut,0), 1))            AS recovery_365d,
        AVG(CASE WHEN r365 >= 0.98*debt_at_cut THEN 1.0 ELSE 0 END) AS pct_fully_recovered
FROM    rec;
--  LGD = 1 - recovery_365d.  If recovery lands near 0.45, LGD is 0.55 and the
--  notebook's placeholder was right; if it lands at 0.70, the product is far more
--  profitable than modelled and the limits can be larger.


-- ---------------------------------------------------------------------
-- S4. UNIVARIATE SIGNAL SCAN   [tells us if the Gini is reachable, cheaply]
--     Bad rate by decile for the candidate features. Needs the label table.
--     A feature whose bad rate is flat across deciles carries no signal;
--     one that goes 2% -> 25% is worth the extraction cost.
-- ---------------------------------------------------------------------
SELECT  feature, decile, n, bad_rate
FROM (
  SELECT 'dtp_mean'          AS feature, NTILE(10) OVER (ORDER BY f.dtp_mean)          AS decile, l.y_v1 AS y FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'dtp_trend',          NTILE(10) OVER (ORDER BY f.dtp_trend),          l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'pct_fast_pay',       NTILE(10) OVER (ORDER BY f.pct_fast_pay),       l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'pay_ratio_mean',     NTILE(10) OVER (ORDER BY f.pay_ratio_mean),     l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'n_midcycle_cuts',    NTILE(10) OVER (ORDER BY f.n_midcycle_cuts),    l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'tenure_months',      NTILE(10) OVER (ORDER BY f.tenure_months),      l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'bill_cv',            NTILE(10) OVER (ORDER BY f.bill_cv),            l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
  UNION ALL SELECT 'credit_ceiling_util',NTILE(10) OVER (ORDER BY f.credit_ceiling_util),l.y_v1 FROM feature_table f JOIN label_table l USING (subscriber_id, obs_cohort)
)
GROUP BY feature, decile
ORDER BY feature, decile;


-- ---------------------------------------------------------------------
-- S5. CREDIT CEILING - the risk judgement the operator already makes
--     How is it set, how close do people run to it, and does hitting it
--     predict anything? If the ceiling already encodes risk, it is both a
--     strong feature and a natural upper bound on the credit limit.
-- ---------------------------------------------------------------------
SELECT  APPROX_QUANTILES(s.credit_ceiling, 10)                          AS ceiling_deciles,   -- [RENAME]
        CORR(s.credit_ceiling, b.avg_bill_3m)                           AS corr_ceiling_bill,
        AVG(b.avg_bill_3m / NULLIF(s.credit_ceiling, 0))                AS avg_utilisation,
        AVG(CASE WHEN mc.n_cuts > 0 THEN 1.0 ELSE 0 END)                AS pct_ever_hit_ceiling,
        AVG(mc.avg_days_to_restore)                                     AS avg_days_to_restore
FROM        crm.subscriber s
LEFT JOIN   agg.billing_3m b ON b.subscriber_id = s.subscriber_id
LEFT JOIN ( SELECT subscriber_id, COUNT(*) AS n_cuts,
                   AVG(DATE_DIFF(restore_date, suspend_date, DAY)) AS avg_days_to_restore
            FROM   billing.suspension
            WHERE  suspend_type = 'ONE_WAY_MIDCYCLE'                    -- [RENAME]
              AND  suspend_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
            GROUP  BY 1 ) mc ON mc.subscriber_id = s.subscriber_id
WHERE   s.sim_type = 'PERMANENT';

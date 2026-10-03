-- ============================================================================
--  DCB credit dataset - v3, restructured for scale        (Trino / Presto)
--
--  Same logic as v2, rebuilt around one pass over the daily fact.
--
--  WHAT CHANGED AND WHY
--    1. sbrp_typ_id = 1 on every daily scan. bill_outstanding_amt is populated
--       only for permanent SIMs (36.9M non-null against 36M permanent), so this
--       cuts the scan by about 80 percent and loses nothing.
--
--    2. sbrp_stat_id is NOT filtered on the daily scans. The status changes over
--       time - 2 active, 3 one-way bar, 9 two-way bar - so filtering to 2 would
--       delete exactly the barred days the label is built from. It is a gate at
--       T0 only.
--
--    3. One daily pass instead of four. STEP 2 rolls the daily fact up to
--       subscriber-month once; DPD, bars and the label all read that rollup.
--
--    4. Debt runs are computed over MONTHS, not days. Within a month the
--       in-debt days are contiguous - the bill lands on day 1 and clears on
--       payment - so a month's debt_days IS its run length, and runs join
--       across months wherever the bill was still open at month end. Same
--       answer, about thirty times less sorting.
--
--  NO percent character anywhere (Python drivers read it as a format spec).
--  NO CASE expressions (IF and FILTER instead).
--  AMOUNTS ARE IN RIAL.
-- ============================================================================

-- ---------------------------------------------------------------------------
--  COHORT C1   <<< the only block to edit between runs
--    T0                 140405
--    feature months     140308 .. 140404   (9)
--    label bills        140405 .. 140408   (4)
--    watch through      140411
--    daily window       14030801 .. 14041130
--  Shock months to avoid in a clean cohort: 140412, 140501, 140502
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- STEP 1  BASE + the median invoice the materiality floor needs
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_base;
CREATE TABLE dwbi_temp40_db.dcb3_base WITH (format='PARQUET') AS
SELECT  s.sbrp_id,
        s.age_on_net_months,
        m.med_invoice
FROM (
    SELECT  sbrp_id, age_on_net_months
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key    = 140404      -- the month immediately before T0
      AND   sbrp_stat_id = 2           -- GATE: active at T0 (point in time only)
      AND   sbrp_typ_id  = 1           -- permanent
      AND   age_on_net_months >= 12
) s
INNER JOIN (
    SELECT  sbrp_id, APPROX_PERCENTILE(invoice_amt, 0.5) AS med_invoice
    FROM (  SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
            FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE  month_key BETWEEN 140308 AND 140404
              AND  sbrp_typ_id = 1
            GROUP BY sbrp_id, month_key ) a
    GROUP BY sbrp_id
    HAVING APPROX_PERCENTILE(invoice_amt, 0.5) > 0
) m ON m.sbrp_id = s.sbrp_id
-- GATE: not churned, and not barred in the 60 days before T0.
-- stat 4 and 8 are churn; stat 9 is a TWO-WAY BAR and belongs in the label,
-- so it must not be filtered as churn.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14030801 AND 14040431
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (4, 8)
) churn ON churn.sbrp_id = s.sbrp_id
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040301 AND 14040431
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (3, 9)
) barred ON barred.sbrp_id = s.sbrp_id
WHERE   churn.sbrp_id  IS NULL
  AND   barred.sbrp_id IS NULL
;


-- ---------------------------------------------------------------------------
-- STEP 2  THE ONE DAILY PASS
--
--  Rolls the daily fact up to one row per subscriber-month. Everything
--  downstream reads this instead of the daily table.
--
--  MATERIALITY: a balance counts as debt only above 25 percent of the
--  subscriber's own median invoice. Set from diagnostic D1/F4; if the balances
--  turn out to be whole unpaid bills only, drop it to 0.05.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_daily_rollup;
CREATE TABLE dwbi_temp40_db.dcb3_daily_rollup WITH (format='PARQUET') AS
SELECT  d.sbrp_id,
        d.day_key / 100                                               AS month_key,
        (d.day_key / 10000) * 12 + MOD(d.day_key / 100, 100)          AS month_idx,
        COUNT(*)                                                      AS days_seen,
        MAX(d.day_key)                                                AS last_day,
        -- ---- debt, against the subscriber's own bill
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 0.25 * b.med_invoice)
                                                                      AS debt_days,
        -- the in-debt flag ON THE LAST DAY of the month. MAX_BY avoids nesting
        -- a window function inside an aggregate, which Trino rejects.
        MAX_BY(IF(d.bill_outstanding_amt > 0.25 * b.med_invoice, 1, 0), d.day_key)
                                                                      AS open_at_month_end,
        MAX(d.bill_outstanding_amt)                                   AS bill_out_max,
        -- past due = still open after the 15th
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 0.25 * b.med_invoice
                           AND MOD(d.day_key, 100) > 15)              AS past_due_days,
        -- carried = more than one bill stacked, which only happens on a miss
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 1.5 * b.med_invoice)
                                                                      AS carried_days,
        -- ---- bars, by status. NOT filtered on stat: that is the point.
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 3)                    AS oneway_days,
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 9)                    AS twoway_days,
        -- a bar that began in a month carrying an overdue bill is non-payment;
        -- one with no overdue bill behind it is the credit ceiling
        MAX(IF(d.sbrp_stat_id = 3
               AND d.bill_outstanding_amt > 0.25 * b.med_invoice
               AND MOD(d.day_key, 100) > 15, 1, 0))                   AS nonpay_bar_day,
        MAX(IF(d.sbrp_stat_id = 3
               AND d.bill_outstanding_amt <= 0.25 * b.med_invoice, 1, 0))
                                                                      AS ceiling_bar_day,
        -- ---- ceiling pressure
        MAX(d.unbill_outstanding_amt)                                 AS unbill_max,
        AVG(d.unbill_outstanding_amt)                                 AS unbill_avg
FROM        dwbi_fact_db.v_fact_sbrp_daily_cip d
INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = d.sbrp_id
WHERE   d.day_key BETWEEN 14030801 AND 14041130    -- features AND watch window
  AND   d.sbrp_typ_id = 1
GROUP BY d.sbrp_id, d.day_key / 100,
         (d.day_key / 10000) * 12 + MOD(d.day_key / 100, 100)
;
--  If your engine has no MAX_BY, run STEP 2b instead and join it in.


-- ---------------------------------------------------------------------------
-- STEP 2b  open_at_month_end without MAX_BY. OPTIONAL - only if STEP 2 fails.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_month_end;
CREATE TABLE dwbi_temp40_db.dcb3_month_end WITH (format='PARQUET') AS
SELECT  e.sbrp_id,
        e.month_key,
        MAX(IF(d.bill_outstanding_amt > 0.25 * b.med_invoice, 1, 0)) AS open_at_month_end
FROM (
    SELECT sbrp_id, day_key / 100 AS month_key, MAX(day_key) AS last_day
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14030801 AND 14041130
      AND  sbrp_typ_id = 1
      AND  sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb3_base)
    GROUP BY sbrp_id, day_key / 100
) e
INNER JOIN  dwbi_fact_db.v_fact_sbrp_daily_cip d
                 ON d.sbrp_id = e.sbrp_id AND d.day_key = e.last_day
INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = e.sbrp_id
GROUP BY e.sbrp_id, e.month_key
;


-- ---------------------------------------------------------------------------
-- STEP 3  DEBT RUNS AND DPD - gaps and islands over MONTHS
--
--  Within a month the in-debt days run from day 1 to the day of payment, so a
--  month's debt_days is its run length. Runs join across months wherever the
--  bill was still open at month end. Sixteen rows per subscriber instead of
--  five hundred days.
--
--      DPD = run length in days, minus the 15-day grace
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_dpd;
CREATE TABLE dwbi_temp40_db.dcb3_dpd WITH (format='PARQUET') AS
WITH feat AS (
    SELECT * FROM dwbi_temp40_db.dcb3_daily_rollup
    WHERE  month_key BETWEEN 140308 AND 140404        -- feature window only
),
runs AS (
    SELECT  sbrp_id, month_idx, debt_days, open_at_month_end,
            -- a run ends at the first month that does not spill over, so the
            -- count of earlier non-spilling months identifies the run
            SUM(IF(open_at_month_end = 0, 1, 0)) OVER (
                PARTITION BY sbrp_id ORDER BY month_idx
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)  AS run_id
    FROM    feat
),
run_len AS (
    SELECT  sbrp_id, run_id, SUM(debt_days) AS run_days
    FROM    runs
    WHERE   debt_days > 0
    GROUP BY sbrp_id, run_id
)
SELECT  f.sbrp_id,
        GREATEST(COALESCE(MAX(r.run_days), 0) - 15, 0)        AS max_dpd_9m,
        COALESCE(MAX(r.run_days), 0)                          AS max_debt_run_days,
        COUNT(r.run_id)                                       AS n_debt_spells_9m,
        SUM(f.debt_days)                                      AS total_debt_days_9m,
        -- LATE MONTH: open at month end. Same definition the label uses.
        SUM(f.open_at_month_end)                              AS n_late_months_9m,
        -- settled inside the month but after the 15th: chronic mild lateness.
        -- A strong predictor, but not default behaviour - its own feature.
        COUNT(*) FILTER (WHERE f.open_at_month_end = 0 AND f.past_due_days > 0)
                                                              AS n_mild_late_months_9m,
        COUNT(*) FILTER (WHERE f.debt_days = 0)               AS n_ontime_months_9m,
        MAX(f.bill_out_max)                                   AS max_debt_amt_9m,
        MAX(f.unbill_max)                                     AS unbill_peak_9m,
        AVG(f.unbill_avg)                                     AS unbill_avg_9m,
        -- monthly debt-day panel
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140308)  AS debtdays_m1,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140309)  AS debtdays_m2,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140310)  AS debtdays_m3,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140311)  AS debtdays_m4,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140312)  AS debtdays_m5,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140401)  AS debtdays_m6,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140402)  AS debtdays_m7,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140403)  AS debtdays_m8,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140404)  AS debtdays_m9
FROM        feat f
LEFT JOIN   run_len r ON r.sbrp_id = f.sbrp_id
GROUP BY f.sbrp_id
;


-- ---------------------------------------------------------------------------
-- STEP 4  BARS IN THE FEATURE WINDOW
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_bars;
CREATE TABLE dwbi_temp40_db.dcb3_bars WITH (format='PARQUET') AS
SELECT  sbrp_id,
        SUM(oneway_days)                                      AS oneway_days_9m,
        SUM(twoway_days)                                      AS twoway_days_9m,
        SUM(nonpay_bar_day)                                   AS n_nonpay_bar_months_9m,
        SUM(ceiling_bar_day)                                  AS n_ceiling_bar_months_9m,
        COUNT(*) FILTER (WHERE oneway_days > 0 OR twoway_days > 0)
                                                              AS n_barred_months_9m,
        -- recency, in months before T0
        MAX(month_idx) FILTER (WHERE oneway_days > 0 OR twoway_days > 0)
                                                              AS last_bar_month_idx,
        MAX(month_idx) FILTER (WHERE twoway_days > 0)         AS last_twoway_month_idx,
        -- how fast service was restored: days barred per barred month
        CAST(SUM(oneway_days) AS DOUBLE)
          / NULLIF(COUNT(*) FILTER (WHERE oneway_days > 0), 0) AS avg_barred_days_per_spell
FROM    dwbi_temp40_db.dcb3_daily_rollup
WHERE   month_key BETWEEN 140308 AND 140404
GROUP BY sbrp_id
;


-- ---------------------------------------------------------------------------
-- STEP 5  MONTHLY PANEL - one pass over the monthly fact
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_panel;
CREATE TABLE dwbi_temp40_db.dcb3_panel WITH (format='PARQUET') AS
WITH mth AS (
    SELECT  c.sbrp_id, c.month_key,
            MAX(COALESCE(c.invoice_amt,0)) AS invoice_amt,
            MAX(COALESCE(c.pmnt_amt,0))    AS pmnt_amt,
            SUM(COALESCE(c.voi_pkg_rev,0) + COALESCE(c.voi_payg_rev,0)
                - COALESCE(c.intl_roam_voi_rev,0)) / 1.1
          + SUM(COALESCE(c.tot_sms_rev,0) - COALESCE(c.tot_sms_tax,0)
                - COALESCE(c.intl_roam_sms_rev,0))
          + SUM(COALESCE(c.tot_data_rev,0) - COALESCE(c.tot_data_tax,0)
                - COALESCE(c.post_intl_roam_data_rev,0)
                - COALESCE(c.pre_intl_roam_data_rev,0))              AS tot_rev,
            SUM(COALESCE(c.data_usg_actl_vol,0)) / POWER(1024,3)     AS data_gb,
            SUM(COALESCE(c.mo_cl_actl_dur,0)) / 60.0                 AS voice_min,
            SUM(COALESCE(c.mo_cl_cnt,0))                             AS call_cnt,
            SUM(COALESCE(c.intl_cl_cnt,0))                           AS intl_cl_cnt
    FROM        dwbi_fact_db.v_fact_sbrp_mthly_cip c
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
    WHERE   c.month_key BETWEEN 140308 AND 140404
      AND   c.sbrp_typ_id = 1
    GROUP BY c.sbrp_id, c.month_key
)
SELECT  sbrp_id,
        MAX(invoice_amt) FILTER (WHERE month_key=140308) AS invoice_m1,
        MAX(invoice_amt) FILTER (WHERE month_key=140309) AS invoice_m2,
        MAX(invoice_amt) FILTER (WHERE month_key=140310) AS invoice_m3,
        MAX(invoice_amt) FILTER (WHERE month_key=140311) AS invoice_m4,
        MAX(invoice_amt) FILTER (WHERE month_key=140312) AS invoice_m5,
        MAX(invoice_amt) FILTER (WHERE month_key=140401) AS invoice_m6,
        MAX(invoice_amt) FILTER (WHERE month_key=140402) AS invoice_m7,
        MAX(invoice_amt) FILTER (WHERE month_key=140403) AS invoice_m8,
        MAX(invoice_amt) FILTER (WHERE month_key=140404) AS invoice_m9,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140308) AS pmnt_m1,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140309) AS pmnt_m2,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140310) AS pmnt_m3,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140311) AS pmnt_m4,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140312) AS pmnt_m5,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140401) AS pmnt_m6,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140402) AS pmnt_m7,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140403) AS pmnt_m8,
        MAX(pmnt_amt)    FILTER (WHERE month_key=140404) AS pmnt_m9,
        MAX(tot_rev)     FILTER (WHERE month_key=140308) AS totrev_m1,
        MAX(tot_rev)     FILTER (WHERE month_key=140309) AS totrev_m2,
        MAX(tot_rev)     FILTER (WHERE month_key=140310) AS totrev_m3,
        MAX(tot_rev)     FILTER (WHERE month_key=140311) AS totrev_m4,
        MAX(tot_rev)     FILTER (WHERE month_key=140312) AS totrev_m5,
        MAX(tot_rev)     FILTER (WHERE month_key=140401) AS totrev_m6,
        MAX(tot_rev)     FILTER (WHERE month_key=140402) AS totrev_m7,
        MAX(tot_rev)     FILTER (WHERE month_key=140403) AS totrev_m8,
        MAX(tot_rev)     FILTER (WHERE month_key=140404) AS totrev_m9,
        SUM(data_gb)                                     AS data_gb_9m,
        SUM(data_gb)   FILTER (WHERE month_key >= 140402) AS data_gb_3m,
        SUM(voice_min)                                   AS voice_min_9m,
        SUM(voice_min) FILTER (WHERE month_key >= 140402) AS voice_min_3m,
        SUM(call_cnt)                                    AS call_cnt_9m,
        SUM(intl_cl_cnt)                                 AS intl_cl_cnt_9m,
        STDDEV_SAMP(tot_rev)                             AS totrev_std_9m,
        STDDEV_SAMP(data_gb)                             AS data_gb_std_9m,
        COUNT(*)                                         AS n_months_seen
FROM    mth
GROUP BY sbrp_id
;


-- ---------------------------------------------------------------------------
-- STEP 6  PAYMENT BEHAVIOUR, INCLUDING MID-CYCLE
--
--  cust_pmnt_typ_id: 4 end of cycle, 6 mid cycle.
--  PROVEN CAPACITY comes from TOTAL payments, not invoice_amt: a subscriber who
--  settles most of a bill mid-cycle met the full obligation even though the
--  invoice may only ever show the remainder.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_pay;
CREATE TABLE dwbi_temp40_db.dcb3_pay WITH (format='PARQUET') AS
WITH pm AS (
    SELECT  p.sbrp_id,
            p.day_key / 100                                     AS month_key,
            SUM(COALESCE(p.pmnt_amt,0))                         AS paid_total,
            SUM(COALESCE(p.pmnt_amt,0)) FILTER (WHERE p.cust_pmnt_typ_id = 6)
                                                                AS paid_midcycle,
            COUNT(*)                                            AS n_payments,
            COUNT(*) FILTER (WHERE p.cust_pmnt_typ_id = 6)      AS n_midcycle_payments,
            MIN(MOD(p.day_key, 100))                            AS first_pay_day
    FROM        dwbi_fact_db.v_fact_pmnt_adjmt p
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = p.sbrp_id
    WHERE   p.cust_pmnt_typ_id IN (4, 6)
      AND   p.bllg_pmnt_stat_id = 2
      AND   p.day_key BETWEEN 14030801 AND 14040431
    GROUP BY p.sbrp_id, p.day_key / 100
)
SELECT  sbrp_id,
        SUM(paid_total)                                   AS paid_total_9m,
        SUM(paid_midcycle)                                AS paid_midcycle_9m,
        SUM(paid_midcycle) / NULLIF(SUM(paid_total), 0)   AS midcycle_share,
        SUM(n_midcycle_payments)                          AS n_midcycle_payments_9m,
        SUM(n_payments)                                   AS n_payments_9m,
        AVG(first_pay_day)                                AS avg_first_pay_day,
        STDDEV_SAMP(paid_total)                           AS paid_std_9m,
        MAX(paid_total)                                   AS proven_capacity,
        APPROX_PERCENTILE(paid_total, 0.5)                AS median_monthly_paid,
        MAX(paid_total) / NULLIF(APPROX_PERCENTILE(paid_total, 0.5), 0)
                                                          AS capacity_headroom
FROM    pm
GROUP BY sbrp_id
;


-- ---------------------------------------------------------------------------
-- STEP 7  POINT-IN-TIME STATE AT T0
--         The ceiling is kept WITHOUT netting off current debt: the ceiling is
--         a risk judgement, the debt is a gate, and they do different jobs.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_pit;
CREATE TABLE dwbi_temp40_db.dcb3_pit WITH (format='PARQUET') AS
SELECT  c.sbrp_id,
        c.age_on_net_months,
        c.max_rat_id                                             AS network_id,
        COALESCE(c.initial_cred_lim_amt,0)                       AS initial_cred_lim_amt,
        COALESCE(c.temporary_cred_lim_amt,0)                     AS temporary_cred_lim_amt,
        COALESCE(c.rfndable_dpos_amt,0)                          AS rfndable_dpos_amt,
        COALESCE(c.non_rfndable_dpos_amt,0)                      AS non_rfndable_dpos_amt,
        COALESCE(c.advance_pmnt_amt,0)                           AS advance_pmnt_amt,
        COALESCE(c.bill_outstanding_amt,0)                       AS bill_outstanding_amt,
        COALESCE(c.unbill_outstanding_amt,0)                     AS unbill_outstanding_amt,
        (COALESCE(c.non_rfndable_dpos_amt,0) + COALESCE(c.initial_cred_lim_amt,0)) * 1.2
          + COALESCE(c.rfndable_dpos_amt,0) + COALESCE(c.advance_pmnt_amt,0)
          + COALESCE(c.temporary_cred_lim_amt,0)                 AS credit_ceiling,
        -- unbill against the ceiling IS the mid-cycle bar's trigger condition,
        -- so this measures how close to the edge the subscriber habitually runs
        COALESCE(c.unbill_outstanding_amt,0) /
          NULLIF((COALESCE(c.non_rfndable_dpos_amt,0)
                  + COALESCE(c.initial_cred_lim_amt,0)) * 1.2
                 + COALESCE(c.rfndable_dpos_amt,0) + COALESCE(c.advance_pmnt_amt,0)
                 + COALESCE(c.temporary_cred_lim_amt,0), 0)      AS ceiling_utilisation,
        COALESCE(c.debt_scr, 0)                                  AS debt_scr,
        COALESCE(c.suspend_scr, 0)                               AS suspend_scr
FROM        dwbi_fact_db.v_fact_sbrp_mthly_cip c
INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
WHERE   c.month_key = 140404
  AND   c.sbrp_typ_id = 1
;


-- ---------------------------------------------------------------------------
-- STEP 8  THE LABEL - from the same rollup
--
--  4 bills (140405..140408), watched through 140411.
--
--  y = 1 if   max DPD >= 60
--        or   the bill was still open at the end of 2 or more months
--        or   a NON-PAYMENT one-way bar occurred
--
--  Escalation to a two-way bar is severity, not the trigger: it takes three
--  unresolved months, so a two-way rule fires late and is right-censored at the
--  end of the window. Ceiling bars never enter the label.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_label;
CREATE TABLE dwbi_temp40_db.dcb3_label WITH (format='PARQUET') AS
WITH out AS (
    SELECT * FROM dwbi_temp40_db.dcb3_daily_rollup
    WHERE  month_key BETWEEN 140405 AND 140411
),
runs AS (
    SELECT  sbrp_id, month_idx, debt_days, open_at_month_end,
            SUM(IF(open_at_month_end = 0, 1, 0)) OVER (
                PARTITION BY sbrp_id ORDER BY month_idx
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS run_id
    FROM    out
),
run_len AS (
    SELECT sbrp_id, run_id, SUM(debt_days) AS run_days
    FROM   runs WHERE debt_days > 0
    GROUP BY sbrp_id, run_id
),
churned AS (
    -- churn only. stat 9 is a two-way bar and belongs in the label.
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040501 AND 14041130
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (4, 8)
),
agg AS (
    SELECT  o.sbrp_id,
            COUNT(*)                                        AS n_months_seen,
            GREATEST(COALESCE(MAX(r.run_days), 0) - 15, 0)  AS max_dpd_out,
            SUM(o.open_at_month_end)                        AS n_late_out,
            SUM(o.debt_days)                                AS total_debt_days_out,
            MAX(o.nonpay_bar_day)                           AS had_nonpay_oneway,
            SUM(o.nonpay_bar_day)                           AS n_nonpay_bar_months,
            MAX(o.ceiling_bar_day)                          AS had_ceiling_oneway,
            MAX(IF(o.twoway_days > 0, 1, 0))                AS escalated_twoway,
            COUNT(*) FILTER (WHERE o.twoway_days > 0)       AS twoway_months_out,
            SUM(o.oneway_days)                              AS oneway_days_out,
            SUM(o.twoway_days)                              AS twoway_days_out,
            MAX(IF(c.sbrp_id IS NULL, 0, 1))                AS churned_flag
    FROM        out o
    LEFT JOIN   run_len r ON r.sbrp_id = o.sbrp_id
    LEFT JOIN   churned c ON c.sbrp_id = o.sbrp_id
    GROUP BY o.sbrp_id
)
SELECT  sbrp_id,
        n_months_seen, max_dpd_out, n_late_out, total_debt_days_out,
        oneway_days_out, twoway_days_out, twoway_months_out,
        had_nonpay_oneway, n_nonpay_bar_months, escalated_twoway,
        had_ceiling_oneway,
        -- rule components, stored so a variant can be re-chosen without re-querying
        IF(max_dpd_out >= 60, 1, 0)                        AS rule1_dpd60,
        IF(n_late_out  >= 2,  1, 0)                        AS rule2_late,
        had_nonpay_oneway                                  AS rule3_nonpay_bar,
        escalated_twoway                                   AS rule4_escalated,
        -- the candidates, most to least conservative
        IF(twoway_months_out >= 2, 1, 0)                   AS y_twoway_2m,
        IF(escalated_twoway = 1, 1, 0)                     AS y_severe,
        IF(max_dpd_out >= 60 OR had_nonpay_oneway = 1, 1, 0)                     AS y_strict,
        IF(max_dpd_out >= 60 OR n_late_out >= 2 OR had_nonpay_oneway = 1, 1, 0)  AS y_v1,
        IF(max_dpd_out >= 60 OR n_late_out >= 3 OR had_nonpay_oneway = 1, 1, 0)  AS y_v2,
        IF(n_late_out >= 2, 1, 0)                                                AS y_loose,
        IF(max_dpd_out < 60 AND had_nonpay_oneway = 0 AND n_late_out = 1, 1, 0)  AS indeterminate
FROM    agg
WHERE   churned_flag  = 0       -- censored outcome
  AND   n_months_seen >= 6      -- incomplete watch window
;


-- ---------------------------------------------------------------------------
-- STEP 9  ASSEMBLY
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_dataset_c1;
CREATE TABLE dwbi_temp40_db.dcb3_dataset_c1 WITH (format='PARQUET') AS
SELECT  '140405' AS obs_cohort, b.sbrp_id, b.med_invoice,
        dpd.*, bar.*, pan.*, pay.*, pit.*,
        lab.y_twoway_2m, lab.y_severe, lab.y_strict, lab.y_v1, lab.y_v2,
        lab.y_loose, lab.indeterminate,
        lab.max_dpd_out, lab.n_late_out, lab.total_debt_days_out,
        lab.oneway_days_out, lab.twoway_days_out, lab.twoway_months_out,
        lab.had_nonpay_oneway, lab.n_nonpay_bar_months, lab.escalated_twoway,
        lab.had_ceiling_oneway,
        lab.rule1_dpd60, lab.rule2_late, lab.rule3_nonpay_bar, lab.rule4_escalated
FROM        dwbi_temp40_db.dcb3_base   b
INNER JOIN  dwbi_temp40_db.dcb3_label  lab ON lab.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_dpd    dpd ON dpd.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_bars   bar ON bar.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_panel  pan ON pan.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pay    pay ON pay.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pit    pit ON pit.sbrp_id = b.sbrp_id
;
--  Drop the duplicated sbrp_id columns the .* joins create before exporting.


-- ---------------------------------------------------------------------------
--  SANITY CHECKS
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS n_rows, COUNT(DISTINCT sbrp_id) AS n_subs
FROM   dwbi_temp40_db.dcb3_dataset_c1;

SELECT AVG(y_twoway_2m) AS bad_twoway_2m, AVG(y_severe) AS bad_severe,
       AVG(y_strict)    AS bad_strict,    AVG(y_v1)     AS bad_v1,
       AVG(y_v2)        AS bad_v2,        AVG(y_loose)  AS bad_loose,
       AVG(indeterminate) AS indet
FROM   dwbi_temp40_db.dcb3_dataset_c1;      -- target band: 5 to 15 pct

SELECT rule1_dpd60, rule2_late, rule3_nonpay_bar, rule4_escalated, COUNT(*) AS n
FROM   dwbi_temp40_db.dcb3_dataset_c1
GROUP BY 1,2,3,4 ORDER BY n DESC;

-- ceiling bars must look DIFFERENT from non-payment bars. If both groups show
-- the same bad rate, the split is not working and the floor needs revisiting.
SELECT had_nonpay_oneway, had_ceiling_oneway, COUNT(*) AS n,
       AVG(max_dpd_out) AS avg_dpd, AVG(y_v1) AS bad_rate
FROM   dwbi_temp40_db.dcb3_dataset_c1
GROUP BY 1,2 ORDER BY n DESC;

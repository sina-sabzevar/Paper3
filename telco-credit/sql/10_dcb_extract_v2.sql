-- ============================================================================
--  DCB credit dataset - rewritten extraction          (Trino / Presto syntax)
--
--  Replaces the 38-step temp_baseeN chain. Same source tables, same dialect.
--  What changed and why: see REVIEW_of_DCB_queries.md
--
--  KEY FIXES
--    1. every window is derived from T0, never from "today"
--    2. the three barring types stay SEPARATE (mid-cycle = usage, not default)
--    3. a real monthly panel instead of 3-month averages
--    4. DPD, pay_ratio and proven_capacity added - the missing credit signal
--    5. label rebuilt around repayment, not revenue continuity
--    7. the label fires on the NON-PAYMENT one-way bar, not on the two-way bar:
--       one-way escalates to two-way only after 3 months, so a two-way-only rule
--       is both three months late and right-censored at the end of the window
--    6. one GROUP BY per source table instead of 38 LEFT JOINs
--
--  AMOUNTS ARE IN RIAL.  400,000 Toman = 4,000,000 Rial.
-- ============================================================================


-- ============================================================================
--  COHORT CALENDAR   <<< the only block to edit between runs
-- ============================================================================
--  now = 1405-07.  Last closed month = 140506.
--  Revenue shock months (network-wide): 140412, 140501, 140502
--
--  cohort  T0       feature months (9)      label bills (4)          watch to
--  ------  -------  ----------------------  -----------------------  --------
--  C1      140405   140308 .. 140404        140405..140408           140411   <- CLEAN
--  C2      140408   140311 .. 140407        140408..140411           140502   <- watch touches shock
--  C3      140411   140402 .. 140410        140411,140412,140501,2   140505   <- stress cohort
--
--  Run the whole script once per cohort, changing ONLY the literals below and
--  the output table suffix. C1 calibrates the PD level; C3 measures how the
--  model degrades under stress.
--
--  THIS RUN = C1
--    feature months m1..m9 : 140308 140309 140310 140311 140312 140401 140402 140403 140404
--    T0                    : 140405
--    label bill months     : 140405 140406 140407 140408
--    label watch through   : 140411
-- ============================================================================


-- ----------------------------------------------------------------------------
-- STEP 1  BASE POPULATION + POLICY GATES
--         Anyone filtered here would also be refused in production, so they
--         must not reach the training sample either.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_base;
CREATE TABLE dwbi_temp40_db.dcb_c1_base WITH (format='PARQUET') AS
SELECT  c.sbrp_id,
        c.age_on_net_months,
        c.sbrp_stat_id
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip c
WHERE   c.month_key   = 140404          -- the month immediately before T0
  AND   c.sbrp_stat_id = 2              -- active
  AND   c.sbrp_typ_id  = 1              -- permanent / postpaid
  AND   c.age_on_net_months >= 12       -- gate: at least a year on net
  -- churn / removal check is relative to T0, NOT to today
  AND   c.sbrp_id NOT IN (
            SELECT DISTINCT sbrp_id
            FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
            WHERE  sbrp_stat_id IN (4, 8, 9)
              AND  day_key BETWEEN 14030801 AND 14040431 )
;

-- ----------------------------------------------------------------------------
-- STEP 2  MONTHLY PANEL - one pass over the monthly fact
--         m1 = oldest (140308) ... m9 = newest (140404)
--         Three quantities per month: invoice, payment, total revenue.
--         These 27 columns are what every trend/volatility feature is built
--         from in Python. Averaging them here throws that away permanently.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_panel;
CREATE TABLE dwbi_temp40_db.dcb_c1_panel WITH (format='PARQUET') AS
WITH mth AS (
    SELECT  sbrp_id,
            month_key,
            MAX(COALESCE(invoice_amt, 0)) AS invoice_amt,
            MAX(COALESCE(pmnt_amt,    0)) AS pmnt_amt,
            SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + SUM(COALESCE(tot_sms_rev,0)  - COALESCE(tot_sms_tax,0)
                - COALESCE(intl_roam_sms_rev,0))
          + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                - COALESCE(post_intl_roam_data_rev,0)
                - COALESCE(pre_intl_roam_data_rev,0))        AS tot_rev,
            SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                - COALESCE(post_intl_roam_data_rev,0)
                - COALESCE(pre_intl_roam_data_rev,0))        AS data_rev,
            SUM(COALESCE(data_usg_actl_vol,0)) / POWER(1024,3) AS data_gb,
            SUM(COALESCE(mo_cl_actl_dur,0)) / 60.0             AS voice_min,
            SUM(COALESCE(mo_cl_cnt,0))                         AS call_cnt,
            SUM(COALESCE(intl_cl_cnt,0))                       AS intl_cl_cnt
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140308,140309,140310,140311,140312,
                          140401,140402,140403,140404)
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY sbrp_id, month_key
)
SELECT  sbrp_id,
        -- ---- invoice panel
        MAX(CASE WHEN month_key=140308 THEN invoice_amt END) AS invoice_m1,
        MAX(CASE WHEN month_key=140309 THEN invoice_amt END) AS invoice_m2,
        MAX(CASE WHEN month_key=140310 THEN invoice_amt END) AS invoice_m3,
        MAX(CASE WHEN month_key=140311 THEN invoice_amt END) AS invoice_m4,
        MAX(CASE WHEN month_key=140312 THEN invoice_amt END) AS invoice_m5,
        MAX(CASE WHEN month_key=140401 THEN invoice_amt END) AS invoice_m6,
        MAX(CASE WHEN month_key=140402 THEN invoice_amt END) AS invoice_m7,
        MAX(CASE WHEN month_key=140403 THEN invoice_amt END) AS invoice_m8,
        MAX(CASE WHEN month_key=140404 THEN invoice_amt END) AS invoice_m9,
        -- ---- payment panel
        MAX(CASE WHEN month_key=140308 THEN pmnt_amt END) AS pmnt_m1,
        MAX(CASE WHEN month_key=140309 THEN pmnt_amt END) AS pmnt_m2,
        MAX(CASE WHEN month_key=140310 THEN pmnt_amt END) AS pmnt_m3,
        MAX(CASE WHEN month_key=140311 THEN pmnt_amt END) AS pmnt_m4,
        MAX(CASE WHEN month_key=140312 THEN pmnt_amt END) AS pmnt_m5,
        MAX(CASE WHEN month_key=140401 THEN pmnt_amt END) AS pmnt_m6,
        MAX(CASE WHEN month_key=140402 THEN pmnt_amt END) AS pmnt_m7,
        MAX(CASE WHEN month_key=140403 THEN pmnt_amt END) AS pmnt_m8,
        MAX(CASE WHEN month_key=140404 THEN pmnt_amt END) AS pmnt_m9,
        -- ---- total revenue panel
        MAX(CASE WHEN month_key=140308 THEN tot_rev END) AS totrev_m1,
        MAX(CASE WHEN month_key=140309 THEN tot_rev END) AS totrev_m2,
        MAX(CASE WHEN month_key=140310 THEN tot_rev END) AS totrev_m3,
        MAX(CASE WHEN month_key=140311 THEN tot_rev END) AS totrev_m4,
        MAX(CASE WHEN month_key=140312 THEN tot_rev END) AS totrev_m5,
        MAX(CASE WHEN month_key=140401 THEN tot_rev END) AS totrev_m6,
        MAX(CASE WHEN month_key=140402 THEN tot_rev END) AS totrev_m7,
        MAX(CASE WHEN month_key=140403 THEN tot_rev END) AS totrev_m8,
        MAX(CASE WHEN month_key=140404 THEN tot_rev END) AS totrev_m9,
        -- ---- usage: aggregates are enough for this tier-2 group
        SUM(data_gb)                                              AS data_gb_9m,
        SUM(CASE WHEN month_key >= 140402 THEN data_gb END)       AS data_gb_3m,
        SUM(voice_min)                                            AS voice_min_9m,
        SUM(CASE WHEN month_key >= 140402 THEN voice_min END)     AS voice_min_3m,
        SUM(call_cnt)                                             AS call_cnt_9m,
        SUM(intl_cl_cnt)                                          AS intl_cl_cnt_9m,
        SUM(data_rev)                                             AS data_rev_9m,
        SUM(CASE WHEN month_key >= 140402 THEN data_rev END)      AS data_rev_3m,
        -- volatility, computed on the real monthly series
        STDDEV_SAMP(tot_rev)                                      AS totrev_std_9m,
        STDDEV_SAMP(data_gb)                                      AS data_gb_std_9m,
        -- data share of revenue, guarded against divide-by-zero
        SUM(data_rev) / NULLIF(SUM(tot_rev), 0)                   AS data_rev_share,
        COUNT(*)                                                  AS n_months_seen
FROM    mth
GROUP BY sbrp_id
;

-- ----------------------------------------------------------------------------
-- STEP 3  DPD PANEL  - the strongest signal, and the one currently missing
--
--  ASSUMPTION TO CONFIRM: v_fact_cust_bil_daily holds, per day, the outstanding
--  balance (debit_amt) of billing cycle `bilcycl`. If so, days-past-due is the
--  number of days that balance stayed above the materiality threshold.
--  If the table has no day_key, use the fallback in STEP 3b instead.
--
--  DEBT_MIN_RIAL = 200,000 Rial (20,000 Toman) - the same materiality floor the
--  existing khosh-hesabi score uses, so the two stay comparable.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_dpd;
CREATE TABLE dwbi_temp40_db.dcb_c1_dpd WITH (format='PARQUET') AS
WITH d AS (
    SELECT  sbrp_id,
            bilcycl,
            COUNT(*) FILTER (WHERE debit_amt > 200000) AS dpd_days,
            MAX(debit_amt)                             AS max_debt_amt
    FROM    dwbi_fact_db.v_fact_cust_bil_daily
    WHERE   bilcycl IN (140308,140309,140310,140311,140312,
                        140401,140402,140403,140404)
      AND   cust_bil_typ_id = '983116577831777608312765670515538102764700000000'
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY sbrp_id, bilcycl
)
SELECT  sbrp_id,
        MAX(CASE WHEN bilcycl=140308 THEN dpd_days END) AS dpd_m1,
        MAX(CASE WHEN bilcycl=140309 THEN dpd_days END) AS dpd_m2,
        MAX(CASE WHEN bilcycl=140310 THEN dpd_days END) AS dpd_m3,
        MAX(CASE WHEN bilcycl=140311 THEN dpd_days END) AS dpd_m4,
        MAX(CASE WHEN bilcycl=140312 THEN dpd_days END) AS dpd_m5,
        MAX(CASE WHEN bilcycl=140401 THEN dpd_days END) AS dpd_m6,
        MAX(CASE WHEN bilcycl=140402 THEN dpd_days END) AS dpd_m7,
        MAX(CASE WHEN bilcycl=140403 THEN dpd_days END) AS dpd_m8,
        MAX(CASE WHEN bilcycl=140404 THEN dpd_days END) AS dpd_m9,
        MAX(max_debt_amt)                               AS max_debt_amt_9m,
        MAX(dpd_days)                                   AS max_dpd_9m,
        COUNT(*) FILTER (WHERE dpd_days > 15)           AS n_late_months_9m,
        COUNT(*) FILTER (WHERE dpd_days = 0)            AS n_ontime_months_9m
FROM    d
GROUP BY sbrp_id
;

-- ----------------------------------------------------------------------------
-- STEP 4  BARRING EVENTS - the three types kept APART
--
--  tot_mdtrm_two_way_cl_barr_curr_mth fires when usage reaches the number's
--  credit ceiling. That is consumption, not delinquency. Folding it in with the
--  other two - as the current khosh-hesabi score does - penalises the heaviest
--  and most valuable subscribers for being heavy.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_barr;
CREATE TABLE dwbi_temp40_db.dcb_c1_barr WITH (format='PARQUET') AS
SELECT  sbrp_id,
        -- counts
        COUNT(*) FILTER (WHERE tot_one_way_cl_barr_curr_mth          > 0) AS n_oneway_9m,
        COUNT(*) FILTER (WHERE tot_mdtrm_two_way_cl_barr_curr_mth    > 0) AS n_midcycle_9m,
        COUNT(*) FILTER (WHERE tot_two_way_cl_barr_curr_mth          > 0) AS n_twoway_9m,
        -- recency: months between the last event of each type and T0
        MIN(CASE WHEN tot_two_way_cl_barr_curr_mth > 0
                 THEN DATE_DIFF('month',
                        DATE(FORMAT('%d-%02d-01', month_key/100, month_key%100)),
                        DATE('1404-05-01')) END)                      AS months_since_twoway,
        MIN(CASE WHEN tot_one_way_cl_barr_curr_mth > 0
                 THEN DATE_DIFF('month',
                        DATE(FORMAT('%d-%02d-01', month_key/100, month_key%100)),
                        DATE('1404-05-01')) END)                      AS months_since_oneway,
        -- the operator's own score components, kept separate from the score
        SUM(COALESCE(debt_scr, 0))                                    AS debt_scr_sum,
        SUM(COALESCE(suspend_scr, 0))                                 AS suspend_scr_sum
FROM    dwbi_fact_db.v_fact_sbrp_mthly m
WHERE   m.month_key IN (140308,140309,140310,140311,140312,
                        140401,140402,140403,140404)
  AND   m.sbrp_typ_id = 1
  AND   m.cust_typ_id = 1
  AND   m.sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
GROUP BY sbrp_id
;
--  NOTE: months_since_* uses DATE_DIFF on a Gregorian-shaped literal only to get
--  a month count; the keys are Jalali. If your Trino lacks the udf, replace with
--  a plain arithmetic month index:  (month_key/100)*12 + (month_key%100).

-- ----------------------------------------------------------------------------
-- STEP 5  MID-CYCLE CUT: how fast did they pay to get reconnected?
--         The cut itself is not a credit signal. The time to clear it is -
--         it measures how quickly the subscriber can reach cash.
--         sbrp_stat_id = 3 is the barred state in the daily fact.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_restore;
CREATE TABLE dwbi_temp40_db.dcb_c1_restore WITH (format='PARQUET') AS
WITH runs AS (
    SELECT  sbrp_id, day_key, sbrp_stat_id,
            LAG(sbrp_stat_id) OVER (PARTITION BY sbrp_id ORDER BY day_key) AS prev_stat
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE   day_key BETWEEN 14030801 AND 14040431
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
)
SELECT  sbrp_id,
        COUNT(*) FILTER (WHERE sbrp_stat_id = 3)                 AS barred_days_9m,
        COUNT(*) FILTER (WHERE prev_stat = 2 AND sbrp_stat_id = 3) AS n_bar_starts_9m,
        -- average length of a barred spell = barred days / number of spells
        CAST(COUNT(*) FILTER (WHERE sbrp_stat_id = 3) AS DOUBLE)
          / NULLIF(COUNT(*) FILTER (WHERE prev_stat = 2 AND sbrp_stat_id = 3), 0)
                                                                 AS avg_days_to_restore
FROM    runs
GROUP BY sbrp_id
;

-- ----------------------------------------------------------------------------
-- STEP 6  POINT-IN-TIME STATE AT T0
--         Credit-ceiling components kept separate. The existing available_credit
--         formula nets off bill_outstanding_amt, which mixes the ceiling (a risk
--         judgement) with current debt (a gate). They do different jobs.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_pit;
CREATE TABLE dwbi_temp40_db.dcb_c1_pit WITH (format='PARQUET') AS
SELECT  sbrp_id,
        age_on_net_months,
        max_rat_id                                                AS network_id,
        COALESCE(initial_cred_lim_amt,0)                          AS initial_cred_lim_amt,
        COALESCE(temporary_cred_lim_amt,0)                        AS temporary_cred_lim_amt,
        COALESCE(rfndable_dpos_amt,0)                             AS rfndable_dpos_amt,
        COALESCE(non_rfndable_dpos_amt,0)                         AS non_rfndable_dpos_amt,
        COALESCE(advance_pmnt_amt,0)                              AS advance_pmnt_amt,
        COALESCE(bill_outstanding_amt,0)                          AS bill_outstanding_amt,
        -- the ceiling itself, WITHOUT netting off current debt
        (COALESCE(non_rfndable_dpos_amt,0) + COALESCE(initial_cred_lim_amt,0)) * 1.2
          + COALESCE(rfndable_dpos_amt,0) + COALESCE(advance_pmnt_amt,0)
          + COALESCE(temporary_cred_lim_amt,0)                    AS credit_ceiling
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140404                 -- last month before T0
  AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
;

-- ----------------------------------------------------------------------------
-- STEP 7  ACTIVITY DAYS - with the parentheses the original is missing
--         The current version reads as
--             data>0 OR (voice>0 AND day_key BETWEEN ...)
--         so the date filter never applies to the data branch and the count
--         covers the whole history instead of the window.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_active;
CREATE TABLE dwbi_temp40_db.dcb_c1_active WITH (format='PARQUET') AS
SELECT  sbrp_id,
        COUNT(DISTINCT day_key) FILTER (WHERE day_key >= 14040201) AS active_days_3m,
        COUNT(DISTINCT day_key)                                    AS active_days_9m,
        -- usage momentum: last 7 days of the window vs first 7 days.
        -- SIGN CONVENTION: positive = growing. Applied to every change feature.
        SUM(COALESCE(data_usg_actl_vol,0))
            FILTER (WHERE day_key BETWEEN 14040425 AND 14040431) / POWER(1024,3)
          - SUM(COALESCE(data_usg_actl_vol,0))
            FILTER (WHERE day_key BETWEEN 14030801 AND 14030807) / POWER(1024,3)
                                                                   AS data_gb_change_wk,
        SUM(COALESCE(tot_cl_actl_dur,0))
            FILTER (WHERE day_key BETWEEN 14040425 AND 14040431) / 60.0
          - SUM(COALESCE(tot_cl_actl_dur,0))
            FILTER (WHERE day_key BETWEEN 14030801 AND 14030807) / 60.0
                                                                   AS voice_min_change_wk
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14030801 AND 14040431
  AND   (COALESCE(data_usg_actl_vol,0) > 0 OR COALESCE(tot_cl_actl_dur,0) > 0)
  AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
GROUP BY sbrp_id
;

-- ----------------------------------------------------------------------------
-- STEP 8  NETWORK MONTHLY INDEX - 24 rows, and the most important small table
--
--  Revenue fell network-wide in 140412, 140501 and 140502. Without this index,
--  every money feature reads a shared drop as individual decline, and the limit
--  engine hands the largest loans to whoever fell furthest. Dividing each
--  month's amount by its network median removes the shock, inflation and
--  seasonality in one step - what remains is the subscriber's relative position,
--  which is what actually carries risk.
--
--  Built on the FULL postpaid base, not the sample.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_network_index;
CREATE TABLE dwbi_temp40_db.dcb_network_index WITH (format='PARQUET') AS
SELECT  month_key,
        APPROX_PERCENTILE(tot_rev, 0.5)     AS median_tot_rev,
        APPROX_PERCENTILE(invoice_amt, 0.5) AS median_invoice,
        AVG(tot_rev)                        AS mean_tot_rev,
        COUNT(*)                            AS n_subscribers
FROM (
    SELECT  sbrp_id, month_key,
            MAX(COALESCE(invoice_amt,0))                              AS invoice_amt,
            SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                - COALESCE(intl_roam_sms_rev,0))
          + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                - COALESCE(post_intl_roam_data_rev,0)
                - COALESCE(pre_intl_roam_data_rev,0))                 AS tot_rev
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140301 AND 140506
      AND   sbrp_typ_id  = 1
      AND   sbrp_stat_id = 2
    GROUP BY sbrp_id, month_key
) t
GROUP BY month_key
ORDER BY month_key
;

-- ============================================================================
--  STEP 9   THE LABEL
--
--  4 bills (140405..140408), watched through 140411.
--
--  WHY THE ONE-WAY BAR AND NOT THE TWO-WAY BAR
--  A one-way bar escalates to two-way only after 3 unresolved months, so the
--  two-way event is a lagging indicator:
--    - it fires three months after the trouble starts, long after a 4-instalment
--      loan has already gone wrong;
--    - and it is right-censored - a one-way bar in the last outcome month cannot
--      become two-way before the watch window closes, so late failures are
--      systematically invisible and the bad rate comes out too low.
--  The one-way bar is the timely, observable event. Escalation is kept as a
--  separate severity flag rather than as the trigger.
--
--  SEPARATING THE TWO KINDS OF ONE-WAY BAR
--  A one-way bar has two causes: non-payment, and usage reaching the number's
--  credit ceiling. Only the first is a credit event. With no reason code, they
--  are told apart by the debt state in that month:
--      one-way bar + past-due debt from an EARLIER cycle -> non-payment  (bad)
--      one-way bar + no past-due debt                    -> ceiling       (not bad)
--
--  >>> CONFIRM THE COLUMN MAPPING BEFORE RUNNING <<<
--  This assumes tot_one_way_cl_barr_curr_mth is the dunning bar and
--  tot_mdtrm_two_way_cl_barr_curr_mth is the mid-cycle ceiling bar. If the
--  mapping is the other way round, swap them here and in STEP 4.
-- ============================================================================
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_c1_label;
CREATE TABLE dwbi_temp40_db.dcb_c1_label WITH (format='PARQUET') AS
WITH outcome_dpd AS (
    -- days past due per outcome bill, observed to the end of the watch window
    SELECT  sbrp_id,
            bilcycl,
            COUNT(*) FILTER (WHERE debit_amt > 200000) AS dpd_days,
            MAX(debit_amt)                             AS max_debt
    FROM    dwbi_fact_db.v_fact_cust_bil_daily
    WHERE   bilcycl IN (140405, 140406, 140407, 140408)
      AND   day_key <= 14041130                  -- watch closes at 1404-11
      AND   cust_bil_typ_id = '983116577831777608312765670515538102764700000000'
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY sbrp_id, bilcycl
),
-- past-due debt carried INTO each month of the watch window: the test that
-- separates a non-payment bar from a credit-ceiling bar
overdue_by_month AS (
    SELECT  sbrp_id,
            m.month_key,
            MAX(d.debit_amt) AS overdue_amt
    FROM    dwbi_fact_db.v_fact_cust_bil_daily d
    CROSS JOIN (SELECT * FROM UNNEST(ARRAY[140405,140406,140407,140408,
                                           140409,140410,140411]) AS t(month_key)) m
    WHERE   d.bilcycl < m.month_key              -- an EARLIER cycle, i.e. past due
      AND   d.day_key BETWEEN m.month_key * 100 + 1 AND m.month_key * 100 + 31
      AND   d.debit_amt > 200000
      AND   d.cust_bil_typ_id = '983116577831777608312765670515538102764700000000'
      AND   d.sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY d.sbrp_id, m.month_key
),
outcome_bar AS (
    SELECT  b.sbrp_id,
            -- ONE-WAY BAR WITH PAST-DUE DEBT = the credit event
            MAX(CASE WHEN b.tot_one_way_cl_barr_curr_mth > 0
                      AND o.overdue_amt IS NOT NULL
                     THEN 1 ELSE 0 END)                               AS had_nonpay_oneway,
            COUNT(*) FILTER (WHERE b.tot_one_way_cl_barr_curr_mth > 0
                               AND o.overdue_amt IS NOT NULL)         AS n_nonpay_oneway_months,
            -- one-way bar with no past-due debt = hit the ceiling, NOT a credit event
            MAX(CASE WHEN b.tot_one_way_cl_barr_curr_mth > 0
                      AND o.overdue_amt IS NULL
                     THEN 1 ELSE 0 END)                               AS had_ceiling_oneway,
            -- escalation: severity, not the trigger
            MAX(CASE WHEN b.tot_two_way_cl_barr_curr_mth > 0
                     THEN 1 ELSE 0 END)                               AS escalated_twoway,
            MAX(CASE WHEN b.tot_mdtrm_two_way_cl_barr_curr_mth > 0
                     THEN 1 ELSE 0 END)                               AS had_midcycle
    FROM        dwbi_fact_db.v_fact_sbrp_mthly b
    LEFT JOIN   overdue_by_month o ON o.sbrp_id = b.sbrp_id
                                  AND o.month_key = b.month_key
    WHERE   b.month_key BETWEEN 140405 AND 140411
      AND   b.sbrp_typ_id = 1 AND b.cust_typ_id = 1
      AND   b.sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY b.sbrp_id
),
-- how long the subscriber stayed barred: the severity ladder
barred_span AS (
    SELECT  sbrp_id,
            COUNT(*) FILTER (WHERE sbrp_stat_id = 3) AS barred_days_out
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE   day_key BETWEEN 14040501 AND 14041130
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY sbrp_id
),
outcome_pay AS (
    SELECT  sbrp_id,
            SUM(COALESCE(invoice_amt,0)) AS invoice_out,
            SUM(COALESCE(pmnt_amt,0))    AS paid_out
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140405 AND 140408
      AND   sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_c1_base)
    GROUP BY sbrp_id
),
-- rows to drop entirely: the outcome is unobservable, not good and not bad
churned AS (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  sbrp_stat_id IN (4, 8, 9)
      AND  day_key BETWEEN 14040501 AND 14041130
),
agg AS (
    SELECT  b.sbrp_id,
            COUNT(o.bilcycl)                                  AS n_bills_seen,
            COALESCE(MAX(o.dpd_days), 0)                      AS max_dpd_out,
            COUNT(o.bilcycl) FILTER (WHERE o.dpd_days > 15)   AS n_late_out,
            COALESCE(MAX(ob.had_nonpay_oneway), 0)            AS had_nonpay_oneway,
            COALESCE(MAX(ob.n_nonpay_oneway_months), 0)       AS n_nonpay_oneway_months,
            COALESCE(MAX(ob.had_ceiling_oneway), 0)           AS had_ceiling_oneway,
            COALESCE(MAX(ob.escalated_twoway), 0)             AS escalated_twoway,
            COALESCE(MAX(ob.had_midcycle), 0)                 AS had_midcycle,
            COALESCE(MAX(bs.barred_days_out), 0)              AS barred_days_out,
            MAX(op.paid_out) / NULLIF(MAX(op.invoice_out), 0) AS pay_ratio_out,
            MAX(CASE WHEN ch.sbrp_id IS NOT NULL THEN 1 ELSE 0 END) AS churned_flag
    FROM        dwbi_temp40_db.dcb_c1_base b
    LEFT JOIN   outcome_dpd  o  ON o.sbrp_id  = b.sbrp_id
    LEFT JOIN   outcome_bar  ob ON ob.sbrp_id = b.sbrp_id
    LEFT JOIN   barred_span  bs ON bs.sbrp_id = b.sbrp_id
    LEFT JOIN   outcome_pay  op ON op.sbrp_id = b.sbrp_id
    LEFT JOIN   churned      ch ON ch.sbrp_id = b.sbrp_id
    GROUP BY b.sbrp_id
)
SELECT  sbrp_id,
        n_bills_seen, max_dpd_out, n_late_out, pay_ratio_out, barred_days_out,
        had_nonpay_oneway, n_nonpay_oneway_months, escalated_twoway,
        had_ceiling_oneway, had_midcycle,          -- ceiling events: features, never label
        -- rule components, stored so the variant can be re-chosen without re-querying
        CASE WHEN max_dpd_out >= 60 THEN 1 ELSE 0 END AS rule1_dpd60,
        CASE WHEN n_late_out  >= 2  THEN 1 ELSE 0 END AS rule2_late,
        had_nonpay_oneway                             AS rule3_nonpay_bar,
        escalated_twoway                              AS rule4_escalated,
        -- ---- the candidates, from most to least conservative ----
        -- severe: the escalation completed
        CASE WHEN escalated_twoway = 1 THEN 1 ELSE 0 END          AS y_severe,
        -- strict: deep delinquency or a non-payment bar
        CASE WHEN max_dpd_out >= 60 OR had_nonpay_oneway = 1
             THEN 1 ELSE 0 END                                    AS y_strict,
        -- v1 (recommended starting point): + repeated lateness
        CASE WHEN max_dpd_out >= 60 OR n_late_out >= 2
                  OR had_nonpay_oneway = 1
             THEN 1 ELSE 0 END                                    AS y_v1,
        -- v2: same, but lateness must be chronic
        CASE WHEN max_dpd_out >= 60 OR n_late_out >= 3
                  OR had_nonpay_oneway = 1
             THEN 1 ELSE 0 END                                    AS y_v2,
        -- loose: lateness alone
        CASE WHEN n_late_out >= 2 THEN 1 ELSE 0 END               AS y_loose,
        -- one mild slip and no bar: neither good nor bad
        CASE WHEN max_dpd_out < 60 AND had_nonpay_oneway = 0
                  AND n_late_out = 1 THEN 1 ELSE 0 END            AS indeterminate
FROM    agg
WHERE   churned_flag = 0          -- censored outcome
  AND   n_bills_seen = 4          -- incomplete outcome window
;

-- ============================================================================
--  STEP 10  FINAL ASSEMBLY
-- ============================================================================
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_dataset_c1;
CREATE TABLE dwbi_temp40_db.dcb_dataset_c1 WITH (format='PARQUET') AS
SELECT  '140405'                   AS obs_cohort,
        b.sbrp_id,
        p.*,
        d.*,
        br.*,
        r.*,
        pit.*,
        a.*,
        l.y_severe, l.y_strict, l.y_v1, l.y_v2, l.y_loose, l.indeterminate,
        l.max_dpd_out, l.n_late_out, l.pay_ratio_out, l.barred_days_out,
        l.had_nonpay_oneway, l.n_nonpay_oneway_months, l.escalated_twoway,
        l.had_ceiling_oneway, l.had_midcycle,
        l.rule1_dpd60, l.rule2_late, l.rule3_nonpay_bar, l.rule4_escalated
FROM        dwbi_temp40_db.dcb_c1_base     b
INNER JOIN  dwbi_temp40_db.dcb_c1_label    l   ON l.sbrp_id   = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_panel    p   ON p.sbrp_id   = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_dpd      d   ON d.sbrp_id   = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_barr     br  ON br.sbrp_id  = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_restore  r   ON r.sbrp_id   = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_pit      pit ON pit.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb_c1_active   a   ON a.sbrp_id   = b.sbrp_id
;
--  Drop the duplicate sbrp_id columns the p.* / d.* style joins create before
--  exporting, or name the columns explicitly if your client objects.

-- ---------------------------------------------------------------------------
--  SANITY CHECKS - run these before exporting
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS n_rows, COUNT(DISTINCT sbrp_id) AS n_subs
FROM   dwbi_temp40_db.dcb_dataset_c1;

SELECT AVG(y_severe) AS bad_severe, AVG(y_strict) AS bad_strict,
       AVG(y_v1)     AS bad_v1,     AVG(y_v2)     AS bad_v2,
       AVG(y_loose)  AS bad_loose,  AVG(indeterminate) AS indet
FROM   dwbi_temp40_db.dcb_dataset_c1;      -- target band: 5% - 15%

SELECT rule1_dpd60, rule2_late, rule3_nonpay_bar, rule4_escalated, COUNT(*) AS n
FROM   dwbi_temp40_db.dcb_dataset_c1
GROUP BY 1,2,3,4 ORDER BY n DESC;          -- if rule2 dominates, 15 days is too loose

-- Does the one-way / two-way split behave as expected? Of the subscribers who
-- took a non-payment one-way bar, what share escalated inside the window?
-- Anything near 100% means the two columns are the same event recorded twice;
-- a share around a third to a half is the normal dunning funnel.
SELECT had_nonpay_oneway,
       COUNT(*)              AS n,
       AVG(escalated_twoway) AS escalation_rate,
       AVG(barred_days_out)  AS avg_barred_days
FROM   dwbi_temp40_db.dcb_dataset_c1
GROUP BY 1;

-- Sanity on the separation itself: ceiling bars should sit with LOW debt,
-- non-payment bars with HIGH debt. If both groups look alike, the debt test is
-- not separating them and the mapping needs checking.
SELECT had_nonpay_oneway, had_ceiling_oneway,
       COUNT(*) AS n, AVG(max_dpd_out) AS avg_dpd, AVG(y_v1) AS bad_rate
FROM   dwbi_temp40_db.dcb_dataset_c1
GROUP BY 1,2 ORDER BY n DESC;

SELECT * FROM dwbi_temp40_db.dcb_network_index ORDER BY month_key;
--  the shock should be visible at 140412, 140501, 140502

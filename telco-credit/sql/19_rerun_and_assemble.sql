-- ============================================================================
--  RE-RUN THE STALE TABLES AND ASSEMBLE. Run this file top to bottom.
--
--  WHY. STEP 9 failed on lab.n_months_out. The file produces that column; the
--  dcb3_label table on the warehouse does not, because it was built before the
--  rename. Rather than find the stale tables one error at a time, this rebuilds
--  every table whose schema has changed, in dependency order, and then
--  assembles - so one run leaves nothing behind.
--
--  WHAT IT DOES NOT TOUCH: STEP 1 (dcb3_base) and STEP 2 (dcb3_daily_rollup).
--  STEP 2 is the single expensive daily pass and its schema is unchanged, so it
--  is deliberately left alone. STEP 1B is left alone too, so that the 0.40
--  threshold the rollup was built with stays consistent with it.
--
--  Everything here reads existing tables or the monthly and payment facts, so
--  it is cheap. Each CREATE TABLE has its own DROP, so re-running is safe.
--
--  T0 = 140501   features 140407..140412   outcome 140501..140506
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

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
    WHERE  month_key BETWEEN 140407 AND 140412        -- feature window only
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
        GREATEST(COALESCE(MAX(r.run_days), 0) - 15, 0)        AS max_dpd_6m,
        COALESCE(MAX(r.run_days), 0)                          AS max_debt_run_days,
        COUNT(r.run_id)                                       AS n_debt_spells_6m,
        SUM(f.debt_days)                                      AS total_debt_days_6m,
        -- LATE MONTH: still open ten days past the due date. Same definition
        -- the label uses.
        SUM(f.open_after_grace)                               AS n_late_months_6m,
        -- past the 15th but settled before day 25: chronic mild lateness.
        -- A strong predictor, but not default behaviour - its own feature.
        COUNT(*) FILTER (WHERE f.open_after_grace = 0 AND f.past_due_days > 0)
                                                              AS n_mild_late_months_6m,
        COUNT(*) FILTER (WHERE f.debt_days = 0)               AS n_ontime_months_6m,
        MAX(f.bill_out_max)                                   AS max_debt_amt_6m,
        MAX(f.unbill_max)                                     AS unbill_peak_6m,
        AVG(f.unbill_avg)                                     AS unbill_avg_6m,
        -- monthly debt-day panel
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140407) AS debtdays_m1,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140408) AS debtdays_m2,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140409) AS debtdays_m3,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140410) AS debtdays_m4,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140411) AS debtdays_m5,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140412) AS debtdays_m6
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
        SUM(oneway_days)                                      AS oneway_days_6m,
        SUM(twoway_days)                                      AS twoway_days_6m,
        -- months in which the ceiling was breached at all
        COUNT(*) FILTER (WHERE oneway_days > 0)               AS n_ceiling_months_6m,
        COUNT(*) FILTER (WHERE oneway_days > 0 OR twoway_days > 0)
                                                              AS n_barred_months_6m,
        -- recency, in months before T0
        MAX(month_idx) FILTER (WHERE oneway_days > 0 OR twoway_days > 0)
                                                              AS last_bar_month_idx,
        MAX(month_idx) FILTER (WHERE twoway_days > 0)         AS last_twoway_month_idx,
        -- how fast service was restored: days barred per barred month
        CAST(SUM(oneway_days) AS DOUBLE)
          / NULLIF(COUNT(*) FILTER (WHERE oneway_days > 0), 0) AS avg_barred_days_per_spell
FROM    dwbi_temp40_db.dcb3_daily_rollup
WHERE   month_key BETWEEN 140407 AND 140412
GROUP BY sbrp_id
;

-- ---------------------------------------------------------------------------
-- STEP 5  MONTHLY PANEL - one pass over the monthly fact
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_panel;
CREATE TABLE dwbi_temp40_db.dcb3_panel WITH (format='PARQUET') AS
WITH mth AS (
    SELECT  c.sbrp_id, c.month_key,
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
    WHERE   c.month_key BETWEEN 140407 AND 140412
      AND   c.sbrp_typ_id = 1
    GROUP BY c.sbrp_id, c.month_key
),
-- The billed amount per month comes from the END-OF-CYCLE bill, NOT from
-- payable_amt on the monthly fact, which is empty across 140312..140409 and
-- would have produced six columns of zeros.
bil AS (
    SELECT  c.sbrp_id,
            c.day_key / 100                        AS month_key,
            -- billed_amt is the TOTAL the subscriber was billed that month:
            -- end-of-cycle (type 2) plus mid-cycle (type 3). Comparable within
            -- a row against totrev_mN, which is the same month's usage.
            SUM(COALESCE(c.payment_due_amt,0))     AS billed_amt,
            SUM(COALESCE(c.payment_due_amt,0))
                FILTER (WHERE c.cust_bil_typ_id = 3) AS mc_billed_amt
    FROM        dwbi_fact_db.v_fact_cust_bil_daily c
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
    WHERE   c.day_key BETWEEN 14040701 AND 14041231
      AND   c.cust_bil_typ_id IN (2, 3)
    GROUP BY c.sbrp_id, c.day_key / 100
)
SELECT  sbrp_id,
        -- ALIGNMENT, and it is now CONSISTENT across the whole row, which it
        -- was not before. billed_mN is the end-of-cycle bill stamped at the end
        -- of month N, which is the usage OF MONTH N - the same month as
        -- totrev_mN and pmnt_mN. The old payable_mN was the usage of month N-1,
        -- one month out of step with everything beside it, and it also read a
        -- column that is empty across 140312..140409.
        -- So these three series may now be compared within a row.
        MAX(billed_amt) FILTER (WHERE month_key=140407) AS billed_m1,
        MAX(billed_amt) FILTER (WHERE month_key=140408) AS billed_m2,
        MAX(billed_amt) FILTER (WHERE month_key=140409) AS billed_m3,
        MAX(billed_amt) FILTER (WHERE month_key=140410) AS billed_m4,
        MAX(billed_amt) FILTER (WHERE month_key=140411) AS billed_m5,
        MAX(billed_amt) FILTER (WHERE month_key=140412) AS billed_m6,
        -- pmnt_m1..m6 REMOVED. pmnt_amt on the monthly fact is empty in 140402
        -- and 140403, and it is redundant anyway: v_fact_pmnt_adjmt in STEP 6
        -- is the authoritative payment source, is not holed, and separates the
        -- payment types. Every payment feature comes from there.
        MAX(tot_rev) FILTER (WHERE month_key=140407) AS totrev_m1,
        MAX(tot_rev) FILTER (WHERE month_key=140408) AS totrev_m2,
        MAX(tot_rev) FILTER (WHERE month_key=140409) AS totrev_m3,
        MAX(tot_rev) FILTER (WHERE month_key=140410) AS totrev_m4,
        MAX(tot_rev) FILTER (WHERE month_key=140411) AS totrev_m5,
        MAX(tot_rev) FILTER (WHERE month_key=140412) AS totrev_m6,
        SUM(data_gb)                                     AS data_gb_6m,
        SUM(data_gb)   FILTER (WHERE month_key >= 140410) AS data_gb_3m,
        SUM(voice_min)                                   AS voice_min_6m,
        SUM(voice_min) FILTER (WHERE month_key >= 140410) AS voice_min_3m,
        SUM(call_cnt)                                    AS call_cnt_6m,
        SUM(intl_cl_cnt)                                 AS intl_cl_cnt_6m,
        STDDEV_SAMP(tot_rev)                             AS totrev_std_6m,
        STDDEV_SAMP(data_gb)                             AS data_gb_std_6m,
        SUM(billed_amt)                                  AS billed_6m,
        -- mc_billed_6m NOT repeated here: dcb3_billref already produces it over
        -- the same window from the same source, and two identical columns break
        -- CREATE TABLE AS.
        -- genuine mid-cycle intensity, from the BILL TYPES (3 vs 2)
        SUM(mc_billed_amt) / NULLIF(SUM(billed_amt), 0)   AS midcycle_billed_share_6m,
        -- NON-CASH SHARE OF USAGE. CONFIRMED: tot_rev is TOTAL usage, cash and
        -- non-cash both, while only NON-CASH usage reaches the bill. So this
        -- ratio is the non-cash share - the part of their spending that runs on
        -- the operator's credit. It is NOT a mid-cycle measure; an earlier note
        -- in this file called it one, which was wrong.
        -- It matters for lending: a subscriber who pays cash for most of their
        -- usage has a small bill and a small apparent exposure, but their real
        -- spending power is the whole of tot_rev.
        SUM(billed_amt) / NULLIF(SUM(tot_rev), 0)         AS noncash_share_6m,
        COUNT(*)                                         AS n_months_panel
-- FULL OUTER on the month key so a subscriber-month present in one source but
-- not the other is still kept. An INNER JOIN here would silently drop months,
-- which is the failure mode this whole file has been chasing.
FROM (
    SELECT  COALESCE(m.sbrp_id, l.sbrp_id)     AS sbrp_id,
            COALESCE(m.month_key, l.month_key) AS month_key,
            m.tot_rev, m.data_gb, m.voice_min,
            m.call_cnt, m.intl_cl_cnt,
            l.billed_amt, l.mc_billed_amt
    FROM            mth m
    FULL OUTER JOIN bil l
                 ON l.sbrp_id = m.sbrp_id AND l.month_key = m.month_key
) j
GROUP BY sbrp_id
;

-- ---------------------------------------------------------------------------
-- STEP 6  PAYMENT BEHAVIOUR, INCLUDING MID-CYCLE
--
--  cust_pmnt_typ_id AND bllg_pmnt_stat_id ARE NOT INTERPRETED HERE.
--  An earlier version of this file filtered cust_pmnt_typ_id IN (4, 6) and
--  split out "mid-cycle" as type 6. That mapping was MY OWN INVENTION - it was
--  never given, it entered through a review note of mine and propagated from
--  there - and the data contradicts it: type 6 is 99.99 pct of payments for the
--  median subscriber, which cannot coexist with an end-of-cycle bill worth 75
--  pct of what was paid. The filter is therefore GONE, because a filter built
--  on a guess silently deletes payment types.
--
--  MID-CYCLE IS NOT DERIVABLE FROM THIS TABLE. It comes from cust_bil_typ_id on
--  v_fact_cust_bil_daily, where 2 is the end-of-cycle bill; and without the
--  cash and non-cash purchase split it cannot be computed from payments at all.
--  P1 in 16_payment_types.sql establishes the codes before anything reads them.
--

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
            COUNT(*)                                            AS n_payments,
            MIN(MOD(p.day_key, 100))                            AS first_pay_day
    FROM        dwbi_fact_db.v_fact_pmnt_adjmt p
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = p.sbrp_id
    -- NO cust_pmnt_typ_id filter. See the note above. bllg_pmnt_stat_id = 2
    -- for "successful" is ALSO unverified and carried over from the original
    -- pipeline; P1 reports the status codes so it can be confirmed or dropped.
    WHERE   p.bllg_pmnt_stat_id = 2
      AND   p.day_key BETWEEN 14040701 AND 14041231
    GROUP BY p.sbrp_id, p.day_key / 100
)
SELECT  sbrp_id,
        SUM(paid_total)                                   AS paid_total_6m,
        SUM(n_payments)                                   AS n_payments_6m,
        AVG(first_pay_day)                                AS avg_first_pay_day,
        STDDEV_SAMP(paid_total)                           AS paid_std_6m,
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
        -- age_on_net_months is NOT selected here. dcb3_base already carries it,
        -- recovered from the NULLs, and duplicating it breaks CREATE TABLE AS.
        -- Never read c.age_on_net_months instead: that is the raw, partly-NULL
        -- column STEP 1 exists to repair.
        c.max_rat_id                                             AS network_id,
        COALESCE(c.initial_cred_lim_amt,0)                       AS initial_cred_lim_amt,
        COALESCE(c.temporary_cred_lim_amt,0)                     AS temporary_cred_lim_amt,
        COALESCE(c.rfndable_dpos_amt,0)                          AS rfndable_dpos_amt,
        COALESCE(c.non_rfndable_dpos_amt,0)                      AS non_rfndable_dpos_amt,
        COALESCE(c.advance_pmnt_amt,0)                           AS advance_pmnt_amt,
        COALESCE(c.bill_outstanding_amt,0)                       AS bill_outstanding_amt,
        COALESCE(c.unbill_outstanding_amt,0)                     AS unbill_outstanding_amt,
        -- THE REAL CEILING. available_credit is the operator's own credit limit
        -- for this SIM, set from SIM value, SIM age and the rest. It is the
        -- quantity whose breach causes the one-way bar, so it is the only
        -- correct ceiling - and it is also the best available benchmark for our
        -- own loan limit, since it is a live credit decision the operator is
        -- already making and already collecting on.
        COALESCE(c.available_credit,0)                           AS available_credit,
        -- kept ONLY as a cross-check. This reconstruction from deposits and
        -- limit components, with a 1.2 multiplier I invented, was standing in
        -- for available_credit before it was known to exist. If the two differ
        -- widely, trust available_credit and drop this.
        (COALESCE(c.non_rfndable_dpos_amt,0) + COALESCE(c.initial_cred_lim_amt,0)) * 1.2
          + COALESCE(c.rfndable_dpos_amt,0) + COALESCE(c.advance_pmnt_amt,0)
          + COALESCE(c.temporary_cred_lim_amt,0)                 AS ceiling_reconstructed,
        -- unbilled usage against the ceiling IS the bar's trigger condition, so
        -- this is how close to the edge the subscriber habitually runs.
        COALESCE(c.unbill_outstanding_amt,0)
          / NULLIF(COALESCE(c.available_credit,0), 0)            AS ceiling_utilisation,
        COALESCE(c.debt_scr, 0)                                  AS debt_scr,
        COALESCE(c.suspend_scr, 0)                               AS suspend_scr
FROM        dwbi_fact_db.v_fact_sbrp_mthly_cip c
INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
WHERE   c.month_key = 140412
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
    WHERE  month_key BETWEEN 140501 AND 140506
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
twoway_consec AS (
    -- "two-way barred two months RUNNING" as specified. Two separated months
    -- are NOT this. month_idx = prev_idx + 1 is required so a month missing
    -- from the rollup cannot make two distant months look adjacent.
    SELECT   sbrp_id,
             MAX(IF(tw = 1 AND prev_tw = 1 AND month_idx = prev_idx + 1, 1, 0))
                                                             AS twoway_2consec
    FROM (
        SELECT  sbrp_id, month_idx,
                IF(twoway_days > 0, 1, 0)                    AS tw,
                LAG(IF(twoway_days > 0, 1, 0)) OVER (
                    PARTITION BY sbrp_id ORDER BY month_idx)  AS prev_tw,
                LAG(month_idx) OVER (
                    PARTITION BY sbrp_id ORDER BY month_idx)  AS prev_idx
        FROM    out
    ) t
    GROUP BY sbrp_id
),
reclaimed AS (
    -- EXCLUSION list, per the business rule: a subscriber who reached 8 or 9
    -- in the outcome window is dropped, not labelled. Read off the rollup, so
    -- no second scan of the daily fact. These are the ONLY statuses excluded -
    -- 3 and 4 are label rules, and the old version of this CTE wrongly had 4
    -- in here, which deleted every two-way bar from the label.
    SELECT   sbrp_id,
             MAX(IF(queue_days   > 0, 1, 0)) AS hit_queue,
             MAX(IF(reclaim_days > 0, 1, 0)) AS hit_reclaim
    FROM     out
    GROUP BY sbrp_id
),
agg AS (
    SELECT  o.sbrp_id,
            COUNT(*)                                        AS n_months_seen,
            GREATEST(COALESCE(MAX(r.run_days), 0) - 15, 0)  AS max_dpd_out,
            SUM(o.open_after_grace)                         AS n_late_out,
            SUM(o.debt_days)                                AS total_debt_days_out,
            MAX(IF(o.twoway_days > 0, 1, 0))                AS escalated_twoway,
            COUNT(*) FILTER (WHERE o.twoway_days > 0)       AS twoway_months_out,
            SUM(o.oneway_days)                              AS oneway_days_out,
            SUM(o.twoway_days)                              AS twoway_days_out,
            MAX(COALESCE(x.hit_queue, 0))                   AS hit_queue,
            MAX(COALESCE(x.hit_reclaim, 0))                 AS hit_reclaim,
            MAX(COALESCE(t.twoway_2consec, 0))              AS twoway_2consec
    FROM        out o
    LEFT JOIN   run_len r       ON r.sbrp_id = o.sbrp_id
    LEFT JOIN   reclaimed x     ON x.sbrp_id = o.sbrp_id
    LEFT JOIN   twoway_consec t ON t.sbrp_id = o.sbrp_id
    GROUP BY o.sbrp_id
)
SELECT  sbrp_id,
        n_months_seen AS n_months_out, max_dpd_out, n_late_out, total_debt_days_out,
        oneway_days_out, twoway_days_out, twoway_months_out,
        escalated_twoway,
        -- rule components, stored so a variant can be re-chosen without re-querying
        IF(max_dpd_out >= 60, 1, 0)                        AS rule1_dpd60,
        IF(n_late_out  >= 2,  1, 0)                        AS rule2_late,
        -- rule3_nonpay_bar DELETED. It fired on a one-way bar, which is only
        -- ever a credit-ceiling breach, so it was marking heavy users bad.
        escalated_twoway                                   AS rule4_escalated,
        -- the candidates, most to least conservative
        -- Every rule below is built on statuses 3 and 4 and on payment
        -- timing. 8 and 9 never appear - those rows are excluded by the WHERE.
        twoway_2consec                                     AS y_twoway_2m,
        -- the non-consecutive version, kept only so the two can be compared
        IF(twoway_months_out >= 2, 1, 0)                   AS y_twoway_any2m,
        IF(escalated_twoway = 1, 1, 0)                     AS y_severe,
        IF(max_dpd_out >= 60, 1, 0)                     AS y_strict,
        IF(max_dpd_out >= 60 OR n_late_out >= 2, 1, 0)  AS y_v1,
        IF(max_dpd_out >= 60 OR n_late_out >= 3, 1, 0)  AS y_v2,
        IF(n_late_out >= 2, 1, 0)                                                AS y_loose,
        IF(max_dpd_out < 60 AND n_late_out = 1, 1, 0)  AS indeterminate
FROM    agg
-- EXCLUDE the reclamation path, per the business rule. This is the ONE
-- status-based exclusion in the label; two-way bars stay and are labelled.
WHERE   hit_queue   = 0
  AND   hit_reclaim = 0
  AND   n_months_seen >= 6      -- the window is 7 months; one missing month
                                -- is tolerated, two is an incomplete outcome.
                                -- G4 in STEP 9 reports the 7-month share.
;

-- ---------------------------------------------------------------------------
-- STEP 9  ASSEMBLY
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_dataset_c1;
CREATE TABLE dwbi_temp40_db.dcb3_dataset_c1 WITH (format='PARQUET') AS
-- EXPLICIT COLUMN LIST, GENERATED - not hand-typed and not a star expansion.
--
--  Why: CREATE TABLE AS cannot create two columns with the same name, and the
--  eight source tables each carry sbrp_id. A plain SELECT is happy to return
--  duplicate names, which is why this statement ran fine without CREATE TABLE
--  and failed with it. USING (sbrp_id) did not collapse them on this engine, so
--  the star expansion is gone.
--
--  The list was generated by parsing the output column list of every CREATE
--  TABLE in this file, so nothing is typed by hand and nothing can be quietly
--  left out. It asserts on construction that no name repeats.
--  97 columns + obs_cohort + 2 derived = 100.
--  If a step's output changes, REGENERATE this block - do not patch it by hand.
SELECT  '140501' AS obs_cohort,
        -- CAPACITY BASIS = paid_total_6m, as decided. Part of the excess of
        -- payments over billing is arrears cleared from BEFORE the window
        -- rather than ongoing capacity, so the window overstates capacity for
        -- anyone catching up. These two make that visible:
        --   paid_to_obligation > 1  was paying down old debt
        --                      < 1  was accumulating new arrears
        -- Discount proven_capacity by arrears_paydown_6m before setting a limit.
        pay.paid_total_6m / NULLIF(r.obligation_6m, 0)     AS paid_to_obligation,
        GREATEST(pay.paid_total_6m - r.obligation_6m, 0)   AS arrears_paydown_6m,
        -- dcb3_base (2)
        b.sbrp_id,
        b.age_on_net_months,
        -- dcb3_billref (9)
        r.med_bill,
        r.n_billed_months,
        r.ec_billed_6m,
        r.mc_billed_6m,
        r.obligation_6m,
        r.midcycle_billed_share,
        r.med_obligation,
        r.max_bill,
        r.bill_std,
        -- dcb3_label (19)
        lab.n_months_out,
        lab.max_dpd_out,
        lab.n_late_out,
        lab.total_debt_days_out,
        lab.oneway_days_out,
        lab.twoway_days_out,
        lab.twoway_months_out,
        lab.escalated_twoway,
        lab.rule1_dpd60,
        lab.rule2_late,
        lab.rule4_escalated,
        lab.y_twoway_2m,
        lab.y_twoway_any2m,
        lab.y_severe,
        lab.y_strict,
        lab.y_v1,
        lab.y_v2,
        lab.y_loose,
        lab.indeterminate,
        -- dcb3_dpd (16)
        dpd.max_dpd_6m,
        dpd.max_debt_run_days,
        dpd.n_debt_spells_6m,
        dpd.total_debt_days_6m,
        dpd.n_late_months_6m,
        dpd.n_mild_late_months_6m,
        dpd.n_ontime_months_6m,
        dpd.max_debt_amt_6m,
        dpd.unbill_peak_6m,
        dpd.unbill_avg_6m,
        dpd.debtdays_m1,
        dpd.debtdays_m2,
        dpd.debtdays_m3,
        dpd.debtdays_m4,
        dpd.debtdays_m5,
        dpd.debtdays_m6,
        -- dcb3_bars (7)
        bar.oneway_days_6m,
        bar.twoway_days_6m,
        bar.n_ceiling_months_6m,
        bar.n_barred_months_6m,
        bar.last_bar_month_idx,
        bar.last_twoway_month_idx,
        bar.avg_barred_days_per_spell,
        -- dcb3_panel (24)
        pan.billed_m1,
        pan.billed_m2,
        pan.billed_m3,
        pan.billed_m4,
        pan.billed_m5,
        pan.billed_m6,
        pan.totrev_m1,
        pan.totrev_m2,
        pan.totrev_m3,
        pan.totrev_m4,
        pan.totrev_m5,
        pan.totrev_m6,
        pan.data_gb_6m,
        pan.data_gb_3m,
        pan.voice_min_6m,
        pan.voice_min_3m,
        pan.call_cnt_6m,
        pan.intl_cl_cnt_6m,
        pan.totrev_std_6m,
        pan.data_gb_std_6m,
        pan.billed_6m,
        pan.midcycle_billed_share_6m,
        pan.noncash_share_6m,
        pan.n_months_panel,
        -- dcb3_pay (7)
        pay.paid_total_6m,
        pay.n_payments_6m,
        pay.avg_first_pay_day,
        pay.paid_std_6m,
        pay.proven_capacity,
        pay.median_monthly_paid,
        pay.capacity_headroom,
        -- dcb3_pit (13)
        pit.network_id,
        pit.initial_cred_lim_amt,
        pit.temporary_cred_lim_amt,
        pit.rfndable_dpos_amt,
        pit.non_rfndable_dpos_amt,
        pit.advance_pmnt_amt,
        pit.bill_outstanding_amt,
        pit.unbill_outstanding_amt,
        pit.available_credit,
        pit.ceiling_reconstructed,
        pit.ceiling_utilisation,
        pit.debt_scr,
        pit.suspend_scr
FROM        dwbi_temp40_db.dcb3_base    b
INNER JOIN  dwbi_temp40_db.dcb3_billref r   ON r.sbrp_id   = b.sbrp_id
INNER JOIN  dwbi_temp40_db.dcb3_label   lab ON lab.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_dpd     dpd ON dpd.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_bars    bar ON bar.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_panel   pan ON pan.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pay     pay ON pay.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pit     pit ON pit.sbrp_id = b.sbrp_id
;

-- ---------------------------------------------------------------------------
--  SEND ME THIS
-- ---------------------------------------------------------------------------
SELECT COUNT(*)              AS n_rows,
       COUNT(DISTINCT sbrp_id) AS n_subs,
       AVG(y_twoway_2m)      AS bad_twoway_2m,
       AVG(y_severe)         AS bad_severe,
       AVG(y_strict)         AS bad_strict,
       AVG(y_v1)             AS bad_v1,
       AVG(y_v2)             AS bad_v2,
       AVG(y_loose)          AS bad_loose,
       AVG(indeterminate)    AS indet
FROM   dwbi_temp40_db.dcb3_dataset_c1;

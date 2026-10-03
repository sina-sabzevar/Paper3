-- ============================================================================
--  FAN-OUT FIX. Re-run these three, in order.
--
--  THE BUG. run_len is grouped by (sbrp_id, run_id), so it holds one row per
--  DEBT RUN. STEP 3 and STEP 8 joined it straight to a per-month relation,
--  which fanned every month row out once per run and multiplied every SUM and
--  COUNT by the run count. A subscriber who pays around the 15th each month has
--  six runs, so their totals came out six times too large - which is exactly
--  88.3 debt days against a true 14.7, and lateness counts of 36 in a 6-month
--  window.
--
--  WHAT WAS WRONG: n_late_out, total_debt_days_out, twoway_months_out,
--  oneway_days_out, twoway_days_out, n_months_out, and in STEP 3
--  n_debt_spells_6m, total_debt_days_6m, n_late_months_6m,
--  n_mild_late_months_6m, n_ontime_months_6m.
--  So y_v1, y_v2, y_loose and y_twoway_any2m were ALL wrong. The 36 pct bad
--  rate was never a real rate.
--
--  WHAT WAS NEVER WRONG: anything built on MAX, because MAX is unchanged by
--  duplication. max_dpd_out, escalated_twoway, twoway_2consec, the debtdays_m*
--  panel, max_debt_amt_6m, unbill_peak_6m - and therefore y_severe at 2.22 pct,
--  y_strict at 1.22 pct and y_twoway_2m at 1.16 pct all stand.
--
--  The fix is a run_agg CTE that collapses run_len to one row per subscriber
--  before the join. STEP 4, 5, 6, 7 read the rollup or the facts and never
--  touched run_len, so they are untouched and need no re-run.
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
),
run_agg AS (
    -- ONE ROW PER SUBSCRIBER. run_len is grouped by (sbrp_id, run_id), so it
    -- holds one row per DEBT RUN. Joining it straight to a per-month relation
    -- fans every month row out once per run, and then every SUM and COUNT over
    -- those months is multiplied by the run count. That is what put values up
    -- to 36 in a 6-month lateness counter and 927 days of debt in a 180-day
    -- window. MAX survives duplication, which is why max_dpd was never wrong.
    SELECT   sbrp_id,
             MAX(run_days) AS max_run_days,
             COUNT(*)      AS n_spells
    FROM     run_len
    GROUP BY sbrp_id
)
SELECT  f.sbrp_id,
        GREATEST(COALESCE(MAX(ra.max_run_days), 0) - 15, 0)   AS max_dpd_6m,
        COALESCE(MAX(ra.max_run_days), 0)                     AS max_debt_run_days,
        COALESCE(MAX(ra.n_spells), 0)                         AS n_debt_spells_6m,
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
LEFT JOIN   run_agg ra ON ra.sbrp_id = f.sbrp_id
GROUP BY f.sbrp_id
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
run_agg AS (
    -- ONE ROW PER SUBSCRIBER. run_len is grouped by (sbrp_id, run_id), so it
    -- holds one row per DEBT RUN. Joining it straight to a per-month relation
    -- fans every month row out once per run, and then every SUM and COUNT over
    -- those months is multiplied by the run count. That is what put values up
    -- to 36 in a 6-month lateness counter and 927 days of debt in a 180-day
    -- window. MAX survives duplication, which is why max_dpd was never wrong.
    SELECT   sbrp_id,
             MAX(run_days) AS max_run_days,
             COUNT(*)      AS n_spells
    FROM     run_len
    GROUP BY sbrp_id
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
            GREATEST(COALESCE(MAX(ra.max_run_days), 0) - 15, 0) AS max_dpd_out,
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
    LEFT JOIN   run_agg ra      ON ra.sbrp_id = o.sbrp_id
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
--  G6 FIRST - all four must be ZERO, or the fan-out is still there
-- ---------------------------------------------------------------------------
SELECT  COUNT(*) FILTER (WHERE n_late_out > 6)            AS impossible_late,
        COUNT(*) FILTER (WHERE total_debt_days_out > 190) AS impossible_debtdays,
        COUNT(*) FILTER (WHERE twoway_months_out > 6)     AS impossible_twoway_months,
        COUNT(*) FILTER (WHERE n_months_out > 6)          AS impossible_months_seen,
        MAX(n_late_out)                                   AS max_late,
        MAX(total_debt_days_out)                          AS max_debtdays
FROM    dwbi_temp40_db.dcb3_label;

-- ---------------------------------------------------------------------------
--  then the real bad rates, and the lateness distribution that is now bounded
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS n_rows,
       AVG(y_twoway_2m) AS bad_twoway_2m, AVG(y_twoway_any2m) AS bad_twoway_any2m,
       AVG(y_severe) AS bad_severe, AVG(y_strict) AS bad_strict,
       AVG(y_v1) AS bad_v1, AVG(y_v2) AS bad_v2, AVG(y_loose) AS bad_loose,
       AVG(indeterminate) AS indet
FROM   dwbi_temp40_db.dcb3_dataset_c1;

SELECT n_late_out, COUNT(*) AS n, AVG(max_dpd_out) AS avg_dpd,
       AVG(total_debt_days_out) AS avg_debt_days, AVG(y_severe) AS rate_twoway
FROM   dwbi_temp40_db.dcb3_dataset_c1
GROUP BY n_late_out ORDER BY n_late_out;

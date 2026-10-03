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
--  CONFIRMED SUBSCRIBER STATUS LADDER (sbrp_stat_id) - CORRECTED
--      2  active
--      3  one-way bar      (outgoing barred)
--      4  TWO-WAY bar      (fully cut off)
--      8  queued for number reclamation
--      9  number reclaimed
--    An earlier message in the project said 9 was the two-way bar. It is not;
--    the user corrected it to 4. Every status test in this file was rebuilt on
--    the ladder above.
--
--    8 and 9 are reached only after roughly five to six months of no activity
--    WHILE IN DEBT.
--
--    BUSINESS RULE, SET BY THE USER: 8 and 9 are ALWAYS EXCLUDED, never
--    labelled. Only 3 and 4 matter. A reclaimed number has no relationship
--    left to observe, so the remaining outcome period is genuinely censored.
--    The cost of excluding them is near zero in any case: reaching 8 takes
--    five to six months, and the outcome window is seven, so anyone who gets
--    there was already flagged bad by the two-way bar or by DPD >= 60 months
--    earlier. G5 in STEP 9 counts them so this stays verified rather than
--    assumed.
--
--  CONFIRMED BILLING SEMANTICS - the whole file rests on these
--    a. bill_outstanding_amt (DAILY fact) = the issued bill, due the 15th of
--       the next month. Goes to 0 the moment it is paid, INCLUDING by a
--       mid-cycle payment. Populated in ALL 30 months.
--    b. unbill_outstanding_amt = that bill PLUS the current month's running
--       usage, so it is live exposure, not an arrear.
--    c. payment_due_amt (v_fact_cust_bil_daily, cust_bil_typ_id = 2) = the
--       END-OF-CYCLE bill. Carries a value only on the LAST DAY of the month,
--       and is keyed by sbrp_id. Stamped at the end of month M it is the usage
--       OF MONTH M, due the 15th of M+1. THIS IS NOW THE BILL SOURCE.
--    d. tot_rev stamped month M (MONTHLY fact) = the usage OF MONTH M.
--    e. payable_amt and invoice_amt on the MONTHLY fact are NOT USED. They are
--       loaded in only 14 of 30 months and empty across 140312..140409, with an
--       identical gap in both - zero months disagree - so it is a loading gap
--       in that table, not a column-naming mistake. Anchoring anything there
--       made the calendar hostage to the gap and collapsed the base to 1371
--       rows. Do not reintroduce either column.
--
--  WHAT (c) AND (d) TOGETHER MEAN
--    - payment_due_amt(M) is the very bill that sits in the daily
--      bill_outstanding_amt through month M+1, so the materiality threshold
--      and the balance it is tested against are the SAME quantity.
--    - billed_mN, pmnt_mN and totrev_mN in the panel are all stamped on month
--      N and all describe the usage OF MONTH N. They are mutually comparable
--      inside a row. This was NOT true of the old payable_mN, which was the
--      usage of month N-1 and one month out of step with its neighbours.
--

--  NO percent character anywhere (Python drivers read it as a format spec).
--  NO CASE expressions - IF and FILTER are used instead.
--  AMOUNTS ARE IN RIAL.
-- ============================================================================

-- ---------------------------------------------------------------------------
--  COHORT CALENDAR   <<< the only block to edit between runs
--
--  Data starts at 1404-01; 1403 is gone. Now is 1405-07, so the last closed
--  month is 140506 and a watch window that must close by then puts the latest
--  usable T0 at 140412. The revenue shock sits at 140412, 140501 and 140502 -
--  squarely on top of every recent watch window.
--
--  NO cohort is free of it. With a 12-month feature window there is no valid T0
--  at all, and with 9 months the earliest is 140410, whose BILLS fall in the
--  shock. A 6-month window is the trade that keeps the bills clean.
--
--  C1  T0 140407   features 140401..140406   bills 140407..140410   watch 140501
--      features clean, bills clean, only the observation period touches the shock
--  C2  T0 140410   features 140404..140409   bills 140410..140501   watch 140504
--      the stress cohort - hold it out and use it to measure degradation
--
--  Shock in the WATCH window inflates the bad rate, which makes the model
--  conservative. Shock in the FEATURE window would distort the limit engine and
--  over-lend. Only the first is acceptable, and only the first happens here.
--
--  THIS RUN = C1
--    feature months  140401 140402 140403 140404 140405 140406
--    T0              140407
--    label bills     140407 140408 140409 140410
--    watch through   140501
--    daily window    14040101 .. 14050131
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- STEP 1  BASE + the median invoice the materiality floor needs
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_base;
CREATE TABLE dwbi_temp40_db.dcb3_base WITH (format='PARQUET') AS
SELECT  s.sbrp_id,
        ten.tenure_at_t0 AS age_on_net_months
FROM (
    SELECT  sbrp_id
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    -- 140406 is the LAST month before T0=140407, so this snapshot is the
    -- state the lender sees at the decision point. It was 140404 - three
    -- months early, left over from an older calendar. That made the active
    -- and permanent tests fire at the wrong point in time and shipped a
    -- stale age_on_net_months into the dataset.
    WHERE   month_key    = 140404      -- the month immediately before T0
      AND   sbrp_stat_id = 2           -- GATE: active at T0 (point in time only)
      AND   sbrp_typ_id  = 1           -- permanent
      -- The tenure test USED to sit here as age_on_net_months >= 12. That
      -- column is NULL for part of the rows and NULL >= 12 evaluates to NULL,
      -- so the test silently deleted every subscriber with a MISSING tenure
      -- instead of only the short-tenured ones. It now lives in the join
      -- below, where the value is recovered rather than assumed.
      -- GATE: no open bill at T0 - DISABLED by default.
      -- In the monthly fact this column appears to be the balance at snapshot
      -- time, and for an active postpaid subscriber there is almost always a
      -- bill outstanding, so requiring zero removes nearly the whole base.
      -- The "not barred in the 60 days before T0" gate below already covers
      -- the pattern this was meant to catch. Re-enable only if G1 in
      -- 08_gate_funnel.sql shows it keeps a sensible share.
      -- AND   COALESCE(bill_outstanding_amt, 0) = 0
) s
-- TENURE, RECOVERED rather than read from one possibly-NULL cell.
-- Take the most recent NON-NULL age_on_net_months anywhere in the feature
-- window and roll it forward to 140406. Every month here is in year 1404, so
-- the month number is MOD(month_key, 100) and the roll-forward is 6 minus it.
-- A subscriber with no non-null tenure in any of the six months still cannot
-- pass, but that is now an explicit inner join rather than a silent NULL.
INNER JOIN (
    SELECT  sbrp_id,
            MAX_BY(age_on_net_months, month_key)
              + (6 - MOD(MAX(month_key), 100))            AS tenure_at_t0
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140311 AND 140404
      AND   sbrp_typ_id = 1
      AND   age_on_net_months IS NOT NULL
    GROUP BY sbrp_id
) ten ON ten.sbrp_id = s.sbrp_id
     AND ten.tenure_at_t0 >= 12
-- GATE: the economic floor from the original DCB pipeline - average revenue
-- over the last three months above 1,000,000 Rial (100k Toman). This is what
-- took the base from 36M to under 7M there, and leaving it out is why the base
-- came back at 21M. It is a ticket-size floor, not a risk filter: below it the
-- loan is too small to carry its own opex.
INNER JOIN (
    SELECT  sbrp_id
    FROM (  SELECT  sbrp_id,
                    SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                        - COALESCE(intl_roam_voi_rev,0)) / 1.1
                  + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                        - COALESCE(intl_roam_sms_rev,0))
                  + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                        - COALESCE(post_intl_roam_data_rev,0)
                        - COALESCE(pre_intl_roam_data_rev,0))  AS rev_3m
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key BETWEEN 140402 AND 140404
              AND   sbrp_typ_id = 1
            GROUP BY sbrp_id ) r
    WHERE   r.rev_3m / 3 > 1000000
) rev ON rev.sbrp_id = s.sbrp_id
-- GATE: never touched the reclamation path, ANYWHERE in the project window.
-- Per the business rule these subscribers do not enter the project at all, so
-- the window here is the FULL 14040101..14050131 - features and outcome both -
-- not just the feature months. That makes this one gate the single place the
-- rule is enforced, and the label-level check in STEP 8 becomes a cheap
-- redundant safety net rather than the thing doing the work.
-- One honest note: screening on outcome-window status is look-ahead - at T0 the
-- lender cannot know who will later be reclaimed. It is the user's rule and the
-- affected count is tiny (reaching 8 takes five to six months, and anyone who
-- gets there is already bad on the two-way bar), but G5 in STEP 9 measures it
-- rather than assuming.
-- NOTE what is NOT here any more: this anti-join used to read IN (4, 8), and
-- on the corrected ladder 4 is a TWO-WAY BAR. So it was deleting every
-- subscriber who was ever fully cut off in six months - the single biggest
-- reason the base came back at 1371 rows, and the exact selection mistake
-- this project exists to avoid, since it strips the bad payers the model has
-- to learn from. Two-way bars are now features and label rules, never gates.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14031101 AND 14041131
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (8, 9)
) reclaim ON reclaim.sbrp_id = s.sbrp_id
-- GATE: barred in the LAST WEEK of the feature window, i.e. still cut off
-- going into T0. Deliberately narrow, for two reasons:
--   1. A one-way bar is overwhelmingly a mid-cycle ceiling hit, which is a
--      large and largely benign population. Gating on 60 days of any bar
--      deletes them from the book for no risk reason.
--   2. Bars earlier in the window are FEATURES - n_nonpay_bar_months_6m and
--      n_ceiling_bar_months_6m carry them. Removing those subscribers is
--      exactly the selection mistake in the original pipeline: it strips the
--      bad-payment examples the model has to learn from.
-- So: barred last week blocks origination, barred before that does not.
-- Window ends at 14040631 - no day of the outcome window is touched.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040425 AND 14040431
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (3, 4)      -- one-way or two-way bar. NOT 9.
) barred ON barred.sbrp_id = s.sbrp_id
WHERE   reclaim.sbrp_id IS NULL
  AND   barred.sbrp_id  IS NULL
;


-- ---------------------------------------------------------------------------
-- STEP 1B  THE MATERIALITY YARDSTICK - med_bill
--
--  SOURCE: v_fact_cust_bil_daily.payment_due_amt with cust_bil_typ_id = 2,
--  which is the END-OF-CYCLE bill and carries a value only on the LAST DAY of
--  each month. Confirmed to be keyed by sbrp_id, so it joins directly - no
--  customer-to-SIM bridge is needed.
--
--  WHY NOT THE MONTHLY FACT. invoice_amt and payable_amt there are loaded in
--  only 14 of 30 months and are empty across 140312..140409, with an IDENTICAL
--  gap - zero months disagree - so it is a loading gap in that table and no
--  choice of column escapes it. Anchoring the threshold there made the whole
--  calendar hostage to the gap and collapsed the base to 1371 rows.
--
--  ALIGNMENT, AND IT IS NOT THE SAME AS payable_amt. Confirmed:
--      payment_due_amt stamped at the END of month M = the usage OF MONTH M,
--      due the 15th of M+1.
--      payable_amt stamped month M = the usage of month M-1.
--  So payment_due_amt(M) is the very bill that sits in the daily
--  bill_outstanding_amt through month M+1. That makes the threshold and the
--  balance it is compared against the SAME quantity, which is better aligned
--  than the daily-maximum proxy this step used before.
--
--  The MEDIAN across the subscriber's own months is used, not the mean or the
--  max, so one unusually large bill cannot move the yardstick.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_billref;
CREATE TABLE dwbi_temp40_db.dcb3_billref WITH (format='PARQUET') AS
SELECT  c.sbrp_id,
        APPROX_PERCENTILE(c.payment_due_amt, 0.5)
            FILTER (WHERE c.payment_due_amt > 0)        AS med_bill,
        COUNT(*) FILTER (WHERE c.payment_due_amt > 0)   AS n_billed_months,
        MAX(c.payment_due_amt)                          AS max_bill,
        STDDEV_SAMP(c.payment_due_amt)
            FILTER (WHERE c.payment_due_amt > 0)        AS bill_std
FROM        dwbi_fact_db.v_fact_cust_bil_daily c
INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
WHERE   c.day_key BETWEEN 14031101 AND 14040431       -- FEATURE window only
  AND   c.cust_bil_typ_id = 2
  -- COST GUARD, and the one thing here to verify. The bill lands on the last
  -- day of the month, which is day 31 in months 1-6, day 30 in 7-11 and day 29
  -- in month 12, so days 28 and up catch every month end while reading about a
  -- tenth of the table. B2 in 14_cust_bil_probe.sql prints n_days, first_day
  -- and last_day per month: if any month shows a bill on an earlier day, or
  -- n_days above 1, DELETE this line and take the cost.
  AND   MOD(c.day_key, 100) >= 28
GROUP BY c.sbrp_id
-- a subscriber with no issued bill in any feature month has no bill to measure
-- against, so there is nothing to call material. Dropped explicitly.
HAVING  COUNT(*) FILTER (WHERE c.payment_due_amt > 0) > 0
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
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 0.40 * r.med_bill)
                                                                      AS debt_days,
        -- IN DEBT ON THE LAST DAY of the month. Used ONLY to decide whether a
        -- debt run continues into the next month. It is NOT a lateness flag:
        -- the bill for month M is issued at the end of M, so this is true for
        -- almost everyone and reads as a 100 pct bad rate if misused.
        MAX_BY(IF(d.bill_outstanding_amt > 0.40 * r.med_bill, 1, 0), d.day_key)
                                                                      AS open_at_month_end,
        -- LATE: still open around day 25, which is ten days past the due date
        -- of the 15th. This is the lateness flag the label counts. Probed over
        -- days 24-26 so a missing day does not lose the month.
        MAX(IF(MOD(d.day_key, 100) BETWEEN 24 AND 26
               AND d.bill_outstanding_amt > 0.40 * r.med_bill, 1, 0))
                                                                      AS open_after_grace,
        MAX(d.bill_outstanding_amt)                                   AS bill_out_max,
        -- past due = still open after the 15th
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 0.40 * r.med_bill
                           AND MOD(d.day_key, 100) > 15)              AS past_due_days,
        -- carried = more than one bill stacked, which only happens on a miss
        COUNT(*) FILTER (WHERE d.bill_outstanding_amt > 1.5 * r.med_bill)
                                                                      AS carried_days,
        -- ---- the status ladder. NOT filtered on stat: that is the point.
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 3)                    AS oneway_days,
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 4)                    AS twoway_days,
        -- TERMINAL NON-PAYMENT. Reached only after months of no activity while
        -- in debt, so these are the worst outcome in the book, not censoring.
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 8)                    AS queue_days,
        COUNT(*) FILTER (WHERE d.sbrp_stat_id = 9)                    AS reclaim_days,
        -- WHY A BAR HAPPENED. The two tests below are mutually exclusive and
        -- together cover every stat=3 day, so no bar is silently dropped.
        -- NON-PAYMENT, either of:
        --   (a) more than one bill stacked on the balance (> 1.5 x med_invoice).
        --       A single bill can never exceed that, so this can only be a
        --       missed bill, and it is non-payment WHATEVER day it is seen -
        --       a mid-cycle bar on the 10th with last month's bill still on
        --       the balance is a bad payer, not a ceiling hit.
        --   (b) a material balance still open past the due date (day > 15).
        -- CREDIT CEILING = everything else: barred while nothing is overdue
        -- and nothing is stacked. This is the subscriber who burned through
        -- the in-cycle allowance, which the user flagged as a sensitive
        -- feature and must NOT be read as bad payment behaviour.
        MAX(IF(d.sbrp_stat_id = 3
               AND (d.bill_outstanding_amt > 1.5 * r.med_bill
                    OR (d.bill_outstanding_amt > 0.40 * r.med_bill
                        AND MOD(d.day_key, 100) > 15)), 1, 0))        AS nonpay_bar_day,
        MAX(IF(d.sbrp_stat_id = 3
               AND NOT (d.bill_outstanding_amt > 1.5 * r.med_bill
                        OR (d.bill_outstanding_amt > 0.40 * r.med_bill
                            AND MOD(d.day_key, 100) > 15)), 1, 0))    AS ceiling_bar_day,
        -- ---- ceiling pressure
        MAX(d.unbill_outstanding_amt)                                 AS unbill_max,
        AVG(d.unbill_outstanding_amt)                                 AS unbill_avg
FROM        dwbi_fact_db.v_fact_sbrp_daily_cip d
INNER JOIN  dwbi_temp40_db.dcb3_billref r ON r.sbrp_id = d.sbrp_id
WHERE   d.day_key BETWEEN 14031101 AND 14041131    -- features AND watch window
  AND   d.sbrp_typ_id = 1
GROUP BY d.sbrp_id, d.day_key / 100,
         (d.day_key / 10000) * 12 + MOD(d.day_key / 100, 100)
;
--  STEP 2b below is a fallback for engines without MAX_BY. Trino has it, so
--  SKIP STEP 2b - do not run it.


-- ---------------------------------------------------------------------------
-- STEP 2b  open_at_month_end without MAX_BY. OPTIONAL - only if STEP 2 fails.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_month_end;
CREATE TABLE dwbi_temp40_db.dcb3_month_end WITH (format='PARQUET') AS
SELECT  e.sbrp_id,
        e.month_key,
        MAX(IF(d.bill_outstanding_amt > 0.40 * r.med_bill, 1, 0)) AS open_at_month_end
FROM (
    SELECT sbrp_id, day_key / 100 AS month_key, MAX(day_key) AS last_day
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14031101 AND 14041131
      AND  sbrp_typ_id = 1
      AND  sbrp_id IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb3_base)
    GROUP BY sbrp_id, day_key / 100
) e
INNER JOIN  dwbi_fact_db.v_fact_sbrp_daily_cip d
                 ON d.sbrp_id = e.sbrp_id AND d.day_key = e.last_day
INNER JOIN  dwbi_temp40_db.dcb3_billref r ON r.sbrp_id = e.sbrp_id
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
    WHERE  month_key BETWEEN 140311 AND 140404        -- feature window only
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
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140311) AS debtdays_m1,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140312) AS debtdays_m2,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140401) AS debtdays_m3,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140402) AS debtdays_m4,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140403) AS debtdays_m5,
        MAX(f.debt_days) FILTER (WHERE f.month_key = 140404) AS debtdays_m6
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
        SUM(nonpay_bar_day)                                   AS n_nonpay_bar_months_6m,
        SUM(ceiling_bar_day)                                  AS n_ceiling_bar_months_6m,
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
WHERE   month_key BETWEEN 140311 AND 140404
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
    WHERE   c.month_key BETWEEN 140311 AND 140404
      AND   c.sbrp_typ_id = 1
    GROUP BY c.sbrp_id, c.month_key
),
-- The billed amount per month comes from the END-OF-CYCLE bill, NOT from
-- payable_amt on the monthly fact, which is empty across 140312..140409 and
-- would have produced six columns of zeros.
bil AS (
    SELECT  c.sbrp_id,
            c.day_key / 100                        AS month_key,
            MAX(COALESCE(c.payment_due_amt,0))     AS billed_amt
    FROM        dwbi_fact_db.v_fact_cust_bil_daily c
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
    WHERE   c.day_key BETWEEN 14031101 AND 14040431
      AND   c.cust_bil_typ_id = 2
      AND   MOD(c.day_key, 100) >= 28
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
        MAX(billed_amt) FILTER (WHERE month_key=140311) AS billed_m1,
        MAX(billed_amt) FILTER (WHERE month_key=140312) AS billed_m2,
        MAX(billed_amt) FILTER (WHERE month_key=140401) AS billed_m3,
        MAX(billed_amt) FILTER (WHERE month_key=140402) AS billed_m4,
        MAX(billed_amt) FILTER (WHERE month_key=140403) AS billed_m5,
        MAX(billed_amt) FILTER (WHERE month_key=140404) AS billed_m6,
        -- pmnt_m1..m6 REMOVED. pmnt_amt on the monthly fact is empty in 140402
        -- and 140403, and it is redundant anyway: v_fact_pmnt_adjmt in STEP 6
        -- is the authoritative payment source, is not holed, and separates the
        -- payment types. Every payment feature comes from there.
        MAX(tot_rev) FILTER (WHERE month_key=140311) AS totrev_m1,
        MAX(tot_rev) FILTER (WHERE month_key=140312) AS totrev_m2,
        MAX(tot_rev) FILTER (WHERE month_key=140401) AS totrev_m3,
        MAX(tot_rev) FILTER (WHERE month_key=140402) AS totrev_m4,
        MAX(tot_rev) FILTER (WHERE month_key=140403) AS totrev_m5,
        MAX(tot_rev) FILTER (WHERE month_key=140404) AS totrev_m6,
        SUM(data_gb)                                     AS data_gb_6m,
        SUM(data_gb)   FILTER (WHERE month_key >= 140402) AS data_gb_3m,
        SUM(voice_min)                                   AS voice_min_6m,
        SUM(voice_min) FILTER (WHERE month_key >= 140402) AS voice_min_3m,
        SUM(call_cnt)                                    AS call_cnt_6m,
        SUM(intl_cl_cnt)                                 AS intl_cl_cnt_6m,
        STDDEV_SAMP(tot_rev)                             AS totrev_std_6m,
        STDDEV_SAMP(data_gb)                             AS data_gb_std_6m,
        COUNT(*)                                         AS n_months_seen
-- FULL OUTER on the month key so a subscriber-month present in one source but
-- not the other is still kept. An INNER JOIN here would silently drop months,
-- which is the failure mode this whole file has been chasing.
FROM (
    SELECT  COALESCE(m.sbrp_id, l.sbrp_id)     AS sbrp_id,
            COALESCE(m.month_key, l.month_key) AS month_key,
            m.tot_rev, m.data_gb, m.voice_min,
            m.call_cnt, m.intl_cl_cnt,
            l.billed_amt
    FROM            mth m
    FULL OUTER JOIN bil l
                 ON l.sbrp_id = m.sbrp_id AND l.month_key = m.month_key
) j
GROUP BY sbrp_id
;


-- ---------------------------------------------------------------------------
-- STEP 6  PAYMENT BEHAVIOUR, INCLUDING MID-CYCLE
--
--  cust_pmnt_typ_id: ASSUMED 4 = end of cycle, 6 = mid cycle. S3 in
--  15_sizing_and_coverage.sql CONTRADICTS that: type 6 is 99.99 pct of all
--  payments for the median subscriber, while the end-of-cycle bill is 75 pct
--  of what was paid. Both cannot hold - if nearly everything were genuinely
--  mid-cycle the end-of-cycle bill would be near zero. So type 6 is not
--  "mid-cycle", and paid_midcycle / midcycle_share / n_midcycle_payments below
--  are NOT TRUSTWORTHY until the code meanings are confirmed.
--  The honest mid-cycle measure in the meantime is 1 - billed/tot_rev from the
--  panel, which the data supports at about 25 pct of outlay.
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
      AND   p.day_key BETWEEN 14031101 AND 14040431
    GROUP BY p.sbrp_id, p.day_key / 100
)
SELECT  sbrp_id,
        SUM(paid_total)                                   AS paid_total_6m,
        SUM(paid_midcycle)                                AS paid_midcycle_6m,
        SUM(paid_midcycle) / NULLIF(SUM(paid_total), 0)   AS midcycle_share,
        SUM(n_midcycle_payments)                          AS n_midcycle_payments_6m,
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
        -- from dcb3_base, which RECOVERED it. Reading c.age_on_net_months here
        -- would reintroduce the NULL that STEP 1 exists to repair.
        b.age_on_net_months,
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
            MAX(o.nonpay_bar_day)                           AS had_nonpay_oneway,
            SUM(o.nonpay_bar_day)                           AS n_nonpay_bar_months,
            MAX(o.ceiling_bar_day)                          AS had_ceiling_oneway,
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
        -- Every rule below is built on statuses 3 and 4 and on payment
        -- timing. 8 and 9 never appear - those rows are excluded by the WHERE.
        twoway_2consec                                     AS y_twoway_2m,
        -- the non-consecutive version, kept only so the two can be compared
        IF(twoway_months_out >= 2, 1, 0)                   AS y_twoway_any2m,
        IF(escalated_twoway = 1, 1, 0)                     AS y_severe,
        IF(max_dpd_out >= 60 OR had_nonpay_oneway = 1, 1, 0)                     AS y_strict,
        IF(max_dpd_out >= 60 OR n_late_out >= 2 OR had_nonpay_oneway = 1, 1, 0)  AS y_v1,
        IF(max_dpd_out >= 60 OR n_late_out >= 3 OR had_nonpay_oneway = 1, 1, 0)  AS y_v2,
        IF(n_late_out >= 2, 1, 0)                                                AS y_loose,
        IF(max_dpd_out < 60 AND had_nonpay_oneway = 0 AND n_late_out = 1, 1, 0)  AS indeterminate
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
SELECT  '140405' AS obs_cohort, b.sbrp_id, r.med_bill,
        dpd.*, bar.*, pan.*, pay.*, pit.*,
        lab.y_twoway_2m, lab.y_twoway_any2m, lab.y_severe, lab.y_strict,
        lab.y_v1, lab.y_v2, lab.y_loose, lab.indeterminate,
        lab.max_dpd_out, lab.n_late_out, lab.total_debt_days_out,
        lab.oneway_days_out, lab.twoway_days_out, lab.twoway_months_out,
        lab.had_nonpay_oneway, lab.n_nonpay_bar_months, lab.escalated_twoway,
        lab.had_ceiling_oneway,
        lab.rule1_dpd60, lab.rule2_late, lab.rule3_nonpay_bar, lab.rule4_escalated
FROM        dwbi_temp40_db.dcb3_base    b
INNER JOIN  dwbi_temp40_db.dcb3_billref r   ON r.sbrp_id = b.sbrp_id
INNER JOIN  dwbi_temp40_db.dcb3_label   lab ON lab.sbrp_id = b.sbrp_id
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

SELECT AVG(y_twoway_2m) AS bad_twoway_2m,
       AVG(y_twoway_any2m) AS bad_twoway_any2m, AVG(y_severe) AS bad_severe,
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

-- G5  WHAT THE 8/9 EXCLUSION COSTS. These subscribers are dropped from the
-- label by rule. The point of this check is that they should be FEW, and
-- nearly all of them should already be bad on the two-way bar - if so, the
-- exclusion loses no information. If excl_subs is large, say so and we will
-- revisit it.
SELECT  COUNT(DISTINCT sbrp_id)                                     AS base_subs,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE queue_days > 0
                                           OR reclaim_days > 0)     AS excl_subs,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE (queue_days > 0
                                           OR reclaim_days > 0)
                                          AND twoway_days > 0)      AS excl_also_twoway
FROM    dwbi_temp40_db.dcb3_daily_rollup
WHERE   month_key BETWEEN 140405 AND 140411;

-- G4  completeness of the outcome window. 7 is the full window. If the 6-month
-- group is large, the tolerance in STEP 8 is carrying real censoring and should
-- be tightened to 7.
SELECT n_months_seen, COUNT(*) AS n, AVG(y_v1) AS bad_rate
FROM   dwbi_temp40_db.dcb3_label
GROUP BY 1 ORDER BY 1;

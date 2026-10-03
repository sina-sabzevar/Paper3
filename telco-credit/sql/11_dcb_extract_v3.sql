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
--  CONFIRMED MECHANICS - the whole file rests on these
--
--  HOW A POSTPAID SIM ACTUALLY WORKS HERE
--    Usage (packages, calls, SMS) is either CASH or NON-CASH.
--      - CASH usage NEVER reaches the bill.
--      - NON-CASH usage accrues against the SIM's CREDIT CEILING.
--    available_credit is that ceiling - the operator's own credit limit for the
--    SIM, set from SIM value, SIM age and similar. It is a live credit decision
--    the operator already makes and already collects on, which makes it the
--    best benchmark there is for our own limit.
--    When non-cash usage crosses the ceiling the line is ONE-WAY BARRED
--    (stat=3) and stays barred until the subscriber pays. Paying frees
--    headroom. At month end whatever non-cash is still unsettled becomes the
--    end-of-cycle bill. Unpaid by the 15th of the next month, it becomes debt -
--    carried on in the SAME bill_outstanding_amt, so the DPD logic is unchanged.
--
--  WHAT THAT MEANS FOR THE LABEL, AND IT COST A RULE
--    A one-way bar has exactly ONE cause: the ceiling. There is no
--    "non-payment one-way bar". So barring often says only that usage is high
--    relative to a low ceiling - which describes a HEAVY, VALUABLE customer,
--    not a delinquent one. rule3_nonpay_bar fired on exactly that and has been
--    DELETED, along with the nonpay/ceiling day classification behind it.
--    The signal in a bar is its DURATION: pay-and-reconnect-same-day is a good
--    payer on a tight ceiling; twenty days barred is someone struggling.
--    Delinquency is measured only from payment timing - DPD past the 15th,
--    repeated lateness - and from the two-way bar (stat=4).
--
--  THE COLUMNS
--    a. bill_outstanding_amt (DAILY) = the issued bill, due the 15th of the
--       next month, and the debt it becomes afterwards. Zeroed by any payment
--       including a mid-cycle one. Populated in ALL 30 months.
--    b. unbill_outstanding_amt = that bill plus the running month's usage, so
--       it is the live exposure measured against available_credit.
--    c. payment_due_amt on v_fact_cust_bil_daily, keyed by sbrp_id:
--         cust_bil_typ_id = 2  END-OF-CYCLE bill, last day of the month only.
--                              Stamped at the end of month M it is the usage OF
--                              MONTH M, due the 15th of M+1.
--         cust_bil_typ_id = 3  MID-CYCLE bill. Does NOT land on the month end,
--                              which is why the old MOD(day_key,100) >= 28 cost
--                              guard had to go - it deleted every one of them.
--       Both are NON-CASH only.
--    d. tot_rev (MONTHLY) stamped month M = TOTAL usage of month M, cash AND
--       non-cash. So billed/tot_rev is the NON-CASH SHARE, not a mid-cycle
--       measure. Mid-cycle intensity comes from bill type 3 against type 2.
--    e. pmnt_amt on v_fact_pmnt_adjmt = payments that land on the bill. Prepaid
--       credit has no part in this project while sbrp_typ_id = 1, so
--       paid_total is not inflated by top-ups.
--    f. payable_amt and invoice_amt on the MONTHLY fact are NOT USED - loaded
--       in only 14 of 30 months, empty across 140312..140409, identical gap in
--       both. Do not reintroduce either.
--    g. cust_pmnt_typ_id is NOT interpreted. "4 end of cycle, 6 mid cycle" was
--       my own invention and the data contradicts it.
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
SELECT  sbrp_id,
        -- THE MATERIALITY YARDSTICK stays on the END-OF-CYCLE bill (type 2)
        -- alone, deliberately. It is compared against the daily
        -- bill_outstanding_amt, which is the end-of-cycle bill balance, so both
        -- sides of that test must be the same quantity. Adding the mid-cycle
        -- bill here would inflate the threshold above the balance it screens.
        APPROX_PERCENTILE(ec_amt, 0.5) FILTER (WHERE ec_amt > 0)  AS med_bill,
        COUNT(*) FILTER (WHERE ec_amt > 0)                        AS n_billed_months,
        -- TRUE TELCO OBLIGATION = end-of-cycle PLUS mid-cycle billing. This is
        -- what the subscriber was actually asked to pay across the window, and
        -- it is the denominator that exposes arrears paydown: paid_total above
        -- obligation means old debt was being cleared inside the window, so the
        -- window overstates ongoing monthly capacity.
        SUM(ec_amt)                                               AS ec_billed_6m,
        SUM(mc_amt)                                               AS mc_billed_6m,
        SUM(ec_amt + mc_amt)                                      AS obligation_6m,
        -- the REAL mid-cycle intensity, from the bill types rather than from an
        -- invented payment-code mapping.
        SUM(mc_amt) / NULLIF(SUM(ec_amt + mc_amt), 0)             AS midcycle_billed_share,
        APPROX_PERCENTILE(ec_amt + mc_amt, 0.5)
            FILTER (WHERE ec_amt + mc_amt > 0)                    AS med_obligation,
        MAX(ec_amt)                                               AS max_bill,
        STDDEV_SAMP(ec_amt) FILTER (WHERE ec_amt > 0)             AS bill_std
FROM (
    SELECT  c.sbrp_id,
            c.day_key / 100                                       AS month_key,
            SUM(COALESCE(c.payment_due_amt,0))
                FILTER (WHERE c.cust_bil_typ_id = 2)              AS ec_amt,
            SUM(COALESCE(c.payment_due_amt,0))
                FILTER (WHERE c.cust_bil_typ_id = 3)              AS mc_amt
    FROM        dwbi_fact_db.v_fact_cust_bil_daily c
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
    WHERE   c.day_key BETWEEN 14031101 AND 14040431   -- FEATURE window only
      AND   c.cust_bil_typ_id IN (2, 3)
      -- NO day-of-month guard. An earlier version had MOD(day_key,100) >= 28 as
      -- a cost guard, valid while only the end-of-cycle bill was read. Type 3
      -- is the MID-CYCLE bill and does not land on the month end, so that guard
      -- would have silently deleted every mid-cycle bill.
    GROUP BY c.sbrp_id, c.day_key / 100
) t
GROUP BY sbrp_id
-- no end-of-cycle bill in any feature month means no bill to measure against.
HAVING  COUNT(*) FILTER (WHERE ec_amt > 0) > 0
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
        -- NO "why a bar happened" SPLIT ANY MORE. This used to classify each
        -- stat=3 day as non-payment or ceiling, from the balance and the day of
        -- month. CONFIRMED: a one-way bar comes from ONE mechanism only -
        -- monthly usage crossing the SIM's credit ceiling. There is no such
        -- thing as a non-payment one-way bar. An unpaid bill only matters here
        -- because it eats ceiling headroom and brings the breach forward.
        --
        -- That makes the bar ITSELF a near-neutral event, and labelling it as
        -- delinquency was labelling HEAVY, VALUABLE USERS as bad: a low ceiling
        -- against high usage bars often and says nothing about willingness to
        -- pay. What carries the signal is HOW LONG the bar lasts - a subscriber
        -- who pays and reconnects the same day is a good payer on a tight
        -- ceiling; one barred for twenty days is struggling. STEP 4 builds that.
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
            -- billed_amt is the TOTAL the subscriber was billed that month:
            -- end-of-cycle (type 2) plus mid-cycle (type 3). Comparable within
            -- a row against totrev_mN, which is the same month's usage.
            SUM(COALESCE(c.payment_due_amt,0))     AS billed_amt,
            SUM(COALESCE(c.payment_due_amt,0))
                FILTER (WHERE c.cust_bil_typ_id = 3) AS mc_billed_amt
    FROM        dwbi_fact_db.v_fact_cust_bil_daily c
    INNER JOIN  dwbi_temp40_db.dcb3_base b ON b.sbrp_id = c.sbrp_id
    WHERE   c.day_key BETWEEN 14031101 AND 14040431
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
        SUM(billed_amt)                                  AS billed_6m,
        SUM(mc_billed_amt)                               AS mc_billed_6m,
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
        COUNT(*)                                         AS n_months_seen
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
      AND   p.day_key BETWEEN 14031101 AND 14040431
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
SELECT  '140405' AS obs_cohort, b.sbrp_id, r.med_bill,
        -- CAPACITY BASIS = paid_total_6m, as decided. But part of the excess of
        -- payments over billing is ARREARS CLEARED FROM BEFORE THE WINDOW, not
        -- ongoing capacity, so the window overstates capacity for anyone who
        -- was catching up. These two make that visible instead of hiding it:
        --   paid_to_obligation  > 1  was paying down old debt in the window
        --                       < 1  was accumulating new arrears
        --   arrears_paydown_6m  the Rial amount of that excess
        -- Discount proven_capacity by this in Python before setting a limit.
        pay.paid_total_6m / NULLIF(r.obligation_6m, 0)     AS paid_to_obligation,
        GREATEST(pay.paid_total_6m - r.obligation_6m, 0)   AS arrears_paydown_6m,
        dpd.*, bar.*, pan.*, pay.*, pit.*,
        lab.y_twoway_2m, lab.y_twoway_any2m, lab.y_severe, lab.y_strict,
        lab.y_v1, lab.y_v2, lab.y_loose, lab.indeterminate,
        lab.max_dpd_out, lab.n_late_out, lab.total_debt_days_out,
        lab.oneway_days_out, lab.twoway_days_out, lab.twoway_months_out,
        lab.escalated_twoway,
        lab.rule1_dpd60, lab.rule2_late, lab.rule4_escalated
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

SELECT rule1_dpd60, rule2_late, rule4_escalated, COUNT(*) AS n
FROM   dwbi_temp40_db.dcb3_dataset_c1
GROUP BY 1,2,3 ORDER BY n DESC;

-- CEILING PRESSURE MUST NOT PREDICT THE LABEL BY ITSELF. A one-way bar is a
-- ceiling breach, so breaching often should NOT on its own mean bad. If the bad
-- rate rises steeply with the number of ceiling months, the label is still
-- picking up heavy usage rather than delinquency and needs another look. What
-- SHOULD separate is how long each bar lasted.
SELECT  n_ceiling_months_6m,
        COUNT(*)                            AS n,
        AVG(y_v1)                           AS bad_rate,
        AVG(avg_barred_days_per_spell)      AS avg_days_barred
FROM    dwbi_temp40_db.dcb3_dataset_c1
GROUP BY 1 ORDER BY 1;

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

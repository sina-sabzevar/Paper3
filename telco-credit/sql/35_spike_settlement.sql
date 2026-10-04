-- ============================================================================
--  THE STRESS TEST ALREADY IN THE DATA                       (Trino/Presto)
--
--  WHAT CHANGED, AND WHY EVERY AFFORDABILITY TABLE BEFORE THIS IS VOID
--
--  The credit is not spent on telco. It funds VOD subscriptions, bill
--  payments and other services the operator cannot see, and it settles on the
--  SIM bill. So telco revenue no longer measures CAPACITY - a subscriber
--  spending 200,000 Toman a month on telco may draw 2,000,000 for other
--  things, and whether they can repay 2,000,000 depends on household income,
--  which is not in any table here.
--
--  Telco spend therefore demotes to an ENGAGEMENT and DISCIPLINE signal. The
--  capacity question has to be answered another way.
--
--  THE ANSWER IS ALREADY IN THE HISTORY
--
--  Over 140301..140506 - 30 continuous months - subscribers have already been
--  billed amounts far above their own normal. Some settled those months and
--  some did not. That is a natural experiment on exactly the question the
--  product asks, and nobody has to run a pilot to get it.
--
--  The headline number this file produces: for each subscriber, the LARGEST
--  multiple of their own baseline obligation that they have demonstrably
--  settled. A subscriber who has already cleared a month five times their
--  normal bill is evidence for a limit at five times their normal bill. One
--  who has never cleared more than 1.2 times is not, however large their
--  telco spend.
--
--  SETTLEMENT IS "BOTH, CUSTOMER CHOOSES", SO THE MODEL TAKES THE WORST CASE
--
--  If the line can be settled in full at month end OR converted to
--  instalments at the customer's option, then risk has to be sized on full
--  settlement: the whole limit arriving on one bill. That is what makes the
--  spike ratio the right unit rather than an instalment-to-income ratio.
--
--  FAILURE IS "DID NOT SETTLE THE SPIKE"
--
--  A spike month counts as failed when the outstanding balance is still
--  material at the END of the following month - two chances, the month itself
--  and the next. Settled otherwise. A two-way bar is carried alongside as an
--  objective corroborating signal, not as the definition.
--
--  NO percent character anywhere. NO CASE expressions.
--  Run S0 first - it decides whether the rest can run at all.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S0  CAN THIS BE BUILT? bill_outstanding_amt is the column the whole label
--     rests on and it was not in the earlier health check. If it is NULL or
--     all-zero the way debt_scr and suspend_scr turned out to be, this
--     approach is dead and the label has to fall back to the two-way bar.
--
--     Checked across ten months rather than one, because debt_scr looked
--     fine in a single month and was all-zero in six of ten.
-- ---------------------------------------------------------------------------
SELECT  month_key,
        COUNT(*)                                        AS n_rows,
        COUNT(bill_outstanding_amt)                     AS n_nonnull,
        COUNT(DISTINCT bill_outstanding_amt)            AS n_distinct,
        COUNT(*) FILTER (WHERE COALESCE(bill_outstanding_amt, 0) = 0) AS n_zero,
        COUNT(*) FILTER (WHERE bill_outstanding_amt > 0) AS n_positive,
        APPROX_PERCENTILE(bill_outstanding_amt, 0.5)    AS p50,
        APPROX_PERCENTILE(bill_outstanding_amt, 0.9)    AS p90,
        MIN(bill_outstanding_amt)                       AS v_min,
        MAX(bill_outstanding_amt)                       AS v_max
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key IN (140409, 140410, 140411, 140412, 140501,
                      140502, 140503, 140504, 140505, 140506)
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;

-- ---------------------------------------------------------------------------
-- S1  BUILD THE MONTHLY PANEL. One row per subscriber-month over the full
--     30 months, with what they owed, what they paid and what was left.
--
--     due is approximated as paid + outstanding. It is an approximation and
--     named as one: the exact obligation needs the monthly Bill type from
--     v_fact_cust_bil_daily, whose VARCHAR key is still unresolved (D2 in
--     31_bill_type_resolved.sql has not been run). paid + outstanding needs
--     no bill-type resolution and is close enough to rank spikes, which is
--     all a ratio to the subscriber's OWN baseline requires.
--
--     month_key BETWEEN 140301 AND 140506 is a safe RANGE filter even though
--     140313..140399 are not real Jalali months - they simply have no rows.
--     The Jalali trap in this project was month ARITHMETIC (140412 plus one
--     is 140501, not 140413), not range comparison.
--
--     Each side is aggregated to one row per subscriber-month BEFORE they
--     meet, so the join cannot fan out.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_panel;
CREATE TABLE dwbi_temp40_db.dcb_panel WITH (format='PARQUET') AS
WITH pay AS (
    -- all payment statuses. Status 2 holds 61.2 pct of payment value and
    -- status 1 holds 38.7 pct, so filtering to 2 discards over a third.
    SELECT   sbrp_id,
             day_key / 100                           AS month_key,
             SUM(COALESCE(pmnt_amt, 0))              AS paid
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14030101 AND 14050631
    GROUP BY sbrp_id, day_key / 100
),
sub AS (
    SELECT   sbrp_id,
             month_key,
             MAX(COALESCE(bill_outstanding_amt, 0))  AS outst,
             MAX(COALESCE(available_credit, 0))      AS avail,
             MAX(IF(sbrp_stat_id = 4, 1, 0))         AS twoway_bar,
             MAX(IF(sbrp_stat_id = 3, 1, 0))         AS oneway_bar
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140506
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
)
SELECT  s.sbrp_id,
        s.month_key,
        COALESCE(p.paid, 0)                          AS paid,
        s.outst,
        s.avail,
        s.twoway_bar,
        s.oneway_bar,
        COALESCE(p.paid, 0) + s.outst                AS due_approx
FROM        sub s
LEFT JOIN   pay p ON p.sbrp_id = s.sbrp_id AND p.month_key = s.month_key
;

-- ---------------------------------------------------------------------------
-- S2  FIND THE SPIKES AND SCORE THEM. One row per subscriber.
--
--     LEAD takes the NEXT PRESENT month, not the next calendar month. Where a
--     month is missing from the panel the comparison reaches across the gap.
--     Stated rather than hidden; months are near-complete over this window so
--     the effect is small, and an absent month is itself informative.
--
--     settled_floor is 10 pct of the month's own due, so "settled" means the
--     residual is immaterial rather than exactly zero - a 400 Rial rounding
--     tail is not a default.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_spike;
CREATE TABLE dwbi_temp40_db.dcb_spike WITH (format='PARQUET') AS
WITH base AS (
    SELECT   sbrp_id,
             APPROX_PERCENTILE(due_approx, 0.5)                   AS baseline_due,
             COUNT(*)                                             AS n_months,
             SUM(paid)                                            AS paid_total,
             MAX(avail)                                           AS avail_max,
             MAX(twoway_bar)                                      AS ever_twoway,
             MAX(oneway_bar)                                      AS ever_oneway
    FROM     dwbi_temp40_db.dcb_panel
    GROUP BY sbrp_id
),
seq AS (
    SELECT  p.sbrp_id,
            p.month_key,
            p.due_approx,
            p.outst,
            LEAD(p.outst) OVER (PARTITION BY p.sbrp_id
                                ORDER BY p.month_key)             AS outst_next,
            b.baseline_due
    FROM        dwbi_temp40_db.dcb_panel p
    INNER JOIN  base b ON b.sbrp_id = p.sbrp_id
    WHERE   b.baseline_due > 0
),
scored AS (
    SELECT  sbrp_id,
            due_approx / baseline_due                             AS ratio,
            -- settled: the residual is immaterial by the end of the next month
            IF(COALESCE(outst_next, 0) <= 0.10 * due_approx, 1, 0) AS settled
    FROM    seq
)
SELECT  b.sbrp_id,
        b.n_months,
        b.baseline_due,
        b.paid_total,
        b.avail_max,
        b.ever_twoway,
        b.ever_oneway,
        -- how stressed this subscriber has ever been, and how they handled it
        COALESCE(MAX(s.ratio), 0)                                 AS max_ratio_seen,
        COALESCE(MAX(IF(s.settled = 1, s.ratio, 0)), 0)            AS max_ratio_settled,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 2)                AS n_spike_2x,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 3)                AS n_spike_3x,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 5)                AS n_spike_5x,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 2 AND s.settled = 1) AS n_settled_2x,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 3 AND s.settled = 1) AS n_settled_3x,
        COUNT(s.ratio) FILTER (WHERE s.ratio >= 5 AND s.settled = 1) AS n_settled_5x,
        -- THE LABEL: a spike of 2x or more that was never settled
        MAX(IF(s.ratio >= 2 AND s.settled = 0, 1, 0))             AS y_spike_fail_2x,
        MAX(IF(s.ratio >= 3 AND s.settled = 0, 1, 0))             AS y_spike_fail_3x
FROM        base b
LEFT JOIN   scored s ON s.sbrp_id = b.sbrp_id
GROUP BY    b.sbrp_id, b.n_months, b.baseline_due, b.paid_total,
            b.avail_max, b.ever_twoway, b.ever_oneway
;

-- ---------------------------------------------------------------------------
-- S3  THE ANSWER. How many subscribers have proved they can carry a given
--     multiple of their own normal bill.
--
--     Read n_proved against 3,000,000 at each multiple. That is the
--     population for a limit set at that multiple of their baseline, on
--     evidence rather than on an assumed affordability stance.
-- ---------------------------------------------------------------------------
SELECT  mult                                                      AS multiple,
        COUNT(*) FILTER (WHERE max_ratio_settled >= mult)         AS n_proved,
        COUNT(*) FILTER (WHERE max_ratio_seen    >= mult)         AS n_ever_stressed,
        COUNT(*) FILTER (WHERE max_ratio_seen >= mult
                           AND max_ratio_settled < mult)          AS n_failed_it,
        100.0 * COUNT(*) FILTER (WHERE max_ratio_settled >= mult)
              / NULLIF(COUNT(*) FILTER (WHERE max_ratio_seen >= mult), 0)
                                                                  AS pass_rate_pct,
        APPROX_PERCENTILE(baseline_due, 0.5) / 10000               AS med_baseline_k_toman
FROM        dwbi_temp40_db.dcb_spike
CROSS JOIN  UNNEST(ARRAY[1.5, 2.0, 3.0, 5.0, 8.0, 12.0]) AS t (mult)
GROUP BY    mult
ORDER BY    mult;

-- The label's own rate, and whether it agrees with the operator's two-way bar.
-- If they disagree sharply, one of them is not measuring default.
SELECT  COUNT(*)                                                  AS subscribers,
        100.0 * SUM(y_spike_fail_2x) / COUNT(*)                   AS fail_2x_pct,
        100.0 * SUM(y_spike_fail_3x) / COUNT(*)                   AS fail_3x_pct,
        100.0 * SUM(ever_twoway) / COUNT(*)                       AS ever_twoway_pct,
        SUM(IF(y_spike_fail_2x = 1 AND ever_twoway = 1, 1, 0))    AS both,
        SUM(IF(y_spike_fail_2x = 1 AND ever_twoway = 0, 1, 0))    AS spike_only,
        SUM(IF(y_spike_fail_2x = 0 AND ever_twoway = 1, 1, 0))    AS bar_only
FROM    dwbi_temp40_db.dcb_spike;

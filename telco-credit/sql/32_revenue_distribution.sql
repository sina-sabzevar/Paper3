-- ============================================================================
--  REVENUE DISTRIBUTION ACROSS THE WHOLE PERMANENT BASE     (Trino/Presto)
--
--  Before any threshold is chosen, the distribution. The question "can we
--  find 3,000,000 subscribers above 170,000 Toman a month" has one honest
--  answer and it is a percentile, not an estimate.
--
--  REVENUE, NOT PAYMENT, AND WHY BOTH ARE HERE
--
--  Revenue includes cash. A subscriber who buys 300,000 Toman of packages
--  with cash generates that revenue and it never appears as a payment on a
--  bill, so payment-based measures understate them. That is the case for
--  using revenue, and it is correct for sizing CAPACITY.
--
--  But the two measure different things. Cash spend is prepaid - money
--  handed over before consumption, with no collection risk at all. An
--  instalment on a bill is credit - consumption first, payment later. A
--  subscriber can be excellent at the first and poor at the second.
--
--  So R3 reports revenue and payment SIDE BY SIDE on the same subscribers.
--  The gap between them is not noise: it is the share of spending that
--  arrives as cash, and for a credit product it is the risk the model has to
--  carry. If revenue clears 170,000 for 5,000,000 subscribers and payment
--  clears it for 2,000,000, the 3,000,000 difference are people who can
--  afford the service but have never been billed and collected from at that
--  level.
--
--  DEFINITIONS, PER KPI_v4
--
--    revenue   = SUM(arpu) - SUM(tot_arpu_tax_amt), per subscriber per month
--    Active1   = active1_base_flag = 1, which makes sbrp_stat_id redundant
--    amounts   are in Rial. 170,000 Toman = 1,700,000 Rial.
--
--  CALENDAR. The four most recent complete months: 140503..140506.
--  Jalali months are written out - 140412 plus one is 140501, not 140413.
--
--  A MONTH WITH NO ROW IS ZERO REVENUE, NOT UNKNOWN. Every month is
--  COALESCEd to 0 before any comparison, so a subscriber absent from a month
--  counts as having earned nothing that month rather than dropping out of the
--  denominator.
--
--  NO percent character anywhere. NO CASE expressions.
--  Run R1, then R2, then R3.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- R1  THE DISTRIBUTION. One row per month, so a bad load month is visible
--     before it is averaged away.
--
--     Read n_over_170k against 3,000,000 directly.
-- ---------------------------------------------------------------------------
SELECT  month_key,
        COUNT(*)                                            AS n_permanent,
        COUNT(*) FILTER (WHERE active1_base_flag = 1)        AS n_active1,
        SUM(COALESCE(arpu, 0) - COALESCE(tot_arpu_tax_amt, 0)) / 1e12
                                                            AS revenue_tn_rial,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.10) / 10000 AS p10_k_toman,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.25) / 10000 AS p25_k_toman,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.50) / 10000 AS p50_k_toman,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.75) / 10000 AS p75_k_toman,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.90) / 10000 AS p90_k_toman,
        APPROX_PERCENTILE(COALESCE(arpu,0)
                        - COALESCE(tot_arpu_tax_amt,0), 0.95) / 10000 AS p95_k_toman,
        COUNT(*) FILTER (WHERE COALESCE(arpu,0)
                             - COALESCE(tot_arpu_tax_amt,0) >= 1700000)
                                                            AS n_over_170k,
        COUNT(*) FILTER (WHERE active1_base_flag = 1
                           AND COALESCE(arpu,0)
                             - COALESCE(tot_arpu_tax_amt,0) >= 1700000)
                                                            AS n_active1_over_170k
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key IN (140503, 140504, 140505, 140506)
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;

-- ---------------------------------------------------------------------------
-- R2  BUILD IT. Revenue and payment per subscriber for the same four months.
--
--     The payment side has no status filter in the WHERE: bllg_pmnt_stat_id
--     = 2 for "successful" is still unverified (register item B), so both
--     totals are carried and R3 compares them.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_revdist;
CREATE TABLE dwbi_temp40_db.dcb_revdist WITH (format='PARQUET') AS
WITH rv AS (
    SELECT   sbrp_id,
             month_key,
             MAX(IF(active1_base_flag = 1, 1, 0))                 AS act1,
             SUM(COALESCE(arpu, 0)
                 - COALESCE(tot_arpu_tax_amt, 0))                 AS rev
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140503, 140504, 140505, 140506)
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
),
pm AS (
    -- no status filter in the WHERE: bllg_pmnt_stat_id = 2 is still
    -- unverified (register item B), so both totals are carried
    SELECT   sbrp_id,
             day_key / 100                                        AS month_key,
             SUM(COALESCE(pmnt_amt, 0))                           AS paid_all,
             COALESCE(SUM(COALESCE(pmnt_amt, 0))
                      FILTER (WHERE bllg_pmnt_stat_id = 2), 0)    AS paid_s2
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14050301 AND 14050631
    GROUP BY sbrp_id, day_key / 100
),
-- EACH SIDE IS FLATTENED TO ONE ROW PER SUBSCRIBER BEFORE THEY MEET.
--
-- An earlier version joined rv and pm to a key list in the same SELECT, both
-- on sbrp_id alone. rv carries up to 4 rows per subscriber and pm up to 4, so
-- that is a 16 row cartesian product, and a month-filtered SUM over it adds
-- each month FOUR times. The month FILTER does not save it - the filtered row
-- is itself duplicated. This is the same fan-out that once produced a 36 pct
-- bad rate out of ordinary behaviour, so each side is aggregated to one row
-- per key first and the join below is strictly one to one.
rv_wide AS (
    SELECT   sbrp_id,
             COALESCE(MAX(act1), 0)                                  AS act1_any,
             IF(COALESCE(SUM(act1), 0) = 4, 1, 0)                    AS act1_all4,
             COALESCE(SUM(rev) FILTER (WHERE month_key = 140503), 0) AS r1,
             COALESCE(SUM(rev) FILTER (WHERE month_key = 140504), 0) AS r2,
             COALESCE(SUM(rev) FILTER (WHERE month_key = 140505), 0) AS r3,
             COALESCE(SUM(rev) FILTER (WHERE month_key = 140506), 0) AS r4
    FROM     rv
    GROUP BY sbrp_id
),
pm_wide AS (
    SELECT   sbrp_id,
             COALESCE(SUM(paid_s2) FILTER (WHERE month_key = 140503), 0) AS q1,
             COALESCE(SUM(paid_s2) FILTER (WHERE month_key = 140504), 0) AS q2,
             COALESCE(SUM(paid_s2) FILTER (WHERE month_key = 140505), 0) AS q3,
             COALESCE(SUM(paid_s2) FILTER (WHERE month_key = 140506), 0) AS q4,
             COALESCE(SUM(paid_all) FILTER (WHERE month_key = 140503), 0) AS q1a,
             COALESCE(SUM(paid_all) FILTER (WHERE month_key = 140504), 0) AS q2a,
             COALESCE(SUM(paid_all) FILTER (WHERE month_key = 140505), 0) AS q3a,
             COALESCE(SUM(paid_all) FILTER (WHERE month_key = 140506), 0) AS q4a
    FROM     pm
    GROUP BY sbrp_id
)
SELECT  v.sbrp_id,
        v.act1_any,
        v.act1_all4,
        v.r1, v.r2, v.r3, v.r4,
        -- a subscriber with no payment rows paid nothing, so COALESCE here
        -- rather than letting the LEFT JOIN leave NULLs that every
        -- comparison downstream would silently fail
        COALESCE(p.q1, 0)  AS q1,  COALESCE(p.q2, 0)  AS q2,
        COALESCE(p.q3, 0)  AS q3,  COALESCE(p.q4, 0)  AS q4,
        COALESCE(p.q1a, 0) AS q1a, COALESCE(p.q2a, 0) AS q2a,
        COALESCE(p.q3a, 0) AS q3a, COALESCE(p.q4a, 0) AS q4a
FROM        rv_wide v
LEFT JOIN   pm_wide p ON p.sbrp_id = v.sbrp_id
;

-- ---------------------------------------------------------------------------
-- R3  THE ANSWER. How many months out of four each subscriber clears
--     170,000 Toman, on revenue and on payment, on the same people.
--
--     The proposed rule is 2 or 3 months, so read months_rev of 2, 3 and 4
--     and add them. months_pay beside it is how many of those same people
--     have actually been billed and collected from at that level.
-- ---------------------------------------------------------------------------
SELECT  months_rev,
        COUNT(*)                                        AS n_subscribers,
        COUNT(*) FILTER (WHERE act1_all4 = 1)           AS n_active1_all4,
        APPROX_PERCENTILE((r1+r2+r3+r4)/4, 0.5) / 10000 AS median_mthly_rev_k_toman,
        -- of these, how many also clear it on PAYMENT in as many months
        SUM(months_pay)                                 AS sum_months_pay,
        COUNT(*) FILTER (WHERE months_pay >= 2)         AS also_2m_on_payment,
        COUNT(*) FILTER (WHERE months_pay >= months_rev) AS payment_keeps_up,
        APPROX_PERCENTILE((q1+q2+q3+q4)/4, 0.5) / 10000 AS median_mthly_paid_k_toman
FROM (
    SELECT  act1_all4, r1, r2, r3, r4, q1, q2, q3, q4,
            IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
          + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0)  AS months_rev,
            IF(q1 >= 1700000,1,0) + IF(q2 >= 1700000,1,0)
          + IF(q3 >= 1700000,1,0) + IF(q4 >= 1700000,1,0)  AS months_pay
    FROM    dwbi_temp40_db.dcb_revdist
) t
GROUP BY months_rev
ORDER BY months_rev;

-- The threshold sweep, so 3,000,000 can be read off against the cut rather
-- than fixed at 170,000 first. n_2to3m and n_at_least_2m are the proposed
-- rule's population at each threshold.
SELECT  thr / 10000                                    AS threshold_k_toman,
        COUNT(*) FILTER (WHERE mr >= 2)                 AS n_at_least_2m,
        COUNT(*) FILTER (WHERE mr IN (2, 3))            AS n_2to3m,
        COUNT(*) FILTER (WHERE mr = 4)                  AS n_all_4m,
        COUNT(*) FILTER (WHERE mr >= 2 AND act1_all4 = 1) AS n_2m_active1,
        COUNT(*) FILTER (WHERE mp >= 2)                 AS n_at_least_2m_on_payment
FROM (
    SELECT  d.act1_all4,
            IF(d.r1 >= t.thr,1,0) + IF(d.r2 >= t.thr,1,0)
          + IF(d.r3 >= t.thr,1,0) + IF(d.r4 >= t.thr,1,0)   AS mr,
            IF(d.q1 >= t.thr,1,0) + IF(d.q2 >= t.thr,1,0)
          + IF(d.q3 >= t.thr,1,0) + IF(d.q4 >= t.thr,1,0)   AS mp,
            t.thr
    FROM        dwbi_temp40_db.dcb_revdist d
    CROSS JOIN  UNNEST(ARRAY[1000000, 1300000, 1500000, 1700000,
                             2000000, 2500000, 3000000]) AS t (thr)
) u
GROUP BY thr
ORDER BY thr;

-- Does the unverified payment status filter matter here too?
SELECT  'status 2 only' AS basis,
        COUNT(*) FILTER (WHERE IF(q1>=1700000,1,0)+IF(q2>=1700000,1,0)
                             + IF(q3>=1700000,1,0)+IF(q4>=1700000,1,0) >= 2)
                                                        AS n_at_least_2m
FROM    dwbi_temp40_db.dcb_revdist
UNION ALL
SELECT  'all statuses',
        COUNT(*) FILTER (WHERE IF(q1a>=1700000,1,0)+IF(q2a>=1700000,1,0)
                             + IF(q3a>=1700000,1,0)+IF(q4a>=1700000,1,0) >= 2)
FROM    dwbi_temp40_db.dcb_revdist;

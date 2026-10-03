-- ============================================================================
--  Three diagnostics on what bill_outstanding_amt actually measures.
--  Run BEFORE the main extract: two parameters depend on the answers.
--  A 100k-subscriber sample is plenty.
--
--  PORTABILITY
--   - no percent character anywhere (Python drivers read it as a format spec)
--   - no CASE expressions (use FILTER, which Trino and Presto both support)
--   - each query is ONE self-contained statement; run them one at a time
--  If FILTER is rejected by your engine, the CASE equivalent is noted under
--  each query.
-- ============================================================================


-- ===========================================================================
-- D1.  Are the non-zero balances whole bills, or small remainders?
--      Sets the materiality floor in 10_dcb_extract_v2.sql.
--
--      Output is one row. Read ratio_pctiles as the balance divided by the
--      subscriber's own median monthly invoice, at the 5th, 10th, 25th, 50th,
--      75th, 90th and 95th percentile of the days where a balance exists.
--
--      p25 at or above 0.9  -> balances are whole unpaid bills. Set the floor
--                              to 0.05; a 0.25 floor would discard real debt.
--      p25 well below 0.25  -> small remainders do survive. Keep 0.25.
-- ===========================================================================
SELECT  COUNT(*)                                             AS n_days_with_balance,
        APPROX_PERCENTILE(r, ARRAY[0.05,0.10,0.25,0.50,0.75,0.90,0.95]) AS ratio_pctiles,
        COUNT(*) FILTER (WHERE r < 0.05)                     AS n_under_005,
        COUNT(*) FILTER (WHERE r < 0.25)                     AS n_under_025,
        COUNT(*) FILTER (WHERE r < 0.90)                     AS n_under_090,
        COUNT(*) FILTER (WHERE r >= 1.50)                    AS n_accumulated
FROM (
    SELECT  d.bill_outstanding_amt / m.med_invoice AS r
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip d
    JOIN (  SELECT  sbrp_id, APPROX_PERCENTILE(invoice_amt, 0.5) AS med_invoice
            FROM (  SELECT  sbrp_id, month_key,
                            MAX(COALESCE(invoice_amt,0)) AS invoice_amt
                    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
                    WHERE   month_key BETWEEN 140308 AND 140404
                    GROUP BY sbrp_id, month_key ) a
            GROUP BY sbrp_id
            HAVING APPROX_PERCENTILE(invoice_amt, 0.5) > 0 ) m
      ON  m.sbrp_id = d.sbrp_id
    WHERE   d.day_key BETWEEN 14040101 AND 14040431
      AND   COALESCE(d.bill_outstanding_amt, 0) > 0
) t
;
--  no FILTER?  COUNT(*) FILTER (WHERE r < 0.25)
--              becomes SUM(CASE WHEN r < 0.25 THEN 1 ELSE 0 END)


-- ===========================================================================
-- D2.  Does a PARTIAL payment clear the balance to zero?
--      The most important of the three.
--
--      Output is one row, five numbers.
--
--      cleared_when_underpaid near 1 -> paying a tenth of a bill zeroes the
--          balance just like paying all of it. The column then tells us only
--          WHETHER something is open, never HOW MUCH, and three things change:
--          pay_ratio has to come from invoice_amt and pmnt_amt, the 60-day
--          threshold has to drop because measured DPD is shorter than reality,
--          and a pay_ratio rule joins the label.
--      cleared_when_underpaid near 0 -> the balance tracks the real amount and
--          the current design stands unchanged.
-- ===========================================================================
SELECT  COUNT(*)                                                AS n_subscriber_months,
        COUNT(*) FILTER (WHERE cov < 0.50)                      AS n_underpaid,
        AVG(cleared) FILTER (WHERE cov < 0.10)                  AS cleared_when_paid_under_10pct,
        AVG(cleared) FILTER (WHERE cov < 0.50)                  AS cleared_when_underpaid,
        AVG(cleared) FILTER (WHERE cov >= 0.90)                 AS cleared_when_paid_in_full
FROM (
    SELECT  mth.sbrp_id,
            mth.pmnt_amt / mth.invoice_amt                      AS cov,
            IF(eom.bill_out_at_eom = 0, 1.0, 0.0)               AS cleared
    FROM (  SELECT  sbrp_id, month_key,
                    MAX(COALESCE(invoice_amt,0)) AS invoice_amt,
                    MAX(COALESCE(pmnt_amt,0))    AS pmnt_amt
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key BETWEEN 140401 AND 140404
            GROUP BY sbrp_id, month_key
            HAVING  MAX(COALESCE(invoice_amt,0)) > 0 ) mth
    JOIN (  SELECT  d.sbrp_id,
                    d.day_key / 100                    AS month_key,
                    MAX(d.bill_outstanding_amt)        AS bill_out_at_eom
            FROM    dwbi_fact_db.v_fact_sbrp_daily_cip d
            JOIN (  SELECT sbrp_id, day_key / 100 AS month_key, MAX(day_key) AS last_day
                    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
                    WHERE  day_key BETWEEN 14040101 AND 14040431
                    GROUP BY sbrp_id, day_key / 100 ) le
              ON  le.sbrp_id = d.sbrp_id AND le.last_day = d.day_key
            GROUP BY d.sbrp_id, d.day_key / 100 ) eom
      ON  eom.sbrp_id = mth.sbrp_id AND eom.month_key = mth.month_key
) t
;
--  no IF()?      IF(x = 0, 1.0, 0.0)  becomes  CAST(x = 0 AS DOUBLE)
--  no FILTER?    AVG(cleared) FILTER (WHERE cov < 0.50)
--                becomes AVG(CASE WHEN cov < 0.50 THEN cleared END)


-- ===========================================================================
-- D3.  Does a mid-cycle payment clear the balance the same way?
--      Confirms the assumption the label rests on.
--
--      cleared_bill_next_day high        -> type 6 behaves like type 4.
--                                           Nothing to change.
--      cleared low, reduced_unbill high  -> mid-cycle payments only touch the
--                                           live balance, so the bar split has
--                                           to be built on unbill instead.
--      had_open_bill_before near 0       -> mid-cycle payments happen when no
--                                           bill is open at all, which makes
--                                           the two kinds of bar cleanly
--                                           separable and lets the carried
--                                           test go.
-- ===========================================================================
SELECT  COUNT(*)                                                   AS n_midcycle_payments,
        AVG(IF(b.bill_out > 0, 1.0, 0.0))                          AS had_open_bill_before,
        AVG(IF(b.bill_out > 0 AND b.bill_out_next = 0, 1.0, 0.0))  AS cleared_bill_next_day,
        AVG(IF(b.unbill_out_next < b.unbill_out, 1.0, 0.0))        AS reduced_unbill_next_day,
        AVG(b.bill_out)                                            AS avg_bill_out_before,
        AVG(b.bill_out_next)                                       AS avg_bill_out_after
FROM (
    SELECT  sbrp_id, day_key,
            COALESCE(bill_outstanding_amt,0)   AS bill_out,
            COALESCE(unbill_outstanding_amt,0) AS unbill_out,
            LEAD(COALESCE(bill_outstanding_amt,0))
              OVER (PARTITION BY sbrp_id ORDER BY day_key) AS bill_out_next,
            LEAD(COALESCE(unbill_outstanding_amt,0))
              OVER (PARTITION BY sbrp_id ORDER BY day_key) AS unbill_out_next
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE   day_key BETWEEN 14040101 AND 14040431
) b
JOIN (
    SELECT  DISTINCT sbrp_id, day_key
    FROM    dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE   cust_pmnt_typ_id = 6
      AND   bllg_pmnt_stat_id = 2
      AND   COALESCE(pmnt_amt,0) > 0
      AND   day_key BETWEEN 14040101 AND 14040425
) mid
  ON  mid.sbrp_id = b.sbrp_id AND mid.day_key = b.day_key
;

-- ============================================================================
--  FAST diagnostics. Replaces 04 and 05 - same questions, seconds not minutes.
--
--  WHY THE EARLIER ONES WERE SLOW
--    They scanned five months of a daily fact across the whole base. To learn
--    what a column contains you need one partition, not five months, and a
--    sample of subscribers, not all of them.
--
--  TWO LEVERS USED HERE
--    1. ONE DAY or ONE MONTH per query. day_key and month_key are almost
--       certainly the partition keys, so this is the difference between
--       reading one partition and reading a hundred.
--    2. A 1-in-199 subscriber sample via MOD on the id. Deterministic, so the
--       same subscribers come back on every run and the queries stay
--       comparable.
--
--  If sbrp_id is a string, write MOD(CAST(sbrp_id AS BIGINT), 199).
--  EDIT the two dates at the top of each query to a day and month you know
--  have data. Keep them inside the same month.
-- ============================================================================


-- ===========================================================================
-- F1.  ONE DAY. Do the daily balance columns exist and carry values?
--      This is the question everything else waits on. Should return instantly.
-- ===========================================================================
SELECT  COUNT(*)                                           AS n_rows,
        COUNT(DISTINCT sbrp_id)                            AS n_subs,
        COUNT(bill_outstanding_amt)                        AS bill_not_null,
        COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)   AS bill_positive,
        MAX(bill_outstanding_amt)                          AS bill_max,
        COUNT(unbill_outstanding_amt)                      AS unbill_not_null,
        COUNT(*) FILTER (WHERE unbill_outstanding_amt > 0) AS unbill_positive,
        MAX(unbill_outstanding_amt)                        AS unbill_max
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key = 14050420
;
--  bill_not_null = 0  ->  the column is empty in the daily fact. Stop here and
--                         tell me: days-past-due moves to monthly granularity
--                         and the payment dates in v_fact_pmnt_adjmt carry the
--                         timing instead.


-- ===========================================================================
-- F2.  ONE MONTH. Do the monthly columns the label needs carry values?
-- ===========================================================================
SELECT  COUNT(*)                                          AS n_rows,
        COUNT(*) FILTER (WHERE invoice_amt > 0)           AS invoice_positive,
        COUNT(*) FILTER (WHERE pmnt_amt > 0)              AS pmnt_positive,
        COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)  AS bill_out_positive,
        APPROX_PERCENTILE(invoice_amt, ARRAY[0.25,0.50,0.75,0.95]) AS invoice_pctiles,
        APPROX_PERCENTILE(pmnt_amt,    ARRAY[0.25,0.50,0.75,0.95]) AS pmnt_pctiles
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140504
;


-- ===========================================================================
-- F3.  ONE SUBSCRIBER, ONE MONTH, DAY BY DAY.
--      The single most informative query here: it shows what the columns
--      actually do across a billing cycle. Run it for two or three different
--      subscribers.
-- ===========================================================================
SELECT  day_key, sbrp_stat_id, bill_outstanding_amt, unbill_outstanding_amt
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14050401 AND 14050431
  AND   sbrp_id = (
            SELECT  sbrp_id
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key = 140504
              AND   bill_outstanding_amt > 0
              AND   invoice_amt > 0
            LIMIT   1 )
ORDER BY day_key
;


-- ===========================================================================
-- F4.  D1 on a sample: are the non-zero balances whole bills or remainders?
--      One month, 1-in-199 subscribers. Sets the materiality floor.
--
--      p25 at or above 0.9  -> whole unpaid bills. Set the floor to 0.05.
--      p25 well below 0.25  -> remainders survive. Keep 0.25.
-- ===========================================================================
SELECT  COUNT(*)                                  AS n_days_with_balance,
        APPROX_PERCENTILE(r, ARRAY[0.10,0.25,0.50,0.75,0.90]) AS ratio_pctiles,
        COUNT(*) FILTER (WHERE r < 0.25)          AS n_under_025,
        COUNT(*) FILTER (WHERE r >= 1.50)         AS n_accumulated
FROM (
    SELECT  d.bill_outstanding_amt / m.invoice_amt AS r
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip d
    JOIN (  SELECT  sbrp_id, MAX(invoice_amt) AS invoice_amt
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key = 140504
              AND   invoice_amt > 0
              AND   MOD(sbrp_id, 199) = 0
            GROUP BY sbrp_id ) m
      ON  m.sbrp_id = d.sbrp_id
    WHERE   d.day_key BETWEEN 14050401 AND 14050431
      AND   d.bill_outstanding_amt > 0
) t
;


-- ===========================================================================
-- F5.  D2 on a sample: does a PARTIAL payment clear the balance to zero?
--      The one that can change the label design.
--
--      cleared_when_paid_under_10pct near 1 -> the balance only says WHETHER
--          something is open, never HOW MUCH. pay_ratio then has to come from
--          invoice_amt and pmnt_amt, the 60-day threshold drops, and a
--          pay_ratio rule joins the label.
-- ===========================================================================
SELECT  COUNT(*)                                        AS n_subscriber_months,
        AVG(cleared) FILTER (WHERE cov < 0.10)          AS cleared_when_paid_under_10pct,
        AVG(cleared) FILTER (WHERE cov < 0.50)          AS cleared_when_underpaid,
        AVG(cleared) FILTER (WHERE cov >= 0.90)         AS cleared_when_paid_in_full
FROM (
    SELECT  m.pmnt_amt / m.invoice_amt                  AS cov,
            IF(e.bill_out = 0, 1.0, 0.0)                AS cleared
    FROM (  SELECT  sbrp_id,
                    MAX(invoice_amt) AS invoice_amt,
                    MAX(pmnt_amt)    AS pmnt_amt
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key = 140504
              AND   invoice_amt > 0
              AND   MOD(sbrp_id, 199) = 0
            GROUP BY sbrp_id ) m
    JOIN (  SELECT  sbrp_id, MAX(bill_outstanding_amt) AS bill_out
            FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
            WHERE   day_key = 14050431          -- last day of the month
            GROUP BY sbrp_id ) e
      ON  e.sbrp_id = m.sbrp_id
) t
;


-- ===========================================================================
-- F6.  D3 on a sample: does a mid-cycle payment clear the balance?
--      Two days only - the payment day and the one after.
-- ===========================================================================
SELECT  COUNT(*)                                            AS n_midcycle_payments,
        AVG(IF(b.bill_out > 0, 1.0, 0.0))                   AS had_open_bill_before,
        AVG(IF(b.bill_out > 0 AND a.bill_out = 0, 1.0, 0.0)) AS cleared_next_day,
        AVG(IF(a.unbill_out < b.unbill_out, 1.0, 0.0))      AS reduced_unbill_next_day
FROM (  SELECT DISTINCT sbrp_id
        FROM   dwbi_fact_db.v_fact_pmnt_adjmt
        WHERE  day_key = 14050420
          AND  cust_pmnt_typ_id = 6
          AND  bllg_pmnt_stat_id = 2
          AND  pmnt_amt > 0 ) p
JOIN (  SELECT sbrp_id,
               COALESCE(bill_outstanding_amt,0)   AS bill_out,
               COALESCE(unbill_outstanding_amt,0) AS unbill_out
        FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
        WHERE  day_key = 14050419 ) b  ON b.sbrp_id = p.sbrp_id
JOIN (  SELECT sbrp_id,
               COALESCE(bill_outstanding_amt,0)   AS bill_out,
               COALESCE(unbill_outstanding_amt,0) AS unbill_out
        FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
        WHERE  day_key = 14050421 ) a  ON a.sbrp_id = p.sbrp_id
;

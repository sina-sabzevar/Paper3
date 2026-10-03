-- ============================================================================
--  NOTE ON THE PERCENT SIGN
--  This file deliberately contains no percent character anywhere - not in SQL,
--  not in string literals, not in comments. Python DB drivers (pyhive, trino,
--  presto, PyMySQL) default to pyformat/format paramstyle and run printf-style
--  substitution over the whole statement before sending it, so a stray percent
--  sign raises "unsupported format character". Modulo is therefore written
--  MOD(x, y), and percentages are spelled "pct".
--  Keep it that way when editing - or pass the SQL parameter-free, e.g.
--      cursor.execute(sql)            with paramstyle set to 'qmark'/'named'
--      sqlalchemy: conn.execute(text(sql))
--      or simply sql.replace(chr(37), chr(37)*2) before execute()
-- ============================================================================
--  Three diagnostics on how bill_outstanding_amt actually behaves.
--  Run these BEFORE the main extract: two parameters depend on the answers.
--  A 100k-subscriber sample is plenty.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- D1.  Are there small lingering balances, or is it all-or-nothing?
--
--  Sets MATERIALITY_FLOOR in 10_dcb_extract_v2.sql.
--
--  Reading it:
--    mass concentrated at >=90pct   -> the balance is whole unpaid bills only.
--                                    Set the floor near zero (0.05); a 25pct
--                                    floor would then be throwing away real debt.
--    a visible shoulder below 25pct -> partial remainders do survive. Keep 0.25.
-- ---------------------------------------------------------------------------
WITH med AS (
    SELECT  sbrp_id, APPROX_PERCENTILE(invoice_amt, 0.5) AS med_invoice
    FROM (  SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
            FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE  month_key BETWEEN 140308 AND 140404
            GROUP BY sbrp_id, month_key ) t
    GROUP BY sbrp_id
    HAVING  APPROX_PERCENTILE(invoice_amt, 0.5) > 0
)
SELECT  CASE WHEN r < 0.05 THEN '1  under 5pct'
             WHEN r < 0.15 THEN '2  5-15pct'
             WHEN r < 0.25 THEN '3  15-25pct'
             WHEN r < 0.50 THEN '4  25-50pct'
             WHEN r < 0.90 THEN '5  50-90pct'
             WHEN r < 1.50 THEN '6  about one bill'
             ELSE               '7  more than one bill (accumulated)'
        END                                   AS balance_vs_own_bill,
        COUNT(*)                              AS n_days,
        COUNT(*) / SUM(COUNT(*)) OVER ()      AS share
FROM (
    SELECT  d.bill_outstanding_amt / m.med_invoice AS r
    FROM        dwbi_fact_db.v_fact_sbrp_daily_cip d
    INNER JOIN  med m ON m.sbrp_id = d.sbrp_id
    WHERE   d.day_key BETWEEN 14040101 AND 14040431
      AND   COALESCE(d.bill_outstanding_amt, 0) > 0        -- non-zero days only
) t
GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- D2.  Does a PARTIAL payment zero the balance?
--
--  This is the one that matters most. If paying 10pct of a bill clears
--  bill_outstanding_amt to zero, then underpayment is invisible in that column
--  and pay_ratio has to be reconstructed from invoice_amt and pmnt_amt instead.
--
--  Reading it:
--    "cleared" high in the low-coverage rows -> partial payments DO zero it.
--                                               The balance cannot be trusted
--                                               as a measure of how much is owed,
--                                               only of whether anything is open.
--    "cleared" near zero there               -> the balance tracks the real
--                                               amount and can be used directly.
-- ---------------------------------------------------------------------------
WITH monthly AS (
    SELECT  c.sbrp_id, c.month_key,
            MAX(COALESCE(c.invoice_amt,0))  AS invoice_amt,
            MAX(COALESCE(c.pmnt_amt,0))     AS pmnt_amt
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip c
    WHERE   c.month_key BETWEEN 140401 AND 140404
    GROUP BY c.sbrp_id, c.month_key
),
month_end AS (
    SELECT  sbrp_id, day_key / 100 AS month_key,
            MAX(day_key)           AS last_day
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE   day_key BETWEEN 14040101 AND 14040431
    GROUP BY sbrp_id, day_key / 100
),
eom AS (
    SELECT  me.sbrp_id, me.month_key,
            MAX(COALESCE(d.bill_outstanding_amt,0)) AS bill_out_at_eom
    FROM        month_end me
    INNER JOIN  dwbi_fact_db.v_fact_sbrp_daily_cip d
                     ON d.sbrp_id = me.sbrp_id AND d.day_key = me.last_day
    GROUP BY me.sbrp_id, me.month_key
)
SELECT  CASE WHEN cov < 0.10 THEN '1  paid under 10pct of the bill'
             WHEN cov < 0.50 THEN '2  paid 10-50pct'
             WHEN cov < 0.90 THEN '3  paid 50-90pct'
             WHEN cov < 1.01 THEN '4  paid in full'
             ELSE                 '5  paid more than billed'
        END                                        AS payment_coverage,
        COUNT(*)                                   AS n_subscriber_months,
        AVG(CASE WHEN bill_out_at_eom = 0 THEN 1.0 ELSE 0 END) AS share_cleared_to_zero
FROM (
    SELECT  m.sbrp_id, m.month_key,
            m.pmnt_amt / NULLIF(m.invoice_amt, 0) AS cov,
            e.bill_out_at_eom
    FROM        monthly m
    INNER JOIN  eom e ON e.sbrp_id = m.sbrp_id AND e.month_key = m.month_key
    WHERE   m.invoice_amt > 0
) t
GROUP BY 1 ORDER BY 1;


-- ---------------------------------------------------------------------------
-- D3.  Does a mid-cycle payment clear the balance the same way?
--
--  Confirms that payment type 6 behaves like type 4, which the label assumes.
--  Compares the balance on the day before a mid-cycle payment with the day
--  after. If "cleared_next_day" is high, the two types are interchangeable
--  for our purposes and no special handling is needed.
-- ---------------------------------------------------------------------------
WITH mid AS (
    SELECT DISTINCT sbrp_id, day_key
    FROM   dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE  cust_pmnt_typ_id = 6            -- mid cycle
      AND  bllg_pmnt_stat_id = 2
      AND  COALESCE(pmnt_amt,0) > 0
      AND  day_key BETWEEN 14040101 AND 14040425
),
bal AS (
    SELECT  sbrp_id, day_key,
            COALESCE(bill_outstanding_amt,0)   AS bill_out,
            COALESCE(unbill_outstanding_amt,0) AS unbill_out,
            LEAD(COALESCE(bill_outstanding_amt,0))
              OVER (PARTITION BY sbrp_id ORDER BY day_key) AS bill_out_next,
            LEAD(COALESCE(unbill_outstanding_amt,0))
              OVER (PARTITION BY sbrp_id ORDER BY day_key) AS unbill_out_next
    FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE   day_key BETWEEN 14040101 AND 14040431
)
SELECT  COUNT(*)                                                  AS n_midcycle_payments,
        AVG(CASE WHEN b.bill_out > 0 THEN 1.0 ELSE 0 END)         AS had_open_bill_before,
        AVG(CASE WHEN b.bill_out > 0 AND b.bill_out_next = 0
                 THEN 1.0 ELSE 0 END)                             AS cleared_bill_next_day,
        AVG(CASE WHEN b.unbill_out_next < b.unbill_out
                 THEN 1.0 ELSE 0 END)                             AS reduced_unbill_next_day,
        AVG(b.bill_out)                                           AS avg_bill_out_before,
        AVG(b.bill_out_next)                                      AS avg_bill_out_after
FROM        mid m
INNER JOIN  bal b ON b.sbrp_id = m.sbrp_id AND b.day_key = m.day_key;

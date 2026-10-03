-- ============================================================================
--  Why did D1 come back empty? Eight one-line queries that isolate the cause.
--  Run them IN ORDER and stop at the first one that returns 0 or all NULL.
--  Each is a single statement. No percent character, no CASE.
--
--  >>> EDIT THESE TWO RANGES TO MATCH YOUR DATA, then keep them consistent <<<
--      monthly window : 140409 .. 140505
--      daily window   : 14050101 .. 14050531
--  (whatever you pick, the daily window must sit INSIDE the monthly one)
-- ============================================================================


-- Q1. Does the daily table have rows in the window at all?
SELECT COUNT(*) AS n_rows, COUNT(DISTINCT sbrp_id) AS n_subs,
       MIN(day_key) AS first_day, MAX(day_key) AS last_day
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14050101 AND 14050531;


-- Q2. THE KEY ONE. Does bill_outstanding_amt exist and carry values THERE?
--     If n_not_null is 0, the column is empty in the daily table and the whole
--     daily-DPD design has to move to monthly granularity. Say so and stop.
SELECT COUNT(*)                                         AS n_rows,
       COUNT(bill_outstanding_amt)                      AS n_not_null,
       COUNT(*) FILTER (WHERE bill_outstanding_amt > 0) AS n_positive,
       MAX(bill_outstanding_amt)                        AS max_value,
       AVG(bill_outstanding_amt)                        AS avg_value
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14050101 AND 14050531;


-- Q3. Same question for unbill_outstanding_amt in the daily table.
SELECT COUNT(*)                                           AS n_rows,
       COUNT(unbill_outstanding_amt)                      AS n_not_null,
       COUNT(*) FILTER (WHERE unbill_outstanding_amt > 0) AS n_positive,
       MAX(unbill_outstanding_amt)                        AS max_value
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14050101 AND 14050531;


-- Q4. And in the MONTHLY table, where your own query reads it from.
SELECT COUNT(*)                                         AS n_rows,
       COUNT(bill_outstanding_amt)                      AS n_not_null,
       COUNT(*) FILTER (WHERE bill_outstanding_amt > 0) AS n_positive,
       MAX(bill_outstanding_amt)                        AS max_value
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key BETWEEN 140409 AND 140505;


-- Q5. Does invoice_amt carry values? The D1 median filter depends on it.
--     Your original code wrote "where invoice_amt <> 0", which suggests many
--     rows are zero - if MOST are, the HAVING clause in D1 emptied the join.
SELECT COUNT(*)                                AS n_rows,
       COUNT(invoice_amt)                      AS n_not_null,
       COUNT(*) FILTER (WHERE invoice_amt > 0) AS n_positive,
       APPROX_PERCENTILE(invoice_amt, ARRAY[0.25,0.50,0.75,0.95]) AS pctiles
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key BETWEEN 140409 AND 140505;


-- Q6. How many subscribers survive the "median invoice > 0" filter?
SELECT COUNT(*) AS n_subs_with_positive_median
FROM ( SELECT sbrp_id
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140409 AND 140505
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id
       HAVING APPROX_PERCENTILE(invoice_amt, 0.5) > 0 ) b;


-- Q7. And pmnt_amt, which D2 needs.
SELECT COUNT(*)                              AS n_rows,
       COUNT(pmnt_amt)                       AS n_not_null,
       COUNT(*) FILTER (WHERE pmnt_amt > 0)  AS n_positive,
       MAX(pmnt_amt)                         AS max_value
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key BETWEEN 140409 AND 140505;


-- Q8. One real subscriber, day by day. The most informative single query here:
--     it shows what the columns actually do over a month.
--     Replace the id with any subscriber that has a non-zero balance.
SELECT day_key, sbrp_stat_id, bill_outstanding_amt, unbill_outstanding_amt
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  sbrp_id = (
          SELECT sbrp_id
          FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
          WHERE  month_key = 140504
            AND  bill_outstanding_amt > 0
            AND  invoice_amt > 0
          LIMIT 1 )
  AND  day_key BETWEEN 14050401 AND 14050531
ORDER BY day_key;

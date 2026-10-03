-- ============================================================================
--  v_fact_cust_bil_daily - IS THIS THE SOURCE THAT FILLS THE GAP?
--                                                           (Trino/Presto)
--  The monthly fact's billing columns (invoice_amt AND payable_amt, identical
--  gap) are empty across 140312..140409. If payment_due_amt here is populated
--  in those months, the calendar stops being constrained and C1 can sit
--  anywhere clear of the shock.
--
--  Run B1 FIRST and send it before B2. B2 is written on the assumptions that
--  the date column is day_key and that there is an sbrp_id - B1 settles both,
--  and if either is wrong B2 needs one edit rather than a guess.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- B1  what this table actually holds. Instant - it reads no data.
--     The thing I most need: is the grain a SUBSCRIBER (sbrp_id) or a CUSTOMER
--     (cust_id)? "cust_bil" suggests customer, and one customer can hold many
--     SIMs, in which case a bill here cannot be attributed to a single SIM
--     without a bridge table and the whole approach changes.
-- ---------------------------------------------------------------------------
SHOW COLUMNS FROM dwbi_fact_db.v_fact_cust_bil_daily;


-- ---------------------------------------------------------------------------
-- B2  COVERAGE PER MONTH - the decisive number.
--     Compare n_due_pos against the 26-28M active permanent subscribers the
--     monthly fact reports. If it holds up across 140402..140409, where
--     payable_amt is exactly zero, this source replaces it.
--
--     first_day and last_day also test your statement that the value only
--     exists on the last day of the month: if that is right, both come back
--     as the same day and n_days is 1.
-- ---------------------------------------------------------------------------
SELECT  day_key / 100                                    AS month_key,
        COUNT(*)                                         AS n_rows,
        COUNT(DISTINCT day_key)                          AS n_days,
        MIN(day_key)                                     AS first_day,
        MAX(day_key)                                     AS last_day,
        COUNT(*) FILTER (WHERE payment_due_amt > 0)      AS n_due_pos,
        APPROX_PERCENTILE(payment_due_amt, 0.5)
            FILTER (WHERE payment_due_amt > 0)           AS due_p50,
        APPROX_PERCENTILE(payment_due_amt, 0.9)
            FILTER (WHERE payment_due_amt > 0)           AS due_p90,
        MAX(payment_due_amt)                             AS due_max
FROM    dwbi_fact_db.v_fact_cust_bil_daily
WHERE   day_key BETWEEN 14030101 AND 14050631
  AND   cust_bil_typ_id = 2
GROUP BY day_key / 100
ORDER BY 1;

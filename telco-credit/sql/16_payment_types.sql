-- ============================================================================
--  WHAT DO THE PAYMENT TYPE CODES MEAN, AND IS THIS TABLE WHOLE?
--                                                           (Trino/Presto)
--  S3 broke an assumption. STEP 6 of the extract was written on
--  "cust_pmnt_typ_id: 4 end of cycle, 6 mid cycle". S3 says type 6 is 99.99
--  pct of all payments for the median subscriber - yet the end-of-cycle bill is
--  75 pct of what was paid. Both cannot be true: if nearly every payment were
--  genuinely mid-cycle, the end-of-cycle bill would be close to zero.
--
--  So type 6 is not "mid-cycle", and every mid-cycle feature built on it is
--  meaningless until the codes are known. That matters because you called
--  mid-cycle behaviour a sensitive and important feature.
--
--  P1 lists what the codes actually are and how big each is.
--  P2 checks this table is not holed in the new feature window - the monthly
--     fact's pmnt_amt IS holed, in 140402 and 140403, and the extract now
--     takes every payment feature from HERE instead, so it has to be whole.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- P1  the code distribution, with the day-of-month profile that reveals the
--     real meaning. A genuinely END-OF-CYCLE payment clusters before the 15th
--     due date; a genuinely MID-CYCLE one is spread across the month. The
--     percentiles of pay_day separate them whatever the codes are named.
-- ---------------------------------------------------------------------------
SELECT  cust_pmnt_typ_id,
        bllg_pmnt_stat_id,
        COUNT(*)                                    AS n_payments,
        COUNT(DISTINCT sbrp_id)                     AS n_subs,
        SUM(COALESCE(pmnt_amt,0))                   AS total_amt,
        APPROX_PERCENTILE(pmnt_amt, 0.5)            AS amt_p50,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.10)  AS pay_day_p10,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.50)  AS pay_day_p50,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.90)  AS pay_day_p90
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14040101 AND 14040431
GROUP BY cust_pmnt_typ_id, bllg_pmnt_stat_id
ORDER BY n_payments DESC;


-- ---------------------------------------------------------------------------
-- P2  per-month coverage of this table across the whole span, so the new
--     feature window 140311..140404 is confirmed whole before anything is run
--     on it.
-- ---------------------------------------------------------------------------
SELECT  day_key / 100                               AS month_key,
        COUNT(*)                                    AS n_payments,
        COUNT(DISTINCT sbrp_id)                     AS n_subs,
        SUM(COALESCE(pmnt_amt,0))                   AS total_amt
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14030101 AND 14050631
  AND   cust_pmnt_typ_id IN (4, 6)
  AND   bllg_pmnt_stat_id = 2
GROUP BY day_key / 100
ORDER BY 1;

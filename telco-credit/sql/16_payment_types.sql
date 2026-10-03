-- ============================================================================
--  ESTABLISH THE CODE MEANINGS BEFORE ANYTHING READS THEM   (Trino/Presto)
--
--  WHAT WENT WRONG. The extract filtered cust_pmnt_typ_id IN (4, 6) and called
--  type 6 "mid-cycle". That mapping was MY OWN INVENTION. It was never given,
--  it entered through a review note of mine and propagated into every version
--  from there, and the data contradicts it: type 6 is 99.99 pct of payments for
--  the median subscriber, which cannot coexist with an end-of-cycle bill worth
--  75 pct of what was paid.
--
--  Both the filter and the mid-cycle features built on it are now removed from
--  11_dcb_extract_v3.sql. Nothing replaces them until these four queries say
--  what the codes are.
--
--  AND THE CORRECTION THAT MATTERS: mid-cycle is identified by cust_bil_typ_id
--  on v_fact_cust_bil_daily, where 2 is the end-of-cycle bill - NOT by any
--  payment-type code. Without the cash and non-cash purchase split it cannot be
--  computed from payments at all. P1 is therefore the important one here.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- P1  cust_bil_typ_id - THE BILL TYPES. CONFIRMED: 2 = end-of-cycle,
--     3 = MID-CYCLE. The extract is already rebuilt on that. P1 is now a
--     VERIFICATION rather than a discovery, and it checks three things:
--       a. type 3 is spread across the month (day_p50 well below 30), which is
--          what makes it mid-cycle. If it also sat on the month end, the split
--          would mean something else.
--       b. how much billing type 3 carries, which sizes the mid-cycle effect.
--       c. whether any OTHER type exists that carries real value, in which case
--          obligation_6m is still incomplete.
--     Note what this already fixed: a cost guard of MOD(day_key,100) >= 28 was
--     in the extract while only type 2 was read. It was valid then and FATAL
--     once type 3 matters, because a mid-cycle bill does not land on the month
--     end. It has been removed.
-- ---------------------------------------------------------------------------
SELECT  cust_bil_typ_id,
        COUNT(*)                                        AS n_rows,
        COUNT(DISTINCT sbrp_id)                         AS n_subs,
        COUNT(DISTINCT day_key)                         AS n_distinct_days,
        MIN(MOD(day_key, 100))                          AS day_min,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.5)       AS day_p50,
        MAX(MOD(day_key, 100))                          AS day_max,
        COUNT(*) FILTER (WHERE payment_due_amt > 0)     AS n_due_pos,
        APPROX_PERCENTILE(payment_due_amt, 0.5)
            FILTER (WHERE payment_due_amt > 0)          AS due_p50,
        SUM(COALESCE(payment_due_amt,0))                AS due_total
FROM    dwbi_fact_db.v_fact_cust_bil_daily
WHERE   day_key BETWEEN 14040101 AND 14040431
GROUP BY cust_bil_typ_id
ORDER BY n_rows DESC;


-- ---------------------------------------------------------------------------
-- P2  cust_pmnt_typ_id and bllg_pmnt_stat_id, with NO assumption about either.
--     Needed because the extract still filters bllg_pmnt_stat_id = 2 for
--     "successful", which is itself carried over unverified. If another status
--     holds a large share of value, that filter is deleting real payments.
-- ---------------------------------------------------------------------------
SELECT  cust_pmnt_typ_id,
        bllg_pmnt_stat_id,
        COUNT(*)                                        AS n_payments,
        COUNT(DISTINCT sbrp_id)                         AS n_subs,
        SUM(COALESCE(pmnt_amt,0))                       AS total_amt,
        APPROX_PERCENTILE(pmnt_amt, 0.5)                AS amt_p50,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.10)      AS pay_day_p10,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.50)      AS pay_day_p50,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.90)      AS pay_day_p90
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14040101 AND 14040431
GROUP BY cust_pmnt_typ_id, bllg_pmnt_stat_id
ORDER BY n_payments DESC;


-- ---------------------------------------------------------------------------
-- P3  does dropping the typ filter change the totals. If the numbers here are
--     far above what the old IN (4, 6) filter produced, that filter was
--     deleting real payments and proven_capacity was understated.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                        AS n_all,
        SUM(COALESCE(pmnt_amt,0))                       AS amt_all,
        COUNT(*) FILTER (WHERE cust_pmnt_typ_id IN (4, 6))          AS n_typ_4_6,
        SUM(COALESCE(pmnt_amt,0)) FILTER (WHERE cust_pmnt_typ_id IN (4, 6))
                                                        AS amt_typ_4_6,
        COUNT(*) FILTER (WHERE bllg_pmnt_stat_id = 2)   AS n_stat_2,
        SUM(COALESCE(pmnt_amt,0)) FILTER (WHERE bllg_pmnt_stat_id = 2)
                                                        AS amt_stat_2
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14040101 AND 14040431;


-- ---------------------------------------------------------------------------
-- P4  is v_fact_pmnt_adjmt whole across the new feature window 140311..140404.
--     Every payment feature now comes from here, so a gap would be fatal -
--     and the monthly fact's pmnt_amt IS holed in 140402 and 140403.
-- ---------------------------------------------------------------------------
SELECT  day_key / 100                                   AS month_key,
        COUNT(*)                                        AS n_payments,
        COUNT(DISTINCT sbrp_id)                         AS n_subs,
        SUM(COALESCE(pmnt_amt,0))                       AS total_amt
FROM    dwbi_fact_db.v_fact_pmnt_adjmt
WHERE   day_key BETWEEN 14030101 AND 14050631
GROUP BY day_key / 100
ORDER BY 1;

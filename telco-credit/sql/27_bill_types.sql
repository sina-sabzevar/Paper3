-- ============================================================================
--  WHICH BILL TYPES ACTUALLY EXIST                         (Trino/Presto)
--
--  mc_billed_6m came back entirely NULL. Two separate problems, and only one
--  of them is fixed.
--
--  FIXED: SUM(x) FILTER (WHERE ...) returns NULL when no row matches, and I had
--  written SUM(ec_amt + mc_amt), so one absent bill type NULLed five columns -
--  obligation_6m, med_obligation, midcycle_billed_share, paid_to_obligation,
--  arrears_paydown_6m. Those are now guarded and a has_midcycle_billing flag
--  records whether the zero is real or just missing data.
--
--  NOT FIXED, AND THIS QUERY SETTLES IT: whether cust_bil_typ_id = 3 exists at
--  all. If it has no rows then mid-cycle billing is NOT AVAILABLE from this
--  source, and since you called mid-cycle behaviour a sensitive and important
--  feature, that is worth knowing plainly rather than shipping columns of zeros
--  that read as "this subscriber never paid mid-cycle".
--
--  READ IT LIKE THIS
--    type 3 present with a day_p50 well below the month end  -> mid-cycle, use it
--    type 3 absent                                           -> the feature does
--        not exist here; drop mc_billed_6m and midcycle_billed_share from X
--    another type with volume and a mid-month day profile     -> that is the one,
--        tell me its number and I will switch to it
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
SELECT  cust_bil_typ_id,
        COUNT(*)                                        AS n_rows,
        COUNT(DISTINCT sbrp_id)                         AS n_subs,
        COUNT(DISTINCT day_key)                         AS n_days,
        MIN(MOD(day_key, 100))                          AS day_min,
        APPROX_PERCENTILE(MOD(day_key, 100), 0.5)       AS day_p50,
        MAX(MOD(day_key, 100))                          AS day_max,
        COUNT(*) FILTER (WHERE payment_due_amt > 0)     AS n_amt_pos,
        COALESCE(APPROX_PERCENTILE(payment_due_amt, 0.5)
                 FILTER (WHERE payment_due_amt > 0), 0) AS amt_p50,
        COALESCE(SUM(payment_due_amt), 0)               AS amt_total
FROM    dwbi_fact_db.v_fact_cust_bil_daily
WHERE   day_key BETWEEN 14050101 AND 14050631
GROUP BY cust_bil_typ_id
ORDER BY n_rows DESC;

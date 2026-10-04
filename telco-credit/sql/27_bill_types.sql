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
--  TWO 47 AND 48 DIGIT VALUES WERE OFFERED AS THE REAL TYPE CODES. They are
--  not substituted, and here is why, checked rather than asserted:
--
--      BIGINT holds 19 digits. Trino's DECIMAL holds 38. The values are 47
--      and 48 digits, so neither fits a numeric cust_bil_typ_id at all.
--      47 is prime, so the shorter one cannot even split into equal-width
--      ids, while the longer one could split four ways - two values that
--      should share a shape do not, which points at a copy that lost
--      characters rather than at two codes.
--
--  T0 below reports the column's declared type. If it is VARCHAR then long
--  string codes are possible after all and the GROUP BY will print them
--  verbatim. If it is numeric, those two values cannot be what the column
--  holds and the real codes are whatever T1 lists.
--
--  Either way the answer comes from the data in one run. Nothing downstream
--  is changed until it does.
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

-- ---------------------------------------------------------------------------
-- T0  What type the column actually is, and what the bill table holds.
--     Run this first - it decides whether a 47 digit code is even possible.
-- ---------------------------------------------------------------------------
SELECT   column_name,
         data_type,
         is_nullable
FROM     dwbi_fact_db.information_schema.columns
WHERE    table_name = 'v_fact_cust_bil_daily'
ORDER BY ordinal_position;

-- ---------------------------------------------------------------------------
-- T1  Every bill type present, with its day profile and its amounts.
--     CAST to VARCHAR so the value prints in full whatever its declared
--     type is - a wide numeric would otherwise come back in exponent form
--     and the digits that matter would be the ones lost.
-- ---------------------------------------------------------------------------
SELECT  CAST(cust_bil_typ_id AS VARCHAR)                AS bil_typ_id_text,
        LENGTH(CAST(cust_bil_typ_id AS VARCHAR))        AS id_digits,
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

-- ---------------------------------------------------------------------------
-- T2  The same thing one level up: if cust_bil_typ_id turns out to be a
--     surrogate key rather than a readable code, the dimension table carries
--     its description. This finds the dimension if one exists.
-- ---------------------------------------------------------------------------
SELECT   table_name
FROM     dwbi_fact_db.information_schema.tables
WHERE    regexp_like(LOWER(table_name), 'bil_typ|bill_typ|dim_bil')
ORDER BY table_name;

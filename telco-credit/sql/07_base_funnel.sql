-- ============================================================================
--  Why does dcb3_base return one row? Run R0 first, then the funnel.
--  All single statements. No percent character, no CASE.
-- ============================================================================


-- ===========================================================================
-- R0.  RETENTION. What periods actually exist? Run this before anything else.
--      If the monthly fact stops at, say, 140410, then a cohort at 140405 has
--      no feature window and the whole calendar has to move forward.
-- ===========================================================================
SELECT MIN(month_key) AS first_month, MAX(month_key) AS last_month,
       COUNT(DISTINCT month_key) AS n_months
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip;

-- and for the daily fact, which is usually pruned harder
SELECT MIN(day_key) AS first_day, MAX(day_key) AS last_day,
       COUNT(DISTINCT day_key / 100) AS n_months
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip;


-- ===========================================================================
-- THE FUNNEL. Each query adds ONE condition. The first big drop is the cause.
-- Replace 140404 with a month R0 shows you actually have.
-- ===========================================================================

-- B1. rows in the base month
SELECT COUNT(*) AS n FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE month_key = 140404;

-- B2. + permanent
SELECT COUNT(*) AS n FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE month_key = 140404 AND sbrp_typ_id = 1;

-- B3. + active
SELECT COUNT(*) AS n FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE month_key = 140404 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2;

-- B4. + at least a year on net.  If this one collapses, age_on_net_months is
--     probably NULL for most rows rather than small.
SELECT COUNT(*)                            AS n,
       COUNT(age_on_net_months)            AS n_age_not_null,
       APPROX_PERCENTILE(age_on_net_months, ARRAY[0.1,0.5,0.9]) AS age_pctiles
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140404 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2;

-- B5. the median-invoice side on its own.  Your original queries always wrote
--     "where invoice_amt <> 0", so if most rows are zero the HAVING clause here
--     removes nearly everyone - this is the prime suspect.
SELECT COUNT(*) AS n_subs_with_positive_median
FROM ( SELECT sbrp_id
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140308 AND 140404
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id
       HAVING APPROX_PERCENTILE(invoice_amt, 0.5) > 0 ) b;

-- B6. how many months of invoice data each subscriber actually has, and how
--     many of those are non-zero. Tells you whether the median is a fair test.
SELECT APPROX_PERCENTILE(n_months,   ARRAY[0.1,0.5,0.9]) AS months_pctiles,
       APPROX_PERCENTILE(n_positive, ARRAY[0.1,0.5,0.9]) AS positive_pctiles
FROM ( SELECT sbrp_id,
              COUNT(*)                                 AS n_months,
              COUNT(*) FILTER (WHERE invoice_amt > 0)  AS n_positive
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140308 AND 140404
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id ) b;

-- B7. the INNER JOIN of B4 and B5 - the two halves together
SELECT COUNT(*) AS n
FROM ( SELECT sbrp_id FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
       WHERE month_key = 140404 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
         AND age_on_net_months >= 12 ) s
INNER JOIN
     ( SELECT sbrp_id
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140308 AND 140404
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id
       HAVING APPROX_PERCENTILE(invoice_amt, 0.5) > 0 ) m
  ON m.sbrp_id = s.sbrp_id;

-- B8. how many the two exclusion gates remove
SELECT COUNT(DISTINCT sbrp_id) AS n_churned
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14030801 AND 14040431
  AND  sbrp_typ_id = 1 AND sbrp_stat_id IN (4, 8);

SELECT COUNT(DISTINCT sbrp_id) AS n_barred_near_t0
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14040301 AND 14040431
  AND  sbrp_typ_id = 1 AND sbrp_stat_id IN (3, 9);

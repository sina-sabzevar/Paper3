-- ============================================================================
--  WHICH MONTHS ACTUALLY EXIST, AND HOW BIG IS EACH        (Trino/Presto)
--
--  This is the one query the whole calendar should have been built on. Every
--  window in the pipeline - feature months, T0, the four bill months, the
--  watch tail - is decided by the answer, and up to now it rested on an
--  inference rather than a measurement.
--
--  Two cheap GROUP BYs, one per table. Send both result sets in full.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- M1  the MONTHLY fact, which every feature and the revenue gate read from.
SELECT  month_key,
        COUNT(*)                                            AS n_rows,
        COUNT(DISTINCT sbrp_id)                             AS n_subs,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE sbrp_typ_id = 1)
                                                            AS n_permanent,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE sbrp_typ_id = 1
                                          AND sbrp_stat_id = 2)
                                                            AS n_perm_active,
        COUNT(*) FILTER (WHERE invoice_amt > 0)             AS n_invoice_pos
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140301 AND 140507
GROUP BY month_key
ORDER BY month_key;


-- M2  the DAILY fact, which the label and every bar or DPD feature read from.
--     Rolled up to month so the output stays short.
SELECT  day_key / 100                                       AS month_key,
        COUNT(*)                                            AS n_rows,
        COUNT(DISTINCT sbrp_id)                             AS n_subs,
        MIN(day_key)                                        AS first_day,
        MAX(day_key)                                        AS last_day,
        COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)    AS n_bill_pos
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14030101 AND 14050731
  AND   sbrp_typ_id = 1
GROUP BY day_key / 100
ORDER BY 1;

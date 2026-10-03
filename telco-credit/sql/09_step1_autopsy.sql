-- ============================================================================
--  WHY DOES STEP 1 RETURN 1371 ROWS                            (Trino/Presto)
--
--  STEP 1 is an INNER JOIN of three independent subqueries plus two anti-joins.
--  Any ONE of them can collapse the result, and 21M -> 639 -> 1371 says the
--  one I blamed before was not the culprit. So: measure each gate ALONE.
--
--  Run F1..F5 one at a time and send every number. Do not skip any - the point
--  is to see which single gate drops the count by orders of magnitude.
--
--  NO percent character anywhere. NO CASE expressions. AMOUNTS AS STORED.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- F1  THE SNAPSHOT GATE, ALONE. One month, so this is cheap.
--     Expect: n_all large, perm near 36M, perm_active somewhat less,
--     and tenure taking a modest bite. If perm_active is already tiny, the
--     problem is month_key 140406 not existing or the status codes.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                                  AS n_all,
        COUNT(DISTINCT sbrp_id)                                   AS n_subs,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1)                   AS f_perm,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND sbrp_stat_id = 2)                  AS f_perm_active,
        COUNT(*) FILTER (WHERE sbrp_typ_id = 1
                           AND sbrp_stat_id = 2
                           AND age_on_net_months >= 12)           AS f_perm_act_ten,
        APPROX_PERCENTILE(age_on_net_months, 0.5)                 AS tenure_p50
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140406;


-- ---------------------------------------------------------------------------
-- F2  WHICH MONTHS ACTUALLY EXIST in the monthly table. If 140406 is missing
--     or thin, F1 explains everything by itself.
-- ---------------------------------------------------------------------------
SELECT  month_key, COUNT(*) AS n_rows, COUNT(DISTINCT sbrp_id) AS n_subs
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140401 AND 140506
GROUP BY month_key
ORDER BY month_key;


-- ---------------------------------------------------------------------------
-- F3  invoice_amt COVERAGE. The med_invoice subquery ends in
--       HAVING APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) > 0
--     which silently deletes every subscriber whose invoice_amt is never
--     positive in the window. We have NEVER measured this column. If
--     inv_positive is small, this is the killer.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                                  AS n_rows,
        COUNT(DISTINCT sbrp_id)                                   AS n_subs,
        COUNT(invoice_amt)                                        AS inv_not_null,
        COUNT(*) FILTER (WHERE invoice_amt > 0)                   AS inv_positive,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE invoice_amt > 0)    AS subs_with_inv,
        APPROX_PERCENTILE(invoice_amt, 0.5)
            FILTER (WHERE invoice_amt > 0)                        AS inv_p50,
        MAX(invoice_amt)                                          AS inv_max
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140401 AND 140406
  AND   sbrp_typ_id = 1;


-- ---------------------------------------------------------------------------
-- F4  THE REVENUE FLOOR, with the exact expression STEP 1 uses, and the
--     distribution around it. Two things to learn:
--       a. how many survive rev_3m/3 > 1000000
--       b. whether 1000000 is the right number at all, or whether these
--          columns are not in Rial. The thresholds below span four orders of
--          magnitude on purpose - whichever one lands near a few million
--          subscribers tells us the unit.
--     Network ARPU is 130k Toman = 1,300,000 Rial, so if the amounts are in
--     Rial then rev_p50 should land somewhere near 1,000,000.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                          AS n_subs,
        COUNT(*) FILTER (WHERE rev_3m > 0)                AS rev_positive,
        COUNT(*) FILTER (WHERE rev_3m / 3 >      10000)   AS above_10k,
        COUNT(*) FILTER (WHERE rev_3m / 3 >     100000)   AS above_100k,
        COUNT(*) FILTER (WHERE rev_3m / 3 >    1000000)   AS above_1m,
        COUNT(*) FILTER (WHERE rev_3m / 3 >   10000000)   AS above_10m,
        APPROX_PERCENTILE(rev_3m / 3, 0.10)               AS rev_p10,
        APPROX_PERCENTILE(rev_3m / 3, 0.50)               AS rev_p50,
        APPROX_PERCENTILE(rev_3m / 3, 0.90)               AS rev_p90,
        MAX(rev_3m / 3)                                   AS rev_max
FROM (
    SELECT  sbrp_id,
            SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                - COALESCE(intl_roam_sms_rev,0))
          + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                - COALESCE(post_intl_roam_data_rev,0)
                - COALESCE(pre_intl_roam_data_rev,0))     AS rev_3m
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140404 AND 140406
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
) r;


-- ---------------------------------------------------------------------------
-- F5  THE TWO ANTI-JOINS. How many subscribers do they each remove.
--     If churn_hits is enormous, the churn gate over the whole feature window
--     is too wide and has to move to a point-in-time test like the bar gate.
-- ---------------------------------------------------------------------------
SELECT  COUNT(DISTINCT sbrp_id) FILTER (WHERE sbrp_stat_id IN (4, 8)
                                          AND day_key BETWEEN 14040101
                                                          AND 14040631) AS churn_hits,
        COUNT(DISTINCT sbrp_id) FILTER (WHERE sbrp_stat_id IN (3, 9)
                                          AND day_key BETWEEN 14040625
                                                          AND 14040631) AS barred_hits
FROM    dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE   day_key BETWEEN 14040101 AND 14040631
  AND   sbrp_typ_id = 1;

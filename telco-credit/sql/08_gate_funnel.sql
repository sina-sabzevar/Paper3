-- ============================================================================
--  Which gate collapsed the base from 21M to 639?
--  Each query adds ONE condition to the previous. Single month, so all fast.
--  No percent character, no CASE.
-- ============================================================================

-- G0. active + permanent + tenure, at T0's month. This was ~21M.
SELECT COUNT(*) AS n
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
  AND  age_on_net_months >= 12;


-- G1. + no open bill at T0.   PRIME SUSPECT.
--     Also reports how many have a positive balance, so the share is visible
--     rather than inferred.
SELECT COUNT(*)                                            AS n_total,
       COUNT(*) FILTER (WHERE COALESCE(bill_outstanding_amt,0) = 0) AS n_zero_balance,
       COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)    AS n_positive,
       COUNT(bill_outstanding_amt)                         AS n_not_null
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
  AND  age_on_net_months >= 12;


-- G2. the revenue floor on its own, with the distribution behind it.
--     If the 10th percentile already exceeds the threshold, the floor is not
--     the problem; if the 90th is below it, the threshold is wrong for 1405
--     and inflation has moved the base.
SELECT COUNT(*)                                        AS n_subs,
       COUNT(*) FILTER (WHERE rev_3m / 3 > 1000000)    AS n_above_floor,
       APPROX_PERCENTILE(rev_3m / 3, ARRAY[0.1,0.25,0.5,0.75,0.9]) AS monthly_rev_pctiles
FROM ( SELECT sbrp_id,
              SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                  - COALESCE(intl_roam_voi_rev,0)) / 1.1
            + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                  - COALESCE(intl_roam_sms_rev,0))
            + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                  - COALESCE(post_intl_roam_data_rev,0)
                  - COALESCE(pre_intl_roam_data_rev,0))  AS rev_3m
       FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
       WHERE  month_key BETWEEN 140404 AND 140406
         AND  sbrp_typ_id = 1
       GROUP BY sbrp_id ) r;


-- G3. the median-invoice side on its own. Checks both that the FILTER form
--     behaves and how many subscribers carry any positive invoice at all.
SELECT COUNT(*)                                      AS n_subs,
       COUNT(*) FILTER (WHERE med_invoice > 0)       AS n_positive_median,
       COUNT(*) FILTER (WHERE n_positive_months = 0) AS n_never_invoiced,
       APPROX_PERCENTILE(n_positive_months, ARRAY[0.1,0.5,0.9]) AS positive_month_pctiles
FROM ( SELECT sbrp_id,
              APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) AS med_invoice,
              COUNT(*) FILTER (WHERE invoice_amt > 0) AS n_positive_months
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140401 AND 140406
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id ) b;


-- G4. G0 and the revenue floor together, without the other two
SELECT COUNT(*) AS n
FROM ( SELECT sbrp_id FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
       WHERE month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
         AND age_on_net_months >= 12 ) s
INNER JOIN
     ( SELECT sbrp_id
       FROM ( SELECT sbrp_id,
                     SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                         - COALESCE(intl_roam_voi_rev,0)) / 1.1
                   + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                         - COALESCE(intl_roam_sms_rev,0))
                   + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                         - COALESCE(post_intl_roam_data_rev,0)
                         - COALESCE(pre_intl_roam_data_rev,0)) AS rev_3m
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140404 AND 140406
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id ) r
       WHERE r.rev_3m / 3 > 1000000 ) rev  ON rev.sbrp_id = s.sbrp_id;


-- G5. G4 plus the median-invoice join
SELECT COUNT(*) AS n
FROM ( SELECT sbrp_id FROM dwbi_fact_db.v_fact_sbrp_mthly_cip
       WHERE month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
         AND age_on_net_months >= 12 ) s
INNER JOIN
     ( SELECT sbrp_id
       FROM ( SELECT sbrp_id,
                     SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                         - COALESCE(intl_roam_voi_rev,0)) / 1.1
                   + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                         - COALESCE(intl_roam_sms_rev,0))
                   + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                         - COALESCE(post_intl_roam_data_rev,0)
                         - COALESCE(pre_intl_roam_data_rev,0)) AS rev_3m
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140404 AND 140406
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id ) r
       WHERE r.rev_3m / 3 > 1000000 ) rev  ON rev.sbrp_id = s.sbrp_id
INNER JOIN
     ( SELECT sbrp_id
       FROM ( SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140401 AND 140406
                AND  sbrp_typ_id = 1
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id
       HAVING APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) > 0 ) m
  ON m.sbrp_id = s.sbrp_id;


-- G6. how many the two exclusion gates would remove
SELECT COUNT(DISTINCT sbrp_id) AS n_churned
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14040101 AND 14040631
  AND  sbrp_typ_id = 1 AND sbrp_stat_id IN (4, 8);

SELECT COUNT(DISTINCT sbrp_id) AS n_barred_near_t0
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14040501 AND 14040631
  AND  sbrp_typ_id = 1 AND sbrp_stat_id IN (3, 9);

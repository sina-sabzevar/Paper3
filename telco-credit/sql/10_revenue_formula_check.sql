-- ============================================================================
--  IS THE REVENUE FORMULA THE THING KILLING STEP 1?        (Trino/Presto)
--
--  History: base was 21M before the revenue gate was added, and about 1400
--  after. The threshold cannot explain that - 1,000,000 Rial is 100k Toman,
--  below the 130k Toman network ARPU, so it should keep a large share. So the
--  suspect is the EXPRESSION, not the number: one of the columns being
--  subtracted is probably not what I assumed, and drives the total negative.
--
--  ONE statement. ONE month, so it is cheap. Every component measured on its
--  own, then the composite. Send the whole row.
--
--  READ IT LIKE THIS
--    If voi_p50, sms_p50 and data_p50 look like sane monthly amounts but
--    composite_p50 is negative or near zero, the subtractions are the bug.
--    If a tax_p50 or roam_p50 is as large as the revenue it is subtracted
--    from, that column is the one.
--    pass_1m is how many clear the current floor on one month.
--
--  NO percent character anywhere. NO CASE expressions. AMOUNTS AS STORED.
-- ============================================================================
SELECT  COUNT(*)                                            AS n_rows,
        COUNT(DISTINCT sbrp_id)                             AS n_subs,

        -- the three positive blocks, before any subtraction
        APPROX_PERCENTILE(COALESCE(voi_pkg_rev,0)
                        + COALESCE(voi_payg_rev,0), 0.5)    AS voi_p50,
        APPROX_PERCENTILE(COALESCE(tot_sms_rev,0),  0.5)     AS sms_p50,
        APPROX_PERCENTILE(COALESCE(tot_data_rev,0), 0.5)     AS data_p50,

        -- the things being subtracted. Any of these as big as the block above
        -- it is the bug.
        APPROX_PERCENTILE(COALESCE(intl_roam_voi_rev,0), 0.5)     AS roam_voi_p50,
        APPROX_PERCENTILE(COALESCE(tot_sms_tax,0), 0.5)           AS sms_tax_p50,
        APPROX_PERCENTILE(COALESCE(intl_roam_sms_rev,0), 0.5)     AS roam_sms_p50,
        APPROX_PERCENTILE(COALESCE(tot_data_tax,0), 0.5)          AS data_tax_p50,
        APPROX_PERCENTILE(COALESCE(post_intl_roam_data_rev,0), 0.5) AS roam_dpost_p50,
        APPROX_PERCENTILE(COALESCE(pre_intl_roam_data_rev,0), 0.5)  AS roam_dpre_p50,

        -- the maxima of the subtracted columns, to catch a wrong scale
        MAX(COALESCE(tot_sms_tax,0))                        AS sms_tax_max,
        MAX(COALESCE(tot_data_tax,0))                       AS data_tax_max,
        MAX(COALESCE(intl_roam_voi_rev,0))                  AS roam_voi_max,

        -- the composite, exactly as STEP 1 computes it for one month
        APPROX_PERCENTILE(
            (COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
             - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + (COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
             - COALESCE(intl_roam_sms_rev,0))
          + (COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
             - COALESCE(post_intl_roam_data_rev,0)
             - COALESCE(pre_intl_roam_data_rev,0)), 0.5)    AS composite_p50,
        APPROX_PERCENTILE(
            (COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
             - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + (COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
             - COALESCE(intl_roam_sms_rev,0))
          + (COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
             - COALESCE(post_intl_roam_data_rev,0)
             - COALESCE(pre_intl_roam_data_rev,0)), 0.9)    AS composite_p90,

        -- how many clear the floor on ONE month
        COUNT(*) FILTER (WHERE
            (COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
             - COALESCE(intl_roam_voi_rev,0)) / 1.1
          + (COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
             - COALESCE(intl_roam_sms_rev,0))
          + (COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
             - COALESCE(post_intl_roam_data_rev,0)
             - COALESCE(pre_intl_roam_data_rev,0)) > 1000000)  AS pass_1m,

        -- and how many clear it on the raw blocks with NO subtraction at all,
        -- which is the control: if this is large and pass_1m is tiny, the
        -- subtractions are proven to be the problem.
        COUNT(*) FILTER (WHERE COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                             + COALESCE(tot_sms_rev,0) + COALESCE(tot_data_rev,0)
                               > 1000000)                   AS pass_raw
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140406
  AND   sbrp_typ_id = 1;

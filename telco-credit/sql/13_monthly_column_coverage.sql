-- ============================================================================
--  WHICH MONTHLY COLUMNS ARE LOADED IN WHICH MONTHS        (Trino/Presto)
--
--  M1 found that invoice_amt is loaded in only 14 of the 30 closed months:
--      140301..140304, 140306, 140311, and 140410..140505.
--  In 140402..140409 it is literally zero. The old feature window sat right in
--  that hole, which is why the base collapsed to about 1400 rows - the
--  med_invoice HAVING deleted everyone.
--
--  Before any calendar is chosen, the SAME question has to be answered for
--  every other monthly column the pipeline reads. If payments and revenue have
--  the same hole, the usable windows shrink again.
--
--  ONE statement. Same shape as M1. Send the whole result.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
SELECT  month_key,
        COUNT(*)                                          AS n_perm_rows,
        COUNT(*) FILTER (WHERE sbrp_stat_id = 2)          AS n_perm_active,

        -- payments. Candidate replacement yardstick for the materiality floor
        -- if invoice_amt stays unusable.
        COUNT(*) FILTER (WHERE pmnt_amt > 0)              AS pmnt_pos,

        -- the revenue blocks the base gate is built from
        COUNT(*) FILTER (WHERE voi_pkg_rev  > 0)          AS voi_pkg_pos,
        COUNT(*) FILTER (WHERE voi_payg_rev > 0)          AS voi_payg_pos,
        COUNT(*) FILTER (WHERE tot_sms_rev  > 0)          AS sms_pos,
        COUNT(*) FILTER (WHERE tot_data_rev > 0)          AS data_rev_pos,

        -- usage, for the behavioural features
        COUNT(*) FILTER (WHERE data_usg_actl_vol > 0)     AS data_vol_pos,
        COUNT(*) FILTER (WHERE mo_cl_actl_dur    > 0)     AS voice_dur_pos,
        COUNT(*) FILTER (WHERE mo_cl_cnt         > 0)     AS call_cnt_pos,

        -- the monthly balance column, for completeness
        COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)  AS bill_pos,

        -- typical levels in the months that ARE loaded, so the materiality
        -- floor can be re-anchored on whichever column survives
        APPROX_PERCENTILE(pmnt_amt, 0.5) FILTER (WHERE pmnt_amt > 0)
                                                          AS pmnt_p50,
        APPROX_PERCENTILE(tot_data_rev, 0.5) FILTER (WHERE tot_data_rev > 0)
                                                          AS data_rev_p50
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140301 AND 140506
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;

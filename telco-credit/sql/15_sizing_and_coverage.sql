-- ============================================================================
--  THE LAST TWO UNKNOWNS, IN ONE FILE                      (Trino/Presto)
--
--  S1 decides the CALENDAR. The monthly fact's BILLING columns are empty
--     across 140312..140409. The bill itself no longer comes from there, but
--     the revenue gate, the payment features and the usage features still do,
--     and their coverage has never been measured. If they share the gap, the
--     shock-free cohort C1 (T0 140405, features 140311..140404) is not
--     available and the windows have to move into 1405.
--
--  S2 decides the PRODUCT. The end-of-cycle bill has a median of about 47,000
--     Toman and a p90 of about 179,000. The minimum ticket of 400,000 Toman
--     over four instalments is 100,000 Toman a month - 2.1x the median
--     subscriber's ENTIRE monthly bill. S2 gives the distribution needed to
--     size how many subscribers can actually carry that, instead of arguing
--     from two percentiles.
--
--  NO percent character anywhere. NO CASE expressions. AMOUNTS IN RIAL.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S1  monthly column coverage per month. Same shape as M1.
--     What matters: are pmnt_pos and the revenue columns healthy in
--     140311..140404, or do they collapse the way payable_amt did?
-- ---------------------------------------------------------------------------
SELECT  month_key,
        COUNT(*)                                          AS n_perm_rows,
        COUNT(*) FILTER (WHERE sbrp_stat_id = 2)          AS n_perm_active,
        COUNT(*) FILTER (WHERE pmnt_amt > 0)              AS pmnt_pos,
        COUNT(*) FILTER (WHERE voi_pkg_rev  > 0)          AS voi_pkg_pos,
        COUNT(*) FILTER (WHERE voi_payg_rev > 0)          AS voi_payg_pos,
        COUNT(*) FILTER (WHERE tot_sms_rev  > 0)          AS sms_pos,
        COUNT(*) FILTER (WHERE tot_data_rev > 0)          AS data_rev_pos,
        COUNT(*) FILTER (WHERE data_usg_actl_vol > 0)     AS data_vol_pos,
        COUNT(*) FILTER (WHERE mo_cl_actl_dur    > 0)     AS voice_dur_pos,
        APPROX_PERCENTILE(pmnt_amt, 0.5) FILTER (WHERE pmnt_amt > 0)
                                                          AS pmnt_p50
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140301 AND 140506
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;


-- ---------------------------------------------------------------------------
-- S2  how many subscribers can carry an instalment, by ticket size.
--
--     avg_bill_3m is the mean end-of-cycle bill over the last three closed
--     months, which is the closest thing to a payment-capacity measure that
--     needs no extra assumption. The thresholds are expressed as the BILL a
--     subscriber must have for the instalment to stay inside a given share of
--     it, at the 400,000 Toman minimum ticket (100,000 Toman a month):
--
--       bill >= 3,333,333 Rial  ->  instalment is 30 pct of the bill
--       bill >= 2,500,000 Rial  ->  40 pct
--       bill >= 2,000,000 Rial  ->  50 pct
--       bill >= 1,428,571 Rial  ->  70 pct
--       bill >= 1,000,000 Rial  ->  100 pct of the bill, i.e. it doubles
--
--     Gated to active permanent subscribers at 140506 so the count means
--     something as a book size.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                          AS n_subs,
        APPROX_PERCENTILE(avg_bill_3m, 0.50)              AS p50,
        APPROX_PERCENTILE(avg_bill_3m, 0.75)              AS p75,
        APPROX_PERCENTILE(avg_bill_3m, 0.90)              AS p90,
        APPROX_PERCENTILE(avg_bill_3m, 0.95)              AS p95,
        APPROX_PERCENTILE(avg_bill_3m, 0.99)              AS p99,
        COUNT(*) FILTER (WHERE avg_bill_3m >= 1000000)    AS n_inst_100pct,
        COUNT(*) FILTER (WHERE avg_bill_3m >= 1428571)    AS n_inst_70pct,
        COUNT(*) FILTER (WHERE avg_bill_3m >= 2000000)    AS n_inst_50pct,
        COUNT(*) FILTER (WHERE avg_bill_3m >= 2500000)    AS n_inst_40pct,
        COUNT(*) FILTER (WHERE avg_bill_3m >= 3333333)    AS n_inst_30pct,
        SUM(avg_bill_3m)                                  AS total_monthly_billing
FROM (
    SELECT  c.sbrp_id,
            AVG(c.payment_due_amt) AS avg_bill_3m
    FROM        dwbi_fact_db.v_fact_cust_bil_daily c
    INNER JOIN (
        SELECT sbrp_id
        FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
        WHERE  month_key    = 140506
          AND  sbrp_stat_id = 2
          AND  sbrp_typ_id  = 1
    ) a ON a.sbrp_id = c.sbrp_id
    WHERE   c.day_key BETWEEN 14050401 AND 14050631
      AND   c.cust_bil_typ_id = 2
      AND   MOD(c.day_key, 100) >= 28
      AND   c.payment_due_amt > 0
    GROUP BY c.sbrp_id
) t;

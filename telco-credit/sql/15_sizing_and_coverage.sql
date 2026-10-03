-- ============================================================================
--  THE LAST TWO UNKNOWNS, IN ONE FILE                      (Trino/Presto)
--
--  S1 decides the CALENDAR.
--  S2 decides the PRODUCT.
--  S3 measures how much mid-cycle payment there actually is.
--
--  CORRECTION THAT MADE S2 NECESSARY. payment_due_amt is the END-OF-CYCLE bill
--  ONLY: cash payments and mid-cycle payments do NOT appear in it. So it is the
--  RESIDUAL after a subscriber has already paid part of the month, not their
--  monthly spend. Sizing the loan against it understates capacity, and badly,
--  because mid-cycle payment is common in this base.
--
--  Capacity has to come from TOTAL payments - v_fact_pmnt_adjmt with
--  cust_pmnt_typ_id IN (4, 6), end-of-cycle AND mid-cycle. That is what STEP 6
--  of the extract already uses for proven_capacity.
--
--  NOTE this does NOT change the materiality threshold in the label. There,
--  0.40 x med_bill compares the daily bill_outstanding_amt against the
--  subscriber's own typical END-OF-CYCLE bill, and both sides live in the same
--  issued-bill world - bill_outstanding_amt is also zeroed by a mid-cycle
--  payment. A heavy mid-cycle payer with a typical residual of 30k and 20k left
--  unpaid past the due date has failed on two thirds of what was due, and the
--  threshold should fire. It is self-normalising, and it stays.
--
--  NO percent character anywhere. NO CASE expressions. AMOUNTS IN RIAL.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S1  monthly column coverage per month.
--     The monthly fact's BILLING columns are empty across 140312..140409. The
--     bill no longer comes from there, but the revenue gate, the payment
--     features and the usage features still do. If they share the gap, the
--     shock-free cohort C1 (T0 140405, features 140311..140404) is not
--     available and the windows must move into 1405.
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
        COUNT(*) FILTER (WHERE mo_cl_actl_dur    > 0)     AS voice_dur_pos
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140301 AND 140506
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;


-- ---------------------------------------------------------------------------
-- S2  HOW MANY SUBSCRIBERS CAN CARRY AN INSTALMENT - on TOTAL payments.
--
--     avg_paid_3m is the mean of TOTAL monthly payments, mid-cycle included,
--     over the last three closed months. This is proven capacity: money the
--     subscriber has actually handed over, not a billed figure.
--
--     The 400,000 Toman minimum ticket over four instalments is 100,000 Toman
--     a month = 1,000,000 Rial. The thresholds are the monthly payment a
--     subscriber needs for that instalment to stay inside a given share of
--     what they already pay:
--
--       paid >= 3,333,333 Rial  ->  instalment is 30 pct of what they pay
--       paid >= 2,500,000 Rial  ->  40 pct
--       paid >= 2,000,000 Rial  ->  50 pct
--       paid >= 1,428,571 Rial  ->  70 pct
--       paid >= 1,000,000 Rial  ->  100 pct, i.e. their outlay doubles
--
--     n_inst_40pct is the headline number: the prudent book size at a 400,000
--     Toman ticket. Compare it against the 3,000,000 loan target.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                          AS n_subs,
        APPROX_PERCENTILE(avg_paid_3m, 0.50)              AS paid_p50,
        APPROX_PERCENTILE(avg_paid_3m, 0.75)              AS paid_p75,
        APPROX_PERCENTILE(avg_paid_3m, 0.90)              AS paid_p90,
        APPROX_PERCENTILE(avg_paid_3m, 0.95)              AS paid_p95,
        APPROX_PERCENTILE(avg_paid_3m, 0.99)              AS paid_p99,
        COUNT(*) FILTER (WHERE avg_paid_3m >= 1000000)    AS n_inst_100pct,
        COUNT(*) FILTER (WHERE avg_paid_3m >= 1428571)    AS n_inst_70pct,
        COUNT(*) FILTER (WHERE avg_paid_3m >= 2000000)    AS n_inst_50pct,
        COUNT(*) FILTER (WHERE avg_paid_3m >= 2500000)    AS n_inst_40pct,
        COUNT(*) FILTER (WHERE avg_paid_3m >= 3333333)    AS n_inst_30pct
FROM (
    SELECT  p.sbrp_id,
            SUM(COALESCE(p.pmnt_amt,0)) / 3.0 AS avg_paid_3m
    FROM        dwbi_fact_db.v_fact_pmnt_adjmt p
    INNER JOIN (
        SELECT sbrp_id
        FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
        WHERE  month_key    = 140506
          AND  sbrp_stat_id = 2
          AND  sbrp_typ_id  = 1
    ) a ON a.sbrp_id = p.sbrp_id
    WHERE   p.day_key BETWEEN 14050401 AND 14050631
      AND   p.cust_pmnt_typ_id IN (4, 6)
      AND   p.bllg_pmnt_stat_id = 2
    GROUP BY p.sbrp_id
) t;


-- ---------------------------------------------------------------------------
-- S3  HOW BIG IS THE MID-CYCLE EFFECT.
--
--     This is the number that says how wrong it was to size the product on the
--     end-of-cycle bill, and it is also a real feature: you flagged mid-cycle
--     behaviour as sensitive and important, and now that billed and tot_rev are
--     both stamped on month M they are finally comparable inside a row.
--
--     midcycle_share = mid-cycle payments / total payments.
--     bill_to_paid   = end-of-cycle bill / total payments. The further below 1
--                      this sits, the more of the month was settled early.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                             AS n_subs,
        APPROX_PERCENTILE(midcycle_share, 0.50)              AS mc_share_p50,
        APPROX_PERCENTILE(midcycle_share, 0.90)              AS mc_share_p90,
        COUNT(*) FILTER (WHERE midcycle_share > 0.5)         AS n_mostly_midcycle,
        COUNT(*) FILTER (WHERE n_mc > 0)                     AS n_any_midcycle,
        APPROX_PERCENTILE(paid_total, 0.5)                   AS paid_p50,
        APPROX_PERCENTILE(bill_total, 0.5)                   AS bill_p50,
        APPROX_PERCENTILE(bill_to_paid, 0.5)                 AS bill_to_paid_p50
FROM (
    SELECT  pay.sbrp_id,
            pay.paid_total,
            pay.paid_mc / NULLIF(pay.paid_total, 0)  AS midcycle_share,
            pay.n_mc,
            bil.bill_total,
            bil.bill_total / NULLIF(pay.paid_total, 0) AS bill_to_paid
    FROM (
        SELECT  p.sbrp_id,
                SUM(COALESCE(p.pmnt_amt,0))                         AS paid_total,
                SUM(COALESCE(p.pmnt_amt,0)) FILTER (WHERE p.cust_pmnt_typ_id = 6)
                                                                    AS paid_mc,
                COUNT(*) FILTER (WHERE p.cust_pmnt_typ_id = 6)      AS n_mc
        FROM    dwbi_fact_db.v_fact_pmnt_adjmt p
        WHERE   p.day_key BETWEEN 14050401 AND 14050631
          AND   p.cust_pmnt_typ_id IN (4, 6)
          AND   p.bllg_pmnt_stat_id = 2
        GROUP BY p.sbrp_id
    ) pay
    INNER JOIN (
        SELECT  c.sbrp_id, SUM(COALESCE(c.payment_due_amt,0)) AS bill_total
        FROM    dwbi_fact_db.v_fact_cust_bil_daily c
        WHERE   c.day_key BETWEEN 14050401 AND 14050631
          AND   c.cust_bil_typ_id = 2
          AND   MOD(c.day_key, 100) >= 28
        GROUP BY c.sbrp_id
    ) bil ON bil.sbrp_id = pay.sbrp_id
    WHERE   pay.paid_total > 0
) u;

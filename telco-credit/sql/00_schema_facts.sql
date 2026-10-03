-- ============================================================================
--  EVERY remaining unknown, in one run. Run top to bottom, send the output.
--  After this I write the extract once, against facts instead of assumptions.
--
--  S1-S2 are metadata and cost nothing.
--  S3-S10 each read ONE month or ONE day.
--  No percent character, no CASE.
-- ============================================================================


-- ===========================================================================
-- S1.  COLUMN LISTS. The single most useful thing - it ends the guessing about
--      what exists and what type it is.
-- ===========================================================================
SHOW COLUMNS FROM dwbi_fact_db.v_fact_sbrp_mthly_cip;
SHOW COLUMNS FROM dwbi_fact_db.v_fact_sbrp_daily_cip;
SHOW COLUMNS FROM dwbi_fact_db.v_fact_sbrp_mthly;
SHOW COLUMNS FROM dwbi_fact_db.v_fact_pmnt_adjmt;


-- ===========================================================================
-- S2.  RETENTION. Which periods exist. Usually answered from partition
--      metadata, so it should be near-instant.
-- ===========================================================================
SELECT DISTINCT month_key FROM dwbi_fact_db.v_fact_sbrp_mthly_cip ORDER BY 1;

SELECT DISTINCT day_key / 100 AS month_key
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip ORDER BY 1;


-- ===========================================================================
-- S3.  POPULATION at one month, split by type and status.
--      Fixes the base filter and confirms what stat 2, 3 and 9 are worth.
--      Replace 140406 with a month S2 shows you have.
-- ===========================================================================
SELECT sbrp_typ_id, sbrp_stat_id, COUNT(*) AS n
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140406
GROUP  BY sbrp_typ_id, sbrp_stat_id
ORDER  BY n DESC;


-- ===========================================================================
-- S4.  WHAT bill_outstanding_amt MEANS IN THE MONTHLY FACT.
--      This is the one that produced 639 rows. If n_zero is a tiny share, the
--      column is the balance at snapshot time and can never be a gate.
-- ===========================================================================
SELECT COUNT(*)                                                  AS n,
       COUNT(bill_outstanding_amt)                               AS n_not_null,
       COUNT(*) FILTER (WHERE COALESCE(bill_outstanding_amt,0) = 0) AS n_zero,
       COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)          AS n_positive,
       APPROX_PERCENTILE(bill_outstanding_amt, ARRAY[0.25,0.5,0.75,0.95]) AS pctiles
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2;


-- ===========================================================================
-- S5.  invoice_amt AND pmnt_amt. How many months each subscriber actually
--      carries a bill, and whether payments are recorded on the same table.
-- ===========================================================================
SELECT COUNT(*)                                            AS n_subs,
       APPROX_PERCENTILE(n_months,      ARRAY[0.1,0.5,0.9]) AS months_seen,
       APPROX_PERCENTILE(n_inv_positive, ARRAY[0.1,0.5,0.9]) AS months_with_invoice,
       APPROX_PERCENTILE(n_pay_positive, ARRAY[0.1,0.5,0.9]) AS months_with_payment
FROM ( SELECT sbrp_id,
              COUNT(*)                                     AS n_months,
              COUNT(*) FILTER (WHERE invoice_amt > 0)      AS n_inv_positive,
              COUNT(*) FILTER (WHERE pmnt_amt > 0)         AS n_pay_positive
       FROM ( SELECT sbrp_id, month_key,
                     MAX(COALESCE(invoice_amt,0)) AS invoice_amt,
                     MAX(COALESCE(pmnt_amt,0))    AS pmnt_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key BETWEEN 140401 AND 140406
                AND  sbrp_typ_id = 1 AND sbrp_stat_id = 2
              GROUP BY sbrp_id, month_key ) a
       GROUP BY sbrp_id ) b;


-- ===========================================================================
-- S6.  THE REVENUE FLOOR, re-measured for 1405.
--      Your original 1,000,000 Rial threshold was set on 1404 data. Inflation
--      moves the base out from under a fixed threshold, so this reports the
--      distribution and the count surviving several candidate floors.
-- ===========================================================================
SELECT COUNT(*)                                          AS n_subs,
       APPROX_PERCENTILE(rev_m, ARRAY[0.1,0.25,0.5,0.75,0.9]) AS monthly_rev_pctiles,
       COUNT(*) FILTER (WHERE rev_m >  500000)           AS above_500k,
       COUNT(*) FILTER (WHERE rev_m > 1000000)           AS above_1m,
       COUNT(*) FILTER (WHERE rev_m > 1500000)           AS above_1_5m,
       COUNT(*) FILTER (WHERE rev_m > 2000000)           AS above_2m
FROM ( SELECT sbrp_id,
              ( SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                    - COALESCE(intl_roam_voi_rev,0)) / 1.1
              + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                    - COALESCE(intl_roam_sms_rev,0))
              + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                    - COALESCE(post_intl_roam_data_rev,0)
                    - COALESCE(pre_intl_roam_data_rev,0)) ) / 3 AS rev_m
       FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
       WHERE  month_key BETWEEN 140404 AND 140406
         AND  sbrp_typ_id = 1 AND sbrp_stat_id = 2
       GROUP BY sbrp_id ) r;


-- ===========================================================================
-- S7.  age_on_net_months. Confirms the tenure gate is not silently emptying.
-- ===========================================================================
SELECT COUNT(*)                                        AS n,
       COUNT(age_on_net_months)                        AS n_not_null,
       COUNT(*) FILTER (WHERE age_on_net_months >= 12) AS n_over_12m,
       APPROX_PERCENTILE(age_on_net_months, ARRAY[0.1,0.5,0.9]) AS pctiles
FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE  month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2;


-- ===========================================================================
-- S8.  ONE DAY of the daily fact: the balance columns and the status mix.
--      Replace with a day inside a month S2 confirmed.
-- ===========================================================================
SELECT sbrp_stat_id,
       COUNT(*)                                                 AS n,
       COUNT(*) FILTER (WHERE bill_outstanding_amt > 0)         AS n_bill_positive,
       APPROX_PERCENTILE(bill_outstanding_amt, ARRAY[0.5,0.9])  AS bill_pctiles,
       APPROX_PERCENTILE(unbill_outstanding_amt, ARRAY[0.5,0.9]) AS unbill_pctiles
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key = 14040620 AND sbrp_typ_id = 1
GROUP  BY sbrp_stat_id
ORDER  BY n DESC;


-- ===========================================================================
-- S9.  ONE SUBSCRIBER ACROSS ONE MONTH. The most informative row set here:
--      it shows what the balance actually does across a billing cycle.
--      Run it for two or three different ids.
-- ===========================================================================
SELECT day_key, sbrp_stat_id, bill_outstanding_amt, unbill_outstanding_amt
FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
WHERE  day_key BETWEEN 14040601 AND 14040631
  AND  sbrp_id = ( SELECT sbrp_id
                   FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
                   WHERE  month_key = 140406 AND sbrp_typ_id = 1
                     AND  sbrp_stat_id = 2 AND bill_outstanding_amt > 0
                   LIMIT 1 )
ORDER BY day_key;


-- ===========================================================================
-- S10. DOES A PARTIAL PAYMENT CLEAR THE BALANCE?
--      Decides whether the balance measures how much is owed, or only whether
--      anything is open. If it is the latter, pay_ratio has to come from
--      invoice_amt and pmnt_amt and the DPD thresholds have to drop.
-- ===========================================================================
SELECT COUNT(*)                                    AS n_subscriber_months,
       AVG(cleared) FILTER (WHERE cov < 0.10)      AS cleared_when_paid_under_10pct,
       AVG(cleared) FILTER (WHERE cov < 0.50)      AS cleared_when_underpaid,
       AVG(cleared) FILTER (WHERE cov >= 0.90)     AS cleared_when_paid_in_full
FROM ( SELECT m.pmnt_amt / m.invoice_amt           AS cov,
              IF(e.bill_out = 0, 1.0, 0.0)         AS cleared
       FROM ( SELECT sbrp_id,
                     MAX(COALESCE(invoice_amt,0)) AS invoice_amt,
                     MAX(COALESCE(pmnt_amt,0))    AS pmnt_amt
              FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
              WHERE  month_key = 140406 AND sbrp_typ_id = 1 AND sbrp_stat_id = 2
                AND  invoice_amt > 0
              GROUP BY sbrp_id ) m
       JOIN ( SELECT sbrp_id, MAX(COALESCE(bill_outstanding_amt,0)) AS bill_out
              FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
              WHERE  day_key = 14040631 AND sbrp_typ_id = 1
              GROUP BY sbrp_id ) e  ON e.sbrp_id = m.sbrp_id ) t;

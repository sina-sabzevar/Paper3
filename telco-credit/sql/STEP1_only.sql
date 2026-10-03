-- ============================================================================
--  STEP 1 ONLY - standalone, ready to paste and run.           (Trino/Presto)
--  Extracted from 11_dcb_extract_v3.sql at commit e5f59bf.
--
--  WHAT CHANGED SINCE THE VERSION YOU LAST RAN
--    1. T0 snapshot month 140404 -> 140406. 140406 is the last month before
--       T0=140407, so this is the state visible at the decision point. The
--       old value ran the active/permanent/tenure gates three months early.
--    2. The barred gate no longer drops everyone barred in the 60 days before
--       T0. It now drops only a bar in the LAST WEEK of the feature window,
--       i.e. a subscriber still cut off going into T0. Earlier bars are kept
--       and become features - the mid-cycle ceiling population stays in, and
--       so do the bad-payment examples the model must learn from.
--
--  Expect MORE rows than the 639 and the 21M you saw before. Send COUNT(*).
--
--  NO percent character anywhere (Python drivers read it as a format spec).
--  NO CASE expressions. AMOUNTS ARE IN RIAL.
--
--  THIS RUN = cohort C1
--    feature months  140401 140402 140403 140404 140405 140406
--    T0              140407
-- ============================================================================

-- STEP 1  BASE + the median invoice the materiality floor needs
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_base;
CREATE TABLE dwbi_temp40_db.dcb3_base WITH (format='PARQUET') AS
SELECT  s.sbrp_id,
        s.age_on_net_months,
        m.med_invoice
FROM (
    SELECT  sbrp_id, age_on_net_months
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    -- 140406 is the LAST month before T0=140407, so this snapshot is the
    -- state the lender sees at the decision point. It was 140404 - three
    -- months early, left over from an older calendar. That made the active
    -- and permanent tests fire at the wrong point in time and shipped a
    -- stale age_on_net_months into the dataset.
    WHERE   month_key    = 140406      -- the month immediately before T0
      AND   sbrp_stat_id = 2           -- GATE: active at T0 (point in time only)
      AND   sbrp_typ_id  = 1           -- permanent
      AND   age_on_net_months >= 12
      -- GATE: no open bill at T0 - DISABLED by default.
      -- In the monthly fact this column appears to be the balance at snapshot
      -- time, and for an active postpaid subscriber there is almost always a
      -- bill outstanding, so requiring zero removes nearly the whole base.
      -- The "not barred in the 60 days before T0" gate below already covers
      -- the pattern this was meant to catch. Re-enable only if G1 in
      -- 08_gate_funnel.sql shows it keeps a sensible share.
      -- AND   COALESCE(bill_outstanding_amt, 0) = 0
) s
-- GATE: the economic floor from the original DCB pipeline - average revenue
-- over the last three months above 1,000,000 Rial (100k Toman). This is what
-- took the base from 36M to under 7M there, and leaving it out is why the base
-- came back at 21M. It is a ticket-size floor, not a risk filter: below it the
-- loan is too small to carry its own opex.
INNER JOIN (
    SELECT  sbrp_id
    FROM (  SELECT  sbrp_id,
                    SUM(COALESCE(voi_pkg_rev,0) + COALESCE(voi_payg_rev,0)
                        - COALESCE(intl_roam_voi_rev,0)) / 1.1
                  + SUM(COALESCE(tot_sms_rev,0) - COALESCE(tot_sms_tax,0)
                        - COALESCE(intl_roam_sms_rev,0))
                  + SUM(COALESCE(tot_data_rev,0) - COALESCE(tot_data_tax,0)
                        - COALESCE(post_intl_roam_data_rev,0)
                        - COALESCE(pre_intl_roam_data_rev,0))  AS rev_3m
            FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE   month_key BETWEEN 140404 AND 140406
              AND   sbrp_typ_id = 1
            GROUP BY sbrp_id ) r
    WHERE   r.rev_3m / 3 > 1000000
) rev ON rev.sbrp_id = s.sbrp_id
INNER JOIN (
    SELECT  sbrp_id, APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) AS med_invoice
    FROM (  SELECT sbrp_id, month_key, MAX(COALESCE(invoice_amt,0)) AS invoice_amt
            FROM   dwbi_fact_db.v_fact_sbrp_mthly_cip
            WHERE  month_key BETWEEN 140401 AND 140406
              AND  sbrp_typ_id = 1
            GROUP BY sbrp_id, month_key ) a
    GROUP BY sbrp_id
    -- median over the months that actually carried a bill. A plain median is
    -- dragged to zero by the zero months, which would drop subscribers who
    -- bill perfectly normally.
    HAVING APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) > 0
) m ON m.sbrp_id = s.sbrp_id
-- GATE: not churned at any point in the feature window.
-- stat 4 and 8 are churn; stat 9 is a TWO-WAY BAR and belongs in the label,
-- so it must not be filtered as churn.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040101 AND 14040631
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (4, 8)
) churn ON churn.sbrp_id = s.sbrp_id
-- GATE: barred in the LAST WEEK of the feature window, i.e. still cut off
-- going into T0. Deliberately narrow, for two reasons:
--   1. A one-way bar is overwhelmingly a mid-cycle ceiling hit, which is a
--      large and largely benign population. Gating on 60 days of any bar
--      deletes them from the book for no risk reason.
--   2. Bars earlier in the window are FEATURES - n_nonpay_bar_months_6m and
--      n_ceiling_bar_months_6m carry them. Removing those subscribers is
--      exactly the selection mistake in the original pipeline: it strips the
--      bad-payment examples the model has to learn from.
-- So: barred last week blocks origination, barred before that does not.
-- Window ends at 14040631 - no day of the outcome window is touched.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040625 AND 14040631
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (3, 9)
) barred ON barred.sbrp_id = s.sbrp_id
WHERE   churn.sbrp_id  IS NULL
  AND   barred.sbrp_id IS NULL
;

-- ---------------------------------------------------------------------------
--  RUN THIS NEXT AND SEND ME THE NUMBER
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS n_base FROM dwbi_temp40_db.dcb3_base;

--  And this one - the revenue floor of 1,000,000 Rial came from the old
--  pipeline and may be wrong for 1405 inflation. I will not guess the new
--  value without seeing the distribution.
SELECT  APPROX_PERCENTILE(med_invoice, 0.10) AS p10,
        APPROX_PERCENTILE(med_invoice, 0.25) AS p25,
        APPROX_PERCENTILE(med_invoice, 0.50) AS p50,
        APPROX_PERCENTILE(med_invoice, 0.75) AS p75,
        APPROX_PERCENTILE(med_invoice, 0.90) AS p90,
        AVG(med_invoice)                     AS mean_invoice,
        AVG(age_on_net_months)               AS mean_tenure
FROM    dwbi_temp40_db.dcb3_base;

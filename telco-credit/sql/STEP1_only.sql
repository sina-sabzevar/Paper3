-- ============================================================================
--  STEP 1 ONLY - standalone, ready to paste and run.           (Trino/Presto)
--
--  WHY THE LAST RUN GAVE 1371 ROWS - two independent causes, both fixed here.
--
--  1. THE STATUS CODES WERE WRONG. Confirmed ladder:
--       2 active  3 one-way bar  4 TWO-WAY bar  8 reclaim queue  9 reclaimed
--     The anti-join here read IN (4, 8), so it deleted every subscriber who
--     had ever been fully cut off in six months. That is the main cause of
--     1371, and it is also the selection mistake this project exists to avoid:
--     it strips out the bad payers the model has to learn from. Two-way bars
--     are now FEATURES and label rules, never a gate.
--
--  2. THE TENURE GATE WAS DELETING SILENTLY. age_on_net_months is NULL for
--     part of the rows, and NULL >= 12 evaluates to NULL, so the inline test
--     dropped every subscriber with a MISSING tenure, not only the
--     short-tenured ones. Tenure is now recovered from the most recent
--     non-null value in the feature window and rolled forward to 140406.
--
--  THE 8/9 RULE, as set by the user: these subscribers do not enter the
--  project at all. The exclusion is therefore over the FULL project window
--  14040101..14050131, features and outcome both, and it is the only
--  status-based exclusion. 3 and 4 are kept and carried into the label.
--
--  Also still in effect from the previous round: T0 snapshot month
--  140404 -> 140406, and the barred gate narrowed to the last week of the
--  feature window, now on codes 3 and 4 rather than 3 and 9.
--
--  Revenue columns are RIAL (confirmed), so the 1,000,000 floor is 100k Toman.
--
--  NO percent character anywhere. NO CASE expressions.
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
        ten.tenure_at_t0 AS age_on_net_months,
        m.med_invoice
FROM (
    SELECT  sbrp_id
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    -- 140406 is the LAST month before T0=140407, so this snapshot is the
    -- state the lender sees at the decision point. It was 140404 - three
    -- months early, left over from an older calendar. That made the active
    -- and permanent tests fire at the wrong point in time and shipped a
    -- stale age_on_net_months into the dataset.
    WHERE   month_key    = 140406      -- the month immediately before T0
      AND   sbrp_stat_id = 2           -- GATE: active at T0 (point in time only)
      AND   sbrp_typ_id  = 1           -- permanent
      -- The tenure test USED to sit here as age_on_net_months >= 12. That
      -- column is NULL for part of the rows and NULL >= 12 evaluates to NULL,
      -- so the test silently deleted every subscriber with a MISSING tenure
      -- instead of only the short-tenured ones. It now lives in the join
      -- below, where the value is recovered rather than assumed.
      -- GATE: no open bill at T0 - DISABLED by default.
      -- In the monthly fact this column appears to be the balance at snapshot
      -- time, and for an active postpaid subscriber there is almost always a
      -- bill outstanding, so requiring zero removes nearly the whole base.
      -- The "not barred in the 60 days before T0" gate below already covers
      -- the pattern this was meant to catch. Re-enable only if G1 in
      -- 08_gate_funnel.sql shows it keeps a sensible share.
      -- AND   COALESCE(bill_outstanding_amt, 0) = 0
) s
-- TENURE, RECOVERED rather than read from one possibly-NULL cell.
-- Take the most recent NON-NULL age_on_net_months anywhere in the feature
-- window and roll it forward to 140406. Every month here is in year 1404, so
-- the month number is MOD(month_key, 100) and the roll-forward is 6 minus it.
-- A subscriber with no non-null tenure in any of the six months still cannot
-- pass, but that is now an explicit inner join rather than a silent NULL.
INNER JOIN (
    SELECT  sbrp_id,
            MAX_BY(age_on_net_months, month_key)
              + (6 - MOD(MAX(month_key), 100))            AS tenure_at_t0
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140401 AND 140406
      AND   sbrp_typ_id = 1
      AND   age_on_net_months IS NOT NULL
    GROUP BY sbrp_id
) ten ON ten.sbrp_id = s.sbrp_id
     AND ten.tenure_at_t0 >= 12
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
-- GATE: never touched the reclamation path, ANYWHERE in the project window.
-- Per the business rule these subscribers do not enter the project at all, so
-- the window here is the FULL 14040101..14050131 - features and outcome both -
-- not just the feature months. That makes this one gate the single place the
-- rule is enforced, and the label-level check in STEP 8 becomes a cheap
-- redundant safety net rather than the thing doing the work.
-- One honest note: screening on outcome-window status is look-ahead - at T0 the
-- lender cannot know who will later be reclaimed. It is the user's rule and the
-- affected count is tiny (reaching 8 takes five to six months, and anyone who
-- gets there is already bad on the two-way bar), but G5 in STEP 9 measures it
-- rather than assuming.
-- NOTE what is NOT here any more: this anti-join used to read IN (4, 8), and
-- on the corrected ladder 4 is a TWO-WAY BAR. So it was deleting every
-- subscriber who was ever fully cut off in six months - the single biggest
-- reason the base came back at 1371 rows, and the exact selection mistake
-- this project exists to avoid, since it strips the bad payers the model has
-- to learn from. Two-way bars are now features and label rules, never gates.
LEFT JOIN (
    SELECT DISTINCT sbrp_id
    FROM   dwbi_fact_db.v_fact_sbrp_daily_cip
    WHERE  day_key BETWEEN 14040101 AND 14050131
      AND  sbrp_typ_id = 1
      AND  sbrp_stat_id IN (8, 9)
) reclaim ON reclaim.sbrp_id = s.sbrp_id
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
      AND  sbrp_stat_id IN (3, 4)      -- one-way or two-way bar. NOT 9.
) barred ON barred.sbrp_id = s.sbrp_id
WHERE   reclaim.sbrp_id IS NULL
  AND   barred.sbrp_id  IS NULL
;

-- ---------------------------------------------------------------------------
--  SEND ME THESE TWO
-- ---------------------------------------------------------------------------
SELECT COUNT(*) AS n_base FROM dwbi_temp40_db.dcb3_base;

SELECT  APPROX_PERCENTILE(med_invoice, 0.10)       AS inv_p10,
        APPROX_PERCENTILE(med_invoice, 0.50)       AS inv_p50,
        APPROX_PERCENTILE(med_invoice, 0.90)       AS inv_p90,
        APPROX_PERCENTILE(age_on_net_months, 0.50) AS ten_p50,
        MIN(age_on_net_months)                     AS ten_min
FROM    dwbi_temp40_db.dcb3_base;

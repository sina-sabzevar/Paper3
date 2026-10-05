-- ============================================================================
--  WHERE ARE THE label = 1 SUBSCRIBERS?                     (Trino/Presto)
--
--  Reads dwbi_temp40_db.dcb_funnel, already built by 43_cohort_funnel.sql, so
--  this is cheap - no new scan of the fact table.
--
--  THE SHORT ANSWER, from 43's own output for window 140401..140406:
--
--      the cohort                 5,100,390
--        label = 1                   28,263   0.5541 pct
--        label = 0                5,072,127  99.4459 pct
--
--  The bads are INSIDE the 5.1M. They are the subscribers who were clean
--  through the feature window and then went two-way barred in the label
--  window, which is exactly the event the product has to predict. The 5.1M is
--  not "the good users" - it is the ELIGIBLE population, of which 0.55 pct
--  turn bad.
--
--  WHAT THE SCREEN REMOVED. 403,976 subscribers cleared the revenue bar but
--  already had a bar event IN the feature window: 382,142 one-way and 21,834
--  two-way. Those are not training data withheld - the product will not
--  extend credit to a subscriber who is already barred, so they sit outside
--  the product entirely. dcb_score applies the SAME screen, so the fitting
--  population and the scoring population are filtered identically and there
--  is no selection mismatch between them.
--
--  WHAT THIS FILE ADDS. Whether the screen is doing real work. If the rejected
--  strata carry a much higher forward two-way rate than the cohort, the screen
--  is removing genuine risk and has earned its place. If they carry a similar
--  rate, the screen is mostly shrinking the book for nothing and should be
--  reconsidered.
--
--  ONE CAVEAT ON READING W1. Stratum 3 was ALREADY two-way barred during the
--  feature window, so its forward "bad" is largely the same bar continuing,
--  not a new event predicted. Expect it near 100 pct and do not read it as
--  model-relevant signal. Stratum 2 is the interesting one: one-way barred but
--  not two-way, so a forward two-way bar there IS a real escalation.
--
--  dcb_funnel's rev_months is counted at the PRODUCTION bar of 1,700,000,
--  not at the per-window bar 42_model_datasets.sql uses. That is the right
--  basis for this question, which is about the product's live rule.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- W1  THE FUNNEL, WITH THE FORWARD BAD RATE IN EACH STRATUM.
--
--     The stratum tag is built in a SUBQUERY so GROUP BY names a real column:
--     Trino does not reliably group by a SELECT alias, and two copies of a
--     nested IF drift apart.
--
--     Read down the bad_pct column. Stratum 4 is the cohort the model is
--     fitted on; the strata above it are what the screen threw away.
-- ---------------------------------------------------------------------------
SELECT   win,
         stratum,
         COUNT(*)                                             AS n,
         SUM(IF(judgeable, 1, 0))                             AS n_judgeable,
         SUM(IF(judgeable, y, 0))                             AS n_bad,
         100.0 * SUM(IF(judgeable, y, 0))
               / NULLIF(SUM(IF(judgeable, 1, 0)), 0)          AS bad_pct
FROM (
    SELECT  win, y,
            n_label_months IS NOT NULL                        AS judgeable,
            IF(rev_months < 2, '1_fails_revenue_bar',
            IF(ow_any = 1,     '2_oneway_in_feature_window',
            IF(tw_any = 1,     '3_twoway_in_feature_window',
                               '4_SCREENED_the_cohort')))     AS stratum
    FROM    dwbi_temp40_db.dcb_funnel
) q
GROUP BY win, stratum
ORDER BY win, stratum;

-- ---------------------------------------------------------------------------
-- W2  DOES IT RECONCILE WITH 43 D1? A built-in cross-check.
--
--     For window 140401..140406 the strata must sum to the funnel steps:
--         stratum 1  = present - pass_rev        = 32,185,293
--         stratum 2  = pass_rev - pass_rev_ow    =    382,142
--         stratum 3  = pass_rev_ow - screened    =     21,834
--         stratum 4  = screened                  =  5,100,390
--     If these do not match, the stratum logic and D1's funnel disagree and
--     one of them is wrong.
-- ---------------------------------------------------------------------------
SELECT   win,
         COUNT(*)                                                   AS present,
         SUM(IF(rev_months >= 2, 1, 0))                             AS pass_rev,
         SUM(IF(rev_months >= 2 AND ow_any = 0, 1, 0))              AS pass_rev_ow,
         SUM(IF(rev_months >= 2 AND ow_any = 0 AND tw_any = 0, 1, 0))
                                                                    AS screened
FROM     dwbi_temp40_db.dcb_funnel
GROUP BY win
ORDER BY win;

-- ---------------------------------------------------------------------------
-- W3  HOW MUCH RISK DOES THE SCREEN ACTUALLY REMOVE?
--
--     The whole judgeable population against the screened cohort. The ratio
--     is the screen's lift: how many times riskier the population would be
--     without it. A large ratio means the screen is most of the credit
--     decision and the model is refining what is left; a ratio near 1 means
--     the screen is shrinking the book without reducing risk.
-- ---------------------------------------------------------------------------
SELECT   win,
         SUM(IF(n_label_months IS NOT NULL, 1, 0))            AS all_judgeable,
         100.0 * SUM(IF(n_label_months IS NOT NULL, y, 0))
               / NULLIF(SUM(IF(n_label_months IS NOT NULL, 1, 0)), 0)
                                                              AS all_bad_pct,
         SUM(IF(n_label_months IS NOT NULL AND rev_months >= 2
                AND ow_any = 0 AND tw_any = 0, 1, 0))         AS screened,
         100.0 * SUM(IF(n_label_months IS NOT NULL AND rev_months >= 2
                        AND ow_any = 0 AND tw_any = 0, y, 0))
               / NULLIF(SUM(IF(n_label_months IS NOT NULL AND rev_months >= 2
                              AND ow_any = 0 AND tw_any = 0, 1, 0)), 0)
                                                              AS screened_bad_pct
FROM     dwbi_temp40_db.dcb_funnel
GROUP BY win
ORDER BY win;

-- ---------------------------------------------------------------------------
-- W4  IS THERE ANYTHING LEFT FOR THE MODEL TO FIND?
--
--     Inside the screened cohort only, the bad rate by how many months
--     cleared the bar. If the rate falls steadily as rev_months rises, there
--     is real separation inside the cohort and the model has signal to work
--     with. If it is flat, the screen has already extracted what the revenue
--     features can say and the model will have to rely on the payment,
--     outstanding and tenure features instead.
--
--     This is the single most useful number for setting expectations on AUC
--     before the fit is run.
-- ---------------------------------------------------------------------------
SELECT   win,
         rev_months,
         COUNT(*)                                             AS n,
         SUM(y)                                               AS n_bad,
         100.0 * SUM(y) / NULLIF(COUNT(*), 0)                 AS bad_pct
FROM     dwbi_temp40_db.dcb_funnel
WHERE    rev_months >= 2
  AND    ow_any = 0
  AND    tw_any = 0
  AND    n_label_months IS NOT NULL
GROUP BY win, rev_months
ORDER BY win, rev_months;

-- ============================================================================
--  WHY 40M AND NOT 26M?                                    (Trino/Presto)
--
--  43 D1 reports 41,270,092 subscribers present in 140501..140506 at
--  sbrp_typ_id = 1, with an average of 5.797 months seen each. That is about
--  39.9M per month, not the 26M held to be the permanent base. The gap is too
--  large to be churn and new activations, which would show up as a LOW
--  avg_months_seen, and it is 5.8 of 6.
--
--  So sbrp_typ_id = 1 is broader than what the business counts. The leading
--  candidate is activity: KPI_v4 defines Active1 as active1_base_flag = 1, and
--  42_model_datasets.sql already carries n_active1 as a FEATURE but does not
--  SCREEN on it.
--
--  WHICH MATTERS MORE THAN A RECONCILIATION. If the 26M is the active base,
--  then the 9,344,723 scored subscribers may include people who were never
--  active in the window - and extending a credit line to a subscriber who is
--  not using the service is a different proposition from lending to one who
--  is. B3 counts them. If it comes back non-trivial, active1 belongs in the
--  screen and the book needs re-cutting.
--
--  THE FUNNEL FOR REFERENCE, window 140501..140506:
--      present                            41,270,092
--      cleared the revenue bar            10,087,975   -31,182,117
--      and never one-way barred            9,437,240      -650,735
--      and never two-way barred -> SCORED  9,344,723       -92,517
--
--  The revenue bar is 97.67 pct of all exclusions. The median subscriber
--  bills about 28,948 Toman a month against a 170,000 Toman bar, roughly 5.9x
--  the median, so most simply do not spend enough. The two bar filters
--  together account for 2.33 pct.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- B1  ONE MONTH, EVERY DEFINITION SIDE BY SIDE. 140506 is the last month of
--     the scoring window.
--
--     If n_active1 lands near 26M, that is the answer and nothing is wrong -
--     the screen simply runs over a wider population than the business
--     headline. If it is also near 40M, activity is not the explanation and
--     the gap is something else: a segment inside sbrp_typ_id = 1 that is not
--     counted as permanent, or a different subscriber-type coding.
-- ---------------------------------------------------------------------------
SELECT  COUNT(DISTINCT sbrp_id)                                   AS n_all,
        COUNT(DISTINCT IF(active1_base_flag = 1, sbrp_id, NULL))  AS n_active1,
        COUNT(DISTINCT IF(active1_base_flag = 1, sbrp_id, NULL))
            * 1.0 / NULLIF(COUNT(DISTINCT sbrp_id), 0)            AS active_share,
        COUNT(DISTINCT IF(sbrp_stat_id = 1, sbrp_id, NULL))        AS n_stat_1,
        COUNT(DISTINCT IF(sbrp_stat_id = 2, sbrp_id, NULL))        AS n_stat_2,
        COUNT(DISTINCT IF(sbrp_stat_id = 3, sbrp_id, NULL))        AS n_stat_3,
        COUNT(DISTINCT IF(sbrp_stat_id = 4, sbrp_id, NULL))        AS n_stat_4,
        COUNT(DISTINCT IF(sbrp_stat_id IN (8,9), sbrp_id, NULL))   AS n_stat_8_9,
        COUNT(DISTINCT IF(sbrp_stat_id NOT IN (1,2,3,4,8,9), sbrp_id, NULL))
                                                                  AS n_stat_other
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key = 140506
  AND   sbrp_typ_id = 1;

-- ---------------------------------------------------------------------------
-- B2  EVERY SUBSCRIBER TYPE, one month. If sbrp_typ_id = 1 is not the whole
--     story - if the permanent base is split across more than one code - this
--     shows it. Run before concluding anything from B1.
-- ---------------------------------------------------------------------------
SELECT   sbrp_typ_id,
         COUNT(DISTINCT sbrp_id)                                  AS n_subs,
         COUNT(DISTINCT IF(active1_base_flag = 1, sbrp_id, NULL)) AS n_active1,
         AVG(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) / 10
                                                                  AS avg_rev_toman
FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE    month_key = 140506
GROUP BY sbrp_typ_id
ORDER BY n_subs DESC;

-- ---------------------------------------------------------------------------
-- B3  THE QUESTION THAT AFFECTS THE BOOK. How many SCORED subscribers were
--     never active in the window?
--
--     42 carries n_active1 - months with active1_base_flag = 1, out of 6 -
--     as a feature but does not screen on it. A subscriber with n_active1 = 0
--     passed the revenue bar in 2 or more months yet was never counted active
--     in any of them, which is contradictory enough to be worth seeing.
--
--     If the count is small, this is a curiosity. If it is large, active1
--     belongs in the screen and the 4,672,361 needs re-cutting.
-- ---------------------------------------------------------------------------
SELECT   n_active1,
         COUNT(*)                                          AS n_scored,
         100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()          AS pct_of_scored,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60               AS med_month_toman,
         AVG(rev_months)                                   AS avg_rev_months
FROM     dwbi_temp40_db.dcb_score
GROUP BY n_active1
ORDER BY n_active1;

-- ---------------------------------------------------------------------------
-- B4  AND THE SAME ON THE LABELLED SIDE, where it can be priced. If never-
--     active subscribers carry a materially different event rate, that settles
--     whether activity belongs in the screen rather than leaving it to
--     judgement.
-- ---------------------------------------------------------------------------
SELECT   n_active1,
         COUNT(*)                                          AS n,
         SUM(y)                                            AS n_bad,
         100.0 * SUM(y) / NULLIF(COUNT(*), 0)              AS bad_pct,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60               AS med_month_toman
FROM     dwbi_temp40_db.dcb_model
GROUP BY n_active1
ORDER BY n_active1;

-- ---------------------------------------------------------------------------
-- B5  THE MONTH-BY-MONTH BASE, so the 6-month distinct count and the
--     per-month count are never confused again. 43's 41,270,092 is the
--     DISTINCT count over six months; each individual month is smaller.
-- ---------------------------------------------------------------------------
SELECT   month_key,
         COUNT(DISTINCT sbrp_id)                                  AS n_subs,
         COUNT(DISTINCT IF(active1_base_flag = 1, sbrp_id, NULL)) AS n_active1
FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE    month_key BETWEEN 140501 AND 140506
  AND    sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;

-- ---------------------------------------------------------------------------
-- B6  HOW THIN IS THE QUALIFICATION? The screen asks for revenue at or above
--     1,700,000 Rial (170,000 Toman) in 2 OR MORE of 6 months - not every
--     month. So "cleared the bar" covers a subscriber who cleared it in
--     exactly 2 months and one who cleared it in all 6, and those are not the
--     same credit proposition.
--
--     dcb_score.rev_months counts months at or above 1,700,000, and the
--     screen forces it to 2 or more, so this runs 2..6.
-- ---------------------------------------------------------------------------
SELECT   rev_months,
         COUNT(*)                                       AS n_scored,
         100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()       AS pct_of_scored,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60            AS med_month_toman,
         APPROX_PERCENTILE(rev_max, 0.5) / 10           AS med_best_month_toman
FROM     dwbi_temp40_db.dcb_score
GROUP BY rev_months
ORDER BY rev_months;

-- ---------------------------------------------------------------------------
-- B7  AND DOES CLEARING IT IN MORE MONTHS MAKE A SUBSCRIBER SAFER?
--
--     NOTE THE BAR. dcb_model carries the 1,050,000 Rial bar, not 1,700,000 -
--     that is deliberate, it is the bar that makes the 1404 cohort the same
--     SIZE as the live 1405 screen. r1..r6 are not persisted, so months above
--     the production bar cannot be recomputed here. The SHAPE of the question
--     is the same: does bar-clearing frequency rank risk?
--
--     If bad_pct is flat across 2..6, then the number of months a subscriber
--     clears the bar carries no risk information and the screen is purely a
--     capacity rule - consistent with the marginal-admit result in 46, where
--     the subscribers a lower bar lets in came in SAFER at 0.4749 pct.
-- ---------------------------------------------------------------------------
SELECT   rev_months,
         COUNT(*)                                       AS n,
         SUM(y)                                         AS n_bad,
         100.0 * SUM(y) / NULLIF(COUNT(*), 0)           AS bad_pct,
         APPROX_PERCENTILE(rev_6m, 0.5) / 60            AS med_month_toman
FROM     dwbi_temp40_db.dcb_model
WHERE    in_band = 1
GROUP BY rev_months
ORDER BY rev_months;

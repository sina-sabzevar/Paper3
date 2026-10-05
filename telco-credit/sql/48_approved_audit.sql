-- ============================================================================
--  DUE DILIGENCE ON THE APPROVED BOOK                      (Trino/Presto)
--
--  Needs dwbi_temp40_db.dcb_pd, which notebook/push_scores.py uploads from
--  handover_scores.csv. The cut is made HERE, in SQL, so changing TAKE is a
--  one-line edit and needs no re-upload.
--
--  WHAT THE SCREEN COULD NOT SEE, and why this file exists.
--
--  The screen looked at bar history inside the FEATURE WINDOW only -
--  140501..140506 for the scored set. A subscriber one-way barred in 140409,
--  or two-way barred in 140312, passes it cleanly. The model never saw that
--  either: f_twoway and oneway_months are computed over the same six months,
--  so nothing in the 34 features carries bar history from before them.
--
--  That is a real blind spot rather than a hypothetical. A2 measures how much
--  of the approved book has it, and A5 tests on dcb_model - where labels
--  exist - whether it would have mattered. If A5 shows older bar history
--  predicting the label, it is a missing feature and the model should be
--  refitted with it before this book is lent against.
--
--  WINDOWS
--      scored features   140501..140506   what the screen and model used
--      pre-history       140301..140412   everything before that, 14 months
--      full              140301..140506
--
--  COST. A1 to A3 and A5 read the monthly table and are ordinary. A4 reads
--  the DAILY table - about 181 days across 4.67M subscribers - and is the
--  expensive one. It is last so the rest can be read without waiting, and it
--  joins to the approved set FIRST so the scan is restricted.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
--  THE CUT. Change TAKE here, nowhere else. 4,672,361 is the chosen book:
--  book PD 0.2094 pct, marginal 0.3142 pct, 2,336 bn Toman at 500,000 each.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_approved;
CREATE TABLE dwbi_temp40_db.dcb_approved WITH (format='PARQUET') AS
SELECT   sbrp_id, pd_4m, grade
FROM     dwbi_temp40_db.dcb_pd
ORDER BY pd_4m
LIMIT    4672361
;

-- ---------------------------------------------------------------------------
-- A1  DOES THE CUT MATCH WHAT PYTHON DECIDED? Check before reading anything
--     else. n must be 4,672,361, distinct must equal n, and book_pd must come
--     back at about 0.2094 pct. A mismatch means the upload is partial or the
--     ORDER BY broke a tie differently, and every figure below would describe
--     a different population from the one select_book.py reported.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                        AS n,
        COUNT(DISTINCT sbrp_id)         AS n_distinct,
        100.0 * AVG(pd_4m)              AS book_pd_pct,
        100.0 * MAX(pd_4m)              AS cutoff_pd_pct,
        COUNT(*) FILTER (WHERE pd_4m IS NULL) AS n_null_pd
FROM    dwbi_temp40_db.dcb_approved;

-- ---------------------------------------------------------------------------
-- A2  THE BLIND SPOT, MEASURED. Bar history in 140301..140412 - entirely
--     before the window the screen and the model looked at.
--
--     Read ever_twoway_pre first. Those subscribers were cut off completely
--     for non-payment at some point in the 14 months before scoring, and
--     nothing in the screen or the features knows it.
--
--     Broken out by grade so you can see whether the model's own ranking
--     happens to correlate with it. If grade A carries as much old bar
--     history as grade E, the model is blind to it rather than pricing it
--     indirectly through outstanding or tenure.
-- ---------------------------------------------------------------------------
SELECT   a.grade,
         COUNT(*)                                             AS n_approved,
         SUM(IF(h.months_seen IS NULL, 1, 0))                 AS absent_pre_window,
         SUM(IF(COALESCE(h.ever_ow, 0) = 1, 1, 0))            AS ever_oneway_pre,
         100.0 * SUM(IF(COALESCE(h.ever_ow, 0) = 1, 1, 0)) / COUNT(*)
                                                              AS pct_oneway_pre,
         SUM(IF(COALESCE(h.ever_tw, 0) = 1, 1, 0))            AS ever_twoway_pre,
         100.0 * SUM(IF(COALESCE(h.ever_tw, 0) = 1, 1, 0)) / COUNT(*)
                                                              AS pct_twoway_pre,
         AVG(COALESCE(h.n_ow_months, 0))                      AS avg_oneway_months,
         AVG(COALESCE(h.n_tw_months, 0))                      AS avg_twoway_months
FROM     dwbi_temp40_db.dcb_approved a
LEFT JOIN (
    -- One row per subscriber. Flattened before the join so it cannot fan out.
    SELECT   sbrp_id,
             COUNT(DISTINCT month_key)                           AS months_seen,
             MAX(IF(sbrp_stat_id = 3, 1, 0))                     AS ever_ow,
             MAX(IF(sbrp_stat_id = 4, 1, 0))                     AS ever_tw,
             COUNT(DISTINCT IF(sbrp_stat_id = 3, month_key, NULL)) AS n_ow_months,
             COUNT(DISTINCT IF(sbrp_stat_id = 4, month_key, NULL)) AS n_tw_months
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140412
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
) h ON h.sbrp_id = a.sbrp_id
GROUP BY a.grade
ORDER BY a.grade;

-- ---------------------------------------------------------------------------
-- A3  REVENUE, BILLS AND PAYMENTS over the full 140301..140506 history.
--
--     Both sides are flattened to one row per subscriber BEFORE being joined
--     to the approved list. Joining two multi-row relations to the same key
--     list gives a cartesian product, and a month-filtered SUM over it
--     multiplies - this project once read revenue as 8,000,000 instead of
--     2,000,000 exactly that way.
--
--     pay_to_rev above 1 is expected: the revenue KPI is arpu NET of tax
--     while payments include the tax paid, plus any arrears settled in the
--     window. It measured 1.40 and 1.28 on the two model windows.
-- ---------------------------------------------------------------------------
SELECT   a.grade,
         COUNT(*)                                          AS n_approved,
         AVG(m.months_seen)                                AS avg_months_seen,
         AVG(m.rev_total) / 10                             AS avg_rev_toman,
         APPROX_PERCENTILE(m.rev_total / NULLIF(m.months_seen,0), 0.5) / 10
                                                           AS med_month_rev_toman,
         AVG(COALESCE(p.paid_total, 0)) / 10               AS avg_paid_toman,
         AVG(COALESCE(p.paid_total, 0)) / NULLIF(AVG(m.rev_total), 0)
                                                           AS pay_to_rev,
         AVG(COALESCE(p.n_payments, 0))                    AS avg_n_payments,
         AVG(m.outst_max) / 10                             AS avg_peak_outst_toman,
         100.0 * SUM(IF(m.outst_max > 0, 1, 0)) / COUNT(*) AS pct_ever_outstanding,
         AVG(m.tenure_max)                                 AS avg_tenure_months
FROM     dwbi_temp40_db.dcb_approved a
LEFT JOIN (
    SELECT   sbrp_id,
             COUNT(DISTINCT month_key)                              AS months_seen,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0))   AS rev_total,
             MAX(COALESCE(bill_outstanding_amt,0))                  AS outst_max,
             MAX(COALESCE(age_on_net_months,0))                     AS tenure_max
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140506
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
) m ON m.sbrp_id = a.sbrp_id
LEFT JOIN (
    SELECT   sbrp_id,
             SUM(COALESCE(pmnt_amt,0)) AS paid_total,
             COUNT(*)                  AS n_payments
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14030101 AND 14050631
    GROUP BY sbrp_id
) p ON p.sbrp_id = a.sbrp_id
GROUP BY a.grade
ORDER BY a.grade;

-- ---------------------------------------------------------------------------
-- A4  PAYMENT DELAY, in days. THE EXPENSIVE ONE - run it last, and narrow the
--     day_key range if it is too slow.
--
--     The daily table is flattened to one row per subscriber-day BEFORE any
--     counting, with MAX over the day. That makes the result correct whether
--     or not the table holds one row per subscriber-day, which has never been
--     established here - the reconnaissance query for it was written and the
--     result never read. Flattening removes the question instead of assuming
--     an answer.
--
--     debt_days is the count of days carrying any billed outstanding, which
--     is the closest thing to "delay on payment" the daily table gives
--     directly. It is not days-past-due against a specific invoice date.
-- ---------------------------------------------------------------------------
SELECT   a.grade,
         COUNT(*)                                       AS n_approved,
         AVG(COALESCE(d.days_seen, 0))                  AS avg_days_seen,
         AVG(COALESCE(d.debt_days, 0))                  AS avg_debt_days,
         APPROX_PERCENTILE(CAST(COALESCE(d.debt_days,0) AS DOUBLE), 0.5)
                                                        AS med_debt_days,
         APPROX_PERCENTILE(CAST(COALESCE(d.debt_days,0) AS DOUBLE), 0.9)
                                                        AS p90_debt_days,
         100.0 * SUM(IF(COALESCE(d.debt_days,0) = 0, 1, 0)) / COUNT(*)
                                                        AS pct_never_in_debt,
         AVG(COALESCE(d.unbill_days, 0))                AS avg_unbill_days
FROM     dwbi_temp40_db.dcb_approved a
LEFT JOIN (
    SELECT   sbrp_id,
             COUNT(*)                            AS days_seen,
             SUM(IF(bill_outst > 0, 1, 0))       AS debt_days,
             SUM(IF(unbill_outst > 0, 1, 0))     AS unbill_days
    FROM (
        -- one row per subscriber-day, whatever the source grain
        SELECT   sbrp_id, day_key,
                 MAX(COALESCE(bill_outstanding_amt, 0))   AS bill_outst,
                 MAX(COALESCE(unbill_outstanding_amt, 0)) AS unbill_outst
        FROM     dwbi_fact_db.v_fact_sbrp_daily_cip
        WHERE    day_key BETWEEN 14050101 AND 14050631
        GROUP BY sbrp_id, day_key
    ) q
    GROUP BY sbrp_id
) d ON d.sbrp_id = a.sbrp_id
GROUP BY a.grade
ORDER BY a.grade;

-- ---------------------------------------------------------------------------
-- A5  WOULD THE BLIND SPOT HAVE MATTERED? The test that decides whether to
--     refit.
--
--     Run on dcb_model, not the approved set, because dcb_model CARRIES THE
--     LABEL. Its feature window is 140401..140406 and its label 140407..
--     140410, so 140301..140312 is entirely before both - the same blind spot
--     the scored set has, on a population where the outcome is known.
--
--     If pct_bad rises with older bar history, the model is missing a real
--     predictor and should be refitted with historical bar counts added to
--     42_model_datasets.sql. If it is flat, the blind spot costs nothing and
--     A2's numbers are descriptive rather than a warning.
--
--     Conditioned on rev_months as well, so the comparison is within
--     similar-revenue subscribers rather than across them.
-- ---------------------------------------------------------------------------
SELECT   pre_bar,
         rev_months,
         COUNT(*)                                     AS n,
         SUM(y)                                       AS n_bad,
         100.0 * SUM(y) / NULLIF(COUNT(*), 0)         AS bad_pct
FROM (
    SELECT  d.y,
            d.rev_months,
            IF(COALESCE(h.ever_tw, 0) = 1, '3_twoway_before',
            IF(COALESCE(h.ever_ow, 0) = 1, '2_oneway_before',
                                           '1_clean_before')) AS pre_bar
    FROM        dwbi_temp40_db.dcb_model d
    LEFT JOIN (
        SELECT   sbrp_id,
                 MAX(IF(sbrp_stat_id = 3, 1, 0)) AS ever_ow,
                 MAX(IF(sbrp_stat_id = 4, 1, 0)) AS ever_tw
        FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
        WHERE    month_key BETWEEN 140301 AND 140312
          AND    sbrp_typ_id = 1
        GROUP BY sbrp_id
    ) h ON h.sbrp_id = d.sbrp_id
) z
GROUP BY pre_bar, rev_months
ORDER BY pre_bar, rev_months;

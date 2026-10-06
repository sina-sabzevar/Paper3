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
--  STEP 0. TYPE THE SCORE COLUMN. Do not skip this.
--
--  If pd_4m arrived as VARCHAR - which it does when the upload infers types
--  from a CSV - then "ORDER BY pd_4m" sorts it as TEXT, and the cut is wrong
--  in the worst possible way: it still returns exactly the right NUMBER of
--  rows, so a count check passes while the population is not the one the
--  model chose.
--
--  Why text sort fails here: pandas writes small floats in scientific
--  notation, so the column holds a mix of '0.0252' and '1.573e-07'. As text,
--  '1e-07' begins with '1' and '0.0252' begins with '0', so EVERY
--  scientific-notation value sorts AFTER every 0.x value - which puts the
--  SAFEST subscribers last and excludes them from the cut.
--
--  Measured on a simulation of the real value range: taking the safest 40 pct
--  by text agreed with the numeric cut on only a quarter of the rows, swapped
--  in subscribers 654x riskier, and turned a 0.082 pct book into a 1.348 pct
--  book.
--
--  CAST(... AS DOUBLE) is a no-op if the column is already DOUBLE, so this is
--  safe to run either way. Trino parses scientific notation correctly.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_pd_num;
CREATE TABLE dwbi_temp40_db.dcb_pd_num WITH (format='PARQUET') AS
SELECT   sbrp_id,
         CAST(pd_4m AS DOUBLE) AS pd_4m,
         grade
FROM     dwbi_temp40_db.dcb_pd
;

-- A0  DID THE CAST SURVIVE EVERY ROW? Any null_after_cast means a value did
--     not parse, and those subscribers would silently drop out of the cut.
--     n must equal the 9,344,723 that were uploaded.
SELECT  COUNT(*)                                      AS n,
        COUNT(pd_4m)                                  AS n_parsed,
        COUNT(*) - COUNT(pd_4m)                       AS null_after_cast,
        MIN(pd_4m)                                    AS min_pd,
        MAX(pd_4m)                                    AS max_pd,
        AVG(pd_4m)                                    AS avg_pd
FROM    dwbi_temp40_db.dcb_pd_num;

-- ---------------------------------------------------------------------------
--  THE CUT. Change TAKE here, nowhere else. 4,672,361 is the chosen book:
--  book PD 0.2094 pct, marginal 0.3142 pct, 2,336 bn Toman at 500,000 each.
--
--  Sorted on the TYPED table, so this is a numeric sort.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_approved;
CREATE TABLE dwbi_temp40_db.dcb_approved WITH (format='PARQUET') AS
SELECT   sbrp_id, pd_4m, grade
FROM     dwbi_temp40_db.dcb_pd_num
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
SELECT  COUNT(*)                              AS n,
        COUNT(DISTINCT sbrp_id)               AS n_distinct,
        100.0 * AVG(pd_4m)                    AS book_pd_pct,
        100.0 * MAX(pd_4m)                    AS cutoff_pd_pct,
        COUNT(*) FILTER (WHERE pd_4m IS NULL) AS n_null_pd,
        -- THE SORT CHECK. Every approved subscriber must be at or below the
        -- cutoff, and nobody outside the cut may sit below it. If a text sort
        -- happened anyway, worse_outside_cut comes back large while the row
        -- count still looks perfect.
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_pd_num p
          WHERE p.pd_4m < (SELECT MAX(pd_4m) FROM dwbi_temp40_db.dcb_approved)
            AND p.sbrp_id NOT IN
                (SELECT sbrp_id FROM dwbi_temp40_db.dcb_approved))
                                              AS safer_left_out
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
-- A4  DAYS CARRYING A BILL. NOT payment delay - I labelled it that and was
--     wrong. THE EXPENSIVE ONE - run it last, and narrow the day_key range
--     if it is too slow.
--
--     MEASURED, and it is why the name changed. On the approved book:
--         grade A  94.6 debt_days of 186 (50.9 pct),  unbill 98.8 pct of days
--         grade B  80.9 debt_days of 186 (43.5 pct),  unbill 99.1 pct of days
--         only 0.3 pct of subscribers were never in debt at all
--
--     Grade A - the SAFER grade - carries an outstanding bill on MORE days
--     than grade B. That settles it: this is the normal postpaid billing
--     cycle, not delinquency. A bill stands open from issue until payment, so
--     bill_outstanding_amt > 0 cannot distinguish "has a current bill" from
--     "is late paying it", and 99 pct of days showing unbilled outstanding is
--     just accrual between cycles.
--
--     REAL delay needs days past the DUE date. This column does not carry a
--     due date, so it cannot be computed from here. Read these numbers as
--     billing-cycle shape - whether a subscriber pays early or late IN the
--     cycle - and not as a risk measure.
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
         AVG(COALESCE(d.days_with_a_bill, 0))           AS avg_days_with_bill,
         APPROX_PERCENTILE(CAST(COALESCE(d.days_with_a_bill,0) AS DOUBLE), 0.5)
                                                        AS med_days_with_bill,
         APPROX_PERCENTILE(CAST(COALESCE(d.days_with_a_bill,0) AS DOUBLE), 0.9)
                                                        AS p90_days_with_bill,
         100.0 * SUM(IF(COALESCE(d.days_with_a_bill,0) = 0, 1, 0)) / COUNT(*)
                                                        AS pct_never_carrying,
         AVG(COALESCE(d.unbill_days, 0))                AS avg_unbill_days
FROM     dwbi_temp40_db.dcb_approved a
LEFT JOIN (
    SELECT   sbrp_id,
             COUNT(*)                            AS days_seen,
             SUM(IF(bill_outst > 0, 1, 0))       AS days_with_a_bill,
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
--
--     THE PRE WINDOW IS 140301..140312 AND MUST NOT BE WIDENED PAST 140406.
--     It has to end before the LABEL window (140407..140410) begins. Running
--     it from 140401 onward instead produced this, on a real run:
--
--         1_clean_before     n_bad 0        0.0 pct
--         2_oneway_before    n_bad 0        0.0 pct
--         3_twoway_before    n_bad 12,078  61.1 pct
--
--     Zero bads in two of three buckets and 61 pct in the third is not a
--     finding, it is the definition collapsing: once the window contains the
--     label months, "two-way before" MEANS "two-way in the label window",
--     which is y = 1, and everyone barred in the label window lands in that
--     bucket so the other two are left with none. If the clean bucket comes
--     back with zero bads, the window is wrong - stop and fix it.
--
--     MEASURED with the correct window: clean 0.3916 pct, one-way before
--     1.5627 pct (4.0x), two-way before 5.1574 pct (13.2x), holding at every
--     revenue level. That is what put pre_ow_any and pre_tw_any into
--     42_model_datasets.sql.
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

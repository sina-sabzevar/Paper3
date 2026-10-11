-- ============================================================================
--  DOES THE LABEL MEASURE THE DRAW, OR SOMETHING THAT STARTED BEFORE IT?
--                                                             (Trino/Presto)
--
--  THE OBJECTION, WHICH IS THE RIGHT ONE
--
--  dcb_model labels y = 1 when sbrp_stat_id = 4 in 140408. A two-way bar is
--  the END of a dunning ladder, not the start of one. If the operator takes
--  months to escalate, then a bar in 140408 was set in motion well before
--  140407, which is the month the DCB draw lands on. In that case the label
--  is not "the subscriber failed to repay the draw". It is "the subscriber
--  was already failing while we were still measuring their features", and
--  two things follow, both bad:
--
--    1. The model is reading the cause of its own label out of q5, q6,
--       paid_6m and outst_max. The 0.8278 test AUC would then be part
--       recognition and part prediction, and there is no way to tell which
--       from the number alone.
--    2. The product question - a draw lands on the 140407 bill, is it repaid
--       on 140408 - is not the question being answered at all.
--
--  10_dcb_extract_v2 already asserts the ladder as "one-way -> +3 months to
--  escalate -> +1 more to persist". That was written as an assumption. It was
--  never measured, and if it is right the one-month label cannot work.
--
--  WHY THE SCREEN DOES NOT ALREADY SOLVE THIS
--
--  dcb_model screens on o1..o6 = 0 and f_twoway = 0, so every labelled
--  subscriber was clean on the monthly snapshot through 140406. If the ladder
--  really took three months, nobody could reach a two-way bar by 140408 and
--  the label would be empty. It is not empty - 19,215 events. So one of these
--  is true, and which one decides the whole design:
--
--    a) the ladder can run in one or two months for some subscribers
--    b) a monthly snapshot misses one-way episodes that start and cure
--       inside a month, so the screen is not catching them
--    c) some two-way bars arrive without a one-way stage at all
--
--  L2 and L4 separate these. Run L0 first; everything else reads its table.
--
--  WHAT EACH STATEMENT DECIDES
--
--    L0  build the base: the screened population plus status and payments
--        for the six months AFTER the feature window
--    L1  the lag curve. When do bars actually land? This alone says where
--        the label month belongs.
--    L2  for subscribers first barred in 140408, what was their status in
--        140407. The decisive cross-tab.
--    L3  did they stop paying before the feature window closed. This is the
--        leakage test.
--    L4  the first non-active status and when it appeared: ladder or no
--        ladder.
--    L5  the repayment-side label, which has no ladder lag at all, and its
--        rate at several coverage thresholds.
--    L6  reconcile against the 19,215 the current label produces.
--
--  NO percent character anywhere. NO CASE expressions.
--  Amounts are RIAL. 1 Toman = 10 Rial.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- L0  THE BASE. Same screen as dcb_model so the answer applies to the actual
--     training population, not to the whole subscriber file.
--
--     Carries status for 140407..140412 and payments for 140405..140409, so
--     every later statement is a GROUP BY and nothing re-reads the fact.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_lag;

CREATE TABLE dwbi_temp40_db.dcb_lag WITH (format='PARQUET') AS
WITH pm AS (
    SELECT   sbrp_id, day_key / 100 AS mk, SUM(COALESCE(pmnt_amt,0)) AS paid
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14040501 AND 14040931
    GROUP BY sbrp_id, day_key / 100
),
pay AS (
    SELECT  sbrp_id,
            COALESCE(SUM(paid) FILTER (WHERE mk = 140405), 0) AS q5,
            COALESCE(SUM(paid) FILTER (WHERE mk = 140406), 0) AS q6,
            COALESCE(SUM(paid) FILTER (WHERE mk = 140407), 0) AS q7,
            COALESCE(SUM(paid) FILTER (WHERE mk = 140408), 0) AS q8,
            COALESCE(SUM(paid) FILTER (WHERE mk = 140409), 0) AS q9
    FROM    pm GROUP BY sbrp_id
),
feat AS (
    -- the feature window, exactly as 42 builds it
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140401), 0) AS r1,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140402), 0) AS r2,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140403), 0) AS r3,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140404), 0) AS r4,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140405), 0) AS r5,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140406), 0) AS r6,
            MAX(IF(month_key=140401 AND sbrp_stat_id=3,1,0)) AS o1,
            MAX(IF(month_key=140402 AND sbrp_stat_id=3,1,0)) AS o2,
            MAX(IF(month_key=140403 AND sbrp_stat_id=3,1,0)) AS o3,
            MAX(IF(month_key=140404 AND sbrp_stat_id=3,1,0)) AS o4,
            MAX(IF(month_key=140405 AND sbrp_stat_id=3,1,0)) AS o5,
            MAX(IF(month_key=140406 AND sbrp_stat_id=3,1,0)) AS o6,
            MAX(IF(sbrp_stat_id=4,1,0))                      AS f_twoway,
            MAX(COALESCE(bill_outstanding_amt,0))
                FILTER (WHERE month_key = 140406)            AS out6
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key IN (140401,140402,140403,140404,140405,140406)
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
),
fwd AS (
    -- the six months after the feature window. MAX over a month is safe:
    -- the monthly fact carries one row per subscriber per month.
    SELECT  sbrp_id,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140407) AS s7,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140408) AS s8,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140409) AS s9,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140410) AS s10,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140411) AS s11,
            MAX(sbrp_stat_id) FILTER (WHERE month_key = 140412) AS s12,
            COALESCE(MAX(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140407), 0)      AS r7
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140407 AND 140412
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT      f.sbrp_id,
            f.r5, f.r6, f.out6,
            w.r7,
            COALESCE(p.q5,0) AS q5, COALESCE(p.q6,0) AS q6,
            COALESCE(p.q7,0) AS q7, COALESCE(p.q8,0) AS q8,
            COALESCE(p.q9,0) AS q9,
            w.s7, w.s8, w.s9, w.s10, w.s11, w.s12,
            -- the first month in 140407..140412 carrying a two-way bar.
            -- 0 means never barred in the six months.
            IF(w.s7  = 4, 140407,
            IF(w.s8  = 4, 140408,
            IF(w.s9  = 4, 140409,
            IF(w.s10 = 4, 140410,
            IF(w.s11 = 4, 140411,
            IF(w.s12 = 4, 140412, 0))))))                AS first_tw,
            -- and the first one-way bar, same convention
            IF(w.s7  = 3, 140407,
            IF(w.s8  = 3, 140408,
            IF(w.s9  = 3, 140409,
            IF(w.s10 = 3, 140410,
            IF(w.s11 = 3, 140411,
            IF(w.s12 = 3, 140412, 0))))))                AS first_ow,
            -- what 42 calls y: a two-way bar in the label month
            IF(w.s8 = 4, 1, 0)                           AS y_current,
            -- how much of the 140407 bill came back in 140408. NULL when
            -- there was no bill to repay, so it never dilutes a rate.
            IF(w.r7 > 0, CAST(COALESCE(p.q8,0) AS DOUBLE) / w.r7, NULL) AS cover8,
            -- and by the end of 140409, which is the two-month version
            IF(w.r7 > 0, CAST(COALESCE(p.q8,0) + COALESCE(p.q9,0) AS DOUBLE) / w.r7, NULL) AS cover89
FROM        feat f
LEFT  JOIN  fwd  w ON w.sbrp_id = f.sbrp_id
LEFT  JOIN  pay  p ON p.sbrp_id = f.sbrp_id
-- THE SCREEN, identical to dcb_model's
WHERE   IF(f.r1>=1050000,1,0) + IF(f.r2>=1050000,1,0) + IF(f.r3>=1050000,1,0)
      + IF(f.r4>=1050000,1,0) + IF(f.r5>=1050000,1,0) + IF(f.r6>=1050000,1,0) >= 2
  AND   f.o1+f.o2+f.o3+f.o4+f.o5+f.o6 = 0
  AND   f.f_twoway = 0;


-- ---------------------------------------------------------------------------
-- L1  THE LAG CURVE. When do the bars actually land?
--
--     If the count is near zero at 140408 and climbs through 140410-140411,
--     the ladder is slow and the label month is in the wrong place. If 140408
--     already carries a normal share, a one-month label is observable.
-- ---------------------------------------------------------------------------
SELECT  first_tw                                        AS bar_month,
        COUNT(*)                                        AS n,
        1000.0 * COUNT(*) / (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_lag) AS per_mille
FROM    dwbi_temp40_db.dcb_lag
WHERE   first_tw > 0
GROUP BY first_tw
ORDER BY first_tw;


-- ---------------------------------------------------------------------------
-- L2  THE DECISIVE CROSS-TAB. For everyone first two-way barred in 140408,
--     what were they in 140407 - the draw month?
--
--     s7 = 2  they were active the month the draw lands, and the bar is a
--             genuine one-month event. The label works.
--     s7 = 3  they were already one-way barred when the draw landed. The
--             draw would have been granted to someone already in dunning,
--             and the label is measuring an episode that started earlier.
-- ---------------------------------------------------------------------------
SELECT  s7                                              AS status_in_draw_month,
        COUNT(*)                                        AS n,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()        AS share_pct
FROM    dwbi_temp40_db.dcb_lag
WHERE   first_tw = 140408
GROUP BY s7
ORDER BY n DESC;


-- ---------------------------------------------------------------------------
-- L3  THE LEAKAGE TEST. Did the labelled subscribers stop paying BEFORE the
--     feature window closed?
--
--     If the barred group paid near zero in 140405 and 140406 while everyone
--     else paid normally, then the features already contain the event and the
--     model is recognising rather than predicting.
-- ---------------------------------------------------------------------------
SELECT  IF(first_tw = 140408, 'barred in 140408', 'everyone else') AS grp,
        COUNT(*)                                        AS n,
        AVG(IF(q5 > 0, 1e0, 0e0))                       AS paid_any_140405,
        AVG(IF(q6 > 0, 1e0, 0e0))                       AS paid_any_140406,
        AVG(IF(q7 > 0, 1e0, 0e0))                       AS paid_any_140407,
        APPROX_PERCENTILE(q6, 0.5)                      AS med_paid_140406,
        APPROX_PERCENTILE(out6, 0.5)                    AS med_outstanding_140406,
        APPROX_PERCENTILE(out6, 0.9)                    AS p90_outstanding_140406
FROM    dwbi_temp40_db.dcb_lag
GROUP BY IF(first_tw = 140408, 'barred in 140408', 'everyone else');


-- ---------------------------------------------------------------------------
-- L4  LADDER OR NO LADDER. For everyone two-way barred anywhere in the six
--     months, did a one-way bar come first, and how many months before?
--
--     gap = 0 means the one-way and the two-way read in the same month, which
--     on a monthly snapshot means the whole escalation happened inside one
--     month. A large share at gap 0 explains how the screen lets these
--     subscribers through, and it is also the case where a one-month label
--     is legitimate.
-- ---------------------------------------------------------------------------
SELECT  IF(first_ow = 0, 'no one-way bar first', 'one-way bar first') AS path,
        IF(first_ow = 0, -1, (first_tw / 100 - first_ow / 100) * 12
                            + (MOD(first_tw, 100) - MOD(first_ow, 100)))  AS months_ow_to_tw,
        COUNT(*)                                        AS n,
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER ()        AS share_pct
FROM    dwbi_temp40_db.dcb_lag
WHERE   first_tw > 0
GROUP BY IF(first_ow = 0, 'no one-way bar first', 'one-way bar first'),
         IF(first_ow = 0, -1, (first_tw / 100 - first_ow / 100) * 12
                            + (MOD(first_tw, 100) - MOD(first_ow, 100)))
ORDER BY n DESC;


-- ---------------------------------------------------------------------------
-- L5  THE LABEL WITH NO LADDER IN IT. The draw rides on the 140407 bill and
--     is due on 140408, so the product event is simply: did that bill come
--     back.
--
--     This has no escalation lag by construction. The question it raises is
--     the opposite one - paying late is normal, so the rate at a strict
--     threshold will be far too high to be a default. 52 D3 found that only
--     coverage under 0.10 carries excess bar risk, so that is the threshold
--     to look at first.
-- ---------------------------------------------------------------------------
SELECT  'one month, by end of 140408'                   AS window,
        COUNT(cover8)                                   AS n_with_a_bill,
        AVG(IF(cover8 < 0.10, 1e0, 0e0))                AS rate_under_0_10,
        AVG(IF(cover8 < 0.50, 1e0, 0e0))                AS rate_under_0_50,
        AVG(IF(cover8 < 0.90, 1e0, 0e0))                AS rate_under_0_90,
        APPROX_PERCENTILE(cover8, 0.5)                  AS median_cover
FROM    dwbi_temp40_db.dcb_lag
UNION ALL
SELECT  'two months, by end of 140409',
        COUNT(cover89),
        AVG(IF(cover89 < 0.10, 1e0, 0e0)),
        AVG(IF(cover89 < 0.50, 1e0, 0e0)),
        AVG(IF(cover89 < 0.90, 1e0, 0e0)),
        APPROX_PERCENTILE(cover89, 0.5)
FROM    dwbi_temp40_db.dcb_lag;


-- ---------------------------------------------------------------------------
-- L6  RECONCILE. y_current must reproduce what 42 builds, or L0's screen has
--     drifted from dcb_model's and none of the above applies to the model.
--
--     n_current should read 19,215 and rate_pct should read 0.2208.
--
--     n_also_barred_later is the number the current label scores as GOOD that
--     a later label window would score as BAD. If it is large relative to
--     19,215, the one-month window is discarding most of the signal.
--
--     n_rows should read 8,701,085. n_absent_in_label_month is the gap between
--     this screen and dcb_model's, which inner-joins the label month and so
--     silently drops subscribers with no row in 140408. If that count is
--     large, dcb_model is not scoring the population it appears to.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                        AS n_rows,
        SUM(y_current)                                  AS n_current,
        100.0 * SUM(y_current) / COUNT(*)               AS rate_pct,
        SUM(IF(first_tw > 140408, 1, 0))                AS n_also_barred_later,
        SUM(IF(first_tw = 140407, 1, 0))                AS n_barred_in_draw_month,
        SUM(IF(first_tw > 0, 1, 0))                     AS n_barred_within_six_months,
        100.0 * SUM(IF(first_tw > 0, 1, 0)) / COUNT(*)  AS rate_six_months_pct,
        SUM(IF(s8 IS NULL, 1, 0))                       AS n_absent_in_label_month
FROM    dwbi_temp40_db.dcb_lag;

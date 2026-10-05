-- ============================================================================
--  HOW FAR CAN THE REVENUE BAR BE LOWERED?               (Trino/Presto)
--
--  WHY. 42_model_datasets.sql returned a surprise. On the SAME window
--  (140401..140406):
--
--      bar 1,700,000 (production)  5,100,390 subscribers at 0.5541 pct
--      bar 1,050,000               8,701,085 subscribers at 0.5213 pct
--
--  Lowering the bar 38 pct grew the population 70 pct and LOWERED the loss
--  rate. The 3,600,695 subscribers the lower bar admitted carry a forward
--  two-way rate of 0.4749 pct - 0.86x the core cohort, not higher. I had
--  predicted the rate would rise, assuming the marginal subscribers would be
--  poorer and riskier. That was wrong.
--
--  It fits what 44 found. The bar-history filter is the RISK screen: one-way
--  barred in the window runs 21x the cohort rate, two-way barred 65x. The
--  revenue bar is a CAPACITY screen - it says how much credit a subscriber can
--  carry, not how likely they are to default. A low-revenue subscriber who has
--  gone six months without a single bar has a small bill and a clean record,
--  which is a good credit risk for a small line.
--
--  SO THIS MEASURES THE WHOLE CURVE instead of two points on it, because it
--  bears on the 15,000 bn gap: at 500,000 Toman each, 9.3M subscribers is a
--  4,672 bn book, 3.2x short. If the bar can come down without the rate
--  rising, the gap closes by adding subscribers at right-sized lines rather
--  than by tripling everyone's line.
--
--  TWO WINDOWS, TWO PURPOSES:
--      B 140401..140406, label 140407..140410 - carries the LABEL, so the
--        risk per bar is measured here
--      C 140501..140506, no label - the LIVE window, so the population and
--        the book are counted here
--  The label is attached ONLY to window B. A window C subscriber is almost
--  certainly also present in 140407..140410, so an unconditioned join would
--  hand them an outcome that happened BEFORE their feature window - a
--  backwards-looking label that means nothing. The join carries
--  p.win = 'B_140401_140406' for exactly that reason.
--
--  THE AGGREGATE IS COMPUTED INSIDE THE CREATE, not persisted per subscriber.
--  perbar sits at one row per (window, subscriber, bar), which over 8 bars and
--  two windows of roughly 38M and 41M subscribers is about 630M rows. Nothing
--  downstream needs that grain, so the table is 16 rows instead and every
--  figure below reads off it.
--
--  WHAT THIS DOES NOT ANSWER. Whether a subscriber on 600,000 Rial a month can
--  carry a 500,000 Toman line. That is affordability, not risk. R3 sizes the
--  line against revenue rather than assuming it flat, because a flat line
--  across a population whose revenue spans an order of magnitude is the real
--  reason the book and the risk look mismatched.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_bar_risk;
CREATE TABLE dwbi_temp40_db.dcb_bar_risk WITH (format='PARQUET') AS
WITH sm AS (
    -- One row per subscriber-month. Flattened first, as always.
    SELECT   sbrp_id, month_key,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS rev,
             MAX(IF(sbrp_stat_id = 3, 1, 0))                      AS ow,
             MAX(IF(sbrp_stat_id = 4, 1, 0))                      AS tw
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140401 AND 140506
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id, month_key
),
tagged AS (
    SELECT  sm.*,
            IF(month_key BETWEEN 140401 AND 140406, 'B_140401_140406',
            IF(month_key BETWEEN 140501 AND 140506, 'C_140501_140506',
               NULL)) AS win
    FROM    sm
),
hist AS (
    -- The bar-history filters, per subscriber per window. These stay FIXED at
    -- every bar - only the revenue threshold moves - because 44 showed the
    -- bar history is where the risk discrimination actually lives.
    SELECT   sbrp_id, win,
             MAX(ow)  AS ow_any,
             MAX(tw)  AS tw_any,
             COUNT(*) AS n_months,
             SUM(rev) AS rev_total
    FROM     tagged
    WHERE    win IS NOT NULL
    GROUP BY sbrp_id, win
),
perbar AS (
    SELECT      t.win, t.sbrp_id, b.bar,
                SUM(IF(t.rev >= b.bar, 1, 0)) AS months_at_bar
    FROM        tagged t
    CROSS JOIN  UNNEST(ARRAY[300000, 500000, 700000, 1050000,
                             1400000, 1700000, 2200000, 3000000]) AS b (bar)
    WHERE       t.win IS NOT NULL
    GROUP BY    t.win, t.sbrp_id, b.bar
),
lab AS (
    SELECT   sbrp_id,
             MAX(IF(sbrp_stat_id = 4, 1, 0)) AS y
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140407, 140408, 140409, 140410)
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT      p.win,
            p.bar,
            COUNT(*)                                            AS screened,
            SUM(l.y)                                            AS n_bad,
            100.0 * SUM(l.y) / NULLIF(COUNT(l.y), 0)            AS bad_pct,
            COUNT(l.y)                                          AS n_judgeable,
            APPROX_PERCENTILE(h.rev_total / NULLIF(h.n_months,0), 0.1)
                                                                AS p10_month_rev,
            APPROX_PERCENTILE(h.rev_total / NULLIF(h.n_months,0), 0.5)
                                                                AS med_month_rev,
            APPROX_PERCENTILE(h.rev_total / NULLIF(h.n_months,0), 0.9)
                                                                AS p90_month_rev,
            -- a line at 2x average monthly revenue in Toman, floored at the
            -- stated 400,000 minimum and capped at 2,000,000
            SUM(LEAST(GREATEST(2.0 * (h.rev_total / NULLIF(h.n_months,0)) / 10,
                               400000), 2000000)) / 1e9         AS book_bn_toman,
            AVG(LEAST(GREATEST(2.0 * (h.rev_total / NULLIF(h.n_months,0)) / 10,
                               400000), 2000000))               AS avg_line_toman,
            100.0 * SUM(IF(2.0 * (h.rev_total / NULLIF(h.n_months,0)) / 10
                           < 400000, 1, 0)) / COUNT(*)          AS pct_on_the_floor
FROM        perbar    p
INNER JOIN  hist      h ON h.sbrp_id = p.sbrp_id AND h.win = p.win
-- the label belongs to window B ONLY; see the header
LEFT JOIN   lab       l ON l.sbrp_id = p.sbrp_id
                       AND p.win = 'B_140401_140406'
WHERE       p.months_at_bar >= 2
  AND       h.ow_any = 0
  AND       h.tw_any = 0
GROUP BY    p.win, p.bar
;

-- ---------------------------------------------------------------------------
-- R1  THE CURVE. Population and forward risk at each bar, screened on the
--     bar-history filters exactly as the product would.
--
--     CHECK FIRST, window B: bar 1,700,000 should return 5,100,390 at
--     0.5541 pct, and bar 1,050,000 should return 8,701,085 at 0.5213 pct.
--     Those are 43 D5 and 42 T1. If both match, this file agrees with both and
--     the rest of the curve can be trusted.
--
--     Then read DOWN bad_pct. Flat or falling as the bar comes down means the
--     revenue bar is not buying risk protection and can be lowered for volume.
--     A steep climb below some bar is the floor, and it should be read off
--     this table rather than guessed.
-- ---------------------------------------------------------------------------
SELECT   win, bar, screened, n_judgeable, n_bad, bad_pct,
         p10_month_rev, med_month_rev, p90_month_rev
FROM     dwbi_temp40_db.dcb_bar_risk
ORDER BY win, bar;

-- ---------------------------------------------------------------------------
-- R2  THE MARGINAL TRANCHE. Each step down the ladder adds subscribers; this
--     asks what THOSE are worth rather than what the blended population is.
--
--     A blended rate can fall while the marginal tranche is still worse than
--     the core - it only has to be better than the average. This is the number
--     that decides whether the next step down is worth taking. The measured
--     tranche between 1,700,000 and 1,050,000 came to 0.4749 pct, so this
--     should show about that between those two bars.
-- ---------------------------------------------------------------------------
SELECT   bar,
         screened,
         n_bad,
         bad_pct,
         screened - LAG(screened) OVER (ORDER BY bar DESC)   AS added_subs,
         n_bad    - LAG(n_bad)    OVER (ORDER BY bar DESC)   AS added_bad,
         100.0 * (n_bad - LAG(n_bad) OVER (ORDER BY bar DESC))
               / NULLIF(screened - LAG(screened)
                        OVER (ORDER BY bar DESC), 0)         AS marginal_bad_pct
FROM     dwbi_temp40_db.dcb_bar_risk
WHERE    win = 'B_140401_140406'
ORDER BY bar DESC;

-- ---------------------------------------------------------------------------
-- R3  THE BOOK ON THE LIVE WINDOW, with the line sized against revenue.
--
--     book_bn_toman is the total exposure at a line of 2x average monthly
--     revenue, floored at 400,000 Toman and capped at 2,000,000. Against the
--     15,000 bn target, this says which bar reaches it and what the average
--     line has to be.
--
--     Watch pct_on_the_floor. A high value means most of that population is
--     being offered the 400,000 minimum rather than a line their revenue
--     supports, which is where affordability stops being a modelling question.
-- ---------------------------------------------------------------------------
SELECT   bar,
         screened                                  AS live_subs,
         med_month_rev / 10                        AS med_month_toman,
         avg_line_toman,
         book_bn_toman,
         pct_on_the_floor,
         15000.0 / NULLIF(book_bn_toman, 0)        AS times_short_of_target
FROM     dwbi_temp40_db.dcb_bar_risk
WHERE    win = 'C_140501_140506'
ORDER BY bar;

-- ============================================================================
--  BILL SHOCK: the nearest thing in history to lending someone money.
--                                                            (Trino/Presto)
--
--  DCB sits on the SAME BILL as the telco charges, settled the same month. So
--  the product does not only extend credit - it RAISES THE BILL the subscriber
--  must pay, by the amount drawn:
--
--      bill before   ticket     bill after    shock
--        170,000     100,000      270,000     1.59x    at the screen bar
--        170,000     300,000      470,000     2.76x
--         28,948     300,000      328,948    11.36x    the median subscriber
--        500,000     300,000      800,000     1.60x    a heavier user
--
--  Every feature in the model describes a subscriber paying their NORMAL bill.
--  None of them describes one asked to pay 2.76x it. That is a payment-shock
--  question, not a credit-history question, and the model as built cannot
--  answer it.
--
--  BUT HISTORY CAN. Bills already move month to month - usage changes, bundles
--  change, roaming happens. So the data already contains the experiment:
--  subscribers whose bill jumped by some factor, and what they paid next
--  month. If coverage falls as the jump grows, that curve is the best estimate
--  available of what a DCB draw does, and reading it at shock = 1.6x and 2.8x
--  gives a defensible first loss rate for the 100,000 and 300,000 tickets.
--
--  WHAT THIS IS NOT, AND IT MATTERS MORE THAN IT FIRST LOOKS.
--
--  Everything above assumes the draw is NEW money on the bill. If a subscriber
--  already pays 300,000 a month for VOD from a bank card and now routes it
--  through DCB, their total outgoings do not change at all - the money was
--  always leaving, only the rail changed:
--
--       0 pct substitution  -> real shock 2.76x
--      50 pct substitution  -> real shock 1.88x
--     100 pct substitution  -> real shock 1.00x
--
--  We do not know the substitution share, because off-net spending is not in
--  this data. SO READ S1 TO S4 AS AN UPPER BOUND ON THE SHOCK, NOT AN
--  ESTIMATE OF IT. The true figure sits somewhere below, and nothing here says
--  where.
--
--  54_offnet_discovery.sql goes looking - the payment table may already carry
--  a type or channel column, and subscribers pay the operator about 40 pct
--  more than telco revenue explains, which is a gap worth identifying before
--  anyone concludes off-net life is invisible.
--
--  Separately: a bill that rose from the subscriber's own usage is not
--  identical to one we created. Both are chosen spending, which is why this is
--  a usable proxy at all. It narrows the unknown; a pilot closes it.
--
--  Population: the MODEL cohort - revenue at or above 1,050,000 Rial in 2 or
--  more of 140401..140406, never one-way and never two-way barred in that
--  window. Self-contained.
--
--  Jalali day counts: months 1-6 have 31 days, month 7 has 30.
--
--  TWO THINGS THE FIRST RUN TAUGHT US. Both are recorded here because both
--  will bite again otherwise.
--
--  1. EVERY RATE CAME BACK ROUNDED TO THE NEAREST TEN POINTS - 20, 30, 40, 50
--     and nothing between. In Trino the literal 1.0 is DECIMAL(2,1), not
--     DOUBLE, and avg() over a decimal KEEPS ITS SCALE: avg(DECIMAL(2,1)) is
--     DECIMAL(38,1), so the mean was rounded to one decimal place before being
--     multiplied by 100. A true 23.4 pct came back as 20. Every rate aggregate
--     in this project now uses 1e0 and 0e0, which are DOUBLE literals. The
--     percentiles were never affected, which is why med_cover carried the
--     finding while the pct columns were flat.
--
--  2. COVER AT A NORMAL BILL IS ABOUT 1.5, NOT 1.0. Subscribers pay half again
--     what "arpu minus tax" says they were billed, and 54 E5 shows the same
--     thing as a roughly constant RATIO across billing bands - 1.68, 1.66,
--     1.61, 1.41 - rather than a constant amount. A deposit or a prepayment
--     habit would be a constant amount. A constant ratio says arpu minus tax
--     is probably NOT the whole invoice, more like 60 pct of it.
--
--     shock is a ratio, so it is unaffected - both sides scale together. cover
--     is inflated by that factor, so a 0.25 cut is really about 0.16 of the
--     true invoice. The thresholds below now run to 1.00 and 1.50 as well, and
--     p10/p25 are reported, so the shape can be read without committing to one
--     cut. Until 54 E3 says which column is the real invoice total, read cover
--     RELATIVE to the normal band rather than against 1.0.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_shock;
CREATE TABLE dwbi_temp40_db.dcb_shock WITH (format='PARQUET') AS
WITH bill AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140401), 0) AS b1,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140402), 0) AS b2,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140403), 0) AS b3,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140404), 0) AS b4,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140405), 0) AS b5,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140406), 0) AS b6,
            MAX(IF(sbrp_stat_id = 3, 1, 0))                AS f_oneway,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                AS f_twoway
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140401 AND 140406
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
),
pay AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(pmnt_amt,0))
                     FILTER (WHERE day_key BETWEEN 14040501 AND 14040531), 0) AS p5,
            COALESCE(SUM(COALESCE(pmnt_amt,0))
                     FILTER (WHERE day_key BETWEEN 14040601 AND 14040631), 0) AS p6,
            COALESCE(SUM(COALESCE(pmnt_amt,0))
                     FILTER (WHERE day_key BETWEEN 14040701 AND 14040730), 0) AS p7
    FROM    dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE   day_key BETWEEN 14040501 AND 14040730
    GROUP BY sbrp_id
),
bars AS (
    -- The outcome that actually matters, carried alongside the payment ratio.
    -- 52 D3 showed why this is needed: among subscribers who underpaid in the
    -- repayment month, only the bottom band - cover under 0.10 - carried any
    -- excess risk at all, at 8.3x. The 0.10-1.00 bands sat at 0.16-0.23 pct,
    -- indistinguishable from subscribers who paid in full. So a cover ratio is
    -- largely PAYMENT RHYTHM, not credit failure, and a premium measured on it
    -- measures rhythm too.
    SELECT   sbrp_id,
             MAX(IF(month_key = 140407 AND sbrp_stat_id = 4, 1, 0)) AS tw07,
             MAX(IF(month_key = 140408 AND sbrp_stat_id = 4, 1, 0)) AS tw08,
             MAX(IF(month_key = 140409 AND sbrp_stat_id = 4, 1, 0)) AS tw09
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140407 AND 140409
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
scr AS (
    SELECT  b.*, COALESCE(p.p5,0) AS p5, COALESCE(p.p6,0) AS p6, COALESCE(p.p7,0) AS p7,
            COALESCE(bb.tw07,0) AS tw07, COALESCE(bb.tw08,0) AS tw08,
            COALESCE(bb.tw09,0) AS tw09
    FROM    bill b
    LEFT JOIN pay p ON p.sbrp_id = b.sbrp_id
    LEFT JOIN bars bb ON bb.sbrp_id = b.sbrp_id
    WHERE   IF(b.b1>=1050000,1,0) + IF(b.b2>=1050000,1,0) + IF(b.b3>=1050000,1,0)
          + IF(b.b4>=1050000,1,0) + IF(b.b5>=1050000,1,0) + IF(b.b6>=1050000,1,0) >= 2
      AND   b.f_oneway = 0
      AND   b.f_twoway = 0
)
-- Three observations per subscriber. Each one is: a bill month, the average of
-- the THREE months before it as the baseline the subscriber is used to, and
-- what they paid the month after. Stacking them triples the sample and lets a
-- subscriber appear in several shock bands, which is what we want - the
-- comparison is within a person as much as between people.
--
-- SHOCK AND COVER ARE COMPUTED HERE, ONCE, AND NOWHERE ELSE.
--
-- The first version of this file divided in twenty places across four queries,
-- each guarded inline, and one of those guards tested the wrong variable:
--   APPROX_PERCENTILE(IF(billed > 0, billed / base, NULL), ...)
-- tests billed and divides by base, so any subscriber with no billing in the
-- three baseline months but a bill in the measured month divided by zero. The
-- rest leaned on AND short-circuiting and on nested IF laziness, neither of
-- which SQL guarantees and neither of which an optimizer is obliged to honour.
--
-- Two guarded divisions here, none below. A baseline of zero or less gives a
-- NULL shock - not an error, and not a silent zero - and a month with no bill
-- gives a NULL cover. Both then propagate as "unknown" instead of as "fine".
--
-- tw_later is a two-way bar in the TWO MONTHS AFTER the repayment month, and
-- obs_ok says whether that window is observable. For bill month 140404 the
-- window is 140406-140407, and 140406 sits inside the screen window where
-- every barred subscriber was excluded by construction - so its bar rate is
-- zero by definition and the row is marked unobservable rather than counted
-- as clean. Only 140405 and 140406 carry a usable outcome.
SELECT   sbrp_id, bill_month, billed, base, paid_next, tw_later, obs_ok,
         IF(base   > 0, billed    / base,   NULL) AS shock,
         IF(billed > 0, paid_next / billed, NULL) AS cover
FROM     (
    SELECT sbrp_id, 140404 AS bill_month, b4 AS billed, (b1+b2+b3)/3.0 AS base,
           p5 AS paid_next, CAST(NULL AS INTEGER) AS tw_later, 0 AS obs_ok FROM scr
    UNION ALL
    SELECT sbrp_id, 140405, b5, (b2+b3+b4)/3.0, p6, GREATEST(tw07, tw08), 1 FROM scr
    UNION ALL
    SELECT sbrp_id, 140406, b6, (b3+b4+b5)/3.0, p7, GREATEST(tw08, tw09), 1 FROM scr
);

-- ---------------------------------------------------------------------------
-- S1  THE CURVE. This is the whole point of the file.
--
--     Read pct_short_025 down the bands: the share who paid less than a
--     quarter of what they were billed. If it climbs with the shock, the
--     effect is real and the size of the climb is the DCB risk premium.
--
--     The bands to read for this product:
--        1.50 - 2.00   a 100,000 ticket on a bill near the screen bar
--        2.00 - 3.00   a 300,000 ticket on a bill near the screen bar
--        over 3.00     a 300,000 ticket on a light user - which is the
--                      argument for sizing the limit from their own bill
--
--     If the curve is FLAT, subscribers absorb a larger bill without failing
--     more and the DCB premium over the base rate is small. That is a real and
--     reassuring finding, not a null result.
--
--     n counts every month in the band; n_with_bill counts those that could
--     default at all. The rates are over n_with_bill - a month with no bill is
--     dropped rather than scored as good, which would dilute every rate.
-- ---------------------------------------------------------------------------
SELECT   IF(shock IS NULL, 'z  no baseline',
         IF(shock < 0.80, 'a  under 0.80  bill fell',
         IF(shock < 1.25, 'b  0.80 - 1.25  normal',
         IF(shock < 1.50, 'c  1.25 - 1.50',
         IF(shock < 2.00, 'd  1.50 - 2.00  a 100k ticket',
         IF(shock < 3.00, 'e  2.00 - 3.00  a 300k ticket',
                          'f  over 3.00  a light user')))))) AS shock_band,
         COUNT(*)                                                AS n,
         COUNT(cover)                                            AS n_with_bill,
         APPROX_PERCENTILE(shock, 0.5)                           AS med_shock,
         APPROX_PERCENTILE(billed, 0.5) / 10                     AS med_billed_toman,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 0.25, 1e0, 0e0))) AS pct_short_025,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 0.50, 1e0, 0e0))) AS pct_short_050,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 1.00, 1e0, 0e0))) AS pct_short_100,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 1.50, 1e0, 0e0))) AS pct_short_150,
         APPROX_PERCENTILE(cover, 0.10)                          AS p10_cover,
         APPROX_PERCENTILE(cover, 0.25)                          AS p25_cover,
         APPROX_PERCENTILE(cover, 0.5)                           AS med_cover
FROM     dwbi_temp40_db.dcb_shock
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- S2  THE SAME CURVE, BUT WITHIN A SUBSCRIBER.
--
--     S1 mixes two things: subscribers whose bill jumped, and subscribers who
--     are simply different. A light user whose bill triples is not the same
--     person as a heavy user whose bill is steady. This restricts to
--     subscribers who appear in BOTH a normal and a shocked month, so the
--     comparison is the same people in two states.
--
--     If S2's gradient is much flatter than S1's, most of S1 was composition -
--     who gets a big bill, not what a big bill does - and the DCB premium is
--     smaller than S1 suggests. Trust S2.
-- ---------------------------------------------------------------------------
WITH tagged AS (
    SELECT   sbrp_id, billed, shock, cover,
             IF(shock >= 1.50, 1, 0)                    AS shocked,
             IF(shock BETWEEN 0.80 AND 1.25, 1, 0)      AS normal
    FROM     dwbi_temp40_db.dcb_shock
    WHERE    shock IS NOT NULL
),
both AS (
    SELECT   sbrp_id
    FROM     tagged
    GROUP BY sbrp_id
    HAVING   MAX(shocked) = 1 AND MAX(normal) = 1
)
SELECT   IF(t.shocked = 1, 'shocked  1.50x and over', 'normal   0.80 - 1.25x') AS state,
         COUNT(*)                                                 AS n_months,
         COUNT(DISTINCT t.sbrp_id)                                AS n_subs,
         COUNT(t.cover)                                           AS n_with_bill,
         100.0 * AVG(IF(t.cover IS NULL, NULL, IF(t.cover < 0.25, 1e0, 0e0))) AS pct_short_025,
         APPROX_PERCENTILE(t.cover, 0.5)                          AS med_cover
FROM     tagged t
INNER JOIN both b ON b.sbrp_id = t.sbrp_id
WHERE    t.shocked = 1 OR t.normal = 1
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- S3  DOES A BIGGER BILL HURT A LIGHT USER MORE THAN A HEAVY ONE?
--
--     The test of the whole limit-ladder design. If the shortfall rate at a
--     given SHOCK is similar across bill sizes, then the ratio is what matters
--     and limits should be a MULTIPLE of the subscriber's bill. If light users
--     fail more at the same ratio, the absolute amount matters too and the
--     ladder needs a floor on billing, not just a cap on limit.
-- ---------------------------------------------------------------------------
SELECT   IF(base < 300000,   'a  under 30k Toman',
         IF(base < 1000000,  'b  30k - 100k',
         IF(base < 3000000,  'c  100k - 300k',
                             'd  over 300k'))) AS baseline_bill,
         IF(shock >= 2.00, 'shock 2x+',
         IF(shock >= 1.50, 'shock 1.5-2x', 'normal')) AS shock_band,
         COUNT(*)                                                 AS n,
         COUNT(cover)                                             AS n_with_bill,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 0.25, 1e0, 0e0))) AS pct_short_025
FROM     dwbi_temp40_db.dcb_shock
WHERE    shock IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;

-- ---------------------------------------------------------------------------
-- S4  THE NUMBER TO QUOTE, IF S1 AND S2 AGREE.
--
--     base_rate is the shortfall rate at a normal bill. shock_rate is the rate
--     in the band a 300,000 ticket puts a screen-bar subscriber in. premium is
--     the ratio - the multiple by which a raised bill lifts the chance of a
--     missed payment, measured rather than assumed.
--
--     Applied to a book: expected shortfall = the model's PD x premium. Say it
--     with the substitution caveat attached, every time: if subscribers are
--     moving spending they already had onto the bill rather than adding to it,
--     the true premium is lower than this and nothing here says how much.
-- ---------------------------------------------------------------------------
SELECT   100.0 * AVG(IF(cover < 0.25, 1e0, 0e0))
             FILTER (WHERE shock BETWEEN 0.80 AND 1.25 AND cover IS NOT NULL) AS base_rate_pct,
         100.0 * AVG(IF(cover < 0.25, 1e0, 0e0))
             FILTER (WHERE shock BETWEEN 2.00 AND 3.00 AND cover IS NOT NULL) AS shock_rate_pct,
         AVG(IF(cover < 0.25, 1e0, 0e0))
             FILTER (WHERE shock BETWEEN 2.00 AND 3.00 AND cover IS NOT NULL)
         / NULLIF(AVG(IF(cover < 0.25, 1e0, 0e0))
             FILTER (WHERE shock BETWEEN 0.80 AND 1.25 AND cover IS NOT NULL), 0) AS premium,
         COUNT(*) FILTER (WHERE shock BETWEEN 0.80 AND 1.25 AND cover IS NOT NULL) AS n_normal,
         COUNT(*) FILTER (WHERE shock BETWEEN 2.00 AND 3.00 AND cover IS NOT NULL) AS n_shocked
FROM     dwbi_temp40_db.dcb_shock;

-- ---------------------------------------------------------------------------
-- S5  THE PREMIUM, MEASURED ON A BAR INSTEAD OF ON A RATIO.
--
--     This is the number to quote. S1 to S4 measure payment coverage, and 52
--     D3 established that coverage between 0.10 and 1.00 carries no excess
--     risk at all - it is people paying in lumps. A premium read off coverage
--     is therefore part rhythm. A two-way bar is the operator's own judgement
--     that a subscriber did not pay, and it does not move with rhythm.
--
--     Restricted to obs_ok = 1, where the two-month outcome window sits
--     entirely outside the screen window. Expect roughly 2 in 3 of the rows in
--     S1, and a base rate near 0.22 pct rather than near 18.
--
--     premium_vs_normal is what a raised bill does to the chance of a bar. It
--     is the figure to multiply the model's PD by when sizing DCB loss - with
--     the substitution caveat attached every time.
-- ---------------------------------------------------------------------------
SELECT   IF(shock IS NULL, 'z  no baseline',
         IF(shock < 0.80, 'a  under 0.80  bill fell',
         IF(shock < 1.25, 'b  0.80 - 1.25  normal',
         IF(shock < 1.50, 'c  1.25 - 1.50',
         IF(shock < 2.00, 'd  1.50 - 2.00  a 100k ticket',
         IF(shock < 3.00, 'e  2.00 - 3.00  a 300k ticket',
                          'f  over 3.00  a light user')))))) AS shock_band,
         COUNT(*)                                            AS n,
         SUM(tw_later)                                       AS n_twoway,
         100.0 * AVG(CAST(tw_later AS DOUBLE))               AS pct_twoway,
         APPROX_PERCENTILE(billed, 0.5) / 10                 AS med_billed_toman
FROM     dwbi_temp40_db.dcb_shock
WHERE    obs_ok = 1
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- S6  AND WITHIN A SUBSCRIBER, on the same outcome. S2 did this for coverage;
--     this does it for the bar. If the within-subscriber premium here is close
--     to S5's between-subscriber one, the effect is causal rather than
--     composition, and THIS is the multiple to use.
-- ---------------------------------------------------------------------------
WITH tagged AS (
    SELECT   sbrp_id, tw_later,
             IF(shock >= 1.50, 1, 0)               AS shocked,
             IF(shock BETWEEN 0.80 AND 1.25, 1, 0) AS normal
    FROM     dwbi_temp40_db.dcb_shock
    WHERE    shock IS NOT NULL AND obs_ok = 1
),
both AS (
    SELECT   sbrp_id FROM tagged GROUP BY sbrp_id
    HAVING   MAX(shocked) = 1 AND MAX(normal) = 1
)
SELECT   IF(t.shocked = 1, 'shocked  1.50x and over', 'normal   0.80 - 1.25x') AS state,
         COUNT(*)                                            AS n_months,
         COUNT(DISTINCT t.sbrp_id)                           AS n_subs,
         SUM(t.tw_later)                                     AS n_twoway,
         100.0 * AVG(CAST(t.tw_later AS DOUBLE))             AS pct_twoway
FROM     tagged t
INNER JOIN both b ON b.sbrp_id = t.sbrp_id
WHERE    t.shocked = 1 OR t.normal = 1
GROUP BY 1
ORDER BY 1;

-- ============================================================================
--  S7  DOES THE CURVE STILL HOLD A YEAR LATER?
--
--  Everything above runs on 140401..140406. Since then prices rose twice by
--  about 30 pct each and billing is up more than 50 pct, so the deflator from
--  that window to today sits somewhere in 1.50x to 1.69x.
--
--  WHAT THAT DOES AND DOES NOT TOUCH. shock is billed over base and cover is
--  paid over billed, both sides from the same window, so inflation cancels and
--  every ratio above stands unchanged - the premium, the 8.3x lift, the rates.
--  What does NOT survive is every absolute Toman figure: S3's baseline bands
--  were cut in 1404 money, so "100k - 300k" there is roughly 150,000 to
--  450,000 today, and a subscriber billing 170,000 today sits in that band
--  rather than in the top one. Reading S3's bands as today's Toman would
--  overstate the risk for exactly the subscribers this product targets.
--
--  WHY THIS CANNOT SIMPLY BE RE-RUN ON 1405. The full analysis needs a bill
--  month, the payment month after it, and two further months for the bar to
--  land - about nine months of history. The last window with all of that is
--  1404. On 1405 the coverage curve can still be measured, which is the part
--  that matters for stability: if it has the same shape at the same shock
--  ratios, the 1404 premium transfers; if it has flattened or steepened, it
--  does not and the premium needs re-measuring when 140507 onward lands.
--
--  Screen is the PRODUCTION bar here, 1,700,000 Rial, matching dcb_score -
--  not the 1,050,000 used for the 1404 cohort.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_shock_1405;
CREATE TABLE dwbi_temp40_db.dcb_shock_1405 WITH (format='PARQUET') AS
WITH bill AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140501), 0) AS b1,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140502), 0) AS b2,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140503), 0) AS b3,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140504), 0) AS b4,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140505), 0) AS b5,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140506), 0) AS b6,
            MAX(IF(sbrp_stat_id = 3, 1, 0))                AS f_oneway,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                AS f_twoway
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140501 AND 140506
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
),
pay AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(pmnt_amt,0))
                     FILTER (WHERE day_key BETWEEN 14050501 AND 14050531), 0) AS p5,
            COALESCE(SUM(COALESCE(pmnt_amt,0))
                     FILTER (WHERE day_key BETWEEN 14050601 AND 14050631), 0) AS p6
    FROM    dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE   day_key BETWEEN 14050501 AND 14050631
    GROUP BY sbrp_id
),
scr AS (
    SELECT  b.*, COALESCE(p.p5,0) AS p5, COALESCE(p.p6,0) AS p6
    FROM    bill b
    LEFT JOIN pay p ON p.sbrp_id = b.sbrp_id
    WHERE   IF(b.b1>=1700000,1,0) + IF(b.b2>=1700000,1,0) + IF(b.b3>=1700000,1,0)
          + IF(b.b4>=1700000,1,0) + IF(b.b5>=1700000,1,0) + IF(b.b6>=1700000,1,0) >= 2
      AND   b.f_oneway = 0
      AND   b.f_twoway = 0
)
SELECT   sbrp_id, bill_month, billed, base, paid_next,
         IF(base   > 0, billed    / base,   NULL) AS shock,
         IF(billed > 0, paid_next / billed, NULL) AS cover
FROM     (
    SELECT sbrp_id, 140504 AS bill_month, b4 AS billed, (b1+b2+b3)/3.0 AS base, p5 AS paid_next FROM scr
    UNION ALL
    SELECT sbrp_id, 140505, b5, (b2+b3+b4)/3.0, p6 FROM scr
);

-- ---------------------------------------------------------------------------
--  Compare band for band against S1. The columns to watch are med_cover and
--  pct_short_025 - if the fall from the normal band to the 2.00-3.00 band is
--  about the same size as in 1404, the curve is stable and the premium
--  transfers. The absolute med_billed_toman SHOULD be 1.5x to 1.7x higher;
--  that is the inflation, not a change in behaviour.
-- ---------------------------------------------------------------------------
SELECT   IF(shock IS NULL, 'z  no baseline',
         IF(shock < 0.80, 'a  under 0.80  bill fell',
         IF(shock < 1.25, 'b  0.80 - 1.25  normal',
         IF(shock < 1.50, 'c  1.25 - 1.50',
         IF(shock < 2.00, 'd  1.50 - 2.00  a 100k ticket',
         IF(shock < 3.00, 'e  2.00 - 3.00  a 300k ticket',
                          'f  over 3.00  a light user')))))) AS shock_band,
         COUNT(*)                                                AS n,
         COUNT(cover)                                            AS n_with_bill,
         APPROX_PERCENTILE(shock, 0.5)                           AS med_shock,
         APPROX_PERCENTILE(billed, 0.5) / 10                     AS med_billed_toman,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 0.25, 1e0, 0e0))) AS pct_short_025,
         100.0 * AVG(IF(cover IS NULL, NULL, IF(cover < 0.50, 1e0, 0e0))) AS pct_short_050,
         APPROX_PERCENTILE(cover, 0.25)                          AS p25_cover,
         APPROX_PERCENTILE(cover, 0.5)                           AS med_cover
FROM     dwbi_temp40_db.dcb_shock_1405
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- S8  THE PAIRED TEST, SPLIT BY HOW BIG THE SHOCK WAS.
--
--     S6 pools every shock at 1.50x and over and finds nothing. That is the
--     right headline, but it could hide a real effect at the extreme: if most
--     of the shocked arm sits in the 1.50-2.00 band, a 3x-and-over effect
--     would be averaged away. This splits the same pairs by the size of the
--     subscriber's own shocked month.
--
--     The design is exactly paired. obs_ok leaves two rows per subscriber, so
--     a subscriber who appears in both states contributes precisely one normal
--     month and one shocked month - which is why S6's n_months and n_subs are
--     identical. Each row below is therefore a within-person comparison, and
--     the only thing differing between the two months is the bill.
--
--     n_only_shocked and n_only_normal are the DISCORDANT pairs - subscribers
--     barred after one month but not the other. They are the whole of the
--     evidence: concordant pairs carry none. McNemar's test on those two
--     counts is the correct paired test, and with roughly 1,000 of them per
--     band it can detect a premium of about 1.2x. If n_only_shocked and
--     n_only_normal are close in every band, a bigger bill does not cause a
--     default at any size, and the between-subscriber gradient in S5 is
--     selection from top to bottom.
-- ---------------------------------------------------------------------------
WITH t AS (
    SELECT   sbrp_id, tw_later, shock,
             IF(shock >= 1.50, 1, 0)               AS shocked,
             IF(shock BETWEEN 0.80 AND 1.25, 1, 0) AS normal
    FROM     dwbi_temp40_db.dcb_shock
    WHERE    shock IS NOT NULL AND obs_ok = 1
),
pairs AS (
    SELECT   sbrp_id,
             MAX(IF(shocked = 1, shock, NULL))     AS shock_level,
             MAX(IF(shocked = 1, tw_later, 0))     AS tw_shocked,
             MAX(IF(normal  = 1, tw_later, 0))     AS tw_normal
    FROM     t
    GROUP BY sbrp_id
    HAVING   MAX(shocked) = 1 AND MAX(normal) = 1
)
SELECT   IF(shock_level < 2.00, 'a  1.50 - 2.00  a 100k ticket',
         IF(shock_level < 3.00, 'b  2.00 - 3.00  a 300k ticket',
                                'c  over 3.00  a light user')) AS shock_band,
         COUNT(*)                                              AS n_pairs,
         SUM(tw_normal)                                        AS n_bar_normal,
         SUM(tw_shocked)                                       AS n_bar_shocked,
         100.0 * AVG(CAST(tw_normal  AS DOUBLE))               AS pct_normal,
         100.0 * AVG(CAST(tw_shocked AS DOUBLE))               AS pct_shocked,
         AVG(CAST(tw_shocked AS DOUBLE))
           / NULLIF(AVG(CAST(tw_normal AS DOUBLE)), 0)         AS premium,
         SUM(IF(tw_shocked = 1 AND tw_normal = 0, 1, 0))       AS n_only_shocked,
         SUM(IF(tw_normal  = 1 AND tw_shocked = 0, 1, 0))      AS n_only_normal
FROM     pairs
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- S9  THE ONE CONFOUND S8 CANNOT RULE OUT BY ITSELF.
--
--     The two months in a pair do NOT share an outcome window. Bill month
--     140405 is judged on bars in 140407-140408; bill month 140406 on
--     140408-140409. They overlap in one month only.
--
--     So if bar rates drift over those months - and if a subscriber's SHOCKED
--     month is systematically the earlier or the later of the two, which it
--     easily could be, since bills tend to move in one direction across a
--     season - then part of S8's result is a calendar effect rather than a
--     bill effect. S8 found the shocked month SAFER at over 3x; a falling bar
--     rate across 140407 to 140409 would manufacture exactly that.
--
--     Part one reads the bar rate by bill month, so any drift is visible.
--     Part two repeats S8's paired test stratified by WHICH month was the
--     shocked one. If the premium is near 1.00 in both strata, the calendar is
--     not driving it and S8 stands. If the two strata disagree sharply, it is,
--     and the comparison needs months with a common outcome window.
-- ---------------------------------------------------------------------------
SELECT   bill_month,
         COUNT(*)                                    AS n,
         SUM(tw_later)                               AS n_twoway,
         100.0 * AVG(CAST(tw_later AS DOUBLE))       AS pct_twoway,
         APPROX_PERCENTILE(shock, 0.5)               AS med_shock
FROM     dwbi_temp40_db.dcb_shock
WHERE    obs_ok = 1
GROUP BY bill_month
ORDER BY bill_month;

WITH t AS (
    SELECT   sbrp_id, bill_month, tw_later, shock,
             IF(shock >= 1.50, 1, 0)               AS shocked,
             IF(shock BETWEEN 0.80 AND 1.25, 1, 0) AS normal
    FROM     dwbi_temp40_db.dcb_shock
    WHERE    shock IS NOT NULL AND obs_ok = 1
),
pairs AS (
    SELECT   sbrp_id,
             MAX(IF(shocked = 1, bill_month, NULL)) AS shocked_month,
             MAX(IF(shocked = 1, tw_later, 0))      AS tw_shocked,
             MAX(IF(normal  = 1, tw_later, 0))      AS tw_normal
    FROM     t
    GROUP BY sbrp_id
    HAVING   MAX(shocked) = 1 AND MAX(normal) = 1
)
SELECT   shocked_month,
         COUNT(*)                                              AS n_pairs,
         100.0 * AVG(CAST(tw_normal  AS DOUBLE))               AS pct_normal,
         100.0 * AVG(CAST(tw_shocked AS DOUBLE))               AS pct_shocked,
         AVG(CAST(tw_shocked AS DOUBLE))
           / NULLIF(AVG(CAST(tw_normal AS DOUBLE)), 0)         AS premium,
         SUM(IF(tw_shocked = 1 AND tw_normal = 0, 1, 0))       AS n_only_shocked,
         SUM(IF(tw_normal  = 1 AND tw_shocked = 0, 1, 0))      AS n_only_normal
FROM     pairs
GROUP BY shocked_month
ORDER BY shocked_month;

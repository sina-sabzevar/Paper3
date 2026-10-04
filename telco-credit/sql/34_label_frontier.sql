-- ============================================================================
--  THE LABEL FRONTIER: HOW MUCH VOLUME EACH POINT OF BAD RATE BUYS
--
--  Reads dcb_sample_base, built by C0 in 33_send_me_this.sql. Nothing else to
--  run first.
--
--  WHAT THE MEASURED CROSS-TAB ALREADY SETTLED
--
--  From sheet C, screening on revenue months and labelling on payment months:
--
--     screen        eligible   bad: pay>=1   bad: pay>=2   bad: pay>=3
--     rev >= 1    12,385,941        20.4 pct      42.1 pct      63.1 pct
--     rev >= 2     9,017,158        14.9 pct      28.8 pct      50.9 pct
--     rev >= 3     6,671,575        11.8 pct      21.5 pct      39.5 pct
--     rev >= 4     4,424,088         9.6 pct      17.0 pct      30.4 pct
--
--  Loosening from rev>=4 to rev>=2 buys 4,593,070 subscribers for 5.3 points
--  of bad rate - about 86 million subscribers per point. Loosening again to
--  rev>=1 buys 7,961,853 more for 10.8 points, which is a worse trade.
--
--  WHAT IT CANNOT SETTLE, AND WHY THIS FILE EXISTS
--
--  C counts MONTHS over 170,000. The loan is repaid out of the four-month
--  TOTAL, not out of any single month. A subscriber who pays 500,000 once and
--  nothing for three months satisfies "pay >= 1 of 4" and defaults on
--  instalments two, three and four. So the loosest label available from C is
--  also the least meaningful one, and the label that matches the product has
--  to be sum-based.
--
--  L1 measures that: the four-month payment total by revenue band, and the
--  share of each band clearing ITS OWN ticket's four instalments. The
--  threshold differs by band because the ticket does - sizing every band
--  against one number would reject the small tickets and flatter the large.
--
--  TICKETS, at 12 instalments and a 50 pct affordability stance, from the
--  measured band medians:
--
--     band 4   median revenue 397,193   ticket 2,250,000   instalment 195,000
--     band 3   median revenue 259,529   ticket 1,500,000   instalment 130,000
--     band 2   median revenue 190,601   ticket 1,000,000   instalment  86,667
--
--  Four instalments' worth, which is what a four-month window can observe:
--     band 4   780,000     band 3   520,000     band 2   346,668   Toman
--  In Rial: 7,800,000 / 5,200,000 / 3,466,680.
--
--  TWO THINGS THIS MEASUREMENT IS NOT
--
--  1. It is CONTEMPORANEOUS, not predictive. dcb_sample_base holds revenue
--     and payment for the same four months, so a bad rate computed from it
--     describes an association. A model predicts the NEXT months from the
--     PREVIOUS ones, which is harder, so every figure here is a floor on what
--     a real model will face rather than an estimate of it.
--  2. It observes 4 instalments of 12. A subscriber can carry four and fail
--     the eighth. The four-month window is what the data allows today; a
--     12-month outcome needs a T0 twelve months back, which the 140301..140506
--     coverage does allow and is worth building next.
--
--  PAYMENTS ARE q1a..q4a, ALL STATUSES. bllg_pmnt_stat_id = 2 holds 61.2 pct
--  of payment value and status 1 holds 38.7 pct, so the filter this project
--  carried throughout discards over a third of the money. Measured: 11,202,782
--  subscribers clear two months on all statuses against 7,623,016 on status 2.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- L1  The four-month payment total by revenue band, against each band's own
--     four-instalment requirement.
-- ---------------------------------------------------------------------------
SELECT  months_rev                                              AS band,
        COUNT(*)                                                AS subscribers,
        APPROX_PERCENTILE(rev_4m, 0.5)  / 10000                 AS med_rev_4m_k,
        APPROX_PERCENTILE(pay_4m, 0.25) / 10000                 AS p25_pay_4m_k,
        APPROX_PERCENTILE(pay_4m, 0.50) / 10000                 AS p50_pay_4m_k,
        APPROX_PERCENTILE(pay_4m, 0.75) / 10000                 AS p75_pay_4m_k,
        -- the band's own requirement: 4 instalments of its own ticket
        COUNT(*) FILTER (WHERE pay_4m >= need)                  AS clears_own,
        100.0 * COUNT(*) FILTER (WHERE pay_4m >= need)
              / COUNT(*)                                        AS clears_own_pct,
        -- and against one flat requirement, for comparison
        COUNT(*) FILTER (WHERE pay_4m >= 3466680)                AS clears_347k,
        COUNT(*) FILTER (WHERE pay_4m >= 5200000)                AS clears_520k,
        COUNT(*) FILTER (WHERE pay_4m >= 7800000)                AS clears_780k
FROM (
    SELECT  IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
          + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0)       AS months_rev,
            r1 + r2 + r3 + r4                                   AS rev_4m,
            q1a + q2a + q3a + q4a                               AS pay_4m,
            -- four instalments of the band's own ticket, in Rial
            IF(IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
             + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0) = 4, 7800000,
               IF(IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
                + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0) = 3, 5200000,
                  3466680))                                     AS need
    FROM    dwbi_temp40_db.dcb_sample_base
) t
GROUP BY months_rev
ORDER BY months_rev;

-- ---------------------------------------------------------------------------
-- L2  THE FRONTIER ITSELF. One row per candidate screen, with the sum-based
--     bad rate. This is the table the label decision comes off.
--
--     Read volume against 3,000,000 and bad_rate_pct together: the model's
--     job is to select the safest 3,000,000 from whatever this screen admits,
--     so a screen admitting three times the target at a moderate bad rate
--     beats a tight screen admitting barely enough.
-- ---------------------------------------------------------------------------
SELECT  min_rev_months                                          AS screen,
        COUNT(*)                                                AS eligible,
        COUNT(*) FILTER (WHERE pay_4m >= need)                  AS good,
        100.0 * COUNT(*) FILTER (WHERE pay_4m <  need)
              / COUNT(*)                                        AS bad_rate_pct,
        100.0 * COUNT(*) / 3000000.0                            AS pct_of_target
FROM (
    SELECT  m.months_rev, m.pay_4m, m.need, s.min_rev_months
    FROM (
        SELECT  IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
              + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0)   AS months_rev,
                q1a + q2a + q3a + q4a                           AS pay_4m,
                IF(IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
                 + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0) = 4, 7800000,
                   IF(IF(r1 >= 1700000,1,0) + IF(r2 >= 1700000,1,0)
                    + IF(r3 >= 1700000,1,0) + IF(r4 >= 1700000,1,0) = 3, 5200000,
                      3466680))                                 AS need
        FROM    dwbi_temp40_db.dcb_sample_base
    ) m
    CROSS JOIN UNNEST(ARRAY[1, 2, 3, 4]) AS s (min_rev_months)
    WHERE   m.months_rev >= s.min_rev_months
) u
GROUP BY min_rev_months
ORDER BY min_rev_months;

-- ============================================================================
--  EVERY NUMBER THE MANAGER DASHBOARD NEEDS                  (Trino/Presto)
--
--  WHAT THIS IS FOR
--
--  The model has not been refit for the one-month product and the label
--  question in 55 is open, so nothing here uses a model score. Every figure
--  is a count or a measured rate, which is also why a business reader can
--  check it.
--
--  THE DESIGN, AND IT MATTERS
--
--    COUNTS come from 140501..140506, the live window. That is who we would
--    lend to today.
--    RATES come from 140401..140406, because a rate needs months AFTER the
--    window to observe the outcome, and 1405 does not have them yet.
--
--  The two windows are screened at different revenue bars on purpose -
--  1,700,000 Rial in 1405 and 1,050,000 in 1404 - because there were two
--  price rises of about 30 pct between them. Screening both at the same
--  nominal bar would compare a rich 1404 cohort against an ordinary 1405 one.
--
--  THE OUTCOME WINDOW IS THREE MONTHS, NOT ONE. A two-way bar is the end of
--  the operator's dunning ladder and 55 is open on how long that ladder takes.
--  Three months is long enough that the answer to 55 cannot move these rates
--  much in either direction. It is deliberately NOT the model's one-month
--  label.
--
--  WHAT EACH STATEMENT FEEDS
--
--    D0  builds dcb_dash_now  - the live population, their bills, their flags
--    D1  the funnel: how many customers qualify, and what removed the rest
--    D2  what the qualifying customers actually bill each month
--    D3  how many can take each ticket size under the limit rule
--    D4  how many carry each red flag, and how many carry none
--    D5  builds dcb_dash_past - the same flags on 1404, with the outcome
--    D6  THE SCORECARD: the measured rate for each flag, and by flag count
--    D7  bill shock: where each ticket size lands the customer
--    D8  is risk stable month to month
--    D9  THE MONEY TABLE: customers, rate, exposure and loss by flag count
--
--  NO percent character anywhere. NO CASE expressions.
--  Amounts are RIAL. 1 Toman = 10 Rial. 1,700,000 Rial = 170,000 Toman.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- D0  THE LIVE POPULATION. 140501..140506 at the production bar.
--
--     bill_low is the SECOND SMALLEST of the six months, not the average. A
--     customer's limit should rest on a bill they reliably reach, and the
--     average is pulled up by one heavy month.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_dash_now;

CREATE TABLE dwbi_temp40_db.dcb_dash_now WITH (format='PARQUET') AS
WITH pm AS (
    SELECT   sbrp_id, SUM(COALESCE(pmnt_amt,0)) AS paid_6m
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14050101 AND 14050631
    GROUP BY sbrp_id
),
pre AS (
    -- bar history in the 12 months before the window
    SELECT   sbrp_id, MAX(IF(sbrp_stat_id = 4, 1, 0)) AS pre_tw
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140401 AND 140412
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
feat AS (
    SELECT  sbrp_id,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140501), 0) AS r1,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140502), 0) AS r2,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140503), 0) AS r3,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140504), 0) AS r4,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140505), 0) AS r5,
            COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
                     FILTER (WHERE month_key = 140506), 0) AS r6,
            MAX(IF(sbrp_stat_id = 3, 1, 0))                AS any_ow,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                AS any_tw
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140501 AND 140506
      AND   sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT      f.sbrp_id,
            f.r1+f.r2+f.r3+f.r4+f.r5+f.r6                               AS rev_6m,
            (f.r1+f.r2+f.r3+f.r4+f.r5+f.r6) / 6                         AS bill_avg,
            ELEMENT_AT(ARRAY_SORT(ARRAY[f.r1,f.r2,f.r3,f.r4,f.r5,f.r6]), 2) AS bill_low,
            COALESCE(p.paid_6m, 0)                                      AS paid_6m,
            -- RED FLAG 1: a month where they billed nothing. New or restarted
            -- lines. Measured at 7.7x in 53.
            IF(IF(f.r1<=0,1,0)+IF(f.r2<=0,1,0)+IF(f.r3<=0,1,0)
              +IF(f.r4<=0,1,0)+IF(f.r5<=0,1,0)+IF(f.r6<=0,1,0) > 0, 1, 0) AS flag_zero_month,
            -- RED FLAG 2: billed, but paid almost nothing back. 52 D3 found
            -- this is the ONLY payment band carrying excess risk.
            IF(f.r1+f.r2+f.r3+f.r4+f.r5+f.r6 > 0
               AND CAST(COALESCE(p.paid_6m,0) AS DOUBLE)
                   / (f.r1+f.r2+f.r3+f.r4+f.r5+f.r6) < 0.10, 1, 0)      AS flag_no_payment,
            -- RED FLAG 3: barred before, in the 12 months prior
            COALESCE(pr.pre_tw, 0)                                      AS flag_barred_before,
            -- RED FLAG 4: the bill is collapsing. The strongest single signal
            -- in 53 and the one that looks like nothing on a credit screen.
            IF(f.r4+f.r5+f.r6 < 0.80 * (f.r1+f.r2+f.r3), 1, 0)          AS flag_falling
FROM        feat f
LEFT  JOIN  pm   p  ON p.sbrp_id  = f.sbrp_id
LEFT  JOIN  pre  pr ON pr.sbrp_id = f.sbrp_id
WHERE   IF(f.r1>=1700000,1,0) + IF(f.r2>=1700000,1,0) + IF(f.r3>=1700000,1,0)
      + IF(f.r4>=1700000,1,0) + IF(f.r5>=1700000,1,0) + IF(f.r6>=1700000,1,0) >= 2
  AND   f.any_ow = 0
  AND   f.any_tw = 0;


-- ---------------------------------------------------------------------------
-- D1  THE FUNNEL. How many customers qualify and what removed the rest.
--     Each step is applied on top of the ones above it, so the numbers add up
--     on the page the way a reader expects.
-- ---------------------------------------------------------------------------
WITH f AS (
    SELECT  sbrp_id,
            IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140501),0) >= 1700000, 1, 0)
          + IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140502),0) >= 1700000, 1, 0)
          + IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140503),0) >= 1700000, 1, 0)
          + IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140504),0) >= 1700000, 1, 0)
          + IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140505),0) >= 1700000, 1, 0)
          + IF(COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))
               FILTER (WHERE month_key=140506),0) >= 1700000, 1, 0)  AS n_months_over_bar,
            MAX(IF(sbrp_stat_id = 3, 1, 0))  AS any_ow,
            MAX(IF(sbrp_stat_id = 4, 1, 0))  AS any_tw
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140501 AND 140506 AND sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT  COUNT(*)                                                    AS step0_all_subscribers,
        SUM(IF(n_months_over_bar >= 2, 1, 0))                       AS step1_bills_enough,
        SUM(IF(n_months_over_bar >= 2 AND any_ow = 0, 1, 0))        AS step2_never_suspended,
        SUM(IF(n_months_over_bar >= 2 AND any_ow = 0 AND any_tw = 0, 1, 0)) AS step3_qualify,
        SUM(IF(n_months_over_bar <  2, 1, 0))                       AS cut_too_small,
        SUM(IF(n_months_over_bar >= 2 AND any_ow = 1, 1, 0))        AS cut_suspended_outgoing,
        SUM(IF(n_months_over_bar >= 2 AND any_ow = 0 AND any_tw = 1, 1, 0)) AS cut_suspended_both
FROM    f;


-- ---------------------------------------------------------------------------
-- D2  WHAT A QUALIFYING CUSTOMER BILLS EACH MONTH.
--
--     This is the number the limit rule has been waiting for. Everything
--     about ticket size depends on it and it has never been measured on the
--     scored set.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                            AS n_customers,
        APPROX_PERCENTILE(bill_low / 10, 0.10)              AS p10_toman,
        APPROX_PERCENTILE(bill_low / 10, 0.25)              AS p25_toman,
        APPROX_PERCENTILE(bill_low / 10, 0.50)              AS median_toman,
        APPROX_PERCENTILE(bill_low / 10, 0.75)              AS p75_toman,
        APPROX_PERCENTILE(bill_low / 10, 0.90)              AS p90_toman,
        APPROX_PERCENTILE(bill_avg / 10, 0.50)              AS median_avg_toman,
        AVG(CAST(bill_low AS DOUBLE) / 10)                  AS mean_toman
FROM    dwbi_temp40_db.dcb_dash_now;


-- ---------------------------------------------------------------------------
-- D3  HOW MANY CUSTOMERS CAN TAKE EACH TICKET under the limit rule.
--
--     The rule from 53: the draw must stay BELOW one month's bill, because a
--     draw equal to the bill doubles it and doubling is where the risk steps
--     up. So a 300,000 Toman ticket needs a bill above 300,000 Toman.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                            AS n_qualify,
        SUM(IF(bill_low > 1000000, 1, 0))                   AS can_take_100k,
        SUM(IF(bill_low > 2000000, 1, 0))                   AS can_take_200k,
        SUM(IF(bill_low > 3000000, 1, 0))                   AS can_take_300k,
        SUM(IF(bill_low > 5000000, 1, 0))                   AS can_take_500k,
        SUM(IF(bill_low > 1000000, 1, 0))
          - SUM(IF(bill_low > 3000000, 1, 0))               AS between_100k_and_300k,
        SUM(IF(bill_low <= 1000000, 1, 0))                  AS too_small_for_minimum_ticket
FROM    dwbi_temp40_db.dcb_dash_now;


-- ---------------------------------------------------------------------------
-- D4  THE RED FLAGS on the live population. How many carry each one, and
--     how many carry none at all.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                            AS n_customers,
        SUM(flag_zero_month)                                AS f1_month_with_no_bill,
        SUM(flag_no_payment)                                AS f2_paid_almost_nothing,
        SUM(flag_barred_before)                             AS f3_barred_in_past_year,
        SUM(flag_falling)                                   AS f4_bill_is_falling,
        SUM(IF(flag_zero_month + flag_no_payment
             + flag_barred_before + flag_falling = 0, 1, 0)) AS no_flags_at_all,
        AVG(CAST(flag_zero_month + flag_no_payment
               + flag_barred_before + flag_falling AS DOUBLE)) AS mean_flags
FROM    dwbi_temp40_db.dcb_dash_now;


-- ---------------------------------------------------------------------------
-- D5  THE SAME FLAGS ON 140401..140406, WITH THE OUTCOME.
--
--     Screened at 1,050,000 Rial, the 1404 equivalent of the 1,700,000 bar,
--     so the two cohorts are the same kind of customer either side of two
--     price rises.
--
--     Outcome: a two-way bar in 140407, 140408 or 140409. Three months, for
--     the reason in the header.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_dash_past;

CREATE TABLE dwbi_temp40_db.dcb_dash_past WITH (format='PARQUET') AS
WITH pm AS (
    SELECT   sbrp_id, SUM(COALESCE(pmnt_amt,0)) AS paid_6m
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14040101 AND 14040631
    GROUP BY sbrp_id
),
pre AS (
    SELECT   sbrp_id, MAX(IF(sbrp_stat_id = 4, 1, 0)) AS pre_tw
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140301 AND 140312 AND sbrp_typ_id = 1
    GROUP BY sbrp_id
),
out AS (
    SELECT   sbrp_id, MAX(IF(sbrp_stat_id = 4, 1, 0)) AS barred
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key IN (140407, 140408, 140409) AND sbrp_typ_id = 1
    GROUP BY sbrp_id
),
feat AS (
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
            MAX(IF(sbrp_stat_id = 3, 1, 0))                AS any_ow,
            MAX(IF(sbrp_stat_id = 4, 1, 0))                AS any_tw
    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE   month_key BETWEEN 140401 AND 140406 AND sbrp_typ_id = 1
    GROUP BY sbrp_id
)
SELECT      f.sbrp_id,
            ELEMENT_AT(ARRAY_SORT(ARRAY[f.r1,f.r2,f.r3,f.r4,f.r5,f.r6]), 2) AS bill_low,
            IF(IF(f.r1<=0,1,0)+IF(f.r2<=0,1,0)+IF(f.r3<=0,1,0)
              +IF(f.r4<=0,1,0)+IF(f.r5<=0,1,0)+IF(f.r6<=0,1,0) > 0, 1, 0) AS flag_zero_month,
            IF(f.r1+f.r2+f.r3+f.r4+f.r5+f.r6 > 0
               AND CAST(COALESCE(p.paid_6m,0) AS DOUBLE)
                   / (f.r1+f.r2+f.r3+f.r4+f.r5+f.r6) < 0.10, 1, 0)      AS flag_no_payment,
            COALESCE(pr.pre_tw, 0)                                      AS flag_barred_before,
            IF(f.r4+f.r5+f.r6 < 0.80 * (f.r1+f.r2+f.r3), 1, 0)          AS flag_falling,
            COALESCE(o.barred, 0)                                       AS barred_next_3m
FROM        feat f
LEFT  JOIN  pm   p  ON p.sbrp_id  = f.sbrp_id
LEFT  JOIN  pre  pr ON pr.sbrp_id = f.sbrp_id
LEFT  JOIN  out  o  ON o.sbrp_id  = f.sbrp_id
WHERE   IF(f.r1>=1050000,1,0) + IF(f.r2>=1050000,1,0) + IF(f.r3>=1050000,1,0)
      + IF(f.r4>=1050000,1,0) + IF(f.r5>=1050000,1,0) + IF(f.r6>=1050000,1,0) >= 2
  AND   f.any_ow = 0
  AND   f.any_tw = 0;


-- ---------------------------------------------------------------------------
-- D6  THE SCORECARD. What each red flag is worth, measured.
--
--     per_1000 is the one to put on the page. "Out of every 1,000 customers
--     like this, N stopped paying" is a sentence a manager can act on;
--     0.2208 pct is not.
-- ---------------------------------------------------------------------------
SELECT  'all customers'                AS segment, COUNT(*) AS n,
        SUM(barred_next_3m)            AS n_stopped,
        1000e0 * SUM(barred_next_3m) / COUNT(*) AS per_1000
FROM    dwbi_temp40_db.dcb_dash_past
UNION ALL
SELECT  'no red flags', COUNT(*), SUM(barred_next_3m), 1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past
WHERE   flag_zero_month + flag_no_payment + flag_barred_before + flag_falling = 0
UNION ALL
SELECT  'flag 1 - a month with no bill', COUNT(*), SUM(barred_next_3m), 1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past WHERE flag_zero_month = 1
UNION ALL
SELECT  'flag 2 - paid almost nothing', COUNT(*), SUM(barred_next_3m), 1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past WHERE flag_no_payment = 1
UNION ALL
SELECT  'flag 3 - barred in the past year', COUNT(*), SUM(barred_next_3m), 1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past WHERE flag_barred_before = 1
UNION ALL
SELECT  'flag 4 - the bill is falling', COUNT(*), SUM(barred_next_3m), 1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past WHERE flag_falling = 1
ORDER BY per_1000;


-- ---------------------------------------------------------------------------
-- D7  BILL SHOCK. Where each ticket size lands a customer.
--
--     A draw below the bill keeps the rise under 2x, which 53 measured as the
--     line between a 1.13x and a 1.91x default rate. This counts how many
--     live customers fall each side of it, per ticket.
-- ---------------------------------------------------------------------------
SELECT  ticket_toman,
        COUNT(*)                                                  AS n_customers,
        SUM(IF(bill_low > 4 * ticket_toman * 10, 1, 0))            AS safe_rise_under_1_25x,
        SUM(IF(bill_low > ticket_toman * 10
               AND bill_low <= 4 * ticket_toman * 10, 1, 0))       AS watch_rise_1_25_to_2x,
        SUM(IF(bill_low <= ticket_toman * 10, 1, 0))               AS risky_rise_2x_or_more
FROM    dwbi_temp40_db.dcb_dash_now
CROSS JOIN UNNEST(ARRAY[100000, 200000, 300000, 500000]) AS t(ticket_toman)
GROUP BY ticket_toman
ORDER BY ticket_toman;


-- ---------------------------------------------------------------------------
-- D8  IS RISK STABLE? The two-way bar rate month by month across both years.
--     If it swings, the loss figure needs a range rather than a number.
-- ---------------------------------------------------------------------------
SELECT  month_key,
        COUNT(*)                                        AS n_subscribers,
        SUM(IF(sbrp_stat_id = 4, 1, 0))                 AS n_barred,
        1000e0 * SUM(IF(sbrp_stat_id = 4, 1, 0)) / COUNT(*) AS per_1000
FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip
WHERE   month_key BETWEEN 140401 AND 140512
  AND   sbrp_typ_id = 1
GROUP BY month_key
ORDER BY month_key;


-- ---------------------------------------------------------------------------
-- D9  THE MONEY TABLE. Customers by how many red flags they carry, with the
--     measured rate for that group, so the page can show exposure and loss
--     without a model.
--
--     Run both halves and line them up by n_flags. Counts come from the live
--     window, rates from the past one.
-- ---------------------------------------------------------------------------
SELECT  'live counts'                                   AS source,
        flag_zero_month + flag_no_payment + flag_barred_before + flag_falling AS n_flags,
        COUNT(*)                                        AS n_customers,
        SUM(IF(bill_low > 3000000, 1, 0))               AS can_take_300k,
        CAST(APPROX_PERCENTILE(bill_low / 10, 0.50) AS DOUBLE) AS median_bill_toman,
        CAST(NULL AS DOUBLE)                            AS per_1000
FROM    dwbi_temp40_db.dcb_dash_now
GROUP BY flag_zero_month + flag_no_payment + flag_barred_before + flag_falling
UNION ALL
SELECT  'measured rates',
        flag_zero_month + flag_no_payment + flag_barred_before + flag_falling,
        COUNT(*),
        CAST(NULL AS BIGINT),
        CAST(NULL AS DOUBLE),
        1000e0 * SUM(barred_next_3m) / COUNT(*)
FROM    dwbi_temp40_db.dcb_dash_past
GROUP BY flag_zero_month + flag_no_payment + flag_barred_before + flag_falling
ORDER BY source, n_flags;


-- ---------------------------------------------------------------------------
-- D10  WHICH BILL SHOULD THE LIMIT REST ON?
--
--      D3 used bill_low - the second lowest of a customer's six months, a bill
--      they reliably reach. That is the cautious basis, and it is why 2,906,210
--      customers who pass the screen cannot take even the 100,000 minimum:
--      the screen asks for 170,000 in ANY TWO of six months, so the other four
--      can be almost nothing.
--
--      This runs the same counts against bill_avg, the plain six-month average,
--      which is the other end of the range. The median customer's average is
--      262,860 Toman against a second-lowest month of 144,031, so this should
--      come back materially larger.
--
--      It is a policy decision with roughly a 2x consequence for the size of
--      the programme, and it costs one query to put numbers on both sides.
--      Nothing else needs re-running: it reads the table D0 already built.
-- ---------------------------------------------------------------------------
SELECT  'second lowest month (used on the dashboard)'  AS basis,
        COUNT(*)                                       AS n_qualify,
        SUM(IF(bill_low > 1000000, 1, 0))              AS can_take_100k,
        SUM(IF(bill_low > 2000000, 1, 0))              AS can_take_200k,
        SUM(IF(bill_low > 3000000, 1, 0))              AS can_take_300k,
        SUM(IF(bill_low > 5000000, 1, 0))              AS can_take_500k,
        SUM(IF(bill_low <= 1000000, 1, 0))             AS cannot_take_minimum
FROM    dwbi_temp40_db.dcb_dash_now
UNION ALL
SELECT  'six-month average',
        COUNT(*),
        SUM(IF(bill_avg > 1000000, 1, 0)),
        SUM(IF(bill_avg > 2000000, 1, 0)),
        SUM(IF(bill_avg > 3000000, 1, 0)),
        SUM(IF(bill_avg > 5000000, 1, 0)),
        SUM(IF(bill_avg <= 1000000, 1, 0))
FROM    dwbi_temp40_db.dcb_dash_now;

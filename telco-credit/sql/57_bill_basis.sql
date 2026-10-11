-- ============================================================================
--  THE LADDER ON THE REAL BILL                              (Trino/Presto)
--
--  WHAT WAS WRONG
--
--  56 built r1..r6 from arpu minus tot_arpu_tax_amt and called it the bill. It
--  is not. That is TOTAL service revenue, cash and non-cash together, and
--  roughly half of it is packages bought with cash that never reach the
--  postpaid account. A draw is repaid on the bill, so sizing a draw against
--  revenue sizes it against money that cannot repay it.
--
--  THE RIGHT COLUMN, already documented in 11_dcb_extract_v3 STEP 1B
--
--      v_fact_cust_bil_daily.payment_due_amt, cust_bil_typ_id = 2
--
--  End-of-cycle bill, carried only on the LAST DAY of each month, keyed by
--  sbrp_id so it joins directly. Stamped at the end of month M it is the usage
--  OF MONTH M, due the 15th of M+1 - the very bill that then sits in the daily
--  bill_outstanding_amt. And it is NON-CASH ONLY, which is precisely why it is
--  the right denominator: it already excludes the cash packages.
--
--  NOT invoice_amt or payable_amt on the monthly fact. 11 established those are
--  loaded in only 14 of 30 months and empty across 140312..140409, with an
--  identical gap, so no choice of column there escapes it. payable_amt is also
--  misaligned - stamped month M it is the usage of month M-1.
--
--  NO 0.52 FACTOR ANYWHERE. B3 MEASURES the non-cash share on this exact
--  population instead of assuming a network-wide figure, which is better than
--  the assumption it replaces and was always available.
--
--  WHAT STAYS AS IT WAS. The screen. The 170,000-in-2-of-6 rule is the
--  business's existing definition and is left on revenue, so the population
--  here is identical to 56's and only the LIMIT BASIS changes. One change at a
--  time.
--
--  RUN B1 FIRST AND STOP IF IT IS EMPTY.
--
--  NO percent character anywhere. NO CASE expressions.
--  Amounts are RIAL. 1 Toman = 10 Rial.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- B1  IS THE COLUMN POPULATED ACROSS BOTH WINDOWS?
--
--     11 found loading gaps in the monthly fact's billing columns and anchored
--     a whole calendar on one before noticing. Do not repeat it.
--
--     n_subs should be in the tens of millions in every month and med_bill
--     should be a plausible monthly bill in Rial. A month with n_subs near
--     zero is a loading gap and every window touching it is unusable.
-- ---------------------------------------------------------------------------
SELECT   day_key / 100                                       AS month_key,
         COUNT(*)                                            AS n_rows,
         COUNT(DISTINCT sbrp_id)                             AS n_subs,
         COUNT(*) FILTER (WHERE payment_due_amt > 0)         AS n_positive,
         APPROX_PERCENTILE(payment_due_amt, 0.5)
           FILTER (WHERE payment_due_amt > 0)                AS med_bill_rial,
         MIN(day_key)                                        AS first_day,
         MAX(day_key)                                        AS last_day
FROM     dwbi_fact_db.v_fact_cust_bil_daily
WHERE    day_key BETWEEN 14040101 AND 14050631
  AND    cust_bil_typ_id = 2
GROUP BY day_key / 100
ORDER BY month_key;


-- ---------------------------------------------------------------------------
-- B2  THE LIVE POPULATION WITH ITS REAL BILL.
--
--     Joins onto dcb_dash_now so the screened population is byte-for-byte the
--     one 56 reported on. rev_low is 56's bill_low renamed to what it actually
--     is, so the mistake cannot propagate again.
--
--     bill_low_true is the SECOND LOWEST of the six end-of-cycle bills, the
--     same conservative basis applied to the right column.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_dash_bill;

CREATE TABLE dwbi_temp40_db.dcb_dash_bill WITH (format='PARQUET') AS
WITH bil AS (
    SELECT   sbrp_id,
             day_key / 100                                        AS mk,
             -- COALESCE around the aggregate, not inside it: SUM FILTER
             -- returns NULL when no row matches and the inner one never runs.
             COALESCE(SUM(COALESCE(payment_due_amt,0))
                      FILTER (WHERE cust_bil_typ_id = 2), 0)      AS ec,
             COALESCE(SUM(COALESCE(payment_due_amt,0))
                      FILTER (WHERE cust_bil_typ_id = 3), 0)      AS mc,
             COUNT(*) FILTER (WHERE cust_bil_typ_id = 3)          AS mc_rows
    FROM     dwbi_fact_db.v_fact_cust_bil_daily
    WHERE    day_key BETWEEN 14050101 AND 14050631
      AND    cust_bil_typ_id IN (2, 3)
    GROUP BY sbrp_id, day_key / 100
),
piv AS (
    SELECT  sbrp_id,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140501), 0) AS b1,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140502), 0) AS b2,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140503), 0) AS b3,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140504), 0) AS b4,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140505), 0) AS b5,
            COALESCE(SUM(ec) FILTER (WHERE mk = 140506), 0) AS b6,
            COALESCE(SUM(mc), 0)                            AS mc_6m,
            COALESCE(SUM(mc_rows), 0)                       AS mc_rows_6m
    FROM    bil
    GROUP BY sbrp_id
)
SELECT      n.sbrp_id,
            n.rev_6m,
            n.bill_low                                      AS rev_low,
            n.bill_avg                                      AS rev_avg,
            n.paid_6m,
            n.flag_zero_month, n.flag_no_payment,
            n.flag_barred_before, n.flag_falling,
            COALESCE(p.b1,0) AS b1, COALESCE(p.b2,0) AS b2, COALESCE(p.b3,0) AS b3,
            COALESCE(p.b4,0) AS b4, COALESCE(p.b5,0) AS b5, COALESCE(p.b6,0) AS b6,
            COALESCE(p.b1,0)+COALESCE(p.b2,0)+COALESCE(p.b3,0)
          + COALESCE(p.b4,0)+COALESCE(p.b5,0)+COALESCE(p.b6,0)  AS billed_6m,
            COALESCE(p.mc_6m, 0)                            AS mc_6m,
            COALESCE(p.mc_rows_6m, 0)                       AS mc_rows_6m,
            ELEMENT_AT(ARRAY_SORT(ARRAY[COALESCE(p.b1,0),COALESCE(p.b2,0),
                                        COALESCE(p.b3,0),COALESCE(p.b4,0),
                                        COALESCE(p.b5,0),COALESCE(p.b6,0)]), 2)
                                                            AS bill_low_true,
            IF(p.sbrp_id IS NULL, 1, 0)                     AS no_bill_rows
FROM        dwbi_temp40_db.dcb_dash_now n
LEFT  JOIN  piv p ON p.sbrp_id = n.sbrp_id;


-- ---------------------------------------------------------------------------
-- B3  THE NON-CASH SHARE, MEASURED ON THIS POPULATION.
--
--     This replaces the 48 pct assumption. billed_6m over rev_6m is the share
--     of a subscriber's spending that reaches the postpaid account. Read the
--     MEDIAN, not the mean - one subscriber with a tiny revenue denominator
--     can send a mean anywhere.
--
--     If it comes back near 0.52 the network figure holds for this group. If
--     it comes back higher, these heavier billers put more on the bill than
--     the network average and the ladder is less restrictive than feared.
--
--     n_no_bill_rows is the honesty check: subscribers in the screened set
--     with no end-of-cycle bill row at all. If that is large, the join is
--     wrong or the column is sparse, and nothing below can be trusted.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                            AS n_customers,
        SUM(no_bill_rows)                                   AS n_no_bill_rows,
        SUM(IF(billed_6m <= 0, 1, 0))                       AS n_zero_billed,
        SUM(IF(mc_rows_6m > 0, 1, 0))                       AS n_with_midcycle,
        APPROX_PERCENTILE(IF(rev_6m > 0,
            CAST(billed_6m AS DOUBLE) / rev_6m, NULL), 0.10) AS p10_noncash_share,
        APPROX_PERCENTILE(IF(rev_6m > 0,
            CAST(billed_6m AS DOUBLE) / rev_6m, NULL), 0.50) AS median_noncash_share,
        APPROX_PERCENTILE(IF(rev_6m > 0,
            CAST(billed_6m AS DOUBLE) / rev_6m, NULL), 0.90) AS p90_noncash_share,
        APPROX_PERCENTILE(billed_6m / 6 / 10, 0.50)         AS median_monthly_bill_toman,
        APPROX_PERCENTILE(rev_6m / 6 / 10, 0.50)            AS median_monthly_rev_toman
FROM    dwbi_temp40_db.dcb_dash_bill;


-- ---------------------------------------------------------------------------
-- B4  WHAT A QUALIFYING CUSTOMER IS ACTUALLY BILLED EACH MONTH.
--     D2 again, on the right column. Compare the two side by side.
-- ---------------------------------------------------------------------------
SELECT  'the real bill (end-of-cycle, non-cash)'            AS basis,
        COUNT(*)                                            AS n_customers,
        APPROX_PERCENTILE(bill_low_true / 10, 0.10)         AS p10_toman,
        APPROX_PERCENTILE(bill_low_true / 10, 0.25)         AS p25_toman,
        APPROX_PERCENTILE(bill_low_true / 10, 0.50)         AS median_toman,
        APPROX_PERCENTILE(bill_low_true / 10, 0.75)         AS p75_toman,
        APPROX_PERCENTILE(bill_low_true / 10, 0.90)         AS p90_toman
FROM    dwbi_temp40_db.dcb_dash_bill
UNION ALL
SELECT  'total revenue (what 56 used)',
        COUNT(*),
        APPROX_PERCENTILE(rev_low / 10, 0.10),
        APPROX_PERCENTILE(rev_low / 10, 0.25),
        APPROX_PERCENTILE(rev_low / 10, 0.50),
        APPROX_PERCENTILE(rev_low / 10, 0.75),
        APPROX_PERCENTILE(rev_low / 10, 0.90)
FROM    dwbi_temp40_db.dcb_dash_bill;


-- ---------------------------------------------------------------------------
-- B5  THE LADDER ON THE REAL BILL. This supersedes D3 and D11.
--
--     The rule is unchanged - the draw stays BELOW one month's bill - but the
--     bill is now the bill. Every count here is the one to publish.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                            AS n_qualify,
        SUM(IF(bill_low_true > 1000000, 1, 0))              AS can_take_100k,
        SUM(IF(bill_low_true > 2000000, 1, 0))              AS can_take_200k,
        SUM(IF(bill_low_true > 3000000, 1, 0))              AS can_take_300k,
        SUM(IF(bill_low_true > 5000000, 1, 0))              AS can_take_500k,
        SUM(IF(bill_low_true <= 1000000, 1, 0))             AS cannot_take_minimum,
        -- and the same on the six-month average bill, the looser basis
        SUM(IF(billed_6m / 6 > 1000000, 1, 0))              AS avg_can_take_100k,
        SUM(IF(billed_6m / 6 > 3000000, 1, 0))              AS avg_can_take_300k
FROM    dwbi_temp40_db.dcb_dash_bill;


-- ---------------------------------------------------------------------------
-- B6  THE BOOK, BY WARNING-SIGN COUNT, ON THE REAL BILL.
--
--     Feeds the money table directly: how many customers at each ticket, and
--     how many of them are clean. Pair the rates from 56 D6 with these counts.
-- ---------------------------------------------------------------------------
SELECT  flag_zero_month + flag_no_payment
      + flag_barred_before + flag_falling                   AS n_flags,
        COUNT(*)                                            AS n_customers,
        SUM(IF(bill_low_true > 1000000, 1, 0))              AS can_take_100k,
        SUM(IF(bill_low_true > 2000000, 1, 0))              AS can_take_200k,
        SUM(IF(bill_low_true > 3000000, 1, 0))              AS can_take_300k,
        SUM(IF(bill_low_true > 5000000, 1, 0))              AS can_take_500k,
        CAST(APPROX_PERCENTILE(bill_low_true / 10, 0.50) AS DOUBLE)
                                                            AS median_bill_toman
FROM    dwbi_temp40_db.dcb_dash_bill
GROUP BY flag_zero_month + flag_no_payment
       + flag_barred_before + flag_falling
ORDER BY n_flags;

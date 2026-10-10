-- ============================================================================
--  WHAT DO WE ACTUALLY KNOW ABOUT OFF-NET SPENDING?        (Trino/Presto)
--
--  53_bill_shock.sql treats a DCB draw as NEW money on the bill, so a 300,000
--  ticket on a 170,000 bill reads as a 2.76x shock. That is the PESSIMISTIC
--  end and it is probably wrong.
--
--  If a subscriber already pays 300,000 a month for VOD from a bank card and
--  now routes it through DCB, their total outgoings do not change at all. The
--  money was always leaving; only the rail changed. Same draw, same bill, and
--  a completely different risk:
--
--      0 pct substitution   -> real shock 2.76x
--     50 pct substitution   -> real shock 1.88x
--    100 pct substitution   -> real shock 1.00x
--
--  Which one it is decides whether DCB is a credit product or a payments
--  product, and nothing measured so far distinguishes them.
--
--  THE CLUE WE ALREADY HAVE. pay_to_rev_ratio on this project measured 1.40
--  and 1.28: subscribers pay the operator about 40 pct MORE than the operator
--  bills them in telco revenue. If arpu minus tax is telco charges, a large
--  share of what moves through v_fact_pmnt_adjmt is NOT a telco charge. Some
--  of it is top-ups and deposits. Some of it may be exactly the off-net
--  spending we were told is invisible - already flowing through the operator
--  and already in the warehouse.
--
--  This file is reconnaissance. It finds out what exists before any more
--  analysis assumes it does not. Read-only, nothing created.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- E1  WHAT TABLES EXIST. Content, VAS, digital goods, bill payment, wallet,
--     merchant - any of these would answer the substitution question directly.
--
--     If the two-part names in this project mean catalog.schema is implicit,
--     this may need the catalog in front: <catalog>.information_schema.tables.
--     Run it whichever way your other queries resolve.
-- ---------------------------------------------------------------------------
SELECT   table_schema, table_name
FROM     information_schema.tables
WHERE    table_schema IN ('dwbi_fact_db', 'dwbi_dim_db', 'dwbi_temp40_db')
  -- regexp_like, not LIKE: a LIKE wildcard is a percent character, and this
  -- project bans those outright - they have been mangled by the client before.
  AND    REGEXP_LIKE(LOWER(table_name),
                     'vas|content|digital|merchant|wallet|ecommerce|billpay|'
                     || 'bill_pay|charge|purchase|service|pmnt|payment|credit|loan')
ORDER BY table_schema, table_name;

-- ---------------------------------------------------------------------------
-- E2  WHAT IS IN THE PAYMENT TABLE. We have only ever read sbrp_id, day_key
--     and pmnt_amt from it. If it carries a payment TYPE, CHANNEL, SOURCE or
--     MERCHANT column, the 40 pct gap above becomes readable directly and the
--     substitution question is answered from data we already have.
-- ---------------------------------------------------------------------------
SELECT   column_name, data_type
FROM     information_schema.columns
WHERE    table_schema = 'dwbi_fact_db'
  AND    table_name   = 'v_fact_pmnt_adjmt'
ORDER BY ordinal_position;

-- ---------------------------------------------------------------------------
-- E3  AND THE SAME FOR THE MONTHLY SUBSCRIBER TABLE. 42 uses eleven of its
--     columns. A revenue breakdown - voice, data, VAS, content, third-party -
--     would say how much of a subscriber's bill is ALREADY non-telco, which is
--     the same question from the billing side.
-- ---------------------------------------------------------------------------
SELECT   column_name, data_type
FROM     information_schema.columns
WHERE    table_schema = 'dwbi_fact_db'
  AND    table_name   = 'v_fact_sbrp_mthly_cip'
ORDER BY ordinal_position;

-- ---------------------------------------------------------------------------
-- E4  CHARACTERISE THE GAP, with no new tables at all.
--
--     Per subscriber over 140401..140406: billed by the operator, paid to the
--     operator, and the difference. A gap that is large, POSITIVE and
--     consistent is money moving through the operator that telco revenue does
--     not explain.
--
--     What the shapes would mean:
--       gap near zero for most, a long tail   -> deposits and prepayment
--       gap broadly proportional to billing   -> a systematic second flow,
--                                                worth identifying in E1/E2
--       gap uncorrelated with billing         -> something unrelated to usage,
--                                                possibly already off-net
-- ---------------------------------------------------------------------------
WITH b AS (
    SELECT   sbrp_id,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS billed_6m
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140401 AND 140406
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
p AS (
    SELECT   sbrp_id, SUM(COALESCE(pmnt_amt,0)) AS paid_6m
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14040101 AND 14040631
    GROUP BY sbrp_id
)
SELECT   COUNT(*)                                                  AS n_subs,
         APPROX_PERCENTILE(b.billed_6m, 0.5) / 10                  AS med_billed_toman,
         APPROX_PERCENTILE(COALESCE(p.paid_6m,0), 0.5) / 10        AS med_paid_toman,
         APPROX_PERCENTILE(COALESCE(p.paid_6m,0) - b.billed_6m, 0.5) / 10
                                                                   AS med_gap_toman,
         APPROX_PERCENTILE(COALESCE(p.paid_6m,0) - b.billed_6m, 0.9) / 10
                                                                   AS p90_gap_toman,
         100.0 * AVG(IF(COALESCE(p.paid_6m,0) > b.billed_6m, 1e0, 0e0))
                                                                   AS pct_paid_more_than_billed,
         APPROX_PERCENTILE(IF(b.billed_6m > 0,
                              CAST(COALESCE(p.paid_6m,0) AS DOUBLE) / b.billed_6m,
                              NULL), 0.5)                          AS med_pay_to_bill
FROM     b
LEFT JOIN p ON p.sbrp_id = b.sbrp_id
WHERE    b.billed_6m > 0;

-- ---------------------------------------------------------------------------
-- E5  IS THE GAP PROPORTIONAL TO THE BILL, OR INDEPENDENT OF IT?
--
--     This is the discriminating view. Walk up the billing bands and read
--     med_gap_toman. If it rises in step with the bill, the gap is part of the
--     telco relationship - rounding, deposits, prepayment - and tells us
--     nothing about off-net life. If it is broadly FLAT in absolute Toman
--     across bands, it is a separate flow of a typical size, which is what a
--     subscription or a bill payment looks like.
--
--     A flat gap of roughly the size of a VOD subscription would be the single
--     most useful finding available right now: it would mean the spending DCB
--     is meant to capture is already visible, and the substitution share could
--     be measured instead of assumed.
-- ---------------------------------------------------------------------------
WITH b AS (
    SELECT   sbrp_id,
             SUM(COALESCE(arpu,0) - COALESCE(tot_arpu_tax_amt,0)) AS billed_6m
    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip
    WHERE    month_key BETWEEN 140401 AND 140406
      AND    sbrp_typ_id = 1
    GROUP BY sbrp_id
),
p AS (
    SELECT   sbrp_id, SUM(COALESCE(pmnt_amt,0)) AS paid_6m
    FROM     dwbi_fact_db.v_fact_pmnt_adjmt
    WHERE    day_key BETWEEN 14040101 AND 14040631
    GROUP BY sbrp_id
)
SELECT   IF(b.billed_6m <   600000, 'a  under 10k Toman a month',
         IF(b.billed_6m <  1800000, 'b  10k - 30k',
         IF(b.billed_6m <  6000000, 'c  30k - 100k',
         IF(b.billed_6m < 18000000, 'd  100k - 300k',
                                    'e  over 300k')))) AS billing_band,
         COUNT(*)                                                  AS n_subs,
         APPROX_PERCENTILE(b.billed_6m, 0.5) / 60                  AS med_month_billed_toman,
         APPROX_PERCENTILE((COALESCE(p.paid_6m,0) - b.billed_6m), 0.5) / 60
                                                                   AS med_month_gap_toman,
         APPROX_PERCENTILE(IF(b.billed_6m > 0,
                              CAST(COALESCE(p.paid_6m,0) AS DOUBLE) / b.billed_6m,
                              NULL), 0.5)                          AS med_pay_to_bill
FROM     b
LEFT JOIN p ON p.sbrp_id = b.sbrp_id
WHERE    b.billed_6m > 0
GROUP BY 1
ORDER BY 1;

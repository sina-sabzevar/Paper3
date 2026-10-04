-- ============================================================================
--  THE BILL TYPES, RESOLVED FROM THE DIMENSION            (Trino/Presto)
--
--  The dimension (info.xlsx, src_sys_id 1999319) holds 24 bill types. The two
--  that matter:
--
--      mid-cycle      "Hot Bill"      unq_id_in_src_sys = '7'
--      end-of-cycle   "monthly Bill"  unq_id_in_src_sys = '5'
--
--  THE PIPELINE HAS BEEN FILTERING ON NOTHING
--
--  11_dcb_extract_v3.sql and 25_scoreset.sql use cust_bil_typ_id = 2 for
--  end-of-cycle and = 3 for mid-cycle. No dimension row has a surrogate id of
--  2 or 3 - every real id is 47 or 48 digits, or -1 for Unknown. That is why
--  mc_billed_6m came back entirely NULL (register item G): the filter matched
--  zero rows, and SUM(x) FILTER over zero rows is NULL, not 0.
--
--  THE COLUMN IS VARCHAR, SO THE IDS CAN BE LITERALS - QUOTED
--
--  An earlier note here argued the ids could not be written as literals
--  because they exceed DECIMAL(38). That applies to numeric storage and is
--  irrelevant for this column: a VARCHAR holds all 48 characters exactly, and
--  a quoted literal matches it exactly.
--
--  What does still matter, and is independent of the type:
--
--    The end-of-cycle value matches the dimension's "monthly Bill" row.
--    The mid-cycle value does NOT - it carries the same leading digits as
--    "Hot Bill" but is an order of magnitude smaller, 47 characters against
--    48. One character was lost in transit. Used verbatim as a VARCHAR
--    literal it matches nothing at all, silently, exactly the way = 3 has
--    been matching nothing.
--
--  Because the comparison is now a string comparison, it is also exact in
--  ways a number is not: a stray space, a lost digit or a value that went
--  through a spreadsheet and came back in exponent form will all fail to
--  match while looking perfectly reasonable in the query text.
--
--  So D2 prints the fact's own values with their LENGTH. Copy the literals
--  from THAT output rather than from a spreadsheet, and the class of error
--  that produced the short mid-cycle value cannot recur. D3 offers the
--  dimension-join form as well, which needs no long literal at any point.
--
--  BEFORE THIS REPLACES ANYTHING, D1 AND D2 MUST AGREE
--
--  D1 names the dimension table - info.xlsx did not say which it is. D2
--  checks that the fact's cust_bil_typ_id really joins to it. If the fact
--  prints 47 digit values, the join is right. If the fact prints small
--  integers like 2 and 3, then there are TWO id systems and the small ones
--  are a different encoding - in which case send D2's output and the filter
--  changes again rather than being guessed at.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- D1  Which table is the bill-type dimension.
-- ---------------------------------------------------------------------------
SELECT   table_schema,
         table_name
FROM     dwbi_fact_db.information_schema.tables
WHERE    regexp_like(LOWER(table_name), 'bil_typ|bill_typ|cust_bil')
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- D2  What the FACT actually holds in that column, printed in full. If these
--     are 47 digit values the dimension join works. If they are 2 and 3, the
--     pipeline's filter was right all along and the dimension uses a
--     different encoding - send the output either way.
-- ---------------------------------------------------------------------------
SELECT   CAST(cust_bil_typ_id AS VARCHAR)           AS typ_id_text,
         LENGTH(CAST(cust_bil_typ_id AS VARCHAR))   AS digits,
         COUNT(*)                                   AS n_rows,
         COUNT(DISTINCT sbrp_id)                    AS n_subs,
         APPROX_PERCENTILE(MOD(day_key, 100), 0.5)  AS day_p50,
         COALESCE(SUM(payment_due_amt), 0)          AS amt_total
FROM     dwbi_fact_db.v_fact_cust_bil_daily
WHERE    day_key BETWEEN 14050101 AND 14050631
GROUP BY cust_bil_typ_id
ORDER BY n_rows DESC;

-- ---------------------------------------------------------------------------
-- D3  THE REPLACEMENT for STEP 1B's yardstick, once D1 has named the
--     dimension. Substitute it for <BIL_DIM> and nothing else changes.
--
--     Note what this now measures that the old version could not: the
--     mid-cycle total is real rather than NULL, so has_midcycle_billing
--     stops being a flag for "we could not tell".
-- ---------------------------------------------------------------------------
-- WITH bil AS (
--     SELECT  c.sbrp_id,
--             c.day_key / 100                                   AS month_key,
--             COALESCE(SUM(COALESCE(c.payment_due_amt, 0))
--                      FILTER (WHERE d.unq_id_in_src_sys = '5'), 0) AS ec_amt,
--             COALESCE(SUM(COALESCE(c.payment_due_amt, 0))
--                      FILTER (WHERE d.unq_id_in_src_sys = '7'), 0) AS mc_amt,
--             COUNT(*) FILTER (WHERE d.unq_id_in_src_sys = '7')     AS mc_rows
--     FROM        dwbi_fact_db.v_fact_cust_bil_daily c
--     INNER JOIN  dwbi_fact_db.<BIL_DIM> d
--             ON  d.cust_bil_typ_id = c.cust_bil_typ_id
--     WHERE   c.day_key BETWEEN 14040701 AND 14041231
--     GROUP BY c.sbrp_id, c.day_key / 100
-- )
-- SELECT   sbrp_id,
--          COALESCE(SUM(ec_amt), 0) + COALESCE(SUM(mc_amt), 0) AS obligation_6m,
--          COALESCE(SUM(ec_amt), 0)                            AS ec_billed_6m,
--          COALESCE(SUM(mc_amt), 0)                            AS mc_billed_6m,
--          IF(COALESCE(SUM(mc_rows), 0) > 0, 1, 0)             AS has_midcycle_billing
-- FROM     bil
-- GROUP BY sbrp_id;

-- ---------------------------------------------------------------------------
-- D3b  The same filter written with VARCHAR literals instead of a join, for
--      when the dimension is not wanted in the query. Paste the two strings
--      from D2's typ_id_text column - NOT from a spreadsheet.
--
--      The end-of-cycle string below is the one that matched the dimension.
--      The mid-cycle string is deliberately left as a marker rather than
--      filled with the 47 character value, because that value is short by a
--      character and would match nothing.
-- ---------------------------------------------------------------------------
-- WITH bil AS (
--     SELECT  c.sbrp_id,
--             c.day_key / 100                                     AS month_key,
--             COALESCE(SUM(COALESCE(c.payment_due_amt, 0)) FILTER (
--                 WHERE c.cust_bil_typ_id =
--                   '983116577831777608312765670515538102764700000000'), 0)
--                                                                 AS ec_amt,
--             COALESCE(SUM(COALESCE(c.payment_due_amt, 0)) FILTER (
--                 WHERE c.cust_bil_typ_id = '<HOT_BILL_ID_FROM_D2>'), 0)
--                                                                 AS mc_amt,
--             COUNT(*) FILTER (
--                 WHERE c.cust_bil_typ_id = '<HOT_BILL_ID_FROM_D2>') AS mc_rows
--     FROM    dwbi_fact_db.v_fact_cust_bil_daily c
--     WHERE   c.day_key BETWEEN 14040701 AND 14041231
--     GROUP BY c.sbrp_id, c.day_key / 100
-- )
-- SELECT   sbrp_id,
--          COALESCE(SUM(ec_amt), 0) + COALESCE(SUM(mc_amt), 0) AS obligation_6m,
--          COALESCE(SUM(ec_amt), 0)                            AS ec_billed_6m,
--          COALESCE(SUM(mc_amt), 0)                            AS mc_billed_6m,
--          IF(COALESCE(SUM(mc_rows), 0) > 0, 1, 0)             AS has_midcycle_billing
-- FROM     bil
-- GROUP BY sbrp_id;

-- ---------------------------------------------------------------------------
-- D4  REGISTER ITEM D, NOW ANSWERABLE: does any other type carry a real
--     obligation? The dimension has 24 types and several plainly do -
--     Late payment fee, Surcharge, Tax, Installation, Repair, Phone and
--     Accessories. obligation_6m currently counts only two of them.
--
--     This ranks every type by amount so the question becomes arithmetic.
--     Which of them belong in a credit obligation is a business call, not
--     mine: a tax bill and a late payment fee are money owed, while an
--     Overpayment Bill or a Deposit may be money held. Send the output and
--     say which to include.
-- ---------------------------------------------------------------------------
-- SELECT   d.cust_bil_typ,
--          d.unq_id_in_src_sys,
--          COUNT(*)                                  AS n_rows,
--          COUNT(DISTINCT c.sbrp_id)                 AS n_subs,
--          COALESCE(SUM(c.payment_due_amt), 0)       AS amt_total,
--          APPROX_PERCENTILE(c.payment_due_amt, 0.5) AS amt_p50,
--          APPROX_PERCENTILE(MOD(c.day_key, 100), 0.5) AS day_p50
-- FROM        dwbi_fact_db.v_fact_cust_bil_daily c
-- INNER JOIN  dwbi_fact_db.<BIL_DIM> d
--         ON  d.cust_bil_typ_id = c.cust_bil_typ_id
-- WHERE    c.day_key BETWEEN 14050101 AND 14050631
-- GROUP BY d.cust_bil_typ, d.unq_id_in_src_sys
-- ORDER BY amt_total DESC;

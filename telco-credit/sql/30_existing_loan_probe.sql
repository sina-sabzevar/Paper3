-- ============================================================================
--  DOES THE OPERATOR ALREADY HAVE REPAYMENT HISTORY?          (Trino/Presto)
--
--  KPI_v4 says it does, in two places:
--
--    "مجموع Loan_poundage_amt از فکت Prod با شرط cust_loan_oprtn_typ_id = 1"
--    "نسبت تعداد مشترکین یکتا که LOAN یا RBT فعال دارند به کل مشترکین B2C"
--
--  and it defines a whole family of KPIs for اعتبار اضطراری - emergency
--  credit - with daily and monthly sales, activations, fee income and unique
--  subscriber counts, plus an automatic variant.
--
--  WHY THIS MATTERS MORE THAN ANY MODEL REFINEMENT
--
--  The project has been building a behavioural PROXY label: a two-way bar
--  stands in for default because no credit history was thought to exist. If
--  subscribers have already taken an operator loan or emergency credit and
--  either repaid it or did not, that is the real thing - an actual credit
--  outcome on this exact population, under this exact product. A model
--  trained on real repayment beats one trained on a proxy, and no amount of
--  feature work closes that gap.
--
--  It also answers the question the proxy cannot: of the subscribers who look
--  creditworthy on payment behaviour, what share actually repay credit when
--  it is extended? That is the number the business case rests on.
--
--  THIS FILE GUESSES NOTHING. KPI_v4 says "fact Prod" without naming the
--  table, so P1 and P2 read the catalogue and report what exists. Only then
--  is it worth writing anything against it. Fill in the real names and run P3.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- P1  Which tables could carry it. Looks for the product facts KPI_v4 names
--     and for anything whose name mentions a loan or credit.
-- ---------------------------------------------------------------------------
-- regexp_like, not LIKE, because a LIKE wildcard is a percent character and
-- a Python driver printf-substitutes the whole statement when it sees one.
SELECT   table_name
FROM     dwbi_fact_db.information_schema.tables
WHERE    regexp_like(LOWER(table_name), 'prod|loan|actv_svcs|pmnt|credit')
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- P2  Which columns carry the loan fields KPI_v4 names. Run this once P1 has
--     reported the table names - it searches the whole schema's columns, so
--     it finds them wherever they live.
-- ---------------------------------------------------------------------------
SELECT   table_name,
         column_name,
         data_type
FROM     dwbi_fact_db.information_schema.columns
WHERE    regexp_like(LOWER(column_name),
                     'loan|poundage|cred_lim|emrgnc|emergency|ofring')
ORDER BY table_name, column_name;

-- ---------------------------------------------------------------------------
-- P3  THE ACTUAL QUESTION. Substitute the real table name from P1 for
--     <PROD_FACT> and the real month column if it is not month_key, then run.
--
--     Reports, for the months payments are complete in (140301..140506):
--       how many subscribers took a loan operation at all
--       how much fee income it produced
--       how it is spread over the months
--
--     If the subscriber count is in the millions, the proxy label should be
--     replaced by real repayment before anything else is done. If it is in
--     the thousands, it is still worth having as a validation set: score
--     those subscribers with the behavioural model and check whether the
--     ones it ranks badly are the ones who actually failed to repay.
-- ---------------------------------------------------------------------------
-- SELECT   month_key,
--          COUNT(*)                                        AS n_rows,
--          COUNT(DISTINCT sbrp_id)                         AS n_subscribers,
--          SUM(COALESCE(loan_poundage_amt, 0)) / 1e9       AS poundage_bn_rial
-- FROM     dwbi_fact_db.<PROD_FACT>
-- WHERE    month_key BETWEEN 140301 AND 140506
--   AND    cust_loan_oprtn_typ_id = 1
-- GROUP BY month_key
-- ORDER BY month_key;

-- ---------------------------------------------------------------------------
-- P4  VOLTE licence probe, as a worked example that the ID KPI_v4 gives is
--     usable. v_actv_svcs with prod_ofring_id = 770021 is the VOLTE licence
--     per the document. If this returns rows, v_actv_svcs is the place to
--     look for whether a LOAN product offering has its own prod_ofring_id -
--     which would give the "has an active LOAN" population directly.
-- ---------------------------------------------------------------------------
SELECT   prod_ofring_id,
         COUNT(*)                AS n_rows,
         COUNT(DISTINCT sbrp_id) AS n_subscribers
FROM     dwbi_fact_db.v_actv_svcs
WHERE    prod_ofring_id = 770021
GROUP BY prod_ofring_id;

-- Then widen it: the offerings with the most subscribers, so a LOAN or
-- emergency-credit offering can be spotted by volume and named.
SELECT   prod_ofring_id,
         COUNT(DISTINCT sbrp_id) AS n_subscribers
FROM     dwbi_fact_db.v_actv_svcs
GROUP BY prod_ofring_id
ORDER BY n_subscribers DESC
LIMIT    40;

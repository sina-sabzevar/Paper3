-- ============================================================================
--  DOES WHAT IS ON THE WAREHOUSE MATCH WHAT STEP 9 EXPECTS?  (Trino/Presto)
--
--  STEP 9 no longer uses a star expansion - it names all 104 columns explicitly,
--  because CREATE TABLE AS cannot create two columns with the same name while a
--  plain SELECT is happy to return them. That makes STEP 9 strict: a column it
--  names that is not actually in the table fails the statement.
--
--  The intermediate tables have changed shape several times - renames, removed
--  columns, a new bill source, a new calendar. If any of them was built from an
--  earlier version of the file, STEP 9 will fail on a name.
--
--  RUN THIS FIRST. An EMPTY result means STEP 9 will find every column it asks
--  for. Anything under "MISSING" names a table that has to be rebuilt.
--  Anything under "EXTRA" is harmless - a leftover column STEP 9 ignores - and
--  is listed only so a stale table is visible.
--
--  The expected list was GENERATED from 11_dcb_extract_v3.sql, so it is exactly
--  what STEP 9 asks for, not a transcription of it.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
WITH expected (tbl, col) AS (
  VALUES
    ('dcb3_base', 'sbrp_id'),
    ('dcb3_base', 'age_on_net_months'),
    ('dcb3_billref', 'sbrp_id'),
    ('dcb3_billref', 'med_bill'),
    ('dcb3_billref', 'n_billed_months'),
    ('dcb3_billref', 'ec_billed_6m'),
    ('dcb3_billref', 'mc_billed_6m'),
    ('dcb3_billref', 'obligation_6m'),
    ('dcb3_billref', 'midcycle_billed_share'),
    ('dcb3_billref', 'med_obligation'),
    ('dcb3_billref', 'max_bill'),
    ('dcb3_billref', 'bill_std'),
    ('dcb3_label', 'sbrp_id'),
    ('dcb3_label', 'n_months_out'),
    ('dcb3_label', 'max_dpd_out'),
    ('dcb3_label', 'n_late_out'),
    ('dcb3_label', 'total_debt_days_out'),
    ('dcb3_label', 'oneway_days_out'),
    ('dcb3_label', 'twoway_days_out'),
    ('dcb3_label', 'twoway_months_out'),
    ('dcb3_label', 'escalated_twoway'),
    ('dcb3_label', 'rule1_dpd60'),
    ('dcb3_label', 'rule2_late'),
    ('dcb3_label', 'rule4_escalated'),
    ('dcb3_label', 'y_twoway_2m'),
    ('dcb3_label', 'y_twoway_any2m'),
    ('dcb3_label', 'y_severe'),
    ('dcb3_label', 'y_strict'),
    ('dcb3_label', 'y_v1'),
    ('dcb3_label', 'y_v2'),
    ('dcb3_label', 'y_loose'),
    ('dcb3_label', 'indeterminate'),
    ('dcb3_dpd', 'sbrp_id'),
    ('dcb3_dpd', 'max_dpd_6m'),
    ('dcb3_dpd', 'max_debt_run_days'),
    ('dcb3_dpd', 'n_debt_spells_6m'),
    ('dcb3_dpd', 'total_debt_days_6m'),
    ('dcb3_dpd', 'n_late_months_6m'),
    ('dcb3_dpd', 'n_mild_late_months_6m'),
    ('dcb3_dpd', 'n_ontime_months_6m'),
    ('dcb3_dpd', 'max_debt_amt_6m'),
    ('dcb3_dpd', 'unbill_peak_6m'),
    ('dcb3_dpd', 'unbill_avg_6m'),
    ('dcb3_dpd', 'debtdays_m1'),
    ('dcb3_dpd', 'debtdays_m2'),
    ('dcb3_dpd', 'debtdays_m3'),
    ('dcb3_dpd', 'debtdays_m4'),
    ('dcb3_dpd', 'debtdays_m5'),
    ('dcb3_dpd', 'debtdays_m6'),
    ('dcb3_bars', 'sbrp_id'),
    ('dcb3_bars', 'oneway_days_6m'),
    ('dcb3_bars', 'twoway_days_6m'),
    ('dcb3_bars', 'n_ceiling_months_6m'),
    ('dcb3_bars', 'n_barred_months_6m'),
    ('dcb3_bars', 'last_bar_month_idx'),
    ('dcb3_bars', 'last_twoway_month_idx'),
    ('dcb3_bars', 'avg_barred_days_per_spell'),
    ('dcb3_panel', 'sbrp_id'),
    ('dcb3_panel', 'billed_m1'),
    ('dcb3_panel', 'billed_m2'),
    ('dcb3_panel', 'billed_m3'),
    ('dcb3_panel', 'billed_m4'),
    ('dcb3_panel', 'billed_m5'),
    ('dcb3_panel', 'billed_m6'),
    ('dcb3_panel', 'totrev_m1'),
    ('dcb3_panel', 'totrev_m2'),
    ('dcb3_panel', 'totrev_m3'),
    ('dcb3_panel', 'totrev_m4'),
    ('dcb3_panel', 'totrev_m5'),
    ('dcb3_panel', 'totrev_m6'),
    ('dcb3_panel', 'data_gb_6m'),
    ('dcb3_panel', 'data_gb_3m'),
    ('dcb3_panel', 'voice_min_6m'),
    ('dcb3_panel', 'voice_min_3m'),
    ('dcb3_panel', 'call_cnt_6m'),
    ('dcb3_panel', 'intl_cl_cnt_6m'),
    ('dcb3_panel', 'totrev_std_6m'),
    ('dcb3_panel', 'data_gb_std_6m'),
    ('dcb3_panel', 'billed_6m'),
    ('dcb3_panel', 'midcycle_billed_share_6m'),
    ('dcb3_panel', 'noncash_share_6m'),
    ('dcb3_panel', 'n_months_panel'),
    ('dcb3_pay', 'sbrp_id'),
    ('dcb3_pay', 'paid_total_6m'),
    ('dcb3_pay', 'n_payments_6m'),
    ('dcb3_pay', 'avg_first_pay_day'),
    ('dcb3_pay', 'paid_std_6m'),
    ('dcb3_pay', 'proven_capacity'),
    ('dcb3_pay', 'median_monthly_paid'),
    ('dcb3_pay', 'capacity_headroom'),
    ('dcb3_pit', 'sbrp_id'),
    ('dcb3_pit', 'network_id'),
    ('dcb3_pit', 'initial_cred_lim_amt'),
    ('dcb3_pit', 'temporary_cred_lim_amt'),
    ('dcb3_pit', 'rfndable_dpos_amt'),
    ('dcb3_pit', 'non_rfndable_dpos_amt'),
    ('dcb3_pit', 'advance_pmnt_amt'),
    ('dcb3_pit', 'bill_outstanding_amt'),
    ('dcb3_pit', 'unbill_outstanding_amt'),
    ('dcb3_pit', 'available_credit'),
    ('dcb3_pit', 'ceiling_reconstructed'),
    ('dcb3_pit', 'ceiling_utilisation'),
    ('dcb3_pit', 'debt_scr'),
    ('dcb3_pit', 'suspend_scr')
),
actual AS (
  SELECT   table_name AS tbl, column_name AS col
  FROM     information_schema.columns
  WHERE    table_schema = 'dwbi_temp40_db'
    AND    table_name IN ('dcb3_base', 'dcb3_billref', 'dcb3_label', 'dcb3_dpd', 'dcb3_bars', 'dcb3_panel', 'dcb3_pay', 'dcb3_pit')
)
SELECT   'MISSING - rebuild this table' AS issue, e.tbl, e.col
FROM     expected e
LEFT JOIN actual a ON a.tbl = e.tbl AND a.col = e.col
WHERE    a.col IS NULL
UNION ALL
SELECT   'EXTRA - harmless leftover'    AS issue, a.tbl, a.col
FROM     actual a
LEFT JOIN expected e ON e.tbl = a.tbl AND e.col = a.col
WHERE    e.col IS NULL
ORDER BY 1, 2, 3;

-- ============================================================================
--  WHICH TABLE IS STALE                                    (Trino/Presto)
--
--  G6 came back clean with max_late = 6, while the dataset still shows
--  n_late_out up to 36 and the same 9,241,763 rows as before the fix. Those two
--  read DIFFERENT tables: G6 reads dcb3_label, the rates read
--  dcb3_dataset_c1. So one is rebuilt and the other is not.
--
--  One query, reading both, settles it. No guessing.
--
--  HOW TO READ IT
--    label_max_late = 6 and ds_max_late = 6     -> both rebuilt, rates are real
--    label_max_late = 6 and ds_max_late > 6     -> re-run STEP 9 only
--    label_max_late > 6                         -> STEP 8 did not take; re-run
--                                                  STEP 8 then STEP 9
--  label_rows below dataset_rows is EXPECTED now: the n_months_seen >= 6 filter
--  was itself inflated by the fan-out, so it passed nearly everyone before and
--  now correctly drops subscribers without a complete 6-month outcome window.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
SELECT  (SELECT COUNT(*)           FROM dwbi_temp40_db.dcb3_label)       AS label_rows,
        (SELECT MAX(n_late_out)    FROM dwbi_temp40_db.dcb3_label)       AS label_max_late,
        (SELECT MAX(total_debt_days_out)
                                   FROM dwbi_temp40_db.dcb3_label)       AS label_max_debtdays,
        (SELECT COUNT(*)           FROM dwbi_temp40_db.dcb3_dataset_c1)  AS dataset_rows,
        (SELECT MAX(n_late_out)    FROM dwbi_temp40_db.dcb3_dataset_c1)  AS ds_max_late,
        (SELECT MAX(total_debt_days_out)
                                   FROM dwbi_temp40_db.dcb3_dataset_c1)  AS ds_max_debtdays,
        (SELECT MAX(n_debt_spells_6m) FROM dwbi_temp40_db.dcb3_dpd)      AS dpd_max_spells,
        (SELECT MAX(n_late_months_6m) FROM dwbi_temp40_db.dcb3_dpd)      AS dpd_max_late_feat;

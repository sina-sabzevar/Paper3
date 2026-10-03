-- ============================================================================
--  STEP 9 TEMPLATE. Paste G1's select_list where marked, then run.
--  Nothing here needs editing except that one paste.
-- ============================================================================
DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_dataset_c1;
CREATE TABLE dwbi_temp40_db.dcb3_dataset_c1 WITH (format='PARQUET') AS
SELECT  '140501' AS obs_cohort,
        -- CAPACITY BASIS = paid_total_6m. Part of the excess of payments over
        -- billing is arrears cleared from BEFORE the window rather than ongoing
        -- capacity, so the window overstates capacity for anyone catching up.
        --   paid_to_obligation > 1  was paying down old debt
        --                      < 1  was accumulating new arrears
        -- Discount proven_capacity by arrears_paydown_6m before setting a limit.
        pay.paid_total_6m / NULLIF(r.obligation_6m, 0)     AS paid_to_obligation,
        GREATEST(pay.paid_total_6m - r.obligation_6m, 0)   AS arrears_paydown_6m,
-- >>>>>>>>>>>>>>>>>>>> PASTE G1 select_list BELOW THIS LINE >>>>>>>>>>>>>>>>>>>>

-- <<<<<<<<<<<<<<<<<<<< PASTE G1 select_list ABOVE THIS LINE <<<<<<<<<<<<<<<<<<<<
FROM        dwbi_temp40_db.dcb3_base    b
INNER JOIN  dwbi_temp40_db.dcb3_billref r   ON r.sbrp_id   = b.sbrp_id
INNER JOIN  dwbi_temp40_db.dcb3_label   lab ON lab.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_dpd     dpd ON dpd.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_bars    bar ON bar.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_panel   pan ON pan.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pay     pay ON pay.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.dcb3_pit     pit ON pit.sbrp_id = b.sbrp_id
;

-- The two derived columns above are the ONLY place STEP 9 assumes a column
-- name. If G1 reports that obligation_6m or paid_total_6m is absent, rebuild
-- dcb3_billref or dcb3_pay; or delete those two lines to get the dataset out
-- and compute both in Python instead.

-- SANITY, run straight after:
SELECT COUNT(*) AS n_rows, COUNT(DISTINCT sbrp_id) AS n_subs
FROM   dwbi_temp40_db.dcb3_dataset_c1;

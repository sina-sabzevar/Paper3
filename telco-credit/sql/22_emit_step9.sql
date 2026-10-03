-- ============================================================================
--  EMIT THE WHOLE STEP 9 STATEMENT FROM YOUR OWN CATALOGUE  (Trino/Presto)
--
--  Four rounds have now failed on "column X cannot be resolved" - sbrp_id,
--  mc_billed_6m, n_months_out, payments_6m. Every one has the same cause: I
--  build the column list from MY file, your tables do not match it, and
--  patching one name at a time cannot converge.
--
--  So this assumes NO column name at all. Run it, copy the single text value it
--  returns, and run that. Nothing to edit, no markers, no paste position.
--
--  Duplicates are handled for you: where a name exists in more than one table
--  the earliest in the priority order wins and the rest are dropped, so
--  sbrp_id resolves once and no name can repeat. CREATE TABLE AS cannot reject
--  the result.
--
--  obs_cohort, paid_to_obligation and arrears_paydown_6m are NOT in the
--  generated statement, deliberately. They are one line of arithmetic each in
--  Python, and leaving them out means the emitted SQL contains no literal and
--  assumes no column - so there is nothing left for it to be wrong about.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
WITH src (tname, talias, pri) AS (
  VALUES ('dcb3_base',    'b',   1),
         ('dcb3_billref', 'r',   2),
         ('dcb3_label',   'lab', 3),
         ('dcb3_dpd',     'dpd', 4),
         ('dcb3_bars',    'bar', 5),
         ('dcb3_panel',   'pan', 6),
         ('dcb3_pay',     'pay', 7),
         ('dcb3_pit',     'pit', 8)
),
cols AS (
  SELECT  s.talias, s.pri, i.column_name, i.ordinal_position,
          ROW_NUMBER() OVER (PARTITION BY i.column_name
                             ORDER BY s.pri, i.ordinal_position) AS rn
  FROM        information_schema.columns i
  INNER JOIN  src s ON s.tname = i.table_name
  WHERE   i.table_schema = 'dwbi_temp40_db'
),
list AS (
  SELECT  COUNT(*) AS n_columns,
          ARRAY_JOIN(ARRAY_AGG('        ' || talias || '.' || column_name
                               ORDER BY pri, ordinal_position),
                     ',' || CHR(10)) AS sel
  FROM    cols
  WHERE   rn = 1
)
SELECT  n_columns,
        -- CHR(59) is a semicolon. Writing one inside a string literal would
        -- break any client that splits a file on semicolons, which is how these
        -- files are being run.
        'DROP TABLE IF EXISTS dwbi_temp40_db.dcb3_dataset_c1' || CHR(59) || CHR(10) ||
        'CREATE TABLE dwbi_temp40_db.dcb3_dataset_c1 AS'       || CHR(10) ||
        'SELECT'                                               || CHR(10) ||
        sel                                                    || CHR(10) ||
        'FROM        dwbi_temp40_db.dcb3_base    b'            || CHR(10) ||
        'INNER JOIN  dwbi_temp40_db.dcb3_billref r   ON r.sbrp_id   = b.sbrp_id' || CHR(10) ||
        'INNER JOIN  dwbi_temp40_db.dcb3_label   lab ON lab.sbrp_id = b.sbrp_id' || CHR(10) ||
        'LEFT  JOIN  dwbi_temp40_db.dcb3_dpd     dpd ON dpd.sbrp_id = b.sbrp_id' || CHR(10) ||
        'LEFT  JOIN  dwbi_temp40_db.dcb3_bars    bar ON bar.sbrp_id = b.sbrp_id' || CHR(10) ||
        'LEFT  JOIN  dwbi_temp40_db.dcb3_panel   pan ON pan.sbrp_id = b.sbrp_id' || CHR(10) ||
        'LEFT  JOIN  dwbi_temp40_db.dcb3_pay     pay ON pay.sbrp_id = b.sbrp_id' || CHR(10) ||
        'LEFT  JOIN  dwbi_temp40_db.dcb3_pit     pit ON pit.sbrp_id = b.sbrp_id' || CHR(10) ||
        CHR(59)                                                AS run_this
FROM    list;

-- ============================================================================
--  GENERATE STEP 9 FROM YOUR OWN TABLES                    (Trino/Presto)
--
--  WHY THIS EXISTS. STEP 9's column list was generated from my SQL file. Your
--  tables have since diverged from it - you commented duplicate columns out to
--  get earlier steps to run, and some tables were built from older versions. So
--  the list names columns your tables do not have (n_months_out is the one that
--  just failed) and every fix costs another round trip.
--
--  G1 reads information_schema and writes the SELECT list from WHAT IS
--  ACTUALLY THERE. It cannot be out of date, whatever state the tables are in.
--
--  IT ALSO FIXES DUPLICATES BY ITSELF. Where a column name exists in more than
--  one table, the first table in the priority order below wins and the others
--  are skipped. sbrp_id resolves to b.sbrp_id that way with no special case, and
--  so does any duplicate you have not found yet. No name can repeat, so
--  CREATE TABLE AS cannot reject the result.
--
--  HOW TO USE
--    1. run G1. It returns ONE long text value - the select list.
--    2. paste it into the template printed under G2, between the two markers.
--    3. run that.
--  Priority order is base, billref, label, dpd, bars, panel, pay, pit - so a
--  shared name is taken from the earliest, which is where it belongs.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- G1  the select list, built from your live catalogue
-- ---------------------------------------------------------------------------
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
  SELECT  s.talias,
          s.pri,
          i.column_name,
          i.ordinal_position,
          ROW_NUMBER() OVER (PARTITION BY i.column_name
                             ORDER BY s.pri, i.ordinal_position) AS rn
  FROM        information_schema.columns i
  INNER JOIN  src s ON s.tname = i.table_name
  WHERE   i.table_schema = 'dwbi_temp40_db'
)
SELECT  COUNT(*)                                            AS n_columns,
        ARRAY_JOIN(ARRAY_AGG('        ' || talias || '.' || column_name
                             ORDER BY pri, ordinal_position),
                   ',' || CHR(10))                          AS select_list
FROM    cols
WHERE   rn = 1;

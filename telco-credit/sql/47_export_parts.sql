-- ============================================================================
--  SPLIT THE TWO TABLES FOR EXPORT                         (Trino/Presto)
--
--  dcb_model is 8,701,085 rows and dcb_score 9,344,723, each about 39 columns,
--  which does not come back from the warehouse in one file. This splits each
--  into two halves. The notebook's loader globs dcb_model* and dcb_score*, so
--  these names are picked up and concatenated automatically.
--
--  THE SPLIT DOES NOT AFFECT THE MODEL. train/valid/test is assigned in Python
--  on md5(sbrp_id) AFTER the parts are concatenated, so how the export is cut
--  is irrelevant as long as every row appears exactly once. V1 below proves
--  that. The export split uses XXHASH64 and the model split uses MD5, so the
--  two are independent and a lost part would not bias one split.
--
--  WHY BITWISE_AND AND NOT MOD. Trino's MOD takes the sign of the dividend and
--  the hash is a signed BIGINT, so MOD(hash, 2) returns -1, 0 OR 1. A split
--  written as "= 0" and "= 1" therefore drops every row where it is -1 - about
--  a quarter of the table, silently, with both parts looking perfectly
--  reasonable on their own. BITWISE_AND(hash, 1) is exactly 0 or 1 whatever
--  the sign, and avoids ABS, which overflows on exactly -2^63.
--
--  WHY HASH AND NOT sbrp_id DIRECTLY. Every observed id in this base is ODD
--  and they share a five-digit block, so MOD on the raw id selects a
--  structured slice rather than a half. A parity split on sbrp_id once put all
--  11.5M rows of a table into one side.
--
--  PLAIN "SELECT *", NOT "SELECT * EXCEPT (...)". EXCEPT is a set operator in
--  Trino, not a column exclusion - that is BigQuery and Databricks syntax.
--  Selecting from a single table with no join returns only that table's own
--  columns, so nothing needs excluding.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_model_p1;
CREATE TABLE dwbi_temp40_db.dcb_model_p1 WITH (format='PARQUET') AS
SELECT * FROM dwbi_temp40_db.dcb_model
WHERE BITWISE_AND(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
          CAST(sbrp_id AS VARCHAR)))), 1) = 0;

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_model_p2;
CREATE TABLE dwbi_temp40_db.dcb_model_p2 WITH (format='PARQUET') AS
SELECT * FROM dwbi_temp40_db.dcb_model
WHERE BITWISE_AND(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
          CAST(sbrp_id AS VARCHAR)))), 1) = 1;

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_score_p1;
CREATE TABLE dwbi_temp40_db.dcb_score_p1 WITH (format='PARQUET') AS
SELECT * FROM dwbi_temp40_db.dcb_score
WHERE BITWISE_AND(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
          CAST(sbrp_id AS VARCHAR)))), 1) = 0;

DROP TABLE IF EXISTS dwbi_temp40_db.dcb_score_p2;
CREATE TABLE dwbi_temp40_db.dcb_score_p2 WITH (format='PARQUET') AS
SELECT * FROM dwbi_temp40_db.dcb_score
WHERE BITWISE_AND(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
          CAST(sbrp_id AS VARCHAR)))), 1) = 1;

-- ---------------------------------------------------------------------------
-- V1  CHECK BEFORE EXPORTING. Every column must come back 0 except the counts.
--
--     lost      rows in neither part   -> must be 0
--     doubled   rows in both parts     -> must be 0
--     delta     p1 + p2 minus original -> must be 0
--
--     A silent loss here is the worst failure available: both halves look
--     plausible, the model trains on a quarter less data than intended, and
--     nothing in the notebook can tell. The notebook's duplicate-sbrp_id check
--     catches the doubling case but CANNOT catch the loss case, which is why
--     it is checked here.
-- ---------------------------------------------------------------------------
SELECT  'dcb_model' AS tbl,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model)      AS n_total,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model_p1)   AS n_p1,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model_p2)   AS n_p2,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model_p1)
      + (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model_p2)
      - (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model)      AS delta,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model m
          WHERE m.sbrp_id NOT IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_model_p1)
            AND m.sbrp_id NOT IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_model_p2))
                                                             AS lost,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_model_p1 a
          INNER JOIN dwbi_temp40_db.dcb_model_p2 b ON b.sbrp_id = a.sbrp_id)
                                                             AS doubled
UNION ALL
SELECT  'dcb_score',
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score),
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score_p1),
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score_p2),
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score_p1)
      + (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score_p2)
      - (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score),
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score s
          WHERE s.sbrp_id NOT IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_score_p1)
            AND s.sbrp_id NOT IN (SELECT sbrp_id FROM dwbi_temp40_db.dcb_score_p2)),
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_score_p1 a
          INNER JOIN dwbi_temp40_db.dcb_score_p2 b ON b.sbrp_id = a.sbrp_id);

-- ---------------------------------------------------------------------------
-- V2  THE HALVES SHOULD BE BALANCED AND CARRY THE SAME EVENT RATE. Not a
--     correctness requirement - the parts are concatenated before anything
--     uses them - but a lopsided split or a rate that differs between halves
--     would mean the hash is not behaving and is worth knowing before export.
-- ---------------------------------------------------------------------------
SELECT   'dcb_model_p1' AS part, COUNT(*) AS n, SUM(y) AS n_bad,
         100.0 * SUM(y) / COUNT(*) AS bad_pct
FROM     dwbi_temp40_db.dcb_model_p1
UNION ALL
SELECT   'dcb_model_p2', COUNT(*), SUM(y), 100.0 * SUM(y) / COUNT(*)
FROM     dwbi_temp40_db.dcb_model_p2
UNION ALL
SELECT   'dcb_score_p1', COUNT(*), NULL, NULL
FROM     dwbi_temp40_db.dcb_score_p1
UNION ALL
SELECT   'dcb_score_p2', COUNT(*), NULL, NULL
FROM     dwbi_temp40_db.dcb_score_p2
ORDER BY part;

-- ---------------------------------------------------------------------------
--  EXPORT THESE FOUR, naming the files so the loader's glob picks them up:
--
--      dcb_model_p1  ->  notebook/data/dcb_model_p1.parquet   (or .csv)
--      dcb_model_p2  ->  notebook/data/dcb_model_p2.parquet
--      dcb_score_p1  ->  notebook/data/dcb_score_p1.parquet
--      dcb_score_p2  ->  notebook/data/dcb_score_p2.parquet
--
--  Do NOT also leave a whole-table dcb_model.parquet in that directory. The
--  loader globs dcb_model*, so it would read the whole table AND both halves,
--  giving every row twice - the duplicate-sbrp_id check would stop the run,
--  but only after the load.
-- ---------------------------------------------------------------------------

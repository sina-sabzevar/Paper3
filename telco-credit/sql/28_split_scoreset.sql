-- ============================================================================
--  SPLIT THE SCORING SET INTO TWO STORED TABLES            (Trino/Presto)
--
--  dcbs_scoreset is about 11M rows. S1 and S2 store each half as its own
--  table so each can be exported separately:
--
--      dwbi_temp40_db.dcbs_scoreset_p1
--      dwbi_temp40_db.dcbs_scoreset_p2
--
--  WHY IT IS WRITTEN THIS WAY
--
--  Each half is selected by a boundary on sbrp_id, computed exactly with
--  ROW_NUMBER. That keeps SELECT * returning exactly the table's own columns -
--  no part_no to strip afterwards. The obvious alternative,
--  SELECT * EXCEPT (part_no), is BigQuery and Databricks syntax; in Trino
--  EXCEPT is a SET operator between queries, not a column exclusion, so it
--  would not do what it looks like.
--
--  The boundary is EXACT, not approximate. APPROX_PERCENTILE would have been
--  shorter but the two statements must agree on the boundary to the row, or
--  a subscriber lands in both tables or in neither.
--
--  LIMIT with OFFSET is not used at all: without a total order the engine may
--  page differently between the two runs, and nothing in the output would show
--  that rows were duplicated or dropped.
--
--  Run S1, then S2, then S3.
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S1  first half - the lower sbrp_id range
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcbs_scoreset_p1;
CREATE TABLE dwbi_temp40_db.dcbs_scoreset_p1 AS
SELECT  *
FROM    dwbi_temp40_db.dcbs_scoreset
WHERE   sbrp_id <= (
    SELECT  MAX(sbrp_id)
    FROM (  SELECT  sbrp_id,
                    ROW_NUMBER() OVER (ORDER BY sbrp_id) AS rn
            FROM    dwbi_temp40_db.dcbs_scoreset ) r
    WHERE   rn <= (SELECT COUNT(*) / 2 FROM dwbi_temp40_db.dcbs_scoreset)
);

-- ---------------------------------------------------------------------------
-- S2  second half - everything above the same boundary.
--     The boundary subquery is identical to S1's, so the two halves meet
--     exactly and cannot overlap.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcbs_scoreset_p2;
CREATE TABLE dwbi_temp40_db.dcbs_scoreset_p2 AS
SELECT  *
FROM    dwbi_temp40_db.dcbs_scoreset
WHERE   sbrp_id > (
    SELECT  MAX(sbrp_id)
    FROM (  SELECT  sbrp_id,
                    ROW_NUMBER() OVER (ORDER BY sbrp_id) AS rn
            FROM    dwbi_temp40_db.dcbs_scoreset ) r
    WHERE   rn <= (SELECT COUNT(*) / 2 FROM dwbi_temp40_db.dcbs_scoreset)
);

-- ---------------------------------------------------------------------------
-- S3  CHECK. Three things must hold:
--       split_total  =  source_rows        nothing lost, nothing duplicated
--       overlap_ids  =  0                  no subscriber in both tables
--       p1_id_max    <  p2_id_min          the ranges do not cross
-- ---------------------------------------------------------------------------
SELECT  (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset)        AS source_rows,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset_p1)     AS p1_rows,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset_p2)     AS p2_rows,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset_p1)
      + (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset_p2)     AS split_total,
        (SELECT MAX(sbrp_id) FROM dwbi_temp40_db.dcbs_scoreset_p1) AS p1_id_max,
        (SELECT MIN(sbrp_id) FROM dwbi_temp40_db.dcbs_scoreset_p2) AS p2_id_min,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset_p1 a
          INNER JOIN dwbi_temp40_db.dcbs_scoreset_p2 b
                  ON b.sbrp_id = a.sbrp_id)                        AS overlap_ids;

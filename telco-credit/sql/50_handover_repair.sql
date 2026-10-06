-- ============================================================================
--  THE HANDOVER TABLE IS DOUBLE-LOADED. REPAIR IT BEFORE ANYTHING READS IT.
--                                                            (Trino/Presto)
--
--  The refit notebook's last cell printed:
--
--      Table dwbi_temp40_db.DCB_Handover140506 exists with 9344723 rows.
--      Appending data.
--      Inserting 9344723 rows in batches of 50000...
--
--  IQ.insert_df APPENDS. The table already held a full set of scores from the
--  pre-refit model, and the cell added a second full set from the refit, keyed
--  on the same sbrp_id. Three consequences, none of them loud:
--
--    1. ORDER BY pd_4m LIMIT 4672361 now draws from TWO models' scores mixed
--       together. The book it returns is from neither model.
--    2. Any join on sbrp_id fans out 2x. Every downstream count doubles.
--    3. COUNT(DISTINCT sbrp_id) still reads 9,344,723, so the obvious sanity
--       check passes while the table is wrong.
--
--  The cell's execution_count is null, so it had not finished when the
--  notebook was saved. The append may be partial - which makes it worse, not
--  better: a partial append leaves an arbitrary subset double-scored.
--
--  THERE IS NO DEDUPE THAT IS HONEST HERE. Old and new rows are
--  indistinguishable - same column set, no batch stamp, no load timestamp.
--  Picking MIN(pd_4m) or MAX(pd_4m) per sbrp_id would silently choose a
--  different model for different subscribers. The table has to be rebuilt.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- H1  HOW BAD IS IT? Run first, before changing anything.
--
--     n_rows      18,689,446 means the append finished.
--                 between 9,344,723 and that means it was interrupted.
--     n_subs      9,344,723 either way - which is the point.
--     max_per_sub 2 confirms the double load.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                        AS n_rows,
         COUNT(DISTINCT sbrp_id)                         AS n_subs,
         COUNT(*) - COUNT(DISTINCT sbrp_id)              AS n_surplus,
         COUNT(DISTINCT pd_4m)                           AS n_distinct_pd
FROM     dwbi_temp40_db.DCB_Handover140506;

-- ---------------------------------------------------------------------------
-- H2  ROWS PER SUBSCRIBER. If dupes is 9,344,723 the append completed; any
--     smaller number is the interrupted case, and singles is the remainder
--     still carrying only the OLD score.
-- ---------------------------------------------------------------------------
SELECT   n_rows_for_sub,
         COUNT(*)                                        AS n_subs
FROM     (
    SELECT   sbrp_id, COUNT(*) AS n_rows_for_sub
    FROM     dwbi_temp40_db.DCB_Handover140506
    GROUP BY sbrp_id
)
GROUP BY n_rows_for_sub
ORDER BY n_rows_for_sub;

-- ---------------------------------------------------------------------------
-- H3  HOW FAR APART ARE THE TWO MODELS ON THE SAME SUBSCRIBER? Read-only, and
--     worth seeing once: it is the cost of having taken the old book.
--
--     CAST because insert_df has typed pd_4m as VARCHAR before on this
--     project, and a VARCHAR ORDER BY is a TEXT sort that puts '1e-07' AFTER
--     '0.0252'. If the cast fails here, that is the answer to what type the
--     column is, and H5 must fix it.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                        AS n_subs_with_two,
         AVG(hi - lo)                                    AS avg_abs_gap,
         APPROX_PERCENTILE(hi - lo, 0.5)                 AS med_abs_gap,
         MAX(hi - lo)                                    AS max_abs_gap,
         AVG(hi / NULLIF(lo, 0))                         AS avg_ratio
FROM     (
    SELECT   sbrp_id,
             MIN(CAST(pd_4m AS DOUBLE))                  AS lo,
             MAX(CAST(pd_4m AS DOUBLE))                  AS hi
    FROM     dwbi_temp40_db.DCB_Handover140506
    GROUP BY sbrp_id
    HAVING   COUNT(*) > 1
);

-- ---------------------------------------------------------------------------
-- H4  THE REBUILD. Drop, then re-run the upload cell ONCE against the refit
--     CSV. Do not append to what is there.
--
--     Nothing depends on this table that cannot be rebuilt from
--     outputs/handover_scores.csv, so the drop is safe - but run H1 first so
--     the state it was in is on the record.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.DCB_Handover140506;

-- Then, in the notebook, in place of the bare insert_df call:
--
--     import IQ
--     h = pd.read_csv("outputs/handover_scores.csv")
--     h["pd_4m"] = h["pd_4m"].astype(float)
--     assert len(h) == 9_344_723,            f"expected 9,344,723 rows, got {len(h):,}"
--     assert h["sbrp_id"].is_unique,          "duplicate sbrp_id in the CSV"
--     assert h["pd_4m"].notna().all(),        "null pd_4m in the CSV"
--     assert h["pd_4m"].between(0, 1).all(),  "pd_4m outside [0, 1]"
--     IQ.insert_df(h, 'dwbi_temp40_db.DCB_Handover140506')
--
-- The asserts stop a bad load; they cannot stop a SECOND good load, which is
-- what happened. Check the table does not exist before running it.

-- ---------------------------------------------------------------------------
-- H5  AFTER THE RELOAD, prove it. All four must hold before the book is cut.
--
--     is_numeric 1 means pd_4m is a real number column. If it is 0 the column
--     is VARCHAR and ORDER BY pd_4m sorts it as TEXT - which was measured on
--     this project to swap in subscribers 654x riskier while leaving the row
--     count correct. Rebuild with a numeric cast before going further.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                         AS n_rows,
         COUNT(DISTINCT sbrp_id)                          AS n_subs,
         SUM(IF(pd_4m IS NULL, 1, 0))                     AS n_null_pd,
         MIN(CAST(pd_4m AS DOUBLE))                       AS min_pd,
         MAX(CAST(pd_4m AS DOUBLE))                       AS max_pd,
         AVG(CAST(pd_4m AS DOUBLE))                       AS mean_pd,
         IF(COUNT(*) = 9344723, 1, 0)                     AS rows_ok,
         IF(COUNT(*) = COUNT(DISTINCT sbrp_id), 1, 0)     AS unique_ok
FROM     dwbi_temp40_db.DCB_Handover140506;

-- ---------------------------------------------------------------------------
-- H6  THE SORT ITSELF. A text sort and a numeric sort agree on the row count
--     and disagree on WHO. agreement below 9,344,723 means pd_4m is still a
--     string. This is the check that would have caught the earlier VARCHAR
--     problem, so it runs every time now.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                         AS n_compared,
         SUM(IF(r_text = r_num, 1, 0))                    AS n_agree,
         IF(SUM(IF(r_text = r_num, 1, 0)) = COUNT(*), 1, 0) AS sort_ok
FROM     (
    SELECT   sbrp_id,
             ROW_NUMBER() OVER (ORDER BY pd_4m)                     AS r_text,
             ROW_NUMBER() OVER (ORDER BY CAST(pd_4m AS DOUBLE))     AS r_num
    FROM     dwbi_temp40_db.DCB_Handover140506
);

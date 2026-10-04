-- ============================================================================
--  EXPORT IN PARTS                                         (Trino/Presto)
--
--  Two different problems, two different answers.
--
--  SCORING SET - genuinely needs all 11M rows, because every subscriber needs
--  an offer. That is a transport problem, and E1 splits it. Change the single
--  number N_PARTS below (it appears in TWO places per query) to get 2, 4 or 8
--  parts. At 78 columns, CSV runs about 12 GB whole: 6 GB in two parts, 3 GB in
--  four, 1.5 GB in eight.
--
--  TRAINING SET - does NOT need 9.24M rows, and this is the bigger win. At a
--  2.22 pct event rate those rows hold about 205,000 bads. Keeping EVERY bad
--  and 10 pct of the goods gives 1.1M rows - 12 pct of the data, 1.2 GB, with
--  all 205,000 bads still present. E2 does that, and carries the sample weight
--  needed to put the base rate back so the model stays calibrated.
--
--  AND BEFORE ANYTHING ELSE: export PARQUET, not CSV, if the client can.
--  Same data, about 2.7 GB instead of 12 - pandas reads it directly with
--  pd.read_parquet and keeps the numeric types, which CSV loses.
--
--  THE SPLIT IS DETERMINISTIC AND EXHAUSTIVE. NTILE over an ORDER BY sbrp_id
--  gives contiguous, equal, non-overlapping parts. LIMIT with OFFSET would not:
--  without a total order the engine may return a different page each run, so
--  rows can be duplicated across parts or dropped from all of them - and
--  nothing in the output would show it.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- E1  SCORING SET, part 1 of 2.    <-- change BOTH 2s together for more parts
-- ---------------------------------------------------------------------------
SELECT  *
FROM (
    SELECT  t.*, NTILE(2) OVER (ORDER BY sbrp_id) AS part_no
    FROM    dwbi_temp40_db.dcbs_scoreset t
) s
WHERE   part_no = 1;

-- E1  SCORING SET, part 2 of 2.
SELECT  *
FROM (
    SELECT  t.*, NTILE(2) OVER (ORDER BY sbrp_id) AS part_no
    FROM    dwbi_temp40_db.dcbs_scoreset t
) s
WHERE   part_no = 2;


-- ---------------------------------------------------------------------------
-- E2  TRAINING SET, down-sampled on the GOODS only.
--
--     Every bad is kept. Goods are kept at GOOD_KEEP, chosen deterministically
--     so the same rows come back on a re-run. sample_weight puts the base rate
--     back: a kept good stands for 1/GOOD_KEEP goods, a bad stands for itself.
--
--     USE THE WEIGHT. In Python:
--         model.fit(X, y, sample_weight=df.sample_weight)
--     Without it the model sees a 17 pct event rate instead of 2.2 pct and
--     every PD it produces is roughly eight times too high. Ranking survives;
--     the level does not, and the limit engine spends the level.
--
--     GOOD_KEEP = 0.10 appears ONCE, in the WHERE and in the weight. Edit both.
-- ---------------------------------------------------------------------------
SELECT  t.*,
        -- a kept good represents 10 of them; a bad represents itself
        IF(y_severe = 1, 1.0, 1.0 / 0.10) AS sample_weight
FROM    dwbi_temp40_db.dcb3_dataset_c1 t
WHERE   y_severe = 1
   OR   MOD(ABS(sbrp_id), 100) < 10;      -- 10 pct of goods, deterministic


-- ---------------------------------------------------------------------------
-- E3  CHECK THE SPLIT BEFORE TRUSTING IT. Run this and read three things:
--       - parts_total must equal the table's own row count
--       - no part may be empty
--       - the id ranges must not overlap between parts
-- ---------------------------------------------------------------------------
SELECT  part_no,
        COUNT(*)                                   AS n_rows,
        MIN(sbrp_id)                               AS id_min,
        MAX(sbrp_id)                               AS id_max,
        COUNT(DISTINCT sbrp_id)                    AS n_distinct
FROM (
    SELECT  sbrp_id, NTILE(2) OVER (ORDER BY sbrp_id) AS part_no
    FROM    dwbi_temp40_db.dcbs_scoreset
) s
GROUP BY part_no
ORDER BY part_no;

-- and the totals, which must match
SELECT  (SELECT COUNT(*) FROM dwbi_temp40_db.dcbs_scoreset)      AS table_rows,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb3_dataset_c1)    AS train_rows,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb3_dataset_c1
          WHERE y_severe = 1)                                    AS train_bads,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb3_dataset_c1
          WHERE y_severe = 1 OR MOD(ABS(sbrp_id), 100) < 10)      AS e2_sample_rows;

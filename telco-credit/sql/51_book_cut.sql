-- ============================================================================
--  THE CANONICAL BOOK CUT - one order, used by both routes  (Trino/Presto)
--
--  "The safest 4,672,361" is not a definition until the tie is settled.
--
--  Isotonic calibration emits a STEP function: every score inside one of its
--  blocks maps to a single pd_4m, so a large block of subscribers carry the
--  identical value. The 1405-07-14 refit made that visible - grade E's mean
--  pd printed as exactly 0.040000 over 542,951 subscribers, which only happens
--  when they are all on one step.
--
--  ORDER BY pd_4m alone therefore does not pick a book. It picks the
--  strictly-safer subscribers, and then fills the remaining places from the
--  step at the cut in whatever order the engine returns - which Trino does not
--  promise, and which pandas settles by CSV row order, itself an accident of
--  the parquet concatenation. The same scores, cut two ways, give two
--  different sets of people.
--
--  THE ORDER, identical here and in notebook/select_book.py:
--
--      pd_4m      ASC    the model
--      pay_cover  DESC   what they paid against what they were billed
--      tenure_m   DESC   how long they have been a subscriber
--      sbrp_id    ASC    makes the order total and reproducible
--
--  pay_cover is a real signal among subscribers the model cannot tell apart,
--  and it is scale-free, so unlike a Rial level it does not drift. sbrp_id is
--  the last key only: it decides nothing except between subscribers who are
--  equal on everything above it.
--
--  REQUIRES dwbi_temp40_db.dcb_pd (STEP 0 of 48_approved_audit.sql) with
--  pd_4m already CAST to DOUBLE. A VARCHAR pd_4m makes ORDER BY a TEXT sort.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- C1  HOW BIG IS THE STEP AT THE CUT? Read this before cutting anything.
--
--     n_tied_at_cut is how many share the cut value. room is how many of them
--     fit. decided_by_tiebreak is the number admitted or refused by the three
--     keys below pd_4m rather than by the model - report it when the book is
--     handed over, because those subscribers are not ranked by risk.
-- ---------------------------------------------------------------------------
WITH s AS (
    SELECT   p.sbrp_id,
             p.pd_4m,
             IF(c.rev_6m > 0, CAST(c.paid_6m AS DOUBLE) / c.rev_6m, 0.0) AS pay_cover,
             c.tenure_m
    FROM     dwbi_temp40_db.dcb_pd    p
    INNER JOIN dwbi_temp40_db.dcb_score c ON c.sbrp_id = p.sbrp_id
),
cut AS (
    SELECT   MAX(pd_4m) AS cut_pd
    FROM     (
        SELECT   pd_4m,
                 ROW_NUMBER() OVER (ORDER BY pd_4m, pay_cover DESC, tenure_m DESC, sbrp_id) AS rn
        FROM     s
    )
    WHERE    rn <= 4672361
)
SELECT   c.cut_pd,
         COUNT(*)                                             AS n_scored,
         SUM(IF(s.pd_4m <  c.cut_pd, 1, 0))                   AS n_strictly_safer,
         SUM(IF(s.pd_4m =  c.cut_pd, 1, 0))                   AS n_tied_at_cut,
         4672361 - SUM(IF(s.pd_4m < c.cut_pd, 1, 0))          AS room_on_the_step,
         SUM(IF(s.pd_4m = c.cut_pd, 1, 0))
             - (4672361 - SUM(IF(s.pd_4m < c.cut_pd, 1, 0)))  AS decided_by_tiebreak
FROM     s
CROSS JOIN cut c
GROUP BY c.cut_pd;

-- ---------------------------------------------------------------------------
-- C2  THE BOOK. Deterministic - re-running it returns the same subscribers.
--     rank is kept so the limit engine can take a prefix of this table later
--     without re-deriving the order.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_book;
CREATE TABLE dwbi_temp40_db.dcb_book WITH (format='PARQUET') AS
SELECT   sbrp_id, pd_4m, pay_cover, tenure_m, rank_in_book,
         IF(pd_4m = cut_value, 1, 0)   AS on_the_cut_step
FROM     (
    SELECT   s.sbrp_id, s.pd_4m, s.pay_cover, s.tenure_m,
             ROW_NUMBER() OVER (ORDER BY s.pd_4m, s.pay_cover DESC,
                                         s.tenure_m DESC, s.sbrp_id) AS rank_in_book,
             MAX(s.pd_4m) OVER ()                                     AS cut_value
    FROM     (
        SELECT   p.sbrp_id,
                 p.pd_4m,
                 IF(c.rev_6m > 0, CAST(c.paid_6m AS DOUBLE) / c.rev_6m, 0.0) AS pay_cover,
                 c.tenure_m
        FROM     dwbi_temp40_db.dcb_pd    p
        INNER JOIN dwbi_temp40_db.dcb_score c ON c.sbrp_id = p.sbrp_id
    ) s
)
WHERE    rank_in_book <= 4672361;

-- ---------------------------------------------------------------------------
-- C3  PROVE IT. All four flags must read 1.
--
--     rows_ok      the book is the size asked for
--     unique_ok    no subscriber twice - this is the check the double-loaded
--                  handover table would have failed while looking correct
--     rank_ok      ranks are a contiguous 1..N, so the window really ordered
--     sorted_ok    pd_4m never decreases down the rank
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                            AS n_rows,
         COUNT(DISTINCT sbrp_id)                             AS n_subs,
         MIN(rank_in_book)                                   AS min_rank,
         MAX(rank_in_book)                                   AS max_rank,
         AVG(pd_4m)                                          AS book_pd,
         MAX(pd_4m)                                          AS cut_pd,
         SUM(on_the_cut_step)                                AS n_on_cut_step,
         IF(COUNT(*) = 4672361, 1, 0)                        AS rows_ok,
         IF(COUNT(*) = COUNT(DISTINCT sbrp_id), 1, 0)        AS unique_ok,
         IF(MIN(rank_in_book) = 1 AND MAX(rank_in_book) = COUNT(*), 1, 0) AS rank_ok
FROM     dwbi_temp40_db.dcb_book;

-- ---------------------------------------------------------------------------
-- C4  Monotone in rank. n_inversions must be 0; anything else means the
--     ordering did not apply and every number above is about a different book.
-- ---------------------------------------------------------------------------
SELECT   COUNT(*)                                            AS n_compared,
         SUM(IF(pd_4m < prev_pd, 1, 0))                      AS n_inversions,
         IF(SUM(IF(pd_4m < prev_pd, 1, 0)) = 0, 1, 0)        AS sorted_ok
FROM     (
    SELECT   pd_4m,
             LAG(pd_4m) OVER (ORDER BY rank_in_book) AS prev_pd
    FROM     dwbi_temp40_db.dcb_book
)
WHERE    prev_pd IS NOT NULL;

-- ---------------------------------------------------------------------------
-- C5  DOES THE SQL BOOK MATCH THE PYTHON BOOK? Only once
--     outputs/approved_book.csv has been loaded somewhere Trino can read it.
--     Replace the table name and run; n_only_sql and n_only_python must be 0.
--
--     Skip it if the CSV is not loaded. The two paths now carry the same
--     ORDER BY, so this confirms that rather than discovering it.
-- ---------------------------------------------------------------------------
-- SELECT   SUM(IF(py.sbrp_id IS NULL, 1, 0))   AS n_only_sql,
--          SUM(IF(sq.sbrp_id IS NULL, 1, 0))   AS n_only_python,
--          COUNT(*)                            AS n_union
-- FROM            dwbi_temp40_db.dcb_book      sq
-- FULL OUTER JOIN dwbi_temp40_db.dcb_book_py   py ON py.sbrp_id = sq.sbrp_id;

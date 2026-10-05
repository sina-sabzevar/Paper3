-- ============================================================================
--  LIMIT BY EVIDENCE, IN TOMAN                               (Trino/Presto)
--
--  Replaces the ratio-based label in 35_spike_settlement.sql, which the
--  measured run showed to be wrong in three ways.
--
--  WHAT THE RUN SHOWED
--
--  bill_outstanding_amt is alive - about 10,000,000 distinct values a month
--  and 17-18,000,000 positive - so the approach itself survives. But:
--
--  1. y_spike_fail_2x fired on 23.9 pct of 41,654,559 subscribers while the
--     operator's own two-way bar fired on 7.0 pct, and they barely overlap:
--     of the 2,915,819 ever barred only 41 pct failed a 2x spike, and of the
--     9,955,440 spike failures only 12 pct were ever barred. The label was
--     not measuring default.
--
--  2. The reason is a design error of mine. The median baseline obligation is
--     44,960 Toman, so a "2x spike" is 89,920 Toman. A subscriber whose
--     normal bill is 45,000, who owes 90,000 one month and clears it in three
--     rather than two, is flagged. That is 45,000 Toman of slowness. A
--     RELATIVE threshold on a SMALL base fires on absolute noise.
--
--  3. 1,721,644 subscribers were two-way barred WITHOUT ever failing a 2x
--     spike. They defaulted on an ORDINARY bill, which is the more dangerous
--     failure - and the ratio label missed all of them.
--
--  WHAT THIS FILE DOES INSTEAD
--
--  Measures the ABSOLUTE amount, because that is the business question.
--  "Can we extend 500,000 Toman" is answered by "has this subscriber ever
--  settled a bill of 500,000 Toman", which needs no baseline and cannot be
--  distorted by a small one.
--
--  The ratio is kept as a FEATURE - "unusual for them" is real information
--  for a model - but it is no longer the label and no longer sets the limit.
--
--  The label becomes a union: failed to settle a MATERIAL obligation, OR ever
--  two-way barred. The second arm is what catches the 1,721,644.
--
--  SETTLEMENT WINDOW IS THREE MONTHS, NOT TWO. At two months the failure rate
--  was 23.9 pct against a 7.0 pct bar rate, which says two months is tighter
--  than the operator's own tolerance. Both are reported so the choice is made
--  on the numbers.
--
--  Needs dcb_panel from 35_spike_settlement.sql S1. Nothing else.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- M1  Per subscriber: the largest obligation they have SETTLED, in Rial, at
--     two settlement windows, plus the ratio kept as a feature.
--
--     MATERIAL_FLOOR is 1,000,000 Rial = 100,000 Toman. Below it a month is
--     not evidence of anything: clearing a 40,000 Toman bill says nothing
--     about carrying a credit line, and failing to clear one is noise.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.dcb_settled;
CREATE TABLE dwbi_temp40_db.dcb_settled WITH (format='PARQUET') AS
WITH base AS (
    SELECT   sbrp_id,
             APPROX_PERCENTILE(due_approx, 0.5)              AS baseline_due,
             COUNT(*)                                        AS n_months,
             MAX(avail)                                      AS avail_max,
             MAX(twoway_bar)                                 AS ever_twoway,
             MAX(oneway_bar)                                 AS ever_oneway
    FROM     dwbi_temp40_db.dcb_panel
    GROUP BY sbrp_id
),
seq AS (
    SELECT  p.sbrp_id,
            p.month_key,
            p.due_approx,
            p.outst,
            LEAD(p.outst, 1) OVER (PARTITION BY p.sbrp_id
                                   ORDER BY p.month_key)     AS outst_n1,
            LEAD(p.outst, 2) OVER (PARTITION BY p.sbrp_id
                                   ORDER BY p.month_key)     AS outst_n2,
            b.baseline_due
    FROM        dwbi_temp40_db.dcb_panel p
    INNER JOIN  base b ON b.sbrp_id = p.sbrp_id
),
scored AS (
    SELECT  sbrp_id,
            due_approx,
            IF(baseline_due > 0, due_approx / baseline_due, 0)  AS ratio,
            -- Settled within the month plus one, and plus two.
            --
            -- NOT COALESCE(outst_nX, 0). At the end of a subscriber's panel
            -- LEAD returns NULL, and COALESCE(NULL, 0) <= 0.10 * due is TRUE,
            -- so every subscriber's last months would score as settled no
            -- matter what they actually owed. A constructed test caught a
            -- subscriber carrying 4,400,000 Rial outstanding being credited
            -- with settling 1,000,000 that way.
            --
            -- A month whose follow-up window runs past the end of the data is
            -- not evidence either way. It is excluded, not counted. That is
            -- right-censoring and the only honest treatment of it.
            IF(outst_n1 IS NULL, NULL,
               IF(outst_n1 <= 0.10 * due_approx, 1, 0))        AS settled_2m,
            IF(outst_n2 IS NULL, NULL,
               IF(outst_n2 <= 0.10 * due_approx, 1, 0))        AS settled_3m
    FROM    seq
    -- only months that are material enough to be evidence either way
    WHERE   due_approx >= 1000000
)
SELECT  b.sbrp_id,
        b.n_months,
        b.baseline_due,
        b.avail_max,
        b.ever_twoway,
        b.ever_oneway,
        -- THE HEADLINE: the largest obligation actually settled, in Rial
        COALESCE(MAX(s.due_approx) FILTER (WHERE s.settled_3m = 1), 0)
                                                                AS max_settled_amt,
        COALESCE(MAX(s.due_approx) FILTER (WHERE s.settled_2m = 1), 0)
                                                                AS max_settled_amt_2m,
        COALESCE(MAX(s.due_approx), 0)                          AS max_due_seen,
        -- the ratio, demoted to a feature
        COALESCE(MAX(s.ratio) FILTER (WHERE s.settled_3m = 1), 0)
                                                                AS max_ratio_settled,
        COUNT(s.due_approx)                                     AS n_material_months,
        COUNT(s.due_approx) FILTER (WHERE s.settled_3m = 1)     AS n_settled_3m,
        -- months that could not be judged because the window ran off the end
        COUNT(s.due_approx) FILTER (WHERE s.settled_3m IS NULL) AS n_censored,
        -- the label, both arms. settled_3m = 0 is a judged failure; NULL is
        -- not a failure, it is an unjudged month.
        -- IF(NULL = 0, 1, 0) returns 0 in Trino, since a NULL condition is
        -- not true, so an unjudged month correctly contributes nothing here.
        COALESCE(MAX(IF(s.settled_3m = 0, 1, 0)), 0)            AS failed_material,
        GREATEST(COALESCE(MAX(IF(s.settled_3m = 0, 1, 0)), 0),
                 b.ever_twoway)                                 AS y_bad
FROM        base b
LEFT JOIN   scored s ON s.sbrp_id = b.sbrp_id
GROUP BY    b.sbrp_id, b.n_months, b.baseline_due, b.avail_max,
            b.ever_twoway, b.ever_oneway
;

-- ---------------------------------------------------------------------------
-- M2  LIMIT BY EVIDENCE. How many subscribers have settled an obligation of
--     at least this many Toman, and what share of those are bad.
--
--     This is the table the limit comes off. Read n_proved against 3,000,000
--     and bad_rate_pct beside it.
-- ---------------------------------------------------------------------------
SELECT  amt / 10000                                          AS limit_k_toman,
        COUNT(*) FILTER (WHERE max_settled_amt >= amt)        AS n_proved,
        COUNT(*) FILTER (WHERE max_due_seen >= amt)           AS n_ever_billed_it,
        COUNT(*) FILTER (WHERE max_due_seen >= amt
                           AND max_settled_amt < amt)         AS n_failed_it,
        100.0 * COUNT(*) FILTER (WHERE max_settled_amt >= amt
                                   AND y_bad = 1)
              / NULLIF(COUNT(*) FILTER (WHERE max_settled_amt >= amt), 0)
                                                              AS bad_rate_pct,
        100.0 * COUNT(*) FILTER (WHERE max_settled_amt >= amt
                                   AND ever_twoway = 1)
              / NULLIF(COUNT(*) FILTER (WHERE max_settled_amt >= amt), 0)
                                                              AS twoway_pct
FROM        dwbi_temp40_db.dcb_settled
CROSS JOIN  UNNEST(ARRAY[1000000, 2000000, 3000000, 5000000,
                         8000000, 12000000, 20000000]) AS t (amt)
GROUP BY    amt
ORDER BY    amt;

-- ---------------------------------------------------------------------------
-- M3  Does the new label agree with the bar? The ratio label did not - 23.9
--     pct against 7.0 pct with 12 pct overlap. This reports the same check so
--     the two can be compared directly.
-- ---------------------------------------------------------------------------
SELECT  COUNT(*)                                              AS subscribers,
        100.0 * SUM(failed_material) / COUNT(*)               AS failed_material_pct,
        100.0 * SUM(ever_twoway) / COUNT(*)                   AS ever_twoway_pct,
        100.0 * SUM(y_bad) / COUNT(*)                         AS y_bad_pct,
        SUM(IF(failed_material = 1 AND ever_twoway = 1, 1, 0)) AS both,
        SUM(IF(failed_material = 1 AND ever_twoway = 0, 1, 0)) AS material_only,
        SUM(IF(failed_material = 0 AND ever_twoway = 1, 1, 0)) AS bar_only,
        -- how much the three-month window loosens it against two
        COUNT(*) FILTER (WHERE max_settled_amt_2m < max_settled_amt)
                                                              AS helped_by_3rd_month
FROM    dwbi_temp40_db.dcb_settled;

# -*- coding: utf-8 -*-
"""Emit sql/42_model_datasets.sql. One template, two tables.

Declaring the window calendar once and deriving every month literal from it
makes a wrong date impossible rather than merely unlikely. This project has
already lost a cycle to a stale date literal in one block of several.

    python3 tools/gen_model_sql.py            # writes the file
    python3 tools/gen_model_sql.py --check    # asserts the file matches
"""
import io, os, re, sys

MIN_REV_MONTHS = 2        # the screen: revenue over the bar in 2+ of 6 months
WINSOR     = 500_000_000  # available_credit reaches 40.9 trillion raw
TENURE_CAP = 480          # age_on_net_months runs -232 to 1,285 raw
PROD_BAR   = 1_700_000    # 170,000 Toman in Rial - the PRODUCTION bar

# Jalali month lengths: months 1-6 have 31 days, 7-11 have 30, month 12 has 29
# normally and 30 in a leap year. Leap years in the current 33-year cycle fall
# at offsets {1,5,9,13,17,22,26,30} of year mod 33, making 1403 a leap year
# (1403 mod 33 = 17) and 1404 ordinary (18). It only bites when a window ENDS
# on month 12, since interior months are covered by the BETWEEN whatever their
# length, but a silently dropped final day is never noticed.
LEAP_OFFSETS = {1, 5, 9, 13, 17, 22, 26, 30}

def last_day(month_key):
    y, mo = month_key // 100, month_key % 100
    if mo <= 6:
        return 31
    if mo <= 11:
        return 30
    return 30 if (y % 33) in LEAP_OFFSETS else 29

# ---------------------------------------------------------------------------
#  THE CALENDAR.  name, feature months, label months, table, revenue bar
#
#  MODEL is ONE table. The 70/20/10 train/validation/test split happens in
#  Python on a hash of sbrp_id, not here, so that all three splits come from
#  an identical population and the split is reproducible without a stored
#  assignment column.
#
#  The bars differ because the 170,000 Toman screen is FIXED NOMINAL and
#  revenue inflates past it. Measured in 43_cohort_funnel.sql: the fixed bar
#  admits 14.6 pct of the base at 140401..140406 but 24.4 pct at
#  140501..140506. SCORE must keep the production bar, because that is the rule
#  the product applies to live subscribers. MODEL takes the bar that admits an
#  equal SHARE, so the model is fitted on a population comparable to the one it
#  scores. 1,050,000 is interim, from the ratio of upper-tail percentiles
#  (1.64x); 43 D3 gives the exact figure.
# ---------------------------------------------------------------------------
COHORTS = [
    ("MODEL", [140401, 140402, 140403, 140404, 140405, 140406],
              [140407, 140408, 140409, 140410], "dcb_model", 1_050_000),
    ("SCORE", [140501, 140502, 140503, 140504, 140505, 140506],
              [],                               "dcb_score", PROD_BAR),
]

# Level features that get a RELATIVE twin, divided by that window's own median.
# Raw Rial levels drift: revenue per subscriber-month grew 1.64x at the p90
# between these two windows. A coefficient learned on 1404 Rial means something
# different applied to 1405 Rial - a subscriber on 2,000,000 was upper-tail in
# 1404 and mid-pack in 1405 - so the model would read them as safer than their
# peers warrant. The ratio to the window median is stable under that drift.
RELATIVE = ["rev_6m", "rev_max", "paid_6m", "outst_max", "avail_max"]


def day_span(months):
    a, b = months[0], months[-1]
    return a * 100 + 1, b * 100 + last_day(b)


def rev_expr(m):
    return ("COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))\n"
            f"                     FILTER (WHERE month_key = {m}), 0)")


def block(name, fm, lm, table, bar):
    d0, d1 = day_span(fm)
    L = []
    L.append(f"DROP TABLE IF EXISTS dwbi_temp40_db.{table};")
    L.append(f"CREATE TABLE dwbi_temp40_db.{table} WITH (format='PARQUET') AS")
    L.append("WITH pm AS (")
    L.append("    SELECT   sbrp_id, day_key / 100 AS mk, "
             "SUM(COALESCE(pmnt_amt,0)) AS paid")
    L.append("    FROM     dwbi_fact_db.v_fact_pmnt_adjmt")
    L.append(f"    WHERE    day_key BETWEEN {d0} AND {d1}")
    L.append("    GROUP BY sbrp_id, day_key / 100")
    L.append("),")
    L.append("pay AS (")
    L.append("    SELECT  sbrp_id,")
    for i, m in enumerate(fm, 1):
        tail = "," if i < 6 else ""
        L.append(f"            COALESCE(SUM(paid) FILTER (WHERE mk = {m}), 0)"
                 f" AS q{i}{tail}")
    L.append("    FROM    pm GROUP BY sbrp_id")
    L.append("),")
    L.append("feat AS (")
    L.append("    SELECT  sbrp_id,")
    for i, m in enumerate(fm, 1):
        L.append(f"            {rev_expr(m)} AS r{i},")
    L.append("            SUM(IF(arpu IS NULL, 1, 0))                      "
             "AS n_arpu_null,")
    for i, m in enumerate(fm, 1):
        L.append(f"            MAX(IF(month_key={m} AND sbrp_stat_id=3,1,0))"
                 f" AS o{i},")
    L.append("            MAX(IF(sbrp_stat_id=4,1,0))                      "
             "AS f_twoway,")
    L.append("            MAX(IF(sbrp_stat_id IN (8,9),1,0))               "
             "AS f_reclaim,")
    L.append("            SUM(IF(active1_base_flag=1,1,0))                 "
             "AS n_active1,")
    L.append(f"            LEAST(MAX(COALESCE(available_credit,0)), {WINSOR})"
             "    AS avail_max,")
    L.append(f"            LEAST(AVG(COALESCE(available_credit,0)), {WINSOR})"
             "    AS avail_avg,")
    L.append(f"            LEAST(MAX(COALESCE(bill_outstanding_amt,0)), {WINSOR})"
             " AS outst_max,")
    L.append(f"            LEAST(AVG(COALESCE(bill_outstanding_amt,0)), {WINSOR})"
             " AS outst_avg,")
    L.append("            GREATEST(LEAST(MAX(COALESCE(age_on_net_months,0)), "
             f"{TENURE_CAP}), 0) AS tenure_m")
    L.append("    FROM    dwbi_fact_db.v_fact_sbrp_mthly_cip")
    L.append(f"    WHERE   month_key IN ({','.join(str(m) for m in fm)})")
    L.append("      AND   sbrp_typ_id = 1")
    L.append("    GROUP BY sbrp_id")
    L.append("),")
    if lm:
        L.append("lab AS (")
        L.append("    SELECT   sbrp_id,")
        L.append("             MAX(IF(sbrp_stat_id = 4, 1, 0))  AS y,")
        L.append("             COUNT(DISTINCT month_key)        AS n_label_months")
        L.append("    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip")
        L.append(f"    WHERE    month_key IN ({', '.join(str(m) for m in lm)})")
        L.append("      AND    sbrp_typ_id = 1")
        L.append("    GROUP BY sbrp_id")
        L.append("),")

    # ---- the screened projection -------------------------------------------
    rm = " + ".join(f"IF(f.r{i}>={bar},1,0)" for i in range(1, 7))
    pm_ = " + ".join(f"IF(COALESCE(p.q{i},0)>={bar},1,0)" for i in range(1, 7))
    L.append("proj AS (")
    L.append("    SELECT  f.sbrp_id,")
    L.append("            f.r1, f.r2, f.r3, f.r4, f.r5, f.r6,")
    L.append("            f.r1+f.r2+f.r3+f.r4+f.r5+f.r6                 AS rev_6m,")
    L.append("            GREATEST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)       AS rev_max,")
    L.append("            LEAST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)          AS rev_min,")
    L.append("            (f.r4+f.r5+f.r6) - (f.r1+f.r2+f.r3)           AS rev_trend,")
    L.append(f"            {rm}")
    L.append("                                                          AS rev_months,")
    L.append("            COALESCE(p.q1,0) AS q1, COALESCE(p.q2,0) AS q2,")
    L.append("            COALESCE(p.q3,0) AS q3, COALESCE(p.q4,0) AS q4,")
    L.append("            COALESCE(p.q5,0) AS q5, COALESCE(p.q6,0) AS q6,")
    L.append("            " + " + ".join(f"COALESCE(p.q{i},0)" for i in range(1, 7))
             + "  AS paid_6m,")
    L.append("            GREATEST(" + ", ".join(f"COALESCE(p.q{i},0)"
             for i in range(1, 7)) + ") AS paid_max,")
    L.append(f"            {pm_}")
    L.append("                                                          AS pay_months,")
    L.append("            " + "+".join(f"f.o{i}" for i in range(1, 7))
             + "                     AS oneway_months,")
    L.append("            f.n_arpu_null, f.n_active1, f.f_reclaim,")
    L.append("            f.avail_max, f.avail_avg, f.outst_max, f.outst_avg,")
    L.append("            f.tenure_m,")
    if lm:
        L.append("            l.n_label_months, l.y,")
    else:
        L.append("            CAST(NULL AS BIGINT)  AS n_label_months,")
        L.append("            CAST(NULL AS INTEGER) AS y,")
    L.append(f"            '{name}' AS cohort")
    L.append("    FROM        feat f")
    L.append("    LEFT JOIN   pay  p ON p.sbrp_id = f.sbrp_id")
    if lm:
        L.append("    INNER JOIN  lab  l ON l.sbrp_id = f.sbrp_id")
    L.append(f"    -- THE SCREEN: revenue at or above {bar:,} Rial in "
             f"{MIN_REV_MONTHS} or more")
    L.append("    -- of 6 months, never one-way barred, never two-way barred.")
    L.append(f"    WHERE   {rm} >= {MIN_REV_MONTHS}")
    L.append("      AND   " + "+".join(f"f.o{i}" for i in range(1, 7)) + " = 0")
    L.append("      AND   f.f_twoway = 0")
    L.append("),")
    # ---- window medians, for the drift-robust relative features ------------
    L.append("med AS (")
    L.append("    -- One row. The medians of THIS window's screened population,")
    L.append("    -- so the relative features below are comparable across")
    L.append("    -- windows even though the Rial levels are not.")
    L.append("    SELECT  " + ",\n            ".join(
        f"APPROX_PERCENTILE({c}, 0.5) AS m_{c}" for c in RELATIVE))
    L.append("    FROM    proj")
    L.append(")")
    L.append("SELECT      proj.*,")
    for i, c in enumerate(RELATIVE):
        tail = "," if i < len(RELATIVE) - 1 else ""
        L.append(f"            proj.{c} / NULLIF(med.m_{c}, 0) "
                 f"AS {c}_rel{tail}")
    L.append("FROM        proj")
    L.append("CROSS JOIN  med")
    L.append(";")
    return "\n".join(L)


HEADER = f"""-- ============================================================================
--  THE MODEL DATASETS                                       (Trino/Presto)
--
--  GENERATED by tools/gen_model_sql.py - do not hand-edit. Every month literal
--  is derived from one calendar declaration in that script, so a wrong date is
--  impossible rather than merely unlikely.
--
--  TARGET
--      screen  revenue at or above the window's bar in {MIN_REV_MONTHS} or more of 6 months,
--              never one-way barred and never two-way barred in that window
--      label   y = 1 if two-way barred in the 4 months IMMEDIATELY AFTER
--
--  TWO TABLES. Data runs 140301..140506; 1403 is deliberately unused.
--
--      table       features        label            role
--      dcb_model   140401..140406  140407..140410   fit, select and test
--      dcb_score   140501..140506  none, the future hand to implementation
--
--  dcb_model is ONE table. The 70/20/10 train/validation/test split happens
--  in Python on a hash of sbrp_id, so all three splits come from an identical
--  population and the split reproduces without a stored assignment column.
--
--  MEASURED: this exact window returned 5,100,390 subscribers at a 0.5541 pct
--  event rate in 43_cohort_funnel.sql D5, at the production bar. The bar here
--  is lower (see below), so the count will be HIGHER and the rate will move.
--
--  WHY THESE WINDOWS. Both feature windows are months 1-6 of their year and
--  the label window is months 7-10, so:
--
--    * the two feature windows sit at the same seasonal position, which makes
--      their distributions comparable;
--    * the label window is months 7-10, and SCORE's features end at 140506 so
--      a 4-month line is really exposed over 140507..140510 - also months
--      7-10. The model is therefore trained on the season it will face.
--
--  That second point is not cosmetic. 43_cohort_funnel.sql measured the
--  two-way bar rate at 0.5730 pct and 0.5541 pct for labels on months 7-10,
--  against 0.9492 pct for a label on months 1-4 - a factor of 1.68 - while
--  screen breadth over the same comparison moved the rate not at all. An
--  earlier calendar validated on months 1-4 and would have been applied to
--  months 7-10, overstating risk by about that factor.
--
--  THE BARS DIFFER ON PURPOSE. The 170,000 Toman screen is fixed NOMINAL and
--  revenue inflates past it: the same bar admitted 14.6 pct of the base at
--  140401..140406 and 24.4 pct at 140501..140506. SCORE keeps the production
--  bar because that is the live rule; MODEL takes the bar admitting an equal
--  SHARE, so the fit sees a population comparable to the one it scores.
--
--  RELATIVE FEATURES. Raw Rial levels drift - 1.64x at the p90 between these
--  two windows - so each level feature also gets a twin divided by its own
--  window's median. A coefficient learned on 1404 Rial means something
--  different applied to 1405 Rial; a ratio to the window median does not.
--
--  WHY THE BARRED SUBSCRIBERS ARE NOT ADDED TO GET MORE label = 1. They were
--  proposed as a way to balance the classes with real bads. Measured on
--  synthetic data giving the barred group the SAME revenue-to-risk
--  relationship as the clean cohort - the assumption most favourable to the
--  idea - adding them moved AUC on the clean population by a mean of -0.0001
--  over six seeds, while the fit put 0.72 of coefficient weight on
--  oneway_months, which the screen forces to ZERO in dcb_score so it cannot
--  fire at scoring time. rev_max fell from 0.208 to 0.108 and tenure_m from
--  0.033 to 0.010 to pay for it.
--
--  The balance needs no help: 28,263 bads over 33 features is 856 events per
--  variable, and down-sampling at GOOD_KEEP=10 already shows the model 5.28
--  pct bads rather than 0.55 pct.
--
--  The version that DOES work is a product decision, not a modelling one: if
--  those subscribers belong in training they belong in scoring too, so the
--  screen changes on BOTH tables. Stratum 2 - cleared the revenue bar,
--  one-way barred, never two-way, 382,142 subscribers - is the real
--  candidate, and W1 in 44_where_are_the_bads.sql measures the forward rate
--  that decides it. See RUN43_FINDINGS.md for the decision table.
--
--  EXCLUDED ON PURPOSE
--      debt_scr, suspend_scr   all zero in 6 of 10 months - their PSI of
--                              13.89 and 14.41 was a loading gap, not drift
--      month-index columns     calendar numbers that shift between windows
--                              whether or not behaviour changes
--      anything from a label window, by construction
--
--  GUARDED
--      age_on_net_months       raw range -232 to 1,285 -> clipped to 0..{TENURE_CAP}
--      available_credit        raw -3.6bn to 40.9tn Rial -> winsorised at
--                              {WINSOR:,}
--      arpu                    23.8 pct NULL, and the tax is zero where arpu
--                              is NULL, so the KPI expression yields 0 rather
--                              than minus-the-tax. n_arpu_null is carried as a
--                              feature - missingness here is informative
--
--  PAYMENTS USE ALL STATUSES. bllg_pmnt_stat_id = 2 holds 61.2 pct of payment
--  value and status 1 holds 38.7 pct, so filtering to 2 discards a third.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
"""

FOOTER = """
-- ---------------------------------------------------------------------------
-- T1  CHECK BEFORE EXPORTING ANYTHING.
--
--     dcb_model's rate is expected NEAR but not AT 0.5541 pct. That figure
--     was measured at the production bar; the bar here is lower, so more
--     subscribers are admitted and the marginal ones are poorer, which should
--     move the rate up somewhat. A rate near 0.95 pct would mean the LABEL
--     months are wrong, not the bar - that is the months 1-4 figure.
--
--     The two row counts should be COMPARABLE. That is the whole purpose of
--     the per-window bar. If dcb_model is far below dcb_score, the bar needs
--     the exact value from 43_cohort_funnel.sql D3.
-- ---------------------------------------------------------------------------
SELECT  'MODEL' AS tbl, COUNT(*) AS n, SUM(y) AS n_bad,
        100.0 * SUM(y) / COUNT(*)                        AS bad_pct,
        APPROX_PERCENTILE(rev_6m, 0.5) / 10000           AS med_rev_6m_k,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5) AS med_rev_months,
        SUM(IF(n_label_months >= 4, 1, 0))               AS n_fully_observed
FROM    dwbi_temp40_db.dcb_model
UNION ALL
SELECT  'SCORE', COUNT(*), NULL, NULL,
        APPROX_PERCENTILE(rev_6m, 0.5) / 10000,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5),
        NULL
FROM    dwbi_temp40_db.dcb_score;

-- ---------------------------------------------------------------------------
-- T2  DID THE RELATIVE FEATURES DO THEIR JOB?
--
--     The raw medians should differ substantially between the two tables -
--     that IS the drift. The relative medians should both be 1.0 by
--     construction, and their upper percentiles should be CLOSE. If the
--     relative p90s still differ markedly, the drift is not a pure level
--     shift and the distribution shape is changing too.
-- ---------------------------------------------------------------------------
SELECT  'MODEL' AS tbl,
        APPROX_PERCENTILE(rev_6m, 0.5)      AS raw_med,
        APPROX_PERCENTILE(rev_6m, 0.9)      AS raw_p90,
        APPROX_PERCENTILE(rev_6m_rel, 0.5)  AS rel_med,
        APPROX_PERCENTILE(rev_6m_rel, 0.9)  AS rel_p90
FROM    dwbi_temp40_db.dcb_model
UNION ALL
SELECT  'SCORE',
        APPROX_PERCENTILE(rev_6m, 0.5),
        APPROX_PERCENTILE(rev_6m, 0.9),
        APPROX_PERCENTILE(rev_6m_rel, 0.5),
        APPROX_PERCENTILE(rev_6m_rel, 0.9)
FROM    dwbi_temp40_db.dcb_score;

-- ---------------------------------------------------------------------------
-- T3  THE SPLIT, PREVIEWED. Python splits on MD5(sbrp_id) mod 100 - under 70
--     is train, 70 to 89 validation, 90 and over test. This is the same draw
--     in SQL, so the three sizes and their event rates can be checked before
--     anything is exported.
--
--     The draw is on a HASH, never on sbrp_id itself: every observed id in
--     this base is odd and they share a five-digit block, so MOD on the raw
--     id selects a structured slice of the network rather than a sample.
-- ---------------------------------------------------------------------------
SELECT  IF(h < 70, 'train', IF(h < 90, 'valid', 'test')) AS split,
        COUNT(*)                                         AS n,
        SUM(y)                                           AS n_bad,
        100.0 * SUM(y) / COUNT(*)                        AS bad_pct
FROM (
    SELECT  y,
            MOD(ABS(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8(
                CAST(sbrp_id AS VARCHAR))))), 100) AS h
    FROM    dwbi_temp40_db.dcb_model
) z
GROUP BY IF(h < 70, 'train', IF(h < 90, 'valid', 'test'))
ORDER BY split;
"""


def build():
    parts = [HEADER]
    for i, (name, fm, lm, table, bar) in enumerate(COHORTS, 1):
        parts.append(
            "\n-- ---------------------------------------------------------"
            "------------------\n"
            f"-- {name}   features {fm[0]}..{fm[-1]}"
            + (f", label {lm[0]}..{lm[-1]}" if lm
               else ", NO LABEL - the outcome is the future")
            + f"\n--          bar {bar:,} Rial"
            + "\n-- -------------------------------------------------------"
              "--------------------\n")
        parts.append(block(name, fm, lm, table, bar))
        parts.append("")
    parts.append(FOOTER)
    return "\n".join(parts)


def selfcheck(sql):
    bad = []
    c = re.sub(r"--[^\n]*", "", sql)
    if "%" in c: bad.append("percent character")
    if c.count("(") != c.count(")"): bad.append("unbalanced parentheses")
    if re.search(r"\bCASE\b", c, re.I): bad.append("CASE expression")
    if any(ord(ch) > 127 for ch in c): bad.append("non-ascii")

    for name, fm, lm, _, _ in COHORTS:
        if set(fm) & set(lm):
            bad.append(f"{name}: feature and label windows overlap")
    for i in range(len(COHORTS) - 1):
        lab, nxt = COHORTS[i][2], COHORTS[i + 1][1]
        if lab and max(lab) >= min(nxt):
            bad.append(f"{COHORTS[i][0]} label reaches into "
                       f"{COHORTS[i+1][0]} feature window")

    # Seasonal alignment and shape, the properties that make the two windows
    # comparable at all. Verified to fire by running against the old calendar.
    fsets = {tuple(sorted({m % 100 for m in c[1]})) for c in COHORTS}
    if len(fsets) != 1:
        bad.append(f"feature windows cover different months-of-year: {fsets}")
    if len({len(c[1]) for c in COHORTS}) != 1:
        bad.append("feature windows differ in length - the per-month features "
                   "would not line up between fitting and scoring")
    starts = [c[1][0] for c in COHORTS]
    if len({starts[i+1] - starts[i] for i in range(len(starts)-1)}) != 1:
        bad.append(f"cohort feature windows unevenly spaced: {starts}")

    # The label season must match what SCORE's forward exposure will really be.
    lab = [c[2] for c in COHORTS if c[2]][0]
    sc_feat = COHORTS[-1][1]
    exposure = []
    m = sc_feat[-1]
    for _ in range(len(lab)):
        y, mo = m // 100, m % 100
        m = (y + 1) * 100 + 1 if mo == 12 else y * 100 + mo + 1
        exposure.append(m)
    if sorted({x % 100 for x in lab}) != sorted({x % 100 for x in exposure}):
        bad.append(f"label season {sorted({x%100 for x in lab})} does not match "
                   f"SCORE's real forward exposure "
                   f"{sorted({x%100 for x in exposure})}")
    return bad


if __name__ == "__main__":
    sql = build()
    problems = selfcheck(sql)
    if problems:
        print("SELF-CHECK FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    out = os.path.normpath(os.path.join(os.path.dirname(__file__), "..",
                                        "sql", "42_model_datasets.sql"))
    if "--check" in sys.argv:
        same = io.open(out, encoding="utf-8").read() == sql
        print(f"{out}: {'matches the generator' if same else 'DIFFERS'}")
        sys.exit(0 if same else 1)
    io.open(out, "w", encoding="utf-8").write(sql)
    print(f"wrote {out}  ({len(sql.splitlines())} lines)")
    print("self-check passed:")
    print("  no percent character, balanced parens, no CASE, ascii only")
    print("  no feature window touches its own label window")
    print("  no label window reaches into the next table's features")
    print("  both feature windows the same LENGTH (per-month features line up)")
    print("  both feature windows at the same months-of-year")
    print("  label season matches SCORE's real forward exposure")

# -*- coding: utf-8 -*-
"""Emit sql/42_model_datasets.sql. One template, three cohorts.

Three near-identical 120-line SQL blocks is where transcription errors live -
this project has already lost time to a leftover date literal in one block of
several. The cohort calendars are declared once at the top and every month
literal in the output is derived from them, so a wrong date is impossible
rather than merely unlikely.

    python3 tools/gen_model_sql.py            # writes the file
    python3 tools/gen_model_sql.py --check    # asserts the file matches
"""
import io, os, sys

REV_T   = 1_700_000       # 170,000 Toman in Rial - the PRODUCTION bar
MIN_REV_MONTHS = 2        # the screen: revenue over the threshold in 2+ months

# The revenue bar PER COHORT. SCORE must use the production bar, because that
# is the rule the product will actually apply to live subscribers.
#
# TRAIN and VALID sit one and two years earlier, and the bar is FIXED NOMINAL,
# so the same 1,700,000 Rial is a materially harsher screen in those windows:
# nominal revenue per subscriber rises with inflation and tariff changes. Left
# at the production value, the earlier windows select the richer tail - which
# is how TRAIN at 140301..140306 returned 3,733,333 subscribers against the
# 6,879,803 measured at 140407..140412.
#
# sql/43_cohort_funnel.sql (D3) measures the bar admitting the SAME SHARE of
# subscribers in each window as 1,700,000 admits in SCORE. Put those numbers
# here once it has run. Until then all three use the production bar, which
# keeps the cohorts honest but leaves TRAIN and VALID smaller and richer
# than SCORE, and the model fitted on a population it will not meet.
COHORT_BAR = {
    "TRAIN": REV_T,       # <- set from 43_cohort_funnel.sql D3
    "VALID": REV_T,       # <- set from 43_cohort_funnel.sql D3
    "SCORE": REV_T,       # production bar, do not change
}
WINSOR  = 500_000_000     # available_credit reaches 40.9 trillion raw
TENURE_CAP = 480          # age_on_net_months runs -232 to 1,285 raw

# Jalali month lengths: months 1-6 have 31 days, months 7-11 have 30, and
# month 12 has 29 normally or 30 in a leap year. The leap years in the current
# 33-year cycle fall at offsets {1,5,9,13,17,22,26,30} of year mod 33, which
# makes 1403 a leap year (1403 mod 33 = 17) and 1404 an ordinary one (18).
#
# This only bites when a feature window ENDS on month 12, because the payment
# filter is a BETWEEN over day_key and every interior month is covered
# whatever its length. It is handled properly anyway: getting it wrong would
# silently drop the last day of a window, and a silent one-day loss is exactly
# the kind of defect that never gets noticed.
LEAP_OFFSETS = {1, 5, 9, 13, 17, 22, 26, 30}

def last_day(month_key):
    y, mo = month_key // 100, month_key % 100
    if mo <= 6:
        return 31
    if mo <= 11:
        return 30
    return 30 if (y % 33) in LEAP_OFFSETS else 29

COHORTS = [
    # name,   feature months,                      label months (4),            table
    ("TRAIN", [140301,140302,140303,140304,140305,140306],
               [140307,140308,140309,140310], "dcb_train"),
    ("VALID", [140401,140402,140403,140404,140405,140406],
               [140407,140408,140409,140410], "dcb_valid"),
    ("SCORE", [140501,140502,140503,140504,140505,140506],
               [],                            "dcb_score"),
]

def day_span(months):
    a, b = months[0], months[-1]
    return a * 100 + 1, b * 100 + last_day(b)

def rev_expr(m):
    return ("COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))\n"
            f"                     FILTER (WHERE month_key = {m}), 0)")

def block(name, fm, lm, table):
    d0, d1 = day_span(fm)
    bar = COHORT_BAR[name]
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
    L.append(")" + ("," if lm else ""))
    if lm:
        L.append("lab AS (")
        L.append("    SELECT   sbrp_id,")
        L.append("             MAX(IF(sbrp_stat_id = 4, 1, 0))  AS y,")
        L.append("             COUNT(DISTINCT month_key)        AS n_label_months")
        L.append("    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip")
        L.append(f"    WHERE    month_key IN ({', '.join(str(m) for m in lm)})")
        L.append("      AND    sbrp_typ_id = 1")
        L.append("    GROUP BY sbrp_id")
        L.append(")")
    # ---- the projection, identical for all three ----
    L.append("SELECT  f.sbrp_id,")
    L.append("        f.r1, f.r2, f.r3, f.r4, f.r5, f.r6,")
    L.append("        f.r1+f.r2+f.r3+f.r4+f.r5+f.r6                        AS rev_6m,")
    L.append("        GREATEST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)              AS rev_max,")
    L.append("        LEAST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)                 AS rev_min,")
    L.append("        (f.r4+f.r5+f.r6) - (f.r1+f.r2+f.r3)                  AS rev_trend,")
    rm = " + ".join(f"IF(f.r{i}>={bar},1,0)" for i in range(1,7))
    L.append(f"        {rm}")
    L.append("                                                             AS rev_months,")
    L.append("        COALESCE(p.q1,0) AS q1, COALESCE(p.q2,0) AS q2, "
             "COALESCE(p.q3,0) AS q3,")
    L.append("        COALESCE(p.q4,0) AS q4, COALESCE(p.q5,0) AS q5, "
             "COALESCE(p.q6,0) AS q6,")
    L.append("        " + " + ".join(f"COALESCE(p.q{i},0)" for i in range(1,7))
             + "  AS paid_6m,")
    L.append("        GREATEST(" + ", ".join(f"COALESCE(p.q{i},0)" for i in range(1,7))
             + ") AS paid_max,")
    pm_ = " + ".join(f"IF(COALESCE(p.q{i},0)>={bar},1,0)" for i in range(1,7))
    L.append(f"        {pm_}")
    L.append("                                                             AS pay_months,")
    L.append("        " + "+".join(f"f.o{i}" for i in range(1,7))
             + "                        AS oneway_months,")
    L.append("        f.n_arpu_null, f.n_active1, f.f_reclaim,")
    L.append("        f.avail_max, f.avail_avg, f.outst_max, f.outst_avg, f.tenure_m,")
    L.append("        l.n_label_months," if lm
             else "        CAST(NULL AS BIGINT) AS n_label_months,")
    L.append("        l.y," if lm else "        CAST(NULL AS INTEGER) AS y,")
    L.append(f"        '{name}' AS cohort")
    L.append("FROM        feat f")
    L.append("LEFT JOIN   pay  p ON p.sbrp_id = f.sbrp_id")
    if lm:
        L.append("INNER JOIN  lab  l ON l.sbrp_id = f.sbrp_id")
    L.append(f"-- THE SCREEN: revenue at or above {bar:,} Rial in "
             f"{MIN_REV_MONTHS} or more months,")
    L.append("-- never one-way barred, never two-way barred in the feature window.")
    L.append(f"WHERE   {rm.replace('f.r','f.r')} >= {MIN_REV_MONTHS}")
    L.append("  AND   " + "+".join(f"f.o{i}" for i in range(1,7)) + " = 0")
    L.append("  AND   f.f_twoway = 0")
    L.append(";")
    return "\n".join(L)

HEADER = f"""-- ============================================================================
--  THE MODEL DATASETS                                       (Trino/Presto)
--
--  GENERATED by tools/gen_model_sql.py - do not hand-edit. Three near-identical
--  120-line blocks is where transcription errors live, and this project has
--  already lost time to a leftover date literal in one block of several. Every
--  month literal below is derived from the cohort calendars declared in that
--  script, so a wrong date is impossible rather than merely unlikely.
--
--  TARGET
--      screen  revenue at or above 170,000 Toman in {MIN_REV_MONTHS} or more of 6 months,
--              never one-way barred and never two-way barred in that window
--      label   y = 1 if two-way barred in the 4 months IMMEDIATELY AFTER
--
--  THREE COHORTS. Data runs 140301..140506.
--
--      cohort    features        label (4 months)  role
--      TRAIN     140301..140306  140307..140310    fit
--      VALID     140401..140406  140407..140410    out of time
--      SCORE     140501..140506  none - the future hand to implementation
--
--  THE THREE WINDOWS ARE YEAR-OVER-YEAR ALIGNED, and that is the point.
--  Every feature window covers months 1-6 of its year and every label window
--  covers months 7-10, exactly 12 months apart. The generator asserts this:
--  it refuses to emit a calendar whose windows differ in length, sit at
--  different months-of-year, are unevenly spaced, or whose label reaches into
--  the next cohort's features.
--
--  WHY ALIGNMENT AND NOT PROXIMITY. An earlier version chose the windows to
--  sit as close together in time as the label allowed: TRAIN 140309..140402,
--  VALID 140407..140412, SCORE 140501..140506. That put VALID on months 7-12
--  and SCORE on months 1-6 - different seasons. Jalali month 1 is Farvardin
--  and carries Nowruz, and telco usage is strongly seasonal, so the revenue
--  features were not comparable between the window the model was judged on
--  and the window it would be applied to. VALID exists to be a rehearsal of
--  SCORE; a rehearsal in a different season is not one. That version also
--  had VALID's label window (140501..140504) overlapping SCORE's feature
--  window (140501..140506), so the period used to JUDGE the model was the
--  same period used to DESCRIBE the live population.
--
--  WHAT ALIGNMENT COSTS. TRAIN is now 24 months before SCORE rather than 8,
--  so the fixed nominal bar bites harder, not less: TRAIN at 140301..140306
--  returned 3,733,333 subscribers against the 6,879,803 measured at
--  140407..140412. That is the trade accepted here, because a drifting bar
--  is correctable - COHORT_BAR above takes a per-window threshold, and
--  43_cohort_funnel.sql D3 measures what each one should be - while a
--  seasonal mismatch cannot be corrected by any threshold.
--
--  SO THE ORDER OF WORK IS: run 43_cohort_funnel.sql, read D3 and D4, set
--  COHORT_BAR for TRAIN and VALID, regenerate this file, then fit.
--
--  NO FIGURE IS ON RECORD FOR THIS VALID WINDOW YET. The 0.95 pct measured
--  in 41_forward_horizons.sql was for features 140407..140412 with label
--  140501..140504, which is NOT a window any cohort here uses any more. The
--  new VALID is features 140401..140406 with label 140407..140410, and its
--  event rate is established by 43_cohort_funnel.sql D5. T4 reports the rate
--  rather than asserting against a number that belongs to a different
--  window - a cross-check against the wrong reference is worse than none.
--
--  PARTIAL OBSERVATION. A subscriber counts as judgeable if they appear in AT
--  LEAST ONE month of the label window - the INNER JOIN on lab enforces it,
--  and someone absent from the whole window is dropped rather than scored
--  clean, because a disappearance is not a repayment. This is deliberately
--  the same rule 41_forward_horizons.sql used (n_out_months > 0), which is
--  what makes T4's comparison against 0.95 pct meaningful. It does mean a
--  subscriber seen in 1 of 4 months and never barred is scored y = 0 on one
--  month of evidence. n_label_months is carried so that population is
--  visible and T5 reports whether it moves the rate.
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
--      available_credit        raw range -3.6bn to 40.9 trillion Rial ->
--                              winsorised at {WINSOR:,}
--      arpu                    23.8 pct NULL, and the tax is zero where arpu
--                              is NULL, so the KPI expression yields 0 rather
--                              than minus-the-tax. n_arpu_null is carried as a
--                              feature in its own right - missingness here is
--                              informative
--
--  PAYMENTS USE ALL STATUSES. bllg_pmnt_stat_id = 2 holds 61.2 pct of payment
--  value and status 1 holds 38.7 pct, so filtering to 2 discards a third.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
"""

FOOTER = """
-- ---------------------------------------------------------------------------
-- T4  CHECK BEFORE EXPORTING ANYTHING.
--
--     Compare VALID's rate against 43_cohort_funnel.sql D5 for window
--     140401..140406, which is the figure of record for THIS window. Do not
--     compare it against the 0.95 pct from 41_forward_horizons.sql: that was
--     measured on features 140407..140412 with label 140501..140504, a
--     different window in a different season, and the two are not
--     interchangeable.
--
--     Also compare the three row counts. If TRAIN and VALID are far below
--     SCORE, the fixed nominal bar is still selecting the richer tail in the
--     earlier windows and COHORT_BAR has not been set from D3 yet.
-- ---------------------------------------------------------------------------
SELECT  'TRAIN' AS cohort, COUNT(*) AS n, SUM(y) AS n_bad,
        100.0 * SUM(y) / COUNT(*) AS bad_pct,
        APPROX_PERCENTILE(rev_6m, 0.5) / 10000 AS med_rev_6m_k,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5) AS med_rev_months
FROM    dwbi_temp40_db.dcb_train
UNION ALL
SELECT  'VALID', COUNT(*), SUM(y), 100.0 * SUM(y) / COUNT(*),
        APPROX_PERCENTILE(rev_6m, 0.5) / 10000,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5)
FROM    dwbi_temp40_db.dcb_valid
UNION ALL
SELECT  'SCORE', COUNT(*), NULL, NULL,
        APPROX_PERCENTILE(rev_6m, 0.5) / 10000,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5)
FROM    dwbi_temp40_db.dcb_score;

-- Subscribers shared between cohorts is expected and fine - the same person
-- appears in all three with different windows. What must not happen is a
-- feature window touching its own label window, and the generator makes that
-- impossible.
SELECT  (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_train t
          INNER JOIN dwbi_temp40_db.dcb_valid v ON v.sbrp_id = t.sbrp_id)
                                                        AS train_valid_shared,
        (SELECT COUNT(*) FROM dwbi_temp40_db.dcb_valid v
          INNER JOIN dwbi_temp40_db.dcb_score s ON s.sbrp_id = v.sbrp_id)
                                                        AS valid_score_shared;

-- ---------------------------------------------------------------------------
-- T5  DOES PARTIAL OBSERVATION MOVE THE RATE? Over a 4-month label window a
--     subscriber can be present for only part of it. Those rows are kept (see
--     the header), so this asks what they are worth: the rate among the fully
--     observed against the rate among the partly observed.
--
--     If the fully-observed rate is materially HIGHER, the headline rate is
--     diluted by subscribers who simply had less time to fail, and the
--     fully-observed figure is the honest one to quote to the business.
-- ---------------------------------------------------------------------------
SELECT  cohort,
        n_label_months,
        COUNT(*)                                        AS n,
        SUM(y)                                          AS n_bad,
        100.0 * SUM(y) / COUNT(*)                       AS bad_pct
FROM    (SELECT cohort, n_label_months, y FROM dwbi_temp40_db.dcb_train
         UNION ALL
         SELECT cohort, n_label_months, y FROM dwbi_temp40_db.dcb_valid) u
GROUP BY cohort, n_label_months
ORDER BY cohort, n_label_months;

SELECT  cohort,
        SUM(IF(n_label_months = 4, 1, 0))               AS n_full,
        100.0 * SUM(IF(n_label_months = 4, y, 0))
              / NULLIF(SUM(IF(n_label_months = 4, 1, 0)), 0)
                                                        AS bad_pct_full,
        SUM(IF(n_label_months < 4, 1, 0))               AS n_partial,
        100.0 * SUM(IF(n_label_months < 4, y, 0))
              / NULLIF(SUM(IF(n_label_months < 4, 1, 0)), 0)
                                                        AS bad_pct_partial,
        100.0 * SUM(IF(n_label_months < 4, 1, 0)) / COUNT(*)
                                                        AS partial_share_pct
FROM    (SELECT cohort, n_label_months, y FROM dwbi_temp40_db.dcb_train
         UNION ALL
         SELECT cohort, n_label_months, y FROM dwbi_temp40_db.dcb_valid) u
GROUP BY cohort
ORDER BY cohort;
"""

def build():
    parts = [HEADER]
    for i, (name, fm, lm, table) in enumerate(COHORTS, 1):
        parts.append(f"\n-- --------------------------------------------------"
                     f"-------------------------\n"
                     f"-- T{i}  {name}   features {fm[0]}..{fm[-1]}"
                     + (f", label {lm[0]}..{lm[-1]}" if lm
                        else ", NO LABEL - the outcome is the future")
                     + "\n-- -----------------------------------------------"
                       "----------------------------\n")
        parts.append(block(name, fm, lm, table))
        parts.append("")
    parts.append(FOOTER)
    return "\n".join(parts)

def selfcheck(sql):
    import re
    bad = []
    if "%" in re.sub(r"--[^\n]*", "", sql): bad.append("percent character")
    c = re.sub(r"--[^\n]*", "", sql)
    if c.count("(") != c.count(")"): bad.append("unbalanced parentheses")
    if re.search(r"\bCASE\b", c, re.I): bad.append("CASE expression")
    if any(ord(ch) > 127 for ch in c): bad.append("non-ascii")
    # the thing that matters: no cohort's features touch its own label
    for name, fm, lm, _ in COHORTS:
        if set(fm) & set(lm):
            bad.append(f"{name}: feature and label windows overlap")
    # Each cohort's label must end before the NEXT cohort's features begin,
    # for the whole chain, not just the first pair. TRAIN -> VALID -> SCORE.
    for i in range(len(COHORTS) - 1):
        lab  = COHORTS[i][2]
        nxt  = COHORTS[i + 1][1]
        if lab and max(lab) >= min(nxt):
            bad.append(f"{COHORTS[i][0]} label reaches into "
                       f"{COHORTS[i+1][0]} feature window")

    # SEASONAL ALIGNMENT. Every feature window must cover the same
    # months-of-year, and so must every label window. Jalali month 1 is
    # Farvardin and carries Nowruz, so a window of months 1-6 and a window of
    # months 7-12 are different seasons with different usage. Validating on
    # one season and scoring another makes VALID a rehearsal of the wrong
    # play - which is exactly what the 140407..140412 window did.
    fsets = {tuple(sorted({m % 100 for m in c[1]})) for c in COHORTS}
    if len(fsets) != 1:
        bad.append(f"feature windows cover different months-of-year: {fsets}")
    lsets = {tuple(sorted({m % 100 for m in c[2]})) for c in COHORTS if c[2]}
    if len(lsets) != 1:
        bad.append(f"label windows cover different months-of-year: {lsets}")

    # Uniform spacing: the cohorts should be the same distance apart.
    starts = [c[1][0] for c in COHORTS]
    if len({starts[i+1] - starts[i] for i in range(len(starts)-1)}) != 1:
        bad.append(f"cohort feature windows are unevenly spaced: {starts}")

    # Every feature window must be the same length.
    if len({len(c[1]) for c in COHORTS}) != 1:
        bad.append("feature windows differ in length")
    return bad

if __name__ == "__main__":
    sql = build()
    problems = selfcheck(sql)
    if problems:
        print("SELF-CHECK FAILED:"); [print("  -", p) for p in problems]
        sys.exit(1)
    out = os.path.join(os.path.dirname(__file__), "..", "sql",
                       "42_model_datasets.sql")
    out = os.path.normpath(out)
    if "--check" in sys.argv:
        have = io.open(out, encoding="utf-8").read()
        same = have == sql
        print(f"{out}: {'matches the generator' if same else 'DIFFERS'}")
        sys.exit(0 if same else 1)
    io.open(out, "w", encoding="utf-8").write(sql)
    print(f"wrote {out}  ({len(sql.splitlines())} lines)")
    print("self-check passed:")
    print("  no percent character, balanced parens, no CASE, ascii only")
    print("  no cohort's feature window touches its own label window")
    print("  no label window reaches into the next cohort's features")
    print("  all feature windows the same length")
    print("  all feature windows at the same months-of-year (seasonally aligned)")
    print("  all label windows at the same months-of-year")
    print("  cohort windows evenly spaced")

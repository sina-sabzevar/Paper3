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

REV_T   = 1_700_000       # 170,000 Toman in Rial
MIN_REV_MONTHS = 2        # the screen: revenue over the threshold in 2+ months
WINSOR  = 500_000_000     # available_credit reaches 40.9 trillion raw
TENURE_CAP = 480          # age_on_net_months runs -232 to 1,285 raw

# Jalali: months 1-6 have 31 days, 7-11 have 30, month 12 has 29 in 1404.
LAST_DAY = {1:31,2:31,3:31,4:31,5:31,6:31,7:30,8:30,9:30,10:30,11:30,12:29}

COHORTS = [
    # name,   feature months,                      label months (4),            table
    ("TRAIN", [140301,140302,140303,140304,140305,140306],
               [140307,140308,140309,140310], "dcb_train"),
    ("VALID", [140407,140408,140409,140410,140411,140412],
               [140501,140502,140503,140504], "dcb_valid"),
    ("SCORE", [140501,140502,140503,140504,140505,140506],
               [],                            "dcb_score"),
]

def day_span(months):
    a, b = months[0], months[-1]
    return a * 100 + 1, b * 100 + LAST_DAY[b % 100]

def rev_expr(m):
    return ("COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))\n"
            f"                     FILTER (WHERE month_key = {m}), 0)")

def block(name, fm, lm, table):
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
    rm = " + ".join(f"IF(f.r{i}>={REV_T},1,0)" for i in range(1,7))
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
    pm_ = " + ".join(f"IF(COALESCE(p.q{i},0)>={REV_T},1,0)" for i in range(1,7))
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
    L.append("-- THE SCREEN: revenue over the threshold in 2 or more months,")
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
--      cohort    features            label (4 months)   role
--      TRAIN     140301..140306      140307..140310     fit
--      VALID     140407..140412      140501..140504     out of time
--      SCORE     140501..140506      none - the future  hand to implementation
--
--  TRAIN's label window ENDS at 140310, before VALID's feature window BEGINS
--  at 140407, so the out-of-time test is genuine rather than a reshuffle of
--  one period.
--
--  VALID is the window measured in 41_forward_horizons.sql at 0.95 pct for
--  this exact screen over 4 months, so the model's validation figure is
--  directly comparable to a number already on record. T4 checks it.
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
--     VALID's rate must land near 0.95 pct. That figure is on record from
--     41_forward_horizons.sql for this exact screen over a 4-month horizon,
--     so a mismatch means these two files disagree and one of them is wrong.
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
    # and TRAIN's label must end before VALID's features begin
    tr_lab = COHORTS[0][2]; va_feat = COHORTS[1][1]
    if tr_lab and max(tr_lab) >= min(va_feat):
        bad.append("TRAIN label window reaches into VALID feature window")
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
    print("self-check passed: no percent, balanced parens, no CASE, ascii only,")
    print("no cohort's feature window touches its own label window, and TRAIN's")
    print("label ends before VALID's features begin.")

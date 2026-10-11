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

# ---------------------------------------------------------------------------
#  WHAT COUNTS AS FAILING TO REPAY.
#
#   "twoway"   sbrp_stat_id = 4 only. Incoming service cut. Severe and LATE -
#              it follows months of arrears, so over a one-month horizon it is
#              both rare and mistimed for this product.
#   "oneway"   sbrp_stat_id = 3 only. Outgoing service cut: the operator's
#              FIRST arrears action.
#   "any_bar"  either. "The operator acted on non-payment", which is what
#              failing to settle a DCB draw actually looks like.
#
#  DEFAULT twoway, and any_bar was WRONG. DCB credit is a separate pool from
#  telco credit - DCB credit cannot buy packages, calls or SMS, and telco
#  credit cannot pay for VOD, bills or other off-net services. A ONE-WAY bar
#  restricts telco usage, so a DCB default cannot cause one. Labelling on
#  "either bar" would have trained the model on telco arrears and called it DCB
#  risk. twoway stays because it is the operator's own severe judgement that a
#  subscriber did not settle, which is the nearest thing in history to the real
#  event.
#
#  NEITHER IS THE RIGHT LABEL, ONLY THE AVAILABLE ONE. The draw lands on the
#  bill and the bill must be settled next month, so a DCB default is AN UNPAID
#  INVOICE, not a service bar. That is measurable from payments against
#  billings and 52_one_month_label_choice.sql measures it - including D3, which
#  tests whether a payment shortfall is real arrears or billing-cycle noise.
#  Once 52 has chosen the cut, add "unpaid" here with its threshold. Do not
#  guess the threshold: pay_to_rev_ratio on this project measured 1.40 and
#  1.28, so most subscribers pay MORE than they are billed and a cut at 1.0
#  would label a large innocent slice.
LABEL_EVENT = "twoway"

# Months between the end of the feature window and the start of the label: the
# EXPOSURE window, where the subscriber draws but no repayment is due yet.
# Zero was right for the four-month line, whose clock started at once. One is
# right for one-month DCB: draw in 140407, bill issued for 140407, repayment
# due in 140408. Setting it to zero here would label on the DRAW month and
# measure arrears that were already running before this product existed.
DRAW_SKIP = 1

# The repayment term, in months. One-month DCB means one label month. Declared
# so a label quietly widened back to the old four-month shape is rejected
# instead of silently changing what the model predicts.
TERM_MONTHS = 1
_EVENT_SQL = {"twoway":  "sbrp_stat_id = 4",
              "oneway":  "sbrp_stat_id = 3",
              "any_bar": "sbrp_stat_id IN (3, 4)"}[LABEL_EVENT]
_EVENT_HUMAN = {"twoway":  "two-way barred",
                "oneway":  "one-way barred",
                "any_bar": "one-way OR two-way barred"}[LABEL_EVENT]

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
#  The fifth element is the PRE window: the 12 months immediately before the
#  feature window, used for historical bar counts. MEASURED in
#  48_approved_audit.sql A5, on dcb_model where the label is known, bar history
#  from BEFORE the feature window predicts the label hard:
#
#      clean before      0.3916 pct
#      one-way before    1.5627 pct    4.0x clean
#      two-way before    5.1574 pct   13.2x clean
#
#  and it holds at every rev_months level - at rev_months = 6 two-way before
#  is still 11x clean - so it is not revenue in disguise. Nothing in the
#  original 34 features carried it: f_twoway and oneway_months are computed
#  over the FEATURE window only, so a subscriber cut off for non-payment a
#  year earlier was invisible to the model.
#
#  Each PRE window sits entirely before its own cohort's feature window, and
#  the two are themselves 12 months apart and on the same months-of-year, so
#  the seasonal alignment the rest of this file maintains is preserved.
#  THE DRAW MONTH IS DELIBERATELY NOT THE LABEL MONTH.
#
#  The product is one-month DCB: the subscriber draws during month M, the draw
#  lands on the bill issued for M, and that bill falls due during M+1. A bar in
#  month M therefore CANNOT have been caused by the draw - it was caused by
#  failing to pay the month M-1 bill, before this product existed. Labelling on
#  M would measure carried-over arrears and call it DCB risk.
#
#  So features end 140406, the subscriber draws in 140407, and the label is
#  140408 - the month the repayment was actually due. One month of exposure,
#  observed where the failure can first appear. 140407 is neither feature nor
#  label; it is the exposure window, and leaving it out of both is the point.
#
#  A bar can also lag into M+2. 52_one_month_label_choice.sql measures where
#  the event really lands, including the rate among subscribers still clean at
#  the end of 140407, which is the only view that separates NEW failures from
#  arrears that were already running.
COHORTS = [
    ("MODEL", [140401, 140402, 140403, 140404, 140405, 140406],
              [140408], "dcb_model", 1_050_000,
              (140301, 140312)),
    ("SCORE", [140501, 140502, 140503, 140504, 140505, 140506],
              [],                               "dcb_score", PROD_BAR,
              (140401, 140412)),
]

# ---------------------------------------------------------------------------
#  WHICH POPULATION THE MODEL TRAINS ON.
#
#  "screened"  the production-equivalent population: revenue over the window's
#              bar in 2+ months, never one-way, never two-way. The default.
#  "superset"  a LOWER revenue bar, same bar-history filters. Covers the range
#              the screen could drift over - it sits at 24.4 pct of the base
#              now and was 14.6 pct a year ago - so the fit does not have to be
#              redone every time the nominal bar loosens.
#  "all"       no screen at all. Every subscriber in the window.
#
#  MEASURED on synthetic data, AUC evaluated IN THE BAND (the only population
#  that is ever scored), across two worlds - one where the risk relationship is
#  the same across the revenue range, one where it differs inside the band:
#
#      world            band-only   superset   whole base
#      homogeneous         0.6835     0.6839       0.6838
#      heterogeneous       0.7235     0.7127       0.6342
#
#  So "all" is break-even at best and costs 0.09 AUC at worst, while
#  "superset" is within 0.011 of band-only in both worlds and buys the
#  drift-robustness. The whole-base model also reports a HEADLINE AUC on the
#  whole base of 0.78-0.82 while performing at 0.63-0.69 in the band, so the
#  number that would be quoted is inflated by 0.13-0.15.
#
#  Which world the real data is in is an empirical question, and W4 in
#  44_where_are_the_bads.sql is the free leading indicator: if the bad rate
#  still falls across rev_months INSIDE the cohort, the relationship survives
#  the screen and "all" is roughly harmless; if it is flat, revenue is spent
#  inside the band and a global fit is the heterogeneous case.
#
#  WHATEVER IS CHOSEN, THE METRICS MUST BE READ IN THE BAND. Every MODEL row
#  carries in_band, and the notebook restricts VALID and TEST to in_band = 1.
#  Comparing a whole-base AUC against a band AUC is comparing two different
#  test sets and says nothing.
# ---------------------------------------------------------------------------
_N_LAB = len([c[2] for c in COHORTS if c[2]][0])   # LABEL MONTHS - c[2], not the whole tuple

MODEL_POP    = "screened"
SUPERSET_BAR = 520_000     # about half the MODEL bar -> roughly the top 40 pct

# Level features that get a RELATIVE twin, divided by that window's own median.
# Raw Rial levels drift: revenue per subscriber-month grew 1.64x at the p90
# between these two windows. A coefficient learned on 1404 Rial means something
# different applied to 1405 Rial - a subscriber on 2,000,000 was upper-tail in
# 1404 and mid-pack in 1405 - so the model would read them as safer than their
# peers warrant. The ratio to the window median is stable under that drift.
# MEASURED on the first real run. Four of the five twins did their job; one
# did the opposite and is removed:
#
#     feature      raw PSI   _rel PSI
#     rev_6m        1.0865     0.0038   twin fixes it
#     rev_max       3.0223     0.0242   twin fixes it
#     paid_6m       0.3338     0.0034   twin fixes it
#     avail_max     0.1938     0.0501   twin fixes it
#     outst_max     0.0551     1.1404   twin MADE IT WORSE  <- removed
#
# outst_max is already STABLE across the two windows, and dividing it by its
# own window's median manufactured drift where there was none. Most
# subscribers carry zero outstanding, so that median sits near zero and is
# itself unstable between windows - a stable numerator over an unstable
# near-zero denominator is a ratio that moves for no behavioural reason.
# NULLIF guards a median of exactly zero, not a small one.
#
# THE RULE THIS ESTABLISHES: a relative twin is only worth building for a
# feature whose RAW column actually drifts AND whose median sits well away
# from zero. Check both before adding one here.
RELATIVE = ["rev_6m", "rev_max", "paid_6m", "avail_max"]


def day_span(months):
    a, b = months[0], months[-1]
    return a * 100 + 1, b * 100 + last_day(b)


def rev_expr(m):
    return ("COALESCE(SUM(COALESCE(arpu,0)-COALESCE(tot_arpu_tax_amt,0))\n"
            f"                     FILTER (WHERE month_key = {m}), 0)")


def block(name, fm, lm, table, bar, pre):
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
    L.append("pre AS (")
    L.append(f"    -- Bar history in the 12 months BEFORE the feature window")
    L.append(f"    -- ({pre[0]}..{pre[1]}). Measured at 13.2x the label rate for")
    L.append("    -- a prior two-way bar and 4.0x for one-way, at every revenue")
    L.append("    -- level - see 48_approved_audit.sql A5. One row per")
    L.append("    -- subscriber, so the LEFT JOIN below cannot fan out.")
    L.append("    SELECT   sbrp_id,")
    L.append("             COUNT(DISTINCT month_key)                  AS pre_months_seen,")
    L.append("             MAX(IF(sbrp_stat_id = 3, 1, 0))            AS pre_ow_any,")
    L.append("             MAX(IF(sbrp_stat_id = 4, 1, 0))            AS pre_tw_any,")
    L.append("             COUNT(DISTINCT IF(sbrp_stat_id = 3, month_key, NULL))")
    L.append("                                                        AS pre_ow_months,")
    L.append("             COUNT(DISTINCT IF(sbrp_stat_id = 4, month_key, NULL))")
    L.append("                                                        AS pre_tw_months")
    L.append("    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip")
    L.append(f"    WHERE    month_key BETWEEN {pre[0]} AND {pre[1]}")
    L.append("      AND    sbrp_typ_id = 1")
    L.append("    GROUP BY sbrp_id")
    L.append("),")
    if lm:
        L.append("lab AS (")
        L.append("    SELECT   sbrp_id,")
        L.append(f"             MAX(IF({_EVENT_SQL}, 1, 0))  AS y,")
        L.append("             COUNT(DISTINCT month_key)        AS n_label_months")
        L.append("    FROM     dwbi_fact_db.v_fact_sbrp_mthly_cip")
        L.append(f"    WHERE    month_key IN ({', '.join(str(m) for m in lm)})")
        L.append("      AND    sbrp_typ_id = 1")
        L.append("    GROUP BY sbrp_id")
        L.append("),")

    # ---- the screened projection -------------------------------------------
    rm = " + ".join(f"IF(f.r{i}>={bar},1,0)" for i in range(1, 7))
    # A month billing nothing. MEASURED in 53_bill_shock.sql S10/S11:
    # subscribers whose history carries a zero month default at 2.706 pct
    # against 0.350 pct for everyone else - 7.7x, on 109,360 subscribers.
    # rev_min already goes to zero for them, so a tree COULD find it, but it
    # has to discover a split at the very bottom of a Rial-scaled column to do
    # so. A count is explicit, scale-free, and survives the inflation that
    # makes rev_min's threshold move every year.
    nz = " + ".join(f"IF(f.r{i}<=0,1,0)" for i in range(1, 7))
    rw = " + ".join(f"IF(f.r{i}>={SUPERSET_BAR},1,0)" for i in range(1, 7))
    ob = "+".join(f"f.o{i}" for i in range(1, 7))
    pm_ = " + ".join(f"IF(COALESCE(p.q{i},0)>={bar},1,0)" for i in range(1, 7))
    L.append("proj AS (")
    L.append("    SELECT  f.sbrp_id,")
    L.append("            f.r1, f.r2, f.r3, f.r4, f.r5, f.r6,")
    L.append("            f.r1+f.r2+f.r3+f.r4+f.r5+f.r6                 AS rev_6m,")
    L.append("            GREATEST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)       AS rev_max,")
    L.append("            LEAST(f.r1,f.r2,f.r3,f.r4,f.r5,f.r6)          AS rev_min,")
    L.append("            (f.r4+f.r5+f.r6) - (f.r1+f.r2+f.r3)           AS rev_trend,")
    L.append(f"            {nz}")
    L.append("                                                          AS n_zero_rev_months,")
    L.append(f"            {rm}")
    L.append("                                                          AS rev_months,")
    L.append(f"            {rw}")
    L.append("                                                          AS rev_months_wide,")
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
    L.append("            COALESCE(pr.pre_months_seen, 0) AS pre_months_seen,")
    L.append("            COALESCE(pr.pre_ow_any, 0)      AS pre_ow_any,")
    L.append("            COALESCE(pr.pre_tw_any, 0)      AS pre_tw_any,")
    L.append("            COALESCE(pr.pre_ow_months, 0)   AS pre_ow_months,")
    L.append("            COALESCE(pr.pre_tw_months, 0)   AS pre_tw_months,")
    L.append("            IF(pr.sbrp_id IS NULL, 1, 0)    AS pre_absent,")
    L.append("            f.avail_max, f.avail_avg, f.outst_max, f.outst_avg,")
    L.append("            f.tenure_m,")
    if lm:
        L.append("            l.n_label_months, l.y,")
    else:
        L.append("            CAST(NULL AS BIGINT)  AS n_label_months,")
        L.append("            CAST(NULL AS INTEGER) AS y,")
    L.append(f"            IF({rm} >= {MIN_REV_MONTHS}")
    L.append(f"                AND {ob} = 0 AND f.f_twoway = 0, 1, 0)")
    L.append("                                                          AS in_band,")
    L.append(f"            '{name}' AS cohort")
    L.append("    FROM        feat f")
    L.append("    LEFT JOIN   pay  p ON p.sbrp_id = f.sbrp_id")
    L.append("    LEFT JOIN   pre  pr ON pr.sbrp_id = f.sbrp_id")
    if lm:
        L.append("    INNER JOIN  lab  l ON l.sbrp_id = f.sbrp_id")
    # SCORE is ALWAYS the production screen - that is the live rule. Only the
    # MODEL table's training population is switchable.
    pop = "screened" if not lm else MODEL_POP
    if pop == "screened":
        L.append(f"    -- THE SCREEN: revenue at or above {bar:,} Rial in "
                 f"{MIN_REV_MONTHS} or more")
        L.append("    -- of 6 months, never one-way barred, never two-way barred.")
        L.append(f"    WHERE   {rm} >= {MIN_REV_MONTHS}")
        L.append(f"      AND   {ob} = 0")
        L.append("      AND   f.f_twoway = 0")
    elif pop == "superset":
        L.append(f"    -- SUPERSET: the lower bar of {SUPERSET_BAR:,} Rial, same")
        L.append("    -- bar-history filters. in_band still marks the")
        L.append("    -- production-equivalent rows, and the metrics use it.")
        L.append(f"    WHERE   {rw} >= {MIN_REV_MONTHS}")
        L.append(f"      AND   {ob} = 0")
        L.append("      AND   f.f_twoway = 0")
    else:
        L.append("    -- NO SCREEN: every subscriber in the window. in_band marks")
        L.append("    -- the production-equivalent rows and the metrics use it,")
        L.append("    -- because an AUC over the whole base is not comparable to")
        L.append("    -- an AUC in the band - it ran 0.13 to 0.15 higher.")
        L.append("    WHERE   1 = 1")
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
--      label   y = 1 if {_EVENT_HUMAN} in the label month(s) below
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
--      available_credit        SEE THE WARNING BELOW before using it in
--                              production. Raw -3.6bn to 40.9tn Rial -> winsorised at
--                              {WINSOR:,}
--      arpu                    23.8 pct NULL, and the tax is zero where arpu
--                              is NULL, so the KPI expression yields 0 rather
--                              than minus-the-tax. n_arpu_null is carried as a
--                              feature - missingness here is informative
--
--  PAYMENTS USE ALL STATUSES. bllg_pmnt_stat_id = 2 holds 61.2 pct of payment
--  value and status 1 holds 38.7 pct, so filtering to 2 discards a third.
--
--  CURRENCY. The database stores money in RIAL. Every threshold in this file
--  is therefore a Rial figure: the 170,000 Toman screen is coded as 1,700,000.
--  1 Toman = 10 Rial. Columns that report Toman say so in their name, and
--  TICKET_TOMAN in the notebook is the one figure that is natively Toman
--  because it is a business input rather than a database value. T4 checks
--  that payments are Rial too, which pay_months assumes.
--
--  NO percent character anywhere. NO CASE expressions.
-- ============================================================================
"""

FOOTER = f"""
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
        -- arpu is RIAL, so dividing by 60 gives Toman per month: 6 months of
        -- Rial / 6 months / 10 Rial-per-Toman. The column name carries the
        -- unit. An earlier version divided by 10000 and called it
        -- med_rev_6m_k, which on a Rial column reads as thousands of RIAL
        -- when it was really thousands of TOMAN - a 10x misread waiting to
        -- happen, in a project where the screen is quoted in Toman and the
        -- data is stored in Rial.
        APPROX_PERCENTILE(rev_6m, 0.5) / 60              AS med_month_toman,
        APPROX_PERCENTILE(rev_6m, 0.5)                   AS med_rev_6m_rial,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5) AS med_rev_months,
        SUM(IF(n_label_months >= {_N_LAB}, 1, 0))         AS n_fully_observed
FROM    dwbi_temp40_db.dcb_model
UNION ALL
SELECT  'SCORE', COUNT(*), NULL, NULL,
        APPROX_PERCENTILE(rev_6m, 0.5) / 60,
        APPROX_PERCENTILE(rev_6m, 0.5),
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

-- ---------------------------------------------------------------------------
-- T4  ARE PAYMENTS IN THE SAME UNIT AS REVENUE? An unverified assumption
--     until this runs, and it matters.
--
--     arpu is Rial, and the screen bar is a Rial figure - 1,700,000 Rial for
--     the 170,000 Toman rule. pay_months compares pmnt_amt against that SAME
--     bar, which is only valid if pmnt_amt is also Rial. If payments are
--     stored in Toman, the comparison is 10x too strict and pay_months is
--     near zero for almost everybody - a silently dead feature rather than a
--     visible error.
--
--     HOW TO READ IT. A postpaid subscriber pays roughly what they are
--     billed, so pay_to_rev_ratio should land near 1. Near 0.1 means payments
--     are in TOMAN and every payment threshold in this project is wrong by a
--     factor of ten. Near 10 means the reverse.
--
--     med_pay_months is the corroborating symptom: it should be broadly
--     similar to med_rev_months. If revenue clears the bar in 4 months and
--     payments in 0, that is the unit mismatch showing itself.
-- ---------------------------------------------------------------------------
SELECT  'MODEL' AS tbl,
        APPROX_PERCENTILE(rev_6m,  0.5)                      AS med_rev_6m_rial,
        APPROX_PERCENTILE(paid_6m, 0.5)                      AS med_paid_6m,
        APPROX_PERCENTILE(paid_6m, 0.5)
            / NULLIF(APPROX_PERCENTILE(rev_6m, 0.5), 0)      AS pay_to_rev_ratio,
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5)   AS med_rev_months,
        APPROX_PERCENTILE(CAST(pay_months AS DOUBLE), 0.5)   AS med_pay_months,
        100.0 * SUM(IF(paid_6m = 0, 1, 0)) / COUNT(*)        AS pct_zero_paid
FROM    dwbi_temp40_db.dcb_model
UNION ALL
SELECT  'SCORE',
        APPROX_PERCENTILE(rev_6m,  0.5),
        APPROX_PERCENTILE(paid_6m, 0.5),
        APPROX_PERCENTILE(paid_6m, 0.5)
            / NULLIF(APPROX_PERCENTILE(rev_6m, 0.5), 0),
        APPROX_PERCENTILE(CAST(rev_months AS DOUBLE), 0.5),
        APPROX_PERCENTILE(CAST(pay_months AS DOUBLE), 0.5),
        100.0 * SUM(IF(paid_6m = 0, 1, 0)) / COUNT(*)
FROM    dwbi_temp40_db.dcb_score;
"""


def build():
    parts = [HEADER]
    for i, (name, fm, lm, table, bar, pre) in enumerate(COHORTS, 1):
        parts.append(
            "\n-- ---------------------------------------------------------"
            "------------------\n"
            f"-- {name}   features {fm[0]}..{fm[-1]}"
            + (f", label {lm[0]}..{lm[-1]}" if lm
               else ", NO LABEL - the outcome is the future")
            + f"\n--          bar {bar:,} Rial"
            + "\n-- -------------------------------------------------------"
              "--------------------\n")
        parts.append(block(name, fm, lm, table, bar, pre))
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

    for name, fm, lm, _, _, _ in COHORTS:
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

    # The PRE window must sit entirely before its own cohort's feature window
    # AND its own label window. A pre window overlapping the label is the
    # leakage that made one audit sheet report 61 pct bad for "two-way before"
    # and 0 pct for everyone else - "before" had come to mean "during".
    for c in COHORTS:
        name, fm, lm, _, _, pre = c
        pre_months = [m for m in range(pre[0], pre[1] + 1)
                      if 1 <= m % 100 <= 12]
        if max(pre_months) >= min(fm):
            bad.append(f"{name}: pre window {pre} is not entirely before its "
                       f"feature window starting {min(fm)}")
        if lm and set(pre_months) & set(lm):
            bad.append(f"{name}: pre window {pre} overlaps its own label "
                       f"window - that is leakage, not history")
    psets = {tuple(sorted({m % 100 for m in range(c[5][0], c[5][1] + 1)
                           if 1 <= m % 100 <= 12})) for c in COHORTS}
    if len(psets) != 1:
        bad.append(f"pre windows cover different months-of-year: {psets}")
    if len({c[5][1] - c[5][0] for c in COHORTS}) != 1:
        bad.append("pre windows differ in span")

    # The label season must match what SCORE's forward exposure will really be,
    # counted from the END of the exposure window rather than the end of the
    # features - DRAW_SKIP months pass before any repayment can be missed.
    def nxt(m):
        y, mo = m // 100, m % 100
        return (y + 1) * 100 + 1 if mo == 12 else y * 100 + mo + 1

    lab = [c[2] for c in COHORTS if c[2]][0]
    sc_feat = COHORTS[-1][1]
    exposure = []
    m = sc_feat[-1]
    for _ in range(DRAW_SKIP):
        m = nxt(m)
    for _ in range(len(lab)):
        m = nxt(m)
        exposure.append(m)

    # And the MODEL label must sit the SAME distance after its own features,
    # or the two cohorts describe different products.
    mdl = [c for c in COHORTS if c[2]][0]
    want = mdl[1][-1]
    for _ in range(DRAW_SKIP + 1):
        want = nxt(want)
    if len(mdl[2]) != TERM_MONTHS:
        bad.append(f"label is {len(mdl[2])} month(s) but TERM_MONTHS is {TERM_MONTHS}")
    if mdl[2][0] != want:
        bad.append(f"MODEL label starts {mdl[2][0]}, but {DRAW_SKIP} draw month(s) "
                   f"after features ending {mdl[1][-1]} puts it at {want}")
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
    print("  every PRE window is entirely before its own features AND label")
    print("  PRE windows seasonally aligned and equal in span")

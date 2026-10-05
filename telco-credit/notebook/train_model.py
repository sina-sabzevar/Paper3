# -*- coding: utf-8 -*-
"""Train, validate out of time, and score — for the chosen target.

    python3 train_model.py

TARGET
    screen  revenue >= 170,000 Toman in 2 or more of 6 months,
            never one-way barred and never two-way barred in that window
    label   y = 1 if two-way barred in the 4 months immediately after
    measured: 6,879,803 screened, 0.95 pct two-way barred within 4 months

THREE COHORTS, built by sql/42_model_datasets.sql. Data runs 140301..140506.

    TRAIN   features 140301..140306   label 140307..140310
    VALID   features 140407..140412   label 140501..140504
    SCORE   features 140501..140506   no label - the outcome is the future

TRAIN's label window ENDS at 140310, before VALID's feature window BEGINS at
140407, so the out-of-time test is genuine rather than a reshuffle of one
period. The 4-month label is what pushes TRAIN back to 140301: a 4-month
label on 140401..140406 features would run to 140410 and collide with
VALID's feature window.

WHY 4 MONTHS COSTS MORE THAN TWICE 2 MONTHS

Risk here is BACK-loaded, measured at p_n proportional to n^1.40. Lengthening
the window from 2 months to 4 raises the event rate from 0.36 pct to 0.95
pct - 2.6x, not the 2.0x a constant hazard would give. The longer window is
the harder problem and the more honest one: a 4-month credit line is exposed
for 4 months.

WHAT A 0.95 PCT EVENT RATE CHANGES

A model predicting "nobody defaults" is 99.05 pct accurate, so accuracy is
meaningless here and is not reported. What is reported:

    AUC and Gini     ranking, which is what the limit engine consumes
    KS               separation at the best cut
    Brier, WEIGHTED  calibration. Unweighted on a down-sampled file this read
                     0.29 on a 2 pct problem in an earlier version of this
                     project, purely from the weighting error.
    decile table     predicted against observed, on rows the calibrator
                     never saw

DOWN-SAMPLING AND sample_weight

Every bad is kept - at 0.95 pct they are the scarce half of the problem.
Goods are sampled at GOOD_KEEP pct and sample_weight restores the base rate.

    USE sample_weight IN EVERY FIT AND EVERY METRIC.

Without it the model sees roughly a 9 pct event rate instead of 0.95 and
every predicted probability comes out about nine times too high. Keeping
GOOD_KEEP pct of goods inflates the ODDS by exactly 100/GOOD_KEEP = 10x; at
these rates that is a 9.2x inflation of the probability itself (0.95 pct
becomes 8.75 pct). Ranking survives that; the level does not, and the limit
engine spends the level.

CALIBRATION IS FITTED AND JUDGED ON DIFFERENT ROWS

Fitting isotonic on a set and then reading its calibration off the same rows
gives a ratio of 1.0000 in every decile by construction - a perfect-looking
table that proves nothing. An earlier version of this project did exactly
that. VALID is split in half: one half calibrates, the other is judged.
"""
import gc, os, sys, time
import numpy as np
import pandas as pd

DATA       = "data"
TRAIN_FILE = "dcb_train"
VALID_FILE = "dcb_valid"
SCORE_FILE = "dcb_score"
OUTDIR     = "outputs"
GOOD_KEEP  = 10          # keep this many goods out of every 100
SEED       = 42

# The credit line per approved subscriber, in Toman. Used only to turn the PD
# ranking into exposure and expected-loss columns - it changes no model fit.
# 500,000 is the line discussed for this product; the stated floor is 400,000.
TICKET_TOMAN = 500_000

# Columns that are NOT features. y and cohort are the label and the tag;
# sbrp_id is an identity and would let a tree memorise individuals.
# n_label_months counts how many months of the LABEL window the subscriber
# appeared in. It is built from the outcome and is NULL in SCORE, so it is
# leakage, not a feature - it is carried in the data to measure partial
# observation, and excluded here.
NOT_FEATURES = {"sbrp_id", "y", "cohort", "sample_weight", "n_label_months"}


# ---------------------------------------------------------------------------
#  LOADING
# ---------------------------------------------------------------------------
def load(stem):
    """Reads parquet if present, else CSV, else the _part* files of either."""
    import glob
    base = os.path.join(DATA, stem)
    for pat in (base + ".parquet", base + "*.parquet",
                base + ".csv",     base + "*.csv"):
        files = sorted(glob.glob(pat))
        if files:
            rd = pd.read_parquet if files[0].endswith(".parquet") else pd.read_csv
            parts = [rd(f) for f in files]
            df = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
            print(f"  {stem}: {len(files)} file(s) -> {len(df):,} rows "
                  f"x {df.shape[1]} cols")
            if "sbrp_id" in df.columns:
                dup = len(df) - df.sbrp_id.nunique()
                if dup:
                    raise ValueError(
                        f"{dup:,} duplicate sbrp_id in {stem}. Parts overlap, so "
                        f"some subscribers are counted twice and the metrics "
                        f"below would be wrong.")
            return df
    raise FileNotFoundError(
        f"nothing found for {stem} under {DATA}/. Run sql/42_model_datasets.sql "
        f"and export dcb_train, dcb_valid and dcb_score.")


def downsample(df, keep_pct, seed):
    """Every bad, keep_pct of the goods, with sample_weight to put the base
    rate back. The draw is on a HASH of sbrp_id, not on sbrp_id itself: every
    observed id in this base is odd and they share a five-digit block, so MOD
    on the raw id selects a structured slice rather than a sample."""
    import hashlib
    bad = df[df.y == 1]
    good = df[df.y == 0]
    h = good.sbrp_id.astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 100)
    good = good[h.values < keep_pct]
    out = pd.concat([bad, good], ignore_index=True)
    out["sample_weight"] = np.where(out.y == 1, 1.0, 100.0 / keep_pct)
    print(f"  kept every bad ({len(bad):,}) and {keep_pct} pct of goods "
          f"({len(good):,}) -> {len(out):,} rows")
    print(f"  raw rate in the sample {out.y.mean():.4%}, weighted back to "
          f"{np.average(out.y, weights=out.sample_weight):.4%}")
    return out


# ---------------------------------------------------------------------------
#  METRICS - every one weighted
# ---------------------------------------------------------------------------
def report(name, y, p, w):
    from sklearn.metrics import roc_auc_score, brier_score_loss
    auc = roc_auc_score(y, p, sample_weight=w)
    br  = brier_score_loss(y, p, sample_weight=w)
    # weighted KS
    o = np.argsort(p)
    ys, ws = np.asarray(y)[o], np.asarray(w)[o]
    cb = np.cumsum(ws * ys);      cb = cb / cb[-1]
    cg = np.cumsum(ws * (1 - ys)); cg = cg / cg[-1]
    ks = np.max(np.abs(cb - cg))
    print(f"  {name:<28} AUC {auc:.4f}   Gini {2*auc-1:.4f}   "
          f"KS {ks:.4f}   Brier {br:.6f}")
    return dict(model=name, auc=auc, gini=2*auc-1, ks=ks, brier=br)


def decile_table(y, p, w, label=""):
    """Predicted against observed, weighted, on rows the calibrator never saw."""
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    d = pd.DataFrame({"d": q, "y": y, "p": p, "w": w})
    g = d.groupby("d").apply(
        lambda t: pd.Series({
            "n":         len(t),
            "weighted_n": t.w.sum(),
            "predicted": np.average(t.p, weights=t.w),
            "observed":  np.average(t.y, weights=t.w),
        }), include_groups=False)
    g["ratio"] = g.observed / g.predicted.replace(0, np.nan)
    print(f"\n  calibration by decile{label} (ratio near 1.0 is the goal)")
    print(g.to_string(float_format=lambda v: f"{v:12.6f}"))
    worst = g.ratio.iloc[(g.ratio - 1.0).abs().to_numpy().argmax()]
    print(f"  furthest from 1.0: {worst:.3f}")
    return g


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rng = np.random.default_rng(SEED)

    print("LOADING")
    tr_raw = load(TRAIN_FILE)
    va_raw = load(VALID_FILE)
    sc_raw = load(SCORE_FILE)

    print("\nEVENT RATES AS BUILT")
    for nm, d in (("TRAIN", tr_raw), ("VALID", va_raw)):
        print(f"  {nm}: {len(d):,} rows, {int(d.y.sum()):,} bad, "
              f"{d.y.mean():.4%}")
    print(f"  SCORE: {len(sc_raw):,} rows, no label")
    print("\n  VALID should land near 0.95 pct - that figure is on record from")
    print("  41_forward_horizons.sql. A mismatch means the two files disagree.")

    FEATURES = [c for c in tr_raw.columns if c not in NOT_FEATURES]
    FEATURES = [c for c in FEATURES
                if c in va_raw.columns and c in sc_raw.columns]
    FEATURES = [c for c in FEATURES
                if pd.api.types.is_numeric_dtype(tr_raw[c])]

    # Drop columns with no variance. oneway_months is zero for every row by
    # construction - the screen requires it - and a constant column is at best
    # dead weight and at worst, in an earlier run of this project, a PSI of
    # 13.89 that read as catastrophic drift when it was really a loading gap.
    # Checked on all three cohorts: a column constant in TRAIN but moving in
    # SCORE is worse than one constant everywhere.
    dead = []
    for c in FEATURES:
        nun = (tr_raw[c].nunique(dropna=True), va_raw[c].nunique(dropna=True),
               sc_raw[c].nunique(dropna=True))
        if max(nun) <= 1:
            dead.append((c, nun))
    if dead:
        print("\nDROPPED - no variance in any cohort:")
        for c, nun in dead:
            print(f"  {c:16s} distinct values TRAIN/VALID/SCORE {nun}")
        FEATURES = [c for c in FEATURES if c not in {d[0] for d in dead}]

    # A column constant in TRAIN but varying elsewhere is a different problem:
    # the model cannot learn a coefficient for it, then meets it moving at
    # scoring time. Report loudly rather than drop silently.
    for c in FEATURES:
        if tr_raw[c].nunique(dropna=True) <= 1:
            print(f"  WARNING {c} is constant in TRAIN but not in VALID/SCORE")

    print(f"\nFEATURES: {len(FEATURES)}")
    print(f"  {FEATURES}")
    leak = [c for c in FEATURES
            if c in ("y", "cohort", "n_label_months", "sample_weight")]
    assert not leak, f"label or label-derived column in the feature list: {leak}"
    assert FEATURES, "no features survived selection"

    print("\nDOWN-SAMPLING TRAIN")
    tr = downsample(tr_raw, GOOD_KEEP, SEED)
    del tr_raw; gc.collect()

    Xtr, ytr, wtr = tr[FEATURES].to_numpy(float), tr.y.to_numpy(int), \
                    tr.sample_weight.to_numpy(float)
    Xva, yva = va_raw[FEATURES].to_numpy(float), va_raw.y.to_numpy(int)
    wva = np.ones(len(yva))          # VALID is the full population, no sampling
    Xtr = np.nan_to_num(Xtr, nan=0.0, posinf=0.0, neginf=0.0)
    Xva = np.nan_to_num(Xva, nan=0.0, posinf=0.0, neginf=0.0)

    # ---- champion: logistic on standardised features ----------------------
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    print("\nFITTING")
    t0 = time.time()
    champ = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs"))
    champ.fit(Xtr, ytr, logisticregression__sample_weight=wtr)
    print(f"  logistic fitted in {time.time()-t0:,.0f}s")

    # ---- challenger: gradient boosting ------------------------------------
    from sklearn.ensemble import HistGradientBoostingClassifier
    t0 = time.time()
    chal = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        early_stopping=True, validation_fraction=0.15, random_state=SEED)
    chal.fit(Xtr, ytr, sample_weight=wtr)
    print(f"  gradient boosting fitted in {time.time()-t0:,.0f}s, "
          f"{chal.n_iter_} iterations")

    print("\nIN-SAMPLE (TRAIN, weighted)")
    RES = [report("logistic (champion)", ytr, champ.predict_proba(Xtr)[:,1], wtr),
           report("HistGB (challenger)", ytr, chal.predict_proba(Xtr)[:,1], wtr)]

    print("\nOUT OF TIME (VALID - a later period, never seen in training)")
    pva_c = champ.predict_proba(Xva)[:,1]
    pva_g = chal.predict_proba(Xva)[:,1]
    RV = [report("logistic (champion)", yva, pva_c, wva),
          report("HistGB (challenger)", yva, pva_g, wva)]

    best = "HistGB" if RV[1]["auc"] > RV[0]["auc"] else "logistic"
    pva  = pva_g if best == "HistGB" else pva_c
    model = chal if best == "HistGB" else champ
    print(f"\n  selected on OUT-OF-TIME AUC: {best}")
    gap = RES[1 if best=='HistGB' else 0]["auc"] - RV[1 if best=='HistGB' else 0]["auc"]
    print(f"  train-to-valid AUC gap {gap:+.4f}"
          + ("   <-- overfitted, reduce max_iter" if gap > 0.05 else ""))

    # ---- calibration: fit on half of VALID, judge on the other half -------
    from sklearn.isotonic import IsotonicRegression
    h = rng.random(len(yva)) < 0.5
    iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-7, y_max=1-1e-7)
    iso.fit(pva[h], yva[h])
    anchor = np.average(yva[h]) / max(np.average(iso.predict(pva[h])), 1e-9)
    print(f"\nCALIBRATION  fitted on {h.sum():,} rows, judged on "
          f"{(~h).sum():,} HELD-BACK rows")
    print(f"  anchor ratio {anchor:.4f}  (1.0 = no rescaling needed)")
    pcal = np.clip(iso.predict(pva[~h]) * anchor, 1e-7, 0.999)
    print(f"  mean PD {pcal.mean():.4%}  vs observed {yva[~h].mean():.4%}  "
          f"-> level error {abs(pcal.mean()-yva[~h].mean())/max(yva[~h].mean(),1e-9):.2%}")
    decile_table(yva[~h], pcal, np.ones((~h).sum()), " on the held-back half")

    # ---- score the live set ----------------------------------------------
    print("\nSCORING THE LIVE SET")
    Xsc = np.nan_to_num(sc_raw[FEATURES].to_numpy(float),
                        nan=0.0, posinf=0.0, neginf=0.0)
    psc = np.clip(iso.predict(model.predict_proba(Xsc)[:,1]) * anchor,
                  1e-7, 0.999)
    out = pd.DataFrame({"sbrp_id": sc_raw.sbrp_id.values, "pd_4m": psc})
    out["grade"] = pd.cut(out.pd_4m,
                          [-1, 0.002, 0.005, 0.010, 0.020, 1.0],
                          labels=["A", "B", "C", "D", "E"])
    print(f"  scored {len(out):,} subscribers")
    print(f"  mean predicted PD {out.pd_4m.mean():.4%}  "
          f"(VALID observed {yva.mean():.4%})")
    print("\n  by grade")
    gb = out.groupby("grade", observed=True).agg(
        n=("pd_4m", "size"), mean_pd=("pd_4m", "mean"))
    gb["share"] = gb.n / gb.n.sum()
    print(gb.to_string(float_format=lambda v: f"{v:12.6f}"))

    # cumulative, which is what the limit engine reads
    o = out.sort_values("pd_4m").reset_index(drop=True)
    o["cum_n"] = np.arange(1, len(o)+1)
    o["cum_pd"] = o.pd_4m.expanding().mean()
    # ---- the table the limit engine consumes ------------------------------
    # Ranked safest first, so row n answers "if I lend to the n safest, what
    # is the average PD of that book". Shares rather than only absolute counts:
    # absolute milestones silently vanish on any population smaller than the
    # smallest milestone, which made this table one useless row in testing.
    print("\n  SELECTING THE SAFEST N - this is the table the limit engine uses")
    print(f"  {'take':>12} {'share':>7} {'book mean PD':>13} "
          f"{'exposure':>14} {'expected loss':>14}")
    marks = [int(len(o) * f) for f in
             (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
    marks += [n for n in (3_000_000,) if n <= len(o)]
    for n in sorted(set(m for m in marks if m > 0)):
        pdn = o.cum_pd.iloc[n - 1]
        expo = n * TICKET_TOMAN
        print(f"  {n:>12,} {n/len(o):>6.1%} {pdn:>12.4%} "
              f"{expo/1e12:>11,.1f} tn {expo*pdn/1e9:>11,.1f} bn")

    # ---- the same question from the other side ----------------------------
    # Not "how many can I take" but "how many can I take without the book's
    # average PD crossing a ceiling". This is the form a credit committee
    # states its appetite in.
    print("\n  LARGEST BOOK UNDER A PD CEILING")
    print(f"  {'ceiling':>9} {'take':>12} {'share':>7} {'exposure':>14} "
          f"{'expected loss':>14}")
    for ceil in (0.0025, 0.005, 0.0075, 0.010, 0.015, 0.020):
        under = np.flatnonzero(o.cum_pd.to_numpy() <= ceil)
        if len(under) == 0:
            print(f"  {ceil:>8.2%} {'-':>12} {'-':>7}   "
                  f"no subscriber qualifies")
            continue
        n = int(under[-1]) + 1
        expo = n * TICKET_TOMAN
        print(f"  {ceil:>8.2%} {n:>12,} {n/len(o):>6.1%} "
              f"{expo/1e12:>11,.1f} tn {expo*o.cum_pd.iloc[n-1]/1e9:>11,.1f} bn")

    print(f"\n  Exposure assumes every approved subscriber draws the full "
          f"{TICKET_TOMAN:,} Toman")
    print("  line, and expected loss assumes a two-way bar loses the WHOLE")
    print("  balance (LGD 100 pct). Both are deliberately pessimistic: the")
    print("  operator keeps collecting after a bar, and most subscribers will")
    print("  not draw the full line. Treat these as a ceiling on the loss, not")
    print("  a forecast of it. The PD column is the model's output; the money")
    print("  columns are that PD times assumptions the business owns.")

    path = os.path.join(OUTDIR, "handover_scores.csv")
    out.to_csv(path, index=False)
    print(f"\n  written to {path}")
    pd.DataFrame(RES + [dict(r, model=r["model"] + " [OOT]") for r in RV]) \
      .to_csv(os.path.join(OUTDIR, "metrics.csv"), index=False)
    print(f"  metrics written to {OUTDIR}/metrics.csv")

    print("\nWHAT IS NOT REPORTED, AND WHY")
    print("  Accuracy. At a 0.95 pct event rate a model predicting 'nobody")
    print("  defaults' scores 99.05 pct, so the number says nothing.")


if __name__ == "__main__":
    main()

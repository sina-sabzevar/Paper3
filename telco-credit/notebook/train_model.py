# -*- coding: utf-8 -*-
"""Fit, select, test and score - 6-month features, 4-month label.

    python3 train_model.py

TARGET
    screen  revenue at or above the window's bar in 2 or more of 6 months,
            never one-way barred and never two-way barred in that window
    label   y = 1 if two-way barred in the 4 months IMMEDIATELY AFTER

TWO TABLES, built by sql/42_model_datasets.sql. 1403 is deliberately unused.

    dcb_model   features 140401..140406   label 140407..140410
    dcb_score   features 140501..140506   no label - the outcome is the future

dcb_model is split 70/20/10 here, on a hash of sbrp_id:

    TRAIN  70 pct   fit both models
    VALID  20 pct   choose between them, and fit the calibrator
    TEST   10 pct   read ONCE, at the end. Nothing is tuned on it.

MEASURED: this window returned 5,100,390 subscribers at 0.5541 pct in
43_cohort_funnel.sql D5, at the production bar. dcb_model uses a lower bar
(see the SQL header), so expect more rows and a somewhat higher rate.

WHAT A RANDOM SPLIT CAN AND CANNOT TELL YOU

A 70/20/10 split by subscriber measures generalisation to OTHER SUBSCRIBERS
IN THE SAME PERIOD. It cannot measure generalisation to a LATER period, and
a later period is exactly where this model is applied.

That matters here more than it usually would, because the drift has been
measured rather than guessed. 43_cohort_funnel.sql found revenue per
subscriber-month up 1.64x at the p90 between the model window and the scoring
window, and the fixed 170,000 Toman screen admitting 14.6 pct of the base in
one and 24.4 pct in the other.

So TEST AUC is an UPPER BOUND on live performance, not an estimate of it. Two
things are done about that rather than noting it and moving on:

    1 the PSI section below measures feature drift between dcb_model and
      dcb_score directly, which is the part a random split hides;
    2 each level feature has a RELATIVE twin from the SQL, divided by its own
      window's median. Raw Rial levels drift; a ratio to the window median
      does not. Set USE_RELATIVE_ONLY if PSI says the raw levels have moved.

WHY NO ACCURACY IS REPORTED

At a rate near 0.55 pct a model predicting "nobody defaults" scores 99.45 pct.
The number cannot tell a working model from an empty one. What is reported:

    AUC and Gini     ranking, which is what the limit engine consumes
    KS               separation at the best cut
    Brier, WEIGHTED  calibration. Unweighted on a down-sampled file this read
                     0.29 on a 2 pct problem earlier in this project, purely
                     from the weighting error.
    decile table     predicted against observed, on TEST

DOWN-SAMPLING AND sample_weight

Every bad is kept; goods are sampled at GOOD_KEEP pct and sample_weight
restores the base rate. USE sample_weight IN EVERY FIT AND EVERY METRIC.
Keeping 10 pct of goods inflates the ODDS by exactly 100/GOOD_KEEP = 10x, and
at these rates roughly 9x the probability itself. Ranking survives that; the
level does not, and the limit engine spends the level.

Only TRAIN is down-sampled. VALID and TEST stay whole, so their metrics need
no weighting correction.

CALIBRATION IS FITTED AND JUDGED ON DIFFERENT ROWS

Isotonic is fitted on VALID and judged on TEST. Fitting and judging on the
same rows gives a ratio of 1.0000 in every decile by construction - a
perfect-looking table that proves nothing. An earlier version of this project
did exactly that.
"""
import gc, os, glob, time, hashlib
import numpy as np
import pandas as pd

DATA       = "data"
MODEL_FILE = "dcb_model"
SCORE_FILE = "dcb_score"
OUTDIR     = "outputs"
GOOD_KEEP  = 10            # keep this many goods out of every 100, in TRAIN
SEED       = 42

SPLIT_TRAIN = 70           # hash mod 100 under this -> train
SPLIT_VALID = 90           # under this -> valid, at or over -> test

# EXPECTED SHAPE, from 42's T1. Ported from the earlier notebook's CFG, which
# had this right: "a missing part is otherwise undetectable - from the outside
# it looks exactly like a smaller export". The duplicate-sbrp_id check catches
# a part counted TWICE; nothing catches a part that never arrived, and a
# half-loaded training set produces a perfectly plausible model on half the
# data. The row count is the stronger form - it also catches a TRUNCATED
# export, which a part count does not.
#
# Set a value to None to skip that check, and update these numbers whenever
# 42 is re-run with a different bar.
EXPECT = {
    "dcb_model": dict(rows=8_701_085, parts=2),
    "dcb_score": dict(rows=9_344_723, parts=2),
}

# The credit line per approved subscriber, in Toman. Used ONLY to turn the PD
# ranking into money columns. It changes no fit and no metric.
TICKET_TOMAN = 500_000

# Measured for THIS window at the PRODUCTION bar by 43_cohort_funnel.sql D5:
# 28,263 bad of 5,100,390 screened = 0.5541 pct. dcb_model uses a lower bar,
# so the rate here should sit somewhat above it. A rate near 0.95 pct would
# mean the LABEL months are wrong - that is the months 1-4 figure, and these
# labels are months 7-10.
REFERENCE_RATE = 0.005541

# Raw Rial level features that have a _rel twin from the SQL. Setting
# USE_RELATIVE_ONLY drops the raw ones and keeps the ratios, which is the
# drift-robust choice when PSI says the levels have moved.
# outst_max is deliberately absent: its raw PSI is 0.0551 (stable) while
# outst_max_rel measured 1.1404, because dividing a stable column by its
# window's near-zero median manufactures drift. The twin is no longer built.
RAW_WITH_REL = ["rev_6m", "rev_max", "paid_6m", "avail_max"]
USE_RELATIVE_ONLY = False

# Not features. sbrp_id is an identity a tree would memorise; n_label_months is
# built from the outcome and is NULL in dcb_score, so it is leakage.
# in_band marks the production-equivalent rows. It is 1 for every row of
# dcb_score by construction, so as a feature it is the oneway_months trap again:
# it would carry weight in TRAIN and be unable to fire at scoring time.
NOT_FEATURES = {"sbrp_id", "y", "cohort", "sample_weight", "n_label_months",
                "split", "in_band"}


# ---------------------------------------------------------------------------
#  LOADING
# ---------------------------------------------------------------------------
def load(stem):
    """Parquet if present, else CSV, else the _part* files of either.

    Raises on duplicate sbrp_id: when a table is exported in parts by a range
    condition, a wrong boundary gives overlapping parts, every row in the
    overlap is counted twice, and every rate below shifts silently.
    """
    base = os.path.join(DATA, stem)
    # GLOB ONLY, no exact-name pattern. An earlier version tried
    # base + ".parquet" first and base + "*.parquet" second, but glob's "*"
    # matches the empty string, so the first was a strict subset of the second:
    # if a whole-table file AND part files both existed, the whole-table file
    # won and the parts were silently ignored - which loads stale data without
    # a word. Globbing only means that case concatenates everything and the
    # duplicate-sbrp_id check below stops the run.
    #
    # File ORDER does not matter: the parts are concatenated and
    # train/valid/test is assigned afterwards on a hash of sbrp_id.
    for ext in (".parquet", ".csv"):
        files = sorted(set(glob.glob(base + "*" + ext)))
        if not files:
            continue
        rd = pd.read_parquet if ext == ".parquet" else pd.read_csv
        parts = [rd(f) for f in files]
        df = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
        print(f"  {stem}: {len(files)} file(s) -> {len(df):,} rows "
              f"x {df.shape[1]} cols")
        if len(files) > 1:
            print(f"    {', '.join(os.path.basename(f) for f in files)}")

        exp = EXPECT.get(stem, {})
        if exp.get("parts") is not None and len(files) != exp["parts"]:
            raise ValueError(
                f"{stem}: found {len(files)} file(s), expected "
                f"{exp['parts']}. A missing part looks exactly like a smaller "
                f"export from the outside, so this is the only thing that "
                f"catches it. Check the export, or set the 'parts' entry for "
                f"{stem} in EXPECT to None if it really is in {len(files)} "
                f"piece(s).")
        if exp.get("rows") is not None and len(df) != exp["rows"]:
            raise ValueError(
                f"{stem}: loaded {len(df):,} rows, expected {exp['rows']:,} "
                f"(short by {exp['rows']-len(df):,}). Either a part is missing "
                f"or truncated, or 42 was re-run with a different bar - in "
                f"which case update EXPECT from its T1 output. A short load "
                f"trains a plausible-looking model on less data than intended.")
        if "sbrp_id" in df.columns:
            dup = len(df) - df.sbrp_id.nunique()
            if dup:
                raise ValueError(
                    f"{dup:,} duplicate sbrp_id across "
                    f"{', '.join(os.path.basename(f) for f in files)}. "
                    f"Those subscribers are counted twice and every metric "
                    f"below would be wrong. Two causes: a whole-table export "
                    f"left in the directory beside its own parts, or parts cut "
                    f"on a boundary that overlaps. Delete the extra file, or "
                    f"re-split with sql/47_export_parts.sql and check its V1.")
        return df
    # Nothing matched. A bare "not found" sends you hunting, so say what the
    # glob looked for and what is actually in the directory - the usual cause
    # is a file carrying an older stem, such as dcbtrain or dcbs_scoreset from
    # the previous pipeline, which the glob cannot match.
    tried = [os.path.join(DATA, stem) + "*" + e for e in (".parquet", ".csv")]
    here = []
    if os.path.isdir(DATA):
        here = sorted(f for f in os.listdir(DATA)
                      if f.endswith((".parquet", ".csv")))
    lines = [f"nothing found for {stem}.",
             f"  looked for : {' , '.join(tried)}",
             f"  DATA={DATA!r} resolves to {os.path.abspath(DATA)}",
             f"  cwd        : {os.getcwd()}"]
    if here:
        lines.append(f"  data files present but NOT matching: {here}")
        lines.append(f"  -> only the STEM matters. Rename so the file begins "
                     f"'{stem}'; any suffix works, e.g. {stem}_even, "
                     f"{stem}_odd, {stem}_p1.")
    elif os.path.isdir(DATA):
        lines.append(f"  {DATA}/ exists but holds no .parquet or .csv at all.")
    else:
        lines.append(f"  {DATA}/ does not exist from this cwd - the notebook "
                     f"may be running from a different directory.")
    lines.append("  Build the tables with sql/42_model_datasets.sql; "
                 "sql/47_export_parts.sql splits them if needed.")
    raise FileNotFoundError("\n".join(lines))


def hash_bucket(ids):
    """MD5(sbrp_id) mod 100.

    On a HASH, never on sbrp_id itself: every observed id in this base is odd
    and they share a five-digit block, so MOD on the raw id selects a
    structured slice of the network rather than a sample. A parity split on
    sbrp_id once put all 11.5M rows in one half.
    """
    return ids.astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 100)


def downsample(df, keep_pct):
    """Every bad, keep_pct of the goods, with sample_weight to restore the
    base rate. The draw is on the same hash, offset so that it is independent
    of the train/valid/test assignment."""
    bad, good = df[df.y == 1], df[df.y == 0]
    h = good.sbrp_id.astype(str).map(
        lambda s: int(hashlib.md5(("ds" + s).encode()).hexdigest()[:8], 16) % 100)
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
    o  = np.argsort(p)
    ys, ws = np.asarray(y)[o], np.asarray(w)[o]
    cb = np.cumsum(ws * ys);       cb = cb / cb[-1]
    cg = np.cumsum(ws * (1 - ys)); cg = cg / cg[-1]
    ks = np.max(np.abs(cb - cg))
    print(f"  {name:<28} AUC {auc:.4f}   Gini {2*auc-1:.4f}   "
          f"KS {ks:.4f}   Brier {br:.6f}")
    return dict(model=name, auc=auc, gini=2*auc-1, ks=ks, brier=br)


def decile_table(y, p, w, label=""):
    """Predicted against observed by score decile, weighted.

    Weighted sums through agg rather than groupby.apply: apply needs
    include_groups on pandas 2.2+ and raises a TypeError without it on older
    versions, so the apply form would break on an older pandas in the
    warehouse environment.
    """
    # Bins by RANK POSITION, not by value quantile. Isotonic regression is a
    # step function and produces heavy ties, so pd.qcut with duplicates="drop"
    # collapses bins: a first run of this gave 9 bins holding 8,090 and 433
    # rows, and the "furthest from 1.0" figure was then read off the 433-row
    # bin. Rank bins are always equal-sized, so the deciles are comparable.
    pv = np.asarray(p, dtype=float)
    n  = len(pv)
    order = np.argsort(pv, kind="mergesort")
    dec = np.empty(n, dtype=int)
    dec[order] = np.arange(n) * 10 // n
    d = pd.DataFrame({
        "d": dec,
        "y": np.asarray(y, dtype=float),
        "p": pv,
        "w": np.asarray(w, dtype=float)})
    d["wp"] = d.w * d.p
    d["wy"] = d.w * d.y
    g = d.groupby("d").agg(n=("y", "size"), weighted_n=("w", "sum"),
                           wp=("wp", "sum"), wy=("wy", "sum"))
    g["predicted"] = g.wp / g.weighted_n
    g["observed"]  = g.wy / g.weighted_n
    g["ratio"]     = g.observed / g.predicted.replace(0, np.nan)
    # The EXPECTED number of bads in the decile. The ratio is not interpretable
    # where this is tiny: a decile of 2,239 rows at a predicted 0.0126 pct
    # expects 0.28 bads, so observing zero is ordinary and gives a ratio of
    # 0.000 that reads as catastrophic miscalibration. An earlier version
    # reported exactly that as "furthest from 1.0".
    g["exp_bad"] = g.weighted_n * g.predicted
    g = g[["n", "weighted_n", "predicted", "observed", "exp_bad", "ratio"]]
    print(f"\n  calibration by decile{label} (ratio near 1.0 is the goal)")
    print(g.to_string(float_format=lambda v: f"{v:12.6f}"))

    MIN_EXP = 10.0
    judge = g[g.exp_bad >= MIN_EXP]
    if len(judge) == 0:
        print(f"  no decile expects {MIN_EXP:.0f}+ bads, so the ratios are all")
        print("  small-sample noise and calibration cannot be judged here.")
    else:
        worst = judge.ratio.iloc[(judge.ratio - 1.0).abs().to_numpy().argmax()]
        print(f"  furthest from 1.0: {worst:.3f}   "
              f"(over the {len(judge)} of {len(g)} deciles expecting "
              f"{MIN_EXP:.0f}+ bads)")
        if len(judge) < len(g):
            print(f"  the other {len(g)-len(judge)} expect too few events for "
                  f"the ratio to mean anything")
    return g


def psi(expected, actual, bins=10):
    """Population Stability Index between two samples of one feature.

    Bin edges come from the EXPECTED sample's quantiles, except for
    low-cardinality features, which are compared on their values. Convention:
        under 0.10   stable
        0.10 to 0.25 moderate shift
        over 0.25    significant shift
    Returns NaN only when a sample is empty.
    """
    e = np.asarray(expected, dtype=float)
    a = np.asarray(actual, dtype=float)
    e = e[np.isfinite(e)]
    a = a[np.isfinite(a)]
    if len(e) == 0 or len(a) == 0:
        return np.nan

    # Low-cardinality features - flags, small counts - cannot be split into
    # ten quantile bins, and an earlier version returned NaN for them. A
    # binary flag can drift as easily as anything else, so those are compared
    # on their VALUES instead of on quantiles. f_reclaim was invisible before.
    vals = np.unique(e)
    if len(vals) <= bins:
        cats = np.unique(np.concatenate([vals, np.unique(a)]))
        pe = np.array([(e == v).sum() for v in cats], dtype=float)
        pa = np.array([(a == v).sum() for v in cats], dtype=float)
    else:
        edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
        if len(edges) < 3:
            return np.nan
        edges[0], edges[-1] = -np.inf, np.inf
        pe, _ = np.histogram(e, bins=edges)
        pa, _ = np.histogram(a, bins=edges)
        pe = pe.astype(float)
        pa = pa.astype(float)
    if pe.sum() == 0 or pa.sum() == 0:
        return np.nan
    pe = pe / pe.sum()
    pa = pa / pa.sum()
    # a floor so an empty bin does not send the log to infinity
    pe = np.clip(pe, 1e-6, None)
    pa = np.clip(pa, 1e-6, None)
    return float(np.sum((pa - pe) * np.log(pa / pe)))


# ---------------------------------------------------------------------------
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rng = np.random.default_rng(SEED)

    print("LOADING")
    md = load(MODEL_FILE)
    sc = load(SCORE_FILE)

    shared = set(md.columns) & set(sc.columns)
    only_md = sorted(set(md.columns) - shared)
    only_sc = sorted(set(sc.columns) - shared)
    if only_md or only_sc:
        print(f"\n  columns only in dcb_model: {only_md}")
        print(f"  columns only in dcb_score: {only_sc}")
        print("  (y and n_label_months are expected here; anything else means")
        print("   one table was built by an older run of the SQL)")

    # ---- the 70/20/10 split ----------------------------------------------
    print("\nSPLITTING dcb_model 70/20/10 on a hash of sbrp_id")
    h = hash_bucket(md.sbrp_id).to_numpy()
    md["split"] = np.where(h < SPLIT_TRAIN, "train",
                  np.where(h < SPLIT_VALID, "valid", "test"))
    for nm in ("train", "valid", "test"):
        d = md[md.split == nm]
        print(f"  {nm:<6} {len(d):>10,} rows  {int(d.y.sum()):>7,} bad  "
              f"{d.y.mean():.4%}")
    print(f"\n  whole table {len(md):,} rows at {md.y.mean():.4%}")
    drift = abs(md.y.mean() - REFERENCE_RATE) / REFERENCE_RATE
    print(f"  reference for this window at the production bar "
          f"{REFERENCE_RATE:.4%} -> {drift:.1%} apart")
    if md.y.mean() > 0.0080:
        print("  WARNING the rate is approaching the 0.95 pct that belongs to a")
        print("  months 1-4 label. These labels should be months 7-10. Check the")
        print("  label months in 42_model_datasets.sql before going further.")

    # The three splits must have similar event rates. They are random draws
    # from one table, so a real gap means the hash is not behaving.
    rates = [md[md.split == nm].y.mean() for nm in ("train", "valid", "test")]
    if max(rates) / max(min(rates), 1e-12) > 1.5:
        print(f"  WARNING split event rates differ by more than 1.5x: "
              f"{[f'{r:.4%}' for r in rates]}")

    # ---- the band ---------------------------------------------------------
    # MODEL_POP in the SQL decides what dcb_model contains. Whatever it
    # contains, the metrics are read on in_band = 1 rows, because that is the
    # only population dcb_score holds and therefore the only one ever scored.
    #
    # Measured on synthetic data: a model trained on the whole base reported an
    # AUC of 0.78-0.82 on the whole base while performing at 0.63-0.69 in the
    # band. Comparing a whole-base AUC against a band AUC compares two
    # different test sets and says nothing.
    if "in_band" not in md.columns:
        md["in_band"] = 1
        print("\n  no in_band column - rebuild with the current SQL. Assuming")
        print("  every row is in band, which is only true for MODEL_POP=screened.")
    band_share = md.in_band.mean()
    print(f"\n  in_band rows: {int(md.in_band.sum()):,} of {len(md):,} "
          f"({band_share:.1%})")
    if band_share < 0.999:
        print("  dcb_model is WIDER than the production screen, so TRAIN sees")
        print("  rows that can never be scored. Metrics below are reported both")
        print("  ways and only the in-band figures are comparable across runs.")

    # ---- features ---------------------------------------------------------
    FEATURES = [c for c in md.columns if c not in NOT_FEATURES]
    FEATURES = [c for c in FEATURES if c in sc.columns]
    FEATURES = [c for c in FEATURES if pd.api.types.is_numeric_dtype(md[c])]

    # Zero-variance columns. oneway_months is zero for every row by
    # construction - the screen requires it - and a constant column is dead
    # weight at best. At worst it is the trap debt_scr and suspend_scr set
    # earlier here: all-zero in 6 of 10 months, producing a PSI of 13.89 that
    # read as catastrophic drift when it was a loading gap.
    dead = [(c, (md[c].nunique(dropna=True), sc[c].nunique(dropna=True)))
            for c in FEATURES
            if max(md[c].nunique(dropna=True), sc[c].nunique(dropna=True)) <= 1]
    if dead:
        print("\nDROPPED - no variance in either table:")
        for c, nun in dead:
            print(f"  {c:16s} distinct values MODEL/SCORE {nun}")
        FEATURES = [c for c in FEATURES if c not in {d[0] for d in dead}]

    if USE_RELATIVE_ONLY:
        drop = [c for c in RAW_WITH_REL if c + "_rel" in FEATURES]
        FEATURES = [c for c in FEATURES if c not in drop]
        print(f"\nUSE_RELATIVE_ONLY: dropped the raw twins {drop}")

    leak = [c for c in FEATURES
            if c in ("y", "cohort", "n_label_months", "sample_weight", "split")]
    assert not leak, f"label or label-derived column in the features: {leak}"
    assert FEATURES, "no features survived selection"
    print(f"\nFEATURES: {len(FEATURES)}")
    print(f"  {FEATURES}")

    # ---- PSI: the drift a random split cannot show -----------------------
    print("\nFEATURE DRIFT, dcb_model against dcb_score (PSI)")
    print("  under 0.10 stable, 0.10-0.25 moderate, over 0.25 significant")
    rows = sorted(((c, psi(md[c], sc[c])) for c in FEATURES),
                  key=lambda t: -(t[1] if np.isfinite(t[1]) else -1))
    for c, v in rows:
        flag = ("" if not np.isfinite(v) else
                "   <-- significant" if v > 0.25 else
                "   <-- moderate" if v > 0.10 else "")
        print(f"  {c:18s} {v:8.4f}{flag}")
    big = [c for c, v in rows if np.isfinite(v) and v > 0.25]
    if big:
        print(f"\n  {len(big)} feature(s) have shifted significantly. This is")
        print("  measured drift, not noise: 43_cohort_funnel.sql found revenue")
        print("  per subscriber-month up 1.64x at the p90 between these two")
        print("  windows. The TEST metrics below are an UPPER BOUND on live")
        print("  performance.")
        raw_big = [c for c in big if c in RAW_WITH_REL]
        if raw_big and not USE_RELATIVE_ONLY:
            print(f"\n  {raw_big} are raw Rial levels with _rel twins already in")
            print("  the data. Set USE_RELATIVE_ONLY = True and re-run to fit on")
            print("  the ratios instead, then compare TEST AUC. If it holds up,")
            print("  prefer that model - it will age better.")

    # ---- matrices ---------------------------------------------------------
    tr = downsample(md[md.split == "train"], GOOD_KEEP)
    va = md[md.split == "valid"]
    te = md[md.split == "test"]

    def X(d):
        return np.nan_to_num(d[FEATURES].to_numpy(float),
                             nan=0.0, posinf=0.0, neginf=0.0)
    Xtr, ytr, wtr = X(tr), tr.y.to_numpy(int), tr.sample_weight.to_numpy(float)
    Xva, yva = X(va), va.y.to_numpy(int)
    Xte, yte = X(te), te.y.to_numpy(int)
    wva, wte = np.ones(len(yva)), np.ones(len(yte))
    # boolean masks for the production-equivalent rows
    bva = va.in_band.to_numpy().astype(bool)
    bte = te.in_band.to_numpy().astype(bool)
    print(f"  VALID in band {bva.sum():,}/{len(bva):,}   "
          f"TEST in band {bte.sum():,}/{len(bte):,}")
    del md
    gc.collect()

    # ---- champion: logistic ----------------------------------------------
    from sklearn.linear_model   import LogisticRegression
    from sklearn.preprocessing  import StandardScaler
    from sklearn.pipeline       import make_pipeline
    print("\nFITTING champion")
    t0 = time.time()
    champ = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs"))
    champ.fit(Xtr, ytr, logisticregression__sample_weight=wtr)
    print(f"  logistic fitted in {time.time()-t0:,.0f}s")

    # ---- challenger: gradient boosting -----------------------------------
    from sklearn.ensemble import HistGradientBoostingClassifier
    print("FITTING challenger")
    t0 = time.time()
    chal = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        early_stopping=True, validation_fraction=0.15, random_state=SEED)
    chal.fit(Xtr, ytr, sample_weight=wtr)
    print(f"  gradient boosting fitted in {time.time()-t0:,.0f}s, "
          f"{chal.n_iter_} iterations of a 400 ceiling")

    print("\nIN-SAMPLE (TRAIN, weighted) - flatters both, reported for the gap")
    RES = [report("logistic (champion)", ytr, champ.predict_proba(Xtr)[:, 1], wtr),
           report("HistGB (challenger)", ytr, chal.predict_proba(Xtr)[:, 1], wtr)]

    print("\nVALID - the selection set, IN BAND")
    pva_c = champ.predict_proba(Xva)[:, 1]
    pva_g = chal.predict_proba(Xva)[:, 1]
    RV = [report("logistic (champion)", yva[bva], pva_c[bva], wva[bva]),
          report("HistGB (challenger)", yva[bva], pva_g[bva], wva[bva])]
    if bva.mean() < 0.999:
        print("  and on ALL VALID rows, for contrast - NOT comparable:")
        report("logistic, all rows", yva, pva_c, wva)
        report("HistGB, all rows",   yva, pva_g, wva)

    best  = "HistGB" if RV[1]["auc"] > RV[0]["auc"] else "logistic"
    i     = 1 if best == "HistGB" else 0
    pva   = pva_g if best == "HistGB" else pva_c
    model = chal  if best == "HistGB" else champ
    print(f"\n  selected on VALID AUC: {best}")
    gap = RES[i]["auc"] - RV[i]["auc"]
    print(f"  train-to-valid AUC gap {gap:+.4f}"
          + ("   <-- overfitted, reduce max_iter" if gap > 0.05
             else "   (acceptable)"))

    # ---- calibration: fit on VALID, judge on TEST ------------------------
    from sklearn.isotonic import IsotonicRegression
    # Fitted on the IN-BAND half of VALID. Calibrating on a wider population
    # would anchor the level to a base rate the scored population does not have.
    iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-7, y_max=1 - 1e-7)
    iso.fit(pva[bva], yva[bva])
    anchor = (np.average(yva[bva])
              / max(np.average(iso.predict(pva[bva])), 1e-9))
    print(f"\nCALIBRATION fitted on VALID in band ({int(bva.sum()):,} rows)")
    print(f"  anchor ratio {anchor:.4f}  (1.0 = no rescaling needed)")

    # ---- TEST: read once -------------------------------------------------
    print(f"\nTEST - {int(bte.sum()):,} in-band rows, untouched until now.")
    print("       Nothing was tuned on these, so this is the honest")
    print("       within-period number for the population that gets scored.")
    pte = np.clip(iso.predict(model.predict_proba(Xte)[:, 1]) * anchor,
                  1e-7, 0.999)
    RT = [report(f"{best} calibrated [TEST in band]",
                 yte[bte], pte[bte], wte[bte])]
    if bte.mean() < 0.999:
        print("  and on ALL TEST rows - NOT the scored population, shown only")
        print("  so the gap between the two is visible:")
        RT.append(report(f"{best} calibrated [TEST all rows]", yte, pte, wte))
        print(f"  the all-rows AUC runs "
              f"{RT[-1]['auc']-RT[0]['auc']:+.4f} against in-band. Quote the "
              f"in-band figure.")
    print(f"  mean PD {pte[bte].mean():.4%}  vs observed {yte[bte].mean():.4%} "
          f" -> level error "
          f"{abs(pte[bte].mean()-yte[bte].mean())/max(yte[bte].mean(),1e-9):.2%}")
    decile_table(yte[bte], pte[bte], wte[bte], " on TEST in band")

    # ---- score the live set ----------------------------------------------
    print("\nSCORING THE LIVE SET")
    psc = np.clip(iso.predict(model.predict_proba(X(sc))[:, 1]) * anchor,
                  1e-7, 0.999)
    out = pd.DataFrame({"sbrp_id": sc.sbrp_id.values, "pd_4m": psc})
    out["grade"] = pd.cut(out.pd_4m, [-1, 0.002, 0.005, 0.010, 0.020, 1.0],
                          labels=["A", "B", "C", "D", "E"])
    print(f"  scored {len(out):,} subscribers")
    print(f"  mean predicted PD {out.pd_4m.mean():.4%}  "
          f"(TEST observed {yte.mean():.4%})")
    if out.pd_4m.mean() > 1.5 * yte.mean():
        print("  NOTE the live set scores materially riskier than TEST. That is")
        print("  consistent with the measured drift - the lower bar admits a")
        print("  broader population in the scoring window - and is a reason to")
        print("  trust the PD ranking more than the PD level.")
    print("\n  by grade")
    gb = out.groupby("grade", observed=True).agg(n=("pd_4m", "size"),
                                                 mean_pd=("pd_4m", "mean"))
    gb["share"] = gb.n / gb.n.sum()
    print(gb.to_string(float_format=lambda v: f"{v:12.6f}"))

    # ---- the tables the limit engine consumes ----------------------------
    o = out.sort_values("pd_4m").reset_index(drop=True)
    o["cum_pd"] = o.pd_4m.expanding().mean()
    print("\n  SELECTING THE SAFEST N - this is the table the limit engine uses")
    print(f"  {'take':>12} {'share':>7} {'book mean PD':>13} "
          f"{'exposure':>14} {'expected loss':>14}")
    marks = [int(len(o) * f) for f in
             (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
    marks += [n for n in (3_000_000,) if n <= len(o)]
    for n in sorted(set(m for m in marks if m > 0)):
        pdn, expo = o.cum_pd.iloc[n - 1], n * TICKET_TOMAN
        print(f"  {n:>12,} {n/len(o):>6.1%} {pdn:>12.4%} "
              f"{expo/1e12:>11,.1f} tn {expo*pdn/1e9:>11,.1f} bn")

    print("\n  LARGEST BOOK UNDER A PD CEILING")
    print(f"  {'ceiling':>9} {'take':>12} {'share':>7} {'exposure':>14} "
          f"{'expected loss':>14}")
    for ceil in (0.0025, 0.005, 0.0075, 0.010, 0.015, 0.020):
        under = np.flatnonzero(o.cum_pd.to_numpy() <= ceil)
        if len(under) == 0:
            print(f"  {ceil:>8.2%} {'-':>12} {'-':>7}   no subscriber qualifies")
            continue
        n, expo = int(under[-1]) + 1, (int(under[-1]) + 1) * TICKET_TOMAN
        print(f"  {ceil:>8.2%} {n:>12,} {n/len(o):>6.1%} "
              f"{expo/1e12:>11,.1f} tn {expo*o.cum_pd.iloc[n-1]/1e9:>11,.1f} bn")

    print(f"\n  Exposure assumes every approved subscriber draws the full "
          f"{TICKET_TOMAN:,} Toman line, and expected loss assumes a two-way")
    print("  bar loses the WHOLE balance (LGD 100 pct). Both are deliberately")
    print("  pessimistic. Treat them as a ceiling on the loss, not a forecast.")

    # float_format matters more than it looks. By default pandas writes small
    # floats in scientific notation - 1.573e-07 - and if that CSV is loaded
    # into a VARCHAR column, "ORDER BY pd_4m" becomes a TEXT sort in which
    # '1e-07' sorts after '0.0252', putting the SAFEST subscribers last. On a
    # simulation of the real value range that turned a 0.082 pct book into a
    # 1.348 pct one while still returning the right row COUNT. A fixed
    # 12-decimal format cannot produce scientific notation, so the file is
    # unambiguous however it is typed on the way in.
    path = os.path.join(OUTDIR, "handover_scores.csv")
    out.to_csv(path, index=False, float_format="%.12f")
    print(f"\n  written to {path}  ({len(out):,} rows)")
    metrics = pd.DataFrame(
        RES + [dict(r, model=r["model"] + " [VALID]") for r in RV] + RT)
    metrics.to_csv(os.path.join(OUTDIR, "metrics.csv"), index=False)
    print(f"  metrics written to {OUTDIR}/metrics.csv")

    print("\nWHAT IS NOT REPORTED, AND WHY")
    print("  Accuracy. At a rate near 0.55 pct a model predicting 'nobody")
    print("  defaults' scores 99.45 pct, so the number says nothing.")
    print("  A whole-population AUC, when dcb_model is wider than the screen.")
    print("  It ran 0.13 to 0.15 above the in-band figure on synthetic data,")
    print("  and only the in-band figure describes the lending decision.")
    print("  An out-of-time estimate. The split is random by subscriber, so")
    print("  TEST measures generalisation to other subscribers in the SAME")
    print("  period. The PSI section is what speaks to the later period, and")
    print("  it says the features have moved.")


if __name__ == "__main__":
    main()

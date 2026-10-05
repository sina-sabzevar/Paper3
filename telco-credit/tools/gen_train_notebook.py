# -*- coding: utf-8 -*-
"""Emit notebook/train_model.ipynb - the training pipeline, cell by cell.

Hand-written .ipynb JSON is a bad idea: one stray comma and the file will not
open, and the error Jupyter shows points at a byte offset rather than at the
cell. The cells are declared here as plain text and nbformat builds and
VALIDATES the document, so a malformed notebook cannot be produced.

    python3 tools/gen_train_notebook.py
"""
import io, os, sys
import nbformat as nbf

MD, CODE = "md", "code"
C = []
def md(s):   C.append((MD, s.strip("\n")))
def code(s): C.append((CODE, s.strip("\n")))

# ===========================================================================
md(r"""
# Telco credit line - PD model, 4-month label

**What this notebook does.** Takes the three cohort tables built by
`sql/42_model_datasets.sql`, fits a probability-of-default model, validates it
on a *later time period*, calibrates it, scores the live population, and
produces the two tables the limit engine needs.

### The target

| | |
|---|---|
| **Screen** | revenue >= 170,000 Toman in **2 or more** of 6 months, never one-way barred, never two-way barred in that window |
| **Label** | `y = 1` if the subscriber is **two-way barred** (`sbrp_stat_id = 4`) within the **4 months immediately after** the feature window |
| **Population** | 6,879,803 subscribers |
| **Event rate** | **0.95%** at the 4-month horizon |

### Why 4 months costs more than twice 2 months

Risk is **back-loaded**: measured at `p_n` proportional to `n^1.40`. Stretching
the window from 2 to 4 months moves the event rate 0.36% -> 0.95%, which is
**2.6x**, not the 2.0x a constant hazard would give. The 4-month window is the
harder problem and the honest one, because a 4-month credit line is exposed for
four months.

### The three cohorts

Data runs `140301..140506`.

| cohort | features | label | role |
|---|---|---|---|
| `TRAIN` | 140309..140402 | 140403..140406 | fit the model |
| `VALID` | 140407..140412 | 140501..140504 | **out of time** - the real test |
| `SCORE` | 140501..140506 | none, the outcome is the future | the live set to lend to |

`TRAIN`'s label window **ends** at 140406, one month before `VALID`'s feature
window **begins** at 140407. That is what makes the validation genuinely
out-of-time rather than a reshuffle of a single period.

### Why TRAIN sits as late as it possibly can

An earlier version of this put `TRAIN` at `140301..140306`, the start of the
data. It returned **3,733,333** subscribers against `VALID`'s **6,879,803** -
a 46% shortfall on the *same* screen.

The cause is that the screen's 170,000 Toman threshold is **fixed nominal**.
Nominal revenue per subscriber rises with inflation and tariff changes, so the
same bar is a materially **harsher** screen the further back the window sits.
A window twelve months earlier therefore selects the richer tail - a different
population from the one `SCORE` holds, which is not what you want to fit a
model on.

`140309..140402` is the latest window a 4-month label permits, 8 months closer
to `SCORE`. `sql/43_cohort_funnel.sql` measures how much drift is left after
the move, and section 3 below checks the event rate.

`VALID` is deliberately the exact window measured in
`41_forward_horizons.sql` at **0.95%** for this same screen over 4 months, so
section 3 can check the two files against each other.

### How to run

1. Run `sql/42_model_datasets.sql`. Check its `T4` output lands near 0.95%.
2. Export `dcb_train`, `dcb_valid`, `dcb_score` into `notebook/data/`
   (parquet or CSV, single file or `_part1`/`_part2` pieces - the loader
   handles all of those).
3. Run this notebook top to bottom.

Run the cells **in order**. Each one depends on names defined above it.
""")

# ---------------------------------------------------------------------------
md(r"""
---
## 0. Imports and environment

Nothing here touches the data. The printed versions matter because one
dependency in this pipeline is version-sensitive, and it is worth seeing the
numbers before a four-minute fit fails on an API change.
""")

code(r'''
# Standard library.
import gc        # the TRAIN frame is dropped explicitly after down-sampling
import os
import glob
import time
import hashlib   # the down-sampling draw; see section 5 for why not MOD

import numpy as np
import pandas as pd

# scikit-learn is imported in the cells that use it rather than all at once,
# so that a missing optional piece fails where it is relevant instead of
# stopping the notebook at cell 1.
import sklearn

print("pandas ", pd.__version__)
print("numpy  ", np.__version__)
print("sklearn", sklearn.__version__)

# Show money and rates without scientific notation - these are Rial and Toman
# figures in the billions and 6.9e+06 is not a readable subscriber count.
pd.set_option("display.float_format", lambda v: f"{v:,.6f}")
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 60)
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 1. Configuration

Every knob in one place. Changing anything below changes the model, so this is
the only cell to edit when re-running.

**`GOOD_KEEP`** is the one with a subtle consequence. See section 5.

**`TICKET_TOMAN`** affects **no model fit**. It only converts the PD ranking
into money columns in section 10, and it is the business's number, not the
model's.
""")

code(r'''
DATA       = "data"          # where the exported cohort files live
TRAIN_FILE = "dcb_train"     # file stems, no extension - the loader globs
VALID_FILE = "dcb_valid"
SCORE_FILE = "dcb_score"
OUTDIR     = "outputs"       # handover_scores.csv and metrics.csv land here

GOOD_KEEP  = 10              # keep this many goods out of every 100 (section 5)
SEED       = 42              # fixed so two runs give the same model

# The credit line per approved subscriber, in Toman. Used ONLY to turn the PD
# ranking into exposure and expected-loss columns in section 10. It changes no
# fit and no metric. 500,000 is the line discussed for this product; the stated
# floor is 400,000.
TICKET_TOMAN = 500_000

# The event rate this screen was measured at over a 4-month horizon, from
# sql/41_forward_horizons.sql. Section 3 checks the loaded data against it.
EXPECTED_RATE = 0.0095

# Columns that are NOT features:
#   sbrp_id         an identity. A tree would happily memorise individuals.
#   y               the label itself.
#   cohort          a constant string tag per file.
#   sample_weight   created by down-sampling, not observed in the data.
#   n_label_months  how many months of the LABEL window the subscriber appeared
#                   in. Built from the outcome and NULL in SCORE, so it is
#                   LEAKAGE. It is carried in the data to measure partial
#                   observation (section 3) and excluded from the model here.
NOT_FEATURES = {"sbrp_id", "y", "cohort", "sample_weight", "n_label_months"}

os.makedirs(OUTDIR, exist_ok=True)
rng = np.random.default_rng(SEED)
print(f"outputs -> {OUTDIR}/   seed {SEED}   ticket {TICKET_TOMAN:,} Toman")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 2. Loading

The export can arrive as parquet or CSV, as one file or split into
`_part1`/`_part2` pieces, because 6.9M rows does not always come back from the
warehouse in a single file. The loader accepts all of those shapes.

**The duplicate check is not decoration.** When a table is exported in parts by
a range condition, getting the boundary wrong gives overlapping parts. Every
row in the overlap is then counted twice, which silently shifts every rate and
metric below. The earlier split in this project was fixed to an exact
`ROW_NUMBER` boundary for exactly this reason. If parts overlap, this raises
instead of continuing.
""")

code(r'''
def load(stem):
    """Load one cohort by file stem.

    Tries, in order: <stem>.parquet, <stem>*.parquet, <stem>.csv, <stem>*.csv.
    The glob forms pick up part files. Multiple parts are concatenated.

    Raises if sbrp_id repeats, which means the parts overlap and every rate
    computed downstream would be wrong.
    """
    base = os.path.join(DATA, stem)
    for pat in (base + ".parquet", base + "*.parquet",
                base + ".csv",     base + "*.csv"):
        files = sorted(glob.glob(pat))
        if not files:
            continue
        reader = pd.read_parquet if files[0].endswith(".parquet") else pd.read_csv
        parts  = [reader(f) for f in files]
        df = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
        print(f"  {stem}: {len(files)} file(s) -> {len(df):,} rows "
              f"x {df.shape[1]} cols")

        if "sbrp_id" in df.columns:
            dup = len(df) - df.sbrp_id.nunique()
            if dup:
                raise ValueError(
                    f"{dup:,} duplicate sbrp_id in {stem}. The parts overlap, "
                    f"so those subscribers are counted twice and every metric "
                    f"below would be wrong. Re-export on an exact boundary.")
        return df

    raise FileNotFoundError(
        f"nothing found for {stem} under {DATA}/. Run sql/42_model_datasets.sql "
        f"and export dcb_train, dcb_valid and dcb_score into {DATA}/.")
''')

code(r'''
print("LOADING")
tr_raw = load(TRAIN_FILE)
va_raw = load(VALID_FILE)
sc_raw = load(SCORE_FILE)

# All three cohorts are projected by the same generated SQL, so their columns
# must match exactly. If they do not, one table was built by an older version
# of 42_model_datasets.sql and the feature list below would silently differ
# between fitting and scoring.
cols_tr, cols_va, cols_sc = set(tr_raw.columns), set(va_raw.columns), set(sc_raw.columns)
if not (cols_tr == cols_va == cols_sc):
    print("\n  WARNING cohort columns differ - was one table built by an older SQL run?")
    print("   TRAIN only:", sorted(cols_tr - cols_va - cols_sc))
    print("   VALID only:", sorted(cols_va - cols_tr - cols_sc))
    print("   SCORE only:", sorted(cols_sc - cols_tr - cols_va))
else:
    print(f"\n  all three cohorts carry the same {len(cols_tr)} columns")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 3. Event rates, and the cross-check against the SQL

`VALID` should land near **0.95%**. That figure is on record from
`41_forward_horizons.sql` for this exact screen at a 4-month horizon, computed
by a completely separate query. If the two disagree, one of the files is wrong
and the model is not the thing to debug.

`TRAIN` will not match it exactly and is not expected to - it is a different
and earlier period, which is the whole point of holding `VALID` back.

### Partial observation

Over a 4-month label window a subscriber can appear in only part of it. Those
rows are **kept**, on the rule "present in at least one label month", which is
the same rule `41_forward_horizons.sql` used (`n_out_months > 0`). Matching
that rule is what makes the 0.95% comparison meaningful.

It does mean a subscriber seen in 1 of 4 months and never barred is scored
`y = 0` on one month of evidence. The second cell measures what that is worth:
if the fully-observed rate is materially higher, the headline rate is diluted
by subscribers who simply had less time to fail.
""")

code(r'''
print("EVENT RATES AS BUILT")
for nm, d in (("TRAIN", tr_raw), ("VALID", va_raw)):
    print(f"  {nm}: {len(d):,} rows, {int(d.y.sum()):,} bad, {d.y.mean():.4%}")
print(f"  SCORE: {len(sc_raw):,} rows, no label")

# The cross-check. A warning, not an assertion: a modest gap is ordinary
# sampling noise, while a large one means the two files disagree.
obs  = va_raw.y.mean()
drift = abs(obs - EXPECTED_RATE) / EXPECTED_RATE
print(f"\n  VALID observed {obs:.4%} vs {EXPECTED_RATE:.4%} on record "
      f"-> {drift:.1%} apart")
if drift > 0.25:
    print("  WARNING more than 25 pct apart. 42_model_datasets.sql and")
    print("  41_forward_horizons.sql disagree about this population. Check the")
    print("  screen and the label months in both before trusting anything below.")
else:
    print("  consistent with the recorded figure.")
''')

code(r'''
# What is partial observation worth? Four months of exposure is not the same
# bet as one, so this asks whether the partly observed dilute the rate.
for nm, d in (("TRAIN", tr_raw), ("VALID", va_raw)):
    if "n_label_months" not in d.columns:
        print(f"  {nm}: no n_label_months column - rebuild with the current SQL")
        continue
    full = d[d.n_label_months >= 4]
    part = d[d.n_label_months <  4]
    print(f"  {nm}: fully observed {len(full):,} at {full.y.mean():.4%}   "
          f"partly observed {len(part):,} at "
          f"{part.y.mean() if len(part) else float('nan'):.4%}   "
          f"partial share {len(part)/len(d):.2%}")
print("\n  If the fully observed rate is materially HIGHER, the headline rate")
print("  is diluted by subscribers who had less time to fail, and the")
print("  fully-observed figure is the honest one to quote to the business.")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 4. Choosing the features

Three filters, then two guards.

**Filters.** Drop the non-features from section 1; keep only columns present in
all three cohorts (a column missing from `SCORE` cannot be used at scoring
time); keep only numeric columns.

**Guard 1 - no variance.** `oneway_months` is zero for every row *by
construction*, because the screen requires it. A constant column is dead weight
at best. At worst it is the trap `debt_scr` and `suspend_scr` set earlier in
this project: both were all-zero in 6 of 10 months, which produced a PSI of
13.89 and 14.41 and read as catastrophic feature drift when it was really a
loading gap. Dropped and reported, never silently.

**Guard 2 - constant in TRAIN only.** Worse than constant everywhere: the model
cannot learn a coefficient for a column that never moves in training, then
meets it moving at scoring time. Reported loudly.

**Then the leakage assertion.** Cheap, and it catches the one class of mistake
that produces a beautiful AUC and a worthless model.
""")

code(r'''
# --- the three filters ---------------------------------------------------
FEATURES = [c for c in tr_raw.columns if c not in NOT_FEATURES]
FEATURES = [c for c in FEATURES if c in va_raw.columns and c in sc_raw.columns]
FEATURES = [c for c in FEATURES if pd.api.types.is_numeric_dtype(tr_raw[c])]

# --- guard 1: columns with no variance anywhere --------------------------
dead = []
for c in FEATURES:
    nun = (tr_raw[c].nunique(dropna=True),
           va_raw[c].nunique(dropna=True),
           sc_raw[c].nunique(dropna=True))
    if max(nun) <= 1:
        dead.append((c, nun))

if dead:
    print("DROPPED - no variance in any cohort:")
    for c, nun in dead:
        print(f"  {c:16s} distinct values TRAIN/VALID/SCORE {nun}")
    FEATURES = [c for c in FEATURES if c not in {d[0] for d in dead}]

# --- guard 2: constant in TRAIN but moving elsewhere --------------------
for c in FEATURES:
    if tr_raw[c].nunique(dropna=True) <= 1:
        print(f"  WARNING {c} is constant in TRAIN but not in VALID/SCORE. The")
        print(f"          model cannot learn a coefficient for it, then meets")
        print(f"          it varying at scoring time.")

# --- the leakage assertion ----------------------------------------------
leak = [c for c in FEATURES
        if c in ("y", "cohort", "n_label_months", "sample_weight")]
assert not leak, f"label or label-derived column in the feature list: {leak}"
assert FEATURES, "no features survived selection"

print(f"\nFEATURES: {len(FEATURES)}")
for c in FEATURES:
    print(f"  {c}")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 5. Down-sampling, and the weight that undoes it

At a 0.95% event rate, 99% of the rows are goods and they are not where the
information is. Keeping every bad and a `GOOD_KEEP`% slice of the goods makes
the fit tractable. `sample_weight` then puts the base rate back.

### Use `sample_weight` in every fit and every metric

Without it the model sees roughly a **9%** event rate instead of 0.95%, and
every predicted probability comes out about **nine times too high**.

The exact arithmetic: keeping 10% of goods inflates the **odds** by exactly
`100 / GOOD_KEEP = 10x`. On the probability itself, at these rates:

```
bads kept    0.0095
goods kept   0.9905 x 0.10 = 0.09905
sample rate  0.0095 / 0.10855 = 8.75%     -> 9.2x the true 0.95%
```

Ranking survives that distortion. **The level does not**, and the limit engine
in section 10 spends the level, not the ranking.

### Why the draw is on a hash

The draw is on `md5(sbrp_id)`, not on `sbrp_id` itself. In this base **every
observed id is odd** and they share a five-digit block, so `MOD` on the raw id
selects a structured slice of the network rather than a sample of it. This was
found the hard way: a parity split on `sbrp_id` put all 11.5M rows in one half.
""")

code(r'''
def downsample(df, keep_pct):
    """Keep every bad and keep_pct percent of the goods, with a sample_weight
    column that restores the population base rate.

    The draw is on md5(sbrp_id) rather than on sbrp_id, because the raw ids in
    this base are all odd and share a five-digit block - MOD on them selects a
    structured slice, not a sample.
    """
    bad  = df[df.y == 1]
    good = df[df.y == 0]

    h = good.sbrp_id.astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 100)
    good = good[h.values < keep_pct]

    out = pd.concat([bad, good], ignore_index=True)
    # Bads were taken whole, so they carry weight 1. Goods stand in for
    # 100/keep_pct of themselves.
    out["sample_weight"] = np.where(out.y == 1, 1.0, 100.0 / keep_pct)

    print(f"  kept every bad ({len(bad):,}) and {keep_pct} pct of goods "
          f"({len(good):,}) -> {len(out):,} rows")
    print(f"  raw rate in the sample {out.y.mean():.4%}, weighted back to "
          f"{np.average(out.y, weights=out.sample_weight):.4%}")
    return out


print("DOWN-SAMPLING TRAIN")
tr = downsample(tr_raw, GOOD_KEEP)

# The raw TRAIN frame is millions of rows and is not needed again. Dropping it
# here rather than at the end of the notebook keeps peak memory down.
del tr_raw
gc.collect()
print("  raw TRAIN frame released")
''')

code(r'''
# Build the matrices once. nan_to_num because the source has real NULLs:
# arpu is 23.8 pct NULL, and a NULL there means no billing row, which the SQL
# already resolves to 0 revenue rather than to minus-the-tax.
Xtr = np.nan_to_num(tr[FEATURES].to_numpy(float), nan=0.0, posinf=0.0, neginf=0.0)
ytr = tr.y.to_numpy(int)
wtr = tr.sample_weight.to_numpy(float)

Xva = np.nan_to_num(va_raw[FEATURES].to_numpy(float), nan=0.0, posinf=0.0, neginf=0.0)
yva = va_raw.y.to_numpy(int)
# VALID is NOT down-sampled - it is the full population for its period, so
# every row already carries weight 1 and the metrics on it need no correction.
wva = np.ones(len(yva))

print(f"TRAIN matrix {Xtr.shape}   weighted rate "
      f"{np.average(ytr, weights=wtr):.4%}")
print(f"VALID matrix {Xva.shape}   rate {yva.mean():.4%}  (no sampling)")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 6. Fitting: champion and challenger

**Champion - logistic regression** on standardised features. Linear, monotone
in each feature, and the coefficients can be read and argued with, which is
what a credit committee will want.

**Challenger - histogram gradient boosting.** Catches interactions the logistic
cannot. It is a challenger, not the default: it wins only if it wins
out-of-time, in section 7.

Both are fitted **with `sample_weight`**.
""")

code(r'''
from sklearn.linear_model    import LogisticRegression
from sklearn.preprocessing  import StandardScaler
from sklearn.pipeline       import make_pipeline

# StandardScaler matters here: the features span raw Rial revenue in the
# millions and a month count in 0..6. Unscaled, lbfgs converges badly.
print("FITTING champion")
t0 = time.time()
champ = make_pipeline(
    StandardScaler(),
    LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs"))
# The pipeline forwards the weight to the final step by its step name.
champ.fit(Xtr, ytr, logisticregression__sample_weight=wtr)
print(f"  logistic fitted in {time.time()-t0:,.0f}s")
''')

code(r'''
from sklearn.ensemble import HistGradientBoostingClassifier

print("FITTING challenger")
t0 = time.time()
chal = HistGradientBoostingClassifier(
    max_iter=400,              # a ceiling; early stopping usually ends sooner
    learning_rate=0.06,
    max_leaf_nodes=31,
    early_stopping=True,
    validation_fraction=0.15,  # carved out of TRAIN, not from VALID
    random_state=SEED)
chal.fit(Xtr, ytr, sample_weight=wtr)
print(f"  gradient boosting fitted in {time.time()-t0:,.0f}s, "
      f"{chal.n_iter_} iterations of a 400 ceiling")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 7. Metrics, and the model choice

Every metric is **weighted**. An unweighted Brier score on a down-sampled file
read 0.29 on a 2% problem in an earlier version of this project - entirely from
the weighting error, not from the model.

| metric | what it tells you |
|---|---|
| **AUC / Gini** | ranking quality. This is what the limit engine consumes. |
| **KS** | separation at the best single cut. |
| **Brier** | calibration - whether the *level* is right, not just the order. |

**Accuracy is deliberately absent.** At a 0.95% event rate, a model that
predicts "nobody defaults" scores 99.05%. The number cannot distinguish a good
model from an empty one, so reporting it would only mislead.

The `decile_table` helper below uses a plain weighted `agg` rather than
`groupby.apply`. `apply` needs the `include_groups` argument on pandas 2.2+ and
raises a `TypeError` without it on older versions - the aggregation form works
on every version and is faster.
""")

code(r'''
def report(name, y, p, w):
    """Weighted AUC, Gini, KS and Brier for one model on one cohort."""
    from sklearn.metrics import roc_auc_score, brier_score_loss
    auc = roc_auc_score(y, p, sample_weight=w)
    br  = brier_score_loss(y, p, sample_weight=w)

    # Weighted KS: the largest gap between the cumulative bad and cumulative
    # good distributions, walking up the score.
    o  = np.argsort(p)
    ys = np.asarray(y)[o]
    ws = np.asarray(w)[o]
    cb = np.cumsum(ws * ys);       cb = cb / cb[-1]
    cg = np.cumsum(ws * (1 - ys)); cg = cg / cg[-1]
    ks = np.max(np.abs(cb - cg))

    print(f"  {name:<28} AUC {auc:.4f}   Gini {2*auc-1:.4f}   "
          f"KS {ks:.4f}   Brier {br:.6f}")
    return dict(model=name, auc=auc, gini=2*auc-1, ks=ks, brier=br)


def decile_table(y, p, w, label=""):
    """Predicted against observed by score decile, weighted.

    Uses weighted sums through agg rather than groupby.apply, which keeps this
    working on pandas versions before 2.2 where apply needs include_groups.
    """
    d = pd.DataFrame({
        "d":  pd.qcut(p, 10, labels=False, duplicates="drop"),
        "y":  np.asarray(y, dtype=float),
        "p":  np.asarray(p, dtype=float),
        "w":  np.asarray(w, dtype=float)})
    d["wp"] = d.w * d.p
    d["wy"] = d.w * d.y

    g = d.groupby("d").agg(n=("y", "size"), weighted_n=("w", "sum"),
                           wp=("wp", "sum"), wy=("wy", "sum"))
    g["predicted"] = g.wp / g.weighted_n
    g["observed"]  = g.wy / g.weighted_n
    g["ratio"]     = g.observed / g.predicted.replace(0, np.nan)
    g = g[["n", "weighted_n", "predicted", "observed", "ratio"]]

    print(f"\n  calibration by decile{label} (ratio near 1.0 is the goal)")
    print(g.to_string(float_format=lambda v: f"{v:12.6f}"))
    worst = g.ratio.iloc[(g.ratio - 1.0).abs().to_numpy().argmax()]
    print(f"  furthest from 1.0: {worst:.3f}")
    return g
''')

code(r'''
print("IN-SAMPLE (TRAIN, weighted) - expected to flatter both models")
RES = [report("logistic (champion)", ytr, champ.predict_proba(Xtr)[:, 1], wtr),
       report("HistGB (challenger)", ytr, chal.predict_proba(Xtr)[:, 1], wtr)]
''')

code(r'''
print("OUT OF TIME (VALID - a later period, never seen in training)")
pva_c = champ.predict_proba(Xva)[:, 1]
pva_g = chal.predict_proba(Xva)[:, 1]
RV = [report("logistic (champion)", yva, pva_c, wva),
      report("HistGB (challenger)", yva, pva_g, wva)]

# Selection is on OUT-OF-TIME AUC. In-sample ranking rewards whichever model
# memorised TRAIN hardest, which is the opposite of what is wanted.
best  = "HistGB" if RV[1]["auc"] > RV[0]["auc"] else "logistic"
i     = 1 if best == "HistGB" else 0
pva   = pva_g if best == "HistGB" else pva_c
model = chal  if best == "HistGB" else champ

print(f"\n  selected on OUT-OF-TIME AUC: {best}")
gap = RES[i]["auc"] - RV[i]["auc"]
print(f"  train-to-valid AUC gap {gap:+.4f}"
      + ("   <-- overfitted, reduce max_iter" if gap > 0.05 else "   (acceptable)"))
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 8. Calibration, fitted and judged on **different** rows

The model's ranking is good but its level is not usable yet: it was fitted on a
down-sampled file. Isotonic regression maps scores onto observed rates.

### The trap this avoids

Fitting isotonic on a set and then reading its calibration off *the same rows*
gives a ratio of 1.0000 in every decile **by construction** - a perfect-looking
table that proves nothing whatsoever. An earlier version of this project did
exactly that and the table looked flawless.

So `VALID` is split in half on a seeded coin flip: **one half fits the
calibrator, the other half judges it**. The decile table below is computed only
on rows the calibrator never saw.
""")

code(r'''
from sklearn.isotonic import IsotonicRegression

# Seeded split of VALID. One half calibrates, the other half judges.
h = rng.random(len(yva)) < 0.5

iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-7, y_max=1 - 1e-7)
iso.fit(pva[h], yva[h])

# A residual level correction. At 1.0 isotonic needed no rescaling, which is
# the healthy case - this is a ratio, not a probability.
anchor = np.average(yva[h]) / max(np.average(iso.predict(pva[h])), 1e-9)

print(f"CALIBRATION  fitted on {h.sum():,} rows, judged on {(~h).sum():,} "
      f"HELD-BACK rows")
print(f"  anchor ratio {anchor:.4f}  (1.0 = no rescaling needed)")

# Judged on the OTHER half.
pcal = np.clip(iso.predict(pva[~h]) * anchor, 1e-7, 0.999)
obs_held = yva[~h].mean()
print(f"  mean PD {pcal.mean():.4%}  vs observed {obs_held:.4%}  "
      f"-> level error {abs(pcal.mean()-obs_held)/max(obs_held,1e-9):.2%}")

cal_tbl = decile_table(yva[~h], pcal, np.ones((~h).sum()),
                       " on the held-back half")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 9. Scoring the live set

`SCORE` carries the most recent six months of features (`140501..140506`) and
no label, because the outcome has not happened yet. These are the subscribers
the product would actually lend to.

Grade bands are cuts on the calibrated PD:

| grade | 4-month PD |
|---|---|
| A | below 0.2% |
| B | 0.2% - 0.5% |
| C | 0.5% - 1.0% |
| D | 1.0% - 2.0% |
| E | above 2.0% |
""")

code(r'''
print("SCORING THE LIVE SET")
Xsc = np.nan_to_num(sc_raw[FEATURES].to_numpy(float),
                    nan=0.0, posinf=0.0, neginf=0.0)

# Same two steps the held-back half was judged through: the selected model,
# then the calibrator and its anchor.
psc = np.clip(iso.predict(model.predict_proba(Xsc)[:, 1]) * anchor, 1e-7, 0.999)

out = pd.DataFrame({"sbrp_id": sc_raw.sbrp_id.values, "pd_4m": psc})
out["grade"] = pd.cut(out.pd_4m,
                      [-1, 0.002, 0.005, 0.010, 0.020, 1.0],
                      labels=["A", "B", "C", "D", "E"])

print(f"  scored {len(out):,} subscribers")
print(f"  mean predicted PD {out.pd_4m.mean():.4%}  "
      f"(VALID observed {yva.mean():.4%})")

print("\n  by grade")
gb = out.groupby("grade", observed=True).agg(n=("pd_4m", "size"),
                                             mean_pd=("pd_4m", "mean"))
gb["share"] = gb.n / gb.n.sum()
print(gb.to_string(float_format=lambda v: f"{v:12.6f}"))
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 10. The two tables the limit engine uses

Sorted safest first, so row `n` answers: *if I lend to the n safest
subscribers, what is the average PD of that book?*

**Table 1 - safest N.** By share of the population rather than by absolute
milestones. Hardcoded milestones of 1M..5M collapsed to a single useless row
when tested on a smaller population, which is exactly the kind of silent
failure that gets shipped.

**Table 2 - largest book under a PD ceiling.** The same question from the other
side, and the form a credit committee states its appetite in: not "how many can
I take" but "how many can I take without the book's average PD crossing x".

### What the money columns assume

- **Exposure** assumes every approved subscriber draws the **full** line.
- **Expected loss** assumes a two-way bar loses the **whole balance**, LGD 100%.

Both are deliberately pessimistic: the operator keeps collecting after a bar,
and most subscribers will not draw the full line. Treat them as a **ceiling on
the loss, not a forecast**. The PD column is the model's output; the money
columns are that PD times assumptions the business owns and can change.
""")

code(r'''
# Cumulative mean PD, safest first.
o = out.sort_values("pd_4m").reset_index(drop=True)
o["cum_n"]  = np.arange(1, len(o) + 1)
o["cum_pd"] = o.pd_4m.expanding().mean()

print("  SELECTING THE SAFEST N - this is the table the limit engine uses")
print(f"  {'take':>12} {'share':>7} {'book mean PD':>13} "
      f"{'exposure':>14} {'expected loss':>14}")

# Share-based marks always exist at any population size. The 3,000,000 mark is
# the stated business minimum, included when the population reaches it.
marks  = [int(len(o) * f) for f in
          (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
marks += [n for n in (3_000_000,) if n <= len(o)]

for n in sorted(set(m for m in marks if m > 0)):
    pdn  = o.cum_pd.iloc[n - 1]
    expo = n * TICKET_TOMAN
    print(f"  {n:>12,} {n/len(o):>6.1%} {pdn:>12.4%} "
          f"{expo/1e12:>11,.1f} tn {expo*pdn/1e9:>11,.1f} bn")
''')

code(r'''
print("  LARGEST BOOK UNDER A PD CEILING")
print(f"  {'ceiling':>9} {'take':>12} {'share':>7} {'exposure':>14} "
      f"{'expected loss':>14}")

for ceil in (0.0025, 0.005, 0.0075, 0.010, 0.015, 0.020):
    # cum_pd rises monotonically, so the last index under the ceiling is the
    # largest book that satisfies it.
    under = np.flatnonzero(o.cum_pd.to_numpy() <= ceil)
    if len(under) == 0:
        print(f"  {ceil:>8.2%} {'-':>12} {'-':>7}   no subscriber qualifies")
        continue
    n    = int(under[-1]) + 1
    expo = n * TICKET_TOMAN
    print(f"  {ceil:>8.2%} {n:>12,} {n/len(o):>6.1%} "
          f"{expo/1e12:>11,.1f} tn {expo*o.cum_pd.iloc[n-1]/1e9:>11,.1f} bn")

print(f"\n  Exposure assumes every approved subscriber draws the full "
      f"{TICKET_TOMAN:,} Toman line, and expected loss assumes a two-way bar")
print("  loses the WHOLE balance (LGD 100 pct). Both are deliberately")
print("  pessimistic. Treat them as a ceiling on the loss, not a forecast.")
''')

# ---------------------------------------------------------------------------
md(r"""
---
## 11. Writing the handover files

| file | what it is |
|---|---|
| `outputs/handover_scores.csv` | one row per live subscriber: `sbrp_id`, `pd_4m`, `grade`. This is the file implementation consumes. |
| `outputs/metrics.csv` | the model comparison, in-sample and out-of-time, for the model-risk record. |
""")

code(r'''
path = os.path.join(OUTDIR, "handover_scores.csv")
out.to_csv(path, index=False)
print(f"  written to {path}  ({len(out):,} rows)")

metrics = pd.DataFrame(RES + [dict(r, model=r["model"] + " [OOT]") for r in RV])
mpath = os.path.join(OUTDIR, "metrics.csv")
metrics.to_csv(mpath, index=False)
print(f"  metrics written to {mpath}")
print()
print(metrics.to_string(index=False, float_format=lambda v: f"{v:10.6f}"))
''')

# ---------------------------------------------------------------------------
md(r"""
---
## What is not reported, and why

**Accuracy.** At a 0.95% event rate a model predicting "nobody defaults" scores
99.05%. It cannot tell a working model from an empty one.

**In-sample metrics as evidence.** They are printed in section 7 for the
train-to-valid gap, which is a useful overfitting signal. They are not the basis
for choosing the model - out-of-time AUC is.

**A single headline number for the book.** The limit tables in section 10 are
deliberately a curve, because the answer depends on an appetite the business
sets, not on the model.

### One figure worth carrying into that decision

At `TICKET_TOMAN = 500,000` across the full screened population of 6,879,803,
the book is about **3,440 bn Toman**. The target discussed was **15,000 bn over
6 months**. This screen cannot reach that at this ticket size - closing the gap
needs a larger line per subscriber or a looser screen, and which of those to
accept is a business decision, not a modelling one.
""")

# ===========================================================================
def build():
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if t == MD
                else nbf.v4.new_code_cell(s) for t, s in C]
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    })
    return nb

if __name__ == "__main__":
    nb = build()
    nbf.validate(nb)                       # raises if the document is malformed

    import ast
    for i, (t, s) in enumerate(C):
        if t == CODE:
            try:
                ast.parse(s)
            except SyntaxError as e:
                print(f"SYNTAX ERROR in code cell {i}: {e}")
                sys.exit(1)

    out = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "notebook", "train_model.ipynb"))
    with io.open(out, "w", encoding="utf-8") as f:
        nbf.write(nb, f)

    nmd = sum(1 for t, _ in C if t == MD)
    ncode = sum(1 for t, _ in C if t == CODE)
    print(f"wrote {out}")
    print(f"  {len(C)} cells: {nmd} markdown, {ncode} code")
    print("  nbformat validation passed, every code cell parses")

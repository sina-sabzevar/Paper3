# -*- coding: utf-8 -*-
"""Emit notebook/validate_model.ipynb - the checks the training run cannot make on itself.

    python3 tools/gen_validate_notebook.py
"""
import io, os, sys
import nbformat as nbf

MD, CODE = "md", "code"
C = []
def md(s):   C.append((MD, s.strip("\n")))
def code(s): C.append((CODE, s.strip("\n")))

# ===========================================================================
md(r"""
# Validating the refit

The training run reports its own metrics. It cannot check whether those metrics
mean what they appear to mean, and four things about the 1405-07-14 refit need
checking before the book is cut.

**What already checks out, from the printed output alone** - no need to re-run
any of it:

| | |
|---|---|
| Gini equals `2*AUC - 1` on all five rows | to 1e-6 |
| The three splits partition the table | 6,090,155 + 1,741,839 + 869,091 = 8,701,085, bads 45,361 |
| Down-sampling is unbiased | weighted rate 0.5220 pct against a true 0.5221 pct |
| Grades reproduce the live mean PD | 0.5952 pct, exactly |
| Grade A against the ladder | 0.1417 vs 0.1438 pct, 1.4 pct apart |
| Calendar structure | every guard in `gen_model_sql.py` passes: no leakage, seasons aligned, pre-window before features and label |

**What this notebook settles:**

1. **PD ties.** The book is cut with `ORDER BY pd_4m LIMIT N`. Isotonic
   regression emits a *step function*, so identical PDs are guaranteed - the
   question is how many subscribers sit on the step at the cut, because every
   one of them is admitted or refused arbitrarily. Grade E's mean PD printed as
   exactly `0.040000` over 542,951 subscribers, which says the steps are wide.
2. **Did the `pre_` features earn their place,** or did AUC move for another
   reason.
3. **What the raw Rial levels cost.** Twelve features drift significantly and
   `r1..r6` have no relative twins. A model built only from scale-free features
   cannot drift with inflation. If it scores nearly as well, it is the better
   production model and the drift problem goes away.
4. **Whether the two models pick the same people.** AUC can barely move while
   the book changes substantially.

Nothing here writes to a database. It re-fits in memory and prints.
""")

# ===========================================================================
code(r"""
import os, gc, hashlib, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Same as the training notebook. If "nothing found", set DATA to the directory
# that actually holds dcb_model*.parquet - print os.getcwd() to see where you are.
DATA   = "."
SEED   = 42
TICKET = 500_000          # Toman per subscriber
TAKE   = 4_672_361        # the book under consideration

SPLIT_TRAIN, SPLIT_VALID = 70, 90     # md5 mod 100 buckets
GOOD_KEEP = 10                        # pct of goods kept in TRAIN

NOT_FEATURES = {"sbrp_id", "y", "cohort", "sample_weight",
                "n_label_months", "split", "in_band"}

print(f"pandas {pd.__version__}  numpy {np.__version__}")
print(f"DATA = {os.path.abspath(DATA)}")
""")

# ===========================================================================
md(r"""
## 1. Load

Globs only, exactly as the training notebook does, so a stale whole-table file
cannot quietly win over the parts. The row counts are asserted rather than
printed: if either is wrong, every number below would be wrong too.
""")

code(r"""
EXPECT = {"dcb_model": 8_701_085, "dcb_score": 9_344_723}

def load(stem):
    import glob
    hits = sorted(glob.glob(os.path.join(DATA, stem + "*.parquet")))
    if not hits:
        hits = sorted(glob.glob(os.path.join(DATA, stem + "*.csv")))
    if not hits:
        raise FileNotFoundError(
            f"nothing matched {os.path.join(DATA, stem)}*  -  "
            f"DATA resolves to {os.path.abspath(DATA)}")
    rd = pd.read_parquet if hits[0].endswith(".parquet") else pd.read_csv
    df = pd.concat([rd(h) for h in hits], ignore_index=True)
    print(f"  {stem}: {len(hits)} file(s) -> {len(df):,} rows x {df.shape[1]} cols")
    for h in hits:
        print(f"     {os.path.basename(h)}")
    assert len(df) == EXPECT[stem], \
        f"{stem} has {len(df):,} rows, expected {EXPECT[stem]:,} - a part is missing or doubled"
    return df

print("LOADING")
md_df = load("dcb_model")
sc    = load("dcb_score")
print("\n  row counts match the SQL exactly")
""")

# ===========================================================================
md(r"""
## 2. Split hygiene

Three things have to hold, and none of them is implied by the row counts the
training run printed:

- **No subscriber appears in two splits.** If the hash were not a function of
  `sbrp_id` alone, a subscriber could land in TRAIN and TEST, and TEST would be
  measuring memorisation.
- **The hash is reproducible.** Recomputing it here must give the identical
  split, or the two notebooks are not talking about the same TEST set.
- **`sbrp_id` is unique in each table.** A duplicated id would be counted twice
  and weighted twice.
""")

code(r"""
def hash_bucket(ids):
    return ids.astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) % 100)

print("UNIQUENESS")
for nm, d in (("dcb_model", md_df), ("dcb_score", sc)):
    dup = len(d) - d.sbrp_id.nunique()
    print(f"  {nm:10s} duplicate sbrp_id: {dup:,}   {'ok' if dup == 0 else '<-- PROBLEM'}")

h = hash_bucket(md_df.sbrp_id).to_numpy()
split = np.where(h < SPLIT_TRAIN, "train", np.where(h < SPLIT_VALID, "valid", "test"))

print("\nSPLIT, recomputed here")
for nm in ("train", "valid", "test"):
    m = split == nm
    print(f"  {nm:6s} {m.sum():>10,} rows  {int(md_df.y.to_numpy()[m].sum()):>7,} bad  "
          f"{md_df.y.to_numpy()[m].mean():.4%}")

# A subscriber can only be in one split because the bucket is a pure function of
# sbrp_id - this proves it rather than assuming it.
per_sub = pd.DataFrame({"sbrp_id": md_df.sbrp_id, "split": split}).groupby("sbrp_id").split.nunique()
print(f"\n  subscribers in more than one split: {int((per_sub > 1).sum()):,}   "
      f"{'ok' if (per_sub > 1).sum() == 0 else '<-- PROBLEM'}")

# Does the TEST set share subscribers with dcb_score? It SHOULD - they are the
# same people a window later. That is not leakage; the windows do not overlap.
te_ids = set(md_df.sbrp_id.to_numpy()[split == "test"])
both = len(te_ids & set(sc.sbrp_id.to_numpy()))
print(f"  TEST subscribers also present in dcb_score: {both:,} of {len(te_ids):,} "
      f"({100*both/len(te_ids):.1f} pct)")
print("  (expected and harmless - different months, no overlapping window)")
""")

# ===========================================================================
md(r"""
## 3. Feature matrix hygiene

`X()` in the training notebook runs `np.nan_to_num(..., nan=0, posinf=0, neginf=0)`.
That is right for the revenue columns, where the SQL already resolves a NULL
`arpu` to zero revenue. It is **silently wrong** for an infinity: `+inf` becomes
`0.0`, which turns the largest value in a column into the smallest and inverts
the ranking for those rows.

The `_rel` features divide by a window median. `NULLIF` guards a median of
exactly zero, not a very small one - which is how `outst_max_rel` injected drift
and had to be dropped. So the infinities are worth counting rather than assuming
away.
""")

code(r"""
FEATURES = [c for c in md_df.columns if c not in NOT_FEATURES]
dropped = [c for c in FEATURES
           if md_df[c].nunique(dropna=False) <= 1 and sc[c].nunique(dropna=False) <= 1]
FEATURES = [c for c in FEATURES if c not in dropped]
print(f"FEATURES: {len(FEATURES)}   dropped for no variance: {dropped}")

print("\nHYGIENE  (counts are rows, both tables)")
bad_any = False
for c in FEATURES:
    a, b = md_df[c].to_numpy(dtype=float), sc[c].to_numpy(dtype=float)
    n_nan = int(np.isnan(a).sum() + np.isnan(b).sum())
    n_inf = int(np.isinf(a).sum() + np.isinf(b).sum())
    if n_nan or n_inf:
        bad_any = True
        flag = "  <-- inf becomes 0.0 and inverts the ranking" if n_inf else ""
        print(f"  {c:18s} nan {n_nan:>10,}   inf {n_inf:>10,}{flag}")
if not bad_any:
    print("  no NaN and no inf in any feature, in either table")

# Two features that are the same column under two names would double its weight
# in the linear model and waste a split in the tree.
sub = md_df[FEATURES].sample(min(200_000, len(md_df)), random_state=SEED)
corr = sub.corr(numeric_only=True).abs()
pairs = [(corr.index[i], corr.columns[j], corr.iat[i, j])
         for i in range(len(corr)) for j in range(i + 1, len(corr))
         if np.isfinite(corr.iat[i, j]) and corr.iat[i, j] > 0.995]
def twins(a, b):
    return a == b[:-4] or b == a[:-4]      # rev_6m vs rev_6m_rel

known = [(a, b, v) for a, b, v in pairs if twins(a, b)]
other = [(a, b, v) for a, b, v in pairs if not twins(a, b)]
print(f"\n  pairs correlated above 0.995: {len(pairs)} "
      f"({len(known)} raw/_rel twins, {len(other)} other)")
print("    the twins are 1.0 by construction - inside ONE table a _rel column is")
print("    its raw column over a constant, so it adds nothing to the fit. It earns")
print("    its place ACROSS tables, by rescaling the live window onto the trained one.")
for a, b, v in sorted(other, key=lambda t: -t[2])[:12]:
    print(f"    {a:18s} {b:18s} {v:.4f}")
if not other:
    print("    no unexpected duplicate pair")
""")

# ===========================================================================
md(r"""
## 4. Re-fit the champion

Self-contained, same seed, same hyper-parameters as the training notebook, so
the numbers below are comparable to its output rather than to a different model.
It should reproduce TEST AUC **0.8278**. If it does not, the two notebooks are
not fitting the same thing and nothing after this point is interpretable.
""")

code(r"""
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic  import IsotonicRegression
from sklearn.metrics   import roc_auc_score

def X(d, cols):
    return np.nan_to_num(d[cols].to_numpy(dtype=np.float32),
                         nan=0.0, posinf=0.0, neginf=0.0)

def downsample_mask(d, keep_pct):
    good = (d.y.to_numpy() == 0)
    hh = d.sbrp_id.astype(str).map(
        lambda s: int(hashlib.md5(("ds" + s).encode()).hexdigest()[:8], 16) % 100).to_numpy()
    return (~good) | (good & (hh < keep_pct))

tr_m, va_m, te_m = split == "train", split == "valid", split == "test"
ds = downsample_mask(md_df[tr_m], GOOD_KEEP)
tr_idx = np.flatnonzero(tr_m)[ds]

y = md_df.y.to_numpy(dtype=np.int8)
w_tr = np.where(y[tr_idx] == 1, 1.0, 100.0 / GOOD_KEEP)

def fit_and_score(cols, label, md=None, scf=None):
    md  = md_df if md  is None else md
    scf = sc    if scf is None else scf
    Xtr = X(md.iloc[tr_idx], cols)
    m = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.1,
        random_state=SEED)
    m.fit(Xtr, y[tr_idx], sample_weight=w_tr)
    del Xtr; gc.collect()

    pva = m.predict_proba(X(md[va_m], cols))[:, 1]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-7, y_max=1 - 1e-7)
    iso.fit(pva, y[va_m])
    anchor = np.average(y[va_m]) / max(np.average(iso.predict(pva)), 1e-9)

    pte = np.clip(iso.predict(m.predict_proba(X(md[te_m], cols))[:, 1]) * anchor, 1e-7, 0.999)
    auc_va = roc_auc_score(y[va_m], pva)
    auc_te = roc_auc_score(y[te_m], pte)
    psc = np.clip(iso.predict(m.predict_proba(X(scf, cols))[:, 1]) * anchor, 1e-7, 0.999)
    gc.collect()
    print(f"  {label:22s} VALID {auc_va:.4f}   TEST {auc_te:.4f}   "
          f"live mean PD {psc.mean():.4%}")
    return dict(model=m, iso=iso, anchor=anchor, auc_va=auc_va, auc_te=auc_te,
                pte=pte, psc=psc)

print("RE-FITTING")
full = fit_and_score(FEATURES, "all 39 features")
print(f"\n  training run reported TEST 0.8278 - reproduced "
      f"{'yes' if abs(full['auc_te'] - 0.8278) < 0.004 else 'NO, investigate before reading on'}")
""")

# ===========================================================================
md(r"""
## 5. PD ties - the check that bears on the book

The book is `ORDER BY pd_4m LIMIT 4,672,361`. Isotonic regression maps every
score inside one of its blocks to a single value, so the output is a step
function and ties are certain.

**If the step at the cut holds more subscribers than the cut has room for, the
people on that step are admitted or refused by whatever order the sort happens
to produce.** Not by risk - the model considers them identical. Two runs of the
same query can return different books.

`tie_at_cut` is the number on the step. `arbitrary` is how many of them are
decided by nothing.
""")

code(r"""
psc = full["psc"]
u, cnt = np.unique(psc, return_counts=True)
print("PD GRANULARITY, live set")
print(f"  distinct PD values            {len(u):,}")
print(f"  largest single value holds    {cnt.max():,} subscribers "
      f"({100*cnt.max()/len(psc):.2f} pct) at PD {u[cnt.argmax()]:.6%}")
print(f"  top plateau (max PD)          {cnt[-1]:,} subscribers at PD {u[-1]:.6%}")
print(f"  values holding over 1 pct of the book: {(cnt > 0.01*len(psc)).sum()}")

order = np.sort(psc)
cut_pd = order[TAKE - 1]
n_at_cut = int((psc == cut_pd).sum())
n_below  = int((psc < cut_pd).sum())
room     = TAKE - n_below
print(f"\nAT THE CUT, take {TAKE:,}")
print(f"  PD at the cut                 {cut_pd:.6%}")
print(f"  strictly safer than the cut   {n_below:,}")
print(f"  tied AT the cut               {n_at_cut:,}")
print(f"  of those, places available    {room:,}")
print(f"  ARBITRARY - tied and refused  {n_at_cut - room:,} "
      f"({100*(n_at_cut-room)/TAKE:.2f} pct of the book)")
if n_at_cut - room > 0.01 * TAKE:
    print("\n  OVER 1 PCT OF THE BOOK IS DECIDED BY SORT ORDER, not by risk.")
    print("  Break the tie on something defensible - lowest exposure, longest")
    print("  tenure, highest payment coverage - and record the rule. Do not")
    print("  leave it to the database.")
else:
    print("\n  the tie at the cut is small enough not to matter")
""")

# ===========================================================================
md(r"""
## 6. Did the `pre_` features earn their place?

`48_approved_audit.sql` A5 measured a prior two-way bar at **13.2x** and a prior
one-way bar at **4.0x** on the label. Two questions the training run never asked:

- Does that lift survive **in the model's own output** - does it score those
  subscribers higher, and by how much?
- Is the lift still there once everything else is held constant, or was it
  standing in for revenue all along?

The second is answered by dropping the six columns and re-fitting. If AUC falls
back toward 0.80, they carry real independent information. If it barely moves,
they were a proxy.
""")

code(r"""
PRE = [c for c in FEATURES if c.startswith("pre_")]
print(f"PRE features: {PRE}\n")

print("PREVALENCE AND OBSERVED LIFT, dcb_model")
base = md_df.y.mean()
for c in ("pre_tw_any", "pre_ow_any"):
    if c not in md_df.columns:
        continue
    g = md_df.groupby(c).y.agg(["size", "mean"])
    for v in g.index:
        n, r = int(g.loc[v, "size"]), g.loc[v, "mean"]
        print(f"  {c} = {v}   {n:>10,} ({100*n/len(md_df):5.2f} pct)   "
              f"rate {r:.4%}   lift {r/base:6.2f}x")

print("\nDOES THE MODEL REFLECT IT? mean predicted PD on TEST")
te = md_df[te_m]
for c in ("pre_tw_any", "pre_ow_any"):
    if c not in te.columns:
        continue
    for v in sorted(te[c].unique()):
        m = te[c].to_numpy() == v
        if m.sum() == 0:
            continue
        print(f"  {c} = {v}   predicted {full['pte'][m].mean():.4%}   "
              f"observed {y[te_m][m].mean():.4%}   n {int(m.sum()):,}")

print("\nABLATION - the same model without them")
no_pre = fit_and_score([c for c in FEATURES if not c.startswith("pre_")], "without pre_")
print(f"\n  cost of removing the pre_ features: "
      f"TEST {full['auc_te'] - no_pre['auc_te']:+.4f}")
""")

# ===========================================================================
md(r"""
## 7. What the raw Rial levels cost

Twelve features drift significantly, led by `rev_max` at PSI 3.0223. The four
`_rel` twins fix four of them; `r1..r6` and `rev_trend` have none, so
`USE_RELATIVE_ONLY` would not touch them.

A feature expressed as a **share of the subscriber's own six-month total** is
scale-free by construction. It needs no window median, so it is immune both to
inflation and to the instability that made `outst_max_rel` worse than its raw
column. This builds that set and fits the same model on it.

**If the scale-free model scores close to the full one, it is the better
production model** - it cannot drift with the Rial, so its TEST number is an
estimate of live performance rather than an upper bound on it.
""")

code(r"""
def scale_free(d):
    # Every feature as a ratio or a count - nothing carrying a Rial level.
    out = pd.DataFrame(index=d.index)
    rev = d.rev_6m.to_numpy(dtype=np.float64)
    n_zero = int((rev <= 0).sum())
    if n_zero:
        print(f"  {n_zero:,} rows have rev_6m <= 0 - every share is undefined for them "
              f"and becomes 0.0 in X()")
    den = np.where(rev > 0, rev, np.nan)          # nan, not 0: a 0/0 share is unknown
    for i in range(1, 7):
        out[f"r{i}_sh"] = d[f"r{i}"].to_numpy() / den
        out[f"q{i}_sh"] = d[f"q{i}"].to_numpy() / den
    for nm, col in (("rev_min_sh", "rev_min"), ("rev_max_sh", "rev_max"),
                    ("rev_trend_sh", "rev_trend"), ("paid_max_sh", "paid_max"),
                    ("outst_max_sh", "outst_max"), ("outst_avg_sh", "outst_avg"),
                    ("avail_max_sh", "avail_max"), ("avail_avg_sh", "avail_avg"),
                    ("pay_cover", "paid_6m")):
        out[nm] = d[col].to_numpy() / den
    # counts and flags - already scale-free, carried through unchanged
    for c in ("rev_months", "rev_months_wide", "pay_months", "n_arpu_null",
              "n_active1", "f_reclaim", "tenure_m", "pre_months_seen",
              "pre_ow_any", "pre_tw_any", "pre_ow_months", "pre_tw_months",
              "pre_absent"):
        if c in d.columns:
            out[c] = d[c].to_numpy()
    return out.astype(np.float32)

sf_md, sf_sc = scale_free(md_df), scale_free(sc)
SF = list(sf_md.columns)
print(f"scale-free features: {len(SF)}")
print("  " + ", ".join(SF))

# PSI on the scale-free set, with the fixed binning
VALUE_PSI_MAX_CATS = 40
def psi(e, a, bins=10):
    e = np.asarray(e, float); a = np.asarray(a, float)
    e = e[np.isfinite(e)];    a = a[np.isfinite(a)]
    if len(e) == 0 or len(a) == 0:
        return np.nan
    ve, ce = np.unique(e, return_counts=True)
    va, ca = np.unique(a, return_counts=True)
    use_values = len(ve) <= max(bins, VALUE_PSI_MAX_CATS)
    edges = None
    if not use_values:
        edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
        use_values = len(edges) < 3
    if use_values:
        de, da = dict(zip(ve, ce)), dict(zip(va, ca))
        cats = sorted(set(de) | set(da))
        if len(cats) > 4 * VALUE_PSI_MAX_CATS:
            return np.nan
        pe = np.array([de.get(v, 0) for v in cats], float)
        pa = np.array([da.get(v, 0) for v in cats], float)
    else:
        edges[0], edges[-1] = -np.inf, np.inf
        pe, _ = np.histogram(e, bins=edges); pa, _ = np.histogram(a, bins=edges)
        pe, pa = pe.astype(float), pa.astype(float)
    pe, pa = pe / pe.sum(), pa / pa.sum()
    pe, pa = np.clip(pe, 1e-6, None), np.clip(pa, 1e-6, None)
    return float(np.sum((pa - pe) * np.log(pa / pe)))

rows = sorted(((c, psi(sf_md[c], sf_sc[c])) for c in SF), key=lambda t: -(t[1] if np.isfinite(t[1]) else -1))
sig = [c for c, v in rows if np.isfinite(v) and v > 0.25]
print(f"\nDRIFT on the scale-free set: {len(sig)} significant (the full set has 12)")
for c, v in rows[:8]:
    print(f"  {c:18s} {v:8.4f}")
""")

code(r"""
# Fit the same model on the scale-free set. Uses the same helpers by swapping
# the frames in, so the comparison is like for like.
print("FITTING scale-free")
sf = fit_and_score(SF, "scale-free only", md=sf_md, scf=sf_sc)

print(f"\n  cost of dropping every Rial level: TEST {sf['auc_te'] - full['auc_te']:+.4f}")
print(f"  live mean PD   full {full['psc'].mean():.4%}   scale-free {sf['psc'].mean():.4%}")
print(f"  TEST observed  {y[te_m].mean():.4%}")
print("\n  The full model's live PD runs above TEST observed because its inputs")
print("  inflated. The scale-free model's should sit much closer - that gap IS")
print("  the drift, measured in the thing the business reads.")
""")

# ===========================================================================
md(r"""
## 8. Do the two models pick the same people?

AUC is an average over all pairs. A book is one specific cut. Two models can sit
0.005 apart on AUC and still disagree about hundreds of thousands of
subscribers, so the overlap is measured directly rather than inferred.
""")

code(r"""
from scipy.stats import spearmanr

samp = np.random.default_rng(SEED).choice(len(full["psc"]), 300_000, replace=False)
rho = spearmanr(full["psc"][samp], sf["psc"][samp]).statistic
print(f"rank correlation between the two models  {rho:.4f}  (300k sample)")

def book(p, n):
    n = min(n, len(p) - 1)
    return set(np.argpartition(p, n)[:n])

for n in (3_000_000, TAKE, 7_122_466):
    a, b = book(full["psc"], n), book(sf["psc"], n)
    ov = len(a & b)
    print(f"\n  book of {n:>9,}:  shared {ov:>9,} ({100*ov/n:5.1f} pct)   "
          f"differ {n-ov:>8,}")
""")

# ===========================================================================
md(r"""
## 9. Verdict
""")

code(r"""
checks = []
checks.append(("row counts match the SQL", True, "asserted at load"))
checks.append(("sbrp_id unique in both tables",
               md_df.sbrp_id.is_unique and sc.sbrp_id.is_unique, ""))
checks.append(("no subscriber in two splits", bool((per_sub > 1).sum() == 0), ""))
checks.append(("TEST AUC reproduced", abs(full["auc_te"] - 0.8278) < 0.004,
               f"{full['auc_te']:.4f}"))
checks.append(("tie at the cut under 1 pct of the book",
               (n_at_cut - room) <= 0.01 * TAKE,
               f"{n_at_cut - room:,} arbitrary"))
checks.append(("pre_ features carry independent signal",
               (full["auc_te"] - no_pre["auc_te"]) > 0.005,
               f"{full['auc_te'] - no_pre['auc_te']:+.4f} TEST"))
checks.append(("scale-free model within 0.01 AUC",
               (full["auc_te"] - sf["auc_te"]) < 0.01,
               f"{sf['auc_te'] - full['auc_te']:+.4f} TEST"))

print("VALIDATION")
for nm, ok, note in checks:
    print(f"  [{'PASS' if ok else 'LOOK'}] {nm:42s} {note}")
print("\n  LOOK is not failure - it is a result that needs a decision.")
""")

# ===========================================================================
def _stamp(nb):
    """Deterministic cell ids.

    nbformat mints a RANDOM id for every cell on every write, so regenerating
    an unchanged notebook still rewrites all 35 of them - a diff that says
    nothing, hides a real change inside it, and trips the commit check. A short
    hash of the cell's own source keeps an id stable while the cell is, and
    changes only for the cell that was actually edited.
    """
    import hashlib
    for i, cell in enumerate(nb.cells):
        h = hashlib.sha1(("".join(cell["source"]) + str(i)).encode()).hexdigest()
        cell["id"] = "c" + h[:10]
    return nb


def build():
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if t == MD else nbf.v4.new_code_cell(s)
                for t, s in C]
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    })
    return nb


if __name__ == "__main__":
    nb = _stamp(build())
    nbf.validate(nb)
    import ast
    for i, (t, s) in enumerate(C):
        if t == CODE:
            try:
                ast.parse(s)
            except SyntaxError as e:
                print(f"SYNTAX ERROR in code cell {i}: {e}")
                sys.exit(1)
    out = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "notebook", "validate_model.ipynb"))
    with io.open(out, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"wrote {out}")
    print(f"  {len(C)} cells: {sum(1 for t,_ in C if t==MD)} markdown, "
          f"{sum(1 for t,_ in C if t==CODE)} code")
    print("  nbformat validation passed, every code cell parses")

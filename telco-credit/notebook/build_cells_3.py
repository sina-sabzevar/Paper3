# -*- coding: utf-8 -*-
"""Cells: WOE/IV, champion scorecard, challenger GBM, metrics."""
def add(md, co):
    md(r"""
## 5. WOE binning and Information Value

The champion is a **WOE logistic scorecard**, not because it scores best but
because a credit committee can read it, every point on the card is traceable to a
bin, and a regulator can be shown why a subscriber was declined. The GBM below
is the challenger; if it wins by a wide margin that is worth knowing, and if it
wins by a little the scorecard ships.

IV reading: below 0.02 is noise, 0.02–0.10 weak, 0.10–0.30 medium, above 0.30
strong. Anything above **0.80 is a leakage warning**, not a triumph.
""")

    co(r"""
def woe_bins(x, y, n_bins=10, min_rate=0.01):
    x = pd.Series(x).astype(float)
    finite = x.replace([np.inf, -np.inf], np.nan)
    try:
        q = pd.qcut(finite, n_bins, duplicates="drop")
    except Exception:
        q = pd.cut(finite, 5, duplicates="drop")
    q = q.cat.add_categories(["__NA__"]).fillna("__NA__")
    g = pd.DataFrame({"b": q, "y": y}).groupby("b", observed=True)["y"].agg(["count","sum"])
    g["bad"], g["good"] = g["sum"], g["count"] - g["sum"]
    tb, tg = max(g.bad.sum(), 1), max(g.good.sum(), 1)
    g["bad_r"]  = (g.bad  + 0.5) / tb
    g["good_r"] = (g.good + 0.5) / tg
    g["woe"] = np.log(g.good_r / g.bad_r)
    g["iv"]  = (g.good_r - g.bad_r) * g.woe
    return g

IV, WOE_MAP = {}, {}
for c in FEATURES:
    g = woe_bins(train_raw.loc[~is_val, c], ytr)
    IV[c] = float(g.iv.sum()); WOE_MAP[c] = g
iv = pd.Series(IV).sort_values(ascending=False)
print("top 20 by Information Value\n")
print(iv.head(20).to_string(float_format=lambda v: f"{v:7.4f}"))
flag = iv[iv > 0.80]
print(f"\nIV above 0.80 (leakage warning): {list(flag.index) if len(flag) else 'none'}")
""")

    co(r"""
def apply_woe(df, cols):
    out = pd.DataFrame(index=df.index)
    for c in cols:
        g = WOE_MAP[c]
        edges = [b for b in g.index if b != "__NA__"]
        if not edges:
            out[c] = 0.0; continue
        cuts = [iv_.left for iv_ in edges] + [edges[-1].right]
        cat = pd.cut(pd.Series(df[c]).astype(float).replace([np.inf,-np.inf], np.nan),
                     bins=pd.IntervalIndex(edges))
        m = {b: g.loc[b, "woe"] for b in edges}
        vals = cat.map(m).astype(float)
        na_w = g.loc["__NA__", "woe"] if "__NA__" in g.index else 0.0
        out[c] = vals.fillna(na_w)
    return out

SEL = [c for c in iv.index if iv[c] >= 0.02][:40]
print(f"{len(SEL)} features with IV >= 0.02 enter the scorecard")
Wtr, Wva = apply_woe(Xtr, SEL), apply_woe(Xva, SEL)
print(f"WOE matrices: {Wtr.shape}  {Wva.shape}   nulls: {int(Wtr.isna().sum().sum())}")
""")

    md(r"""
## 6. Champion — WOE logistic scorecard
""")

    co(r"""
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss, roc_curve
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

champ = make_pipeline(
    SimpleImputer(strategy="median"), StandardScaler(),
    LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))
champ.fit(Wtr, ytr)
p_tr_c = champ.predict_proba(Wtr)[:, 1]
p_va_c = champ.predict_proba(Wva)[:, 1]
print(f"champion  train AUC {roc_auc_score(ytr, p_tr_c):.4f}   "
      f"valid AUC {roc_auc_score(yva, p_va_c):.4f}")
""")

    md(r"""
## 7. Challenger — gradient boosting

`HistGradientBoostingClassifier`, which is what is installed here; LightGBM or
XGBoost drop in at this cell with no other change.

**Regularised on purpose.** The depth and leaf limits are not timidity — an
unconstrained GBM on this many rows will memorise and hand back a train AUC near
0.99 that collapses out of sample. The train/valid gap printed below is the
number that tells you whether the constraint was enough.
""")

    co(r"""
chal = HistGradientBoostingClassifier(
    max_iter=400, learning_rate=0.06, max_depth=5, max_leaf_nodes=31,
    min_samples_leaf=200, l2_regularization=1.0,
    early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
    class_weight="balanced", random_state=42)
chal.fit(Xtr, ytr)
p_tr_g = chal.predict_proba(Xtr)[:, 1]
p_va_g = chal.predict_proba(Xva)[:, 1]
print(f"challenger train AUC {roc_auc_score(ytr, p_tr_g):.4f}   "
      f"valid AUC {roc_auc_score(yva, p_va_g):.4f}")
print(f"iterations used: {chal.n_iter_}")
""")

    md(r"""
## 8. The metrics that decide it

`gap` is train AUC minus valid AUC. A large gap means the model memorised, and
no amount of train AUC compensates.
""")

    co(r"""
def ks_stat(y_true, p):
    fpr, tpr, _ = roc_curve(y_true, p)
    return float(np.max(tpr - fpr))

def report(name, ytr_, ptr_, yva_, pva_):
    a_tr, a_va = roc_auc_score(ytr_, ptr_), roc_auc_score(yva_, pva_)
    return dict(model=name,
                auc_train=a_tr, auc_valid=a_va, gap=a_tr - a_va,
                gini_valid=2*a_va - 1, ks_valid=ks_stat(yva_, pva_),
                brier_valid=brier_score_loss(yva_, pva_))

RES = pd.DataFrame([
    report("WOE logistic (champion)", ytr, p_tr_c, yva, p_va_c),
    report("HistGradientBoosting (challenger)", ytr, p_tr_g, yva, p_va_g),
])
print(RES.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

best = RES.loc[RES.auc_valid.idxmax(), "model"]
print(f"\nselected on VALID auc: {best}")
P_TR, P_VA = ((p_tr_c, p_va_c) if best.startswith("WOE") else (p_tr_g, p_va_g))

print("\n--- the 0.90 question, answered on this run ---")
for _, r in RES.iterrows():
    v = r.auc_valid
    verdict = ("ABOVE 0.90 on held-out data and a 2 pct event rate - suspect "
               "leakage before celebrating" if v > 0.90 else
               "in the honest band for a behavioural telco scorecard" if v >= 0.70 else
               "below 0.70 - weak, needs better features or a longer window")
    print(f"  {r.model:<34} valid {v:.4f}   {verdict}")
    if r.gap > 0.05:
        print(f"      gap {r.gap:.3f} - memorising; tighten regularisation")
""")

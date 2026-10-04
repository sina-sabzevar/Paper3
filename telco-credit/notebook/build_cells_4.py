# -*- coding: utf-8 -*-
"""Cells: calibration, score scaling, PSI, limit engine, economics."""
def add(md, co):
    md(r"""
## 9. Calibration and PD anchoring

`class_weight="balanced"` deliberately distorts the probabilities — it has to, to
learn from a 2 pct event rate. So the raw output ranks well but is not a PD.
Isotonic recalibration on held-out data restores the level, and the PD is then
anchored so the portfolio mean equals the observed bad rate.

Ranking is what the model learned. The level is what the limit engine spends.
""")

    co(r"""
from sklearn.isotonic import IsotonicRegression

# The calibrator must be FITTED and JUDGED on different rows. Fitting isotonic
# on the validation set and then reading its calibration off the same rows gives
# ratio = 1.0000 in every decile by construction - a perfect-looking plot that
# proves nothing. So the validation set splits again: half calibrates, half
# tests. The deciles below are therefore an honest read.
h2 = (h[is_val] < CFG["valid_frac"] / 2).values
Xcal, Xtst = Xva[h2], Xva[~h2]
ycal, ytst = yva[h2], yva[~h2]
p_cal, p_tst = P_VA[h2], P_VA[~h2]

iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-6, y_max=1-1e-6)
iso.fit(p_cal, ycal)
anchor = ycal.mean() / max(iso.predict(p_cal).mean(), 1e-9)
pd_tst = np.clip(iso.predict(p_tst) * anchor, 1e-6, 0.999)
print(f"calibration fitted on {len(ycal):,} rows, judged on {len(ytst):,} HELD-BACK rows")
print(f"mean PD {pd_tst.mean():.4%}  vs observed {ytst.mean():.4%}  "
      f"-> level error {abs(pd_tst.mean()-ytst.mean())/ytst.mean():.2%}")
print(f"Brier {brier_score_loss(ytst, pd_tst):.6f}   AUC {roc_auc_score(ytst, pd_tst):.4f}")

dec = pd.qcut(pd_tst, 10, labels=False, duplicates="drop")
cal = pd.DataFrame({"decile": dec, "pd": pd_tst, "y": ytst}).groupby("decile").agg(
    n=("y","size"), predicted=("pd","mean"), actual=("y","mean"))
cal["ratio"] = cal.actual / cal.predicted
print("\ncalibration by decile on the held-back half (ratio near 1.0 is the goal)")
print(cal.to_string(float_format=lambda v: f"{v:8.4f}"))
print(f"\nworst decile ratio: {cal.ratio.min():.3f} to {cal.ratio.max():.3f}")

# everything downstream uses the held-back half
pd_va, yva_eval = pd_tst, ytst
""")

    md(r"""
## 10. Score scaling

Points, not probabilities, because the business reads points. `base=600` at
`20:1` odds with `PDO=40` means every 40 points doubles the odds of being good.
""")

    co(r"""
F = CFG["score_pdo"] / np.log(2)
O = CFG["score_base"] - F * np.log(CFG["score_base_odds"])
def to_score(p):
    p = np.clip(p, 1e-6, 1-1e-6)
    return O + F * np.log((1 - p) / p)

# clip to a readable band: an unclipped log-odds score ran 29 to 1224, which is
# arithmetically fine and useless on a policy sheet.
sc_va = np.clip(to_score(pd_va), 300, 900)
bands = [-np.inf, 520, 560, 600, 640, 680, np.inf]
names = ["F", "E", "D", "C", "B", "A"]
grade = pd.cut(sc_va, bands, labels=names)
gt = pd.DataFrame({"grade": grade, "y": yva_eval, "pd": pd_va}).groupby(
        "grade", observed=False).agg(n=("y","size"), bad_rate=("y","mean"), mean_pd=("pd","mean"))
gt["share"] = gt.n / gt.n.sum()
print(f"score range {sc_va.min():.0f} to {sc_va.max():.0f}, median {np.median(sc_va):.0f}\n")
print(gt.to_string(float_format=lambda v: f"{v:9.4f}"))
print("\nmonotonic bad rate across grades (A best):",
      bool(np.all(np.diff(gt.bad_rate.dropna().values[::-1]) >= -1e-9)))
""")

    md(r"""
## 11. PSI — the check the revenue shock makes necessary

The shock sits at 140412 / 140501 / 140502, which is **between** the training
feature window (140407–140412) and the scoring feature window (140501–140506).
That is the worst place for it: the model learned on a pre-shock population and
will score a post-shock one.

PSI above **0.25** on a feature means its distribution moved enough that the
model is extrapolating. This is the only route by which the shock quietly costs
us accuracy, so it is measured rather than assumed.
""")

    co(r"""
def psi(a, b, bins=10):
    a, b = pd.Series(a).replace([np.inf,-np.inf], np.nan).dropna(), \
           pd.Series(b).replace([np.inf,-np.inf], np.nan).dropna()
    if a.empty or b.empty: return np.nan
    qs = np.unique(np.nanquantile(a, np.linspace(0, 1, bins + 1)))
    if len(qs) < 3: return 0.0
    qs[0], qs[-1] = -np.inf, np.inf
    pa = np.histogram(a, qs)[0] / len(a)
    pb = np.histogram(b, qs)[0] / len(b)
    pa, pb = np.clip(pa, 1e-6, None), np.clip(pb, 1e-6, None)
    return float(np.sum((pb - pa) * np.log(pb / pa)))

PSI = pd.Series({c: psi(train_raw[c], score_raw[c]) for c in FEATURES}
                ).sort_values(ascending=False)
print("worst 15 features by PSI (train features vs scoring features)\n")
print(PSI.head(15).to_string(float_format=lambda v: f"{v:7.4f}"))
sev = PSI[PSI > 0.25]
print(f"\nPSI > 0.25 (model extrapolating): {len(sev)} features")
if len(sev): print("  " + ", ".join(sev.index[:12]))
print(f"PSI > 0.10 (watch): {int((PSI > 0.10).sum())} features")
print("\nAny feature above 0.25 must be either dropped, re-binned, or the model")
print("retrained on a cohort closer to the scoring window before go-live.")
""")

    md(r"""
## 12. The limit engine

Four ceilings, and the loan is the smallest of them:

1. **affordability** — the instalment stays inside a share of proven capacity
2. **size against the bill** — a multiple of the typical monthly obligation
3. **SIM collateral** — a haircut on the operator's own `available_credit`
4. **grade cap** — a hard ceiling per risk band

Then the **payment-shock uplift**, which is the single most important correction
in this notebook: the model never saw a loan. Everyone in training carried only
their telco bill; a borrower carries that plus an instalment. So the PD the model
produces understates loan default, and the uplift

$$\mathrm{logit}(PD_{adj}) = \mathrm{logit}(PD) + \kappa \cdot \max(0,\ \mathrm{shock}-1)$$

penalises exactly the subscribers for whom the instalment is large relative to
what they have ever actually paid. Limit and PD depend on each other, so it is
solved by fixed-point iteration.
""")

    co(r"""
GRADE_POLICY = {   # grade: (alpha share of capacity, bill multiple, hard cap Toman)
    "A": (0.45, 1.70, 1_000_000), "B": (0.40, 1.55, 800_000),
    "C": (0.35, 1.40, 600_000),   "D": (0.30, 1.25, 450_000),
    "E": (0.25, 1.15, 400_000),   "F": (0.00, 0.00, 0),
}
def limits(pd_, score_, cap_rial, oblig_rial, avail_rial, n_iter=6):
    # pd.cut on an ndarray returns a Categorical, which has no .values - wrap it
    g = pd.Series(pd.cut(score_, bands, labels=names))
    alpha = g.map({k: v[0] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
    mult  = g.map({k: v[1] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
    hard  = g.map({k: v[2] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
    cap_t, obl_t, av_t = cap_rial/RIAL_PER_TOMAN, oblig_rial/RIAL_PER_TOMAN, avail_rial/RIAL_PER_TOMAN
    C = np.vstack([alpha * cap_t * CFG["n_instal"],        # affordability
                   mult * obl_t,                           # size vs the bill
                   CFG["collateral_mult"] * av_t,          # operator's own line
                   hard])                                  # grade cap
    C = np.where(np.isfinite(C), C, 0.0)
    L, which = C.min(0), C.argmin(0)
    p_adj = pd_.copy()
    for _ in range(n_iter):
        inst = L / CFG["n_instal"] * (1 + CFG["fee_rate_total"])
        shock = (inst + obl_t/6) / np.maximum(cap_t, 1.0)
        lg = np.log(np.clip(p_adj,1e-6,1-1e-6)/(1-np.clip(p_adj,1e-6,1-1e-6)))
        p_adj = 1/(1+np.exp(-(lg + CFG["shock_uplift_k"]*np.maximum(0, shock-1))))
        L = np.where(p_adj > CFG["pd_decline_at"], 0.0, L)
    L = np.where(L >= CFG["min_ticket"], np.floor(L/50_000)*50_000, 0.0)
    return L, p_adj, g, which

CEILINGS = ["affordability", "size vs bill", "operator credit line", "grade cap"]

va_rows = train_raw.loc[is_val]
cap   = va_rows["proven_capacity"].to_numpy()[~h2]
oblig = va_rows["obligation_6m"].to_numpy()[~h2]
avail = va_rows["available_credit"].to_numpy()[~h2]
L_va, pd_adj, g_va, bind = limits(pd_va, sc_va, cap, oblig, avail)

elig = L_va > 0
print(f"offered a limit: {elig.sum():,} of {len(L_va):,}  ({elig.mean():.1%})")
if elig.any():
    print(f"mean limit  {L_va[elig].mean():,.0f} Toman   median {np.median(L_va[elig]):,.0f}")
    print(f"PD before uplift {pd_va[elig].mean():.4%}   after {pd_adj[elig].mean():.4%}")
    print(f"uplift adds {(pd_adj[elig].mean()-pd_va[elig].mean())*1e4:.0f} bps to portfolio PD")
""")

    md(r"""
### Which ceiling actually binds

The most useful diagnostic in the notebook. Four ceilings apply and the loan is
the smallest; this says which one is smallest, and therefore what to change to
reach more subscribers. Raising a ceiling that never binds does nothing.
""")

    co(r"""
bt = pd.Series(bind).map(dict(enumerate(CEILINGS))).value_counts(normalize=True)
print("the binding ceiling, across all scored subscribers\n")
for k, v in bt.items(): print(f"  {k:<24} {v:6.1%}")
print("\nmedian value of each ceiling, Toman (the smallest is what you get)\n")
cap_t, obl_t, av_t = cap/RIAL_PER_TOMAN, oblig/RIAL_PER_TOMAN, avail/RIAL_PER_TOMAN
gser  = pd.Series(pd.cut(sc_va, bands, labels=names))
alpha = gser.map({k: v[0] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
mult  = gser.map({k: v[1] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
hard  = gser.map({k: v[2] for k, v in GRADE_POLICY.items()}).astype(float).to_numpy()
for nm, v in [("affordability", alpha*cap_t*CFG["n_instal"]),
              ("size vs bill", mult*obl_t),
              ("operator credit line", CFG["collateral_mult"]*av_t),
              ("grade cap", hard)]:
    print(f"  {nm:<24} {np.nanmedian(v):>12,.0f}")
print(f"\n  minimum ticket required   {CFG['min_ticket']:>12,.0f}")
print(f"  median proven capacity    {np.median(cap_t):>12,.0f}  per month")
print(f"  instalment at min ticket  {CFG['min_ticket']/CFG['n_instal']:>12,.0f}  per month")
print("\nIf the instalment exceeds median monthly capacity, the ticket is the")
print("problem, not the model - no cutoff can fix an unaffordable loan size.")
""")

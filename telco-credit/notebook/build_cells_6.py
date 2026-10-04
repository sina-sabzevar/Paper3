# -*- coding: utf-8 -*-
"""Cells: charts, scoring the live set, final handover table."""
def add(md, co):
    md(r"""
## 15. Charts

Four panels, one job each. Categorical hues are assigned in fixed order from the
validated palette and never cycled; a single-series panel carries no legend
because its title names it.
""")

    co(r"""
fig, ax = plt.subplots(2, 2, figsize=(13, 9))

# (1) ROC - identity, 2 series -> legend required
a = ax[0,0]
for (nm, pv, col) in [("WOE logistic", p_va_c, PAL[0]), ("Gradient boosting", p_va_g, PAL[1])]:
    fpr, tpr, _ = roc_curve(yva, pv)
    a.plot(fpr, tpr, color=col, label=f"{nm}  AUC {roc_auc_score(yva, pv):.3f}")  # full valid set
a.plot([0,1],[0,1], color=INK3, lw=1, ls=(0,(4,3)))
a.set_title("Held-out ROC", color=INK, fontsize=11, loc="left")
a.set_xlabel("false positive rate"); a.set_ylabel("true positive rate")
a.legend(frameon=False, fontsize=9, loc="lower right")

# (2) calibration - magnitude vs identity line, 1 series + reference
a = ax[0,1]
a.plot([cal.predicted.min(), cal.predicted.max()], [cal.predicted.min(), cal.predicted.max()],
       color=INK3, lw=1, ls=(0,(4,3)))
a.plot(cal.predicted, cal.actual, color=PAL[0], marker="o", ms=7)
a.set_title("Calibration by PD decile — predicted vs actual", color=INK, fontsize=11, loc="left")
a.set_xlabel("predicted PD"); a.set_ylabel("observed bad rate")

# (3) bad rate by grade - magnitude, single series, direct labels
a = ax[1,0]
gg = gt.dropna(subset=["bad_rate"])
a.bar(gg.index.astype(str), gg.bad_rate.values, color=PAL[0], width=0.62)
for xi, v in zip(range(len(gg)), gg.bad_rate.values):
    a.text(xi, v, f"{v:.2%}", ha="center", va="bottom", fontsize=9, color=INK2)
a.set_title("Observed bad rate by score grade", color=INK, fontsize=11, loc="left")
a.set_ylabel("bad rate"); a.margins(y=0.18); a.grid(axis="x", visible=False)

# (4) the frontier - loans against expected loss, the actual trade-off
a = ax[1,1]
f_ok  = POL[POL.budget_ok]
f_bad = POL[~POL.budget_ok]
a.scatter(f_bad.n_loans/1e6, f_bad.el_rate, s=26, color=INK3, alpha=.55,
          label="over budget")
a.scatter(f_ok.n_loans/1e6,  f_ok.el_rate,  s=34, color=PAL[0], label="within budget")
w = POL.set_index("policy").loc[WINNER]
a.scatter([w.n_loans/1e6], [w.el_rate], s=150, facecolor="none",
          edgecolor=PAL[1], lw=2.2, zorder=5, label=f"MCDM choice {WINNER}")
a.axvline(CFG["target_loans"]/1e6, color=PAL[3], lw=1.6, ls=(0,(5,3)))
a.text(CFG["target_loans"]/1e6, a.get_ylim()[1], " 3M target", color=PAL[3],
       fontsize=9, va="top", ha="left")
a.set_title("Policy frontier — loan count against expected loss", color=INK, fontsize=11, loc="left")
a.set_xlabel("loans (millions)"); a.set_ylabel("expected loss / exposure")
a.legend(frameon=False, fontsize=9, loc="upper left")

plt.tight_layout()
os.makedirs("outputs", exist_ok=True)
plt.savefig("outputs/model_report.png", dpi=140, bbox_inches="tight")
plt.show()
print("saved outputs/model_report.png")
""")

    md(r"""
## 16. Score the live set

Same features, same transforms, applied to `dcbs_scoreset` — subscribers as they
stand today, with no outcome to check against. This is where the model earns its
keep or does not.
""")

    co(r"""
Xsc = score_raw[FEATURES]
raw_sc = (champ.predict_proba(apply_woe(Xsc, SEL))[:, 1] if best.startswith("WOE")
          else chal.predict_proba(Xsc)[:, 1])
pd_sc = np.clip(iso.predict(raw_sc) * anchor, 1e-6, 0.999)
score_sc = to_score(pd_sc)
L_sc, pd_sc_adj, g_sc, bind_sc = limits(
    pd_sc, score_sc,
    score_raw["proven_capacity"].values,
    score_raw["obligation_6m"].values,
    score_raw["available_credit"].values)

w = POL.set_index("policy").loc[WINNER]
approve = (score_sc >= w.cutoff) & (L_sc > 0)
L_final = np.where(approve,
                   np.minimum(L_sc, w.stance * score_raw["proven_capacity"].values
                              / RIAL_PER_TOMAN * CFG["n_instal"]), 0.0)
L_final = np.where(L_final >= w.ticket, np.floor(L_final/50_000)*50_000, 0.0)
approve = L_final > 0

print(f"scored      {len(score_sc):,}")
print(f"approved    {approve.sum():,}  ({approve.mean():.1%})")
print(f"principal   {L_final.sum()/1e9:,.1f} billion Toman  "
      f"(budget {CFG['budget_toman']/1e9:,.0f})")
print(f"mean limit  {L_final[approve].mean():,.0f} Toman")
print(f"portfolio PD after shock uplift {pd_sc_adj[approve].mean():.4%}")
el = (pd_sc_adj[approve] * CFG['lgd'] * L_final[approve] * CFG['ead_factor']).sum()
print(f"expected loss {el/1e9:,.2f} billion Toman "
      f"= {el/max(L_final[approve].sum(),1):.3%} of principal")
print(f"\nscore-set rows vs train rows: {len(score_raw):,} vs {len(train_raw):,}")
print("the score set SHOULD be larger - it carries no complete-outcome filter.")
""")

    md(r"""
## 17. What the implementation team receives

Not the feature table. One row per approved subscriber, four columns they can
act on, plus a **random control cell**.

The control cell is not optional. The model has never seen a loan, so its
absolute PD is an extrapolation. A few percent of subscribers approved *without*
the scorecard is the only way to ever measure how much the scorecard was worth —
and once the first cohort has repaid, it is the only data that can retrain this
model on the actual product rather than on telco bills.
""")

    co(r"""
CONTROL_FRAC = 0.03
rng = np.random.default_rng(99)
ctrl = (rng.random(len(score_raw)) < CONTROL_FRAC) & (L_sc > 0)

hand = pd.DataFrame({
    "sbrp_id":      score_raw["sbrp_id"].values,
    "pd":           np.round(pd_sc_adj, 6),
    "score":        np.round(score_sc).astype(int),
    "grade":        g_sc.astype(str),
    "limit_toman":  L_final.astype(int),
    "cell":         np.where(ctrl & ~approve, "control",
                    np.where(approve, "scorecard", "declined")),
})
hand.loc[hand.cell == "control", "limit_toman"] = CFG["min_ticket"]
deliver = hand[hand.limit_toman > 0].copy()
os.makedirs("outputs", exist_ok=True)
deliver.to_csv("outputs/handover_credit_offers.csv", index=False)

print(deliver.head(10).to_string(index=False))
print(f"\nrows delivered {len(deliver):,}")
print(deliver.cell.value_counts().to_string())
print(f"\ntotal committed {deliver.limit_toman.sum()/1e9:,.1f} billion Toman")
print("written to outputs/handover_credit_offers.csv")
""")

    md(r"""
## 18. What this notebook does not know

Stated plainly, because these are the things that decide whether the launch works
and none of them is in the data:

1. **No loan has ever been made.** The label is default on a *telco bill*. The
   payment-shock uplift is a correction, not a measurement, and `κ = 0.55` is an
   assumption. The control cell replaces it with a fact after one cohort.
2. **The held-out split is in-time, not out-of-time.** Cohort C2 (`T0=140412`,
   features clear of the revenue shock) is the real test and is one
   `recalendar.py --t0 1404 12 --out 7` away.
3. **The shock sits between training and scoring features.** Section 11 measures
   it; any feature above PSI 0.25 must be dropped, re-binned, or the model
   retrained closer to the scoring window.
4. **The budget is binding, not the risk.** 1.2 trillion Toman over 3,000,000
   loans is exactly 400,000 each, which leaves the limit engine no room to
   differentiate. Either the budget rises, the count falls, or the minimum ticket
   does.
5. **`bllg_pmnt_stat_id = 2` is still unverified** — it is in the extraction's
   WHERE clause and inherited from the original pipeline. If it is wrong,
   `paid_total_6m` is incomplete and every capacity-based limit here is understated.
""")

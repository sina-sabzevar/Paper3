# -*- coding: utf-8 -*-
"""Cells: policy grid, unit economics, MCDM, final output, charts."""
def add(md, co):
    md(r"""
## 13. The policy grid

One model, many possible policies. A policy is a **score cutoff** crossed with an
**affordability stance** crossed with a **minimum ticket**. Each produces a
different book: more loans or less loss, never both. MCDM below picks one, but
first every candidate is priced.

Counts are scaled from the validation sample to the full eligible population, so
the loan numbers are comparable with the 3,000,000 target.
""")

    co(r"""
POP_SCALE = len(train_raw) / len(pd_va)   # eval slice -> full population

def price(cut, stance, ticket):
    keep = (sc_va >= cut) & elig
    if keep.sum() < 50: return None
    cap_t = cap[keep] / RIAL_PER_TOMAN
    L = np.minimum(L_va[keep], stance * cap_t * CFG["n_instal"])
    L = np.where(L >= ticket, np.floor(L/50_000)*50_000, 0.0)
    ok = L > 0
    if ok.sum() < 50: return None
    L, p = L[ok], pd_adj[keep][ok]
    n_loans   = ok.sum() * POP_SCALE
    exposure  = (L * CFG["ead_factor"]).sum() * POP_SCALE
    principal = L.sum() * POP_SCALE
    el        = (p * CFG["lgd"] * L * CFG["ead_factor"]).sum() * POP_SCALE
    fee       = (L * CFG["fee_rate_total"]).sum() * POP_SCALE
    telco     = (L * CFG["incremental_rev_share"]
                   * CFG["telco_gross_margin"]).sum() * POP_SCALE
    funding   = exposure * CFG["cost_of_funds"] * (CFG["n_instal"]/12)
    opex      = n_loans * CFG["opex_per_loan"]
    profit    = fee + telco - el - funding - opex
    budget_ok = principal <= CFG["budget_toman"]
    return dict(cutoff=cut, stance=stance, ticket=ticket,
                n_loans=n_loans, principal=principal, mean_limit=L.mean(),
                pd_mean=p.mean(), el=el, el_rate=el/max(exposure,1),
                fee=fee, telco_margin=telco, profit=profit,
                roa=profit/max(principal,1), budget_ok=budget_ok,
                hits_target=n_loans >= CFG["target_loans"])

# the stance range deliberately reaches past prudence: at a median capacity near
# 83,000 Toman a month, a 100,000 instalment is MORE than the whole monthly
# capacity of the median subscriber, so a 400,000 ticket is unreachable at any
# prudent stance. The grid spans that boundary so the trade-off is visible
# instead of the result just coming back empty.
grid = [price(c, s, t)
        for c in [0, 500, 520, 540, 560, 580, 600, 620]
        for s in [0.25, 0.30, 0.40, 0.50, 0.70, 1.00]
        for t in [CFG["min_ticket"], 300_000, 200_000, 150_000]]
POL = pd.DataFrame([g for g in grid if g]).reset_index(drop=True)
POL["policy"] = ["P" + str(i+1).zfill(2) for i in range(len(POL))]
print(f"{len(POL)} priced policies\n")
show = ["policy","cutoff","stance","ticket","n_loans","principal","pd_mean","el_rate","profit","budget_ok","hits_target"]
print(POL[show].head(12).to_string(index=False, float_format=lambda v: f"{v:,.4g}"))
feasible = POL[POL.budget_ok & POL.hits_target]
print(f"\nwithin budget AND hitting 3M loans: {len(feasible)} of {len(POL)}")
""")

    md(r"""
### Break-even ticket — why the small-ticket policies all lose money

Every policy in the grid below a certain ticket shows negative profit, and it is
not the risk. `opex_per_loan` is a **fixed** cost per loan while the fee is a
**percentage** of the ticket, so there is a ticket size below which the fee
cannot even cover the cost of booking the loan — before a single default.
""")

    co(r"""
fee_r   = CFG["fee_rate_total"]
telco_r = CFG["incremental_rev_share"] * CFG["telco_gross_margin"]
fund_r  = CFG["cost_of_funds"] * (CFG["n_instal"]/12) * CFG["ead_factor"]
pd_port = float(pd_adj[elig].mean()) if elig.any() else 0.02
risk_r  = pd_port * CFG["lgd"] * CFG["ead_factor"]

print("per Toman lent, as a share of the ticket\n")
for nm, v in [("fee income", fee_r), ("incremental telco margin", telco_r)]:
    print(f"  + {nm:<26} {v:>7.2%}")
for nm, v in [("funding cost", fund_r), (f"risk cost at PD {pd_port:.2%}", risk_r)]:
    print(f"  - {nm:<26} {v:>7.2%}")
margin = fee_r + telco_r - fund_r - risk_r
print(f"  {'':<28} {'-'*7}")
print(f"  = margin before opex        {margin:>7.2%}\n")

print(f"ON FEE INCOME ALONE the margin is {fee_r - fund_r - risk_r:+.2%} - the product")
print("loses money by construction, because 4 pct over four months is about")
print(f"{fee_r*12/CFG['n_instal']:.0%} annualised against a {CFG['cost_of_funds']:.0%} cost of funds.")
print("The incremental telco margin is what makes it work, and it is the larger")
print("line by far. Any business case built on the fee alone will fail.\n")

if margin > 0:
    print(f"break-even ticket           {CFG['opex_per_loan']/margin:>12,.0f} Toman")
else:
    print("NO ticket breaks even at these assumptions - the margin is negative")
print(f"break-even on opex alone    {CFG['opex_per_loan']/(fee_r+telco_r):>12,.0f} Toman")
print(f"stated minimum ticket       {CFG['min_ticket']:>12,.0f} Toman")
print("\nThe 400,000 minimum is close to where a 4 pct fee alone covers a fixed")
print(f"15,000 Toman booking cost ({CFG['opex_per_loan']/fee_r:,.0f} Toman), which is probably where")
print("the number came from. Below it the loan cannot pay for its own booking.")
print("\nSENSITIVITY: incremental_rev_share is an ASSUMPTION, not a measurement.")
for sh in [0.0, 0.15, 0.35, 0.50]:
    m = fee_r + sh*CFG["telco_gross_margin"] - fund_r - risk_r
    be = CFG["opex_per_loan"]/m if m > 0 else float("inf")
    print(f"  share {sh:>5.0%} -> margin {m:>+7.2%}  break-even ticket "
          + (f"{be:>10,.0f}" if np.isfinite(be) else "  never"))
print("\nIf incremental spend is below about 15 pct, nothing works. Measuring it")
print("on the first cohort matters more than any model refinement.")
""")

    md(r"""
## 14. MCDM

Four methods on the same decision matrix, because agreeing is evidence and
disagreeing is a warning. Criteria:

| criterion | direction | why |
|---|---|---|
| `n_loans` | max | the 3M target |
| `profit` | max | it has to pay for itself |
| `el_rate` | **min** | expected loss on exposure |
| `pd_mean` | **min** | minimum risk, which is the stated goal |
| `roa` | max | efficiency of the budget |

Weights come two ways: **entropy** (data-driven — a criterion that barely varies
earns little weight) and **AHP** (judgement, with the consistency ratio checked;
above 0.10 the judgements are incoherent and must be redone). Both are reported
because a result that only survives one weighting is not a decision.
""")

    co(r"""
CRIT   = ["n_loans", "profit", "el_rate", "pd_mean", "roa"]
BENEF  = [True, True, False, False, True]
M = POL[CRIT].astype(float).values

def norm_vec(M):
    d = np.sqrt((M**2).sum(0)); d[d == 0] = 1; return M / d

def entropy_w(M):
    P = M / np.where(M.sum(0) == 0, 1, M.sum(0))
    P = np.clip(P, 1e-12, None)
    E = -(P * np.log(P)).sum(0) / np.log(len(M))
    d = 1 - E
    return d / d.sum()

# AHP: pairwise judgement on the Saaty scale
A = np.array([
    [1,   1/2, 1/3, 1/3, 1  ],   # n_loans
    [2,   1,   1/2, 1/2, 2  ],   # profit
    [3,   2,   1,   1,   3  ],   # el_rate
    [3,   2,   1,   1,   3  ],   # pd_mean
    [1,   1/2, 1/3, 1/3, 1  ],   # roa
], float)
ev, V = np.linalg.eig(A)
k = int(np.argmax(ev.real)); w_ahp = np.abs(V[:, k].real); w_ahp /= w_ahp.sum()
lmax = ev.real[k]; n = len(A)
CI = (lmax - n) / (n - 1); CR = CI / {5: 1.12}[n]
w_ent = entropy_w(M)
print(f"AHP consistency ratio {CR:.4f}  ->", "COHERENT" if CR < 0.10 else "INCOHERENT, redo")
print(pd.DataFrame({"criterion": CRIT, "entropy": w_ent, "AHP": w_ahp}
     ).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
""")

    co(r"""
def topsis(M, w, benefit):
    N = norm_vec(M) * w
    best  = np.where(benefit, N.max(0), N.min(0))
    worst = np.where(benefit, N.min(0), N.max(0))
    dp = np.sqrt(((N - best)**2).sum(1)); dn = np.sqrt(((N - worst)**2).sum(1))
    return dn / np.where(dp + dn == 0, 1, dp + dn)

def vikor(M, w, benefit, v=0.5):
    f_best  = np.where(benefit, M.max(0), M.min(0))
    f_worst = np.where(benefit, M.min(0), M.max(0))
    rng = np.where(f_best - f_worst == 0, 1, f_best - f_worst)
    d = w * (f_best - M) / rng
    S, R = d.sum(1), d.max(1)
    def nz(x): 
        r = x.max() - x.min(); return (x - x.min()) / (1 if r == 0 else r)
    Q = v * nz(S) + (1 - v) * nz(R)
    return 1 - Q          # higher is better, for comparability

def saw(M, w, benefit):
    Z = M.copy().astype(float)
    for j in range(Z.shape[1]):
        col = Z[:, j]
        Z[:, j] = col/col.max() if benefit[j] else (col.min()/np.where(col==0,1e-12,col))
    return (Z * w).sum(1)

SC = {}
for wname, w in [("entropy", w_ent), ("AHP", w_ahp)]:
    SC[f"TOPSIS_{wname}"] = topsis(M, w, BENEF)
    SC[f"VIKOR_{wname}"]  = vikor(M, w, BENEF)
    SC[f"SAW_{wname}"]    = saw(M, w, BENEF)
S = pd.DataFrame(SC, index=POL.policy)
R = S.rank(ascending=False)
R["mean_rank"] = R.mean(1)
out = POL.set_index("policy").join(R[["mean_rank"]]).sort_values("mean_rank")
print("rank agreement between methods (Spearman)\n")
print(S.corr(method="spearman").to_string(float_format=lambda v: f"{v:.3f}"))
print("\ntop 8 policies by mean rank across all six method-weight combinations\n")
cols = ["cutoff","stance","ticket","n_loans","pd_mean","el_rate","profit","budget_ok","hits_target","mean_rank"]
print(out[cols].head(8).to_string(float_format=lambda v: f"{v:,.4g}"))
""")

    md(r"""
### Sensitivity — does the winner survive perturbed weights?

A winner that only wins at one exact weight vector is an artefact. 2,000 Dirichlet
draws around the entropy weights; the figure to read is how often the top choice
stays on top.
""")

    co(r"""
rng = np.random.default_rng(7)
W = rng.dirichlet(np.maximum(w_ent, 1e-3) * 40, 2000)
wins = np.zeros(len(POL), int)
for w in W:
    wins[np.argmax(topsis(M, w, BENEF))] += 1
stab = pd.Series(wins, index=POL.policy).sort_values(ascending=False) / len(W)
print("share of 2,000 perturbed weightings each policy wins\n")
print(stab.head(6).to_string(float_format=lambda v: f"{v:.3%}"))
WINNER = stab.index[0]
print(f"\nmost robust policy: {WINNER}  ({stab.iloc[0]:.1%} of draws)")
print(POL.set_index("policy").loc[WINNER, cols[:-1]].to_string(float_format=lambda v: f"{v:,.4g}"))
""")

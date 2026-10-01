# -*- coding: utf-8 -*-
"""Lending frontier: how many loans, at what expected loss, under the budget.

Answers "what is the maximum we can lend and at what risk" as a surface over the
two things still unmeasured - the population bad rate and the model's Gini.
Replace POP_BAD and GINI with the measured values once 02_label_report.sql and a
first model run come back; everything else here is already fixed by the product.
"""
import numpy as np, matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from scipy.stats import norm
from scipy.optimize import brentq

# ----------------------------------------------------------------- constraints
BASE        = 10_000_000      # eligible subscribers
BUDGET      = 1_200e9         # Toman available to lend (floor)
MIN_TICKET  = 400_000         # smallest loan the business will issue
N_INST      = 4
FEE         = 0.04
LGD         = 0.55            # <- replace with 1 - recovery_365d from S3
EAD_FACTOR  = 0.70            # <- replace once real loan data exists

# unmeasured yet - the two axes of the surface
POP_BAD_GRID = [0.06, 0.08, 0.10, 0.15]
GINI_GRID    = [0.35, 0.45, 0.55, 0.65]

C = dict(s1="#2a78d6", s2="#eb6834", s3="#1baf7a", s4="#eda100", s7="#4a3aa7",
         critical="#d03b3b", surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9", axis="#c3c2b7")
mpl.rcParams.update({
    "figure.facecolor": C["surface"], "axes.facecolor": C["surface"],
    "savefig.facecolor": C["surface"], "figure.dpi": 110, "savefig.dpi": 150,
    "font.size": 10, "axes.edgecolor": C["axis"], "axes.linewidth": 0.8,
    "axes.labelcolor": C["ink2"], "axes.titlecolor": C["ink"],
    "axes.titlesize": 11.5, "axes.titleweight": "600", "axes.titlelocation": "left",
    "axes.titlepad": 10, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": C["muted"], "ytick.color": C["muted"],
    "xtick.labelcolor": C["ink2"], "ytick.labelcolor": C["ink2"],
    "grid.color": C["grid"], "grid.linewidth": 0.7, "legend.frameon": False,
    "lines.linewidth": 2.0})


def approved_bad_rate(pop_bad, gini, approval_rate):
    """Bi-normal score model: goods ~ N(0,1), bads ~ N(-d,1), AUC = Phi(d/sqrt2)."""
    d = np.sqrt(2) * norm.ppf((gini + 1) / 2)
    t = brentq(lambda t: (1 - pop_bad) * (1 - norm.cdf(t))
                       + pop_bad * (1 - norm.cdf(t + d)) - approval_rate, -12, 12)
    return pop_bad * (1 - norm.cdf(t + d)) / approval_rate


def loss_ratio(pop_bad, gini, approval_rate):
    """Expected loss as a share of money lent."""
    return approved_bad_rate(pop_bad, gini, approval_rate) * LGD * EAD_FACTOR


def max_loans(pop_bad, gini, loss_cap):
    """Most loans issuable while expected loss stays under the cap AND the budget
    still affords the minimum ticket."""
    budget_cap = BUDGET / MIN_TICKET                      # hard: cannot go deeper
    lo, hi = 1e-4, min(0.999, budget_cap / BASE)
    if loss_ratio(pop_bad, gini, lo) > loss_cap:
        return 0.0
    if loss_ratio(pop_bad, gini, hi) <= loss_cap:
        return hi * BASE
    return brentq(lambda q: loss_ratio(pop_bad, gini, q) - loss_cap, lo, hi) * BASE


# ------------------------------------------------------------------- the tables
print(f"Budget {BUDGET/1e9:,.0f}B Toman  |  minimum ticket {MIN_TICKET:,} "
      f"-> at most {BUDGET/MIN_TICKET/1e6:.1f}M loans, whatever the risk\n")

for cap in [0.01, 0.02, 0.03]:
    print(f"\nMaximum loans with expected loss <= {cap:.0%} of money lent  (millions)")
    print(f"{'pop bad rate':>13} |" + "".join(f"{f'Gini {g:.2f}':>11}" for g in GINI_GRID))
    print("-" * 13 + "-+" + "-" * 11 * len(GINI_GRID))
    for p in POP_BAD_GRID:
        row = ""
        for g in GINI_GRID:
            n = max_loans(p, g, cap) / 1e6
            flag = "+" if abs(n - BUDGET / MIN_TICKET / 1e6) < 1e-6 else " "
            row += f"{n:>9.2f}{flag} "
        print(f"{p:>12.0%}  |" + row)
print("\n  + = capped by the budget, not by risk: more money would buy more loans")

# -------------------------------------------------------------------- the chart
fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.6))

ax = axes[0]
q = np.linspace(0.02, min(0.999, BUDGET / MIN_TICKET / BASE), 120)
for g, col in zip(GINI_GRID, [C["s2"], C["s4"], C["s1"], C["s3"]]):
    ax.plot(q * BASE / 1e6, [loss_ratio(0.10, g, x) for x in q], color=col,
            label=f"Gini {g:.2f}")
ax.axvline(3.0, color=C["s7"], lw=1.6, ls=(0, (4, 3)))
ax.text(3.0, ax.get_ylim()[1] * 0.94, " target 3M", fontsize=9,
        color=C["s7"], fontweight="600")
ax.axhline(0.03, color=C["critical"], lw=1.3, ls=(0, (4, 3)))
ax.text(2.95, 0.0305, "3% loss ceiling", fontsize=8.5, color=C["critical"], ha="right")
ax.yaxis.set_major_formatter(PercentFormatter(1.0))
ax.set_xlabel("loans issued (millions)"); ax.set_ylabel("expected loss / money lent")
ax.set_title("Loss rises as you lend deeper  (population bad rate 10%)")
ax.yaxis.grid(True); ax.set_axisbelow(True); ax.legend(loc="upper left")

ax = axes[1]
xs = np.arange(len(GINI_GRID))
w = 0.26
for i, (cap, col) in enumerate(zip([0.01, 0.02, 0.03], [C["s1"], C["s3"], C["s4"]])):
    vals = [max_loans(0.10, g, cap) / 1e6 for g in GINI_GRID]
    ax.bar(xs + (i - 1) * w, vals, width=w - 0.02, color=col,
           edgecolor=C["surface"], linewidth=2, label=f"loss <= {cap:.0%}")
# the budget ceiling and the 3M target are the same number - that IS the finding
CEIL = BUDGET / MIN_TICKET / 1e6
ax.axhline(CEIL, color=C["critical"], lw=1.6, ls=(0, (4, 3)))
ax.text(len(GINI_GRID) - 0.52, CEIL + 0.04,
        f"target 3M = budget ceiling ({MIN_TICKET/1000:.0f}k minimum ticket)",
        fontsize=8.5, color=C["critical"], fontweight="600", ha="right")
ax.set_ylim(0, CEIL * 1.18)
ax.set_xticks(xs); ax.set_xticklabels([f"{g:.2f}" for g in GINI_GRID])
ax.set_xlabel("model Gini"); ax.set_ylabel("maximum loans (millions)")
ax.set_title("Risk binds only at low Gini - otherwise the budget does")
ax.yaxis.grid(True); ax.set_axisbelow(True); ax.legend(loc="upper left")

fig.tight_layout()
fig.savefig("outputs/11_lending_frontier.png", bbox_inches="tight")
print("\nchart -> outputs/11_lending_frontier.png")

# -*- coding: utf-8 -*-
"""Cells 1-10: contract, data, EDA, split."""
CELLS = []
def md(s): CELLS.append(("markdown", s.strip("\n")))
def co(s): CELLS.append(("code", s.strip("\n")))

md(r"""
# Telco micro-credit scorecard — DCB cohort C1

**What this notebook does, in order:** enforces the feature/label contract, trains
a champion scorecard and a challenger GBM, measures them honestly on held-out
data, turns scores into limits through a payment-shock-adjusted limit engine,
prices the book, then uses MCDM to pick one policy out of many on explicit
criteria — and ends with the table the implementation team receives.

## The one thing to read before running

The dataset carries **19 columns computed from the outcome window**, not just the
label. Several *are* the label under another name: `rule1_dpd60` is `y_strict`,
`escalated_twoway` is `y_severe`. Putting them in `X` yields a train AUC above
0.99 and a model worth nothing — and it does not look broken, it looks excellent.

So `X` is taken from a **positive list**, never by `df.drop(...)`, and a cell
below asserts that no outcome column reached the feature matrix. If that assert
fires, stop: every number after it is fiction.

**On the 0.90 AUC target.** On *training* data that is easy and means nothing —
an unregularised GBM on 9M rows reaches 0.99 by memorising. What decides whether
this product works is the **held-out** figure. For a behavioural credit scorecard
on telco data, an honest AUC lands around **0.72–0.85** (Gini 0.45–0.70). This
notebook reports train and held-out side by side and prints the gap, because the
gap is the finding. If held-out AUC comes back above 0.90 on a 2.2 pct event
rate, the first thing to suspect is leakage, not success.
""")

co(r"""
import warnings, hashlib, json, os
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib as mpl, matplotlib.pyplot as plt
from scipy import stats

RNG = np.random.default_rng(42)

# validated categorical palette (dataviz reference instance, light surface)
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
       "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURFACE, INK, INK2, INK3 = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8982"
mpl.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.edgecolor": INK3,
    "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e7e1", "grid.linewidth": 0.8,
    "font.size": 10, "figure.dpi": 110, "lines.linewidth": 2.0,
})
pd.set_option("display.width", 200, "display.max_columns", 80)
print("ready")
""")

md(r"""
## 1. Configuration

Every number the analysis depends on sits here. `LABEL` is the decision that
matters most: `y_severe` is the **operator's own definition of default** — the
line was fully cut off and stays cut until the debt is paid. It is not a
threshold I invented, which is why it is the default.
""")

co(r"""
CFG = dict(
    # ---- data
    train_csv = "data/dcb3_dataset_c1.csv",
    score_csv = "data/dcbs_scoreset.csv",
    n_synth    = 120_000,          # used only when the CSVs are absent

    # ---- label
    LABEL      = "y_severe",       # 2.22 pct - the operator's own default definition
    LABEL_ALT  = "y_strict",       # 1.22 pct - DPD >= 60, the persistence view

    # ---- split
    valid_frac = 0.30,             # hash split on sbrp_id, stratified check after

    # ---- product
    n_instal       = 4,
    min_ticket     = 400_000,      # Toman
    budget_toman   = 1_200e9,      # 1.2 trillion Toman
    target_loans   = 3_000_000,
    fee_rate_total = 0.04,         # 4 pct over the 4 instalments

    # ---- THE REVENUE LINE THAT DECIDES WHETHER THIS PRODUCT WORKS.
    # The fee alone cannot carry it: 4 pct over four months is about 12 pct
    # annualised against a 23 pct cost of funds, so on fee income the product
    # loses money by construction. What pays for it is INCREMENTAL TELCO
    # MARGIN - credit lets the subscriber buy services they would not otherwise
    # buy, and the operator keeps the gross margin on that. Leaving this out
    # (as a first version of this notebook did) makes a viable product look
    # loss-making.
    incremental_rev_share = 0.35,  # share of the limit that is NEW spend
    telco_gross_margin    = 0.55,  # margin on that spend

    # ---- risk
    lgd            = 0.55,
    ead_factor     = 0.70,
    opex_per_loan  = 15_000,       # Toman
    cost_of_funds  = 0.23,         # annual
    shock_uplift_k = 0.55,         # kappa in the payment-shock uplift

    # ---- limit engine dials. These are POLICY, not facts. available_credit is
    # the operator's own live credit line for the SIM - a limit it already
    # extends and already collects on - so a multiple of it is a defensible
    # anchor. An earlier version hardcoded 0.30, a number with no basis that
    # turned out to be the binding constraint on the whole book.
    collateral_mult = 1.00,
    pd_decline_at   = 0.35,        # refuse outright above this adjusted PD

    # ---- score scaling
    score_base = 600, score_base_odds = 20.0, score_pdo = 40,
)
RIAL_PER_TOMAN = 10
for k, v in CFG.items(): print(f"{k:>16} = {v}")
""")

md(r"""
## 2. The feature / label contract

Generated from the SQL, not typed. `FEATURES` is the positive list; `OUTCOME` is
everything the outcome window produced and may never be an input.
""")

co(r"""
FEATURES = ['age_on_net_months','med_bill','n_billed_months','ec_billed_6m','mc_billed_6m',
 'obligation_6m','midcycle_billed_share','med_obligation','max_bill','bill_std','max_dpd_6m',
 'max_debt_run_days','n_debt_spells_6m','total_debt_days_6m','n_late_months_6m',
 'n_mild_late_months_6m','n_ontime_months_6m','max_debt_amt_6m','unbill_peak_6m','unbill_avg_6m',
 'debtdays_m1','debtdays_m2','debtdays_m3','debtdays_m4','debtdays_m5','debtdays_m6',
 'oneway_days_6m','twoway_days_6m','n_ceiling_months_6m','n_barred_months_6m',
 'last_bar_month_idx','last_twoway_month_idx','avg_barred_days_per_spell',
 'billed_m1','billed_m2','billed_m3','billed_m4','billed_m5','billed_m6',
 'totrev_m1','totrev_m2','totrev_m3','totrev_m4','totrev_m5','totrev_m6',
 'data_gb_6m','data_gb_3m','voice_min_6m','voice_min_3m','call_cnt_6m','intl_cl_cnt_6m',
 'totrev_std_6m','data_gb_std_6m','billed_6m','midcycle_billed_share_6m','noncash_share_6m',
 'n_months_panel','paid_total_6m','n_payments_6m','avg_first_pay_day','paid_std_6m',
 'proven_capacity','median_monthly_paid','capacity_headroom','network_id',
 'initial_cred_lim_amt','temporary_cred_lim_amt','rfndable_dpos_amt','non_rfndable_dpos_amt',
 'advance_pmnt_amt','bill_outstanding_amt','unbill_outstanding_amt','available_credit',
 'ceiling_reconstructed','ceiling_utilisation','debt_scr','suspend_scr',
 'paid_to_obligation','arrears_paydown_6m']

OUTCOME = ['n_months_out','max_dpd_out','n_late_out','total_debt_days_out','oneway_days_out',
 'twoway_days_out','twoway_months_out','escalated_twoway','rule1_dpd60','rule2_late',
 'rule4_escalated','y_twoway_2m','y_twoway_any2m','y_severe','y_strict','y_v1','y_v2',
 'y_loose','indeterminate']

assert not (set(FEATURES) & set(OUTCOME)), "a column is in both lists"
print(f"{len(FEATURES)} features, {len(OUTCOME)} outcome columns, no overlap")
print("\nthe 11 that a naive drop of the y_ columns would leave behind:")
print("  " + ", ".join(c for c in OUTCOME if not c.startswith('y_') and c != 'indeterminate'))
""")

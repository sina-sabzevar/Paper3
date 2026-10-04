# generated from the notebook cells - run to prove they execute
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
def synth(n, with_label=True, seed=42):
    r = np.random.default_rng(seed)
    d = {}
    # latent creditworthiness drives both behaviour and the outcome
    z = r.normal(0, 1, n)
    cap = np.exp(r.normal(13.6, 0.95, n))                      # proven capacity, Rial
    d["proven_capacity"]     = cap
    d["median_monthly_paid"] = cap * r.uniform(0.45, 0.95, n)
    d["paid_total_6m"]       = d["median_monthly_paid"] * r.uniform(4.5, 6.5, n)
    d["paid_std_6m"]         = cap * r.uniform(0.05, 0.5, n)
    d["capacity_headroom"]   = cap / np.maximum(d["median_monthly_paid"], 1)
    d["n_payments_6m"]       = r.poisson(7, n) + 1
    d["avg_first_pay_day"]   = np.clip(r.normal(14, 6, n) - 2.2 * z, 1, 31)
    d["med_bill"]            = cap * r.uniform(0.3, 0.9, n)
    d["med_obligation"]      = d["med_bill"] * r.uniform(1.0, 1.5, n)
    d["ec_billed_6m"]        = d["med_bill"] * r.uniform(4.5, 6.5, n)
    d["mc_billed_6m"]        = d["ec_billed_6m"] * r.uniform(0.0, 0.5, n)
    d["obligation_6m"]       = d["ec_billed_6m"] + d["mc_billed_6m"]
    d["billed_6m"]           = d["obligation_6m"]
    d["midcycle_billed_share"]    = d["mc_billed_6m"] / d["obligation_6m"]
    d["midcycle_billed_share_6m"] = d["midcycle_billed_share"]
    d["max_bill"]            = d["med_bill"] * r.uniform(1.0, 3.0, n)
    d["bill_std"]            = d["med_bill"] * r.uniform(0.05, 0.6, n)
    d["n_billed_months"]     = r.integers(3, 7, n)
    d["paid_to_obligation"]  = d["paid_total_6m"] / np.maximum(d["obligation_6m"], 1)
    d["arrears_paydown_6m"]  = np.maximum(d["paid_total_6m"] - d["obligation_6m"], 0)
    # delinquency behaviour, correlated with z
    d["max_dpd_6m"]          = np.clip(r.gamma(1.4, 9, n) - 7 * z, 0, 180).round()
    d["max_debt_run_days"]   = d["max_dpd_6m"] + 15
    d["n_debt_spells_6m"]    = r.integers(0, 7, n)
    d["total_debt_days_6m"]  = np.clip(r.normal(70, 35, n) - 12 * z, 0, 186).round()
    d["n_late_months_6m"]    = np.clip(r.binomial(6, 1/(1+np.exp(1.1*z)), n), 0, 6)
    d["n_mild_late_months_6m"] = np.clip(6 - d["n_late_months_6m"] - r.integers(0,3,n), 0, 6)
    d["n_ontime_months_6m"]  = 6 - d["n_late_months_6m"]
    d["max_debt_amt_6m"]     = d["max_bill"] * r.uniform(1, 2.5, n)
    d["unbill_peak_6m"]      = d["max_bill"] * r.uniform(1, 3, n)
    d["unbill_avg_6m"]       = d["unbill_peak_6m"] * r.uniform(0.3, 0.8, n)
    for i in range(1, 7):
        d[f"debtdays_m{i}"] = np.clip(r.normal(12, 8, n) - 2*z, 0, 31).round()
        d[f"billed_m{i}"]   = d["med_bill"] * r.uniform(0.6, 1.5, n)
        d[f"totrev_m{i}"]   = d[f"billed_m{i}"] * r.uniform(1.0, 2.2, n)
    d["oneway_days_6m"]      = np.clip(r.gamma(1.1, 6, n) - 2*z, 0, 186).round()
    d["twoway_days_6m"]      = np.clip(r.gamma(0.25, 7, n) - 3*z, 0, 120).round()
    d["n_ceiling_months_6m"] = np.clip(r.binomial(6, 0.3, n), 0, 6)
    d["n_barred_months_6m"]  = np.clip(d["n_ceiling_months_6m"] + r.integers(0,2,n), 0, 6)
    d["last_bar_month_idx"]  = r.integers(16860, 16872, n)
    d["last_twoway_month_idx"] = d["last_bar_month_idx"] - r.integers(0, 6, n)
    d["avg_barred_days_per_spell"] = np.clip(r.normal(8, 6, n) - 2.5*z, 0, 60)
    d["data_gb_6m"]   = np.exp(r.normal(2.4, 1.0, n))
    d["data_gb_3m"]   = d["data_gb_6m"] * r.uniform(0.35, 0.65, n)
    d["voice_min_6m"] = np.exp(r.normal(5.6, 0.9, n))
    d["voice_min_3m"] = d["voice_min_6m"] * r.uniform(0.35, 0.65, n)
    d["call_cnt_6m"]  = r.poisson(380, n)
    d["intl_cl_cnt_6m"] = r.poisson(1.1, n)
    d["totrev_std_6m"]  = d["med_bill"] * r.uniform(0.1, 0.7, n)
    d["data_gb_std_6m"] = d["data_gb_6m"] * r.uniform(0.1, 0.6, n)
    d["noncash_share_6m"] = np.clip(r.beta(5, 3, n), 0, 1)
    d["n_months_panel"]  = 6
    d["age_on_net_months"] = r.integers(12, 190, n)
    d["network_id"] = r.integers(1, 4, n)
    d["available_credit"] = cap * r.uniform(0.8, 3.0, n)
    d["ceiling_reconstructed"] = d["available_credit"] * r.uniform(0.7, 1.3, n)
    d["unbill_outstanding_amt"] = d["available_credit"] * np.clip(r.beta(2,5,n), 0, 1)
    d["ceiling_utilisation"] = d["unbill_outstanding_amt"] / d["available_credit"]
    d["bill_outstanding_amt"] = d["med_bill"] * r.uniform(0, 2, n)
    for c in ["initial_cred_lim_amt","temporary_cred_lim_amt","rfndable_dpos_amt",
              "non_rfndable_dpos_amt","advance_pmnt_amt"]:
        d[c] = cap * r.uniform(0, 1.2, n)
    d["debt_scr"]    = np.clip(60 + 11*z + r.normal(0, 9, n), 0, 100)
    d["suspend_scr"] = np.clip(60 + 9*z  + r.normal(0, 11, n), 0, 100)
    df = pd.DataFrame(d)
    df["sbrp_id"] = np.arange(n) + (0 if with_label else 10_000_000)
    if with_label:
        # a realistic, NOT flattering, signal: held-out AUC should land ~0.78-0.84
        lin = -4.05 - 1.05*z + 0.004*d["max_dpd_6m"] + 0.16*d["n_late_months_6m"] \
              + 0.9*d["ceiling_utilisation"] - 0.35*np.log1p(d["proven_capacity"]/1e6)
        p = 1/(1+np.exp(-lin))
        df["y_severe"] = (r.random(n) < p).astype(int)
        df["y_strict"] = (df.y_severe & (r.random(n) < 0.55)).astype(int)
    return df

import glob

def load_parts(stem):
    # Reads one file or many parts. The export file splits the scoring set
    # because 11M rows x 78 columns is about 12 GB as CSV. Parts are
    # concatenated here, and parquet is preferred when present - the same data
    # at roughly a fifth the size, with numeric types preserved.
    base = stem.rsplit(".", 1)[0]
    pats = [f"{base}.parquet", f"{base}_part*.parquet",
            f"{stem}",         f"{base}_part*.csv"]
    files = []
    for pat in pats:
        f = sorted(glob.glob(pat))
        if f: files = f; break
    if not files:
        return None
    rd = pd.read_parquet if files[0].endswith(".parquet") else pd.read_csv
    frames = [rd(f) for f in files]
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    print(f"  {os.path.basename(base)}: {len(files)} file(s) -> {len(df):,} rows")
    if len(frames) > 1:
        # a split that lost or duplicated rows is invisible unless checked
        tot = sum(len(f_) for f_ in frames)
        assert tot == len(df), "concat lost rows"
        if "sbrp_id" in df:
            dup = len(df) - df.sbrp_id.nunique()
            print(f"    duplicate sbrp_id across parts: {dup:,}"
                  + ("   <-- PARTS OVERLAP, the split is wrong" if dup else "   OK"))
    if "part_no" in df: df = df.drop(columns=["part_no"])
    return df

print("loading")
train_raw = load_parts(CFG["train_csv"])
SOURCE = "real" if train_raw is not None else "synthetic"
if train_raw is None:
    train_raw = synth(CFG["n_synth"], True, 42)
score_raw = load_parts(CFG["score_csv"])
if score_raw is None:
    score_raw = synth(int(CFG["n_synth"]*1.15), False, 7)

# E2 in the export file down-samples the GOODS and ships a sample_weight.
# Ignoring it makes the model see a 17 pct event rate instead of 2.2 pct, and
# every PD comes out about eight times too high - ranking survives, the level
# does not, and the limit engine spends the level.
if "sample_weight" in train_raw.columns:
    SW = train_raw["sample_weight"].to_numpy(float)
    print(f"\nsample_weight present - the training set is DOWN-SAMPLED on goods")
    print(f"  raw event rate in the file {train_raw[CFG['LABEL']].mean():.2%}")
    print(f"  weighted back to           "
          f"{np.average(train_raw[CFG['LABEL']], weights=SW):.2%}")
else:
    SW = np.ones(len(train_raw))
    print("\nno sample_weight column - treating the training set as a full population")

print(f"source: {SOURCE}")
print(f"train {train_raw.shape}   score {score_raw.shape}")
missing = [c for c in FEATURES if c not in train_raw.columns]
print(f"features missing from train: {missing if missing else 'none'}")
FEATURES = [c for c in FEATURES if c in train_raw.columns and c in score_raw.columns]
print(f"usable features: {len(FEATURES)}")

# ---- CELL ----
leak = [c for c in FEATURES if c in OUTCOME]
assert not leak, f"OUTCOME COLUMN IN X: {leak}"
assert CFG["LABEL"] not in FEATURES
y = train_raw[CFG["LABEL"]].astype(int).values
print(f"X has {len(FEATURES)} columns, none from the outcome window  [PASS]")
print(f"label {CFG['LABEL']}: {y.mean():.4%}  ({y.sum():,} bads in {len(y):,})")
print(f"\nevent rate {y.mean():.2%} is a LOW-EVENT-RATE problem.")
print("handled with class weighting and calibration - never by loosening the label.")

# ---- CELL ----
h = train_raw["sbrp_id"].astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF)
is_val = (h < CFG["valid_frac"]).values
Xtr, Xva = train_raw.loc[~is_val, FEATURES], train_raw.loc[is_val, FEATURES]
ytr, yva = y[~is_val], y[is_val]
print(f"train {Xtr.shape[0]:,}  bad {ytr.mean():.4%}")
print(f"valid {Xva.shape[0]:,}  bad {yva.mean():.4%}")
print(f"stratification drift: {abs(ytr.mean()-yva.mean())/y.mean():.2%} of base rate")

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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
champ.fit(Wtr, ytr, logisticregression__sample_weight=SW[~is_val])
p_tr_c = champ.predict_proba(Wtr)[:, 1]
p_va_c = champ.predict_proba(Wva)[:, 1]
print(f"champion  train AUC {roc_auc_score(ytr, p_tr_c):.4f}   "
      f"valid AUC {roc_auc_score(yva, p_va_c):.4f}")

# ---- CELL ----
chal = HistGradientBoostingClassifier(
    max_iter=400, learning_rate=0.06, max_depth=5, max_leaf_nodes=31,
    min_samples_leaf=200, l2_regularization=1.0,
    early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
    class_weight="balanced", random_state=42)
chal.fit(Xtr, ytr, sample_weight=SW[~is_val])
p_tr_g = chal.predict_proba(Xtr)[:, 1]
p_va_g = chal.predict_proba(Xva)[:, 1]
print(f"challenger train AUC {roc_auc_score(ytr, p_tr_g):.4f}   "
      f"valid AUC {roc_auc_score(yva, p_va_g):.4f}")
print(f"iterations used: {chal.n_iter_}")

# ---- CELL ----
def ks_stat(y_true, p):
    fpr, tpr, _ = roc_curve(y_true, p)
    return float(np.max(tpr - fpr))

def report(name, ytr_, ptr_, yva_, pva_):
    # weighted throughout: on a down-sampled training file the unweighted
    # figures describe the sample, not the book
    swt, swv = SW[~is_val], SW[is_val]
    a_tr = roc_auc_score(ytr_, ptr_, sample_weight=swt)
    a_va = roc_auc_score(yva_, pva_, sample_weight=swv)
    return dict(model=name,
                auc_train=a_tr, auc_valid=a_va, gap=a_tr - a_va,
                gini_valid=2*a_va - 1, ks_valid=ks_stat(yva_, pva_),
                brier_valid=brier_score_loss(yva_, pva_, sample_weight=swv))

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

# ---- CELL ----
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

SWva = SW[is_val]; sw_cal, sw_tst = SWva[h2], SWva[~h2]
iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-6, y_max=1-1e-6)
iso.fit(p_cal, ycal, sample_weight=sw_cal)
# the anchor must be the WEIGHTED event rate, or a down-sampled file pins the
# portfolio PD to the sample's inflated rate instead of the population's
anchor = (np.average(ycal, weights=sw_cal)
          / max(np.average(iso.predict(p_cal), weights=sw_cal), 1e-9))
pd_tst = np.clip(iso.predict(p_tst) * anchor, 1e-6, 0.999)
print(f"calibration fitted on {len(ycal):,} rows, judged on {len(ytst):,} HELD-BACK rows")
obs_w = np.average(ytst, weights=sw_tst)
pdm_w = np.average(pd_tst, weights=sw_tst)
print(f"mean PD {pdm_w:.4%}  vs observed {obs_w:.4%}  "
      f"-> level error {abs(pdm_w-obs_w)/obs_w:.2%}   (both population-weighted)")
# Brier and AUC must be WEIGHTED too. Unweighted on a down-sampled file they
# describe the sample's inflated event rate, not the population's - Brier came
# back at 0.29 on a 2 pct problem purely from that.
print(f"Brier {brier_score_loss(ytst, pd_tst, sample_weight=sw_tst):.6f}   "
      f"AUC {roc_auc_score(ytst, pd_tst, sample_weight=sw_tst):.4f}   (weighted)")

dec = pd.qcut(pd_tst, 10, labels=False, duplicates="drop")
cal = pd.DataFrame({"decile": dec, "pd": pd_tst, "y": ytst}).groupby("decile").agg(
    n=("y","size"), predicted=("pd","mean"), actual=("y","mean"))
cal["ratio"] = cal.actual / cal.predicted
print("\ncalibration by decile on the held-back half (ratio near 1.0 is the goal)")
print(cal.to_string(float_format=lambda v: f"{v:8.4f}"))
print(f"\nworst decile ratio: {cal.ratio.min():.3f} to {cal.ratio.max():.3f}")

# everything downstream uses the held-back half
pd_va, yva_eval = pd_tst, ytst

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# ---- CELL ----
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

# -*- coding: utf-8 -*-
"""Cells: data load / synthetic, EDA, split."""
def add(md, co):
    md(r"""
## 3. Load

Reads the two CSVs exported from `dcb3_dataset_c1` and `dcbs_scoreset`. When they
are absent it generates a stand-in with the same columns and a deliberately
*realistic* signal strength, so the notebook runs end to end and the metrics
below are in a believable range rather than a flattering one.
""")

    co(r"""
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
""")

    md(r"""
### The contract assertion

This is the cell that decides whether anything below is real.
""")

    co(r"""
leak = [c for c in FEATURES if c in OUTCOME]
assert not leak, f"OUTCOME COLUMN IN X: {leak}"
assert CFG["LABEL"] not in FEATURES
y = train_raw[CFG["LABEL"]].astype(int).values
print(f"X has {len(FEATURES)} columns, none from the outcome window  [PASS]")
print(f"label {CFG['LABEL']}: {y.mean():.4%}  ({y.sum():,} bads in {len(y):,})")
print(f"\nevent rate {y.mean():.2%} is a LOW-EVENT-RATE problem.")
print("handled with class weighting and calibration - never by loosening the label.")
""")

    md(r"""
## 4. Split

Hashing `sbrp_id` makes the split reproducible and keeps a subscriber on one side
of it forever, which matters once this is re-run.

**This is an in-time split, not out-of-time.** Honest about what it is: it
measures whether the model generalises across subscribers, not across time. The
real out-of-time test is cohort **C2** (`T0=140412`, features clear of the
revenue shock), built with one `recalendar.py` command. Until C2 is scored, the
held-out numbers below are an upper bound on what production will see.
""")

    co(r"""
h = train_raw["sbrp_id"].astype(str).map(
        lambda s: int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF)
is_val = (h < CFG["valid_frac"]).values
Xtr, Xva = train_raw.loc[~is_val, FEATURES], train_raw.loc[is_val, FEATURES]
ytr, yva = y[~is_val], y[is_val]
print(f"train {Xtr.shape[0]:,}  bad {ytr.mean():.4%}")
print(f"valid {Xva.shape[0]:,}  bad {yva.mean():.4%}")
print(f"stratification drift: {abs(ytr.mean()-yva.mean())/y.mean():.2%} of base rate")
""")

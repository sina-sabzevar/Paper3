# Model contract — train set, score set, and what must never be an input

The goal, as stated: train a model on this database, then hand the implementation
team a final database carrying the model's predictions. That needs **two**
datasets, and so far only the first exists.

## The two datasets

| | T0 | feature window | label window | rows |
|---|---|---|---|---|
| **TRAIN** `dcb3_dataset_c1` | 140501 | 140407..140412 | 140501..140506 | built |
| **SCORE** `dcb3_scoreset` | 140507 | **140501..140506** | none | **not built yet** |

The score set's feature window is exactly the train set's **label** window. Those
months are closed (140506 is the last complete month), so it can be built today
with no waiting. The six-month gap between training features and scoring features
is the minimum achievable — any smaller gap would mean the training label window
had not closed.

### How to build the score set

```
python3 tools/recalendar.py --t0 1405 7
```

Then run STEP 1, 1B, 2, 3, 4, 5, 6, 7 — **and NOT STEP 8**, which is the label,
and not STEP 9 as written, which joins it. Assemble without `dcb3_label`:
`22_emit_step9.sql` with `dcb3_label` removed from its `src` list emits that
statement from the catalogue.

Three things must hold or the model will score a different population than it
learned on:

1. **Same code.** Build it from the same file with only the calendar changed.
   That is what `recalendar.py` is for; hand-editing the dates reintroduces every
   error of the last two days.
2. **No `n_months_seen >= 6` filter.** That is a label-side rule — it exists so a
   training row has a complete outcome. A scoring row has no outcome at all, so
   applying it would silently drop live subscribers.
3. **Keep the 8/9 exclusion.** That is the business rule, and it applies to both.

When done, restore the training calendar with
`python3 tools/recalendar.py --t0 1405 1 --out 6`.

## The leakage trap

`dcb3_dataset_c1` carries **19** columns computed from the outcome window, not
just the label. Dropping only the `y_` columns leaves **11** of them in `X`:

```
n_months_out, max_dpd_out, n_late_out, total_debt_days_out, oneway_days_out,
twoway_days_out, twoway_months_out, escalated_twoway,
rule1_dpd60, rule2_late, rule4_escalated
```

Several of these **are the label by another name** — `rule1_dpd60` is `y_strict`,
`escalated_twoway` is `y_severe`. A model given them scores a perfect Gini in
training and is worthless in production, and it will not look broken: it will
look excellent. None of them exists in the score set either, so the failure
surfaces only when the two sets are lined up.

The safe rule is positive, not subtractive: **take X from the list below**, never
`df.drop(...)`.

## MODEL INPUTS — 77 columns

Everything from the feature window 140407..140412 and the T0 snapshot.

```python
FEATURES = ['age_on_net_months', 'med_bill', 'n_billed_months', 'ec_billed_6m', 'mc_billed_6m', 'obligation_6m', 'midcycle_billed_share', 'med_obligation', 'max_bill', 'bill_std', 'max_dpd_6m', 'max_debt_run_days', 'n_debt_spells_6m', 'total_debt_days_6m', 'n_late_months_6m', 'n_mild_late_months_6m', 'n_ontime_months_6m', 'max_debt_amt_6m', 'unbill_peak_6m', 'unbill_avg_6m', 'debtdays_m1', 'debtdays_m2', 'debtdays_m3', 'debtdays_m4', 'debtdays_m5', 'debtdays_m6', 'oneway_days_6m', 'twoway_days_6m', 'n_ceiling_months_6m', 'n_barred_months_6m', 'last_bar_month_idx', 'last_twoway_month_idx', 'avg_barred_days_per_spell', 'billed_m1', 'billed_m2', 'billed_m3', 'billed_m4', 'billed_m5', 'billed_m6', 'totrev_m1', 'totrev_m2', 'totrev_m3', 'totrev_m4', 'totrev_m5', 'totrev_m6', 'data_gb_6m', 'data_gb_3m', 'voice_min_6m', 'voice_min_3m', 'call_cnt_6m', 'intl_cl_cnt_6m', 'totrev_std_6m', 'data_gb_std_6m', 'billed_6m', 'midcycle_billed_share_6m', 'noncash_share_6m', 'n_months_panel', 'paid_total_6m', 'n_payments_6m', 'avg_first_pay_day', 'paid_std_6m', 'proven_capacity', 'median_monthly_paid', 'capacity_headroom', 'network_id', 'initial_cred_lim_amt', 'temporary_cred_lim_amt', 'rfndable_dpos_amt', 'non_rfndable_dpos_amt', 'advance_pmnt_amt', 'bill_outstanding_amt', 'unbill_outstanding_amt', 'available_credit', 'ceiling_reconstructed', 'ceiling_utilisation', 'debt_scr', 'suspend_scr']
```

## OUTCOME WINDOW — 19 columns, never inputs

```python
OUTCOME = ['n_months_out', 'max_dpd_out', 'n_late_out', 'total_debt_days_out', 'oneway_days_out', 'twoway_days_out', 'twoway_months_out', 'escalated_twoway', 'rule1_dpd60', 'rule2_late', 'rule4_escalated', 'y_twoway_2m', 'y_twoway_any2m', 'y_severe', 'y_strict', 'y_v1', 'y_v2', 'y_loose', 'indeterminate']
LABEL = "y_severe"      # 2.22 pct, the operator's own definition of default
LABEL_ALT = "y_strict"  # 1.22 pct, DPD >= 60, the persistence view
```

`sbrp_id` is an identifier, not a feature. `obs_cohort` is a constant.

## What the implementation team receives

Not this table. They get one row per subscriber with: `sbrp_id`, the model's
probability of default, the score band or grade, and the limit the engine
assigns. The feature columns stay on our side — they are inputs to a decision,
not the decision.

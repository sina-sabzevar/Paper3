# First run on the real data — what it says

Source: the executed notebook, 24 of 24 code cells, no errors.
Train `dcbtrain_part1/2.parquet`, score `dcbs_pred_part1/2.parquet`.

## The answer to the two questions

| | |
|---|---|
| scored | 11,567,908 |
| **approved** | **40,366  (0.349 pct)** |
| **principal** | **22.5 billion Toman** |
| mean ticket | 557,400 Toman |
| handover rows | 41,052  (40,366 scorecard + 686 control) |
| portfolio PD after shock uplift | 1.9264 pct |
| expected loss | 0.17 bn Toman = 0.735 pct of principal |

Against the three hard constraints:

| constraint | target | delivered | |
|---|---|---|---|
| loans | 3,000,000 | 40,366 | **1.35 pct of target** |
| budget | 1,200 bn Toman | 22.5 bn | 1.88 pct used, 1,177.5 bn idle |
| minimum ticket | 400,000 | 557,400 mean | clears it |

## The model is not the problem

| | |
|---|---|
| label `y_severe` | 2.2231 pct — 205,456 bads in 9,241,763 |
| valid AUC | 0.8358 logistic, **0.8536** gradient boosting |
| valid Gini | 0.7073 |
| train-valid gap | 0.0059 — not overfitted |
| PD level error | **0.59 pct** (2.2164 predicted vs 2.2296 observed, weighted) |
| decile ratios | 0.877 to 1.093 — genuinely calibrated |
| bad rate monotonic across grades | True |

A model that ranks at 0.85 Gini 0.71 and whose PD level is right to within
0.59 pct is not what is rejecting 99.65 pct of the base.

## What is rejecting them: two ceilings sit below the minimum ticket

The loan is the MINIMUM of four ceilings. Two of the four have a median
below the 400,000 minimum, so the median subscriber is capped under the
floor and gets nothing at all.

| ceiling | median | binds | vs 400,000 minimum |
|---|---|---|---|
| affordability | 497,120 | 2.9 pct | clears |
| **size vs bill** | **310,240** | **96.0 pct** | **89,760 short** |
| operator credit line | 347,926 | 1.0 pct | 52,074 short |
| grade cap | 1,000,000 | 0.1 pct | clears |

`size vs bill` is `mult * obligation_6m`, and `obligation_6m` is built from
billed amounts. The project already retracted sizing against the bill once:
the bill is a RESIDUAL net of cash and mid-cycle payments, so it understates
what a subscriber carries. Rebuilding the ticket test on total payments is
what produced the 3,991,092 figure at a 40 pct stance. That ceiling puts the
retracted assumption back in, and it now binds 96 pct of the book.

Note also that deleting it is not sufficient: the operator credit line at a
median of 347,926 still blocks the median subscriber.

## Second blocker: eight features are extrapolating

PSI, training window against scoring window:

| feature | PSI | |
|---|---|---|
| `suspend_scr` | 14.4120 | |
| `debt_scr` | 13.8912 | |
| `last_twoway_month_idx` | 9.1907 | a calendar index, see below |
| `last_bar_month_idx` | 6.6435 | a calendar index, see below |
| `mc_billed_6m` | 5.3333 | register item G, mid-cycle billing |
| `initial_cred_lim_amt` | 1.7801 | |
| `age_on_net_months` | 0.3848 | |
| `ceiling_reconstructed` | 0.2744 | |

8 features above 0.25, 17 above 0.10.

`last_bar_month_idx` and `last_twoway_month_idx` are raw month indices. The
scoring window sits six months after the training window, so every
subscriber's index shifts by six whether or not their behaviour changed. The
model learned that about 16865 means recent; in the scoring set the same
recency reads about 16871. These are calendar time leaking in as a feature
and must become "months since" (T0 minus the index) or be dropped.

`debt_scr` and `suspend_scr` at 13.9 and 14.4 are not drift in any ordinary
sense. A distribution does not move that far in six months; check whether
they are NULL or constant in one of the two windows.

## Three smaller things

1. **78 of 80 features.** Missing: `n_payments_6m` (the `pay.payments_6m`
   column commented out to get STEP 9 to run) and `has_midcycle_billing`
   (register item G, whether `cust_bil_typ_id = 3` exists at all — still
   unrun).
2. **`proven_capacity` contains at least one NaN.** Cell 30 prints
   `median proven capacity nan` because it uses `np.median`, which
   propagates, while the ceiling medians use `np.nanmedian`. The count is
   unknown but not zero, and each NaN row hits
   `C = np.where(np.isfinite(C), C, 0.0)`, which turns the affordability
   ceiling into 0 and silently rejects that subscriber.
3. **No `sample_weight` column**, because the full 9,241,763-row training set
   was exported rather than the down-sample. That is correct, not a fault:
   weight 1.0 everywhere is right for a full population.

## What to do next, in order

1. Rebuild `size vs bill` on total payments rather than billed amounts, or
   remove it and let affordability bind. It is the 96 pct constraint.
2. Decide the operator credit line multiple. At `collateral_mult = 1.00` its
   median is 347,926, under the minimum ticket. This is policy, not data.
3. Convert the two month-index features to "months since", or drop them.
4. Establish whether `debt_scr` and `suspend_scr` are populated in both
   windows before trusting any PD built on them.
5. Re-run. Then the question of whether 3M loans is reachable can be answered
   on numbers rather than on the current 40,366.

## The constraint that will not go away

1,200 bn divided by 3,000,000 loans is exactly 400,000 Toman — the stated
minimum ticket. The budget and the loan count together leave the limit engine
no room: every approved subscriber must receive exactly the minimum and not
one Toman more. Any subscriber who warrants more than 400,000 makes the
3M target unreachable within the budget. This is a business decision, not a
modelling one, and it should be settled before the next run.

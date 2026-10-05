# The model, measured

`train_model.ipynb` on `dcb_model` (8,701,085 rows, 45,361 bads at 0.5213%) and
`dcb_score` (9,344,723). Zero errors, 20 cells executed.

## It works, and better than I predicted

| | AUC | Gini | KS |
|---|---|---|---|
| logistic, VALID | 0.7385 | 0.4769 | 0.3652 |
| HistGB, VALID | 0.7918 | 0.5836 | 0.4346 |
| **HistGB calibrated, TEST in band** | **0.8017** | **0.6034** | **0.4551** |

**I set that expectation too low.** After W4 I said to expect modest and
pointed at `rev_months` alone scoring 0.5479. TEST came in at **0.8017**. W4
tested one feature; the payment, outstanding and tenure columns carry far more
than it implied, and I over-read a single-feature result as a ceiling on the
whole set.

HistGB beat logistic by **+0.0533** on VALID, so the interactions are real and
the challenger won on merit. Train-to-valid gap +0.0205 — acceptable, not
overfitted.

### Calibration

- mean PD **0.5234%** against observed **0.5146%** — level error **1.72%**
- all **10 of 10** deciles expect 10+ bads, so every ratio is readable
- worst decile ratio **0.822**, best **1.049**

Tight for a 0.5% event. The isotonic anchor came back 1.0000, meaning no
rescaling was needed.

## The business answer

At 500,000 Toman per subscriber, ranked safest first:

| take | book PD | exposure | expected loss | loss rate |
|---|---|---|---|---|
| 934,472 | 0.0965% | 467 bn | 0.5 bn | 0.10% |
| 1,868,944 | 0.1379% | 934 bn | 1.3 bn | 0.14% |
| **3,000,000** | **0.1646%** | **1,500 bn** | **2.5 bn** | **0.16%** |
| 4,672,361 | 0.2094% | 2,336 bn | 4.9 bn | 0.21% |
| 9,344,723 | 0.6046% | 4,672 bn | 28.2 bn | 0.60% |

**The original ask is comfortably met.** 3,000,000 subscribers at 500,000 Toman
carries a **0.1646%** average PD and about **2.5 bn Toman** of expected loss on
1,500 bn lent — and that is with LGD at 100%, which the limit table states is
deliberately pessimistic. The operator keeps collecting after a bar, so the
realised loss should be lower.

Under a PD ceiling: **0.25% admits 5,775,729** (2.9 tn, 7.2 bn loss), **0.50%
admits 9,156,827** — 98% of the live set.

### The 15,000 bn target is still the open gap

| | Toman per subscriber needed |
|---|---|
| at 3,000,000 | 5,000,000 |
| at 9,344,723 | 1,605,184 |

At 500,000 each the full book is 4,672 bn — **3.21× short**. The thread that
could close it is `46_bar_ladder_risk.sql`: the revenue bar turned out to be a
**capacity** screen rather than a risk screen, so lowering it adds volume
without adding loss rate. That is a line-size and screen-width decision, not a
modelling one.

## The one defect this exposed

Four of the five relative twins did their job. One did the opposite:

| feature | raw PSI | `_rel` PSI | |
|---|---|---|---|
| `rev_6m` | 1.0865 | **0.0038** | twin fixes it |
| `rev_max` | 3.0223 | **0.0242** | twin fixes it |
| `paid_6m` | 0.3338 | **0.0034** | twin fixes it |
| `avail_max` | 0.1938 | **0.0501** | twin fixes it |
| `outst_max` | **0.0551** | **1.1404** | **twin made it worse** |

`outst_max` is already stable across the two windows, and dividing it by its
own window's median manufactured drift where there was none. Most subscribers
carry zero outstanding, so that median sits near zero and is itself unstable
between windows — a stable numerator over an unstable near-zero denominator
moves for no behavioural reason. `NULLIF` guards a median of exactly zero, not
a small one.

**Removed.** And it establishes a rule now recorded in the generator: build a
relative twin only for a feature whose raw column actually drifts *and* whose
median sits well away from zero. Check both.

## Drift is the live risk, and it is large

13 features shifted significantly (PSI > 0.25), led by `rev_max` at **3.0223**.
The live set scores a mean PD of **0.6046%** against TEST's observed 0.5146% —
17% higher, which is the drift showing up in the level rather than the ranking.

**So trust the ranking more than the level.** The safest-N ordering is what the
limit engine consumes and it survives a monotone level shift; the absolute PD
does not.

### What would reduce it, and is not yet done

`r1..r6` and `rev_trend` carry PSI of 0.15 to 0.83 and have **no relative
twins**, so setting `USE_RELATIVE_ONLY` would not touch them — it only swaps
the four aggregate levels for their ratios. The more complete fix is to express
each month as a **share of the subscriber's own 6-month total** (`r1/rev_6m`,
and so on), which is scale-free by construction and needs no window median, so
it is immune to both inflation and the window effect. That is a change to the
SQL and a re-run, and worth doing before this model goes anywhere near
production — but the current result stands on its own.

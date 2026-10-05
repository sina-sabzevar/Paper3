# 43_cohort_funnel.sql — first run, measured

Source: `test43.xlsx`, sheets d1/d2/d4/d5/d6. **D3 was not in the export** and is
still needed; see *Open* at the bottom.

## 0. The diagnostic validates against the previous work

Window D (`140407..140412` features, `140501..140504` label) returns **6,879,803
screened at 0.9492%**. That is exactly what `41_forward_horizons.sql` measured on
the same window. The two files agree, so the rest of this output can be trusted.

## 1. Coverage is ruled out

| window | present | avg months seen | avg NULL-arpu rows |
|---|---|---|---|
| A 140301..140306 | 33,631,341 | 5.880 | 1.351 |
| B 140401..140406 | 37,689,659 | 5.879 | 1.394 |
| C 140501..140506 | 41,270,092 | 5.797 | 1.362 |
| D 140407..140412 | 40,138,652 | 5.866 | 1.366 |

Months-seen and the NULL-arpu rate are flat. The early months are not thin, and
the base itself grows 33.6M → 41.3M. **Not a loading gap** — so the alternative
hypothesis is dead and the early windows are usable.

## 2. It is nominal drift, and it is large

Revenue per subscriber-month, months 1-6 of each year:

| | 1403 | 1404 | 1405 | 1403→1405 |
|---|---|---|---|---|
| median | 187,125 | 210,216 | 289,485 | **1.55x** |
| p75 | 738,117 | 859,143 | 1,358,814 | **1.84x** |
| p90 | 1,561,386 | 1,796,746 | 2,935,251 | **1.88x** |
| mean | 547,185 | 620,477 | 1,018,812 | **1.86x** |

Growth accelerated sharply in the second year: +13% then +64% at the mean. The
1,700,000 Rial bar sits in the upper tail, where the factor is ~1.86x.

## 3. The screen has silently loosened — this is the finding that matters most

The bar is fixed nominal, so as revenue inflates past it the screen admits more
of the base every year:

| window | share of base admitted | screened |
|---|---|---|
| A 1403 h1 | 12.0% | 3,733,333 |
| B 1404 h1 | 14.6% | 5,100,390 |
| D 1404 h2 | 18.4% | 6,879,803 |
| **C 1405 h1** | **24.4%** | **9,344,723** |

**The 6,879,803 figure is stale.** At the same 170,000 Toman rule the current
window holds **9,344,723 subscribers, +35.8%**. Nobody changed the rule; the rule
changed underneath because it is nominal. Left alone it keeps loosening, and the
eligible population keeps growing without a decision being taken.

## 4. The event rate is driven by LABEL SEASON, not by screen breadth

| window | label span | months | screen breadth | event rate |
|---|---|---|---|---|
| A | 140307..140310 | 7-10 | 12.0% | **0.5730%** |
| B | 140407..140410 | 7-10 | 14.6% | **0.5541%** |
| D | 140501..140504 | 1-4 | 18.4% | **0.9492%** |

A and B sit at materially different breadths (12.0% vs 14.6%) and give almost the
same rate — the broader one is marginally *lower*. So breadth does not move the
rate in this range. D differs chiefly in which calendar months its label covers,
and is **1.68x** higher.

Jalali months 1-4 are Farvardin–Tir and contain Nowruz. A four-month exposure
across Nowruz looks materially riskier than the same exposure across months 7-10.

## 5. Which season the product actually faces

`SCORE` features run to 140506, so lending starts in month 7 and a four-month
line is exposed over **140507..140510 — months 7-10**. A's and B's labels are
months 7-10. The cohorts now sit in the same season as the real exposure.

**The 0.95% on record was measured on months 1-4 — the wrong season for this
product's window.** The honest expectation for the current plan is **~0.55%**.

This cuts both ways: lending timed into Nowruz would face the 0.95% figure. The
rate is a property of *when* you lend, not only *who* you lend to.

## 6. Partial observation is a non-issue

Fully observed equals screened exactly in all three labelled windows — 100.0000%.
Nobody screened in disappears within the next four months, so the earlier concern
about a four-month label diluting the rate does not arise.

## What changed in the code

- `COHORT_BAR` in `42_model_datasets.sql` set to **910,000** (TRAIN) and
  **1,050,000** (VALID), interim values from the percentile ratios, equalizing the
  admitted share to ~24% in all three windows. **Replace with D3's exact values.**
- `EXPECTED_RATE` in the notebook set to **0.005541** from D5 window B.
- Window **E** (`140307..140312` features, `140401..140404` label) added to
  `43_cohort_funnel.sql`. Its label is months 1-4 in a *different* year, which is
  the control for the 1.68x seasonal claim — that currently rests on one
  observation. If E lands near 0.95% the reading holds; near 0.56% and the D
  figure is about 1405 specifically, not about the season.

## Loan book, restated

At 500,000 Toman per subscriber:

| | subscribers | book | expected loss at 0.5541% | at 0.9492% |
|---|---|---|---|---|
| on record | 6,879,803 | 3,440 bn | 19.1 bn | 32.7 bn |
| **now** | **9,344,723** | **4,672 bn** | **25.9 bn** | **44.4 bn** |

The 15,000 bn target is still **3.21x** out of reach at this ticket; it needs
~1,605,000 Toman per subscriber across the whole screened population. That is a
business decision about line size, not a modelling one.

## Open

1. **D3** — the bar ladder. Needed for the exact `COHORT_BAR`. The table
   `dcb_funnel_bars` exists (D4 and D6 read from it), so only the sheet is
   missing, not the data.
2. **Window E** — re-run `43` to settle whether 1.68x is seasonal.
3. **Whether the screen should stay nominal.** A fixed bar is a drifting rule.
   Options: re-express it in real terms, re-set it periodically, or define it as a
   percentile of the base. This needs a decision, not a query.

---

# Where are the label = 1 subscribers?

Asked after the first run, and worth recording because the answer is easy to
misread.

**The 5,100,390 is not "the good users".** It is the *eligible* population, and
the bads are inside it:

| | | |
|---|---|---|
| the cohort | 5,100,390 | |
| label = 1 | 28,263 | 0.5541% |
| label = 0 | 5,072,127 | 99.4459% |

A label = 1 subscriber is one who was **clean through the feature window and
then went two-way barred in the label window**. That is exactly the event the
product has to predict — someone already barred is not a lending decision.

## After the 70/20/10 split

| split | rows | bads |
|---|---|---|
| TRAIN | 3,570,273 | ~19,784 |
| VALID | 1,020,078 | ~5,652 |
| TEST | 510,039 | ~2,826 |

~19,784 bads is ample to fit on, and ~2,826 in TEST gives an AUC with a tight
interval. **The constraint is the ratio, not the count**, and `sample_weight`
handles the ratio.

## What the screen removed, and why it is not withheld training data

403,976 subscribers cleared the revenue bar but already had a bar event **in**
the feature window — 382,142 one-way and 21,834 two-way. The product will not
extend credit to a subscriber who is already barred, so they sit outside the
product rather than being data we declined to use.

The part that matters: **`dcb_score` applies the same screen.** The fitting
population and the scoring population are filtered identically, so there is no
selection mismatch between them. This is not the classic reject-inference
problem, because the screen conditions on observable features we also hold for
the scoring population — not on an unobserved model score.

## What is not yet known

Whether the screen is doing real work. `44_where_are_the_bads.sql` answers it
from the existing `dcb_funnel` table, so it is cheap:

- **W1** the forward two-way rate in each rejected stratum against the cohort's
  0.5541%. Much higher in the rejected strata means the screen removes genuine
  risk; similar means it shrinks the book for nothing.
- **W2** reconciles the strata against D1's funnel steps — verified
  arithmetically that the identity holds.
- **W3** the screen's lift: how many times riskier the population is without it.
- **W4** the bad rate by `rev_months` **inside** the cohort. This is the most
  useful number for setting AUC expectations before fitting: a rate that falls
  steadily as `rev_months` rises means real separation remains; a flat rate
  means the screen already extracted what revenue can say and the model must
  lean on payment, outstanding and tenure instead.

Read W1 with one caveat: stratum 3 was **already** two-way barred during the
feature window, so its forward bad is largely the same bar continuing rather
than a new event predicted. Expect it near 100% and do not read it as signal.
Stratum 2 is the interesting one — one-way but not two-way, so a forward
two-way bar there is a real escalation.

---

# Should we add barred subscribers to get more label = 1?

Proposed: add subscribers who hold at least one filter (revenue above 170k) but
fail the bar filters, to balance the classes with more real bads.

**Not to the training table alone.** Two separate things are being conflated —
class *balance* and population *definition* — and the balance is already solved.

## The bad count is not a constraint

28,263 bads against 33 features is **856 events per variable**, roughly 57x the
usual 10–20 rule of thumb for a stable logistic fit.

And down-sampling already fixes the ratio. At `GOOD_KEEP = 10` the model sees
**5.28%** bads, not 0.55%. Adding both barred strata would move the *raw* rate
from 0.5541% to 1.10% — marginal next to what weighting already does, and it is
the weighted rate the fit actually sees.

## Measured: it does not help, and it costs

Fitted on synthetic data where the barred group carries the **same**
revenue-to-risk relationship as the clean cohort, just a higher baseline rate
and its bar flags set — the most favourable realistic assumption for the
proposal. TEST is always the clean population, because that is what `dcb_score`
contains.

| | AUC on clean TEST |
|---|---|
| clean TRAIN | baseline |
| TRAIN + barred | **mean delta −0.0001** over 6 seeds (−0.0018 to +0.0015) |

No gain. And the coefficients show why:

| feature | clean | + barred |
|---|---|---|
| `rev_6m` | 0.833 | 0.952 |
| `rev_max` | 0.208 | **0.108** |
| `outst_max` | 0.539 | 0.544 |
| `tenure_m` | 0.033 | **0.010** |
| `oneway_months` | 0.000 | **0.720** ← constant 0 in `dcb_score` |

The model spends 0.72 of weight on a feature that **cannot vary at scoring
time**, because the screen forces it to zero in the live set. That weight does
nothing, and `rev_max` and `tenure_m` are diluted to pay for it.

This is the same train/score mismatch the seasonal alignment and the per-window
bar were introduced to remove — reintroduced deliberately. It is also
detectable: PSI on `oneway_months` would go from 0 to very large.

## The version of the idea that does work

**If you want them in training, you must also want them in scoring.** Change
the screen on *both* tables — which makes it a product decision, not a
modelling one.

Stratum 2 is the real candidate: **382,142** subscribers who cleared the
revenue bar, were one-way barred, and were never two-way barred. A forward
two-way bar there is a genuine escalation, not a continuation. Admitting them
adds **191 bn Toman** of book at 500,000 each — against the cohort's 2,550 bn.

| their forward rate | blended rate | extra expected loss | |
|---|---|---|---|
| 1% | 0.585% | 1.9 bn | admit |
| 2% | 0.655% | 3.8 bn | admit |
| 3% | 0.725% | 5.7 bn | admit on a smaller line |
| 5% | 0.864% | 9.6 bn | admit on a smaller line |
| 10% | 1.213% | 19.1 bn | decline |
| 20% | 1.910% | 38.2 bn | decline |

**W1 in `44_where_are_the_bads.sql` measures the real rate.** That single number
decides it; the table above is just the decision frame.

Stratum 3 (21,834, already two-way barred) is not a candidate at all — their
forward bar is largely the same bar continuing, so it is not a prediction and
they are not a lending decision.

If the rate lands in the "smaller line" band, the drill-down worth having is
stratum 2 by **how many** one-way months they had: one bar event is a different
risk from four. That needs a new aggregate — `dcb_funnel` only carries `ow_any`
as a flag — so it is worth writing only once W1 says the group is promising.

## If more balance is wanted anyway

Lower `GOOD_KEEP`, which is free and does not change who the model is about:
`GOOD_KEEP = 5` gives 10.0% bads, `GOOD_KEEP = 2` gives 21.8%. Be aware that
rebalancing past a moderate level buys no ranking improvement and makes
calibration worse, which isotonic then has to undo. `GOOD_KEEP = 10` is a
reasonable place to stay.

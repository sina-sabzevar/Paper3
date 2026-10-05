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

---

# Does balance help? Measured

Challenged: is a 10M-row dataset with 5M label=1 not good for the model?

**Balance itself is fine, and I framed the earlier objection badly.** Sweeping
the training balance across the whole range, on one fixed test set, 5 seeds:

| `GOOD_KEEP` | train rows | bads in train | AUC | mean PD if weights forgotten |
|---|---|---|---|---|
| 100% | 1,000,000 | 0.55% | 0.7278 | 0.55% |
| 20% | 204,412 | 2.70% | 0.7279 | 2.66% |
| 10% | 104,963 | 5.25% | 0.7276 | 5.08% |
| 5% | 55,239 | 9.98% | 0.7277 | 9.39% |
| 2% | 25,404 | 21.71% | 0.7279 | 19.40% |
| 0.55% | 10,984 | **50.21%** | 0.7274 | **42.49%** |

**AUC spread across the entire sweep: 0.0005.** Balance does not change the
ranking, which is what the limit engine consumes. What it changes is the
*level*: at 50/50 without `sample_weight` the model predicts 42.49% against a
true 0.55%, and the limit engine spends the level.

So a balanced set would not be *worse* — it simply is not *better*, and
down-sampling with weights already gives the balance with the level intact.

## The real constraint is arithmetic, not methodological

| | bads |
|---|---|
| needed for 10M rows at 50/50 | 5,000,000 |
| available at the two-way label | **28,263** (177x short) |
| available at an estimated one-way label | ~236,000 (21x short) |

A 50/50 set **is** available today — keep 28,263 goods, get 56,526 rows — and
the sweep says it ranks identically on 100x less data. 5M bads only exists if
the population is the whole base rather than the eligible one, which is the
population mismatch measured in the previous section.

## Where more events could legitimately come from: the label

This is the productive version of the request. A one-way bar means the
subscriber **did not pay** — arguably more relevant to a credit line than being
fully cut off, and roughly **8x more common**.

`45_alternative_labels.sql` prices the menu on the *identical* cohort and the
*identical* label window, so only the event definition varies:

- **L1** the menu: two-way, one-way, either, one-way in 2+ months, 3+ months,
  with the balanced-set size each would support. `cohort_n` must come back
  5,100,390 and `pct_twoway` 0.5541%, which reconciles the file against 43.
- **L2** whether a one-way bar is transient or persistent. Mass at 1 month
  means most are a subscriber who paid late once and cured it — weak evidence
  of default and a poor label. Mass at 2–4 months is recurring non-payment.
- **L3** that the flags and the month counts agree. They come from different
  aggregates (`MAX(IF(...))` against `COUNT(DISTINCT IF(...))`), so this is a
  real test of both.
- **L4** whether a softer label still separates across `rev_months`. This is
  the one that decides it: if `pct_oneway_2plus` falls the way `pct_twoway`
  does, the softer label carries the same signal with 8x the events, which is
  the best available outcome. If it is flat, the extra events are noise.

**If a softer label is adopted**, two things must follow: the same definition
goes into `42_model_datasets.sql`, and the limit tables' LGD 100% assumption
has to be revisited — a one-way bar does not lose the whole balance, so that
assumption would be far too pessimistic for it.

---

# 44 and 45, measured

`w2` reconciles exactly with 43's D1 and `l3` returns all zeros, so both files
are internally correct and the figures below can be trusted.

## 1. The screen is doing enormous work — keep it

Window B (`140401..140406` features, `140407..140410` label), forward two-way
rate by stratum:

| stratum | n | forward rate | vs the cohort |
|---|---|---|---|
| fails the revenue bar | 32,185,293 | 2.737% | 4.9x |
| one-way barred in window | 382,142 | **11.622%** | **21.0x** |
| two-way barred in window | 21,834 | 35.761% | 64.5x |
| **SCREENED (the cohort)** | 5,100,390 | **0.554%** | 1.0x |

The one-way filter alone separates 21x. This is not a screen that shrinks the
book for nothing.

## 2. Do NOT admit the one-way group

Their forward two-way rate is **11.62%**. Against the decision table recorded
earlier — admit under 2%, smaller line at 3–5%, decline at 10%+ — this is a
clear decline:

| | |
|---|---|
| volume gained | +7.5% |
| blended book rate | 0.5541% → **1.3256%** (2.39x) |

7.5% more customers for 2.4x the loss rate. The question is closed.

## 3. Do NOT train on the whole base — W4 answered it

Bad rate by `rev_months` **inside** the cohort:

| `rev_months` | n | bad rate |
|---|---|---|
| 2 | 1,284,520 | 0.6768% |
| 3 | 924,415 | 0.5865% |
| 4 | 775,661 | 0.5829% |
| 5 | 788,032 | 0.5143% |
| 6 | 1,327,762 | 0.4198% |

Monotone, but the gradient is only **1.61x** across the whole range, and
`rev_months` used alone as a score gives an **AUC of 0.5479**.

So the revenue dimension is largely **spent by the screen**. That is the
*heterogeneous* world from the training-population experiment, where fitting on
the whole base cost **−0.09 AUC** in the band. `MODEL_POP` stays `"screened"`.

**And it corrects an expectation I set earlier.** I said that if W4 fell
steadily, to expect AUC around 0.70–0.78. That was too optimistic: it falls,
but weakly. How much the model achieves now depends on whether `outst_max`,
the payment columns and `tenure_m` carry signal independent of revenue, which
nothing measured so far tests. The notebook's own output answers it.

## 4. Keep the two-way label

| label | n | share | vs two-way count |
|---|---|---|---|
| two-way (current) | 28,263 | 0.554% | 1.00x |
| one-way, any | 166,994 | 3.274% | **5.91x** |
| one-way 2+ months | 22,696 | 0.445% | **0.80x** |
| one-way 3+ months | 6,649 | 0.130% | 0.24x |

- **`one-way 2+ months` fails its own purpose** — it is *rarer* than two-way
  (0.80x), so it cannot supply more events whatever its separation.
- **`one-way any`** does give 5.91x the events, but its gradient across
  `rev_months` is 3.6% → 2.8%, visibly flatter than two-way's. More events,
  less signal.
- **86.4% of one-way bars lasted a single month** — a subscriber who paid late
  once and cured it. That is weak evidence of default for a credit line.

One caution on reading `l2`: the apparent fall in "also two-way" as one-way
months rise (7.7% → 7.4% → 5.3% → 0.0%) is at least partly **mechanical**, not
behavioural. Status is one value per subscriber-month, so a subscriber one-way
barred in all four label months has no month left to show status 4. Do not read
that column as a behavioural finding.

A second caution: `l4` reports to one decimal place only, so gradient ratios
computed from it are imprecise — `one-way 2+` at 0.6% → 0.3% could be anywhere
from 1.6x to 2.6x. The two-way gradient of 1.61x is exact because W4 carries
counts. This project has previously reported a spurious spread by reading
hazard ratios off one-decimal percentages; the same care applies here.

## Settled

| question | answer |
|---|---|
| screen earning its keep? | yes — 21x on the one-way filter |
| admit the one-way group? | **no** — 11.62% forward rate |
| train on the whole base? | **no** — revenue is spent inside the band |
| `MODEL_POP` | `"screened"` |
| label | two-way bar, unchanged |
| expected AUC | modest; my earlier 0.70–0.78 was too optimistic |

Nothing further blocks the model. Run `42`, export, run the notebook.

---

# Currency: Rial vs Toman

Asked whether the Rial/Toman distinction was accounted for. Audited every
constant and conversion. **1 Toman = 10 Rial**, and the database stores Rial.

## The screen conversion is right

| | Rial (as coded) | Toman |
|---|---|---|
| production screen bar | **1,700,000** | 170,000 |
| MODEL bar (equalizing) | 1,050,000 | 105,000 |
| SUPERSET bar | 520,000 | 52,000 |
| 46 ladder range | 300,000 – 3,000,000 | 30,000 – 300,000 |
| avail/outst winsor cap | 500,000,000 | 50,000,000 |

`TICKET_TOMAN = 500,000` is the one natively-Toman figure, because it is a
business input rather than a database value — 5,000,000 Rial.

**The sanity check that confirms it:** `SCORE`'s median subscriber runs
**255,819 Toman/month** against a 170,000 Toman bar — comfortably over, as a
screened population should be. `MODEL`'s runs 154,500 against its 105,000 bar.
Both coherent. Had the bar been applied in the wrong unit, the screen would
have admitted either almost nobody or almost everybody.

**The book is Toman end to end:** 9,344,723 × 500,000 Toman = **4,672 bn
Toman** (= 46,724 bn Rial), against a 15,000 bn Toman target, so 3.21× short.
Read as bn *Rial* that gap would look 32×, not 3.2×.

## One real defect, fixed

`42` T1 reported `APPROX_PERCENTILE(rev_6m, 0.5) / 10000 AS med_rev_6m_k`.
`rev_6m` is Rial, so `/10000` gives units of 10,000 Rial = 1,000 Toman. It
returned 934.7 — which is 934,700 Toman, but `_k` on a Rial column reads as
thousands of *Rial*, i.e. 93,470 Toman. A 10× misread waiting to happen.

Replaced with two explicitly named columns: `med_month_toman` (`/60` — six
months of Rial, divided by 6 months and by 10 Rial-per-Toman) and
`med_rev_6m_rial`.

## One assumption that was never verified — now checked

`arpu` is Rial. `pay_months` compares `pmnt_amt` against **the same Rial bar**,
which is only valid if payments are stored in Rial too. If they are in Toman,
the comparison is 10× too strict and `pay_months` is near zero for almost
everyone — a **silently dead feature**, not a visible error.

Nothing measured so far tests this. `42` T4 now does:

- **`pay_to_rev_ratio`** — a postpaid subscriber pays roughly what they are
  billed, so this should land near **1**. Near **0.1** means payments are in
  Toman and every payment threshold in this project is wrong by ten.
- **`med_pay_months` against `med_rev_months`** — the corroborating symptom. If
  revenue clears the bar in 4 months and payments in 0, that is the mismatch
  showing itself.

Indirect evidence suggests they are the same unit — `40_revenue_matrices.sql`
produced payment and revenue spreads of the same order (17.5× and 26.5×) rather
than differing by ten — but that is inference, not measurement. T4 settles it.

The header of `42` now states the convention so this cannot drift again.

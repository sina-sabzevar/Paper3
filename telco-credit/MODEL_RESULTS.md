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

---

# The chosen book: 4,672,361

Decision: take the safest 4,672,361 — half the scored population — on the basis
that the loss rate stays under 0.5%.

## Cumulative against marginal

The cumulative table alone hides the number that decides where to stop:

| take | share | book PD | **marginal PD** | exposure | exp loss |
|---|---|---|---|---|---|
| 934,472 | 10% | 0.0965% | 0.0965% | 467 bn | 0.5 bn |
| 1,868,944 | 20% | 0.1379% | 0.1793% | 934 bn | 1.3 bn |
| 2,803,416 | 30% | 0.1595% | 0.2027% | 1,402 bn | 2.2 bn |
| 3,737,889 | 40% | 0.1832% | 0.2543% | 1,869 bn | 3.4 bn |
| **4,672,361** | **50%** | **0.2094%** | **0.3142%** | **2,336 bn** | **4.9 bn** |
| 5,606,833 | 60% | 0.2437% | 0.4152% | 2,803 bn | 6.8 bn |
| 6,541,306 | 70% | 0.2782% | 0.4852% | 3,271 bn | 9.1 bn |
| 7,475,778 | 80% | 0.3199% | **0.6118%** | 3,738 bn | 12.0 bn |
| 9,344,723 | 100% | 0.6046% | 2.5918% | 4,672 bn | 28.2 bn |

**Book PD** is the average over everyone taken — it sets total loss. **Marginal
PD** is the last subscriber admitted — it says whether the next slice is worth
taking. At 4,672,361 both clear the ceiling: book 0.2094%, marginal 0.3142%.

The marginal rate first crosses 0.5% at the **80%** mark (0.6118%), so there is
headroom well past this cut if volume is wanted later.

## Stress

| scenario | rate | loss | |
|---|---|---|---|
| as predicted | 0.2094% | 4.9 bn | within |
| +17% drift seen in the live set | 0.2450% | 5.7 bn | within |
| lending into months 1-4 (measured 1.68×) | 0.3518% | 8.2 bn | within |
| twice predicted | 0.4188% | 9.8 bn | within |
| three times predicted | 0.6282% | 14.7 bn | **breaches** |

**It takes a 2.4× miss to breach 0.5%.** At 3,000,000 it took 3.0× — so this
cut trades some cushion for 836 bn more book. A deliberate trade with a wide
margin remaining.

Against the 15,000 bn target this book is 6.42× short, so the gap is a
line-size and screen-width question (`46_bar_ladder_risk.sql`), not a
model one.

## notebook/select_book.py

Cuts the book out of `handover_scores.csv` and reports the PD cutoff, the book
and marginal rates against appetite, the money at the chosen ticket and LGD,
the stress table, and the grade mix. Writes `outputs/approved_book.csv`.

Separate from the notebook on purpose: the model's job ended at a ranked score
per subscriber. Where to cut will be revisited — different appetite, different
line, different month — and none of that should mean re-running an 8.7M row fit.

`TAKE`, `TICKET_TOMAN`, `APPETITE` and `LGD` are the four knobs. `LGD = 1.00`
is pessimistic by choice: the operator keeps collecting after a bar.

## What has not changed

`pd_4m` is the probability of a **two-way bar within 4 months**, not the share
of credit repaid. Every label behind it came from subscribers who had **no
credit line**, so the model predicts "would be cut off for not paying their own
bill" — a proxy for "would not repay credit", not a measurement of it. On TEST
it ran about 10% conservative in this score region, which is the right
direction, but the behavioural effect of handing someone spendable credit is
unmeasured and unmeasurable from this data. A pilot is the only thing that
closes it.

---

# The refit, measured — run 1405-07-14

`42` re-run with the six `pre_*` columns, both tables re-exported, notebook
re-run end to end. 8,701,085 rows / 45 columns / 39 features (`oneway_months`
dropped for no variance, which is correct — the screen forces it to zero).

## It worked, and A5 was right about why

| | before | after | |
|---|---|---|---|
| **HistGB calibrated, TEST in band** | 0.8017 | **0.8278** | **+0.0261** |
| Gini | 0.6034 | **0.6557** | +0.0523 |
| KS | 0.4551 | **0.5151** | +0.0600 |
| logistic, VALID | 0.7385 | **0.7843** | **+0.0458** |
| HistGB, VALID | 0.7918 | **0.8157** | +0.0239 |

**The linear model gained twice what boosting did.** A prior bar is close to a
straight additive signal — it did not need a tree to find it, which is why W4's
single-feature probe underestimated the whole set and why A5 found it by a plain
cross-tab. The challenger still wins by +0.0314 on VALID, so interactions are
real, just no longer where most of the new information lives.

## The book

| take | before | after | | exposure | loss after |
|---|---|---|---|---|---|
| 934,472 | 0.0965% | 0.0941% | −2.5% | 467 bn | 0.4 bn |
| 3,000,000 | 0.1646% | **0.1412%** | −14.2% | 1,500 bn | 2.1 bn |
| **4,672,361** | **0.2094%** | **0.1790%** | **−14.5%** | 2,336 bn | **4.2 bn** |
| 7,475,778 | 0.3199% | 0.2667% | −16.6% | 3,738 bn | 10.0 bn |
| 9,344,723 | 0.6046% | 0.5952% | −1.6% | 4,672 bn | 27.8 bn |

Marginal PD is not printed by the notebook; derived across consecutive deciles
it is **0.2694%** at the chosen cut and first crosses 0.50% at the **80%** mark
(0.5180% at 7,475,778).

**Under a 0.25% ceiling the model now admits 7,122,466, up 1,346,737 (+23.3%).**
That is the headline for the volume question: the refit bought more book at the
same risk than any screen change has.

## Calibration moved the wrong way at the end that matters

Level error is fine — 0.5232% predicted against 0.5146% observed, 1.68%. But the
decile table over-predicts risk where the book is drawn:

| | predicted | observed | ratio |
|---|---|---|---|
| safest 3 deciles | 0.1038% | 0.0806% | **0.776** |
| safest 5 deciles | 0.1305% | 0.1171% | 0.898 |
| all 10 | 0.5232% | 0.5146% | 0.983 |

Worst single decile **0.677** (was 0.822). Observed risk is still monotone across
all ten, so the ranking — which is what the book is cut on — is sound. The error
is conservative in direction: realised should land at or under 0.1790%. State it
rather than quote 0.1790% as a point estimate.

## Two defects this run exposed

**1. The handover table was double-loaded.** The upload cell printed `Table
dwbi_temp40_db.DCB_Handover140506 exists with 9344723 rows. Appending data.` and
inserted a second full set on the same keys. `COUNT(DISTINCT sbrp_id)` still
reads 9,344,723, so the obvious check passes while `ORDER BY pd_4m` returns a
book from neither model and every join fans out 2×. Execution count is null, so
it did not finish — an arbitrary subset is double-scored. Old and new rows are
indistinguishable, so no dedupe is honest. `50_handover_repair.sql` measures,
drops and verifies the rebuild.

**2. `pre_ow_months` and `pre_tw_months` returned PSI `nan`.** My bug. The
function sent anything with more than ten distinct values to quantile bins;
these carry thirteen values of which ~99.9% are zero, so every quantile edge
collapsed onto 0 and it returned `nan`. **Cardinality was the wrong test —
concentration is what breaks quantiles.** Both are checked now, the value path
uses `np.unique(..., return_counts=True)` instead of a per-category scan, and the
fix is verified against a synthetic column of the same shape.

A caveat survives the fix: PSI weights by prevalence, so tripling the rate of a
0.1%-prevalence feature still reads 0.0023. For these two, PSI will almost never
flag anything. Watch the rate in the non-zero tail instead — that tail is where
the 13.2× lift lives.

## Drift, restated

12 features significant (was 13), still led by `rev_max` at 3.0223. Live mean PD
0.5952% against TEST observed 0.5146% — **+15.7%**, down from +17.5%. The six
`pre_*` features are the most stable in the set: 0.0000 to 0.0003. A count of
past bars should be stable, so that is a sanity check passing, not a surprise.

---

# The validation run, measured

`validate_model.ipynb` against the refit data. Seven checks.

| | result | |
|---|---|---|
| row counts match the SQL | PASS | asserted at load |
| `sbrp_id` unique in both tables | PASS | |
| no subscriber in two splits | PASS | the hash is a pure function of the id |
| TEST AUC reproduced | PASS | 0.8278 refits from scratch |
| **tie at the cut under 1 pct of the book** | **LOOK** | **579,159 arbitrary** |
| `pre_` features carry independent signal | PASS | **+0.0239** TEST |
| scale-free model within 0.01 AUC | PASS | **−0.0048** TEST |

**The model and the datasets are clean.** No leakage, no split contamination,
no weighting error, and the headline reproduces from scratch.

## The cut was never a definition

579,159 subscribers — **12.40 percent of the book, 290 bn Toman of exposure** —
were refused while carrying exactly the same `pd_4m` as subscribers who were
approved. Isotonic calibration emits a step function; `ORDER BY pd_4m` took
everyone strictly safer and then filled the last places in whatever order the
engine returned.

That row is **LOOK, not PASS**: the check is `(n_at_cut - room) <= 0.01 * TAKE`,
and 1 percent of 4,672,361 is 46,724. 579,159 is 12.4× over it.

Fixed by the explicit order now in both routes — `pd_4m` asc, `pay_cover` desc,
`tenure_m` desc, `sbrp_id` asc. **The book has to be re-cut**, and the count the
tie-break decided travels with it when it is handed over.

## The `pre_` features earned their place

Removing them costs **0.0239** of test AUC against a total refit gain of 0.0261,
so they account for **92 percent** of the refit. The signal is independent, not a
proxy for revenue — which is what A5's cross-tab implied and this confirms
against the fitted model.

## Drop every Rial level — it costs 0.0048

A scale-free model scores **0.8230** against 0.8278. That is **0.58 percent of
the AUC** to remove every Rial amount from the inputs.

Take the trade. Twelve features in the full model drift significantly, led by
`rev_max` at PSI 3.0223, which is exactly why 0.8278 is an **upper bound** on
live performance rather than an estimate of it. Scale-free features cannot drift
with inflation, so 0.8230 **is** the estimate. Swapping a fifth of a percent of a
bounded number for an unbounded one is the right direction, and it ends the
yearly re-tuning the nominal design would otherwise need.

This is the answer to the drift item that has been open since the first run — not
a mitigation of it. The remaining work is to move the construction into
`42_model_datasets.sql` so the columns arrive scale-free rather than being
derived in the notebook.

---

# Bill shock: the effect is selection, not causation

`53_bill_shock.sql` on 140401–140406, outcome a two-way bar in the two months
after the repayment month.

## Between subscribers it looks real

| shock band | n | bars | rate | vs normal |
|---|---|---|---|---|
| bill fell | 4,393,649 | 18,086 | 0.4116% | 1.80× |
| **normal 0.80–1.25** | 6,428,541 | 14,723 | **0.2290%** | 1.00× |
| 1.25–1.50 | 2,441,872 | 5,948 | 0.2436% | 1.06× |
| 1.50–2.00 — a 100k ticket | 2,141,578 | 6,501 | 0.3036% | 1.33× |
| 2.00–3.00 — a 300k ticket | 1,138,755 | 5,143 | 0.4516% | **1.97×** |
| over 3.00 | 796,137 | 5,741 | 0.7211% | 3.15× |

## Within the same subscribers it disappears

`obs_ok` leaves two rows per subscriber, so everyone in S6 contributes exactly
one normal month and one shocked month — which is why `n_months` equals
`n_subs`. A clean paired design, 1,169,169 subscribers.

| | bars | rate |
|---|---|---|
| their normal month | 3,353 | 0.2868% |
| their shocked month (≥1.5×) | 3,257 | 0.2786% |

**Ratio 0.97, z = −1.18, 95% interval 0.92 to 1.02** on an unpaired standard
error, so conservative. **A bigger bill does not make a subscriber default.**

The entire S5 gradient is selection: subscribers whose bills jump are riskier
subscribers, and that is already what the model scores them on.

## It agrees with everything else we measured

- S2, on coverage rather than bars: within-subscriber median cover falls
  1.684 → 1.063. They pay a big bill **more slowly**.
- `52` D3, from the other side: coverage between 0.10 and 1.00 carries **no**
  excess bar risk — only "paid essentially nothing" does, at 8.3×.

Slower, not worse. A bigger bill stretches the payment; it does not break it.

## What that means for the product

The DCB premium over a subscriber's own base risk is **1.00**, not the 1.4×
I estimated from coverage. So expected loss is the model's PD at a one-month
horizon, with no shock multiplier — and the one-month base rate is measured:
**0.2208%**, 19,215 events.

Three caveats, unchanged:

1. A bar may lag more than the two months this window allows.
2. The substitution share is still unknown. It can only make this safer.
3. Nobody in this data was ever given spendable credit.

`S8` splits the paired test by shock size, because S6 pools everything at 1.5×
and over. At these counts it detects a premium above roughly 1.05× in each
band, so a null there is a real null.

## The 1405 check

`S7` runs the coverage curve on 140501–140506 at the production bar. The curve
has not flattened — premium normal → 2–3× is 1.41× in 1404 and 1.64× in 1405.
Median bills are 1.58× to 1.73× higher, which brackets the 1.50–1.69 deflator
from the two 30% price rises, though part of that gap is S7's richer screen
rather than inflation alone.

## S8: the paired test, split by size — all three bands flat or safer

| shock | pairs | normal | shocked | premium | discordant | McNemar |
|---|---|---|---|---|---|---|
| 1.50–2.00 (100k) | 767,568 | 0.2366% | 0.2331% | 0.985 | 628 vs 655 | p = 0.47 |
| 2.00–3.00 (300k) | 286,658 | 0.3342% | 0.3328% | 0.996 | 330 vs 334 | p = 0.91 |
| over 3.00 | 114,943 | 0.5037% | 0.4472% | **0.888** | 168 vs 233 | **p = 0.0014** |

Totals reconcile exactly with S6 — 3,353 normal, 3,257 shocked, 1,169,169 pairs.

Bands a and b are indistinguishable from no effect. Band c is significant **in
the safe direction**: past three times normal, a subscriber is *less* likely to
be barred than in their own ordinary month.

That is the mirror of S5's first row, which I almost skipped past: the highest
default rate of any band belongs to subscribers whose bill **fell** — 0.4116%,
1.80× normal. A collapsing bill is what precedes a bar, because the subscriber
has already stopped using the service. A bill that jumps is a month of health.
`rev_trend` is already in the feature set, which is the right place for it.

`S9` tests the one confound left: the two months in a pair do not share an
outcome window (140405 is judged on 140407–08, 140406 on 140408–09), so a drift
in bar rates across those months could manufacture the band-c result. It reads
the rate by bill month and repeats the paired test stratified by which month was
the shocked one.

## The loss number this supports

| | |
|---|---|
| one-month cohort rate, measured | **0.2208%** |
| shock premium to apply | **1.00** (0.92–1.02) |
| model selection at the 50% cut | 0.343 (0.1790 / 0.5213 on the 4-month label) |
| implied one-month book PD | **0.0758%** — an estimate, pending the refit |

At 8,801,772 approved and an average 302,300 Toman: 2,661 bn outstanding per
cycle, **2.0 bn lost per cycle, about 24 bn a year against 31,929 bn lent.**

It is built from two measured numbers rather than guessed, but it is not a
fitted result. The refit on the one-month label may move it.

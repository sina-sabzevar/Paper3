# How many good debtors are in the network

Measured on `test22.xlsx`, window 140501–140506. Payments use all
`bllg_pmnt_stat_id` values. Bar status from the monthly fact.

## 1. Payment behaviour predicts the two-way bar — decisively

| months paid ≥170k | subscribers | two-way barred | rate | lift | ever reclaimed |
|---|---|---|---|---|---|
| 0 | 23,353,837 | 959,104 | 4.1 pct | — | **39.6 pct** |
| 1 | 4,177,966 | 292,612 | 7.0 pct | 1.0× | 2.8 pct |
| 2 | 3,145,130 | 159,673 | 5.1 pct | 1.4× | 1.9 pct |
| 3 | 3,015,647 | 97,343 | 3.2 pct | 2.2× | 1.0 pct |
| 4 | 2,838,806 | 56,855 | 2.0 pct | 3.5× | 0.7 pct |
| 5 | 2,518,193 | 29,619 | 1.2 pct | 5.8× | 0.5 pct |
| **6** | 2,220,513 | 8,347 | **0.4 pct** | **17.5×** | 0.3 pct |

A **17.5-fold** reduction in two-way bar rate from one paying month to six.
The premise the whole model rests on is confirmed on 41.5 million
subscribers, and it needed no model to confirm.

**The zero-payment bucket is a trap.** At 4.1 pct it looks safer than
pay_months = 1, and it is not — it is *absent*. 39.6 pct of those 23.4 million
have hit reclamation, against 2.8 pct in the next bucket. They cannot be
barred for non-payment because they do not consume. 21.5 million of them sit
in one cell with 57.9 pct Active1 and essentially zero payment. The monotone
signal starts at pay_months = 1 and is clean from there down.

## 2. The clean population, and how they pay

Never one-way barred, never two-way barred:

| months paid | subscribers | paid over 6m | per month | best month | available credit | worst outstanding | median tenure |
|---|---|---|---|---|---|---|---|
| 1 | 3,591,420 | 534k | 89k | 245k | 293k | 6.15k | 19.4 yr |
| 2 | 2,774,509 | 844k | 141k | 332k | 346k | 10.46k | 19.8 yr |
| 3 | 2,743,700 | 1,205k | 201k | 456k | 407k | 15.63k | 20.0 yr |
| 4 | 2,629,940 | 1,703k | 284k | 589k | 498k | 5.54k | 20.0 yr |
| 5 | 2,354,386 | 2,366k | 394k | 721k | 583k | 0.09k | 20.0 yr |
| **6** | **2,078,409** | **3,507k** | **584k** | **958k** | **702k** | **0.00k** | 19.3 yr |

Three things in that table.

**Worst outstanding goes to zero.** 15.63k at three paying months, 5.54k at
four, 0.09k at five, and exactly **0** at six. The 2,078,409 subscribers who
paid above 170,000 Toman in all six months have never carried an unpaid
balance in the window. That is an observed fact, not a model output.

**They are not marginal.** Median 3,507k Toman paid over six months is 584k a
month against a 170k threshold, with a best single month of 958k.

**Tenure separates the barred.** At six paying months:

| longest one-way run | subscribers | median tenure |
|---|---|---|
| 0 | 2,078,409 | **19.3 yr** |
| 1 | 118,971 | 11.5 yr |
| 2 | 11,779 | 8.3 yr |
| 3 | 2,217 | **6.7 yr** |

19.3 years against 6.7. Tenure is a strong feature and it is already in the
pipeline as `age_on_net_months`.

## 3. The population, at each cut

All "never two-way barred in the window":

| rule | subscribers | vs 3M target | band two-way rate |
|---|---|---|---|
| pay 2+, one-way run ≤2 | 13,363,723 | 4.5× | 2.53 pct |
| pay 3+, one-way run ≤2 | 10,389,568 | 3.5× | 1.80 pct |
| pay 3+, one-way run ≤1 | 10,340,237 | 3.4× | 1.80 pct |
| pay 4+, one-way run ≤1 | 7,440,370 | 2.5× | 1.26 pct |
| pay 4+, never one-way | 7,062,735 | 2.4× | 1.26 pct |
| **pay 5+, never one-way** | **4,432,795** | **1.5×** | **0.82 pct** |
| pay 6 of 6, never one-way | 2,078,409 | 0.7× **short** | 0.40 pct |

## 4. The book, on an evidence-based limit

A subscriber who has already paid 958,000 Toman in one month has
demonstrated they can. That needs no affordability stance — the stance-based
method was voided by the credit-line reframe anyway.

| rule | subscribers | median limit | book |
|---|---|---|---|
| pay 6 | 2,078,409 | 958k | 1,990 bn |
| **pay 5+** | **4,432,795** | **832k** | **3,688 bn** |
| pay 4+ | 7,062,735 | 742k | 5,237 bn |
| pay 3+ | 9,806,435 | 662k | 6,487 bn |
| pay 2+ | 12,580,944 | 589k | 7,408 bn |
| pay 1+ | 16,172,364 | 513k | 8,290 bn |

**A convergence worth noting.** The affordability method, before it was
retired, put the maximum book near 8,800 bn Toman. This arrives at 8,290 bn
from a completely different direction — what subscribers have already been
observed to pay in a single month. Two independent routes to the same order
of magnitude is worth more than either alone.

And it still falls well short of 15,000 bn. **The ceiling is not the model.**

## 5. Recommendation

**Screen: paid ≥170,000 Toman in 5 or 6 of the last 6 months, never one-way
barred, never two-way barred. 4,432,795 subscribers.**

- 1.5× the 3,000,000 target, so there is room to select within it
- band two-way rate 0.82 pct
- book 3,688 bn Toman at the median best month

Not pay 6 of 6: 2,078,409 is **short** of the target, so it cannot be met from
that group at all. Not pay 4+: it reaches 7,062,735, but the band rate rises
from 0.82 to 1.26 pct — 53 pct more risk for volume already in surplus.

## 6. What the model is now for, and what is still missing

The screen above already delivers the target at a sub-1 pct observed bar rate,
**without a model.** So the model's job is no longer to find the population —
it is to rank within those 4.4 million so the limit can be varied, the worst
tail declined, and the book priced. That is a smaller and much better posed
problem than the one this project started with.

**The one thing still missing is out-of-time validation.** Every rate above is
contemporaneous: payment and bar status come from the same six months. A real
model predicts the *next* months from the *previous* ones, and no number here
tests that. The data supports it — payments are continuous from 140301, so
features from 140407–140412 against outcomes in 140501–140506 is available and
is the next thing to build. Until it exists, 0.82 pct is an association and
not a forecast.

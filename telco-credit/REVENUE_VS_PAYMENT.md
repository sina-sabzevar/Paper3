# Revenue against payment — and why the screen changes

Measured on `40_revenue_matrices.xlsx`, window 140501–140506. Sheets 2 and 3
are duplicates (H3 exported twice), so the output is H2, H3, H4, H5, H6.

## 1. I predicted revenue would be flatter. It is steeper.

| months | revenue n | rate | payment n | rate |
|---|---|---|---|---|
| 1 | 3,235,980 | 5.3 pct | 4,177,966 | 7.0 pct |
| 2 | 2,236,108 | 3.7 pct | 3,145,130 | 5.1 pct |
| 3 | 1,877,589 | 2.7 pct | 3,015,647 | 3.2 pct |
| 4 | 1,939,092 | 1.6 pct | 2,838,806 | 2.0 pct |
| 5 | 1,666,179 | 1.0 pct | 2,518,193 | 1.2 pct |
| **6** | 2,369,007 | **0.2 pct** | 2,220,513 | **0.4 pct** |
| | | **26.5× lift** | | 17.5× lift |

My reasoning was that revenue would be diluted by cash payers who never had a
bill to default on. Wrong. **Being engaged every month is a stronger statement
than making a payment every month.**

## 2. The two axes are complementary, not redundant

Two-way rate, revenue down, payment across:

| rev\pay | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| **0** | 4.2 | **7.9** | 4.8 | 2.6 | 1.5 | 0.9 | 0.4 |
| **1** | 4.8 | **7.9** | 6.9 | 3.9 | 2.2 | 1.2 | 0.6 |
| **2** | 1.3 | 4.1 | 6.5 | 4.7 | 2.6 | 1.5 | 0.7 |
| **3** | 0.6 | 2.0 | 3.6 | 4.4 | 2.8 | 1.6 | 0.8 |
| **4** | 0.3 | 1.0 | 1.9 | 2.3 | 2.3 | 1.4 | 0.6 |
| **5** | 0.2 | 0.5 | 1.1 | 1.3 | 1.3 | 1.4 | 0.5 |
| **6** | **0.1** | 0.1 | 0.2 | 0.3 | 0.3 | 0.3 | 0.2 |

Within `rev_months = 6` the rate barely moves with payment — 0.1 to 0.3 pct
across the whole range. Once a subscriber earns above 170k every month, how
they pay adds almost nothing.

Within `rev_months = 0` payment separates **20-fold**, 7.9 down to 0.4 pct.

So revenue dominates where it is high, and payment is what separates the
low-revenue mass. The model wants both.

## 3. `pay_months = 0` is the safest column, at every revenue level

| revenue months | pay 0 | rate | pay = rev | rate | ratio |
|---|---|---|---|---|---|
| 2 | 233,451 | 1.3 pct | 427,392 | 6.5 pct | 5.0× |
| 3 | 125,778 | 0.6 pct | 395,752 | 4.4 pct | 7.3× |
| 4 | 86,590 | 0.3 pct | 492,043 | 2.3 pct | 7.7× |
| 5 | 51,152 | 0.2 pct | 530,193 | 1.4 pct | 7.0× |
| 6 | 47,283 | **0.1 pct** | 1,210,748 | 0.2 pct | 2.0× |

The reason is in what they generate against what they pay:

| rev | pay | subscribers | median revenue 6m | median paid 6m | paid/revenue |
|---|---|---|---|---|---|
| 6 | 0 | 47,283 | 2,690k | 297k | **11 pct** |
| 6 | 6 | 1,210,748 | 2,647k | 4,426k | 167 pct |

`rev 6 / pay 0` generate 2,690k Toman over six months with 297k of recorded
payment. **Their bills are being settled through a channel that is not in
`v_fact_pmnt_adjmt`** — someone else pays, or the method is not captured. They
are the safest cell in the entire grid at 0.1 pct, and a payment-based screen
rejects every one of them.

This is the same coverage hole as the 50 pct payment-row finding seen from the
other side, and it is larger than cash alone explains.

The reverse case: `paid/revenue` of 167 to 181 pct in the high-payment cells.
Those subscribers pay more than they generate, which is arrears settlement or
payment for services outside the SIM.

## 4. The riskiest large cell

| rate | subscribers | rev | pay | reading |
|---|---|---|---|---|
| **7.9 pct** | 2,699,020 | 0 | 1 | almost no revenue, one large payment |
| 7.9 pct | 799,251 | 1 | 1 | same signature |
| 6.9 pct | 704,389 | 1 | 2 | minimal revenue, sporadic payment |

About 3.5 million subscribers at 7.9 pct. Low engagement plus one substantial
payment is the signature of **paying down a debt**, not of a healthy user. A
payment-only screen ranks them *above* the dormant `pay_months = 0` group. The
revenue axis is what exposes them.

## 5. The zero-revenue bucket is a third missing data

| rev months | subscribers | null arpu months | share of their months |
|---|---|---|---|
| 0 | 27,946,137 | 55,968,453 | **33.4 pct** |
| 1 | 3,235,980 | 143,233 | 0.7 pct |
| 6 | 2,369,007 | 0 | 0 pct |

56,219,749 null months, 9,369,958 subscriber-equivalents, essentially all
inside `rev_months = 0`. So roughly a third of that bucket is *revenue not
recorded* rather than *no revenue*. It mixes dormant SIMs with unmeasured ones.

At `rev_months = 6` the null count is exactly 0, by construction — a NULL month
cannot clear 170,000 Toman.

## 6. Band rates, at every cut

| cut | revenue n | rate | payment n | rate |
|---|---|---|---|---|
| 6 | 2,369,007 | 0.20 pct | 2,220,513 | 0.40 pct |
| **5+** | **4,035,186** | **0.53 pct** | 4,738,706 | 0.83 pct |
| 4+ | 5,974,278 | 0.88 pct | 7,577,512 | 1.27 pct |
| 3+ | 7,851,867 | 1.31 pct | 10,593,159 | 1.82 pct |

Revenue gives a lower band rate at every cut.

## 7. The screen changes

**Previously recommended:** pay 5+ of 6, never one-way, never two-way —
4,432,795 subscribers.

That screen **rejects the safest cell in the grid** (47,283 at `rev 6 / pay 0`,
0.1 pct) while keeping 530,193 at `rev 5 / pay 5` at 1.4 pct. The ordering is
wrong.

**Revised:** `rev_months >= 5` of 6, never one-way barred, never two-way
barred, **with no payment-months condition at all**.

| | |
|---|---|
| subscribers | **3,804,977** (1.3× the 3,000,000 target) |
| band two-way rate | **0.53 pct** against 0.83 pct for the payment screen |

Intersecting the two — `BOTH rev 5+ AND pay 5+` — gives 2,550,070, which is
**short** of the target *and* worse, because the payment leg discards the best
subscribers.

**Payment months stay as a model feature,** where the H6 grid shows they earn
their place: within `rev_months = 0` they separate 7.9 pct from 0.4 pct. As a
*screen* they invert the ordering.

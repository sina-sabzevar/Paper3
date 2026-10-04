# The product is a credit line, not a telco loan — what that voids

The credit funds VOD subscriptions, bill payments and other services the
operator cannot see, and settles on the SIM bill. Settlement is at the
customer's choice: in full at month end, or converted to instalments.

## What this voids

Every affordability table produced before this sized the loan as a share of
telco revenue — instalment ≤ 30/40/50 pct of monthly revenue. **That logic is
void.** It assumed the money is spent on telco, so telco spend measures
capacity. It does not. A subscriber spending 200,000 Toman a month on telco
may draw 2,000,000 for VOD and bills, and whether they can repay 2,000,000
depends on household income, which is in no table here.

Specifically retired:

- `LOAN_BOOK_15TN.md`'s affordability grid (4,478 / 6,156 / 7,613 bn at 30 /
  40 / 50 pct stances). The stances have no basis once the spend is off-net.
- The conclusion that 15,000 bn "does not fit at six instalments". It was
  derived from telco-revenue affordability and does not survive the reframe.
- The band tickets in `LABEL_FRONTIER.md` (2,250,000 / 1,500,000 / 1,000,000),
  which were 12 instalments at a 50 pct revenue stance.

What survives: every **population count**, because those are measured. 9,017,158
subscribers with revenue over 170,000 in two or more of four months is a fact
about the data and does not depend on what the credit is spent on.

Telco spend demotes from a capacity measure to an **engagement and discipline**
signal — still predictive, no longer dispositive.

## What replaces it

Because settlement can be in full at the customer's option, risk must be sized
on the worst case: **the whole limit arriving on one bill.** So the right unit
is not instalment-to-income. It is the **multiple of the subscriber's own
normal bill** that they have been shown to carry.

And that is already measured in the history. Over 140301–140506, thirty
continuous months, subscribers have been billed amounts far above their own
normal. Some settled those months, some did not. It is a natural experiment on
exactly the question the product asks, and it needs no pilot.

`35_spike_settlement.sql` extracts it. The headline column is
**`max_ratio_settled`** — the largest multiple of their own baseline a
subscriber has demonstrably cleared. A subscriber who has already settled a
month five times their normal bill is evidence for a limit at five times their
normal bill. One who has never cleared more than 1.2 times is not, however
large their telco spend.

## The label

**`y_spike_fail_2x`** — a month at two or more times their own baseline
obligation where the outstanding balance was still material at the end of the
following month. Two chances: the month itself and the next.

The two-way bar is carried alongside as an objective corroborating signal, not
as the definition. If the two disagree sharply, one of them is not measuring
default and that needs to be known before either is trusted.

## Why the baseline is a median and not a mean

A spike inflates the mean it is being measured against, so a mean baseline
hides exactly the months the metric exists to find. Tested on four constructed
subscribers:

| subscriber | behaviour | max ratio, median base | max ratio, mean base | failure caught? |
|---|---|---|---|---|
| A | flat | 1.00 | 1.00 | n/a |
| B | settled a 5× month | 5.00 | 3.00 | n/a |
| C | left a 5× month open | 5.00 | 2.31 | both |
| D | left a 2× month open | 2.00 | 1.52 | **median only** |

On the mean baseline D's failure is missed entirely — the ratio falls to 1.52
and never trips the 2× test. The SQL uses `APPROX_PERCENTILE(due_approx, 0.5)`.

## What has to be checked before any of this runs

`bill_outstanding_amt` is the column the whole label rests on, and it was **not**
in the A1 health check — I asked for seven columns and left it out. `S0` checks
it across ten months rather than one, because `debt_scr` looked fine in a single
month and turned out to be all-zero in six of ten. If `bill_outstanding_amt` is
dead the same way, this approach dies with it and the label falls back to the
two-way bar.

## One approximation, named

`due_approx = paid + outstanding`. The exact obligation needs the `monthly Bill`
type from `v_fact_cust_bil_daily`, whose VARCHAR key is still unresolved — `D2`
in `31_bill_type_resolved.sql` has not been run. `paid + outstanding` needs no
bill-type resolution and is sufficient to rank a subscriber's months against
their own baseline, which is all a self-referential ratio requires. It would
not be sufficient for an absolute obligation figure.

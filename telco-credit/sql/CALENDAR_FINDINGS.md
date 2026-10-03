# Month inventory — what M1 and M2 established

Measured, not inferred. Source: `12_month_inventory.sql`, run 1405-07.

## Two of my assumptions were wrong

**1. Data does not start at 140401.** Both fact tables are complete and
continuous from **140301** to **140506**, with 140507 partial (ends 14050709,
so "now" is about 1405-07-09). I had been treating 1403 as unavailable and
built every window on a six-month 1404 runway that did not need to be that
tight. There are **30 complete months** available, not 6.

**2. `invoice_amt` is not loaded every month.** It is loaded in only 14 of the
30 closed months:

| run | months | length |
|---|---|---|
| 140301..140304 | Farvardin–Tir 1403 | 4 |
| 140306 | Shahrivar 1403 | 1 |
| 140311 | Bahman 1403 | 1 |
| **140410..140505** | **Dey 1404 – Mordad 1405** | **8** |

In 140402..140409 it is literally **0**. In the loaded months it sits at
26–28M positive rows against 28–29M active permanent subscribers, so coverage
there is genuine and near-complete — this is a loading gap, not a semantic one.

## This was the cause of the 1371 rows

`med_invoice` in STEP 1 ends in

```sql
HAVING APPROX_PERCENTILE(invoice_amt, 0.5) FILTER (WHERE invoice_amt > 0) > 0
```

over the feature window **140401..140406** — which contains **zero** loaded
months. So `med_invoice` was NULL for essentially everyone and the inner join
deleted the base. Moving the dates to 1405 landed on the eight-month loaded run,
which is why the same query then returned 11.5M.

Neither the revenue formula nor the status codes nor the tenure gate were the
cause. Those were three real bugs found along the way and worth fixing, but they
were not this.

## What is healthy everywhere

`bill_outstanding_amt` in the **daily** table is populated in every single
month: 597M–666M positive-balance rows per month, consistently. This matters
more than it sounds, because **the label is built on the daily balance, not on
`invoice_amt`**. So the label can be built over any window; only the
materiality yardstick is constrained.

The monthly table holds exactly one row per subscriber per month
(`n_rows == n_subs` in every month), so the `GROUP BY sbrp_id, month_key` with
`MAX`/`SUM` inherited from the original pipeline was never necessary.

Jalali month lengths are confirmed by the daily `last_day` column: months 1–6
end at 31, months 7–11 at 30, and 140412 ends at **14041229**, so 1404 is not a
leap year. The day-31 upper bound used throughout `recalendar.py` is safe.

## `payable_amt` has the identical gap — it is the table, not the column

`payable_amt` is the correct column of the two, and its coverage was re-measured
per month. **Zero months disagree with `invoice_amt`:** same loaded runs
(140301..140304, 140306, 140311, 140410..140505), same zeros across
140312..140409 and at 140506. In the broken months `payable_amt` is exactly 0
where `invoice_amt` held a few thousand stray rows, but the shape is the same.

So this is a **loading gap in the monthly fact's billing columns**, not a
column-naming mistake, and no choice of monthly billing column escapes it.
Switching to `payable_amt` is still correct and has been done — it is the right
column — but it is not a fix for the calendar.

## The consequence for the materiality floor

`0.40 * med_invoice` is the threshold the whole label rests on — what counts as
a material unpaid balance. Anchoring it on `invoice_amt` makes the calendar
hostage to a loading gap. The fix is to anchor it on something loaded every
month. Two candidates, in order of preference:

1. **The month-maximum of the daily `bill_outstanding_amt`.** This is the bill
   just after issuance, which is what `invoice_amt` was standing in for in the
   first place. STEP 2's rollup already computes `bill_out_max` per
   subscriber-month, so the quantity exists; it only needs to be available
   *before* the threshold is applied, which means splitting the rollup into a
   raw pass and a thresholded pass.
2. **`pmnt_amt`** — the typical monthly payment. Simpler, but it measures what
   the subscriber chose to pay rather than what they were billed, so it is a
   weaker yardstick for materiality. Coverage not yet measured.

### Done: the yardstick now comes from the daily table

STEP 1 no longer computes `med_invoice`. A new **STEP 1B** builds
`dcb3_billref.med_bill` from the daily balance:

* per subscriber-month, `MAX(bill_outstanding_amt)` over the feature window;
* then the **median** of those monthly maxima.

The month-maximum is the right proxy because the bill for month M-1 is issued at
the end of M-1, so on day 1 of M the balance *is* that bill and it falls to zero
on payment. A month carrying an unpaid earlier bill shows two stacked and a high
maximum, which is why the median across the subscriber's own months is used
rather than the mean or the max — one carry-over month cannot move it.

Every `0.40 *` and `1.5 *` threshold in the rollup, and the label that rests on
them, now reads `med_bill`. The panel's `invoice_m1..m6` became
`payable_m1..m6`. STEP 7 was also reading raw `age_on_net_months` from the
monthly table, which reintroduced the NULL that STEP 1 repairs; it now reads the
recovered value from `dcb3_base`.

Cost: one extra daily pass over the feature window. Unavoidable — the threshold
has to exist before it can be applied at day level, and once a month is rolled
up the day detail needed for `debt_days` is gone.

### Still blocking: do payments and revenue share the gap?

`13_monthly_column_coverage.sql` measures `payable_amt`, `pmnt_amt`, the revenue
blocks and the usage columns per month. Payments and revenue are monthly-only —
nothing in the daily table can replace them — so this result decides the
calendar and nothing else should be locked until it lands.

If they share the billing gap, the only usable monthly window is the eight
months 140410..140505, with the shock sitting at 140412/140501/140502 right
across the middle of it, and the design has to shrink to something like three
feature months with T0 at 140501. If they are loaded throughout, the shock-free
C1 below is available.

## Candidate calendars, once the yardstick no longer constrains them

With 30 months available and the shock at 140412 / 140501 / 140502:

| | T0 | features | bill months | watch to | shock contact |
|---|---|---|---|---|---|
| **C1** | **140405** | 140311..140404 | 140405..140408 | 140411 | **none** |
| C2 | 140412 | 140406..140411 | 140412..140503 | 140506 | whole window |

C1 is strictly better than the 140407 cohort I had been planning: it is
completely clear of the shock, where 140407 put 140501 inside the watch tail.
C2 is worth building as the stress holdout — it measures how much the model
degrades when the shock lands on the outcome, which is the closest thing
available to a forward-looking test.

Both become possible only because 1403 is in fact available. The old constraint
that "no cohort is free of the shock" was an artefact of the wrong start date.


---

# The bill source is settled: `v_fact_cust_bil_daily.payment_due_amt`

Measured over 140301..140506 with `cust_bil_typ_id = 2`:

* **Complete in all 30 months.** 22.7M to 27.4M positive bills per month,
  growing monotonically, no gap anywhere — including 140312..140409, where the
  monthly fact's `payable_amt` and `invoice_amt` are both empty.
* `n_days = 1` in **every** month, and `first_day = last_day` = the month's last
  day. The `MOD(day_key,100) >= 28` cost guard is therefore valid and stays.
* Month ends confirm the Jalali lengths the tooling assumes: months 1–6 end on
  31, 7–11 on 30, month 12 on 30 in 1403 and **29** in 1404 — so 1403 is a leap
  year and 1404 is not. The day-31 upper bound in `recalendar.py` covers both.
* Keyed by `sbrp_id`, so it joins directly. No customer-to-SIM bridge.

**The calendar is no longer constrained by the bill.** One thing still is: the
revenue gate, the payment features and the usage features still read the monthly
fact, and their per-month coverage has never been measured. `S1` in
`15_sizing_and_coverage.sql` settles it. If they are healthy in 140311..140404,
the shock-free C1 (T0 = 140405) is available.

# The number that matters more than the calendar

The end-of-cycle bill distribution, month 140506:

| | Toman |
|---|---|
| median monthly bill | **47,410** |
| p90 monthly bill | **178,900** |
| network ARPU as quoted | 130,000 |

ARPU sitting 2.7x above the median is consistent — telco spend is heavily
right-skewed, and the maximum bill here is around 12 billion Toman, clearly
corporate. But it means **ARPU is the wrong number to plan the product
against**. Half of the postpaid base bills under 48,000 Toman a month.

Against that, the stated minimum ticket of 400,000 Toman over four instalments
is **100,000 Toman a month**:

* for the **median** subscriber that is **2.11x their entire monthly bill**;
* for the **p90** subscriber it is **0.56x** their monthly bill.

The bill a subscriber needs for the instalment to stay within a given share of
it:

| instalment as share of bill | required monthly bill | where that sits |
|---|---|---|
| 30 pct | 333,000 Toman | above p90 |
| 40 pct | 250,000 Toman | above p90 |
| 50 pct | 200,000 Toman | above p90 |
| 70 pct | 143,000 Toman | below p90 |
| 100 pct — the bill doubles | 100,000 Toman | below p90 |

So on any prudent affordability stance the 400,000 Toman ticket only fits
subscribers **above the 90th percentile**, which is under 2.8M of the 27.4M
billed base before any risk screening at all. Reaching **3 million loans at a
400,000 Toman minimum** therefore requires an affordability stance near
**70 pct of the monthly bill** — a payment shock that will show up as real
defaults, and exactly the regime the `shock_uplift_k` term in the notebook's
limit engine was written to penalise.

At a prudent 40 pct stance, the ticket that fits the population is closer to
**200,000 Toman**, needing a bill of 125,000 Toman, which sits below p90.

`S2` gives the full distribution and the counts at each stance, so this is sized
on the real book rather than on two percentiles. This is a business decision, not
a modelling one: **budget, loan count and minimum ticket are over-constrained**,
and something has to give — the ticket, the count, or the risk appetite.

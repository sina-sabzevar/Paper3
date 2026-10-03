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

`13_monthly_column_coverage.sql` measures the coverage of `pmnt_amt`, the
revenue blocks and the usage columns per month. That result decides both the
yardstick and the calendar, so it is the next thing to run.

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

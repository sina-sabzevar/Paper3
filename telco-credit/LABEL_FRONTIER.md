# The label: how loose can it go

Measured, from `test_all_1.xlsx` sheet `C` — the full 5×5 joint distribution of
revenue months against payment months, 40,734,185 subscribers, both over
170,000 Toman, months 140503–140506.

|  | pay 0 | pay 1 | pay 2 | pay 3 | pay 4 | total |
|---|---|---|---|---|---|---|
| **rev 0** | 26,395,036 | 1,507,533 | 389,505 | 48,155 | 8,015 | 28,348,244 |
| **rev 1** | 1,182,062 | 1,426,440 | 615,289 | 134,458 | 10,534 | 3,368,783 |
| **rev 2** | 560,491 | 602,637 | 792,001 | 349,853 | 40,601 | 2,345,583 |
| **rev 3** | 361,695 | 322,021 | 606,216 | 749,693 | 207,862 | 2,247,487 |
| **rev 4** | 424,368 | 328,886 | 590,176 | 1,149,211 | 1,931,447 | 4,424,088 |
| total | 28,923,652 | 4,187,517 | 2,993,187 | 2,431,370 | 2,198,459 | 40,734,185 |

## The frontier

Screening on revenue, labelling on payment:

| screen | eligible | vs 3M | bad if label = pay ≥1 | pay ≥2 | pay ≥3 |
|---|---|---|---|---|---|
| rev months ≥ 1 | 12,385,941 | 4.1× | 20.4 pct | 42.1 pct | 63.1 pct |
| **rev months ≥ 2** | **9,017,158** | **3.0×** | **14.9 pct** | **28.8 pct** | 50.9 pct |
| rev months ≥ 3 | 6,671,575 | 2.2× | 11.8 pct | 21.5 pct | 39.5 pct |
| rev months ≥ 4 | 4,424,088 | 1.5× | 9.6 pct | 17.0 pct | 30.4 pct |

Payment-based screens are deliberately absent. Screening on the same variable
that defines the label reads as a 0 pct bad rate and means nothing.

## What each point of bad rate buys

Taking rev ≥ 4 as the anchor, on the `pay ≥ 1` label:

| loosening to | extra subscribers | extra bad rate | subscribers per point |
|---|---|---|---|
| rev ≥ 3 | +2,247,487 | +2.2 pct | 103 million |
| **rev ≥ 2** | **+4,593,070** | **+5.3 pct** | **86 million** |
| rev ≥ 1 | +7,961,853 | +10.8 pct | 74 million |

The trade worsens monotonically, and it worsens sharply at rev ≥ 1. **rev ≥ 2
is where the curve bends.**

## The recommendation

**Screen on revenue months ≥ 2. Label on the four-month payment total, not on
a count of months.**

That admits 9,017,158 subscribers, three times the 3,000,000 target, which is
the point: the model's job becomes selecting the safest 3,000,000 out of
9,000,000. A screen admitting barely enough leaves the model nothing to choose
between, and every selection decision then falls to the screen.

Against rev ≥ 4, this costs 5.3 points of bad rate and buys 4.6 million more
subscribers. Against rev ≥ 1, it saves 5.5 points and gives up 8.0 million —
the worse half of that trade.

**Why the label must be sum-based.** Sheet `C` counts months over a threshold.
The loan is repaid out of the four-month total, not out of any single month. A
subscriber who pays 500,000 once and nothing for three months satisfies
"pay ≥ 1 of 4" and defaults on instalments two, three and four. So the loosest
label available from `C` is also the least meaningful one. The project already
paid for a month-count label once: `n_late_out >= 2` produced a 36 pct bad
rate that turned out to be ordinary lumpiness.

`34_label_frontier.sql` measures the sum-based version off `dcb_sample_base`,
with each band tested against **its own** ticket's four instalments, since the
ticket differs by band and one flat threshold would reject the small tickets
and flatter the large:

| band | median monthly revenue | ticket (12 inst, 50 pct stance) | instalment | 4 instalments |
|---|---|---|---|---|
| 4 | 397,193 | 2,250,000 | 195,000 | 780,000 |
| 3 | 259,529 | 1,500,000 | 130,000 | 520,000 |
| 2 | 190,601 | 1,000,000 | 86,667 | 346,668 |

## Two things these numbers are not

**They are contemporaneous, not predictive.** `dcb_sample_base` holds revenue
and payment for the same four months, so a bad rate computed from it describes
an association. A model predicts the *next* months from the *previous* ones,
which is strictly harder. Every figure above is a **floor** on what a real
model faces, not an estimate of it.

**They observe 4 instalments of 12.** A subscriber can carry four and fail the
eighth. Four months is what a T0 of 140503 allows; payments are continuous from
140301, so a T0 twelve months back would give a full-term outcome and is worth
building before go-live.

## Payments must use all statuses

Every figure here uses `q1a..q4a`. `bllg_pmnt_stat_id = 2` holds 61.2 pct of
payment value and status 1 holds 38.7 pct, so the filter this project carried
throughout discards over a third of the money. Measured: 11,202,782 subscribers
clear two months on all statuses against 7,623,016 on status 2 alone — a third
of them lost to a filter that was never verified.

# Assumption register

Every fact this pipeline depends on, with its status and where it came from.

**The rule: no SQL may be written that depends on an UNCONFIRMED row.** Every
mistake in this project so far came from breaking that rule — a fact I invented,
stated as if it described the data, and then built on.

## CONFIRMED by Sina

| # | Fact | Where it is used |
|---|---|---|
| 1 | `sbrp_stat_id`: 2 active, 3 one-way bar, 4 **two-way bar**, 8 reclaim queue, 9 reclaimed | gates, rollup, label |
| 2 | 8 and 9 are reached only after ~5–6 months inactive **while in debt** | excluded from the project entirely, by business rule |
| 3 | 8 and 9 subscribers never enter the project | STEP 1 anti-join over the full window |
| 4 | Permanent = `sbrp_typ_id = 1`, active = `sbrp_stat_id = 2` | STEP 1 snapshot |
| 5 | A one-way bar has **one** cause: non-cash usage crossing the SIM credit ceiling. There is no non-payment one-way bar | killed `rule3_nonpay_bar` |
| 6 | `available_credit` **is** that ceiling | STEP 7, limit benchmark |
| 7 | Usage is cash or non-cash. Cash **never** reaches the bill; non-cash does | `noncash_share_6m` |
| 8 | `tot_rev` month M = **total** usage of M, cash and non-cash | panel |
| 9 | `bill_outstanding_amt` = issued bill, due the 15th of next month, **and the debt it becomes after that**. Zeroed by any payment including mid-cycle | DPD, label |
| 10 | `unbill_outstanding_amt` = that bill plus the running month's usage | ceiling utilisation |
| 11 | `cust_bil_typ_id`: 2 end-of-cycle bill (last day of month only), **3 mid-cycle bill** | `med_bill`, `obligation_6m` |
| 12 | `payment_due_amt` at end of M = usage **of M**, due 15th of M+1 | yardstick alignment |
| 13 | `payment_due_amt` is **net** of cash and mid-cycle payments — a residual | killed my ticket sizing |
| 14 | `v_fact_cust_bil_daily` is keyed by `sbrp_id` | direct join, no bridge |
| 15 | `pmnt_amt` on `v_fact_pmnt_adjmt` = payments landing on the bill; prepaid credit is irrelevant while `sbrp_typ_id = 1` | `paid_total`, capacity |
| 16 | Capacity basis = **total payments** (`paid_total`) | Sina's decision |
| 17 | Revenue columns are in **Rial** | the 1,000,000 floor = 100k Toman |
| 18 | Engine is Trino/Presto | `FILTER`, `MAX_BY`, `APPROX_PERCENTILE` |
| 19 | Revenue shock at 140412, 140501, 140502 | cohort choice |

## CONFIRMED by measurement

| # | Fact | Evidence |
|---|---|---|
| 20 | Both facts complete 140301..140506; 140507 ends 14050709 | M1, M2 |
| 21 | Monthly `invoice_amt` and `payable_amt` loaded in only 14 of 30 months, empty 140312..140409, **identical** gap | M1 + the payable re-run |
| 22 | Monthly `pmnt_amt` holed in exactly 140402, 140403 | S1 |
| 23 | Revenue and usage columns whole in all 30 months | S1 |
| 24 | Daily `bill_outstanding_amt` whole in all 30 months | M2 |
| 25 | `payment_due_amt` type 2 whole in all 30 months, one day per month | the cust_bil probe |
| 26 | Monthly fact is one row per subscriber-month | M1 (`n_rows == n_subs`) |
| 27 | Jalali: months 1–6 end 31, 7–11 end 30, month 12 ends 30 in 1403 and 29 in 1404 | M2 `last_day` |
| 28 | Total monthly payments: median 83,172 Toman, p90 344,301 | S2 |
| 29 | 3,991,092 subscribers can carry a 400k ticket at a 40 pct stance | S2 |

## UNCONFIRMED — nothing may be built on these

| # | Open question | Blocks | How it gets answered |
|---|---|---|---|
| A | What `cust_pmnt_typ_id` values mean | nothing — the filter is removed | P2 |
| B | Whether `bllg_pmnt_stat_id = 2` for "successful" is right. **Carried over unverified and still in the WHERE** | `paid_total` completeness | P2, P3 |
| C | Is bill type 3 really spread across the month | `mc_billed_6m` | P1 |
| D | Does any other `cust_bil_typ_id` carry value | `obligation_6m` completeness | P1 |
| G | **Does `cust_bil_typ_id = 3` exist at all.** `mc_billed_6m` came back entirely NULL, so either the code is wrong or mid-cycle bills are not in this table. Until settled, every mid-cycle feature is unavailable rather than zero | `mc_billed_6m`, `midcycle_billed_share` | `27_bill_types.sql` |
| H | Two values were offered as the real mid-cycle and end-of-cycle bill codes: `823067872317374799613180673527768019589` + 8 zeros (47 digits) and `9831165778317776083127656705155381027647` + 8 zeros (48 digits). **Not substituted.** BIGINT holds 19 digits and Trino's DECIMAL 38, so neither fits a numeric `cust_bil_typ_id`; 47 is prime so the shorter cannot split into equal-width ids while the longer can split four ways, so the two do not share a shape. `27_bill_types.sql` T0 reports the column's declared type and T1 prints every code present, cast to VARCHAR so nothing is lost to exponent form | every mid-cycle and end-of-cycle feature | `27_bill_types.sql` |
| E | Is `v_fact_pmnt_adjmt` whole over 140407..140412 | every payment feature | P4 |
| F | How `available_credit` compares to my reconstruction | whether to drop the reconstruction | after extraction |

## RETRACTED — things I asserted that were wrong

| Claim | Reality |
|---|---|
| `cust_pmnt_typ_id` 4 = end of cycle, 6 = mid cycle | My invention. Data contradicts it. |
| 9 = two-way bar | It is 4. 9 is a reclaimed number. |
| Ceiling = components × 1.2 | The 1.2 was invented. `available_credit` is the real column. |
| One-way bars split into non-payment vs ceiling | Only one mechanism exists. |
| Data starts 140401 | It starts 140301. |
| `1 − billed/tot_rev` is mid-cycle intensity | It is the cash share. |
| Shock in features over-lends | It under-lends. The shock was a revenue drop. |
| Median bill 47k Toman means the 400k ticket fits <10 pct | That was a residual bill, not capacity. 3.99M fit at a 40 pct stance. |
| Mid-cycle is ~25 pct of outlay | An inference from `bill_to_paid`, never established. |
| A 5-15 pct bad rate is the target | **My own convention**, borrowed from consumer-credit scorecards. Not a requirement. The real bad rate here is 1-2 pct and the label must not be loosened to meet a borrowed number. `rule3_nonpay_bar` was exactly that mistake: it counted ceiling breaches as delinquency and inflated the rate artificially. |
| The 36 pct figure at all | It was a BUG, not a loose definition. `run_len` is one row per debt run; joining it to a per-month relation fanned every month out once per run and multiplied every SUM and COUNT. A subscriber paying around the 15th has six runs, so their counters came out six times too large - lateness of 36 in a 6-month window, 927 debt days in a 180-day one. `y_v1`, `y_v2`, `y_loose`, `y_twoway_any2m` were all affected. Anything built on MAX was never wrong, so `y_severe` 2.22 pct, `y_strict` 1.22 pct and `y_twoway_2m` 1.16 pct stand. |
| 36 pct of the base is bad | No. That is `n_late_out >= 2` - paid after the 15th in two of six months, which is ordinary telco behaviour. Real delinquency is 2.22 pct (two-way bar), 1.22 pct (DPD>=60), 1.16 pct (two-way in two consecutive months). |

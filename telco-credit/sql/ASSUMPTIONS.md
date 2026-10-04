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
| P1 | **The credit is not spent on telco.** It funds VOD, bill payments and other off-net services, and settles on the SIM bill, with settlement in full or by instalments at the customer's choice. Telco revenue therefore does NOT measure capacity - every affordability stance derived from it is void. Risk is sized on the worst case, the full limit on one bill, so the unit is the multiple of the subscriber's OWN normal bill that they have been shown to carry | all affordability tables; `LOAN_BOOK_15TN.md` grid; `LABEL_FRONTIER.md` tickets | stated by Sina |
| P2 | Label is **`y_spike_fail_2x`**: a month at 2x or more of the subscriber's median obligation where the outstanding balance was still material at the end of the FOLLOWING month. The two-way bar is corroboration, not the definition | the model's target | `35_spike_settlement.sql` |
| P3 | **`bill_outstanding_amt` is unverified** and was omitted from the A1 health check. The spike label rests entirely on it. `S0` checks it across ten months, since `debt_scr` looked fine in one month and was all-zero in six of ten. If it is dead, the label falls back to the two-way bar | the whole spike approach | `35_spike_settlement.sql` S0 |
| B | **ANSWERED, AND THE FILTER IS WRONG.** `bllg_pmnt_stat_id` measured over 140503..140506: status `2` holds 137,699 bn Rial, status `1` holds **86,987 bn** across 23.8M subscribers, `3` holds 309 bn, `-2` holds 0. Filtering `= 2` discards **38.8 pct of all payment value**. Measured effect: subscribers with 2+ months over 170k Toman fall from 11,202,782 (all statuses) to 7,623,016 (status 2 only) - 3,579,766 lost, 32 pct | `paid_total` and every payment feature | `test_all_1.xlsx` sheet `b2`, `R3-3` |
| B2 | **`debt_scr` and `suspend_scr` are ALL ZERO in 6 of 10 months** (11 distinct values in 140409, 140411, 140412, 140503; exactly 1 in the other six, and `n_zero = n_rows = 39,830,450` at 140506). That is the entire explanation for their PSI of 13.89 and 14.41 - a loading gap, not drift. **Drop both features**; re-binning cannot help a column that is zero | 2 of the 80 features | `test_all_1.xlsx` sheet `A2`, `A1` |
| B3 | **`arpu` is 23.8 pct NULL** (30,352,192 non-null of 39,830,450). The KPI revenue definition is `arpu - tot_arpu_tax_amt`, so for 9.5M subscribers it evaluates to minus the tax. `age_on_net_months` has min **-232** and max 1,285; `available_credit` has min **-3,643,635,807** and max **40,944,005,245,667** Rial (4.1 trillion Toman) | revenue, tenure, the operator credit ceiling | `test_all_1.xlsx` sheet `A1` |
| B4 | The base is larger than assumed: **39,830,450 permanent**, **30,345,860 Active1**, against the 24,000,000 stated in conversation | every population count | `test_all_1.xlsx` sheets `R1`, `A1` |
| C | Is bill type 3 really spread across the month | `mc_billed_6m` | P1 |
| D | Does any other `cust_bil_typ_id` carry value | `obligation_6m` completeness | P1 |
| G | **Does `cust_bil_typ_id = 3` exist at all.** `mc_billed_6m` came back entirely NULL, so either the code is wrong or mid-cycle bills are not in this table. Until settled, every mid-cycle feature is unavailable rather than zero | `mc_billed_6m`, `midcycle_billed_share` | `27_bill_types.sql` |
| H | `cust_bil_typ_id` is **VARCHAR**, 48 characters, so a quoted literal matches it directly. Resolved against the dimension in `info.xlsx`: mid-cycle is **Hot Bill**, `unq_id_in_src_sys` `'7'`; end-of-cycle is **monthly Bill**, `'5'`. The end-of-cycle value on record matches that row. The mid-cycle value supplied is 47 characters and an order of magnitude small - a character lost in transit - so as a literal it matches nothing. Take literals from a GROUP BY on the fact, not from a spreadsheet: a spreadsheet parses the text as a number and float64 keeps about 17 significant digits | `ec_billed_6m`, `mc_billed_6m`, `obligation_6m` | `info.xlsx`, `BILL_TYPES.md` |
| G-CAUSE | **Register item G is answered.** `mc_billed_6m` was entirely NULL because `cust_bil_typ_id = 3` matched **zero rows** - no dimension row has a surrogate id of 2 or 3. The pipeline's end-of-cycle filter `= 2` matched nothing either. `D2` in `31_bill_type_resolved.sql` confirms which encoding the fact table carries before the filter is replaced | both bill filters | `31_bill_type_resolved.sql` |
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

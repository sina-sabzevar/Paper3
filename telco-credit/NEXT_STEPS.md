# Runbook — from here to a book you can defend

Everything below works on the tables you already have. **No `42` re-run, no
re-export.** Roughly 30 minutes, most of it the notebook re-fit.

Run the steps in order. Each one says what to check before moving on.

---

## Step 1 — re-run the training notebook

One edit, in section 1 of `notebook/train_model.ipynb`:

```python
FEATURE_SET = "scale_free"      # it ships as "full"
```

Then run the notebook top to bottom.

**Why.** `validate_model.ipynb` measured the trade on your data: full **0.8278**,
scale-free **0.8230**. That 0.0048 buys immunity from inflation. The full
model's 0.8278 is an *upper bound* on live performance — twelve of its features
drift, `rev_max` at PSI 3.0223 — while a scale-free feature cannot drift at all,
so 0.8230 is an *estimate*. Trading a bounded number for an unbounded one is the
right direction.

**What to check:**

| | expect |
|---|---|
| `SCALE-FREE: 34 features, dropped 26 carrying a Rial level` | the switch took |
| `FEATURE DRIFT` section | far fewer than 12 significant |
| `TEST in band` AUC | near **0.8230** |
| `mean predicted PD` on the live set | much closer to **0.5146 pct** than the full model's 0.5952 |
| `distinct pd_4m values ... sit on a shared value` | a new line; note the number |

That last gap closing **is** the drift, measured in the number the business
reads. If it does not close, something else is moving and it needs chasing
before the book is cut.

This run also writes `pay_cover` and `tenure_m` into
`outputs/handover_scores.csv`. Step 2 needs them.

---

## Step 2 — re-cut the book

```bash
cd telco-credit/notebook
python3 select_book.py
```

**Why this is not optional.** The book you have now was cut by
`sort_values("pd_4m")`, which settles ties by CSV row order — an accident of
how the parquet parts concatenated. The validation measured the step at the
cut: **579,159 subscribers, 12.40 pct of the book, 290 bn Toman**, admitted or
refused by nothing. The script now orders on

```
pd_4m asc, pay_cover desc, tenure_m desc, sbrp_id asc
```

**What to check:** the `tie at the cut` block it now prints. Whatever the number
is, it travels with the book when you hand it over — those subscribers are not
ranked by risk.

Expect a different ladder from the one on record. 0.1790 pct was the full
model's book PD; scale-free scores are different scores.

---

## Step 3 — clean up Trino

The handover table holds two full sets of scores. Measure it first so its state
is on the record, then rebuild.

```sql
-- sql/50_handover_repair.sql
H1    -- how bad is it: n_rows, n_subs, n_surplus
H2    -- rows per subscriber: 2 confirms the double load
H3    -- how far apart the two models were on the same subscriber
H4    -- DROP TABLE dwbi_temp40_db.DCB_Handover140506
```

Then load once, from a script that cannot append:

```bash
cd telco-credit/notebook
python3 push_scores.py
```

It drops before it creates, types `pd_4m` as `DOUBLE`, carries `pay_cover` and
`tenure_m`, and refuses on a duplicate `sbrp_id` or a null `pd_4m`. If you load
through your `IQ` wrapper instead, guard it — `IQ.insert_df` **appends**, which
is what produced the double load:

```python
import IQ
h = pd.read_csv("outputs/handover_scores.csv")
h["pd_4m"] = h["pd_4m"].astype(float)
assert len(h) == 9_344_723,           f"expected 9,344,723 rows, got {len(h):,}"
assert h["sbrp_id"].is_unique,        "duplicate sbrp_id"
assert h["pd_4m"].notna().all(),      "null pd_4m"
assert h["pd_4m"].between(0, 1).all(), "pd_4m outside [0, 1]"
# the table must NOT exist - drop it first, or this appends again
IQ.insert_df(h, 'dwbi_temp40_db.DCB_Handover140506')
```

```sql
H5, H6   -- verify: rows, uniqueness, no nulls, and that a numeric sort
         -- and a text sort agree (they do not if pd_4m is VARCHAR)
```

**What to check:** `rows_ok`, `unique_ok` and `sort_ok` all read `1`.

---

## Step 4 — build the book in Trino

```sql
-- sql/51_book_cut.sql
C1   -- how many sit on the step at the cut, BEFORE cutting
C2   -- CREATE dwbi_temp40_db.dcb_book with rank_in_book
C3   -- rows_ok, unique_ok, rank_ok
C4   -- sorted_ok: n_inversions must be 0
```

It carries the same `ORDER BY` as `select_book.py`, so the two routes return
the same people. `pay_cover` is read from `dcb_score` rather than `dcb_pd` —
same formula, same source, and `dcb_score` is authoritative.

**What to check:** all four flags read `1`, and `n_on_cut_step` matches what
Step 2 printed.

---

## Step 5 — the one query that has never run

```sql
-- sql/49_base_reconciliation.sql
B1, B2, B5   -- is the 26M permanent base active1_base_flag, or another typ_id?
B3, B4       -- how many SCORED subscribers were never active in the window,
             -- and do they carry a different event rate?
```

The screen filters on revenue and the two service bars. **It does not filter on
activity.** If B4 shows never-active subscribers carrying a materially different
rate, activity belongs in the screen and the book needs re-cutting again — so
run this before lending, not after.

---

## Then the decisions, which are not mine

1. **How big a book.** Under a 0.25 pct ceiling the refit admits **7,122,466**,
   up 1,346,737. You chose 4,672,361 against a worse risk curve. Worth
   revisiting — not because 4.67M is wrong, but because it was chosen against
   different numbers.
2. **Line size.** 15,000 bn across 9,344,723 is 1,605,184 Toman each; across the
   chosen book it is 3,210,368. At 500,000 the whole scored population reaches
   4,672 bn. No model moves this.
3. **Whether the bar stays nominal.** Fixed in Rial, it has loosened
   12.0 → 14.6 → 18.4 → 24.4 pct on its own. Left alone it keeps going.
4. **A pilot.** Nobody in this data was ever given spendable credit. The
   0.2 pct is the right number for the population; it is not a promise about a
   product that has never run.


---

# Revised runbook — after the DCB change

The earlier steps assumed the four-month product. The label has changed, so
**the dataset and the model both have to be rebuilt**. One cycle, not two —
everything below should go in before `42` runs.

## Already in the generator, not yet run

| change | why |
|---|---|
| label is `140408`, one month | the product is one-month DCB; `140407` is the draw month and belongs to neither features nor label |
| `LABEL_EVENT = "twoway"` | a one-way bar restricts telco usage, which a DCB default cannot cause |
| `n_zero_rev_months` | a zero-billing month in the window is **7.7×** riskier and nothing looked for it |
| `DRAW_SKIP`, `TERM_MONTHS` | declared and guarded, so a label quietly widened back is rejected |

## The cycle

**1. `sql/42_model_datasets.sql`** — rebuilds both tables. All structural
guards pass. Expect `dcb_model` to shrink in events, not rows: the one-month
label gives about **19,215** against the four-month 45,361.

**2. Get the tables to the notebook.** Two routes, same output:

- `python3 notebook/fetch_dcb.py` — pulls both tables through `IQ.Get_DF`
  and writes the same parquet files the notebook globs. Skips the export and
  the file transfer entirely. Use this if IQ reaches Trino from the machine
  the notebook runs on.
- `sql/47_export_parts.sql` — the export route, if it does not.

Both split on `BITWISE_AND(hash, 1)`, so the files are interchangeable.

**Either way, the usual next step — concatenating the two parquet parts into a
single CSV and training from that — now works without editing anything.**
`EXPECT` counts parts per extension: two parquet files, or one CSV. A genuinely
missing parquet part still stops the run.

One thing the CSV route needs and the parquet route does not: **`sbrp_id` has to
stay an integer.** The split is `md5(str(sbrp_id)) mod 100`, and
`str(9891234567)` is not `str(9891234567.0)` — a float column puts a different
set of subscribers in train, valid and test, with nothing to show for it. The
loader now casts it back and says so, and refuses outright if the column is
float *and* has nulls, because that cannot be fixed by casting.

**3. `notebook/train_model.ipynb`** with:

```python
FEATURE_SET         = "scale_free"   # costs 0.0048 AUC, immune to inflation
DROP_AVAIL_FEATURES = True           # before any second-cycle scoring
```

The second one matters more than it did a week ago: granting DCB raises
`available_credit` by the grant, so from cycle two those columns describe our
own decision rather than the subscriber.

**4. `notebook/select_book.py`** — the tie-break is already in. Re-cut.

**5. `sql/51_book_cut.sql`** — build `dcb_book` in Trino with the same order.

## What does NOT need rebuilding

The **premium is not a model feature.** The model predicts a subscriber's base
risk at their normal bill; the limit engine multiplies by the premium the draw
implies — 1.13 under 2× the bill, 1.91 at or above it. Keeping that outside the
model means it can be re-measured, or changed as a policy, without a refit.

The same goes for the limit ladder and the screen bar. Those are product
decisions sitting on top of a ranking, not parameters of it.

## Expect these to move

| | before | after |
|---|---|---|
| event rate | 0.5213 pct | **0.2208 pct** |
| TEST AUC | 0.8278 | lower — a thinner label is harder |
| book PD | 0.1790 pct | roughly a third of it |

A one-month label has 42 pct of the events. Do not read a fall in AUC as the
model getting worse until it is compared against the one-month base rate
rather than the four-month one.

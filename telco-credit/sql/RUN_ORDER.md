# Run order — and why a stale table breaks the assembly

## What just went wrong

`dcb3_dataset_c1` failed on `mc_billed_6m` even though the SQL file has that
column only once. The file was not the problem: **`dcb3_panel` on the warehouse
was built by an earlier run and physically still has the old column.** STEP 9
reads the tables that exist, not the file.

That is my fault for not saying it. Over the last few rounds I changed the
output schema of nearly every intermediate table — status codes, the bar split,
the bill source, the calendar, three column renames — and never said that the
chain has to be rebuilt. Running steps one at a time left a mix of old and new
tables that cannot be joined.

## Which tables are stale

Every one of them. The output schema of each changed:

| table | what changed in it |
|---|---|
| `dcb3_base` | tenure recovered from NULL, 8/9 excluded, `med_invoice` gone |
| `dcb3_billref` | **new table**, and later rebuilt on bill types 2 and 3 |
| `dcb3_daily_rollup` | status codes fixed, bar split removed, `queue_days`/`reclaim_days` added |
| `dcb3_dpd` | calendar moved |
| `dcb3_bars` | nonpay/ceiling counts removed, `n_ceiling_months_6m` added |
| `dcb3_panel` | `payable_m*` → `billed_m*`, `pmnt_m*` removed, `mc_billed_6m` removed, `n_months_seen` → `n_months_panel`, `noncash_share_6m` added |
| `dcb3_pay` | mid-cycle columns removed, type filter removed |
| `dcb3_pit` | `available_credit` added, `age_on_net_months` removed, ceiling rebuilt |
| `dcb3_label` | rule3 gone, `n_months_seen` → `n_months_out`, terminal exclusion |

So: **drop and rebuild in order.** Each `CREATE TABLE` in the file is preceded
by its own `DROP TABLE IF EXISTS`, so re-running a step is safe.

## The order

```
STEP 1   dcb3_base            gates
STEP 1B  dcb3_billref         needs dcb3_base
STEP 2   dcb3_daily_rollup    needs dcb3_billref  (the 0.40 threshold)
         -- SKIP STEP 2b. Trino has MAX_BY.
STEP 3   dcb3_dpd             needs dcb3_daily_rollup
STEP 4   dcb3_bars            needs dcb3_daily_rollup
STEP 5   dcb3_panel           needs dcb3_base
STEP 6   dcb3_pay             needs dcb3_base
STEP 7   dcb3_pit             needs dcb3_base
STEP 8   dcb3_label           needs dcb3_daily_rollup
STEP 9   dcb3_dataset_c1      needs all of the above
```

STEP 2 is the expensive one — the single daily pass. Steps 3 to 8 all read
tables, not the daily fact, except STEP 6 which reads the payments fact.

## Check BEFORE running STEP 9

Do not discover a collision by failing the assembly. This reads the real
tables, so it is authoritative in a way that reading the SQL file is not —
my own parse of the file said "no duplicates remain" while a stale table on the
warehouse still carried one.

```sql
SELECT   column_name, COUNT(*) AS in_n_tables,
         ARRAY_AGG(table_name ORDER BY table_name) AS tables
FROM     information_schema.columns
WHERE    table_schema = 'dwbi_temp40_db'
  AND    table_name IN ('dcb3_base','dcb3_billref','dcb3_label','dcb3_dpd',
                        'dcb3_bars','dcb3_panel','dcb3_pay','dcb3_pit')
  AND    column_name <> 'sbrp_id'
GROUP BY column_name
HAVING   COUNT(*) > 1
ORDER BY 2 DESC;
```

Empty result means STEP 9 will not hit a duplicate-name error. `sbrp_id` is
excluded because the join is `USING (sbrp_id)`, which emits it once.

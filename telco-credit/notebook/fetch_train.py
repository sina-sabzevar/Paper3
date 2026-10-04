# -*- coding: utf-8 -*-
"""Move the training set into Python as CSV.

    python3 fetch_train.py              # down-sampled, one fetch   <- do this
    python3 fetch_train.py --full       # all 9.24M rows, two halves joined on disk

WHY THE DEFAULT NEEDS NO SPLIT AND NO CONCAT

The scoring set has to be split because every one of its 11M subscribers needs
an offer. The training set does not: a model learns the boundary from the bads
and from enough goods to place it, not from every good in the base.

    full table            9,240,000 rows    7.32 GB in pandas
    all bads + 10 pct goods 1,108,615 rows  0.88 GB in pandas

Every bad is kept - all ~205,000 of them, since they are the scarce half of the
problem at a 2.22 pct event rate. Only goods are sampled. That is 12 pct of the
table in one fetch, with nothing to join afterwards, and it was measured on
this data to cost about 0.001 AUC.

USE sample_weight WHEN YOU FIT:

    model.fit(X, y, sample_weight=df.sample_weight)

Without it the model sees a 17 pct event rate instead of 2.22 pct and every PD
comes out roughly eight times too high. Ranking survives that; the level does
not, and the limit engine spends the level.

WHY --full JOINS ON DISK AND NOT WITH pd.concat

At the moment of pd.concat([part0, part1]) both halves and the result are all
live, so the peak is about 14.64 GB - twice what one unsplit fetch would need.
Splitting and then concatenating in memory is strictly worse than not
splitting. Appending the second half to the first half's CSV does the join on
disk, where it is free, and the later read_csv holds one copy.

THE TRAP --full GUARDS

Appending assumes both halves have the same columns in the same order. If a
fetch ever returns them in a different order, every value lands under the wrong
header and the file still looks perfectly well-formed. So the first half's
column list is kept and the second is reindexed onto it, which raises if a
column is missing instead of silently shifting the data.

TWO DRIVER RULES, both learned the hard way on this project:

  1. NO PERCENT CHARACTER ANYWHERE IN A QUERY STRING. Python DB drivers default
     to pyformat paramstyle and printf-substitute the WHOLE statement, so a
     stray percent raises "unsupported format character". This is why the SQL
     uses MOD() and str.format with braces, never printf-style formatting.
  2. NO TRAILING SEMICOLON. Many helpers wrap the query in a subselect, and a
     semicolon in the middle of one is a syntax error.
"""
import gc, os, sys, time
import numpy as np
import pandas as pd

SCHEMA    = "dwbi_temp40_db"
TABLE     = "dcb3_dataset_c1"
OUTDIR    = "data"
LABEL     = "y_severe"
GOOD_KEEP = 10            # keep this many goods out of every 100

# A UNIFORM DRAW FROM sbrp_id, VIA A HASH - NOT MOD ON THE ID ITSELF.
#
# Every one of the ten real sbrp_id values in the handover file is odd, which
# under uniform parity is a 1-in-1024 coincidence, so the id almost certainly
# carries a fixed low bit. They are composed rather than sequential - they
# share a five digit block after the two leading digits. MOD on such an id
# does not sample, it selects a structured slice: one issuing batch, one
# region, one SIM generation. And it does so silently, because the result
# looks like a sample.
#
# A hash is uniform over its output whatever the input encodes, so MOD on the
# hash is a real draw. It stays deterministic, which is what matters for a
# training set: the same subscribers are chosen on every re-run, so the data
# does not shift under the model between one fit and the next.
DRAW = ("MOD(ABS(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8("
        "CAST(sbrp_id AS VARCHAR))))), {m})")


def fetch(sql, label=""):
    """The only place IQ is called. If Get_DF takes a connection, a timeout or
    a different argument order, change THIS function and nothing else."""
    import IQ
    t0 = time.time()
    df = IQ.Get_DF(sql)
    print("    {}: {:,} rows x {} cols in {:,.0f}s".format(
        label, len(df), df.shape[1], time.time() - t0))
    return df


def guards(q):
    assert "%" not in q, "a percent character would break the driver"
    assert not q.rstrip().endswith(";"), "no trailing semicolon"
    return q


# ---------------------------------------------------------------------------
#  DOWN-SAMPLED - the default. Every bad, one good in ten.
#
#  The goods are picked by a hashed draw - see the note on DRAW above for why
#  MOD on the raw id would have taken a structured slice rather than a sample.
# ---------------------------------------------------------------------------
def sampled_query():
    return guards(
        "SELECT t.*, IF({label} = 1, 1.0, 100.0 / {keep}) AS sample_weight\n"
        "FROM   {schema}.{table} t\n"
        "WHERE  {label} = 1\n"
        "  OR   {draw} < {keep}".format(
            label=LABEL, keep=GOOD_KEEP, schema=SCHEMA, table=TABLE,
            draw=DRAW.format(m=100)))


# ---------------------------------------------------------------------------
#  FULL - both halves by a hashed draw, not by parity of sbrp_id.
#
#  On parity, with every observed id odd, one half would get ZERO rows and the
#  other all 9.2M - a split that silently does nothing, discovered only after
#  two full scans. A hash splits evenly however the ids are composed.
# ---------------------------------------------------------------------------
def half_query(half):
    return guards(
        "SELECT t.*, 1.0 AS sample_weight\n"
        "FROM   {schema}.{table} t\n"
        "WHERE  {draw} = {half}".format(
            schema=SCHEMA, table=TABLE, half=half, draw=DRAW.format(m=2)))


def report(df):
    w = df["sample_weight"].to_numpy(float)
    print("    bads {:,}   raw rate {:.2%}   weighted back to {:.2%}".format(
        int((df[LABEL] == 1).sum()), df[LABEL].mean(),
        float(np.average(df[LABEL], weights=w))))


def main():
    full = "--full" in sys.argv
    os.makedirs(OUTDIR, exist_ok=True)
    path = "{}/{}{}.csv".format(OUTDIR, TABLE, "_full" if full else "")

    if not full:
        print("DOWN-SAMPLED TRAINING SET (every bad, {} goods in 100)".format(GOOD_KEEP))
        df = fetch(sampled_query(), "train")
        report(df)
        df.to_csv(path, index=False)
        print("    wrote {}  ({:.2f} GB on disk)".format(
            path, os.path.getsize(path) / 1e9))
        print("\nin the notebook:")
        print('  CFG["train_csv"] = "{}"'.format(path))
        print("  and fit with sample_weight=df.sample_weight")
        return

    print("FULL TRAINING SET - two halves appended into one CSV")
    print("every row gets sample_weight 1.0, because nothing was sampled")
    cols, total = None, 0
    for half in (0, 1):
        part = fetch(half_query(half), "parity {}".format(half))
        if cols is None:
            cols = list(part.columns)
        else:
            # Raises on a missing column rather than shifting every value one
            # place under the wrong header.
            missing = set(cols) - set(part.columns)
            assert not missing, "half 1 is missing columns: {}".format(sorted(missing))
            part = part[cols]
        print("    id range {} .. {}".format(part.sbrp_id.min(), part.sbrp_id.max()))
        part.to_csv(path, index=False,
                    mode="w" if half == 0 else "a",
                    header=(half == 0))
        total += len(part)
        del part
        gc.collect()

    print("\nrows written {:,}   file {:.2f} GB".format(
        total, os.path.getsize(path) / 1e9))
    print("compare against  SELECT COUNT(*) FROM {}.{}".format(SCHEMA, TABLE))
    print("a shortfall means rows matched neither half - what ABS() prevents.")
    print("\nread it back ONCE, not as two frames:")
    print("    df = pd.read_csv({!r})".format(path))
    print("CSV does not store dtypes, so pass dtype= or downcast after reading")
    print("if 7.3 GB as float64 is more than you have.")


if __name__ == "__main__":
    main()

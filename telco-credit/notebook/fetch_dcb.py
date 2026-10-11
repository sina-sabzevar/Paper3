# -*- coding: utf-8 -*-
"""Pull dcb_model and dcb_score out of Trino and leave them ready to train on.

    python3 fetch_dcb.py

ONE LOOP, BOTH TABLES, ONE RUN. It replaces 47_export_parts.sql, the file
transfer, and the by-hand concatenation that followed - for both tables.

OUTPUT picks what it leaves behind:

    "single_csv"      one csv per table.  The default, and what the notebook
                      has been trained from.
    "single_parquet"  one parquet per table. Same thing but faster to read and
                      it keeps the column types - see THE DTYPE TRAP below.
    "parts"           two parquet parts per table, as 47 writes them.

Any of the three loads without editing the notebook: EXPECT counts files per
extension, two parquet or one csv.

WHY IT STILL FETCHES IN HALVES whatever the output is. dcb_score is around
9.3M rows by 46 columns; pulling it in one statement is where this falls over.
The halves are a hash split, so each is a random half rather than a slice of
the network, and for a single-file output they are STREAMED - half one is
written, released, then half two is appended. Both halves are never in memory
at once, which is the whole point of splitting.

THE DTYPE TRAP, and why "single_parquet" is the safer default if you have a
choice. The train/valid/test split is md5(str(sbrp_id)) mod 100, so the TYPE
of sbrp_id is part of the answer: str(9891234567) is '9891234567' but
str(9891234567.0) is '9891234567.0', and those hash to different buckets. A
csv does not carry the type, and on some pandas versions one blank cell turns
the column to float on the way back in. The notebook catches it and casts it
back - but a parquet never loses it in the first place.

THE SPLIT IS THE SAME ONE 47 USES: BITWISE_AND on a hashed id, not MOD.
Trino's MOD takes the sign of the DIVIDEND, so MOD(signed_hash, 2) returns
-1, 0 or 1 and a split on =0 and =1 silently drops about a quarter of the
table. The hash and not the raw id, because every observed sbrp_id in this
base is odd and they share a five-digit block.

THE TWO DRIVER RULES, asserted before anything is sent: no percent character,
which breaks the driver, and no trailing semicolon.
"""
import gc
import os
import sys
import time

import pandas as pd

SCHEMA = "dwbi_temp40_db"
TABLES = ("dcb_model", "dcb_score")
OUTDIR = "data"
OUTPUT = "single_csv"        # single_csv | single_parquet | parts
HALVES = 2

HALF = ("SELECT * FROM {schema}.{table} "
        "WHERE BITWISE_AND(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8("
        "CAST(sbrp_id AS VARCHAR)))), 1) = {half}")


def guards(q):
    assert "%" not in q, "a percent character would break the driver"
    assert not q.rstrip().endswith(";"), "no trailing semicolon"
    return q


def fetch(sql, label=""):
    """The only place IQ is called. If Get_DF takes a connection, a timeout or
    a different argument order, change THIS function and nothing else."""
    import IQ
    t0 = time.time()
    df = IQ.Get_DF(guards(sql))
    print("      {}: {:,} rows x {} cols in {:,.0f}s".format(
        label, len(df), df.shape[1], time.time() - t0))
    return df


def one_table(table):
    """Fetch every half and write whatever OUTPUT asks for. Returns a summary."""
    rows = 0
    ids = set()
    cols = None
    written = []

    for half in range(HALVES):
        df = fetch(HALF.format(schema=SCHEMA, table=table, half=half),
                   "half {}".format(half))
        if df.empty:
            sys.exit("half {} of {} came back empty. A split that puts "
                     "everything on one side is the signature of a hash "
                     "problem, not of an empty table.".format(half, table))

        if cols is None:
            cols = list(df.columns)
        elif list(df.columns) != cols:
            # Same table and same SELECT, so this should not happen - but if it
            # does, appending would silently shift every value one column over.
            missing = set(cols) ^ set(df.columns)
            if missing:
                sys.exit("half {} of {} has different columns: {}".format(
                    half, table, sorted(missing)))
            df = df[cols]

        rows += len(df)
        ids.update(df.sbrp_id.tolist())

        if OUTPUT == "parts":
            path = os.path.join(OUTDIR, "{}_p{}.parquet".format(table, half + 1))
            df.to_parquet(path, index=False)
            written.append(path)
        elif OUTPUT == "single_csv":
            path = os.path.join(OUTDIR, "{}.csv".format(table))
            # header only on the first half, append after that: the two halves
            # are never both in memory.
            df.to_csv(path, index=False, mode="w" if half == 0 else "a",
                      header=(half == 0))
            if half == 0:
                written.append(path)
        elif OUTPUT == "single_parquet":
            # parquet cannot be appended to, so the halves are staged and
            # joined at the end - the one case where both are briefly on disk.
            path = os.path.join(OUTDIR, ".stage_{}_{}.parquet".format(table, half))
            df.to_parquet(path, index=False)
            written.append(path)
        else:
            sys.exit("OUTPUT must be single_csv, single_parquet or parts")

        del df
        gc.collect()

    if OUTPUT == "single_parquet":
        final = os.path.join(OUTDIR, "{}.parquet".format(table))
        joined = pd.concat([pd.read_parquet(p) for p in written],
                           ignore_index=True)
        joined.to_parquet(final, index=False)
        del joined
        gc.collect()
        for p in written:
            os.remove(p)
        written = [final]

    return rows, len(ids), written


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print("OUTPUT = {}   into {}".format(OUTPUT, os.path.abspath(OUTDIR)))
    summary = []
    for table in TABLES:
        print("\n  {}".format(table))
        rows, ids, written = one_table(table)
        for p in written:
            print("      -> {}  ({:,} bytes)".format(p, os.path.getsize(p)))
        summary.append((table, rows, ids))

    print("\nWRITTEN")
    ok = True
    for table, rows, ids in summary:
        flag = ""
        if rows != ids:
            flag = "   <-- {:,} subscribers appear in BOTH halves".format(rows - ids)
            ok = False
        print("  {:<10} {:>12,} rows   {:>12,} distinct sbrp_id{}".format(
            table, rows, ids, flag))

    if not ok:
        sys.exit("\nA subscriber in both halves means the hash split is not a "
                 "partition. Do not train on this - every duplicated row is "
                 "counted twice and lands in whichever split the first copy "
                 "drew.")

    print("\nBEFORE THE NOTEBOOK")
    print("  Compare those row counts against T1 in 42_model_datasets.sql.")
    print("  They must match exactly. The notebook no longer asserts them -")
    print("  the label window changed and the new counts are not known in")
    print("  advance - so this is the only place the total meets its source.")
    print("\n  Then set DATA = {!r} in the notebook,".format(os.path.abspath(OUTDIR)))
    print("  or run it from the directory above {!r}.".format(OUTDIR))


if __name__ == "__main__":
    main()

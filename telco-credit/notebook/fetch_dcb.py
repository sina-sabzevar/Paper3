# -*- coding: utf-8 -*-
"""Pull dcb_model and dcb_score straight out of Trino, skipping the export.

    python3 fetch_dcb.py

WHAT THIS REPLACES. 47_export_parts.sql writes the two tables to files, those
files move to wherever the notebook runs, and the notebook globs them up. If
IQ reaches Trino from the same machine as the notebook, that whole round trip
is unnecessary: this fetches the tables directly and writes the SAME parquet
files the notebook already looks for. Nothing in the notebook changes.

WHY STILL WRITE FILES rather than hand the frames over in memory. Two reasons.
The fetch is the slow part and it should happen once, not on every notebook
restart. And the notebook's loader checks the part count, which is what caught
a half-finished export before - keeping the files keeps that check working.

THE SPLIT IS THE SAME ONE 47 USES. BITWISE_AND on a hashed id, not MOD: Trino's
MOD takes the sign of the DIVIDEND, so MOD(signed_hash, 2) returns -1, 0 or 1
and a split on =0 and =1 silently drops about a quarter of the table. The same
hash and the same halves mean these files are interchangeable with 47's.

NOT ON THE RAW ID. Every observed sbrp_id in this base is odd and they share a
five-digit block, so a parity split on the id puts everything in one half and a
hundred-modulus draw takes a structured slice of the network rather than a
sample.

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
PARTS  = 2          # must match EXPECT[...]["parts"] in the notebook

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
    print("    {}: {:,} rows x {} cols in {:,.0f}s".format(
        label, len(df), df.shape[1], time.time() - t0))
    return df


def main():
    if PARTS != 2:
        sys.exit("HALF splits in two. For a different part count, change the "
                 "predicate as well as PARTS.")
    os.makedirs(OUTDIR, exist_ok=True)
    summary = []

    for table in TABLES:
        print("\n{}".format(table))
        total = 0
        ids_seen = 0
        for half in range(PARTS):
            sql = HALF.format(schema=SCHEMA, table=table, half=half)
            df = fetch(sql, "half {}".format(half))
            if df.empty:
                sys.exit("half {} of {} came back empty. A split that puts "
                         "everything on one side is the signature of a hash "
                         "problem, not of an empty table.".format(half, table))
            path = os.path.join(OUTDIR, "{}_p{}.parquet".format(table, half + 1))
            df.to_parquet(path, index=False)
            print("      -> {}".format(path))
            total += len(df)
            ids_seen += df.sbrp_id.nunique()
            del df
            gc.collect()
        summary.append((table, total, ids_seen))

    print("\nWRITTEN")
    for table, total, ids in summary:
        flag = "" if total == ids else "   <-- a subscriber is in BOTH halves"
        print("  {:<10} {:>12,} rows   {:>12,} distinct sbrp_id{}".format(
            table, total, ids, flag))

    print("\nCHECK THESE BEFORE RUNNING THE NOTEBOOK")
    print("  Against T1 in 42_model_datasets.sql, the row counts must match")
    print("  exactly. The notebook no longer asserts them - the label window")
    print("  changed and the new counts are not known in advance - so this is")
    print("  the only place the total gets compared to the source.")
    print("\n  Then set DATA in the notebook to {}".format(
        os.path.abspath(OUTDIR)))
    print("  or run the notebook from the directory above it.")


if __name__ == "__main__":
    main()

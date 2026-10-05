# -*- coding: utf-8 -*-
"""Push handover_scores.csv back into Trino as dwbi_temp40_db.dcb_pd.

    python3 push_scores.py

WHY THE WHOLE SCORE SET AND NOT JUST THE APPROVED CUT. Uploading all 9,344,723
scores once makes the cut a SQL decision - "ORDER BY pd_4m LIMIT 4672361" - so
a different appetite, a different take, or a re-cut after the audit costs
nothing and needs no second upload. Uploading only the 4,672,361 would freeze
the decision into the data.

THE CONNECTION IS YOURS TO SUPPLY. This uses the DB-API that the trino package
exposes; if you reach Trino through your own IQ wrapper, replace connect()
below with whatever that provides and leave the rest alone. The only thing
this script needs is a cursor that executes SQL.

A FASTER PATH, if you have it. 9.3M rows through INSERT ... VALUES is minutes,
not seconds. If you can write to the warehouse's object store, writing the CSV
out as parquet and pointing an external table at it is far quicker. This route
is here because it needs nothing but a SQL connection.
"""
import os
import sys
import pandas as pd

SCORES = os.path.join("outputs", "handover_scores.csv")
SCHEMA = "dwbi_temp40_db"
TABLE  = "dcb_pd"
CHUNK  = 20_000          # rows per INSERT statement


def connect():
    """Return a DB-API connection. REPLACE THIS with your own if needed."""
    try:
        import trino
    except ImportError:
        sys.exit("the trino package is not installed. Either pip install "
                 "trino, or replace connect() with your IQ connection.")
    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", "localhost"),
        port=int(os.environ.get("TRINO_PORT", 8080)),
        user=os.environ.get("TRINO_USER", os.environ.get("USER", "unknown")),
        catalog=os.environ.get("TRINO_CATALOG", "hive"),
        schema=SCHEMA)


def main():
    if not os.path.exists(SCORES):
        sys.exit(f"{SCORES} not found - run the notebook first.")
    df = pd.read_csv(SCORES, usecols=["sbrp_id", "pd_4m", "grade"])
    print(f"read {len(df):,} scores from {SCORES}")

    # Guard the two things that would make the audit downstream meaningless.
    dup = len(df) - df.sbrp_id.nunique()
    if dup:
        sys.exit(f"{dup:,} duplicate sbrp_id in {SCORES} - every join "
                 f"downstream would fan out. Do not upload this.")
    if df.pd_4m.isna().any():
        sys.exit(f"{int(df.pd_4m.isna().sum()):,} null pd_4m - the cut would "
                 f"silently drop them.")
    print(f"  no duplicate sbrp_id, no null pd_4m")

    conn = connect()
    cur  = conn.cursor()
    full = f"{SCHEMA}.{TABLE}"

    cur.execute(f"DROP TABLE IF EXISTS {full}")
    cur.fetchall()
    cur.execute(f"CREATE TABLE {full} ("
                f"sbrp_id BIGINT, pd_4m DOUBLE, grade VARCHAR)")
    cur.fetchall()
    print(f"  created {full}")

    rows = list(df.itertuples(index=False, name=None))
    sent = 0
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i + CHUNK]
        vals = ", ".join(
            "({:d}, {:.10g}, '{}')".format(int(a), float(b), str(c))
            for a, b, c in batch)
        cur.execute(f"INSERT INTO {full} (sbrp_id, pd_4m, grade) VALUES {vals}")
        cur.fetchall()
        sent += len(batch)
        if (i // CHUNK) % 25 == 0 or sent == len(rows):
            print(f"    {sent:>10,} / {len(rows):,}", flush=True)

    cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT sbrp_id) FROM {full}")
    n, d = cur.fetchall()[0]
    print(f"\n{full}: {n:,} rows, {d:,} distinct sbrp_id")
    if n != len(df) or d != len(df):
        sys.exit(f"MISMATCH - uploaded {len(df):,} but the table holds "
                 f"{n:,} rows and {d:,} distinct ids. Do not run the audit "
                 f"against a partial upload.")
    print("matches the file exactly. Now run sql/48_approved_audit.sql.")


if __name__ == "__main__":
    main()

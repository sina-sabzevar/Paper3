# -*- coding: utf-8 -*-
"""Pull the training and scoring datasets out of the warehouse into parquet.

    python3 fetch_datasets.py

The scoring set is about 11M rows by 80 columns, too large to move in one go.
sql/28_split_scoreset.sql has already stored it as two tables, dcbs_scoreset_p1
and _p2; this script fetches one at a time, writes it to parquet and frees it
before the next - holding both at once in pandas would need roughly 7 GB as
float64. The split itself is NOT redone here: doing it in SQL means the row
counts and the overlap check were verified in the warehouse (S3 of that file)
before any of it moved.

TWO RULES THIS CODE FOLLOWS, both learned the hard way on this project:

  1. NO PERCENT CHARACTER ANYWHERE IN A QUERY STRING. Python DB drivers default
     to pyformat paramstyle and printf-substitute the WHOLE statement, so a
     stray percent raises "unsupported format character". Not in the SQL, not in
     a string literal, not in a comment inside the SQL.
  2. NO TRAILING SEMICOLON. Many helpers wrap the query in a subselect, and a
     semicolon in the middle of one is a syntax error.
"""
import gc, os, sys, time
import numpy as np
import pandas as pd

SCHEMA     = "dwbi_temp40_db"
TRAIN_TBL  = "dcb3_dataset_c1"
SCORE_TBLS = ["dcbs_scoreset_p1",     # written by sql/28_split_scoreset.sql
              "dcbs_scoreset_p2"]
OUTDIR     = "data"
GOOD_KEEP  = 10       # keep this percent of goods in the training fetch
LABEL      = "y_severe"


# ---------------------------------------------------------------------------
#  THE ONLY PLACE IQ IS CALLED. If Get_DF takes a connection, a timeout or a
#  different argument order, change THIS function and nothing else.
# ---------------------------------------------------------------------------
def fetch(sql, label=""):
    import IQ
    t0 = time.time()
    df = IQ.Get_DF(sql)
    print(f"    {label}: {len(df):,} rows x {df.shape[1]} cols "
          f"in {time.time()-t0:,.0f}s")
    return df


def shrink(df):
    """Halve the memory before writing. float64 -> float32 costs no precision
    that matters for features whose own measurement error is larger."""
    before = df.memory_usage(deep=True).sum() / 1e9
    for c in df.columns:
        if c == "sbrp_id":
            continue
        k = df[c].dtype.kind
        if k == "f":
            df[c] = df[c].astype("float32")
        elif k in "iu":
            df[c] = pd.to_numeric(df[c], downcast="integer")
    after = df.memory_usage(deep=True).sum() / 1e9
    print(f"    memory {before:.2f} -> {after:.2f} GB")
    return df


def _has_parquet():
    for m in ("pyarrow", "fastparquet"):
        try:
            __import__(m); return True
        except ImportError:
            pass
    return False

PARQUET = _has_parquet()


def write(df, stem):
    # Parquet is about a fifth the size of CSV and keeps the numeric types that
    # CSV throws away. It needs pyarrow or fastparquet, so if neither is
    # installed this falls back rather than failing after the fetch has already
    # been paid for - losing an 11M row query to a missing writer would be a
    # poor trade. `pip install pyarrow` is worth doing first.
    df = shrink(df)
    if PARQUET:
        path = stem + ".parquet"
        df.to_parquet(path, index=False, compression="snappy")
    else:
        path = stem + ".csv"
        df.to_csv(path, index=False)
    print(f"    wrote {path}  ({os.path.getsize(path)/1e9:.2f} GB on disk)")
    return path


# ---------------------------------------------------------------------------
#  TRAINING SET - down-sampled on the GOODS only.
#
#  Every bad is kept. At a 2.22 pct event rate the full 9.24M rows hold about
#  205,000 bads, and keeping all of them with 10 pct of goods gives roughly
#  1.1M rows. Measured on this data: that costs about 0.001 AUC.
#
#  sample_weight puts the base rate back. USE IT:
#      model.fit(X, y, sample_weight=df.sample_weight)
#  Without it the model sees a 17 pct event rate instead of 2.2 pct and every
#  PD comes out roughly eight times too high. Ranking survives; the level does
#  not, and the limit engine spends the level.
# ---------------------------------------------------------------------------
def train_query():
    return f"""
SELECT  t.*,
        IF({LABEL} = 1, 1.0, 100.0 / {GOOD_KEEP}) AS sample_weight
FROM    {SCHEMA}.{TRAIN_TBL} t
WHERE   {LABEL} = 1
   OR   MOD(ABS(sbrp_id), 100) < {GOOD_KEEP}
""".strip()


# ---------------------------------------------------------------------------
#  SCORING SET - every row is needed, because every subscriber needs an offer.
#
#  One plain read per stored half. The halves were cut on an exact sbrp_id
#  boundary in SQL, so they are contiguous and cannot overlap; the loop below
#  still checks, because a silent overlap would quietly score some subscribers
#  twice and leave others with no offer at all.
# ---------------------------------------------------------------------------
def score_query(table):
    return f"SELECT * FROM {SCHEMA}.{table}"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for q in [train_query()] + [score_query(t) for t in SCORE_TBLS]:
        assert "%" not in q, "a percent character would break the driver"
        assert not q.rstrip().endswith(";"), "no trailing semicolon"

    print("TRAINING SET")
    tr = fetch(train_query(), "train")
    n_bad = int((tr[LABEL] == 1).sum())
    w = tr["sample_weight"].to_numpy(float)
    print(f"    bads {n_bad:,}   raw rate {tr[LABEL].mean():.2%}   "
          f"weighted back {np.average(tr[LABEL], weights=w):.2%}")
    train_path = write(tr, f"{OUTDIR}/dcb3_dataset_c1")
    train_ids = set(tr["sbrp_id"].tolist()); del tr; gc.collect()

    print("\nSCORING SET")
    seen, total = set(), 0
    for i, tbl in enumerate(SCORE_TBLS, start=1):
        part = fetch(score_query(tbl), f"{tbl} ({i} of {len(SCORE_TBLS)})")
        ids = set(part["sbrp_id"].tolist())
        overlap = len(seen & ids)
        print(f"    id range {part.sbrp_id.min()} .. {part.sbrp_id.max()}   "
              f"overlap with earlier parts: {overlap:,}"
              + ("   <-- THE SPLIT IS WRONG" if overlap else "   OK"))
        seen |= ids; total += len(part)
        write(part, f"{OUTDIR}/dcbs_scoreset_part{i}")
        del part, ids; gc.collect()

    print(f"\nscoring rows {total:,}   distinct ids {len(seen):,}")
    if total != len(seen):
        print(f"    {total - len(seen):,} DUPLICATE ids - the parts overlap")
    print(f"training ids also in the scoring set: {len(train_ids & seen):,}")
    ext = "parquet" if PARQUET else "csv"
    if not PARQUET:
        print("\nNOTE: neither pyarrow nor fastparquet is installed, so these are")
        print("CSV - roughly five times the size, and the numeric types are lost")
        print("on the way back in. `pip install pyarrow` and re-run if you can.")
    print("\nin the notebook, set:")
    print(f'  CFG["train_csv"] = "{OUTDIR}/dcb3_dataset_c1.{ext}"')
    print(f'  CFG["score_csv"] = "{OUTDIR}/dcbs_scoreset.{ext}"')
    print("  load_parts globs the _part* files, concatenates them and checks")
    print("  for lost or duplicated rows on the way in.")


if __name__ == "__main__":
    main()

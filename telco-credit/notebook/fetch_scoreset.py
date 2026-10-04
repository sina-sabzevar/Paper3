# -*- coding: utf-8 -*-
"""Move the 11M-row scoring set into Python in two halves, by parity of sbrp_id.

    python3 fetch_scoreset.py

WHY PARITY AND NOT A WINDOW FUNCTION

MOD(sbrp_id, 2) splits the table with a single scan and a filter. The halves
are non-overlapping and exhaustive by construction - every id is even or odd,
and no id is both - so nothing has to be verified about the boundary. An
alternative using ROW_NUMBER() OVER (ORDER BY sbrp_id) would make the cluster
sort all 11M rows to learn something parity already gives for free.

ABS() is there because MOD in Trino keeps the sign of its argument: for a
negative id MOD(-3, 2) is -1, which matches neither 0 nor 1, and those rows
would be dropped from both halves without a trace. sbrp_id is very probably
always positive; ABS costs nothing and removes the question.

WHY THE HALVES ARE NEVER CONCATENATED

11M rows x 80 columns is about 7.0 GB as float64. At the moment of
pd.concat([part1, part2]) both halves AND the result are live, so the peak is
about 14.1 GB - twice what fetching the whole table in one call would need.
Concatenating would make the split worse than not splitting.

Scoring does not need the halves together. A PD is a function of one row, so
each half is scored on its own and only the two small (sbrp_id, pd) frames are
ever combined. That is 11M x 2, about 0.18 GB.

TWO DRIVER RULES, both learned the hard way on this project:

  1. NO PERCENT CHARACTER ANYWHERE IN A QUERY STRING. Python DB drivers default
     to pyformat paramstyle and printf-substitute the WHOLE statement, so a
     stray percent raises "unsupported format character". This is why the SQL
     says MOD(x, 2) and not x pct 2, and why str.format with braces is used
     for substitution rather than printf-style formatting.
  2. NO TRAILING SEMICOLON. Many helpers wrap the query in a subselect, and a
     semicolon in the middle of one is a syntax error.
"""
import gc, os, time
import pandas as pd

SCHEMA  = "dwbi_temp40_db"
TABLE   = "dcbs_scoreset"
OUTDIR  = "data"

# sbrp_id, not sbrp - the column is sbrp_id everywhere in the pipeline.
BASE = "SELECT * FROM {schema}.{table} WHERE MOD(ABS(sbrp_id), 2) = {half}"


def query(half):
    return BASE.format(schema=SCHEMA, table=TABLE, half=half)


def fetch(sql, label=""):
    """The only place IQ is called. If Get_DF takes a connection, a timeout or
    a different argument order, change THIS function and nothing else."""
    import IQ
    t0 = time.time()
    df = IQ.Get_DF(sql)
    print("    {}: {:,} rows x {} cols in {:,.0f}s".format(
        label, len(df), df.shape[1], time.time() - t0))
    return df


def shrink(df):
    """float64 -> float32 halves the file. It costs no precision that matters
    for features whose own measurement error is larger. sbrp_id is left alone:
    it is an identity, and float32 cannot hold a 9-digit integer exactly."""
    before = df.memory_usage(deep=True).sum() / 1e9
    for c in df.columns:
        if c == "sbrp_id":
            continue
        k = df[c].dtype.kind
        if k == "f":
            df[c] = df[c].astype("float32")
        elif k in "iu":
            df[c] = pd.to_numeric(df[c], downcast="integer")
    print("    memory {:.2f} -> {:.2f} GB".format(
        before, df.memory_usage(deep=True).sum() / 1e9))
    return df


def _parquet():
    for m in ("pyarrow", "fastparquet"):
        try:
            __import__(m)
            return True
        except ImportError:
            pass
    return False

PARQUET = _parquet()


def write(df, stem):
    # Parquet is about a fifth the size of CSV and keeps the numeric types CSV
    # throws away. If neither writer is installed this falls back to CSV rather
    # than failing after an 11M row fetch has already been paid for.
    df = shrink(df)
    path = stem + (".parquet" if PARQUET else ".csv")
    if PARQUET:
        df.to_parquet(path, index=False, compression="snappy")
    else:
        df.to_csv(path, index=False)
    print("    wrote {}  ({:.2f} GB on disk)".format(
        path, os.path.getsize(path) / 1e9))
    return path


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    for h in (0, 1):
        q = query(h)
        assert "%" not in q, "a percent character would break the driver"
        assert not q.rstrip().endswith(";"), "no trailing semicolon"

    total, ids_seen, paths = 0, set(), []
    for h, name in ((0, "even"), (1, "odd")):
        part = fetch(query(h), "{} ids".format(name))
        ids = set(part["sbrp_id"].tolist())

        # Parity cannot overlap, so this should be 0 by construction. It is
        # checked anyway: an overlap would score some subscribers twice and
        # leave others with no offer, and neither shows up downstream.
        overlap = len(ids_seen & ids)
        print("    id range {} .. {}   duplicate ids within half: {:,}"
              "   overlap with the other half: {:,}{}".format(
                  part.sbrp_id.min(), part.sbrp_id.max(),
                  len(part) - len(ids), overlap,
                  "   <-- WRONG" if overlap else "   OK"))

        total += len(part)
        ids_seen |= ids
        paths.append(write(part, "{}/{}_{}".format(OUTDIR, TABLE, name)))
        del part, ids
        gc.collect()

    print("\nrows fetched {:,}   distinct ids {:,}".format(total, len(ids_seen)))
    print("compare rows fetched against")
    print("    SELECT COUNT(*) FROM {}.{}".format(SCHEMA, TABLE))
    print("they must match exactly - a shortfall means rows matched neither")
    print("half, which is what ABS() in the query exists to prevent.")

    print("\nSCORE EACH HALF SEPARATELY. Do not concatenate them:")
    print("    out = []")
    print("    for p in {!r}:".format(paths))
    print("        d = pd.read_parquet(p) if p.endswith('.parquet') else pd.read_csv(p)")
    print("        out.append(pd.DataFrame({'sbrp_id': d.sbrp_id,")
    print("                                 'pd': model.predict_proba(d[FEATURES])[:, 1]}))")
    print("        del d; gc.collect()")
    print("    pd.concat(out, ignore_index=True).to_parquet('data/scores.parquet')")
    print("that concatenation is 11M x 2 columns, about 0.18 GB - safe.")
    print("concatenating the full halves instead would peak near 14 GB.")


if __name__ == "__main__":
    main()

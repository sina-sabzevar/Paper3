# -*- coding: utf-8 -*-
"""Move the 11M-row scoring set into Python in two halves, by parity of sbrp_id.

    python3 fetch_scoreset.py

WHY A HASH AND NOT PARITY OF sbrp_id

An earlier version of this split on MOD(ABS(sbrp_id), 2). That was wrong, and
the ten real sbrp_id values in the handover file show why: every one of them
is odd. Under uniform parity that is a 1-in-1024 coincidence, so sbrp_id
almost certainly carries a fixed low bit - a check digit, or an id derived as
something doubled plus one. These ids are composed, not sequential: they share
a five digit block after the two leading digits.

On a parity split, that means one half gets ZERO rows and the other gets all
11.5M. Measured on ids composed this way: 0 rows where half were expected. The
split silently does nothing, and it is only caught after paying for two full
scans of an 11.5M row table.

Not every modulus fails this way - MOD(id, 199) is unaffected, since 199 is
prime and coprime to 2 and 10 - but a hash removes the question instead of
depending on the modulus being lucky.

MOD on a hash has no such failure mode. MD5 and XXHASH64 are uniform over
their output whatever structure the input has, so the halves come out even
however the operator composes its ids. The halves are still non-overlapping
and exhaustive by construction - a hash maps each id to exactly one bucket -
so nothing has to be verified about a boundary.

WHY THE HALVES ARE NEVER CONCATENATED

11M rows x 80 columns is about 7.0 GB as float64. At the moment of
pd.concat([part1, part2]) both halves AND the result are live, so the peak is
about 14.1 GB - twice what fetching the whole table in one call would need.
Concatenating would make the split worse than not splitting.

Scoring does not need the halves together. A PD is a function of one row, so
each half is scored on its own and only the two small (sbrp_id, pd) frames are
ever combined. That is 11M x 2, about 0.18 GB.

Output is CSV. Each half lands near 3.3 GB, and read_csv returns float64
regardless of what shrink() did before writing, so pass dtype= on the way back
in if the halves are tight on memory.

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
# The hash, not the id: see the note above on every observed id being odd.
BASE = ("SELECT * FROM {schema}.{table} "
        "WHERE MOD(ABS(FROM_BIG_ENDIAN_64(XXHASH64(TO_UTF8("
        "CAST(sbrp_id AS VARCHAR))))), 2) = {half}")


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
    """float64 -> float32 halves what is held in memory while the half is live.
    CSV does not record it, so this buys headroom during the fetch, not a
    smaller file. It costs no precision that matters
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


def write(df, stem):
    # CSV, as asked. Two things it costs, both manageable:
    #   - about 2.5x the size of parquet, so each half lands near 3.3 GB
    #   - no dtypes, so read_csv gives float64 back whatever shrink() did here;
    #     pass dtype= on the way in, or downcast again after reading
    df = shrink(df)
    path = stem + ".csv"
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

    print("\nSCORE EACH HALF SEPARATELY. Do not concatenate the halves:")
    print("    out = []")
    print("    for p in {!r}:".format(paths))
    print("        d = pd.read_csv(p)")
    print("        out.append(pd.DataFrame({'sbrp_id': d.sbrp_id,")
    print("                                 'pd': model.predict_proba(d[FEATURES])[:, 1]}))")
    print("        del d; gc.collect()")
    print("    pd.concat(out, ignore_index=True).to_csv('data/scores.csv', index=False)")
    print("THAT concat is fine: 11M x 2 columns, about 0.18 GB. Concatenating")
    print("the full halves instead would peak near 14 GB - worse than never")
    print("having split. The model needs one row at a time to produce a PD.")


if __name__ == "__main__":
    main()

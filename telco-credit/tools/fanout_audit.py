#!/usr/bin/env python3
"""Flag joins that can duplicate rows, which silently multiplies every SUM.

This class of bug does not raise an error and does not look wrong in the
output. It cost a full turn here: run_len is grouped by (sbrp_id, run_id), so
joining it to a per-month relation fanned each month row out once per debt run
and multiplied every SUM and COUNT by the run count. A subscriber paying around
the 15th each month has six runs, so their counters came out six times too
large - 36 late months inside a six-month window, 927 debt days inside 180 -
and a 36 pct bad rate read as a business finding rather than an error.

A join is safe when the right-hand relation has at most one row per join key.
That holds when its GROUP BY is exactly the join key. It is flagged when the
GROUP BY has more columns than the join matches on.

    python3 fanout_audit.py ../sql/11_dcb_extract_v3.sql

Anything flagged needs a human read: a relation grouped by (sbrp_id, month_key)
is SAFE when joined on both, and dangerous when joined on sbrp_id alone.
Pair this with the G6 bounds check, which catches in the data what slips past
here: every per-month counter has an arithmetic ceiling.
"""
import io, re, sys


def audit(path):
    sql = io.open(path, encoding="utf-8").read()
    sql = "\n".join(l for l in sql.split("\n") if not l.lstrip().startswith("--"))
    flagged = 0
    for stmt in re.split(r"\n;\s*\n", sql):
        m = re.search(r"CREATE TABLE [\w.]*\.(\w+)", stmt)
        if not m:
            continue
        ctes = {c.group(1): c.group(2)
                for c in re.finditer(r"(\w+) AS \(\s*(.*?)\n\),?\n", stmt, re.S)}
        for j in re.finditer(r"JOIN\s+([\w.]+)\s+(\w+)?\s*ON\s+([^\n]+(?:\n\s+AND[^\n]+)*)",
                             stmt):
            rel, cond = j.group(1).split(".")[-1], j.group(3)
            if rel not in ctes:
                continue
            g = re.search(r"GROUP BY ([^\n]+)", ctes[rel])
            if not g:
                continue
            keys = [k.strip().split(".")[-1] for k in g.group(1).split(",")]
            matched = [k for k in keys if re.search(rf"\b{re.escape(k)}\b", cond)]
            if len(matched) < len(keys):
                flagged += 1
                print(f"{m.group(1)}: JOIN {rel}")
                print(f"    grouped by {keys}")
                print(f"    join matches only {matched}")
                print("    -> can duplicate rows; every SUM downstream is multiplied\n")
    print(f"flagged joins: {flagged}")
    return flagged


if __name__ == "__main__":
    sys.exit(1 if audit(sys.argv[1]) else 0)

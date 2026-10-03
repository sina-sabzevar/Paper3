#!/usr/bin/env python3
"""Move the DCB extract to a different cohort calendar, without hand-editing dates.

Every window in 11_dcb_extract_v3.sql is derived from three numbers: the T0
month, how many feature months precede it, and how many outcome months follow
it. Forty-three date literals are spread across the file, and every calendar
change so far has introduced at least one wrong one (140404 for 140406, 1403
for 1404, a bad day-of-month bound). This script derives all of them instead.

Each date-bearing line of SQL is classified by its ROLE from the surrounding
text, then rewritten. A line carrying a date that matches no known role is a
hard error, so a literal can never be silently left on the old calendar.

    python3 recalendar.py --check                  prove a round-trip is a no-op
    python3 recalendar.py --t0 1405 2 --feat 3 --out 3

Jalali note: months 1-6 have 31 days, 7-11 have 30, month 12 has 29 or 30. Day
31 is always used as an upper BETWEEN bound - harmless for a shorter month,
since no day_key above the real last day exists, and it removes any need to
know which years are leap years. One consequence worth knowing: the "last week
before T0" gate is computed as day 25 to day 31, so it spans seven real days in
a 31-day month, six in a 30-day month and five in month 12. The gate only has
to catch a subscriber still cut off going into T0, and the days nearest T0 are
the ones that matter, so this is accepted rather than special-cased.
"""
import argparse, json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL  = ROOT / "sql" / "11_dcb_extract_v3.sql"
CAL  = ROOT / "sql" / "calendar.json"

PANELS = [("invoice_amt", "invoice"), ("pmnt_amt", "pmnt"), ("tot_rev", "totrev")]


def addm(y, m, k):
    t = (y * 12 + (m - 1)) + k
    return t // 12, t % 12 + 1


def mk(ym):          return ym[0] * 100 + ym[1]
def d_first(ym):     return ym[0] * 10000 + ym[1] * 100 + 1
def d_last(ym):      return ym[0] * 10000 + ym[1] * 100 + 31


def calendar(t0y, t0m, n_feat, n_out):
    """Every window the SQL needs, derived from the three numbers."""
    t0 = (t0y, t0m)
    feat = [addm(t0y, t0m, -n_feat + i) for i in range(n_feat)]
    out  = [addm(t0y, t0m, i) for i in range(n_out)]
    rev3 = addm(t0y, t0m, -3)
    return dict(
        t0=mk(t0), n_feat=n_feat, n_out=n_out,
        feat_months=[mk(x) for x in feat],
        snap=mk(feat[-1]),                     # last month before T0
        feat_range=(mk(feat[0]), mk(feat[-1])),
        rev_range=(mk(rev3), mk(feat[-1])),
        rev_from=mk(rev3),
        out_range=(mk(out[0]), mk(out[-1])),
        daily_all=(d_first(feat[0]), d_last(out[-1])),
        daily_feat=(d_first(feat[0]), d_last(feat[-1])),
        barred_week=(d_last(feat[-1]) - 6, d_last(feat[-1])),
    )


def classify(line, c):
    """Return a (old -> new) substitution for this line, or None if it has no date."""
    # Matches a 6-digit month_key AND an 8-digit day_key. An earlier version of
    # this guard was \b14\d{4}\b, which cannot match 14040101 - there is no word
    # boundary after six digits when two more follow - so every day_key line was
    # skipped and the round-trip check passed while leaving them on the old
    # calendar. Exactly the silent miss this script exists to prevent.
    if not re.search(r"\b1\d{5}(\d{2})?\b", line):
        return None
    pivot = "FILTER (WHERE" in line and re.search(r"month_key\s*=\s*14\d{4}", line)
    if pivot:
        return "pivot"
    if re.search(r"month_key\s*>=\s*14\d{4}", line):
        return "rev_from"
    m = re.search(r"month_key\s+BETWEEN\s+(14\d{4})\s+AND\s+(14\d{4})", line)
    if m:
        pair = (int(m.group(1)), int(m.group(2)))
        for role in ("feat_range", "rev_range", "out_range"):
            if pair == c[role]:
                return role
        raise SystemExit(f"unrecognised month range {pair}: {line.strip()}")
    m = re.search(r"day_key\s+BETWEEN\s+(1\d{7})\s+AND\s+(1\d{7})", line)
    if m:
        pair = (int(m.group(1)), int(m.group(2)))
        for role in ("daily_all", "daily_feat", "barred_week"):
            if pair == c[role]:
                return role
        raise SystemExit(f"unrecognised day range {pair}: {line.strip()}")
    if re.search(r"month_key\s*=\s*14\d{4}", line):
        return "snap"
    if re.search(r"'14\d{4}'\s+AS obs_cohort", line):
        return "t0"
    raise SystemExit(f"date literal with no known role: {line.strip()}")


def rewrite(text, old, new):
    out, counts = [], {}
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("--"):          # comments carry no authority
            out.append(line); continue
        role = classify(line, old)
        if role is None:
            out.append(line); continue
        counts[role] = counts.get(role, 0) + 1
        if role == "pivot":
            for i, om in enumerate(old["feat_months"]):
                line = re.sub(rf"(month_key\s*=\s*){om}\b",
                              lambda mo, i=i: mo.group(1) + str(new["feat_months"][i]), line)
        elif role in ("snap", "rev_from", "t0"):
            line = re.sub(r"(14\d{4})", str(new[role]), line, count=1)
        else:
            a, b = new[role]
            line = re.sub(r"(1\d{3,7})(\s+AND\s+)(1\d{3,7})",
                          lambda mo: f"{a}{mo.group(2)}{b}", line, count=1)
        out.append(line)
    return "\n".join(out), counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", nargs=2, type=int, metavar=("YEAR", "MONTH"))
    ap.add_argument("--feat", type=int)
    ap.add_argument("--out", type=int)
    ap.add_argument("--check", action="store_true",
                    help="rewrite onto the SAME calendar and assert nothing changed")
    a = ap.parse_args()

    cur = json.loads(CAL.read_text())
    old = calendar(cur["t0_year"], cur["t0_month"], cur["n_feat"], cur["n_out"])

    if a.check:
        nt0y, nt0m, nf, no = cur["t0_year"], cur["t0_month"], cur["n_feat"], cur["n_out"]
    else:
        if not a.t0:
            sys.exit("--t0 YEAR MONTH is required unless --check")
        nt0y, nt0m = a.t0
        nf = a.feat if a.feat else cur["n_feat"]
        no = a.out  if a.out  else cur["n_out"]
    new = calendar(nt0y, nt0m, nf, no)

    if nf != cur["n_feat"]:
        sys.exit(f"feature-month count {cur['n_feat']} -> {nf} changes the PANEL COLUMN "
                 f"COUNT (invoice_m1..m{cur['n_feat']}), which is a structural change this "
                 f"script does not make. Change the panel blocks first, then rerun.")

    text = SQL.read_text()
    outp, counts = rewrite(text, old, new)

    if a.check:
        if outp != text:
            sys.exit("ROUND-TRIP FAILED: rewriting onto the same calendar changed the file")
        print("round-trip clean. roles found:", json.dumps(counts, sort_keys=True))
        print("current calendar:", json.dumps({k: v for k, v in old.items()
                                               if k != "feat_months"}, sort_keys=True))
        return

    SQL.write_text(outp)
    CAL.write_text(json.dumps(dict(t0_year=nt0y, t0_month=nt0m, n_feat=nf, n_out=no),
                              indent=2) + "\n")
    print(f"rewritten to T0={new['t0']}  features={new['feat_range']}  "
          f"outcome={new['out_range']}  daily={new['daily_all']}")
    print("roles rewritten:", json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()

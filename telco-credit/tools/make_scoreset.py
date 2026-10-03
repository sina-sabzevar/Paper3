#!/usr/bin/env python3
"""Generate the SCORING pipeline from the training one, without touching it.

The model is trained on features at T0=140501 labelled over 140501..140506.
To score live subscribers it needs the same features computed at T0=140507,
over 140501..140506 - the training set's label window, which is closed. No
label, no outcome window.

WHY THIS IS A SEPARATE FILE RATHER THAN A recalendar.py RUN. The table names are
the same. Re-pointing the calendar and re-running the steps would OVERWRITE
dcb3_base, dcb3_panel and the rest, destroying the training set's
intermediates - dcb3_dataset_c1 would survive but could never be rebuilt. So
this emits a parallel pipeline writing to a different prefix, and leaves
11_dcb_extract_v3.sql on the training calendar.

What it changes, and nothing else:
  - every date literal, by role, to the T0=140507 calendar
  - dwbi_temp40_db.dcb3_*  ->  dwbi_temp40_db.<prefix>_*   (external facts are
    left alone)
  - STEP 8 is REMOVED. It is the label, and with it goes the
    n_months_seen >= 6 filter, which is a label-side rule: a scoring row has no
    outcome, so applying it would silently drop live subscribers.
  - STEP 9 is rebuilt without the label table and without its columns.
  - obs_cohort becomes the scoring cohort.
The 8/9 reclamation exclusion is KEPT - that is the business rule and applies
to both sides.

    python3 tools/make_scoreset.py
"""
import io, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "sql" / "11_dcb_extract_v3.sql"
OUT = ROOT / "sql" / "25_scoreset.sql"
PREFIX = "dcbs"
T0 = (1405, 7)
N_FEAT = 6

sys.path.insert(0, str(ROOT / "tools"))
from recalendar import calendar, rewrite, classify  # noqa: E402
import json

cur = json.loads((ROOT / "sql" / "calendar.json").read_text())
old = calendar(cur["t0_year"], cur["t0_month"], cur["n_feat"], cur["n_out"])
new = calendar(T0[0], T0[1], N_FEAT, 1)   # n_out=1: no outcome window is used

text = SRC.read_text()
text, counts = rewrite(text, old, new)

# drop STEP 8 entirely
m = re.search(r"-- -+\n-- STEP 8 .*?\n;\n", text, re.S)
assert m, "STEP 8 block not found"
text = text[:m.start()] + text[m.end():]

# rebuild STEP 9 without the label
m = re.search(r"-- -+\n-- STEP 9  ASSEMBLY\n-- -+\n.*?\n;\n", text, re.S)
assert m, "STEP 9 block not found"
keep = [("dcb3_base","b"),("dcb3_billref","r"),("dcb3_dpd","dpd"),
        ("dcb3_bars","bar"),("dcb3_panel","pan"),("dcb3_pay","pay"),("dcb3_pit","pit")]
sys.path.insert(0, str(ROOT / "tools"))
# parse each kept table's output columns out of the already-rewritten text
def outer_cols(stmt):
    starts = [x.start() for x in re.finditer(r"(?m)^SELECT", stmt)]
    body = stmt[starts[-1]:]
    d = 0
    for t in re.finditer(r"\(|\)|^FROM\b", body, re.M):
        tok = t.group(0)
        if tok == "(": d += 1
        elif tok == ")": d -= 1
        elif d == 0:
            body = body[len("SELECT"):t.start()]; break
    out, buf, d = [], "", 0
    for ch in body:
        if ch == "(": d += 1
        elif ch == ")": d -= 1
        if ch == "," and d == 0: out.append(buf); buf = ""
        else: buf += ch
    if buf.strip(): out.append(buf)
    names = []
    for it in out:
        t = " ".join(it.split())
        mm = re.search(r"\bAS\s+([A-Za-z_]\w*)\s*$", t, re.I) or re.search(r"([A-Za-z_]\w*)\s*$", t)
        if mm: names.append(mm.group(1))
    return names

nocom = "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("--"))
tables = {}
for st in re.split(r"\n;\s*\n", nocom):
    mm = re.search(r"CREATE TABLE dwbi_temp40_db\.(\w+)", st)
    if mm: tables[mm.group(1)] = outer_cols(st)

lines, seen = [], set()
for t, a in keep:
    for c in tables[t]:
        if c == "sbrp_id" and a != "b": continue
        assert c not in seen, f"duplicate {c}"
        seen.add(c); lines.append(f"        {a}.{c},")
step9 = f"""-- ---------------------------------------------------------------------------
-- STEP 9  SCORING-SET ASSEMBLY. No label table, no label columns.
--  {len(seen)} columns. Generated - regenerate rather than hand-edit.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS dwbi_temp40_db.{PREFIX}_scoreset;
CREATE TABLE dwbi_temp40_db.{PREFIX}_scoreset AS
SELECT  '{new['t0']}' AS obs_cohort,
        pay.paid_total_6m / NULLIF(r.obligation_6m, 0)     AS paid_to_obligation,
        GREATEST(pay.paid_total_6m - r.obligation_6m, 0)   AS arrears_paydown_6m,
{chr(10).join(lines).rstrip(',')}
FROM        dwbi_temp40_db.{PREFIX}_base    b
INNER JOIN  dwbi_temp40_db.{PREFIX}_billref r   ON r.sbrp_id   = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.{PREFIX}_dpd     dpd ON dpd.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.{PREFIX}_bars    bar ON bar.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.{PREFIX}_panel   pan ON pan.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.{PREFIX}_pay     pay ON pay.sbrp_id = b.sbrp_id
LEFT  JOIN  dwbi_temp40_db.{PREFIX}_pit     pit ON pit.sbrp_id = b.sbrp_id
;
"""
text = text[:m.start()] + step9 + text[m.end():]

# rename ONLY the temp tables, never the source facts
text = re.sub(r"dwbi_temp40_db\.dcb3_", f"dwbi_temp40_db.{PREFIX}_", text)

hdr = f"""-- ============================================================================
--  SCORING SET - generated by tools/make_scoreset.py. DO NOT HAND-EDIT.
--
--  T0 = {new['t0']}   features {new['feat_range'][0]}..{new['feat_range'][1]}   NO label window
--
--  Same feature code as the training pipeline, same calendar roles, different
--  T0 - which is the only way the model sees at scoring time what it saw at
--  training time.
--
--  Writes to dwbi_temp40_db.{PREFIX}_* so it CANNOT overwrite the training
--  tables. Running the training pipeline on a re-pointed calendar would have
--  destroyed dcb3_base and the rest, leaving dcb3_dataset_c1 unrebuildable.
--
--  STEP 8 is absent: it is the label. The n_months_seen >= 6 filter goes with
--  it, which is correct - a scoring row has no outcome to be complete.
--  The 8/9 reclamation exclusion is KEPT: business rule, applies to both.
--
--  Run top to bottom. Final table: dwbi_temp40_db.{PREFIX}_scoreset
-- ============================================================================

"""
# Drop any statement that reads a table this pipeline does not create. Removing
# STEP 8 took the label table with it, but the SANITY CHECKS that read it sat
# AFTER the CREATE block and survived - they would have failed on a missing
# dcbs_label. A general rule is safer than patching each one: build the set of
# tables actually created, then keep only statements that reference nothing else.
created = set(re.findall(r"CREATE TABLE dwbi_temp40_db\.(\w+)", text))
# split on lines that are exactly a semicolon - the file's own statement
# terminator - rather than a regex with a lookbehind, which silently matched
# nothing and left the orphaned checks in place.
chunks, buf = [], []
for line in text.split("\n"):
    buf.append(line)
    if line.strip() == ";":
        chunks.append("\n".join(buf)); buf = []
if buf: chunks.append("\n".join(buf))

kept, dropped = [], []
for ch in chunks:
    code = "\n".join(l for l in ch.split("\n") if not l.lstrip().startswith("--"))
    missing = set(re.findall(r"dwbi_temp40_db\.(\w+)", code)) - created
    if missing and "CREATE TABLE" not in code:
        dropped.append(sorted(missing)); continue
    kept.append(ch)
text = "\n".join(kept)
print("dropped statements referencing tables not built here:",
      dropped if dropped else "none")

OUT.write_text(hdr + text)
print(f"wrote {OUT.name}: T0={new['t0']}, features {new['feat_range']}, "
      f"{len(seen)} feature columns, prefix {PREFIX}_")
print("roles rewritten:", json.dumps(counts, sort_keys=True))

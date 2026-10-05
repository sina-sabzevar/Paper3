# ---------------------------------------------------------------------------
#  WHERE ARE MY FILES? Paste this into a cell and run it. It changes nothing.
# ---------------------------------------------------------------------------
import os, glob

DATA = "data"          # same value the notebook uses

print("cwd                :", os.getcwd())
print("DATA               :", DATA)
print("DATA resolves to   :", os.path.abspath(DATA))
print("DATA exists        :", os.path.isdir(DATA))

print("\nthe loader is looking for:")
for stem in ("dcb_model", "dcb_score"):
    for ext in (".parquet", ".csv"):
        pat = os.path.join(DATA, stem) + "*" + ext
        print(f"   {pat:<34} -> {sorted(glob.glob(pat)) or 'nothing'}")

if os.path.isdir(DATA):
    entries = sorted(os.listdir(DATA))
    print(f"\nwhat is actually in {os.path.abspath(DATA)}  ({len(entries)} items):")
    for e in entries:
        p = os.path.join(DATA, e)
        size = os.path.getsize(p) / 1e6 if os.path.isfile(p) else 0
        print(f"   {e:<44} {size:>10,.1f} MB")
else:
    print(f"\n{DATA} does not exist from this cwd. Look wider:")
    for d in (".", "..", "notebook", "../notebook"):
        if os.path.isdir(d):
            hits = [f for f in os.listdir(d) if f.endswith((".parquet", ".csv"))]
            if hits:
                print(f"   {os.path.abspath(d)}: {hits[:8]}")

# ---- say what to change, and keep it to the point ------------------------
# An earlier version of this scanned the PARENT directory too and emitted a
# rename suggestion for every data file it found there. On a working directory
# holding 200 unrelated CSVs that buried the one line that mattered under 200
# lines of nonsense - it proposed renaming user_item_rating_mohsen.csv to
# dcb_model_p1.csv. Suggestions are now confined to DATA itself, and when DATA
# does not exist the answer is almost always the PATH, not the names.
found_here = []
if os.path.isdir(DATA):
    found_here = [f for f in sorted(os.listdir(DATA))
                  if f.endswith((".parquet", ".csv"))]

if not os.path.isdir(DATA):
    print("\n" + "=" * 66)
    print(f"  {DATA!r} does not exist from this cwd, so the problem is the PATH.")
    print("  Looking for the four files nearby:")
    hits = {}
    for d in (".", "..", "data", "../data", os.path.expanduser("~")):
        if not os.path.isdir(d):
            continue
        f = [x for x in os.listdir(d)
             if x.startswith(("dcb_model", "dcb_score"))
             and x.endswith((".parquet", ".csv"))]
        if f:
            hits[os.path.abspath(d)] = sorted(f)
    if hits:
        for d, f in hits.items():
            print(f"\n    {d}")
            for x in f:
                print(f"       {x}")
        best = max(hits, key=lambda d: len(hits[d]))
        rel = os.path.relpath(best, os.getcwd())
        print(f"\n  -> set DATA = {rel!r}   (or the absolute {best!r})")
        print("     The filenames are fine if they START with dcb_model or")
        print("     dcb_score - the suffix is free, and dcb_modelpart1 matches")
        print("     the glob just as well as dcb_model_p1.")
    else:
        print("\n    no dcb_model* or dcb_score* files found nearby. They have")
        print("    not been exported yet, or they are somewhere else entirely.")
    print("=" * 66)

elif not found_here:
    print(f"\n  {os.path.abspath(DATA)} exists but holds no .parquet or .csv.")

else:
    bad = [f for f in found_here
           if not f.startswith(("dcb_model", "dcb_score"))]
    if bad:
        print(f"\n  data files in {DATA} that the glob does NOT match:")
        for f in bad:
            low = f.lower()
            stem = ("dcb_score" if any(k in low for k in ("pred", "score"))
                    else "dcb_model" if any(k in low for k in ("train", "model"))
                    else "dcb_model_OR_dcb_score")
            sfx = "even" if "even" in low else "odd" if "odd" in low else "p1"
            ext = ".parquet" if f.endswith(".parquet") else ".csv"
            print(f"     {f}  ->  {stem}_{sfx}{ext}")
        print("\n  only the STEM matters; the suffix is free.")
    else:
        print("\n  every data file here already matches the glob. Good.")

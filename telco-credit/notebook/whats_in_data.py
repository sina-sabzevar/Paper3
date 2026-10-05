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

# ---- suggest the rename, if files are there under another name -------------
cands = []
for root in (DATA, ".", ".."):
    if not os.path.isdir(root):
        continue
    for f in os.listdir(root):
        if f.endswith((".parquet", ".csv")) and not f.startswith(("dcb_model",
                                                                  "dcb_score")):
            cands.append(os.path.join(root, f))
if cands:
    print("\ndata files present under a name the loader does NOT match:")
    for c in sorted(set(cands)):
        base = os.path.basename(c)
        low  = base.lower()
        if "pred" in low or "score" in low or "scoreset" in low:
            stem = "dcb_score"
        elif "train" in low or "model" in low:
            stem = "dcb_model"
        else:
            stem = "dcb_model_OR_dcb_score"
        suffix = "even" if "even" in low else "odd" if "odd" in low else "p1"
        ext = ".parquet" if base.endswith(".parquet") else ".csv"
        print(f"   {c}")
        print(f"      -> rename to {DATA}/{stem}_{suffix}{ext}")
    print("\n  only the STEM matters. dcb_model_even / dcb_model_odd is fine,")
    print("  so is dcb_model_p1 / dcb_model_p2. The suffix is free.")

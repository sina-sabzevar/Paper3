# -*- coding: utf-8 -*-
"""Print one compact block covering the whole run.

PASTE THIS INTO A NEW CELL AT THE BOTTOM OF THE NOTEBOOK AND RUN IT, or

    exec(open("run_summary.py").read())

It must run in the SAME kernel that ran the notebook - it reads the live
variables, not the files, so everything is the run you actually did.

Every block is wrapped: a name that does not exist prints MISSING and the
rest still prints. Nothing here recomputes anything, so it cannot change
a result.
"""
import numpy as np, pandas as pd

G = globals()
def have(*names):
    return all(n in G for n in names)

L = []
def say(s=""):
    L.append(str(s))

say("=" * 64)
say("RUN SUMMARY")
say("=" * 64)

# --- 1. what was loaded ---------------------------------------------------
say("\n[1] DATA LOADED")
if have("train_raw", "score_raw"):
    say(f"  train rows      {len(train_raw):,}")
    say(f"  score rows      {len(score_raw):,}")
    say(f"  features used   {len(FEATURES) if 'FEATURES' in G else '?'}")
    say(f"  source          {G.get('SOURCE', '?')}")
    if "SW" in G and "CFG" in G:
        lab = CFG["LABEL"]
        say(f"  label           {lab}")
        say(f"  raw event rate  {train_raw[lab].mean():.4%}")
        say(f"  weighted back   {np.average(train_raw[lab], weights=SW):.4%}")
else:
    say("  MISSING train_raw / score_raw")

# --- 2. is the model sound ------------------------------------------------
say("\n[2] MODEL - if this is broken every number below is noise")
if have("RES"):
    say(RES.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    say(f"  chosen: {G.get('best', '?')}")
else:
    say("  MISSING RES (cell 20)")

# --- 3. is the PD level right ---------------------------------------------
say("\n[3] CALIBRATION - the limit engine spends the LEVEL, not the ranking")
if have("cal"):
    # The goal is 1.0, so neither the min nor the max is "best" - the worst
    # decile is the one furthest from 1.0 in either direction.
    worst = cal.ratio.iloc[(cal.ratio - 1.0).abs().to_numpy().argmax()]
    say(f"  range               {cal.ratio.min():.3f} to {cal.ratio.max():.3f}")
    say(f"  furthest from 1.0   {worst:.3f}")
    say("  (ratio = actual / predicted; 1.000 means the PD level is right)")
else:
    say("  MISSING cal (cell 22)")
if have("anchor"):
    # anchor is a RATIO (observed weighted rate / mean isotonic prediction),
    # not a PD. Printing it as a percentage made a healthy 1.0 read as
    # "99.9993%", which looks broken and is not.
    say(f"  anchor ratio        {float(anchor):.4f}   (1.0 = no rescaling needed)")

# --- 4. has the scoring set drifted ---------------------------------------
say("\n[4] PSI - the scoring window is 6 months after the training window")
if have("PSI"):
    say(f"  features PSI > 0.25 (extrapolating) {int((PSI > 0.25).sum())}")
    say(f"  features PSI > 0.10 (watch)         {int((PSI > 0.10).sum())}")
    say("  worst 5:")
    for n, v in PSI.head(5).items():
        say(f"      {n:<34} {v:7.4f}")
else:
    say("  MISSING PSI (cell 26)")

# --- 5. which policy was chosen -------------------------------------------
say("\n[5] POLICY CHOSEN BY MCDM")
if have("w"):
    try:
        say("  " + ", ".join(f"{k}={v}" for k, v in dict(w).items()))
    except Exception:
        say(f"  {w}")
else:
    say("  MISSING w (cell 43 reads the chosen policy row)")
if have("CI"):
    say(f"  AHP consistency ratio {float(CI):.4f}")
if have("feasible", "POL"):
    say(f"  policies within budget AND hitting the loan target: "
        f"{len(feasible)} of {len(POL)}")

# --- 6. THE BOOK - the two questions -------------------------------------
say("\n" + "=" * 64)
say("[6] THE BOOK")
say("=" * 64)
if have("score_sc", "approve", "L_final"):
    appr = int(approve.sum())
    say(f"  scored            {len(score_sc):,}")
    say(f"  APPROVED          {appr:,}   ({approve.mean():.2%} of scored)")
    say(f"  PRINCIPAL         {L_final.sum()/1e9:,.1f} billion Toman")
    if appr:
        la = L_final[approve]
        say(f"  mean limit        {la.mean():,.0f} Toman")
        say(f"  median limit      {np.median(la):,.0f} Toman")
        say(f"  min / max limit   {la.min():,.0f} / {la.max():,.0f} Toman")
        for q in (10, 25, 50, 75, 90):
            say(f"      p{q:<3}          {np.percentile(la, q):,.0f} Toman")
else:
    say("  MISSING score_sc / approve / L_final (cell 43)")

if have("pd_sc_adj", "approve"):
    say(f"  portfolio PD      {pd_sc_adj[approve].mean():.4%}")
if have("el"):
    say(f"  expected loss     {el/1e9:,.2f} billion Toman")
    if have("L_final"):
        say(f"  EL / principal    {el/max(L_final.sum(), 1):.4%}")

# --- 7. against the business constraints ----------------------------------
say("\n[7] AGAINST THE THREE HARD CONSTRAINTS")
if have("approve", "L_final", "CFG"):
    appr = int(approve.sum())
    prin = float(L_final.sum())
    tgt  = CFG.get("target_loans", 3_000_000)
    bud  = CFG.get("budget_toman", 1.2e12)
    mint = CFG.get("min_ticket", 400_000)
    # POP_SCALE exists if the notebook scaled a sample up to the real base
    scale = float(G.get("POP_SCALE", 1.0))
    if scale != 1.0:
        say(f"  (POP_SCALE = {scale:g} is applied below)")
    for name, got, need, unit, ok_if_ge in (
            ("loans",     appr * scale,   tgt, "loans",         True),
            ("principal", prin * scale / 1e9, bud / 1e9, "billion Toman", False),
    ):
        mark = ("OK" if got >= need else "SHORT") if ok_if_ge else \
               ("OK" if got <= need else "OVER BUDGET")
        say(f"  {name:<10} {got:>15,.1f} {unit:<14} target {need:,.1f}   {mark}")
    if appr:
        below = int((L_final[approve] < mint).sum())
        say(f"  approved offers below the {mint:,} minimum ticket: {below:,}"
            + ("   <-- these cannot be issued" if below else "   OK"))
else:
    say("  MISSING approve / L_final / CFG")

# --- 8. the handover file -------------------------------------------------
say("\n[8] HANDOVER FILE")
if have("deliver"):
    say(f"  rows delivered    {len(deliver):,}")
    say(f"  columns           {list(deliver.columns)}")
    if "limit_toman" in deliver:
        say(f"  total committed   {deliver.limit_toman.sum()/1e9:,.1f} billion Toman")
    for col in ("cell", "grade"):
        if col in deliver:
            say(f"  by {col}:")
            vc = deliver[col].value_counts().sort_index()
            for k, v in vc.items():
                extra = ""
                if "limit_toman" in deliver:
                    s = deliver.loc[deliver[col] == k, "limit_toman"].sum()
                    extra = f"   {s/1e9:>8,.1f} bn Toman"
                say(f"      {str(k):<12} {v:>12,}{extra}")
else:
    say("  MISSING deliver (cell 45)")

say("\n" + "=" * 64)
out = "\n".join(L)
print(out)
try:
    with open("outputs/run_summary.txt", "w") as f:
        f.write(out)
    print("\nalso written to outputs/run_summary.txt - send me that file")
except Exception as e:
    print(f"\n(could not write the file: {e} - just copy the text above)")

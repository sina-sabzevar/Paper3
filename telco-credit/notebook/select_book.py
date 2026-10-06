# -*- coding: utf-8 -*-
"""Cut the approved book out of handover_scores.csv.

    python3 select_book.py

Takes the N safest subscribers by predicted PD and writes the list
implementation will work from, with the figures a credit committee signs.

WHY A SEPARATE SCRIPT. The model's job ended at a ranked score per subscriber.
Where to cut is a business decision that will be revisited - a different
appetite, a different line size, a different month - and none of that should
mean re-running an 8.7M row fit. This reads the scores and nothing else.
"""
import os
import numpy as np
import pandas as pd

SCORES   = os.path.join("outputs", "handover_scores.csv")
OUT      = os.path.join("outputs", "approved_book.csv")

TAKE          = 4_672_361   # how many to approve, safest first
TICKET_TOMAN  = 500_000     # the line per approved subscriber
APPETITE      = 0.005       # the book PD ceiling the committee has set
LGD           = 1.00        # 1.00 = a bar loses the whole balance. Pessimistic.

# Measured on TEST, in the score region a take of this size draws from: the
# model predicted 456 events and 412 occurred, so it runs about 10 pct
# CONSERVATIVE there. Reported, not corrected - a 10 pct cushion in the
# pessimistic direction is worth keeping.
TEST_CALIB_RATIO = 0.904


def main():
    if not os.path.exists(SCORES):
        raise FileNotFoundError(
            f"{SCORES} not found. Run the notebook first - it writes "
            f"handover_scores.csv at the end.")
    df = pd.read_csv(SCORES)
    need = {"sbrp_id", "pd_4m"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"{SCORES} is missing {sorted(missing)}")
    print(f"loaded {len(df):,} scored subscribers from {SCORES}")

    if TAKE > len(df):
        raise ValueError(
            f"TAKE={TAKE:,} exceeds the {len(df):,} subscribers scored. The "
            f"screen admits that many and no more.")

    # THE CUT, AND THE TIE AT IT.
    #
    # Sorting on pd_4m alone is not a cut, it is a cut plus an accident.
    # Isotonic calibration emits a step function, so a block of subscribers
    # carry one identical pd_4m; mergesort then settles them by CSV row order,
    # which traces back to the order the parquet parts happened to concatenate
    # in, and Trino's ORDER BY makes no stability promise whatsoever. Two
    # routes to "the safest N" return two different sets of people.
    #
    # So the order is made total and explicit. pay_cover is what the subscriber
    # paid against what they were billed - a real signal among subscribers the
    # model scores identically, and scale-free, so it does not drift with the
    # Rial. tenure_m breaks what that ties. sbrp_id makes the result
    # reproducible and identical in Python and in SQL.
    keys, asc = ["pd_4m"], [True]
    for k, up in (("pay_cover", False), ("tenure_m", False), ("sbrp_id", True)):
        if k in df.columns:
            keys.append(k); asc.append(up)
    if "pay_cover" not in df.columns:
        print("\n  NOTE handover_scores.csv carries no pay_cover column, so the")
        print("  tie at the cut is broken on sbrp_id alone - reproducible, but")
        print("  arbitrary. Re-run the training notebook to get the real key.")
    df = df.sort_values(keys, ascending=asc, kind="mergesort").reset_index(drop=True)
    book = df.iloc[:TAKE].copy()

    # How much of the book did the tie-break decide rather than the model?
    _cut = float(df.pd_4m.iloc[TAKE - 1])
    _below = int((df.pd_4m < _cut).sum())
    _tied = int((df.pd_4m == _cut).sum())
    _room = TAKE - _below
    print(f"\n  tie at the cut      {_tied:>12,} share pd_4m = {_cut:.6%}")
    print(f"  of those, admitted  {_room:>12,}   refused {_tied - _room:,}")
    if _tied - _room > 0.01 * TAKE:
        print(f"  -> {100*(_tied-_room)/TAKE:.1f} pct of the book was decided by the "
              f"tie-break, not by pd_4m.")
        print("     The order is defensible and reproducible, but say so when the")
        print("     book is handed over - those subscribers are not ranked by risk.")
    elif _tied - _room > 0:
        print("  -> the tie-break decided well under 1 pct of the book")
    else:
        print("  -> no tie at the cut; pd_4m alone determines the book")

    cut_pd   = float(book.pd_4m.iloc[-1])
    book_pd  = float(book.pd_4m.mean())
    exposure = TAKE * TICKET_TOMAN
    exp_loss = exposure * book_pd * LGD

    # The marginal slice is what says whether the NEXT subscriber is worth
    # taking. A book average can sit comfortably under appetite while the
    # subscribers at the edge are well over it.
    edge = max(1, TAKE // 10)
    marg_pd = float(book.pd_4m.iloc[-edge:].mean())

    print(f"\nTHE CUT")
    print(f"  approved            {TAKE:>12,}  "
          f"({TAKE/len(df):.1%} of those scored)")
    print(f"  PD cutoff           {cut_pd:>12.4%}  "
          f"approve at or below this score")
    print(f"  book PD             {book_pd:>12.4%}")
    print(f"  marginal PD, last {edge:,} {marg_pd:>8.4%}")
    for nm, v in (("book", book_pd), ("marginal", marg_pd)):
        flag = "within" if v <= APPETITE else "OVER"
        print(f"    {nm:<9} vs appetite {APPETITE:.2%}: {flag}")

    print(f"\nTHE MONEY, at {TICKET_TOMAN:,} Toman and LGD {LGD:.0%}")
    print(f"  exposure            {exposure/1e9:>9,.0f} bn Toman")
    print(f"  expected loss       {exp_loss/1e9:>9,.1f} bn Toman")
    print(f"  loss rate           {book_pd*LGD:>12.4%}")

    print(f"\nSTRESS - the level is the model's least reliable output")
    for nm, m in (("as predicted", 1.0),
                  ("+17 pct, the drift between the two windows", 1.17),
                  ("lending into months 1-4 instead (measured 1.68x)", 1.68),
                  ("twice predicted", 2.0), ("three times predicted", 3.0)):
        r = book_pd * m * LGD
        print(f"  {nm:<48} {r:>7.4%}  {exposure*r/1e9:>5.1f} bn  "
              f"{'within' if r <= APPETITE else 'OVER APPETITE'}")
    breach = APPETITE / (book_pd * LGD)
    print(f"\n  it takes a {breach:.1f}x miss on the predicted rate to breach "
          f"{APPETITE:.2%}")

    if "grade" in book.columns:
        print(f"\nGRADE MIX of the approved book")
        g = book.groupby("grade", observed=True).agg(
            n=("pd_4m", "size"), mean_pd=("pd_4m", "mean"))
        g["share"] = g.n / g.n.sum()
        print(g.to_string(float_format=lambda v: f"{v:12.6f}"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = [c for c in ("sbrp_id", "pd_4m", "grade") if c in book.columns]
    # fixed decimals, never scientific notation - see handover_scores.csv
    book[cols].to_csv(OUT, index=False, float_format="%.12f")
    print(f"\nwritten to {OUT}  ({len(book):,} rows, columns {cols})")

    print(f"\nWHAT THIS FILE IS NOT")
    print(f"  pd_4m is the probability of a TWO-WAY BAR within 4 months, not")
    print(f"  the share of credit a subscriber repays. And every label behind")
    print(f"  it came from subscribers who had NO credit line - the model")
    print(f"  predicts 'would be cut off for not paying their own bill', which")
    print(f"  is a proxy for 'would not repay credit', not a measurement of it.")
    print(f"  On TEST it ran {1-TEST_CALIB_RATIO:.0%} conservative in this score")
    print(f"  region, which is the direction you want, but the behavioural")
    print(f"  effect of handing someone spendable credit is unmeasured here.")


if __name__ == "__main__":
    main()

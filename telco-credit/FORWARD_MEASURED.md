# The forward answer, measured

Out of time. Features 140407–140412, outcomes 140501–140504, windows disjoint.
Screened population: never one-way barred and never two-way barred in the
feature window. Zero subscribers were absent from the outcome window, so
nothing was censored.

## The answer

| revenue cut | subscribers | vs 3M | 2 months | 3 months | 4 months |
|---|---|---|---|---|---|
| **2+ of 6** | **6,879,803** | **2.3×** | **0.36 pct** | **0.63 pct** | **0.95 pct** |
| 3+ of 6 | 5,204,055 | 1.7× | 0.33 pct | 0.58 pct | 0.87 pct |
| 4+ of 6 | 3,933,300 | 1.3× | 0.31 pct | 0.54 pct | 0.81 pct |
| 5+ of 6 | 2,851,593 | 1.0× | 0.28 pct | 0.48 pct | 0.73 pct |
| 6 of 6 | 1,753,823 | 0.6× | 0.25 pct | 0.44 pct | 0.68 pct |

**Every cut is under 1 pct at every horizon.** The loosest, revenue in 2 or
more of six months, gives **6,879,803 subscribers** and clears 1 pct even at
four months — 2.3 times the 3,000,000 target.

## My estimates were wrong in both directions

| cut | horizon | my estimate | measured | |
|---|---|---|---|---|
| 2+ | 4 mo | 1.23 pct | 0.95 pct | pessimistic by 0.28 |
| 3+ | 4 mo | 0.88 pct | 0.87 pct | within 0.01 |
| 5+ | 4 mo | 0.35 pct | 0.73 pct | **optimistic by 0.38** |
| 6 | 4 mo | 0.13 pct | 0.68 pct | **optimistic by 0.55, 5× too low** |

I said the contemporaneous band rate was a conservative ceiling. For the loose
cuts it was. **For the tight cuts it was a floor, and badly so.**

**Why: reverse causality in the contemporaneous measure.** A subscriber barred
during the window loses service, generates less revenue, and so is *less likely
to show six months above 170,000 Toman*. Being barred pushes you out of the
band you are being counted in. That deflates the rate in a way a forward window
cannot, and it inflates it most where the band is tightest. I flagged exactly
this entanglement for the payment label and did not see it here until the
measurement came back.

## The hazard is back-loaded, and the shape is stable

From exact counts, not the rounded rates:

| cut | bad 2m | bad 3m | bad 4m | 3m/2m | 4m/2m |
|---|---|---|---|---|---|
| 2+ | 25,086 | 43,686 | 65,303 | 1.741 | 2.603 |
| 3+ | 17,338 | 30,211 | 45,468 | 1.742 | 2.622 |
| 4+ | 12,171 | 21,187 | 32,001 | 1.741 | 2.629 |
| 5+ | 7,954 | 13,780 | 20,913 | 1.732 | 2.629 |
| 6 | 4,405 | 7,681 | 11,870 | 1.744 | 2.695 |

A constant hazard predicts 1.500 and 2.000. Measured: **1.740 and 2.636**,
and the spread across five cuts is 1.732–1.744 and 2.603–2.695. Fitting
`p_n ∝ n^k` gives **k = 1.40**, and the same k predicts a 3m/2m ratio of 1.763
against the 1.740 measured. One exponent fits both horizons across all five
cuts.

**Mechanism:** a two-way bar is the end of an escalation. Debt accumulates, a
one-way bar usually comes first, then the operator escalates. That takes months,
so the monthly hazard rises with time rather than staying flat.

A caveat on my own first pass at this: I initially read the ratios off F3's
percentages, which are rounded to one decimal, and reported a 1.3–3.5 spread.
That spread was a rounding artefact. The exact counts in F2 show the shape is
near-identical across every cut.

## What that means for a longer facility

| revenue cut | 2m | 3m | 4m | 6m\* | 12m\* |
|---|---|---|---|---|---|
| 2+ | 0.36 | 0.63 | 0.95 | 1.69 | 4.46 |
| 3+ | 0.33 | 0.58 | 0.87 | 1.55 | 4.08 |
| **5+** | 0.28 | 0.48 | **0.73** | **1.30** | **3.42** |
| 6 | 0.25 | 0.44 | 0.68 | 1.17 | 3.08 |

\* extrapolated at `n^1.40` from the measured 2-month rate.

**A 12-instalment product cannot quote the 4-month rate.** At revenue 5+ the
measured 4-month figure is 0.73 pct and the 12-month extrapolation is 3.42 pct —
nearly five times larger. Both are workable, but they are different numbers to
put in front of a credit committee, and only the first is measured.

## The bar conditions are worth what they cost

| screen | subscribers | forward 4-month rate |
|---|---|---|
| revenue 3+, no bar condition at all | 5,554,943 | 1.7 pct |
| revenue 3+, never two-way | 5,502,289 | 1.3 pct |
| **revenue 3+, never one-way AND never two-way** | **5,204,055** | **0.9 pct** |

| condition | volume cost | rate saved |
|---|---|---|
| never two-way | 52,654 (0.9 pct) | 0.4 points |
| also never one-way | 298,234 (5.4 pct) | 0.4 points |

**The never-one-way condition nearly halves the forward bad rate for 5.4 pct of
the volume.** That is measured, not assumed, and it settles the question of
whether to include it.

## Zero censoring

No screened subscriber was absent from the outcome window. The NULL handling I
built for that case was unnecessary here — worth keeping for other windows, but
it changed nothing.

## The anomaly holds up forward

`rev_months = 0` comes in at 0.7 pct over four months, **lower than revenue
bands 1 through 5**. The dormancy explanation survives a forward test: 27.1
million subscribers who cannot be barred for non-payment because they do not
consume. They are not a credit opportunity and they are not a risk.

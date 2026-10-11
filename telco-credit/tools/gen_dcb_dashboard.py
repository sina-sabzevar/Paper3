# -*- coding: utf-8 -*-
"""Manager dashboard for the DCB product. Chart geometry computed, never placed by hand."""
import io, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style

GRADES = [("A", 3_029_397, 0.001417, 400_000),
          ("B", 4_087_448, 0.003298, 300_000),
          ("C", 1_085_787, 0.007387, 150_000),
          ("D",   599_140, 0.013538, 100_000),
          ("E",   542_951, 0.040000,       0)]
SCORED  = 9_344_723
APPROVED = sum(g[1] for g in GRADES if g[3] > 0)
OUTSTANDING = sum(g[1] * g[3] for g in GRADES)
AVG_LIMIT = OUTSTANDING / APPROVED
TARGET_BN = 15000.0

def f(n): return "{:,}".format(int(round(n)))
out = io.StringIO(); W = out.write

W(dash_style.head("DCB Credit Programme"))

# ----------------------------------------------------------------- header
W("""<header>
  <p class="eyebrow">Direct Carrier Billing &middot; credit programme &middot; 1405-07-18</p>
  <h1>A one-month credit line, settled on the next bill</h1>
  <p class="lede">The product is now pure DCB: a subscriber spends against their mobile account and
  repays on the following invoice. Shorter exposure, smaller tickets, and &mdash; because the money
  returns every month instead of every four &mdash; a far larger annual volume from the same balance
  sheet.</p>
  <div class="spec">
    <span class="chip">term <b>1 month</b></span>
    <span class="chip">minimum <b>100,000 Toman</b></span>
    <span class="chip">average <b>300,000 Toman</b></span>
    <span class="chip">segmented by <b>risk grade</b></span>
    <span class="chip">repaid on <b>the next bill</b></span>
  </div>
</header>
""")

# ----------------------------------------------------------------- hero
ann12 = OUTSTANDING * 12 / 1e9
W("""<section>
  <div class="hero">
    <div class="big">
      <span class="v">%s bn</span>
      <span class="k">annual disbursement, Toman &mdash; at monthly turnover</span>
    </div>
    <p class="sub">Against a <b class="num">15,000 bn</b> ambition that the four-month product could
    not reach. The balance sheet at risk at any one time is only
    <b class="num">%s bn</b>.</p>
  </div>
  <div class="kpi k6" style="margin-top:14px">
    <div class="tile"><span class="k">Approved</span><span class="v">%s</span>
      <span class="s">grades A&ndash;D of %s scored</span></div>
    <div class="tile"><span class="k">Average limit</span><span class="v">%s</span>
      <span class="s">Toman, against a 300,000 design</span></div>
    <div class="tile"><span class="k">Outstanding</span><span class="v">%s bn</span>
      <span class="s">Toman, at any one time</span></div>
    <div class="tile"><span class="k">Cycles per year</span><span class="v">12</span>
      <span class="s">the four-month product managed 3</span></div>
    <div class="tile"><span class="k">Expected loss rate</span><span class="v">0.09&ndash;0.14</span>
      <span class="s">pct; the span is a design choice, not an unknown</span></div>
    <div class="tile"><span class="k">Annual loss</span><span class="v">27&ndash;46 bn</span>
      <span class="s">Toman, against 31,929 bn lent</span></div>
  </div>
</section>
""" % (f(ann12), f(OUTSTANDING/1e9), f(APPROVED), f(SCORED), f(AVG_LIMIT), f(OUTSTANDING/1e9)))

# ------------------------------------------------- the volume chart
W("""<section>
  <div class="head">
    <h2>Why the shorter term changes the answer</h2>
    <p>The same money lent, collected and lent again. A four-month line turns over three times a
    year; a one-month line turns over twelve. Annual disbursement, in billions of Toman:</p>
  </div>
  <div class="card">
    <div class="svgbox">
""")
BW, BH = 790, 300
PL, PR, PT, PB = 178, 706, 24, 214
bars = [("Four-month line", "500,000 x 3 cycles", 4_672_361*500_000*3/1e9, False),
        ("One-month DCB",   "300,000 x 12 cycles", ann12, True)]
XMAX = max(max(b[2] for b in bars), TARGET_BN) * 1.12
def bx(v): return PL + v / XMAX * (PR - PL)
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="Annual disbursement against the 15,000 bn target">\n' % (BW, BH))
for g in range(0, int(XMAX)+1, 10000):
    if g == 0: continue
    W('      <line class="gl" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>\n' % (bx(g), PT, bx(g), PB))
    W('      <text class="tk" x="%.1f" y="%d" text-anchor="middle">%s</text>\n' % (bx(g), PB+18, f(g)))
bh, gap = 54, 34
for i, (l1, l2, v, hot) in enumerate(bars):
    y = PT + 16 + i*(bh+gap)
    W('      <text class="an" x="%d" y="%.1f" text-anchor="end" fill="var(--ink-2)">%s</text>\n'
      % (PL-12, y+bh/2-6, l1))
    W('      <text class="tk" x="%d" y="%.1f" text-anchor="end">%s</text>\n'
      % (PL-12, y+bh/2+10, l2))
    W('      <rect x="%d" y="%.1f" width="%.1f" height="%d" rx="4" fill="%s"/>\n'
      % (PL, y, max(bx(v)-PL, 3), bh, "var(--s1)" if hot else "var(--sunk)"))
    W('      <text class="dl" x="%.1f" y="%.1f" fill="%s">%s bn</text>\n'
      % (bx(v)+10, y+bh/2+5, "var(--s1)" if hot else "var(--ink-2)", f(v)))
tx = bx(TARGET_BN)
W('      <line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--crit)" stroke-width="2"/>\n' % (tx, PT, tx, PB+4))
W('      <text class="dl" x="%.1f" y="%d" text-anchor="middle" fill="var(--crit)">15,000 bn ambition</text>\n' % (tx, PT-8))
W('      <line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>\n' % (PL, PB, PR, PB))
W('      <text class="tk" x="%d" y="%d">billions of Toman disbursed in a year</text>\n' % (PL, PB+40))
W('    </svg>\n    </div>\n')
W("""    <p class="cap"><b>One caveat, and it is the first question to settle.</b> These are annual
    <i>disbursement</i> figures &mdash; money lent over a year. If the 15,000 bn ambition means peak
    <i>outstanding</i> instead, the one-month product stands at %s bn and is %s&times; short. The two
    readings differ by a factor of twelve, so the target needs defining before any of this is
    presented as met.</p>
  </div>
</section>
""" % (f(OUTSTANDING/1e9), "{:.1f}".format(TARGET_BN/(OUTSTANDING/1e9))))

# ------------------------------------------------- the limit ladder
W("""<section>
  <div class="head">
    <h2>The limit ladder</h2>
    <p>The decision is no longer who to approve but how much to give each person. Limits step down
    with risk grade and the average lands on the 300,000 design.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Grade</th><th>Subscribers</th><th>Share</th><th>Limit</th><th>Outstanding</th><th>Annual at 12 cycles</th></tr></thead>
      <tbody>
""")
for g, n, pd_, lim in GRADES:
    cls = ' class="off"' if lim == 0 else ''
    o = n*lim/1e9
    W('        <tr%s><td>%s</td><td>%s</td><td>%.1f pct</td><td>%s</td><td>%s bn</td><td>%s bn</td></tr>\n'
      % (cls, g + ("" if lim else " &mdash; declined"), f(n), 100*n/SCORED,
         (f(lim) if lim else "&mdash;"), (f(o) if lim else "&mdash;"), (f(o*12) if lim else "&mdash;")))
W('        <tr class="tot"><td>A&ndash;D</td><td>%s</td><td>%.1f pct</td><td>%s avg</td><td>%s bn</td><td>%s bn</td></tr>\n'
  % (f(APPROVED), 100*APPROVED/SCORED, f(AVG_LIMIT), f(OUTSTANDING/1e9), f(ann12)))
W("""      </tbody>
      <tfoot><tr><td colspan="6">Grades come from the risk model's ranking, which is sound and tested
      &mdash; but the <b>boundaries between them are four-month default probabilities</b>, so A&ndash;E
      order subscribers correctly while the thresholds themselves carry the old product's meaning and
      will be re-cut with the new label.
      <b>The limit column is a design, not a measurement</b> &mdash; it is set to meet the 100,000 floor
      and the 300,000 average, and it should be re-derived from each subscriber's own billing before
      launch. Grade E is declined here; whether to decline it or price it is a decision, not a
      result.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""")

# ------------------------------------------------- the population
W("""<section>
  <div class="head">
    <h2>Where the 9.3 million come from</h2>
    <p>Measured on the live window. One screen does almost all the filtering.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Step</th><th>Rule</th><th>Remaining</th><th>Removed</th></tr></thead>
      <tbody>
        <tr><td>Permanent subscribers</td><td>six-month window</td><td>41,270,092</td><td>&mdash;</td></tr>
        <tr><td>Cleared the revenue bar</td><td>170,000 Toman in 2 of 6 months</td><td>10,087,975</td><td>31,182,117</td></tr>
        <tr><td>Never one-way barred</td><td>outgoing never suspended</td><td>9,437,240</td><td>650,735</td></tr>
        <tr class="tot"><td>Never two-way barred</td><td>incoming never suspended</td><td>9,344,723</td><td>92,517</td></tr>
      </tbody>
      <tfoot><tr><td colspan="4">The revenue bar is <b>97.7 pct</b> of all exclusions. It was sized for a
      500,000 Toman line carried over four bills. <b>A 100,000 minimum ticket needs far less capacity</b>,
      so the same bar now excludes subscribers the new product could serve &mdash; and the bar is fixed in
      Rial, so it has already loosened on its own from 12.0 to 24.4 pct of the base over two years.
      Re-sizing it is the largest single lever on volume.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""")

# ------------------------------------------------- known / not known
W("""<section>
  <div class="head">
    <h2>What a bigger bill does &mdash; and the limit rule it gives you</h2>
    <p>DCB lands on the same invoice, so the product does not only lend: it raises the bill the
    subscriber has to pay. Measured on one calendar month, holding bill size and prior direction
    constant, a bill that more than doubles carries <b>1.91&times;</b> the default rate. One that rises
    by less than that carries <b>1.13&times;</b>. The gap between those two numbers is the whole of the
    limit decision.</p>
  </div>
  <div class="card">
    <div class="svgbox">
__PREMIUM_CHART__
    </div>
    <p class="cap">Default rate relative to a bill in its normal range, from 12,042 defaults over
    4.0 million subscriber-months. Whiskers are 95 percent intervals. <b>A bill that falls is as
    dangerous as one that doubles</b> &mdash; a collapsing bill is what precedes a service bar, because
    the subscriber has already stopped using the service.</p>
  </div>

  <div class="card">
    <h3>Which premium a given limit lands in</h3>
    <p class="cap" style="margin-top:6px">Pick the row for what a subscriber bills in a month and
    the column for what you lend them. The cell is the resulting rise and the premium it carries.</p>
__GRID__
    <div class="glegend">
      <span><i class="g1"></i>1.00&times; &mdash; rise under 1.25&times;</span>
      <span><i class="g2"></i>1.13&times; &mdash; rise of 1.25 to 2.00&times;</span>
      <span><i class="g3"></i>1.91&times; &mdash; rise of 2.00&times; or more</span>
    </div>
    <p class="cap"><b>Keep the draw below one month\'s bill and you stay out of the red.</b>
    Strictly below &mdash; a draw of exactly one month\'s bill makes the rise 2.00&times;, which is
    already the 1.91 band. The 170,000 row is the current screen bar: a 100,000 ticket puts it
    in amber, a 300,000 ticket puts it in the red. That is the difference between <b>27 bn</b> and <b>46 bn</b> of
    annual loss on the same book.</p>
  </div>

  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Comparison</th><th>Normal bill</th><th>Raised bill</th><th>Premium</th><th>Reading</th></tr></thead>
      <tbody>
        <tr><td>The bill fell</td><td>0.2563 pct</td><td>0.4836 pct</td><td>1.89&times;</td><td>the riskiest month of all</td></tr>
        <tr><td>Rose by up to 2&times;</td><td>0.2563 pct</td><td>0.2904 pct</td><td><b>1.13&times;</b></td><td>1.10 to 1.17</td></tr>
        <tr class="tot"><td>Rose by 2&times; or more</td><td>0.2563 pct</td><td>0.4889 pct</td><td><b>1.91&times;</b></td><td>1.83 to 1.99</td></tr>
      </tbody>
      <tfoot><tr><td colspan="5">One calendar month, so no calendar effect; pooled across four bill-size
      bands and three prior-direction bands, so neither how much a subscriber normally bills nor which
      way their bill was already moving can explain it. 12,042 defaults over 4.0 million
      subscriber-months. <b>Adjusting for all of that moved the estimate from 1.97 to 1.91</b> &mdash; which
      is itself the finding: the obvious confounders are not where the risk is. What it still cannot
      rule out is selection on something unobserved, so treat 1.91 as the number to plan with rather
      than a proven causal effect. Note the first row: a bill that <i>falls</i> is as dangerous as one
      that doubles.</td></tr></tfoot>
    </table></div>
    <p class="cap"><b>The rule that follows.</b> Keep the draw below one month's bill and the
    rise stays under 2&times;, where the premium is 1.13 rather than 1.91. That single constraint is the
    difference between <b>27 bn</b> and <b>46 bn</b> of annual loss. A 100,000 minimum ticket clears the
    2.00&times; edge only while the bill stays above <b>100,000 Toman a month</b>, because the edge is
    draw equals bill and nothing else. The screen bar, which nobody ever validated, sits at 170,000
    &mdash; a 70 pct margin over that edge, which is the right side to err on.</p>
    <p class="cap"><b>And a screen that is missing.</b> Subscribers whose billing history has a
    <b>zero month</b> inside the qualifying window &mdash; new or restarted lines &mdash; default at
    <b>2.71 pct against 0.35 pct</b> for everyone else. That is <b>7.7&times;</b>, on 109,360 subscribers,
    and the current screen does not look for it: it asks for revenue above the bar in 2 of 6 months,
    which a line that first appeared in month 4 can satisfy.</p>
  </div>
</section>

<section>
  <div class="head">
    <h2>What is measured, and what is not</h2>
    <p>The loss rate is no longer the blank it was. What remains unknown is narrower, and worth
    stating as precisely as what is known.</p>
  </div>
  <div class="split">
    <div class="panel known">
      <h3><span class="dot" style="background:var(--good)"></span>Measured on real data</h3>
      <ul>
        <li>The population and every filter in it &mdash; <b>9,344,723</b> subscribers clear the current
        screen, from a base of 41,270,092.</li>
        <li>The model <b>ranks</b> risk well: AUC <b>0.8278</b> on subscribers nothing was tuned on,
        Gini 0.6557. The ordering is what the limit engine consumes.</li>
        <li>A subscriber's <b>bar history</b> from the year before predicts the outcome at
        <b>13.2&times;</b>. It is the strongest single feature and it is already in the model.</li>
        <li>A model built with <b>no Rial amounts at all</b> scores 0.8230 &mdash; within half a percent,
        and immune to inflation, which otherwise forces a re-tune every year.</li>
        <li>Risk is <b>seasonal</b>: the same exposure across Nowruz ran <b>1.68&times;</b> higher.</li>
        <li>The <b>one-month default rate</b>: <b>0.2208 pct</b>, 19,215 events across 8,701,085
        subscribers. Thick enough to fit a model on, and it sorts cleanly by billing consistency.</li>
        <li>A payment shortfall between a tenth and full payment carries <b>no excess default
        risk</b> &mdash; only "paid essentially nothing" does, at 8.3&times;. Paying slowly is not failing.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Not yet measured</h3>
      <ul>
        <li><b>What a raised bill does to default risk.</b> The history cannot separate it from the
        calendar &mdash; see the section above. The range is <b>0.75&times; to 1.38&times;</b>, and the
        across-subscriber <b>1.97&times;</b> is the planning bound. The loss figures quoted here span
        that: <b>0.08 pct at a premium of 1, 0.15 pct at 1.97</b>.</li>
        <li><b>The model has not yet been refitted on the one-month label.</b> The base case scales
        the measured one-month rate of <b>0.2208 pct</b> by the selection the model already achieves
        at this cut. Built from measured numbers, but not a fitted result.</li>
        <li>Whether a service bar can <b>lag beyond the two months</b> this window allows. A longer
        lag would push the true rate up.</li>
        <li><b>Behaviour under credit.</b> Nobody in this data was ever given spendable credit. The
        model measures who fails to pay their own phone bill, which is not the same thing.</li>
        <li>Whether a <b>100,000 floor</b> is affordable for subscribers the current bar excludes.</li>
      </ul>
    </div>
  </div>
  <div class="card" style="margin-top:14px">
    <p class="cap" style="margin-top:0"><b>What is left is a refit, not a redesign.</b> The label
    window shortens from four months to one, the cohort is rebuilt, and the model is re-fitted on the
    same features. Everything else &mdash; the population, the features, the ranking, the drift work &mdash;
    carries over unchanged. A one-month horizon also means every month becomes its own cohort, so
    there is <i>more</i> training data available, not less.</p>
  </div>
</section>
""")

# ------------------------------------------------- decisions
W("""<section>
  <div class="head">
    <h2>Five decisions needed</h2>
    <p>One is a measurement that has to be made before the rest are worth deciding. The other
    four are not modelling questions, and each changes the size of the programme.</p>
  </div>
  <div class="warnbox" style="margin-bottom:14px">
    <h3>Open, and it sits under every risk number on this page</h3>
    A two-way bar is the <b>end</b> of the operator's dunning ladder, not the start of it. The
    label asks whether a subscriber was barred in 140408, one month after the draw lands on the
    140407 bill &mdash; but if escalation takes months, that bar was set in motion before the
    draw existed. The model would then be reading the cause of its own label out of the payment
    columns, and the measured 0.2208 pct would not be the rate at which draws go unpaid.
    <b><code>55_label_lag.sql</code> settles it</b> and has not yet been run. Until it does, treat the loss figures here as
    the right shape and an unverified level. The
    <a href="https://claude.ai/artifact/H5jJHuD6i6r3gim31Rfrte">workbook</a> sets out what each outcome would mean.
  </div>
  <div class="card">
    <div class="ask">

      <div class="q"><span class="n">01</span><div class="b">
        <h3>Does the label measure the draw, or something that started before it?</h3>
        <p>Every subscriber in the training set was clean on the monthly status through 140406,
        so all 19,215 events went from clean to two-way barred in at most two months. Either the
        ladder can run that fast, or the monthly snapshot is missing one-way episodes, or some
        bars skip the one-way stage. <b>55_label_lag.sql</b> distinguishes them. It is one query
        and it decides whether the model needs refitting on a different label.</p></div></div>

      <div class="q"><span class="n">02</span><div class="b">
        <h3>Is the 15,000 bn target annual lending or peak exposure?</h3>
        <p>At monthly turnover the two differ by twelve times. On the first reading the programme
        clears the target at <b>2.1&times;</b>; on the second it stands at 2,661 bn and is 5.6&times;
        short. Everything in the volume case depends on which is meant.</p></div></div>

      <div class="q"><span class="n">03</span><div class="b">
        <h3>Does the revenue bar come down?</h3>
        <p>It excludes 31.2 million subscribers and was sized for a four-month, 500,000 Toman line.
        A 100,000 ticket needs a fraction of that capacity. Lowering it is the largest lever on
        volume &mdash; and when it was tested, the subscribers a lower bar admits came in
        <b>safer</b>, not riskier.</p></div></div>

      <div class="q"><span class="n">04</span><div class="b">
        <h3>Is 300,000 on one bill too much?</h3>
        <p>Under the old product a 500,000 line sat across four bills &mdash; about three quarters of
        total billing. A 300,000 ticket on a single bill is <b>1.76&times;</b> that month's invoice at
        the screen level. Per bill, the new product asks more of the subscriber, not less, which is
        why the limit should be sized from their own billing rather than set flat.</p></div></div>

      <div class="q"><span class="n">05</span><div class="b">
        <h3>Does it launch as a pilot?</h3>
        <p>The loss rate on a product nobody has run is not knowable from history. A capped cohort
        for one or two cycles converts the largest unknown on this page into a measurement, and a
        one-month term means the answer arrives in weeks.</p></div></div>

    </div>
  </div>
</section>

<p class="cap" style="margin-top:22px">The full chain of evidence behind these numbers
  &mdash; the label definition, nine subscribers worked end to end, and the two shock
  measurements that turned out to be wrong &mdash; is in the
  <a href="https://claude.ai/artifact/H5jJHuD6i6r3gim31Rfrte">DCB Risk Workbook</a>.</p>

<footer>
  <span>Population, screen, model and seasonality: measured in this project's queries and training
  notebook on windows 140401&ndash;140506. Limit ladder and volume: arithmetic on those counts at the
  stated ticket sizes.</span>
  <span>All figures in Toman. The database stores Rial; every amount here is the Rial value divided
  by ten. No loss rate is quoted for the one-month product because none has been measured.</span>
</footer>
</div>
""")
# ------------------------------------------------- the bill-shock premium chart
# Measured premiums with their 95 pct intervals. A bar with no interval is one where
# the stratified estimate was published without one - the whisker is left off rather
# than invented.
SHOCK = [("The bill fell",        "below 0.80\u00d7",    1.887, None,  None,  "crit"),
         ("Normal",               "0.80 to 1.25\u00d7",  1.000, None,  None,  "base"),
         ("Rose, under 2\u00d7",      "1.25 to 2.00\u00d7",  1.133, 1.10, 1.17, "warn"),
         ("Rose by 2\u00d7 or more",  "2.00\u00d7 and above", 1.907, 1.829, 1.989, "crit")]
CW, CH = 790, 286
QL, QR, QT, QB = 196, 712, 20, 212
QMAX = 2.25
def px(v): return QL + v / QMAX * (QR - QL)
_FILL = {"crit":"var(--crit)", "warn":"var(--warn)", "base":"var(--sunk)"}
sv = io.StringIO(); S = sv.write
S('    <svg viewBox="0 0 %d %d" role="img" aria-label="Default rate premium by how much the bill moved">\n' % (CW, CH))
for g in (0.5, 1.0, 1.5, 2.0):
    S('      <line class="gl" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>\n' % (px(g), QT, px(g), QB))
    S('      <text class="tk" x="%.1f" y="%d" text-anchor="middle">%s&times;</text>\n'
      % (px(g), QB+18, "{:.1f}".format(g)))
qh, qgap = 34, 10
for i, (l1, l2, v, lo, hi, kind) in enumerate(SHOCK):
    y = QT + 10 + i*(qh+qgap)
    S('      <text class="an" x="%d" y="%.1f" text-anchor="end" fill="var(--ink-2)">%s</text>\n'
      % (QL-12, y+qh/2-3, l1))
    S('      <text class="tk" x="%d" y="%.1f" text-anchor="end">%s</text>\n'
      % (QL-12, y+qh/2+12, l2))
    S('      <rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" fill="%s"/>\n'
      % (px(0), y, max(px(v)-px(0), 2), qh, _FILL[kind]))
    if lo is not None:
        cy = y + qh/2
        S('      <line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--ink)" stroke-width="1.6"/>\n'
          % (px(lo), cy, px(hi), cy))
        for e in (lo, hi):
            S('      <line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--ink)" stroke-width="1.6"/>\n'
              % (px(e), cy-7, px(e), cy+7))
    # the value label clears the whisker cap, never sits under it
    lx = px(hi) if hi is not None else px(v)
    S('      <text class="dl" x="%.1f" y="%.1f" fill="var(--ink)">%s&times;</text>\n'
      % (lx+10, y+qh/2+5, "{:.2f}".format(v)))
S('      <line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--ink-3)" stroke-width="1.5" stroke-dasharray="4 3"/>\n'
  % (px(1.0), QT, px(1.0), QB+4))
S('      <line class="ax" x1="%.1f" y1="%d" x2="%d" y2="%d"/>\n' % (px(0), QB, QR, QB))
S('      <text class="tk" x="%.1f" y="%d">default rate relative to a bill in its normal range</text>\n'
  % (px(0), QB+42))
S('    </svg>\n')

# ------------------------------------------------- the ticket-by-bill grid
BILLS = [(1_000_000, "a heavy user"), (500_000, ""), (300_000, ""),
         (170_000, "the screen bar"), (100_000, "")]
LENDS = [100_000, 200_000, 300_000, 500_000]
def band(sh):
    if sh < 1.25: return "g1", "1.00"
    if sh < 2.00: return "g2", "1.13"
    return "g3", "1.91"
gv = io.StringIO(); G = gv.write
G('    <div class="tbl-s"><div class="grid" style="grid-template-columns:auto repeat(%d,1fr)">\n' % len(LENDS))
G('      <div class="ghead"></div>\n')
for L in LENDS:
    G('      <div class="ghead">lend %s</div>\n' % f(L))
for b, note in BILLS:
    G('      <div class="grow">%s<em>%s</em></div>\n' % (f(b), note or "&nbsp;"))
    for L in LENDS:
        sh = 1.0 + L / float(b)
        cls, prem = band(sh)
        G('      <div class="gcell %s"><b>%s&times;</b><span class="sh">bill %s&times;</span></div>\n'
          % (cls, prem, "{:.2f}".format(sh)))
G('    </div></div>\n')

html = out.getvalue().replace("__PREMIUM_CHART__", sv.getvalue()).replace("__GRID__", gv.getvalue())
assert "__PREMIUM_CHART__" not in html and "__GRID__" not in html
io.open("/home/user/Paper3/telco-credit/outputs/dcb_dashboard.html","w",encoding="utf-8").write(html)
print("written", len(html), "bytes")

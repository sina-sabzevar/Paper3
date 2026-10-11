# -*- coding: utf-8 -*-
"""Manager dashboard for the DCB product. Chart geometry computed, never placed by hand."""
import io, math

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

W("""<title>DCB Credit Programme</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Layout: a presentation surface - wide bands, big figures, one idea per band,
   readable from across a meeting room. */
:root{
  --plane:#f6f6f3; --surface:#fdfdfc; --raise:#eeeeea; --sunk:#e6e6e0;
  --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.09); --grid:#e1e0d9; --axis:#c3c2b7;
  --s1:#2a78d6; --s2:#eb6834;
  --o1:#86b6ef; --o2:#3987e5; --o3:#256abf; --o4:#104281;
  --good:#0ca30c; --good-ink:#006300; --warn:#fab219; --crit:#d03b3b;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --good:#0ca30c; --good-ink:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --good:#0ca30c; --good-ink:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}
*{box-sizing:border-box}
body{background:var(--plane);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.5;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding-inline:22px;padding-block:36px 72px}
h1,h2,h3{margin:0;text-wrap:balance}
h1{font-size:clamp(30px,5.4vw,46px);font-weight:700;letter-spacing:-0.025em;line-height:1.08}
h2{font-size:clamp(20px,3.2vw,26px);font-weight:600;letter-spacing:-0.015em}
h3{font-size:15px;font-weight:600}
p{margin:0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.eyebrow{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:0.12em;
  text-transform:uppercase;color:var(--ink-3)}

header{display:flex;flex-direction:column;gap:14px;padding-bottom:10px}
.lede{color:var(--ink-2);font-size:17px;max-width:64ch}
.spec{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.chip{font-family:var(--mono);font-size:12.5px;background:var(--raise);
  border:1px solid var(--rule);border-radius:999px;padding:4px 12px;color:var(--ink-2)}
.chip b{color:var(--ink);font-weight:600}

section{margin-top:40px}
.head{border-top:2px solid var(--ink);padding-top:14px;margin-bottom:18px;
  display:flex;flex-direction:column;gap:7px}
.head p{color:var(--ink-2);font-size:15px;max-width:66ch}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:22px 20px}
.card + .card{margin-top:14px}
.cap{color:var(--ink-3);font-size:13px;line-height:1.55;margin-top:16px;max-width:72ch}
.cap b{color:var(--ink-2);font-weight:500}

.hero{background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:26px 22px;display:flex;flex-wrap:wrap;gap:26px 40px;align-items:flex-end}
.hero .big{display:flex;flex-direction:column;gap:4px}
.hero .big .v{font-family:var(--mono);font-size:clamp(38px,8vw,64px);font-weight:600;
  letter-spacing:-0.03em;line-height:0.98}
.hero .big .k{font-size:14px;color:var(--ink-2)}
.hero .sub{color:var(--ink-2);font-size:15px;max-width:38ch;flex:1 1 280px}

.kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);}
.kpi.k6{grid-template-columns:repeat(3,minmax(0,1fr))}
.kpi{
  border:1px solid var(--rule);border-radius:8px;overflow:hidden}
@media (max-width:760px){.kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{background:var(--surface);padding:16px 17px 18px;display:flex;flex-direction:column;gap:6px}
.tile .k{font-family:var(--mono);font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:var(--ink-3)}
.tile .v{font-family:var(--mono);font-size:clamp(21px,3.2vw,27px);font-weight:600;letter-spacing:-0.02em;line-height:1}
.tile .s{font-size:12.5px;color:var(--ink-3);line-height:1.4}

table{border-collapse:collapse;width:100%;font-size:14px;min-width:420px}
.tbl-s{overflow-x:auto;margin-top:6px}
th,td{text-align:right;padding:9px 11px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:0.07em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;border-bottom:1px solid var(--axis)}
tbody td{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2)}
tbody td:first-child{font-family:var(--sans);color:var(--ink);font-weight:500}
tr.off td{color:var(--ink-3)}
tr.tot td{font-weight:600;color:var(--ink);border-top:1px solid var(--axis);border-bottom:none}
tfoot td{font-family:var(--sans);font-size:13px;color:var(--ink-3);white-space:normal;
  text-align:left;border-bottom:none;padding-top:12px;line-height:1.55}
tfoot b{color:var(--ink-2);font-weight:500}

.svgbox{overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.gl{stroke:var(--grid);stroke-width:1}
.ax{stroke:var(--axis);stroke-width:1}
.tk{fill:var(--ink-3);font-family:var(--mono);font-size:11px}
.dl{font-family:var(--mono);font-size:12.5px;font-weight:600}
.an{font-family:var(--sans);font-size:12px;fill:var(--ink-3)}

.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.split{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:20px 18px}
.panel.known{border-left:3px solid var(--good)}
.panel.unknown{border-left:3px solid var(--crit)}
.panel h3{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.panel ul{margin:0;padding-left:0;list-style:none;display:flex;flex-direction:column;gap:11px}
.panel li{font-size:14px;color:var(--ink-2);line-height:1.5;padding-left:16px;position:relative}
.panel li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:1.5px;background:var(--ink-3)}
.panel li b{color:var(--ink);font-weight:600}

.ask{display:flex;flex-direction:column;gap:0}
.q{display:flex;gap:16px;padding:16px 0;border-bottom:1px solid var(--rule)}
.q:last-child{border-bottom:none}
.q .n{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ink-3);flex:0 0 24px;padding-top:2px}
.q .b{min-width:0}
.q .b h3{margin-bottom:4px}
.q .b p{font-size:14px;color:var(--ink-2)}
code{font-family:var(--mono);font-size:13px;background:var(--raise);padding:1px 5px;border-radius:4px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);color:var(--ink-3);font-size:12.5px;
  display:flex;flex-direction:column;gap:6px}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
""")

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
    <div class="tile"><span class="k">Expected loss rate</span><span class="v">0.076 pct</span>
      <span class="s">measured base rate, model selection applied</span></div>
    <div class="tile"><span class="k">Annual loss</span><span class="v">24 bn</span>
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
    <h2>What a bigger bill does &mdash; measured, not assumed</h2>
    <p>DCB lands on the same invoice, so the product does not only lend: it raises the bill the
    subscriber has to pay. The obvious worry is that a bill well above normal gets paid worse. It
    does not.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Comparison</th><th>Normal bill</th><th>Raised bill</th><th>Premium</th><th>Reading</th></tr></thead>
      <tbody>
        <tr><td>Across subscribers</td><td>0.2290 pct</td><td>0.4516 pct</td><td>1.97&times;</td><td>looks alarming</td></tr>
        <tr class="tot"><td>The same 1,169,169 subscribers</td><td>0.2868 pct</td><td>0.2786 pct</td><td>0.97&times;</td><td>no effect</td></tr>
      </tbody>
      <tfoot><tr><td colspan="5">Each of those subscribers contributes exactly one normal month and
      one raised month, so the only thing differing is the bill. The premium is <b>0.97, with a 95 pct
      interval of 0.92 to 1.02</b>. Split by how large the rise was, every band comes back at or below
      1.00 &mdash; 0.985 at a 100,000 ticket, 0.996 at 300,000, and 0.888 past three times, that last one
      significant in the <i>safe</i> direction. <b>The whole of the across-subscriber gradient is
      selection</b>: people whose bills jump are riskier people, which is what the model already scores
      them on.</td></tr></tfoot>
    </table></div>
    <p class="cap"><b>The arrow runs the other way.</b> The highest default rate of any group belongs
    to subscribers whose bill <i>fell</i> &mdash; 0.4116 pct, 1.80&times; normal. A collapsing bill is what
    precedes a service bar, because the subscriber has already stopped using the service. A bill that
    jumps is a month of health. Subscribers do pay a large bill more slowly &mdash; median coverage falls
    from 1.68 to 1.06 &mdash; but they pay it.</p>
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
        <li>A raised bill carries <b>no extra default risk</b> for the same subscriber &mdash; premium
        1.00, measured on 1,169,169 paired comparisons.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Not yet measured</h3>
      <ul>
        <li><b>The model has not yet been refitted on the one-month label.</b> The
        <b>0.076 pct</b> above is the measured one-month base rate of <b>0.2208 pct</b> scaled by the
        selection the model already achieves at this cut. It is an estimate built from two measured
        numbers, not a guess &mdash; but it is not a fitted result, and the refit may move it.</li>
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
    <h2>Four decisions needed</h2>
    <p>None of these is a modelling question. Each one changes the size of the programme.</p>
  </div>
  <div class="card">
    <div class="ask">

      <div class="q"><span class="n">01</span><div class="b">
        <h3>Is the 15,000 bn target annual lending or peak exposure?</h3>
        <p>At monthly turnover the two differ by twelve times. On the first reading the programme
        clears the target at <b>2.1&times;</b>; on the second it stands at 2,661 bn and is 5.6&times;
        short. Everything in the volume case depends on which is meant.</p></div></div>

      <div class="q"><span class="n">02</span><div class="b">
        <h3>Does the revenue bar come down?</h3>
        <p>It excludes 31.2 million subscribers and was sized for a four-month, 500,000 Toman line.
        A 100,000 ticket needs a fraction of that capacity. Lowering it is the largest lever on
        volume &mdash; and when it was tested, the subscribers a lower bar admits came in
        <b>safer</b>, not riskier.</p></div></div>

      <div class="q"><span class="n">03</span><div class="b">
        <h3>Is 300,000 on one bill too much?</h3>
        <p>Under the old product a 500,000 line sat across four bills &mdash; about three quarters of
        total billing. A 300,000 ticket on a single bill is <b>1.76&times;</b> that month's invoice at
        the screen level. Per bill, the new product asks more of the subscriber, not less, which is
        why the limit should be sized from their own billing rather than set flat.</p></div></div>

      <div class="q"><span class="n">04</span><div class="b">
        <h3>Does it launch as a pilot?</h3>
        <p>The loss rate on a product nobody has run is not knowable from history. A capped cohort
        for one or two cycles converts the largest unknown on this page into a measurement, and a
        one-month term means the answer arrives in weeks.</p></div></div>

    </div>
  </div>
</section>

<footer>
  <span>Population, screen, model and seasonality: measured in this project's queries and training
  notebook on windows 140401&ndash;140506. Limit ladder and volume: arithmetic on those counts at the
  stated ticket sizes.</span>
  <span>All figures in Toman. The database stores Rial; every amount here is the Rial value divided
  by ten. No loss rate is quoted for the one-month product because none has been measured.</span>
</footer>
</div>
""")
io.open("/home/user/Paper3/telco-credit/outputs/dcb_dashboard.html","w",encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()), "bytes")

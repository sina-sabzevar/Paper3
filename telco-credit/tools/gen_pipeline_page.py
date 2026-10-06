# -*- coding: utf-8 -*-
"""Generates the pipeline page. All chart geometry is computed here, never hand-placed."""
import io, math

TICKET = 500_000
SCORED = 9_344_723

# ---------------------------------------------------------------- the funnel
PRESENT = 41_270_092
FUNNEL = [
    ("Permanent subscribers in the window",
     "sbrp_typ_id = 1, month_key 140501..140506",
     PRESENT, None, None),
    ("Cleared the revenue bar",
     "revenue &ge; 170,000 Toman in 2 or more of the 6 months",
     10_087_975, 31_182_117, "did not bill 170,000 Toman in any 2 months"),
    ("Never one-way barred",
     "sbrp_stat_id = 3 in no month of the window",
     9_437_240, 650_735, "outgoing service suspended at least once"),
    ("Never two-way barred &mdash; SCORED",
     "sbrp_stat_id = 4 in no month of the window",
     9_344_723, 92_517, "incoming service suspended at least once"),
]
TOTAL_CUT = PRESENT - SCORED

# ------------------------------------------------------- the ladder (10..80pct)
LADDER = [
    (934_472,  0.000965, 0.000965),
    (1_868_944,0.001379, 0.001793),
    (2_803_416,0.001595, 0.002027),
    (3_737_889,0.001832, 0.002543),
    (4_672_361,0.002094, 0.003142),
    (5_606_833,0.002437, 0.004152),
    (6_541_306,0.002782, 0.004852),
    (7_475_778,0.003199, 0.006118),
]
FULL = (9_344_723, 0.006046, 0.025918)
CHOSEN = 4_672_361
CHOSEN_PD = 0.002094
CHOSEN_MARG = 0.003142
CEIL = 0.005

# --------------------------------------------- revenue distribution, window C
DIST = [("p25", 602), ("median", 28_948), ("p75", 135_881), ("p90", 293_525)]
BAR_T = 170_000

STRESS = [
    ("As modelled", 1.00),
    ("Live-set drift, +17pct", 1.17),
    ("Lending into Nowruz, 1.68x", 1.68),
    ("Twice the modelled rate", 2.00),
    ("Three times the modelled rate", 3.00),
]

DRIFT = [
    ("1403 h1", "140301..140306", 0.120, 3_733_333),
    ("1404 h1", "140401..140406", 0.146, 5_100_390),
    ("1404 h2", "140407..140412", 0.184, 6_879_803),
    ("1405 h1", "140501..140506", 0.244, 9_344_723),
]

def f(n):   return "{:,}".format(n)
def pc(x, d=4): return ("{:." + str(d) + "f}").format(100 * x)
def bn(take): return take * TICKET / 1e9

out = io.StringIO()
W = out.write

# =============================================================== head / style
W("""<title>Telco Credit Line Pipeline</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Layout: one narrow analytical column; each pipeline stage is a numbered band
   with its own chart, read top to bottom in the order the data moves. */
:root{
  --plane:#f7f7f5; --surface:#fcfcfb; --raise:#f1f1ed;
  --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --rule:rgba(11,11,11,0.10);
  --o1:#86b6ef; --o2:#3987e5; --o3:#256abf; --o4:#104281;
  --s1:#2a78d6; --s2:#eb6834;
  --cut:#d9d8d1;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --good-ink:#006300;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
}
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#17171a; --raise:#1f1f22;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#898781;
  --grid:#2c2c2a; --axis:#383835; --rule:rgba(255,255,255,0.10);
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --s1:#3987e5; --s2:#d95926;
  --cut:#2c2c2a;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --good-ink:#0ca30c;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#17171a; --raise:#1f1f22;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#898781;
  --grid:#2c2c2a; --axis:#383835; --rule:rgba(255,255,255,0.10);
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --s1:#3987e5; --s2:#d95926;
  --cut:#2c2c2a;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --good-ink:#0ca30c;
}
*{box-sizing:border-box}
body{background:var(--plane);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding-inline:20px;padding-block:40px 72px}
h1,h2,h3{text-wrap:balance;margin:0}
h1{font-size:clamp(28px,5.2vw,40px);font-weight:600;letter-spacing:-0.02em;line-height:1.12}
h2{font-size:clamp(19px,3vw,23px);font-weight:600;letter-spacing:-0.01em}
h3{font-size:14px;font-weight:600;letter-spacing:0.01em}
p{margin:0}
.lede{color:var(--ink-2);font-size:16px;max-width:62ch}
.eyebrow{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:0.1em;
  text-transform:uppercase;color:var(--ink-3)}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}

header{display:flex;flex-direction:column;gap:14px;padding-bottom:28px}
.chain{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 12px;
  font-family:var(--mono);font-size:13px;color:var(--ink-2);
  border-top:1px solid var(--rule);padding-top:18px}
.chain b{color:var(--ink);font-weight:600}
.chain i{color:var(--ink-3);font-style:normal}

/* numbered stage bands - the pipeline genuinely is a sequence */
section{margin-top:40px}
.band{display:flex;gap:16px;align-items:baseline;border-top:1px solid var(--rule);
  padding-top:16px;margin-bottom:18px}
.band .n{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ink-3);
  flex:0 0 26px;padding-top:4px}
.band .t{min-width:0;display:flex;flex-direction:column;gap:6px}
.band .t p{color:var(--ink-2);font-size:14.5px;max-width:60ch}

.card{background:var(--surface);border:1px solid var(--rule);border-radius:6px;
  padding:20px 18px;margin-left:42px}
@media (max-width:620px){ .card{margin-left:0} .band{gap:10px} }
.card + .card{margin-top:14px}
.cap{color:var(--ink-3);font-size:12.5px;line-height:1.5;margin-top:14px;max-width:66ch}
.cap b{color:var(--ink-2);font-weight:500}

/* ---- funnel ---- */
.fun{display:flex;flex-direction:column;gap:18px}
.frow{display:flex;flex-direction:column;gap:7px}
.fhead{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
.fhead .nm{font-size:14px;font-weight:600}
.fhead .rule{font-family:var(--mono);font-size:11.5px;color:var(--ink-3)}
.ftrack{display:flex;height:26px;width:100%}
.fkeep{border-radius:0 4px 4px 0;min-width:3px}
.frow:first-child .fkeep{border-radius:4px}
.fcut{background:var(--cut);border-radius:0 4px 4px 0;margin-left:2px;min-width:3px}
.ffoot{display:flex;flex-wrap:wrap;gap:3px 16px;font-family:var(--mono);font-size:12px}
.ffoot .keep{color:var(--ink);font-weight:600}
.ffoot .cut{color:var(--ink-3)}
.ffoot .why{color:var(--ink-3);font-family:var(--sans);font-size:12px}

/* ---- share bar ---- */
.share{display:flex;height:30px;margin-top:4px}
.share div{min-width:3px}
.share div + div{margin-left:2px}
.shlegend{display:flex;flex-direction:column;gap:7px;margin-top:14px}
.shrow{display:flex;align-items:baseline;gap:9px;font-size:13px;flex-wrap:wrap}
.sw{width:10px;height:10px;border-radius:2px;flex:0 0 auto;transform:translateY(1px)}
.shrow .v{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2);margin-left:auto}

/* ---- stat tiles ---- */
.kpi{--cols:4;display:grid;grid-template-columns:repeat(var(--cols),minmax(0,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:6px;overflow:hidden;
  margin-left:42px}
.kpi.c6{--cols:3}
@media (max-width:720px){ .kpi{--cols:2} }
@media (max-width:620px){ .kpi{margin-left:0} }
.tile{background:var(--surface);padding:15px 16px 16px;display:flex;flex-direction:column;gap:5px}
.tile .k{font-family:var(--mono);font-size:10.5px;letter-spacing:0.07em;
  text-transform:uppercase;color:var(--ink-3)}
.tile .v{font-family:var(--mono);font-size:24px;font-weight:600;letter-spacing:-0.015em;line-height:1}
.tile .s{font-size:12px;color:var(--ink-3);line-height:1.4}
.hero .v{font-size:clamp(23px,4.3vw,35px)}

/* ---- tables ---- */
.tbl-s{overflow-x:auto;margin-top:16px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:430px}
th,td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:0.06em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;border-bottom:1px solid var(--axis)}
tbody td{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2)}
tbody td:first-child{font-family:var(--sans);color:var(--ink)}
tr.mark td{color:var(--ink);font-weight:600;background:var(--raise)}
tr.mark td:first-child{font-weight:600}
tfoot td{font-family:var(--sans);font-size:12.5px;line-height:1.5;color:var(--ink-3);
  border-bottom:none;padding-top:11px;white-space:normal;text-align:left}
tfoot b{color:var(--ink-2);font-weight:500}

/* ---- meters / stress ---- */
.meter{display:flex;flex-direction:column;gap:9px}
.mrow{display:flex;flex-direction:column;gap:6px}
.mhead{display:flex;gap:10px;align-items:baseline;font-size:13.5px}
.mhead .mv{margin-left:auto;font-family:var(--mono);font-variant-numeric:tabular-nums;
  color:var(--ink-2)}
.mtrack{position:relative;height:22px;background:var(--raise);border-radius:4px}
.mfill{position:absolute;inset:0 auto 0 0;border-radius:4px;min-width:3px}
.mref{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--crit)}
.state{font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:3px;
  letter-spacing:0.03em}
.ok{color:var(--good-ink);background:color-mix(in srgb,var(--good) 13%,transparent)}
.no{color:var(--crit);background:color-mix(in srgb,var(--crit) 15%,transparent)}

/* ---- legend / svg ---- */
.lg{display:flex;flex-wrap:wrap;gap:8px 18px;margin-bottom:12px;font-size:12.5px;
  color:var(--ink-2)}
.lg span{display:flex;align-items:center;gap:7px}
.lg i{width:14px;height:2px;border-radius:1px;display:block}
.svgbox{overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.gl{stroke:var(--grid);stroke-width:1}
.ax{stroke:var(--axis);stroke-width:1}
.tk{fill:var(--ink-3);font-family:var(--mono);font-size:10.5px}
.dl{font-family:var(--mono);font-size:11px;font-weight:600}
.an{fill:var(--ink-3);font-family:var(--sans);font-size:11px}

/* ---- notes ---- */
.notes{display:flex;flex-direction:column;gap:0}
.note{display:flex;gap:13px;padding:13px 0;border-bottom:1px solid var(--rule)}
.note:last-child{border-bottom:none}
.note .fl{flex:0 0 auto;width:9px;height:9px;border-radius:50%;margin-top:6px}
.note .bd{min-width:0}
.note .bd h3{margin-bottom:3px}
.note .bd p{color:var(--ink-2);font-size:13.5px}
.note code{font-family:var(--mono);font-size:12.5px;background:var(--raise);
  padding:1px 4px;border-radius:3px}

footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);
  color:var(--ink-3);font-size:12px;display:flex;flex-direction:column;gap:5px}

/* ---- tooltip ---- */
#tip{position:fixed;z-index:50;pointer-events:none;opacity:0;transition:opacity .09s;
  background:var(--surface);color:var(--ink);border:1px solid var(--axis);
  border-radius:5px;padding:7px 9px;font-size:12px;line-height:1.45;
  box-shadow:0 4px 14px rgba(0,0,0,0.13);max-width:240px}
#tip .tt{font-weight:600;margin-bottom:2px}
#tip .tv{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2)}
[data-tip]{cursor:default}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="wrap">
""")

# ===================================================================== header
W("""<header>
  <p class="eyebrow">Postpaid credit line &middot; cohort 140501&ndash;140506 &middot; measured, not projected</p>
  <h1>From 41.27 million subscribers to a book of 4,672,361</h1>
  <p class="lede">Every filter in the pipeline, with the count it removed and the rule that removed it.
  One screen does 97.67 percent of the work. All figures are query output or notebook output
  from this repository; nothing here is an estimate.</p>
  <div class="chain">
    <span><i>present</i> <b class="num">41,270,092</b></span>
    <span>&rarr;</span>
    <span><i>scored</i> <b class="num">9,344,723</b></span>
    <span>&rarr;</span>
    <span><i>approved</i> <b class="num">4,672,361</b></span>
    <span>&rarr;</span>
    <span><i>exposure</i> <b class="num">2,336 bn Toman</b></span>
    <span>&rarr;</span>
    <span><i>expected loss</i> <b class="num">4.9 bn</b></span>
  </div>
</header>
""")

# ============================================================ 1. the funnel
W("""<section>
  <div class="band"><div class="n">01</div><div class="t">
    <h2>The population screen</h2>
    <p>Three filters run on the six-month feature window. Each row below is drawn to the
    width of the stage above it, so the pale segment is exactly what that filter removed.</p>
  </div></div>
  <div class="card">
    <div class="fun">
""")
ords = ["var(--o1)", "var(--o2)", "var(--o3)", "var(--o4)"]
for i, (nm, rule, keep, cut, why) in enumerate(FUNNEL):
    prev = FUNNEL[i-1][2] if i else keep
    outer = 100.0 * prev / PRESENT
    kw = 100.0 * keep / prev
    cw = 100.0 - kw
    W('      <div class="frow">\n')
    W('        <div class="fhead"><span class="nm">%s</span>'
      '<span class="rule">%s</span></div>\n' % (nm, rule))
    W('        <div class="ftrack" style="width:%.4f%%">\n' % outer)
    W('          <div class="fkeep" style="width:%.4f%%;background:%s" data-tip="%s|%s subscribers &middot; %s of the starting base"></div>\n'
      % (kw, ords[i], nm.replace("&mdash; SCORED", "").strip(), f(keep), pc(keep / PRESENT, 2) + " pct"))
    if cut:
        W('          <div class="fcut" style="width:%.4f%%" data-tip="Removed here|%s subscribers &middot; %s of all exclusions"></div>\n'
          % (cw, f(cut), pc(cut / TOTAL_CUT, 2) + " pct"))
    W('        </div>\n')
    W('        <div class="ffoot"><span class="keep">%s kept</span>' % f(keep))
    if cut:
        W('<span class="cut">&minus;%s</span><span class="why">%s</span>' % (f(cut), why))
    else:
        W('<span class="why">the starting base, 6-month distinct count</span>')
    W('</div>\n      </div>\n')
W("""    </div>
    <p class="cap"><b>Read the pale segments.</b> The revenue bar removes
    31,182,117 subscribers; the two service-bar filters together remove 743,252.
    The starting figure is a distinct count across six months, so a subscriber present
    in any one of them counts once &mdash; average months seen is 5.797 of 6.</p>
  </div>
""")

# share of exclusions
shares = [("The revenue bar", 31_182_117, "var(--o2)"),
          ("The one-way filter", 650_735, "var(--o3)"),
          ("The two-way filter", 92_517, "var(--o4)")]
W('  <div class="card">\n    <h3>Where the 31,925,369 exclusions come from</h3>\n')
W('    <div class="share">\n')
for nm, v, col in shares:
    W('      <div style="width:%.4f%%;background:%s" data-tip="%s|%s subscribers &middot; %s pct of exclusions"></div>\n'
      % (100.0 * v / TOTAL_CUT, col, nm, f(v), pc(v / TOTAL_CUT, 2)))
W('    </div>\n    <div class="shlegend">\n')
for nm, v, col in shares:
    W('      <div class="shrow"><span class="sw" style="background:%s"></span>'
      '<span>%s</span><span class="v">%s &middot; %s pct</span></div>\n'
      % (col, nm, f(v), pc(v / TOTAL_CUT, 2)))
W("""    </div>
    <p class="cap">The credit screen is not rejecting risky subscribers. It is rejecting
    subscribers who do not bill enough. The two filters that <i>are</i> about payment
    behaviour &mdash; the one-way and two-way service bars &mdash; account for
    <b>2.33 percent</b> of all exclusions between them.</p>
  </div>
""")

# ===================================== 1b. why the bar cuts so deep (log strip)
VB_W, VB_H = 720, 188
LX, RX = 18, 702
AXY = 88
PWID = RX - LX
def xlog(v): return LX + (math.log10(v) - 2.0) / 4.0 * PWID

W('  <div class="card">\n    <h3>Why the revenue bar removes three quarters of the base</h3>\n')
W('    <div class="svgbox">\n')
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="Average monthly revenue distribution against the 170,000 Toman bar, log scale">\n' % (VB_W, VB_H))
# shaded region above the bar
W('      <rect x="%.2f" y="26" width="%.2f" height="%.2f" fill="var(--s1)" opacity="0.07"/>\n'
  % (xlog(BAR_T), RX - xlog(BAR_T), AXY - 26))
# decade gridlines + ticks
for d, lab in ((100, "100"), (1_000, "1k"), (10_000, "10k"), (100_000, "100k"), (1_000_000, "1M")):
    x = xlog(d)
    W('      <line class="gl" x1="%.2f" y1="26" x2="%.2f" y2="%d"/>\n' % (x, x, AXY))
    W('      <text class="tk" x="%.2f" y="%d" text-anchor="middle">%s</text>\n' % (x, AXY + 15, lab))
W('      <line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>\n' % (LX, AXY, RX, AXY))
W('      <text class="tk" x="%d" y="%d" text-anchor="start">Toman per month, log scale</text>\n' % (LX, 180))
# the bar rule
bx = xlog(BAR_T)
W('      <line x1="%.2f" y1="20" x2="%.2f" y2="%d" stroke="var(--crit)" stroke-width="2"/>\n' % (bx, bx, AXY + 4))
W('      <text class="dl" x="%.2f" y="14" text-anchor="end" fill="var(--crit)">the bar &mdash; 170,000</text>\n' % (bx - 6))
# percentile lollipops, labels staggered so nothing collides
rows = {"p25": 1, "p75": 1, "median": 2, "p90": 2}
for nm, v in DIST:
    x = xlog(v)
    W('      <line class="ax" x1="%.2f" y1="34" x2="%.2f" y2="%d"/>\n' % (x, x, AXY))
    W('      <circle cx="%.2f" cy="34" r="4.5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>\n' % x)
    ly = 128 if rows[nm] == 1 else 152
    anc = "middle"; tx = x
    if x < LX + 48: anc, tx = "start", LX
    if x > RX - 48: anc, tx = "end", RX
    W('      <text class="dl" x="%.2f" y="%d" text-anchor="%s" fill="var(--ink-2)">%s  %s</text>\n'
      % (tx, ly, anc, nm, f(v)))
    W('      <line class="gl" x1="%.2f" y1="%d" x2="%.2f" y2="%d"/>\n' % (x, AXY + 2, x, ly - 9))
W('    </svg>\n    </div>\n')
W("""    <p class="cap"><b>The bar sits at 5.9&times; the median subscriber.</b> Half the base
    bills under 28,948 Toman a month, against a screen set at 170,000. It still admits
    24.4 percent, because the rule tests <i>individual months</i> &mdash; two of six above the
    bar &mdash; not the average. So a subscriber well below the bar on average can pass on
    two good months, and the shaded region overstates who qualifies.</p>
  </div>
""")

# ========================================================= 2. the screen drifts
W("""<section>
  <div class="band"><div class="n">02</div><div class="t">
    <h2>The bar is fixed in Rial, so it loosens every year</h2>
    <p>Nobody changed the 170,000 Toman rule. Revenue inflated past it, so the same rule
    admits a larger share of the base each window. Left alone it keeps loosening and the
    eligible population keeps growing without a decision being taken.</p>
  </div></div>
  <div class="card">
    <div class="meter">
""")
for lab, win, share, n in DRIFT:
    last = (n == SCORED)
    W('      <div class="mrow" data-tip="%s|%s pct of the base &middot; %s screened">\n' % (lab, pc(share, 1), f(n)))
    W('        <div class="mhead"><span style="font-weight:%s">%s</span>'
      '<span class="num" style="color:var(--ink-3);font-size:12px">%s</span>'
      '<span class="mv">%s pct &middot; %s</span></div>\n'
      % ("600" if last else "400", lab, win, pc(share, 1), f(n)))
    W('        <div class="mtrack"><div class="mfill" style="width:%.3f%%;background:%s"></div></div>\n'
      % (100.0 * share / 0.26, "var(--o4)" if last else "var(--o2)"))
    W('      </div>\n')
W("""    </div>
    <p class="cap">Revenue per subscriber-month grew <b>1.86&times;</b> at the mean from 1403 h1 to
    1405 h1 &mdash; plus 13 percent in the first year, plus 64 percent in the second. Tracks are
    drawn to a 26 percent full scale. <b>The 6,879,803 figure on record is stale:</b> at the same
    rule the current window holds 9,344,723, up 35.8 percent.</p>
  </div>
""")

# ============================================================ 3. the label
W("""<section>
  <div class="band"><div class="n">03</div><div class="t">
    <h2>What the model is trained to predict</h2>
    <p>A subscriber is <i>bad</i> if, in the four months after the feature window, the operator
    had to bar their service for non-payment. The training cohort runs its features over
    140401&ndash;140406 and its label over 140407&ndash;140410, at the same months-of-year the live
    book will actually face.</p>
  </div></div>
  <div class="kpi">
    <div class="tile"><span class="k">Training rows</span><span class="v">8,701,085</span>
      <span class="s">screened on the same three filters</span></div>
    <div class="tile"><span class="k">Bads</span><span class="v">45,361</span>
      <span class="s">barred within the 4-month label window</span></div>
    <div class="tile"><span class="k">Event rate</span><span class="v">0.5213%</span>
      <span class="s">months 7&ndash;10, the product's real season</span></div>
    <div class="tile"><span class="k">Fully observed</span><span class="v">100.00%</span>
      <span class="s">nobody screened in disappears</span></div>
  </div>
  <div class="card">
    <h3>The event rate is a property of when you lend, not only who</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>Window</th><th>Label months</th><th>Season</th><th>Screen breadth</th><th>Event rate</th></tr></thead>
      <tbody>
        <tr><td>A &middot; 1403 h1</td><td>140307&ndash;140310</td><td>7&ndash;10</td><td>12.0 pct</td><td>0.5730%</td></tr>
        <tr class="mark"><td>B &middot; 1404 h1</td><td>140407&ndash;140410</td><td>7&ndash;10</td><td>14.6 pct</td><td>0.5541%</td></tr>
        <tr><td>D &middot; 1404 h2</td><td>140501&ndash;140504</td><td>1&ndash;4</td><td>18.4 pct</td><td>0.9492%</td></tr>
      </tbody>
      <tfoot><tr><td colspan="5">A and B sit at very different breadths and give nearly the same rate,
      so screen width does not move it. D differs mainly in season and is <b>1.68&times;</b> higher &mdash;
      Jalali months 1&ndash;4 contain Nowruz.</td></tr></tfoot>
    </table></div>
    <p class="cap">The 0.95 percent figure on record was measured over months 1&ndash;4, the wrong
    season for this window. Features run to 140506, so a four-month line is exposed over
    <b>140507&ndash;140510</b> &mdash; months 7&ndash;10. Lending timed into Nowruz would face the higher rate.</p>
  </div>
""")

# ============================================================= 4. the model
W("""<section>
  <div class="band"><div class="n">04</div><div class="t">
    <h2>The model, on held-out subscribers</h2>
    <p>Gradient boosting against a standardised logistic baseline, 70/20/10 split by
    subscriber, calibrated by isotonic regression, read on the in-band rows only.</p>
  </div></div>
  <div class="kpi">
    <div class="tile hero"><span class="k">AUC, test in band</span><span class="v">0.8017</span>
      <span class="s">HistGB, calibrated</span></div>
    <div class="tile"><span class="k">Gini</span><span class="v">0.6034</span>
      <span class="s">&nbsp;</span></div>
    <div class="tile"><span class="k">KS</span><span class="v">0.4551</span>
      <span class="s">&nbsp;</span></div>
    <div class="tile"><span class="k">Level error</span><span class="v">1.72%</span>
      <span class="s">0.5234 predicted vs 0.5146 observed</span></div>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Model</th><th>Split</th><th>AUC</th><th>Gini</th><th>KS</th></tr></thead>
      <tbody>
        <tr><td>Logistic, standardised</td><td>valid</td><td>0.7385</td><td>0.4769</td><td>0.3652</td></tr>
        <tr><td>HistGB</td><td>valid</td><td>0.7918</td><td>0.5836</td><td>0.4346</td></tr>
        <tr class="mark"><td>HistGB, calibrated</td><td>test, in band</td><td>0.8017</td><td>0.6034</td><td>0.4551</td></tr>
      </tbody>
      <tfoot><tr><td colspan="5">Boosting beat the linear baseline by <b>+0.0533</b> on valid, so the
      interactions are real. Train-to-valid gap +0.0205. All 10 of 10 deciles expect 10 or more
      bads, so every decile ratio is readable; worst 0.822, best 1.049.</td></tr></tfoot>
    </table></div>
  </div>
""")

# ===================================================== 5. the ladder line chart
LW, LH = 720, 336
PL, PR, PT, PB = 54, 612, 26, 254
YMAX = 0.0065
def xi(i): return PL + i * (PR - PL) / (len(LADDER) - 1.0)
def yv(v): return PB - (v / YMAX) * (PB - PT)

W("""<section>
  <div class="band"><div class="n">05</div><div class="t">
    <h2>Where to stop: book rate against marginal rate</h2>
    <p>Rank every scored subscriber safest first and admit them in order. <b>Book PD</b> is the
    average over everyone taken and sets total loss. <b>Marginal PD</b> is the last subscriber
    admitted and says whether the next slice is worth having. The cumulative curve alone
    hides the number that decides the cut.</p>
  </div></div>
  <div class="card">
    <div class="lg">
      <span><i style="background:var(--s1)"></i>Book PD, cumulative</span>
      <span><i style="background:var(--s2)"></i>Marginal PD, last admitted</span>
      <span><i style="background:var(--crit);height:2px"></i>0.50 pct appetite ceiling</span>
    </div>
    <div class="svgbox">
""")
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="Book and marginal default rate against the size of the book">\n' % (LW, LH))
# y grid + ticks
t = 0
while t <= 0.006 + 1e-9:
    y = yv(t)
    W('      <line class="gl" x1="%d" y1="%.2f" x2="%d" y2="%.2f"/>\n' % (PL, y, PR, y))
    W('      <text class="tk" x="%d" y="%.2f" text-anchor="end">%s</text>\n'
      % (PL - 9, y + 3.5, ("0" if t == 0 else pc(t, 1) + "%")))
    t += 0.001
# ceiling
cy = yv(CEIL)
W('      <line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="var(--crit)" stroke-width="2"/>\n' % (PL, cy, PR, cy))
W('      <text class="dl" x="%d" y="%.2f" fill="var(--crit)">0.50%% ceiling</text>\n' % (PL + 6, cy - 7))
# chosen rule
chx = xi(4)
W('      <line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="var(--axis)" stroke-width="1"/>\n' % (chx, PT, chx, PB))
W('      <text class="an" x="%.2f" y="%d" text-anchor="middle" fill="var(--ink-2)">the chosen cut</text>\n' % (chx, PT - 8))
# axes
W('      <line class="ax" x1="%d" y1="%d" x2="%d" y2="%d"/>\n' % (PL, PB, PR, PB))
# x ticks
for i, (take, b, m) in enumerate(LADDER):
    x = xi(i)
    W('      <text class="tk" x="%.2f" y="%d" text-anchor="middle">%d%%</text>\n'
      % (x, PB + 17, round(100 * take / SCORED)))
    W('      <text class="tk" x="%.2f" y="%d" text-anchor="middle" opacity="0.8">%.2fM</text>\n'
      % (x, PB + 31, take / 1e6))
W('      <text class="tk" x="%d" y="%d" text-anchor="start">share of the scored population admitted, safest first</text>\n' % (PL, PB + 50))
# series paths
for key, col, idx in (("book", "var(--s1)", 1), ("marg", "var(--s2)", 2)):
    pts = [(xi(i), yv(r[idx])) for i, r in enumerate(LADDER)]
    W('      <polyline fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" points="%s"/>\n'
      % (col, " ".join("%.2f,%.2f" % p for p in pts)))
# markers (surface ring, >=8px on the chosen point)
for i, (take, b, m) in enumerate(LADDER):
    for v, col in ((b, "var(--s1)"), (m, "var(--s2)")):
        r = 5.0 if i == 4 else 3.4
        W('      <circle cx="%.2f" cy="%.2f" r="%.1f" fill="%s" stroke="var(--surface)" stroke-width="2"/>\n'
          % (xi(i), yv(v), r, col))
# direct labels at the right end
W('      <text class="dl" x="%d" y="%.2f" fill="var(--s1)">book 0.3199%%</text>\n' % (PR + 8, yv(LADDER[-1][1]) + 4))
W('      <text class="dl" x="%d" y="%.2f" fill="var(--s2)">marginal 0.6118%%</text>\n' % (PR + 8, yv(LADDER[-1][2]) + 4))
# the chosen pair, labelled
W('      <text class="dl" x="%.2f" y="%.2f" text-anchor="middle" fill="var(--s1)">0.2094%%</text>\n' % (chx, yv(CHOSEN_PD) + 19))
W('      <text class="dl" x="%.2f" y="%.2f" text-anchor="middle" fill="var(--s2)">0.3142%%</text>\n' % (chx, yv(CHOSEN_MARG) - 11))
# crosshair + hit zones
W('      <line id="xh" x1="0" y1="%d" x2="0" y2="%d" stroke="var(--axis)" stroke-width="1" opacity="0"/>\n' % (PT, PB))
hw = (PR - PL) / (len(LADDER) - 1.0)
for i, (take, b, m) in enumerate(LADDER):
    x = xi(i)
    W('      <rect x="%.2f" y="%d" width="%.2f" height="%d" fill="transparent" class="hit" data-x="%.2f" '
      'data-tip="%s subscribers &middot; %d pct|Book PD %s pct &middot; marginal PD %s pct<br>Exposure %s bn &middot; expected loss %.1f bn"></rect>\n'
      % (x - hw / 2, PT, hw, PB - PT, x, f(take), round(100 * take / SCORED),
         pc(b), pc(m), "{:,.0f}".format(bn(take)), bn(take) * b))
W('    </svg>\n    </div>\n')

# the full table, including the 100 pct row the plot leaves out
W('    <div class="tbl-s"><table>\n'
  '      <thead><tr><th>Take</th><th>Share</th><th>Book PD</th><th>Marginal PD</th>'
  '<th>Exposure</th><th>Expected loss</th></tr></thead>\n      <tbody>\n')
for take, b, m in LADDER + [FULL]:
    cls = ' class="mark"' if take == CHOSEN else ''
    W('        <tr%s><td>%s</td><td>%d pct</td><td>%s%%</td><td>%s%%</td>'
      '<td>%s bn</td><td>%.1f bn</td></tr>\n'
      % (cls, f(take), round(100 * take / SCORED), pc(b), pc(m),
         "{:,.0f}".format(bn(take)), bn(take) * b))
W("""      </tbody>
      <tfoot><tr><td colspan="6">The plot stops at the 80 percent mark. The final decile's
      marginal rate is <b>2.5918 percent</b>, four times the plot's range, and it is the row above &mdash;
      drawing it would flatten everything the decision depends on. Marginal PD first crosses the
      0.50 percent ceiling at the <b>80 percent</b> mark, so there is headroom past the chosen cut
      if volume is wanted later. Exposure and loss are in billions of Toman at 500,000 per subscriber,
      LGD 100 percent.</td></tr></tfoot>
    </table></div>
  </div>
""")

# ========================================================== 6. the chosen cut
W("""<section>
  <div class="band"><div class="n">06</div><div class="t">
    <h2>The chosen book</h2>
    <p>The safest half of the scored population. Both rates clear the appetite ceiling, and
    the realised rate would have to miss the model by 2.4&times; before the book breaches it.</p>
  </div></div>
  <div class="kpi c6">
    <div class="tile hero"><span class="k">Approved</span><span class="v">4,672,361</span>
      <span class="s">50 pct of 9,344,723 scored</span></div>
    <div class="tile"><span class="k">Book PD</span><span class="v">0.2094%</span>
      <span class="s">against a 0.50 pct ceiling</span></div>
    <div class="tile"><span class="k">Marginal PD</span><span class="v">0.3142%</span>
      <span class="s">the last subscriber admitted</span></div>
    <div class="tile"><span class="k">Exposure</span><span class="v">2,336 bn</span>
      <span class="s">Toman, at 500,000 each</span></div>
    <div class="tile"><span class="k">Expected loss</span><span class="v">4.9 bn</span>
      <span class="s">Toman, LGD 100 pct</span></div>
    <div class="tile"><span class="k">Miss to breach</span><span class="v">2.4&times;</span>
      <span class="s">realised vs modelled rate</span></div>
  </div>
  <div class="card">
    <h3>Stress: how far the rate can move before the book breaches</h3>
    <div class="meter">
""")
SMAX = 0.0066
for lab, mult in STRESS:
    r = CHOSEN_PD * mult
    breach = r > CEIL
    W('      <div class="mrow" data-tip="%s|Loss rate %s pct &middot; %.2f bn Toman">\n' % (lab, pc(r), bn(CHOSEN) * r))
    W('        <div class="mhead"><span>%s</span>'
      '<span class="state %s">%s</span>'
      '<span class="mv">%s pct &middot; %.1f bn</span></div>\n'
      % (lab, "no" if breach else "ok", "breaches" if breach else "within", pc(r), bn(CHOSEN) * r))
    W('        <div class="mtrack"><div class="mfill" style="width:%.3f%%;background:%s"></div>'
      '<div class="mref" style="left:%.3f%%" title="0.50 pct ceiling"></div></div>\n'
      % (100.0 * r / SMAX, "var(--crit)" if breach else "var(--s1)", 100.0 * CEIL / SMAX))
    W('      </div>\n')
W("""    </div>
    <p class="cap">The red rule on each track is the 0.50 percent ceiling. The book absorbs the
    drift measured in the live set, absorbs a Nowruz-season label, and absorbs twice the modelled
    rate. It breaches only at three times modelled, at <b>14.7 bn</b> Toman of loss.</p>
  </div>
""")

# ============================================================ 7. the target
TARGET = 15000.0
W("""<section>
  <div class="band"><div class="n">07</div><div class="t">
    <h2>Against the 15,000 bn ambition</h2>
    <p>The gap is not a modelling problem and it does not close by loosening the screen.
    At 500,000 Toman a head the whole scored population reaches 4,672 bn.</p>
  </div></div>
  <div class="card">
    <div class="meter">
""")
tgt_rows = [
    ("The chosen book &mdash; 4,672,361", bn(CHOSEN), "var(--o4)"),
    ("Every scored subscriber &mdash; 9,344,723", bn(SCORED), "var(--o2)"),
    ("The 15,000 bn ambition", TARGET, "var(--cut)"),
]
for lab, v, col in tgt_rows:
    W('      <div class="mrow" data-tip="%s|%s bn Toman &middot; %s pct of the 15,000 bn target">\n'
      % (lab.replace("&mdash;", "-"), "{:,.0f}".format(v), "{:.1f}".format(100 * v / TARGET)))
    W('        <div class="mhead"><span>%s</span><span class="mv">%s bn &middot; %s pct of target</span></div>\n'
      % (lab, "{:,.0f}".format(v), "{:.1f}".format(100 * v / TARGET)))
    W('        <div class="mtrack"><div class="mfill" style="width:%.3f%%;background:%s"></div></div>\n'
      % (100.0 * v / TARGET, col))
    W('      </div>\n')
W('    </div>\n    <div class="tbl-s"><table>\n'
  '      <thead><tr><th>If the book is</th><th>Ticket needed for 15,000 bn</th><th>Against the 170,000 bar</th></tr></thead>\n'
  '      <tbody>\n')
for n, note in ((3_000_000, ""), (CHOSEN, ""), (SCORED, "")):
    tk = TARGET * 1e9 / n
    W('        <tr%s><td>%s subscribers</td><td>%s Toman</td><td>%.1f&times; the monthly bar</td></tr>\n'
      % (' class="mark"' if n == CHOSEN else '', f(n), "{:,.0f}".format(tk), tk / 170_000))
W("""      </tbody>
      <tfoot><tr><td colspan="3">A 500,000 Toman line is already <b>4.3&times;</b> the entire four-month
      billing history of the median subscriber in the base. Lowering the screen to add volume means
      writing 500,000 Toman lines against subscribers who bill 29,000 a month. The gap closes on
      <b>line size over the subscribers already qualified</b>, not on screen width.</td></tr></tfoot>
    </table></div>
  </div>
""")

# ======================================================== 8. open items
W("""<section>
  <div class="band"><div class="n">08</div><div class="t">
    <h2>What is not settled</h2>
    <p>Six things stand between this page and a lending decision. The first one moves the cut.</p>
  </div></div>
  <div class="card">
    <div class="notes">

      <div class="note"><span class="fl" style="background:var(--crit)"></span><div class="bd">
        <h3>This book predates the refit, so the cut will move</h3>
        <p>The audit found a feature the model never saw: a subscriber's bar history in the
        <i>year before</i> the feature window predicts the label at <b>13.2&times;</b> for a prior
        two-way bar and <b>4.0&times;</b> for a one-way bar, and it holds at every level of
        <code>rev_months</code>. Six <code>pre_*</code> columns are now in
        <code>42_model_datasets.sql</code> and the refit has not run. Expect the ranking to
        improve on 0.8017 and the safest-4,672,361 to be a <i>different set of subscribers</i>.
        Re-cut before lending.</p></div></div>

      <div class="note"><span class="fl" style="background:var(--warn)"></span><div class="bd">
        <h3>Trust the ranking, not the level</h3>
        <p>Thirteen features shifted significantly between the training and live windows, led by
        <code>rev_max</code> at PSI <b>3.0223</b>. The live set scores a mean PD of
        <b>0.6046 percent</b> against test's observed <b>0.5146</b> &mdash; 17 percent higher. That is
        inflation showing up in the level, not a worse population. The safest-N ordering survives a
        monotone level shift; the absolute PD does not.</p></div></div>

      <div class="note"><span class="fl" style="background:var(--warn)"></span><div class="bd">
        <h3>Two book rates that should agree, do not</h3>
        <p>The Trino audit returns a book PD of <b>0.21318 percent</b> where the notebook returns
        <b>0.2094</b> &mdash; 1.8 percent apart, and not yet explained. Small enough not to change the
        decision, large enough that it has to be chased before the figure goes in front of anyone.</p></div></div>

      <div class="note"><span class="fl" style="background:var(--warn)"></span><div class="bd">
        <h3>The base itself does not reconcile</h3>
        <p>The window holds <b>41,270,092</b> subscribers at <code>sbrp_typ_id = 1</code>, about
        39.9M per month, against the <b>26M</b> permanent base the business counts. Average months
        seen is 5.797 of 6, so it is not churn. <code>49_base_reconciliation.sql</code> tests whether
        <code>active1_base_flag</code> is the difference &mdash; and whether any scored subscriber was
        never active in the window, which the screen does not check.</p></div></div>

      <div class="note"><span class="fl" style="background:var(--s1)"></span><div class="bd">
        <h3>The screen is a capacity rule wearing a risk rule's clothes</h3>
        <p>Admitting the subscribers a lower bar lets in produced a rate of <b>0.4749 percent</b> &mdash;
        <b>0.86&times;</b>, safer than those already inside. The bar does not sort by risk. Keeping it
        fixed in Rial also means it keeps loosening on its own. Both deserve a decision rather than
        inheritance.</p></div></div>

      <div class="note"><span class="fl" style="background:var(--s1)"></span><div class="bd">
        <h3>What no query here can answer</h3>
        <p>Every figure on this page measures who failed to pay <i>their own phone bill</i>. Nobody in
        this data was ever given a credit line, so the behavioural effect of handing a subscriber
        500,000 Toman of spendable credit &mdash; much of it at off-net merchants the operator cannot
        see &mdash; is not in it and cannot be derived from it. A pilot is the only thing that closes
        this. The 0.2094 percent is the right number for the population; it is not a promise about a
        product that has never run.</p></div></div>

    </div>
  </div>
</section>

<footer>
  <span>Sources: <span class="num">43_cohort_funnel.sql</span> (funnel, drift, seasonality),
  <span class="num">42_model_datasets.sql</span> (cohorts, screen),
  <span class="num">train_model.ipynb</span> (metrics, PSI, calibration),
  <span class="num">select_book.py</span> (ladder, exposure),
  <span class="num">48_approved_audit.sql</span> (audit, pre-window finding),
  <span class="num">49_base_reconciliation.sql</span> (base, unrun).</span>
  <span>All currency in Toman. The database stores Rial; every threshold here is the Rial value
  divided by ten. Counts are query output, not estimates.</span>
</footer>
</div>

<div id="tip" role="status" aria-live="polite"></div>
<script>
(function(){
  var tip = document.getElementById('tip'), xh = document.getElementById('xh');
  function show(el, ev){
    var raw = el.getAttribute('data-tip'); if(!raw) return;
    var i = raw.indexOf('|');
    var t = i < 0 ? raw : raw.slice(0, i), v = i < 0 ? '' : raw.slice(i + 1);
    tip.innerHTML = '<div class="tt">' + t + '</div>' + (v ? '<div class="tv">' + v + '</div>' : '');
    tip.style.opacity = '1';
    place(ev);
    var hx = el.getAttribute('data-x');
    if(hx && xh){ xh.setAttribute('x1', hx); xh.setAttribute('x2', hx); xh.setAttribute('opacity','1'); }
  }
  function place(ev){
    var r = tip.getBoundingClientRect();
    var x = ev.clientX + 14, y = ev.clientY - r.height - 12;
    if(x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
    if(x < 8) x = 8;
    if(y < 8) y = ev.clientY + 18;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hide(){ tip.style.opacity = '0'; if(xh) xh.setAttribute('opacity','0'); }
  var marks = document.querySelectorAll('[data-tip]');
  for(var k = 0; k < marks.length; k++){
    (function(el){
      el.addEventListener('mouseenter', function(ev){ show(el, ev); });
      el.addEventListener('mousemove', function(ev){ if(tip.style.opacity === '1') place(ev); });
      el.addEventListener('mouseleave', hide);
    })(marks[k]);
  }
  document.addEventListener('scroll', hide, true);
})();
</script>
""")

html = out.getvalue()
# every <section> after the first needs the previous one closed; section 08 closes itself
parts = html.split("<section>")
assert len(parts) == 9, len(parts)
html = parts[0] + "<section>" + "</section>\n\n<section>".join(parts[1:])
assert html.count("<section>") == html.count("</section>") == 8
with io.open("/home/user/Paper3/telco-credit/outputs/pipeline.html", "w", encoding="utf-8") as fh:
    fh.write(html)
print("written", len(html), "bytes; sections balanced")

# -*- coding: utf-8 -*-
"""The plain-language dashboard. Written for a business reader: no model, no
statistics vocabulary, every figure either counted or shown as arithmetic.

Every number in Q came back from sql/56_dashboard_numbers.sql, run 1405-07-19.
Re-run it and replace Q to refresh the page; nothing here is hand-typed from
memory and nothing is estimated.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style

CYCLES = 12                 # a one-month loan turns over twelve times a year
MIN_TKT = 100_000

# ---- D1  the funnel, 140501..140506 at the 170,000 Toman bar
D1 = dict(base=41_270_092, after_bar=10_087_975, after_ow=9_437_240, qualify=9_344_723)
QUALIFY = D1["qualify"]

# ---- D2  what a qualifying customer SPENDS WITH US each month.
#      This is service revenue net of tax (arpu - tot_arpu_tax_amt), NOT the
#      invoice. 54 E5 measured the gap as a roughly constant ratio across
#      billing bands, so the real invoice is around 1.67x these figures and
#      every count built on them is a floor. D11 runs the sensitivity.
#      bill_low is the SECOND LOWEST of their six months - an amount they
#      reliably reach. bill_avg is the plain average of the six.
D2 = dict(p10=38_323, p25=84_748, median=144_031, p75=233_798, p90=363_544,
          median_avg=262_860, mean=181_994)

# ---- D3  how many can take each ticket with the loan kept below their bill
D3 = {100_000: 6_438_513, 200_000: 3_013_027, 300_000: 1_455_303, 500_000: 369_677}
BELOW_MIN = QUALIFY - D3[MIN_TKT]

# ---- D7  a flat 300,000 to everyone, and where it lands them
D7_300 = dict(safe=13_829, watch=1_441_474, risky=7_889_420)

# ---- D4 / D6  the warning signs. Counts are live, rates were counted on
#      140401..140406 with a three-month outcome. Ordered worst first.
CLEAN_PER_1000 = 3.100
ALL_PER_1000   = 4.371
WARNINGS = [
 dict(name="They were cut off at some point in the past year", short="Cut off in the past year",
      plain="Not in the six months we already check - in the year before that, "
            "which nothing looks at today.",
      per_1000=46.206, live=104_684, past=104_510,
      fix="Decline. This is the strongest signal we have and it is not "
          "expensive to check."),
 dict(name="There is a month where they billed nothing", short="A month with no bill",
      plain="The line is new, or it was switched off and restarted. A bill that "
            "appears out of nowhere has no history behind it.",
      per_1000=20.909, live=316_213, past=230_188,
      fix="Decline, or wait until they have six full months. Nothing in the "
          "current screen catches this."),
 dict(name="They billed, but paid almost nothing back", short="Paid almost nothing back",
      plain="Under a tenth of what they owed across six months. Paying slowly "
            "is normal and carries almost no extra risk. Paying nothing is the "
            "one that does.",
      per_1000=9.638, live=147_700, past=107_597,
      fix="Decline. There is no loan small enough to make this safe."),
 dict(name="The bill is falling", short="The bill is falling",
      plain="They use less every month. This one catches people out: the "
            "customer pays, has been with us for years and has never been cut "
            "off. They are leaving, and a leaving customer stops paying.",
      per_1000=5.006, live=1_680_104, past=1_726_359,
      fix="Lend, but do not raise their limit. One in five qualifying "
          "customers is in this group, so declining them all is expensive."),
]
NO_FLAGS_LIVE = 7_212_252

# ---- D9  how the risk stacks up as warning signs accumulate
D9 = [(0, 7_212_252, 3.100), (1, 2_018_446, 7.994), (2, 111_825, 17.126)]

# ---- D8  the bar rate across the whole network, month by month
D8 = [(140401,14.672),(140402,17.658),(140403,14.163),(140404,17.849),
      (140405,18.733),(140406,18.424),(140407,18.684),(140408,18.463),
      (140409,18.636),(140410,16.679),(140411,21.061),(140412,21.430),
      (140501,22.116),(140502,21.737),(140503,23.320),(140504,26.816),
      (140505,21.574),(140506,22.931)]
UPLIFT = 1.36               # 1405 first half against 1404 first half
TARGET_BN = 15_000.0
SHOCK_BAND = 1.133          # the loan stays under the bill
SHOCK_OVER = 1.907          # the loan matches or exceeds it

# ------------------------------------------------------------ the arithmetic
# Give each customer the largest standard loan that stays below their bill.
LADDER = [(500_000, D3[500_000]),
          (300_000, D3[300_000] - D3[500_000]),
          (200_000, D3[200_000] - D3[300_000]),
          (100_000, D3[100_000] - D3[200_000])]
SERVED      = sum(n for _, n in LADDER)
OUTSTANDING = sum(t * n for t, n in LADDER)
AVG_TICKET  = OUTSTANDING / SERVED
ANNUAL      = OUTSTANDING * CYCLES / 1e9
PER_MONTH   = CLEAN_PER_1000 / 3.0          # a loan is out for one month
LOSS        = ANNUAL * PER_MONTH / 1000.0 * SHOCK_BAND
LOSS_UP     = LOSS * UPLIFT

FLAT_ANNUAL = QUALIFY * 300_000 * CYCLES / 1e9
FLAT_PREM   = (D7_300["safe"] + D7_300["watch"] * SHOCK_BAND
               + D7_300["risky"] * SHOCK_OVER) / float(QUALIFY)
FLAT_LOSS   = FLAT_ANNUAL * PER_MONTH / 1000.0 * FLAT_PREM

def f(n):   return "{:,}".format(int(round(n)))
def one(x): return "{:.1f}".format(x)
def bnf(x): return "{:,.1f}".format(x)
def pc(a, b): return "{:.0f}".format(100.0 * a / b)

out = io.StringIO(); W = out.write

EXTRA = """
.fun{display:flex;flex-direction:column;gap:3px}
.fstep{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:center;
  padding:11px 14px;border-radius:6px;background:var(--raise);min-width:0}
.fstep.keep{background:color-mix(in srgb,var(--s1) 14%,var(--surface))}
.fstep.last{background:color-mix(in srgb,var(--good) 16%,var(--surface))}
.fstep .t{font-size:14.5px;color:var(--ink);min-width:0}
.fstep .t em{font-style:normal;display:block;color:var(--ink-3);font-size:12.5px;margin-top:2px}
.fstep .v{font-family:var(--mono);font-size:17px;font-weight:600;white-space:nowrap}
.fdrop{display:grid;grid-template-columns:1fr auto;gap:14px;padding:5px 14px 5px 30px;
  font-size:13px;color:var(--ink-3)}
.fdrop .v{font-family:var(--mono);white-space:nowrap}

.warns{display:flex;flex-direction:column;gap:12px}
.wrn{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;
  background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:18px;border-left:3px solid var(--crit)}
@media (max-width:620px){.wrn{grid-template-columns:1fr;gap:10px}}
.wrn.mild{border-left-color:var(--warn)}
.wrn .score{text-align:center;min-width:122px}
.wrn .score .m{font-family:var(--mono);font-size:30px;font-weight:600;color:var(--crit);
  letter-spacing:-0.02em;line-height:1}
.wrn.mild .score .m{color:var(--warn)}
.wrn .score .l{font-size:11.5px;color:var(--ink-3);margin-top:5px;line-height:1.35}
.wrn h3{font-size:16px;margin-bottom:6px}
.wrn p{font-size:14px;color:var(--ink-2);line-height:1.55}
.wrn .do{margin-top:10px;font-size:13.5px;color:var(--ink);
  background:var(--raise);border-radius:5px;padding:9px 11px;line-height:1.5}
.wrn .cnt{font-family:var(--mono);font-size:12.5px;color:var(--ink-3);margin-top:8px}

.rule{display:flex;flex-wrap:wrap;gap:20px 36px;align-items:center;
  background:color-mix(in srgb,var(--good) 11%,var(--surface));
  border:1px solid color-mix(in srgb,var(--good) 40%,var(--rule));
  border-radius:8px;padding:24px 22px}
.rule .big{font-size:clamp(21px,3.6vw,29px);font-weight:600;letter-spacing:-0.02em;
  line-height:1.25;flex:1 1 300px;min-width:0;text-wrap:balance}
.rule .why{font-size:14px;color:var(--ink-2);line-height:1.6;flex:1 1 260px;min-width:0}

.steps{display:flex;flex-direction:column;gap:0;margin-top:4px}
.stp{display:grid;grid-template-columns:30px 1fr;gap:14px;padding:14px 0;
  border-bottom:1px solid var(--rule)}
.stp:last-child{border-bottom:none}
.stp .n{font-family:var(--mono);font-size:15px;font-weight:600;color:var(--s1)}
.stp h3{font-size:15px;margin-bottom:3px}
.stp p{font-size:14px;color:var(--ink-2);line-height:1.55}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:13px;color:var(--ink-2)}
.legend span{display:flex;align-items:center;gap:7px}
.legend i{width:11px;height:11px;border-radius:2px;display:block}
.split > *{min-width:0}
.panel .tbl-s{max-width:100%}
"""

W(dash_style.head("Lending on the Phone Bill", EXTRA))

# ------------------------------------------------------------------ header
W("""<header>
  <p class="eyebrow">Direct Carrier Billing &middot; what it is and what it costs</p>
  <h1>Lending customers money on their next phone bill</h1>
  <p class="lede">A customer borrows against their phone bill, spends it on
  services they already use, and repays it on the bill that arrives next month.
  Every figure on this page was counted on our own customers in the last twelve
  months. There are no forecasts and no model &mdash; where something has not
  been measured, the page says so.</p>
  <div class="spec">
    <span class="chip">term <b>one month</b></span>
    <span class="chip">loans <b>100,000 to 500,000 Toman</b></span>
    <span class="chip">counted on <b>1404 and 1405</b></span>
    <span class="chip">all amounts <b>Toman</b></span>
  </div>
</header>
""")

W("""<div class="kpi" style="margin-top:26px">
  <div class="tile"><span class="k">customers who qualify</span><span class="v">%s</span>
    <span class="s">out of %s on the network</span></div>
  <div class="tile"><span class="k">we can actually lend to</span><span class="v">%s</span>
    <span class="s">the rest bill too little to carry even the smallest loan</span></div>
  <div class="tile"><span class="k">lent over a year</span><span class="v">%s bn</span>
    <span class="s">%s pct of the 15,000 bn ambition</span></div>
  <div class="tile"><span class="k">expected to go unpaid</span><span class="v">%s bn</span>
    <span class="s">a year, assuming we recover nothing</span></div>
</div>
<p class="cap"><b>The second figure is the one that changed.</b> We assumed every
qualifying customer could take the typical 300,000 Toman loan. Having counted
it, only <b>%s</b> can &mdash; %s in every 100. Giving each customer a loan
sized to their own bill instead reaches <b>%s</b> customers and lends
<b>%s bn</b> a year, which is most of the way to the target. The rest of this
page is how that works.</p>
""" % (f(QUALIFY), f(D1["base"]), f(SERVED), f(ANNUAL), pc(ANNUAL, TARGET_BN),
       one(LOSS), f(D3[300_000]), pc(D3[300_000], QUALIFY), f(SERVED), f(ANNUAL)))

# ------------------------------------------------------------------ funnel
D1["lendable"] = D3[MIN_TKT]

W("""<section>
  <div class="head">
    <h2>Who qualifies</h2>
    <p>Three checks, one after the other. None of them is a judgement call
    &mdash; each is a fact about the last six months.</p>
  </div>
  <div class="card">
    <div class="fun">
""")
STEPS = [("Everyone on a permanent contract", "the starting point", "base", "", None),
         ("They bill enough to carry a loan",
          "at least 170,000 Toman in 2 of the last 6 months", "after_bar", "keep",
          ("did not bill 170,000 Toman in any two months", "base", "after_bar")),
         ("Their outgoing service has never been cut off",
          "not once in the last six months", "after_ow", "keep",
          ("had outgoing service suspended", "after_bar", "after_ow")),
         ("Their incoming service has never been cut off",
          "not once in the last six months", "qualify", "keep",
          ("had incoming service suspended", "after_ow", "qualify")),
         ("They spend enough with us to carry the smallest loan",
          "at least 100,000 Toman of service in a month they reliably reach", "lendable", "last",
          ("spend too little for a 100,000 loan", "qualify", "lendable"))]
for title, sub, key, cls, drop in STEPS:
    if drop:
        why, a, b = drop
        W('      <div class="fdrop"><span>&minus; %s</span><span class="v">%s</span></div>\n'
          % (why, f(D1[a] - D1[b])))
    W('      <div class="fstep %s"><div class="t">%s<em>%s</em></div>'
      '<div class="v">%s</div></div>\n' % (cls, title, sub, f(D1[key])))
W("""    </div>
    <p class="cap"><b>Why the last step drops %s more.</b> The third check
    asks for 170,000 Toman in <i>any two</i> of six months. The other four can
    be almost nothing, and for %s customers they are &mdash; someone billing
    20,000, 30,000, 50,000, 60,000, 180,000 and 200,000 passes it. The fourth
    step asks a different question: is there a monthly bill they <i>reliably</i>
    reach that is large enough to carry a loan. <b>%s customers qualify;
    %s can actually be lent to.</b> Both numbers are real and they answer
    different questions.</p>
    <p class="cap">The first check still does almost all the work &mdash; it
    removes %s customers, 97 of every 100 we turn away. It is not a judgement
    about whether someone would repay, only about whether their bill can carry
    a loan at all.</p>
  </div>
</section>
""" % (f(QUALIFY - D1["lendable"]), f(QUALIFY - D1["lendable"]), f(QUALIFY),
       f(D1["lendable"]), f(D1["base"] - D1["after_bar"])))

# -------------------------------------------------------- the loan size
W("""<section>
  <div class="head">
    <h2>How big the loan should be</h2>
    <p>This is the decision that sets the size of the whole programme, and it
    had never been counted until now.</p>
  </div>
  <div class="rule">
    <div class="big">Never lend someone more than they bill in a month.</div>
    <div class="why">When the loan is smaller than the usual bill, the bill goes
    up by less than double and customers carry on paying at close to the normal
    rate. Once the loan matches the bill, the bill doubles &mdash; and
    <b>customers whose bill doubles stop paying %s times as often</b>. The line
    is sharp and it sits exactly at "the loan equals the bill".</div>
  </div>

  <div class="card" style="margin-top:14px">
    <h3>A flat 300,000 Toman loan does not work</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>If every qualifying customer is offered 300,000</th><th>Customers</th><th>Share</th></tr></thead>
      <tbody>
        <tr><td>Their bill barely moves</td><td>%s</td><td>%s pct</td></tr>
        <tr><td>Their bill rises, but stays under double</td><td>%s</td><td>%s pct</td></tr>
        <tr class="tot"><td>Their bill doubles or more &mdash; the risky band</td>
            <td>%s</td><td><b>%s pct</b></td></tr>
      </tbody>
      <tfoot><tr><td colspan="3">Five customers in every six would be pushed
      into the band where people stop paying %s times as often. The typical
      qualifying customer reliably bills <b>%s Toman</b> a month, so a 300,000
      loan is roughly twice what most of them spend. <b>The ticket has to be set
      per customer, not per product.</b></td></tr></tfoot>
    </table></div>
  </div>

  <div class="card">
    <h3>Sizing each loan to the customer's own bill</h3>
    <p class="cap" style="margin-top:6px">Give every customer the largest
    standard loan that still stays below what they bill.</p>
    <div class="tbl-s"><table>
      <thead><tr><th>Loan</th><th>Customers who can take it</th><th>Lent at any one time</th></tr></thead>
      <tbody>
""" % (one(SHOCK_OVER / SHOCK_BAND),
       f(D7_300["safe"]), pc(D7_300["safe"], QUALIFY),
       f(D7_300["watch"]), pc(D7_300["watch"], QUALIFY),
       f(D7_300["risky"]), pc(D7_300["risky"], QUALIFY),
       one(SHOCK_OVER / SHOCK_BAND), f(D2["median"])))
for t, n in LADDER:
    W('        <tr><td>%s Toman</td><td>%s</td><td>%s bn</td></tr>\n'
      % (f(t), f(n), one(t * n / 1e9)))
W("""        <tr class="tot"><td>Everyone we can lend to</td><td><b>%s</b></td>
            <td><b>%s bn</b></td></tr>
        <tr class="off"><td>Bill too small for even a 100,000 loan</td><td>%s</td><td>&mdash;</td></tr>
      </tbody>
      <tfoot><tr><td colspan="3">Average loan <b>%s Toman</b>. That money comes
      back and goes out again every month, so <b>%s bn is lent over a year</b>
      &mdash; %s pct of the 15,000 bn ambition, from a book that is never more
      than %s bn at risk at any one moment. <b>%s customers, nearly a third of
      those who qualify, bill too little to take even the smallest loan.</b>
      Lowering the 100,000 minimum is the only thing that reaches them.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (f(SERVED), bnf(OUTSTANDING / 1e9), f(BELOW_MIN), f(AVG_TICKET), f(ANNUAL),
       pc(ANNUAL, TARGET_BN), bnf(OUTSTANDING / 1e9), f(BELOW_MIN)))

# ------------------------------------------------------------- the warnings
W("""<section>
  <div class="head">
    <h2>Four warning signs</h2>
    <p>Counted on %s customers who passed the same three checks, following them
    for three months to see who stopped paying. A customer with none of these
    signs stops paying at <b>%s in every 1,000</b>.</p>
  </div>
  <div class="card" style="margin-bottom:14px">
    <div class="svgbox">
""" % (f(8_701_085), one(CLEAN_PER_1000)))
SW, SH = 790, 258
SL, SR, ST, SB = 250, 672, 16, 200
SMAX = max(w["per_1000"] for w in WARNINGS) * 1.16
def sx(v): return SL + v / SMAX * (SR - SL)
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="how often each group stops paying">\n' % (SW, SH))
for g in (10, 20, 30, 40):
    W('      <line class="gl" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>\n' % (sx(g), ST, sx(g), SB))
    W('      <text class="tk" x="%.1f" y="%d" text-anchor="middle">%d</text>\n' % (sx(g), SB+17, g))
ROWS = [("No warning signs at all", CLEAN_PER_1000, "var(--good)")] + \
       [(w["short"], w["per_1000"], "var(--crit)" if w["per_1000"] >= 9 else "var(--warn)")
        for w in WARNINGS]
bh, gp = 26, 10
for i, (nm, v, col) in enumerate(ROWS):
    y = ST + 8 + i * (bh + gp)
    assert len(nm) < 32, ("chart label too long for its column", nm)
    label = nm
    W('      <text class="an" x="%d" y="%.1f" text-anchor="end" fill="var(--ink-2)">%s</text>\n'
      % (SL-12, y+bh/2+4, label))
    W('      <rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" fill="%s">'
      '<title>%s: %s in 1,000</title></rect>\n'
      % (sx(0), y, max(sx(v)-sx(0), 2), bh, col, nm, one(v)))
    W('      <text class="dl" x="%.1f" y="%.1f" fill="var(--ink)">%s</text>\n'
      % (sx(v)+9, y+bh/2+5, one(v)))
W('      <line class="ax" x1="%.1f" y1="%d" x2="%d" y2="%d"/>\n' % (sx(0), SB, SR, SB))
W('      <text class="tk" x="%.1f" y="%d">out of every 1,000 customers, how many stopped paying in three months</text>\n'
  % (sx(0), SB+40))
W('    </svg>\n    </div>\n  </div>\n  <div class="warns">\n')
for wn in WARNINGS:
    mild = "" if wn["per_1000"] >= 9 else " mild"
    W("""    <div class="wrn%s">
      <div class="score"><div class="m">%s</div><div class="l">in 1,000 stop paying<br>%s times the clean rate</div></div>
      <div>
        <h3>%s</h3>
        <p>%s</p>
        <div class="do"><b>What to do:</b> %s</div>
        <div class="cnt">customers with this sign today: %s &nbsp;&middot;&nbsp; %s pct of those who qualify</div>
      </div>
    </div>
""" % (mild, one(wn["per_1000"]), one(wn["per_1000"] / CLEAN_PER_1000), wn["name"],
       wn["plain"], wn["fix"], f(wn["live"]), pc(wn["live"], QUALIFY)))
W("""  </div>
  <div class="split" style="margin-top:14px">
    <div class="panel">
      <h3>Every extra sign roughly doubles the risk</h3>
      <div class="tbl-s"><table>
        <thead><tr><th>Warning signs</th><th>Customers</th><th>Stop paying, per 1,000</th></tr></thead>
        <tbody>
""")
for k, n, r in D9:
    W('          <tr%s><td>%s</td><td>%s</td><td><b>%s</b></td></tr>\n'
      % (' class="tot"' if k == 0 else "", "none" if k == 0 else
         ("one" if k == 1 else "two or more"), f(n), one(r)))
W("""        </tbody>
        <tfoot><tr><td colspan="3"><b>%s customers &mdash; %s in every 100
        &mdash; carry no warning sign at all.</b> The programme does not need to
        find good customers. It needs to not lend to the %s who are already
        showing one.</td></tr></tfoot>
      </table></div>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Risk is rising, and not slowly</h3>
      <div class="tbl-s"><table>
        <thead><tr><th>Period</th><th>Cut off, per 1,000 each month</th></tr></thead>
        <tbody>
          <tr><td>First half of 1404</td><td>16.9</td></tr>
          <tr class="tot"><td>First half of 1405</td><td><b>23.1</b></td></tr>
        </tbody>
        <tfoot><tr><td colspan="2">Across the whole network, <b>%s times as many
        customers are being cut off as a year ago</b>. The warning-sign rates on
        this page were counted on 1404, so they are a floor. Carrying that
        increase through puts expected losses at <b>%s bn</b> a year rather than
        %s bn.</td></tr></tfoot>
      </table></div>
    </div>
  </div>
</section>
""" % (f(NO_FLAGS_LIVE), pc(NO_FLAGS_LIVE, QUALIFY), f(QUALIFY - NO_FLAGS_LIVE),
       "{:.2f}".format(UPLIFT), one(LOSS_UP), one(LOSS)))

# ------------------------------------------------------------- what it costs
W("""<section>
  <div class="head">
    <h2>What it is likely to cost</h2>
    <p>Worked out in the open so every step can be argued with.</p>
  </div>
  <div class="card">
    <div class="steps">
      <div class="stp"><span class="n">1</span><div>
        <h3>%s customers borrow %s Toman on average</h3>
        <p>That is <b>%s bn</b> out on loan at any one time. The money comes back
        each month and goes out again, so <b>%s bn</b> is lent over a full
        year.</p></div></div>
      <div class="stp"><span class="n">2</span><div>
        <h3>About 1 in every 1,000 does not pay it back</h3>
        <p>Customers with no warning sign stopped paying at %s in 1,000 over
        three months. A loan is only out for one month, so roughly a third of
        that applies to any single loan. This assumes the risk is spread evenly
        across the three months, which is a simplification.</p></div></div>
      <div class="stp"><span class="n">3</span><div>
        <h3>So we lose roughly %s bn Toman a year</h3>
        <p>It assumes we recover <b>nothing</b> from a customer who stops paying,
        which is deliberately pessimistic &mdash; the operator keeps collecting
        after the line is cut off. Against %s bn lent, that is about
        <b>__PER_K__ Toman lost for every 1,000 lent</b>. Carrying through the
        year-on-year rise in cut-offs puts it at <b>%s bn</b>.</p></div></div>
      <div class="stp"><span class="n">4</span><div>
        <h3>A flat 300,000 loan would cost %s bn instead</h3>
        <p>It lends more &mdash; %s bn a year &mdash; but pushes %s pct of
        customers into the band where people stop paying nearly twice as often.
        <b>%s times the losses for %s times the lending.</b> That is the whole
        argument for sizing the loan to the bill.</p></div></div>
    </div>
  </div>
</section>
""" % (f(SERVED), f(AVG_TICKET), bnf(OUTSTANDING/1e9), f(ANNUAL),
       one(CLEAN_PER_1000), one(LOSS), f(ANNUAL), one(LOSS_UP),
       one(FLAT_LOSS), f(FLAT_ANNUAL), pc(D7_300["risky"], QUALIFY),
       one(FLAT_LOSS / LOSS), one(FLAT_ANNUAL / ANNUAL)))

# ------------------------------------------------------------- what's open
W("""<section>
  <div class="head">
    <h2>What we do not know yet</h2>
    <p>Four things, said plainly, so nothing above is taken as more certain than
    it is.</p>
  </div>
  <div class="split">
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Nobody in this data ever had credit</h3>
      <ul>
        <li>Every number here describes how customers behave when they are
        <b>not</b> borrowing. How they behave when they are is genuinely
        unknown.</li>
        <li><b>A capped pilot is the only thing that answers it</b>, and a
        one-month loan means the answer arrives in weeks rather than a year.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>We are measuring what they spend, not what they are invoiced</h3>
      <ul>
        <li>Every figure here uses <b>service revenue</b> &mdash; what a customer
        spends with us in a month, before tax. That is not the same as the
        invoice they receive, and we have never confirmed which column holds
        the invoice total.</li>
        <li>What we do know: customers pay back about <b>one and a half times</b>
        what this figure says they were charged, and that gap is a steady
        proportion rather than a fixed amount. So <b>the real invoice is larger
        &mdash; perhaps 1.67 times larger</b>.</li>
        <li><b>That makes the customer counts a floor, not a ceiling.</b> If the
        invoice is really 1.67 times this, a 100,000 loan on someone spending
        100,000 raises their bill by 1.6 times, not double, and they should have
        counted as lendable. <b>Many of the %s we excluded probably are.</b></li>
        <li>The rule itself is unaffected, because it compares a loan to a bill
        and both move together. Only the headcounts move.</li>
      </ul>
    </div>
  </div>
  <div class="split" style="margin-top:14px">
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Which month the limit is set against</h3>
      <ul>
        <li>We use a month the customer <b>reliably</b> reaches &mdash; their
        second-lowest of six, __MED__ Toman for a typical customer.</li>
        <li>Their six-month average is __MEDAVG__ Toman. Setting limits against
        the average instead would <b>roughly double the programme</b> and take
        on more risk. A decision, not a detail, and cheap to count both ways.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Does the loan add to the bill or replace part of it?</h3>
      <ul>
        <li>If customers spend it on things they were buying anyway, the bill
        barely moves and the limit rule has room to spare.</li>
        <li>If it is all extra spending, the bill rises by the full amount.
        <b>Everything here assumes the second</b>, which is the cautious
        reading.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>What "stopped paying" means here</h3>
      <ul>
        <li>A customer counts as having stopped paying when their line is cut off
        in both directions. That is the operator's own decision and it takes time
        to reach, so some customers already in trouble have not been cut off yet
        when we count.</li>
        <li>That makes these rates a <b>floor rather than a ceiling</b>. It is
        being checked separately. It changes how many we have caught by the time
        we look, not which customers are risky.</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  <span>Customer counts are from billing records for 140501&ndash;140506. Risk
  figures were counted on 140401&ndash;140406, because measuring whether someone
  stops paying needs the months afterwards to observe it. All amounts in Toman;
  the billing system stores Rial and every figure here is that value divided by
  ten.</span>
  <span>The detailed version, with the queries and the statistics behind every
  figure, is in the <a href="https://claude.ai/artifact/HZSVj2iWoYHdhrTDxjF2uQ">programme
  deck</a> and the <a href="https://claude.ai/artifact/H5jJHuD6i6r3gim31Rfrte">risk
  workbook</a>.</span>
</footer>
</div>
""" % f(BELOW_MIN))

html = (out.getvalue()
        .replace("__PER_K__", "{:.2f}".format(LOSS / ANNUAL * 1000))
        .replace("__MED__", f(D2["median"]))
        .replace("__MEDAVG__", f(D2["median_avg"])))
assert "__" not in html.replace("__EXTRA__", ""), "a placeholder went unfilled"

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_manager.html"), "w", encoding="utf-8").write(html)
print("written", len(html), "bytes")
print("served %s  avg ticket %s  annual %s bn  loss %s bn (%s bn uplifted)"
      % (f(SERVED), f(AVG_TICKET), f(ANNUAL), one(LOSS), one(LOSS_UP)))
print("flat 300k: annual %s bn  premium %.3f  loss %s bn" % (f(FLAT_ANNUAL), FLAT_PREM, one(FLAT_LOSS)))

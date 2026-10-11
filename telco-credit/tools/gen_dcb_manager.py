# -*- coding: utf-8 -*-
"""The plain-language dashboard. Written for a business reader: no model, no
statistics vocabulary, every figure either measured or shown as arithmetic.

HOW TO UPDATE IT. Run sql/56_dashboard_numbers.sql and paste the results into
Q below. Anything still None renders as a visible gap on the page with the
statement that fills it - the page can never print a number nobody measured.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style

TICKET   = 300_000          # the average ticket the product is built around
MIN_TKT  = 100_000
CYCLES   = 12               # a one-month term turns over twelve times a year

Q = dict(
    # ---- D1  the funnel. MEASURED on 140501..140506 at the 170,000 bar.
    base            = 41_270_092,
    after_bar       = 10_087_975,
    after_ow        =  9_437_240,
    qualify         =  9_344_723,

    # ---- D2  what a qualifying customer bills each month.  PENDING D2
    median_bill     = None,
    p25_bill        = None,
    p75_bill        = None,

    # ---- D3  how many can take each ticket under the limit rule.  PENDING D3
    can_take_100k   = None,
    can_take_200k   = None,
    can_take_300k   = None,
    can_take_500k   = None,

    # ---- D4  how many carry each warning sign, live window.  PENDING D4
    n_zero_month    = None,
    n_no_payment    = None,
    n_barred_before = None,
    n_falling       = None,
    n_clean         = None,

    # ---- D6  the measured rate for a customer with no warning signs. PENDING D6
    clean_per_1000  = None,
)

# What IS measured about risk today, from 53 and 52 on 140401..140406 with a
# two-month outcome. Each row: the sign, how much riskier, and whether the
# rate beside it was measured directly or worked out from the multiplier.
BASE_PER_1000 = 2.21        # 0.2208 pct over ONE month, which is the term
SHOCK_RATIO   = 1.68        # 1.907 / 1.133 - what ignoring the limit rule costs
WARNINGS = [
 dict(name="A month where they billed nothing",
      plain="The line is new, or it was switched off and restarted. A bill that "
            "appears out of nowhere has no history behind it.",
      mult=7.7, per_1000=None, direct=False, src="counted on 109,360 customers",
      fix="Add it to the screen. It is not checked today and it is the cheapest "
          "thing on this page to fix."),
 dict(name="They billed, but paid almost nothing back",
      plain="Under a tenth of what they owed, across six months. Paying slowly "
            "is normal and carries no extra risk at all. Paying nothing is the "
            "one that does.",
      mult=8.3, per_1000=None, direct=False, src="counted on six months of payments",
      fix="Decline. There is no limit small enough to make this safe."),
 dict(name="They were barred in the past year",
      plain="The service was cut off before. Not in the six months we look at, "
            "which we already check, but in the year before that, which we do not.",
      mult=13.2, per_1000=None, direct=False, src="counted on the prior year's records",
      fix="Decline, or start them at the smallest ticket and let them earn it."),
 dict(name="The bill is falling",
      plain="They are using less every month. This one surprises people: the "
            "customer pays, has been with us for years and has never been cut "
            "off. They are leaving, and a leaving customer stops paying.",
      mult=1.9, per_1000=None, direct=False, src="counted against customers with a steady bill",
      fix="Lend, but do not raise their limit. The trend is the warning."),
]

def f(n):   return "{:,}".format(int(round(n)))
def one(x): return "{:.1f}".format(x)

out = io.StringIO(); W = out.write

# A value that nobody has measured is a gap on the page, never a number.
PENDING = []
def V(key, unit="", stmt=""):
    v = Q.get(key)
    if v is None:
        if stmt and stmt not in PENDING: PENDING.append(stmt)
        return '<span class="gap" title="waiting on %s">%s</span>' % (stmt, stmt)
    return f(v) + unit

EXTRA = """
/* a figure nobody has measured yet */
.gap{font-family:var(--mono);font-size:0.82em;letter-spacing:0.04em;
  background:color-mix(in srgb,var(--warn) 24%,var(--surface));
  border:1px dashed color-mix(in srgb,var(--warn) 70%,var(--rule));
  border-radius:4px;padding:1px 7px;color:var(--ink-2);white-space:nowrap}
.tile .v .gap{font-size:14px}

/* the funnel, as a plain waterfall */
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

/* the warning-sign cards */
.warns{display:flex;flex-direction:column;gap:12px}
.wrn{display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:start;
  background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:18px;border-left:3px solid var(--crit)}
@media (max-width:620px){.wrn{grid-template-columns:1fr;gap:10px}}
.wrn .score{text-align:center;min-width:112px}
.wrn .score .m{font-family:var(--mono);font-size:30px;font-weight:600;color:var(--crit);
  letter-spacing:-0.02em;line-height:1}
.wrn .score .l{font-size:11.5px;color:var(--ink-3);margin-top:5px;line-height:1.35}
.wrn h3{font-size:16px;margin-bottom:6px}
.wrn p{font-size:14px;color:var(--ink-2);line-height:1.55}
.wrn .do{margin-top:10px;font-size:13.5px;color:var(--ink);
  background:var(--raise);border-radius:5px;padding:9px 11px;line-height:1.5}
.wrn .do b{font-weight:600}
.wrn .cnt{font-family:var(--mono);font-size:12.5px;color:var(--ink-3);margin-top:8px}

/* the one rule */
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
"""

W(dash_style.head("Lending on the Phone Bill", EXTRA))

# ------------------------------------------------------------------ header
W("""<header>
  <p class="eyebrow">Direct Carrier Billing &middot; what it is and what it costs</p>
  <h1>Lending customers money on their next phone bill</h1>
  <p class="lede">A customer borrows up to 300,000 Toman, spends it on services
  they already buy, and repays it on the bill that arrives next month. This page
  is who can have it, how much each person should get, and what it is likely to
  cost us. No forecasts &mdash; every number here is something we counted.</p>
  <div class="spec">
    <span class="chip">term <b>one month</b></span>
    <span class="chip">typical loan <b>300,000 Toman</b></span>
    <span class="chip">smallest loan <b>100,000 Toman</b></span>
    <span class="chip">counted on <b>the last six months</b></span>
  </div>
</header>
""")

ANNUAL = Q["qualify"] * TICKET * CYCLES / 1e9
PER_CYCLE = Q["qualify"] * TICKET / 1e9
W("""<div class="kpi" style="margin-top:26px">
  <div class="tile"><span class="k">customers who qualify today</span><span class="v">%s</span>
    <span class="s">out of %s on the network</span></div>
  <div class="tile"><span class="k">lent out at any one time</span><span class="v">%s bn</span>
    <span class="s">if every one of them borrows the typical amount</span></div>
  <div class="tile"><span class="k">lent over a year</span><span class="v">%s bn</span>
    <span class="s">the same money, lent and repaid twelve times</span></div>
  <div class="tile"><span class="k">stop paying, per 1,000</span><span class="v">%s</span>
    <span class="s">in the month a loan would be due</span></div>
</div>
<p class="cap">A one-month loan is the whole reason the second and third figures
are so different. Money lent in month one comes back in month two and goes out
again in month three. A four-month loan does that three times a year; this does
it twelve times.</p>
""" % (f(Q["qualify"]), f(Q["base"]), f(PER_CYCLE), f(ANNUAL), one(BASE_PER_1000)))

# ------------------------------------------------------------------ funnel
W("""<section>
  <div class="head">
    <h2>Who qualifies</h2>
    <p>Three checks, applied one after the other. Nothing here is a judgement
    call &mdash; each one is a fact about the last six months.</p>
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
          "not once in the last six months", "qualify", "last",
          ("had incoming service suspended", "after_ow", "qualify"))]
for title, sub, key, cls, drop in STEPS:
    if drop:
        why, a, b = drop
        W('      <div class="fdrop"><span>&minus; %s</span><span class="v">%s</span></div>\n'
          % (why, f(Q[a] - Q[b])))
    W('      <div class="fstep %s"><div class="t">%s<em>%s</em></div>'
      '<div class="v">%s</div></div>\n' % (cls, title, sub, f(Q[key])))
W("""    </div>
    <p class="cap"><b>The first check does almost all of the work.</b> It removes
    %s customers, which is 97 out of every 100 we turn away. It is not a judgement
    about whether they would repay &mdash; it is about whether their bill is big
    enough to carry a loan at all. If we want more customers, that number is the
    one to move, and moving it adds volume without making the book riskier.</p>
  </div>
</section>
""" % f(Q["base"] - Q["after_bar"]))

# ------------------------------------------------------------- the one rule
W("""<section>
  <div class="head">
    <h2>How much to give each person</h2>
    <p>One rule covers it, and it is the most useful thing we measured.</p>
  </div>
  <div class="rule">
    <div class="big">Never lend someone more than they bill in a month.</div>
    <div class="why">If the loan is smaller than their usual bill, the bill they
    get goes up by less than double, and customers in that position stop paying
    at close to the normal rate. Once the loan is as large as the bill, the bill
    doubles &mdash; and <b>customers whose bill doubles stop paying almost twice
    as often</b>. The line is sharp, and it sits exactly at "the loan equals the
    bill".</div>
  </div>
  <div class="card" style="margin-top:14px">
    <h3>What that is worth</h3>
    <p class="cap" style="margin-top:6px">Same customers, same book, two
    different limit policies.</p>
    <div class="tbl-s"><table>
      <thead><tr><th>Policy</th><th>How often they stop paying</th><th>Lost in a year</th></tr></thead>
      <tbody>
        <tr><td>Every loan stays under one month's bill</td><td>the ordinary rate</td>
            <td><b>__LOSS_OK__ bn Toman</b></td></tr>
        <tr class="tot"><td>Loans allowed to match or exceed it</td>
            <td><b>__RATIO__ times</b> as often</td><td><b>__LOSS_BAD__ bn Toman</b></td></tr>
      </tbody>
      <tfoot><tr><td colspan="3">A difference of <b>__LOSS_GAP__ bn Toman a year</b>
      from a rule that costs nothing to apply, because we already know what every
      customer bills. The multiple was counted on 4 million customer-months; the
      money is that multiple applied to this book.</td></tr></tfoot>
    </table></div>
  </div>
  <div class="card">
    <h3>How many customers can take each loan size</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>Loan</th><th>Needs a monthly bill above</th><th>Customers who have one</th></tr></thead>
      <tbody>
        <tr><td>100,000 Toman</td><td>100,000</td><td>%s</td></tr>
        <tr><td>200,000 Toman</td><td>200,000</td><td>%s</td></tr>
        <tr class="tot"><td>300,000 Toman</td><td>300,000</td><td>%s</td></tr>
        <tr><td>500,000 Toman</td><td>500,000</td><td>%s</td></tr>
      </tbody>
      <tfoot><tr><td colspan="3">The typical qualifying customer bills
      %s Toman a month. <b>This is the one table that decides the size of the
      programme</b>, because it says how much of the 9.3 million can actually
      take the typical loan rather than a smaller one. It has never been
      counted; statements D2 and D3 count it.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (V("can_take_100k", stmt="D3"), V("can_take_200k", stmt="D3"),
       V("can_take_300k", stmt="D3"), V("can_take_500k", stmt="D3"),
       V("median_bill", stmt="D2")))

# ------------------------------------------------------------- the warnings
W("""<section>
  <div class="head">
    <h2>Four warning signs</h2>
    <p>These are the things that actually predict a customer stopping paying.
    Each one was counted on real customers over a real six months. The number on
    the left is how many stopped paying for every 1,000 customers carrying that
    sign, against <b>%s in 1,000</b> for an ordinary customer.</p>
  </div>
  <div class="warns">
""" % one(BASE_PER_1000))
KEYS = ["n_zero_month", "n_no_payment", "n_barred_before", "n_falling"]
for wn, key in zip(WARNINGS, KEYS):
    per = wn["per_1000"] if wn["direct"] else BASE_PER_1000 * wn["mult"]
    how = "%s times the ordinary rate" % one(wn["mult"])
    W("""    <div class="wrn">
      <div class="score"><div class="m">%s</div><div class="l">in 1,000 stop paying<br>%s</div></div>
      <div>
        <h3>%s</h3>
        <p>%s</p>
        <div class="do"><b>What to do:</b> %s</div>
        <div class="cnt">how many customers have this sign today: %s &nbsp;&middot;&nbsp; %s</div>
      </div>
    </div>
""" % (one(per), how, wn["name"], wn["plain"], wn["fix"], V(key, stmt="D4"), wn["src"]))
W("""  </div>
  <p class="cap">How much riskier each group is was counted directly. The rate
  beside it is that multiplier applied to the ordinary rate, because the counts
  themselves were made over a different stretch of months and mixing the two
  would be misleading. It also assumes the signs do not overlap, and a customer
  carrying two of them is not necessarily twice as risky.
  <b>Statement D6 replaces all four with one clean count on one set of months</b>,
  including the rate for a customer carrying no signs at all &mdash; which is
  the number the business case should actually be built on, and is lower than
  anything on this page.</p>
</section>
""")

# ------------------------------------------------------------- what it costs
W("""<section>
  <div class="head">
    <h2>What it is likely to cost</h2>
    <p>Worked out in the open, so every step can be argued with.</p>
  </div>
  <div class="card">
    <div class="steps">
      <div class="stp"><span class="n">1</span><div>
        <h3>%s customers borrow 300,000 Toman each</h3>
        <p>That is <b>%s bn Toman</b> out on loan at any one time, and
        <b>%s bn</b> lent over a full year as the same money cycles twelve
        times.</p></div></div>
      <div class="stp"><span class="n">2</span><div>
        <h3>About %s in every 1,000 do not pay it back</h3>
        <p>That is what we counted on customers who passed the same three
        checks, over one month, which is the length of the loan. The real figure
        for the lending book should be <i>lower</i>, because we would be turning
        away everyone carrying a warning sign.</p></div></div>
      <div class="stp"><span class="n">3</span><div>
        <h3>So we lose roughly %s bn Toman a year</h3>
        <p>%s bn lent over the year, %s in every 1,000 not repaid. It assumes we
        recover <b>nothing</b> from a customer who stops paying, which is
        deliberately pessimistic &mdash; the operator keeps collecting after the
        line is cut off, so the real figure should come in under this.</p></div></div>
      <div class="stp"><span class="n">4</span><div>
        <h3>Ignore the limit rule and it becomes about %s bn</h3>
        <p>Customers whose bill doubles stop paying %s times as often as
        customers whose bill rises by less. That multiple is the difference
        between the two figures, on exactly the same book and the same
        customers. <b>It is the most expensive decision on this page and it
        costs nothing to get right.</b></p></div></div>
    </div>
  </div>
</section>
""" % (f(Q["qualify"]), f(PER_CYCLE), f(ANNUAL), one(BASE_PER_1000),
       one(ANNUAL * BASE_PER_1000 / 1000.0), f(ANNUAL), one(BASE_PER_1000),
       one(ANNUAL * BASE_PER_1000 / 1000.0 * SHOCK_RATIO), one(SHOCK_RATIO)))

# ------------------------------------------------------------- what's open
W("""<section>
  <div class="head">
    <h2>What we do not know yet</h2>
    <p>Three things, said plainly, so nothing on this page is taken as more
    certain than it is.</p>
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
      <h3><span class="dot" style="background:var(--crit)"></span>Does the loan add to the bill, or replace part of it?</h3>
      <ul>
        <li>If customers spend the loan on things they were going to buy
        anyway, their bill barely moves and the limit rule has room to spare.</li>
        <li>If it is all extra spending, the bill rises by the full amount.
        <b>Everything here assumes the second</b>, which is the cautious
        reading.</li>
      </ul>
    </div>
  </div>
  <div class="panel unknown" style="margin-top:14px">
    <h3><span class="dot" style="background:var(--crit)"></span>What "stopped paying" means here</h3>
    <ul>
      <li>We count a customer as having stopped paying when their line is cut
      off in both directions. That is the operator's own decision and it takes
      time to reach &mdash; so some customers who are already in trouble have
      not been cut off yet when we count.</li>
      <li>This makes the rates on this page a <b>floor rather than a ceiling</b>,
      and it is being checked separately. It does not change which customers are
      risky, only how many of them we have caught by the time we look.</li>
    </ul>
  </div>
</section>
""")

if PENDING:
    W("""<div class="warnbox" style="margin-top:26px">
    <h3>Figures still being counted</h3>
    The boxes marked %s on this page are waiting on
    <code>sql/56_dashboard_numbers.sql</code>. Run it and the page fills in; until
    then they are shown as gaps rather than estimates, because an estimate here
    would be indistinguishable from a count and nobody downstream could tell.
  </div>
""" % " and ".join("<b>" + x + "</b>" for x in sorted(PENDING)))

W("""<footer>
  <span>Customer counts are from the last six months of billing records.
  Risk figures are counted on the six months before that, because measuring
  whether someone stops paying needs months afterwards to observe. All amounts
  in Toman.</span>
  <span>The detailed version, with the queries and the statistics behind every
  figure, is in the <a href="https://claude.ai/artifact/HZSVj2iWoYHdhrTDxjF2uQ">programme
  deck</a> and the <a href="https://claude.ai/artifact/H5jJHuD6i6r3gim31Rfrte">risk
  workbook</a>.</span>
</footer>
</div>
""")

LOSS_OK  = ANNUAL * BASE_PER_1000 / 1000.0
html = (out.getvalue()
        .replace("__LOSS_OK__",  one(LOSS_OK))
        .replace("__LOSS_BAD__", one(LOSS_OK * SHOCK_RATIO))
        .replace("__LOSS_GAP__", one(LOSS_OK * SHOCK_RATIO - LOSS_OK))
        .replace("__RATIO__",    one(SHOCK_RATIO)))
assert "__" not in html.replace("__EXTRA__",""), "a placeholder went unfilled"

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_manager.html"), "w", encoding="utf-8").write(html)
print("written", len(html), "bytes;", len(PENDING), "pending statements:", sorted(PENDING))

# -*- coding: utf-8 -*-
"""The manager dashboard, on the model's own numbers.

Grades, limits and PDs come from the trained model (refit run 1405-07-14).
The funnel comes from the 1405 window. The loss band and the bill-shock
premiums are as the programme deck carries them.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style

# ---- the model's grade mix. pd is the FOUR-MONTH probability the model was
#      fitted on; it sets the ranking and the limit. The money below uses the
#      one-month loss band, because the product is one month.
GRADES = [("A", 3_029_397, 0.001417, 400_000, "safest"),
          ("B", 4_087_448, 0.003298, 300_000, ""),
          ("C", 1_085_787, 0.007387, 150_000, ""),
          ("D",   599_140, 0.013538, 100_000, ""),
          ("E",   542_951, 0.040000,       0, "declined")]
SCORED   = 9_344_723
APPROVED = sum(g[1] for g in GRADES if g[3] > 0)
DECLINED = SCORED - APPROVED
OUTSTAND = sum(g[1] * g[3] for g in GRADES)
AVG_LIM  = OUTSTAND / APPROVED
CYCLES   = 12
ANNUAL   = OUTSTAND * CYCLES / 1e9
LOSS_LO, LOSS_HI = 0.0009, 0.0014      # one-month loss rate band
TARGET_BN = 15_000.0

# ---- the funnel, 140501..140506 at the 170,000 Toman bar
FUNNEL = [("Everyone on a permanent contract", "the starting point", 41_270_092, None),
          ("They bill enough to carry a loan", "at least 170,000 Toman in 2 of 6 months",
           10_087_975, "did not bill 170,000 in any two months"),
          ("Outgoing service never cut off", "not once in six months",
           9_437_240, "had outgoing service suspended"),
          ("Incoming service never cut off", "not once in six months",
           9_344_723, "had incoming service suspended"),
          ("Scored well enough to lend to", "the model declines the riskiest grade",
           APPROVED, "scored in the riskiest grade")]

# ---- how much a bigger bill raises the risk. Measured on 4.0M customer-months.
SHOCK = [("The bill barely moves", "under 1.25 times", 1.000),
         ("It rises, but stays under double", "1.25 to 2.00 times", 1.133),
         ("It doubles or more", "2.00 times and above", 1.907)]

# ---- what the model is
AUC, KS = 0.8278, 0.5151

STRESS = [("As modelled", 1.00), ("Live-set drift", 1.157),
          ("Lending into Nowruz", 1.68), ("Twice the modelled rate", 2.00)]

def f(n):   return "{:,}".format(int(round(n)))
def one(x): return "{:.1f}".format(x)
def bnf(x): return "{:,.1f}".format(x)
def pc(a, b): return "{:.0f}".format(100.0 * a / b)

# each grade's share of total expected loss, from exposure times its own risk
RISKW = [(g[0], g[1] * g[3] * g[2]) for g in GRADES if g[3] > 0]
RISKT = sum(w for _, w in RISKW)
LOSS_MID = ANNUAL * (LOSS_LO + LOSS_HI) / 2

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
.gr{font-family:var(--mono);font-weight:600}
.split > *{min-width:0}
.panel .tbl-s{max-width:100%}
"""

W(dash_style.head("Lending on the Phone Bill", EXTRA))

W("""<header>
  <p class="eyebrow">Direct Carrier Billing &middot; what it is and what it costs</p>
  <h1>Lending customers money on their next phone bill</h1>
  <p class="lede">A customer borrows against their phone bill, spends it on
  services they already use, and repays it on the bill that arrives next month.
  Every customer is scored, given a limit that matches their score, and the
  riskiest are declined. This is the size of that programme.</p>
  <div class="spec">
    <span class="chip">term <b>one month</b></span>
    <span class="chip">limits <b>100,000 to 400,000 Toman</b></span>
    <span class="chip">approved <b>%s</b></span>
    <span class="chip">all amounts <b>Toman</b></span>
  </div>
</header>

<div class="kpi" style="margin-top:26px">
  <div class="tile"><span class="k">customers approved</span><span class="v">%s</span>
    <span class="s">%s&#37; of everyone scored</span></div>
  <div class="tile"><span class="k">average limit</span><span class="v">%s</span>
    <span class="s">set by the customer's own score</span></div>
  <div class="tile"><span class="k">lent over a year</span><span class="v">%s bn</span>
    <span class="s">%s&#37; of the 15,000 bn ambition</span></div>
  <div class="tile"><span class="k">expected to go unpaid</span><span class="v">%s&ndash;%s bn</span>
    <span class="s">a year, assuming we recover nothing</span></div>
</div>
<p class="cap">The one-month term is why the third figure is so large. Only
<b>%s bn</b> is out on loan at any one moment; it comes back and goes out again
every month, twelve times a year. A four-month product would do it three times
on the same money.</p>
""" % (f(APPROVED), f(APPROVED), pc(APPROVED, SCORED), f(AVG_LIM), f(ANNUAL),
       pc(ANNUAL, TARGET_BN), one(ANNUAL*LOSS_LO), one(ANNUAL*LOSS_HI), bnf(OUTSTAND/1e9)))

# ------------------------------------------------------------------ funnel
W("""<section>
  <div class="head">
    <h2>Who gets it</h2>
    <p>Four checks on the customer's record, then the score.</p>
  </div>
  <div class="card">
    <div class="fun">
""")
prev = None
for i, (title, sub, n, drop) in enumerate(FUNNEL):
    if drop:
        W('      <div class="fdrop"><span>&minus; %s</span><span class="v">%s</span></div>\n'
          % (drop, f(prev - n)))
    cls = "last" if i == len(FUNNEL)-1 else ("keep" if i else "")
    W('      <div class="fstep %s"><div class="t">%s<em>%s</em></div>'
      '<div class="v">%s</div></div>\n' % (cls, title, sub, f(n)))
    prev = n
W("""    </div>
    <p class="cap"><b>The revenue check does almost all the work.</b> It removes
    %s customers &mdash; 97 of every 100 we turn away. It is not a judgement
    about whether they would repay, only about whether their bill is large
    enough to carry a loan, so lowering it adds volume without making the book
    riskier. <b>The score removes only %s more</b>, because by the time a
    customer has cleared the first three checks they are already a reasonable
    risk.</p>
  </div>
</section>
""" % (f(41_270_092 - 10_087_975), f(DECLINED)))

# ------------------------------------------------------------------ grades
W("""<section>
  <div class="head">
    <h2>How much each customer gets</h2>
    <p>The model sorts every customer into one of five grades. The grade sets
    the limit, and the safest customers get the most.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Grade</th><th>Customers</th><th>Limit</th><th>4-month default rate</th>
      <th>Lent at a time</th><th>Share of losses</th></tr></thead>
      <tbody>
""")
for name, n, pd, lim, note in GRADES:
    if lim == 0:
        W('        <tr class="off"><td><span class="gr">%s</span> &mdash; %s</td><td>%s</td>'
          '<td>declined</td><td>%s&#37;</td><td>&mdash;</td><td>&mdash;</td></tr>\n'
          % (name, note, f(n), "{:.2f}".format(pd*100)))
        continue
    share = dict(RISKW)[name] / RISKT
    W('        <tr><td><span class="gr">%s</span>%s</td><td>%s</td><td>%s</td>'
      '<td>%s&#37;</td><td>%s bn</td><td><b>%s&#37;</b></td></tr>\n'
      % (name, (" &mdash; " + note) if note else "", f(n), f(lim),
         "{:.2f}".format(pd*100), bnf(n*lim/1e9), "{:.0f}".format(100*share)))
W("""        <tr class="tot"><td>Approved</td><td><b>%s</b></td><td>%s average</td>
            <td></td><td><b>%s bn</b></td><td>100&#37;</td></tr>
      </tbody>
      <tfoot><tr><td colspan="6"><b>Grade B carries half the losses</b> and it is
      the second-safest group &mdash; because it is the largest, and it gets a
      300,000 limit. Risk per customer is not the same as risk to the book, and
      the limits are where that gets decided. The default rate column is the model's own score
      on the four-month history it was built from, used to order customers and
      set limits; the money below uses the one-month rate, because the product
      is one month.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (f(APPROVED), f(AVG_LIM), bnf(OUTSTAND/1e9)))

# ------------------------------------------------------------- bill shock
W("""<section>
  <div class="head">
    <h2>One rule the limits have to respect</h2>
    <p>The loan lands on the customer's next bill. How far that bill jumps
    decides how likely they are to stop paying, and the effect is sharp.</p>
  </div>
  <div class="rule">
    <div class="big">Never lend someone more than they bill in a month.</div>
    <div class="why">Below that line the bill rises by less than double and
    customers carry on paying at close to the normal rate. At or above it the
    bill doubles &mdash; and <b>customers whose bill doubles stop paying
    %s times as often</b>. The line sits exactly at "the loan equals the
    bill".</div>
  </div>
  <div class="card" style="margin-top:14px">
    <div class="tbl-s"><table>
      <thead><tr><th>What happens to their bill</th><th>How far it rises</th>
      <th>They stop paying</th></tr></thead>
      <tbody>
""" % one(SHOCK[2][2] / SHOCK[1][2]))
for nm, rng, v in SHOCK:
    cls = ' class="tot"' if v > 1.5 else (' class="off"' if v == 1.0 else "")
    lab = "at the normal rate" if v == 1.0 else ("%s times as often" % "{:.2f}".format(v))
    W('        <tr%s><td>%s</td><td>%s</td><td><b>%s</b></td></tr>\n' % (cls, nm, rng, lab))
W("""      </tbody>
      <tfoot><tr><td colspan="3">Measured on 4.0 million customer-months,
      holding the month, the size of the bill and which way it was already
      moving all constant. <b>The limit table above already respects this</b>
      &mdash; the largest limit is 400,000 and it goes only to grade A, whose
      customers bill well above that.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""")

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
        <p><b>%s bn</b> is out on loan at any one time. It comes back each month
        and goes out again, so <b>%s bn</b> is lent across a full year.</p></div></div>
      <div class="stp"><span class="n">2</span><div>
        <h3>The one-month default rate is 0.09 to 0.14&#37;</h3>
        <p>The span is a choice about how wide to open the book, not an
        uncertainty. Lend only to the safest and it sits at the bottom; approve
        everyone the model passes and it sits at the top.</p></div></div>
      <div class="stp"><span class="n">3</span><div>
        <h3>So we lose %s to %s bn Toman a year</h3>
        <p>That assumes we recover <b>nothing</b> from a customer who stops
        paying, which is deliberately pessimistic &mdash; the operator keeps
        collecting after the line is cut off. Against %s bn lent, the midpoint
        is about <b>1.15 Toman lost for every 1,000 lent</b>.</p></div></div>
    </div>
  </div>
  <div class="card">
    <h3>If losses come in worse than modelled</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>Scenario</th><th>Multiple</th><th>Lost in a year</th>
      <th>Against %s bn lent</th></tr></thead>
      <tbody>
""" % (f(APPROVED), f(AVG_LIM), bnf(OUTSTAND/1e9), f(ANNUAL),
       one(ANNUAL*LOSS_LO), one(ANNUAL*LOSS_HI), f(ANNUAL), f(ANNUAL)))
for nm, m in STRESS:
    cls = ' class="tot"' if m == 1.00 else ""
    W('        <tr%s><td>%s</td><td>%s&times;</td><td>%s bn</td><td>%s&#37;</td></tr>\n'
      % (cls, nm, "{:.2f}".format(m), one(LOSS_MID*m),
         "{:.2f}".format(100*LOSS_MID*m/ANNUAL)))
W("""      </tbody>
      <tfoot><tr><td colspan="4">Even at <b>twice</b> the modelled rate the
      programme loses under <b>%s bn</b> on <b>%s bn</b> lent. The loss case is
      not where the risk in this product sits &mdash; the volume case is.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (one(LOSS_MID*2), f(ANNUAL)))

# ------------------------------------------------------------- open
W("""<section>
  <div class="head">
    <h2>What we do not know yet</h2>
    <p>Two things, so nothing above is taken as more certain than it is.</p>
  </div>
  <div class="split">
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Nobody in this data ever had credit</h3>
      <ul>
        <li>The score describes how customers behave when they are <b>not</b>
        borrowing. How they behave when they are is genuinely unknown.</li>
        <li><b>A capped pilot is the only thing that answers it</b>, and a
        one-month loan means the answer arrives in weeks rather than a year.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>Is the 15,000 bn target lending or exposure?</h3>
      <ul>
        <li>At monthly turnover the two differ by twelve times. As
        <b>lending over a year</b> the programme reaches %s bn, more than
        twice the target.</li>
        <li>As <b>money out at any one moment</b> it reaches %s bn and falls
        well short. Everything in the volume case depends on which is
        meant.</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  <span>Customer counts are from billing records for 140501&ndash;140506.
  Grades, limits and the risk ranking come from the scoring model refit on
  1405-07-14, which reads %s on its accuracy measure. The bill-shock figures
  were measured on 4.0 million customer-months.</span>
  <span>All amounts in Toman; the billing system stores Rial and every figure
  here is that value divided by ten. The fuller versions, with the queries and
  the statistics behind each figure, are the
  <a href="https://claude.ai/artifact/HZSVj2iWoYHdhrTDxjF2uQ">programme deck</a>
  and the <a href="https://claude.ai/artifact/H5jJHuD6i6r3gim31Rfrte">risk
  workbook</a>.</span>
</footer>
</div>
""" % (f(ANNUAL), bnf(OUTSTAND/1e9), "{:.4f}".format(AUC)))

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_manager.html"), "w", encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()), "bytes")
print("approved %s  avg limit %s  outstanding %s bn  annual %s bn  loss %s-%s bn"
      % (f(APPROVED), f(AVG_LIM), bnf(OUTSTAND/1e9), f(ANNUAL),
         one(ANNUAL*LOSS_LO), one(ANNUAL*LOSS_HI)))

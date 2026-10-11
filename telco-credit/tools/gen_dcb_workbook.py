# -*- coding: utf-8 -*-
"""The detailed companion to the DCB deck: what the label is, nine worked
subscribers, and the whole bill-shock chain of evidence.

Every figure here is carried as a constant with its source named beside it.
Nothing is placed by hand - bars, strata and premiums are computed from these
constants, so a corrected measurement changes the page by changing one line.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style

# ====================================================================== DATA
# --- the label.  42_model_datasets.sql (screen, windows) and
#     52_one_month_label_choice.sql (the one-month rate).
SCREENED  = 8_701_085      # subscribers past the screen on 140401-140406
LAB1_N    = 19_215         # two-way bars in a single label month
LAB1_PCT  = 0.2208
LAB4_N    = 45_361         # the four-month label this was measured against
LAB4_PCT  = 0.5213
BAR_MODEL = 105_000        # Toman. the model window's revenue bar
BAR_PROD  = 170_000        # Toman. the production bar

# --- S5, the crude shock gradient. 53_bill_shock.sql, 140401-140406,
#     outcome a two-way bar in the two months after the repayment month.
S5 = [("The bill fell",      "under 0.80",  4_393_649, 18_086, 0.4116, 1.80),
      ("Normal",             "0.80 - 1.25", 6_428_541, 14_723, 0.2290, 1.00),
      ("Rose a little",      "1.25 - 1.50", 2_441_872,  5_948, 0.2436, 1.06),
      ("Rose by half",       "1.50 - 2.00", 2_141_578,  6_501, 0.3036, 1.33),
      ("Rose past double",   "2.00 - 3.00", 1_138_755,  5_143, 0.4516, 1.97),
      ("Rose past triple",   "over 3.00",     796_137,  5_741, 0.7211, 3.15)]

# --- S8, the paired test split by shock size.
S8 = [("1.50 - 2.00", 767_568, 0.2366, 0.2331, 0.985, "628 vs 655", "0.47"),
      ("2.00 - 3.00", 286_658, 0.3342, 0.3328, 0.996, "330 vs 334", "0.91"),
      ("over 3.00",   114_943, 0.5037, 0.4472, 0.888, "168 vs 233", "0.0014")]

# --- S9, the confound that killed the paired design.
S9 = [("140405 carried the raised bill", 592_731, 0.3696, 0.2785, 0.75, "405 vs 945"),
      ("140406 carried the raised bill", 576_438, 0.2016, 0.2786, 1.38, "721 vs 277")]

# --- S10/S11, Mantel-Haenszel over bill-size bands, one calendar month,
#     split by which way the bill was already moving. Reference band still
#     contaminated here, so every number is understated.
S1011 = [("The bill was falling", 0.707, 1.001),
         ("The bill was flat",    0.825, 1.447),
         ("The bill was rising",  0.924, 1.668)]
S1011_POOLED = (0.832, 1.396)

# --- the corrected run: clean 0.80-1.25 reference, new lines excluded,
#     RBG intervals.
MH = [("The bill fell",        1.887, 1.834, 1.942, "crit"),
      ("Normal",               1.000, None,  None,  "base"),
      ("Rose by up to 2x",     1.133, 1.097, 1.171, "warn"),
      ("Rose by 2x or more",   1.907, 1.829, 1.989, "crit")]
MH_DEFAULTS = 12_042
MH_MONTHS   = 4.0e6
MH_CRUDE    = 1.908

# --- the premium falls as the bill grows, which is the reverse of the raw read
BYSIZE = [("under 150,000", 2.11), ("150,000 - 300,000", 1.61),
          ("300,000 - 600,000", 1.37), ("above 600,000", 1.00)]

# --- the screen nobody wrote
NEWLINE = dict(n=109_360, bars=2_959, rate=2.706, other_n=8_585_353,
               other_bars=30_050, other_rate=0.350, ratio=7.7)

# --- other measured multipliers used in the scenarios
M_PREBAR   = 13.2   # a two-way bar in the 12 months before the window
M_NOPAY    = 8.3    # payment coverage under 0.10 (52, D3)
COVER_OK   = "0.10 to 1.00 carries no excess bar risk at all"

# --- the model, refit run 1405-07-14
AUC = [("Logistic, VALID",            0.7385, 0.7843),
       ("HistGB, VALID",              0.7918, 0.8157),
       ("HistGB calibrated, TEST",    0.8017, 0.8278)]
SCALEFREE = 0.8230
PRE_GAIN  = 0.0239
CALIB = [("Safest 3 deciles", 0.1038, 0.0806, 0.776),
         ("Safest 5 deciles", 0.1305, 0.1171, 0.898),
         ("All 10 deciles",   0.5232, 0.5146, 0.983)]
DRIFT_LIVE, DRIFT_TEST = 0.5952, 0.5146

# ---------------------------------------------------------------- scenarios
# Nine constructed profiles. The revenue months are invented to make a point;
# every multiplier attached to them is measured, and its query is named.
# Revenue is in thousands of Toman.
def _sh(rev6, ticket): return (rev6 + ticket) / float(rev6)

SCN = [
 dict(n="01", tag="Steady, heavy biller", ticket=300,
      rev=[200,205,198,210,202,207], tenure=96, cover=1.00, prebar=0, zero=0,
      sees="rev_6m, rev_max, rev_trend, pay_months, tenure_m",
      drivers=[("A draw of 300,000 on a 207,000 bill", 1.907,
                "53 S10/S11 corrected, rise of 2x or more")],
      verdict="warn",
      note="Nothing about this subscriber is risky. The ticket is. At 150,000 "
           "the same person sits at 1.72x and carries the 1.133 premium, which "
           "is less than half the expected loss for half the draw."),

 dict(n="02", tag="Steady, light biller", ticket=100,
      rev=[115,108,120,112,118,110], tenure=54, cover=0.96, prebar=0, zero=0,
      sees="rev_6m, rev_min, pay_months, tenure_m",
      drivers=[("A draw of 100,000 on a 110,000 bill", 1.133,
                "53 S10/S11 corrected, rise of up to 2x")],
      verdict="warn",
      note="The 100,000 minimum ticket is the binding case. It clears 2.00x "
           "only while the bill stays above 100,000 Toman, and this subscriber "
           "is 10,000 above that line. A month of lighter use puts them in the "
           "1.91 band at the product's smallest possible draw."),

 dict(n="03", tag="The bill is collapsing", ticket=150,
      rev=[480,445,390,305,230,160], tenure=71, cover=0.92, prebar=0, zero=0,
      sees="rev_trend, r1..r6, rev_max, rev_min",
      drivers=[("The bill fell across the window", 1.887,
                "53 S10/S11 corrected, bill below 0.80x"),
               ("A draw of 150,000 on a 160,000 bill", 1.133,
                "53 S10/S11 corrected, rise of up to 2x")],
      verdict="crit",
      note="The strongest single signal in the data, and it looks like nothing "
           "on a credit screen - the subscriber pays, has tenure and has never "
           "been barred. They are leaving. rev_trend reads -620,000 and that is "
           "the column carrying it."),

 dict(n="04", tag="Spending is escalating", ticket=300,
      rev=[120,135,150,175,205,260], tenure=38, cover=0.94, prebar=0, zero=0,
      sees="rev_trend, r1..r6, avail_max",
      drivers=[("A 2x draw on a bill already climbing", 1.668,
                "53 S10/S11, rising + 2x or more. Understated: measured "
                "before the reference band was cleaned")],
      verdict="crit",
      note="The trap in the feature set. A rising bill reads as health, and on "
           "its own it is. Combined with a draw that doubles it, this is the "
           "worst cell measured anywhere in 53. The limit engine has to read "
           "rev_trend and the draw size together, not either alone."),

 dict(n="05", tag="Spending had been falling", ticket=150,
      rev=[300,290,180,150,140,145], tenure=83, cover=0.98, prebar=0, zero=0,
      sees="rev_trend, r1..r6",
      drivers=[("A 2x draw on a bill that had been falling", 1.001,
                "53 S10/S11, falling + 2x or more")],
      verdict="good",
      note="The same 2x rise as 04 and no excess risk whatsoever. For someone "
           "whose bill had been dropping, a doubled month is a return to what "
           "they used to spend. Direction is not a detail on top of size - it "
           "decides whether size matters."),

 dict(n="06", tag="The line is new", ticket=150,
      rev=[0,0,0,180,195,188], tenure=4, cover=1.00, prebar=0, zero=3,
      sees="n_zero_rev_months, rev_months, tenure_m, pre_absent",
      drivers=[("A zero-billing month inside the window", 7.7,
                "53, new-subscriber group: 2.706 pct against 0.350 pct")],
      verdict="crit",
      note="This profile satisfies the screen. It asks for revenue above the "
           "bar in 2 of 6 months and this line clears it in 3. Nothing looks "
           "for the gap. 109,360 subscribers are in this position and they bar "
           "at 7.7x everyone else."),

 dict(n="07", tag="Barred before", ticket=150,
      rev=[180,176,184,179,181,177], tenure=112, cover=0.88, prebar=1, zero=0,
      sees="pre_tw_any, pre_tw_months, pre_months_seen",
      drivers=[("A two-way bar in the 12 months before the window", 13.2,
                "42, pre-window measurement against the label rate")],
      verdict="crit",
      note="The screen excludes a bar inside the feature window and says "
           "nothing about the year before it. That history is the single most "
           "valuable thing in the feature set: removing the six pre_ columns "
           "costs 0.0239 of test AUC, which is 92 percent of what the refit "
           "gained."),

 dict(n="08", tag="Bills, but does not pay", ticket=150,
      rev=[220,218,225,219,222,221], tenure=63, cover=0.04, prebar=0, zero=0,
      sees="paid_6m, paid_max, pay_months, outst_max, outst_avg",
      drivers=[("Payment coverage under 0.10", 8.3,
                "52, D3: the only coverage band carrying excess risk")],
      verdict="crit",
      note="Revenue says nothing is wrong. The payment side says everything "
           "is. This is the case the revenue bar cannot see, because the bar "
           "screens on what a subscriber is billed rather than what they pay."),

 dict(n="09", tag="Pays slowly, pays eventually", ticket=300,
      rev=[350,344,358,349,352,347], tenure=77, cover=0.61, prebar=0, zero=0,
      sees="paid_6m, pay_months, outst_max",
      drivers=[("A draw of 300,000 on a 347,000 bill", 1.133,
                "53 S10/S11 corrected, rise of up to 2x")],
      verdict="good",
      note="The false alarm, and worth stating because it is the one a credit "
           "committee will want to decline. Coverage of 0.61 means a growing "
           "balance and a subscriber who is always behind - and " + COVER_OK +
           ". Only paying essentially nothing does, which is 08."),
]

# ====================================================================== SETUP
def f(n):   return "{:,}".format(int(round(n)))
def pct(x, d=4): return ("{:." + str(d) + "f}").format(x)
def tm(k):  return f(k * 1000)                      # thousands of Toman -> Toman

def band_of(shock):
    if shock < 1.25: return "g1", 1.000
    if shock < 2.00: return "g2", 1.133
    return "g3", 1.907

# guard: a scenario whose headline driver is a draw must agree with the band
# its own arithmetic falls into. Catches a ticket edited without its premium.
for s in SCN:
    sh = _sh(s["rev"][5], s["ticket"])
    s["shock"] = sh
    for label, mult, src in s["drivers"]:
        if label.startswith("A draw of"):
            assert abs(band_of(sh)[1] - mult) < 1e-9, (s["n"], sh, mult)

out = io.StringIO(); W = out.write

EXTRA = """
/* the label calendar */
.cal{display:flex;gap:3px;min-width:560px;margin-top:6px}
.cal .mo{flex:1 1 0;border-radius:3px;padding:7px 2px 8px;text-align:center;
  font-family:var(--mono);font-size:10px;color:var(--ink-2);line-height:1.3;
  border:1px solid var(--rule)}
.cal .mo b{display:block;font-size:11px;color:var(--ink);font-weight:600}
.cal .pre,.callegend i.pre{background:var(--raise)}
.cal .ft,.callegend i.ft{background:color-mix(in srgb,var(--o2) 20%,var(--surface))}
.cal .dw,.callegend i.dw{background:color-mix(in srgb,var(--warn) 30%,var(--surface))}
.cal .lb,.callegend i.lb{background:color-mix(in srgb,var(--crit) 24%,var(--surface))}
.callegend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:13px;color:var(--ink-2)}
.callegend span{display:flex;align-items:center;gap:7px}
.callegend i{width:12px;height:12px;border-radius:3px;display:block;border:1px solid var(--rule)}

/* the nine subscribers */
.scns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media (max-width:820px){.scns{grid-template-columns:1fr}}
.scn{background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:18px 18px 20px;display:flex;flex-direction:column;gap:13px;min-width:0}
.scn.good{border-left:3px solid var(--good)}
.scn.warn{border-left:3px solid var(--warn)}
.scn.crit{border-left:3px solid var(--crit)}
.scn .top{display:flex;align-items:baseline;gap:10px}
.scn .top .n{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ink-3)}
.scn .top h3{font-size:15.5px;min-width:0}
.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 14px;
  font-family:var(--mono);font-size:12px;color:var(--ink-3)}
.facts span{display:flex;justify-content:space-between;gap:8px;border-bottom:1px dotted var(--rule);padding-bottom:3px}
.facts b{color:var(--ink-2);font-weight:500}
.drw{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);
  background:var(--raise);border-radius:5px;padding:8px 10px;line-height:1.45}
.drw b{color:var(--ink);font-weight:600}
.drv{display:flex;flex-direction:column;gap:9px;margin:0;padding:0;list-style:none}
.drv li{display:flex;gap:11px;align-items:flex-start;font-size:13px;color:var(--ink-2);line-height:1.45}
.drv .m{font-family:var(--mono);font-size:14px;font-weight:600;flex:0 0 58px;text-align:right}
.drv .m.hot{color:var(--crit)}
.drv .m.mid{color:var(--warn)}
.drv .m.ok{color:var(--good-ink)}
.drv em{font-style:normal;display:block;color:var(--ink-3);font-size:11.5px;
  font-family:var(--mono);margin-top:2px}
.pd{display:flex;align-items:baseline;gap:9px;border-top:1px solid var(--rule);padding-top:11px}
.pd .v{font-family:var(--mono);font-size:21px;font-weight:600;letter-spacing:-0.02em}
.pd .k{font-size:12px;color:var(--ink-3);line-height:1.35}
.scn .note{font-size:13px;color:var(--ink-3);line-height:1.55}
.sees{font-family:var(--mono);font-size:11px;color:var(--ink-3);line-height:1.5;
  border-top:1px solid var(--rule);padding-top:10px}
.sees b{color:var(--ink-2);font-weight:500;letter-spacing:0.06em;text-transform:uppercase;font-size:10px}

.warnbox{background:color-mix(in srgb,var(--warn) 13%,var(--surface));
  border:1px solid color-mix(in srgb,var(--warn) 45%,var(--rule));
  border-radius:8px;padding:16px 18px;font-size:14px;color:var(--ink-2);line-height:1.6}
.warnbox b{color:var(--ink);font-weight:600}
/* a panel holding a min-width table is a grid child: without this the track
   cannot shrink and the whole page scrolls sideways on a phone */
.split > *{min-width:0}
.panel .tbl-s{max-width:100%}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:12px;font-size:13px;color:var(--ink-2)}
.legend span{display:flex;align-items:center;gap:7px}
.legend i{width:11px;height:11px;border-radius:2px;display:block}
"""

W(dash_style.head("DCB Risk Workbook", EXTRA))

# ---------------------------------------------------------------- header
W("""<header>
  <p class="eyebrow">Direct Carrier Billing &middot; the detail behind the deck</p>
  <h1>What the label means, and what moves it</h1>
  <p class="lede">The one-page deck carries the decisions. This carries the
  evidence under them: how a default is defined when nobody in the data ever
  had credit, nine subscribers worked end to end, and the whole bill-shock
  chain including the two measurements that turned out to be wrong.</p>
  <div class="spec">
    <span class="chip">windows <b>140401&ndash;140408</b></span>
    <span class="chip">screened <b>%s</b></span>
    <span class="chip">label <b>one month</b></span>
    <span class="chip">all amounts <b>Toman</b></span>
  </div>
</header>
""" % f(SCREENED))

W("""<div class="kpi" style="margin-top:26px">
  <div class="tile"><span class="k">base rate, one month</span><span class="v">%s pct</span>
    <span class="s">%s two-way bars in a single label month</span></div>
  <div class="tile"><span class="k">population</span><span class="v">%s</span>
    <span class="s">subscribers past the screen on the 1404 window</span></div>
  <div class="tile"><span class="k">worst measured premium</span><span class="v">13.2&times;</span>
    <span class="s">a two-way bar in the 12 months before</span></div>
  <div class="tile"><span class="k">model, test AUC</span><span class="v">%s</span>
    <span class="s">on the four-month label, not yet refit for DCB</span></div>
</div>
""" % (pct(LAB1_PCT), f(LAB1_N), f(SCREENED), "{:.4f}".format(AUC[2][2])))

# ================================================== 1. what the label is
W("""<section>
  <div class="head">
    <p class="eyebrow">Part one</p>
    <h2>What counts as a default</h2>
    <p>Nobody in this data was ever given spendable credit, so the label cannot
    be "did not repay the DCB debt". It is the operator's own action: the month
    after the draw, was the line two-way barred.</p>
  </div>
  <div class="card">
    <h3>The calendar</h3>
    <div class="svgbox"><div class="cal">
""")
CAL = ([("1403", "01&ndash;12", "pre", "bar history")] +
       [("1404", "0" + str(m), "ft", "features") for m in range(1, 7)] +
       [("1404", "07", "dw", "the draw"), ("1404", "08", "lb", "the label")])
for yr, mo, cls, _lab in CAL:
    W('      <div class="mo %s"><b>%s</b>%s</div>\n' % (cls, mo, yr))
W("""    </div></div>
    <div class="callegend">
      <span><i class="pre"></i>140301&ndash;140312 &mdash; bar history, read but never scored</span>
      <span><i class="ft"></i>140401&ndash;140406 &mdash; the six feature months</span>
      <span><i class="dw"></i>140407 &mdash; the draw lands on this bill</span>
      <span><i class="lb"></i>140408 &mdash; was the line two-way barred</span>
    </div>
    <p class="cap">The draw month sits between the features and the label on
    purpose. A subscriber is scored on what they did before the credit existed
    and judged on the first bill that carries it, which is the only shape a
    one-month product can be measured in.</p>
  </div>
""")

W("""  <div class="split" style="margin-top:14px">
    <div class="panel known">
      <h3><span class="dot" style="background:var(--good)"></span>The label is</h3>
      <ul>
        <li><b>sbrp_stat_id = 4</b> in month 140408 &mdash; a two-way bar. The
        line can neither call nor be called.</li>
        <li><b>Two-way, not one-way.</b> A one-way bar restricts telco spending,
        and DCB credit is a separate pool: a subscriber cannot buy packages with
        it and cannot pay their bill with it. A DCB default cannot produce a
        one-way bar, so counting one would be counting the wrong event.</li>
        <li><b>One month.</b> The draw is repaid on the next bill, so the window
        that matters is the one month after it.</li>
        <li>Measured at <b>%s pct</b>, <b>%s events</b> &mdash; thick enough to
        fit on. The four-month version of the same label ran %s pct.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>The label is not</h3>
      <ul>
        <li><b>A repayment record.</b> No subscriber in this window had DCB
        credit to fail to repay. The bar is a proxy for the behaviour that
        would cause a default, not an observation of one.</li>
        <li><b>Prompt.</b> A bar can lag more than the window allows, so some
        defaults land outside it and the measured rate is a floor.</li>
        <li><b>Blind to substitution.</b> Whether a subscriber spends DCB credit
        <i>instead of</i> what they already buy, or <i>on top of</i> it, is
        unknown. Substitution can only make this safer.</li>
        <li><b>Behaviour under credit.</b> Everything here is how subscribers
        behave without it. A pilot is the only thing that answers that.</li>
      </ul>
    </div>
  </div>
""" % (pct(LAB1_PCT), f(LAB1_N), pct(LAB4_PCT)))

W("""  <div class="card" style="margin-top:14px">
    <h3>The screen that produced the population</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>Condition</th><th>Column</th><th>What it removes</th></tr></thead>
      <tbody>
        <tr><td>Revenue at or above %s in 2 of the 6 months</td>
            <td>r1 &hellip; r6</td><td>subscribers too light to carry a bill</td></tr>
        <tr><td>Never one-way barred in the window</td>
            <td>o1 &hellip; o6</td><td>lines already restricted</td></tr>
        <tr><td>Never two-way barred in the window</td>
            <td>f_twoway</td><td>lines already gone</td></tr>
      </tbody>
      <tfoot><tr><td colspan="3">The revenue bar is <b>97.67 percent of all
      exclusions</b>, and 46_bar_ladder_risk showed it is a <b>capacity</b>
      screen rather than a risk one: lowering it adds volume without adding
      loss rate. The production bar is %s, measured here at %s because the model
      window predates two price rises. <b>Nothing in this screen looks for a
      zero-billing month</b>, which Part three shows is worth 7.7x.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (f(BAR_MODEL), f(BAR_PROD), f(BAR_MODEL)))

# ================================================== 2. nine subscribers
W("""<section>
  <div class="head">
    <p class="eyebrow">Part two</p>
    <h2>Nine subscribers, worked through</h2>
    <p>Each card is a constructed profile. The six months of revenue are
    invented to make a point; every multiplier attached to them is measured,
    and the query it came from is printed under it.</p>
  </div>
  <div class="warnbox">
    <b>What these cards do not contain is a model score.</b> The model has not
    yet been refit on the one-month label, so there is no pd for these profiles
    and inventing one would be the worst thing on this page. What each card
    shows instead is arithmetic you can check: the measured base rate of
    %s pct multiplied by the measured premiums the profile triggers. Where two
    premiums apply, the range runs from the largest alone to all of them
    multiplied &mdash; the drivers are not known to be independent, and the
    truth is somewhere inside. Once the refit runs, every card gets a real pd
    and this arithmetic becomes the check on it.
  </div>
  <div class="scns" style="margin-top:14px">
""" % pct(LAB1_PCT))

SPW, SPH = 268, 58
for s in SCN:
    rev, tk = s["rev"], s["ticket"]
    top = max(max(rev), rev[5] + tk)
    cls, prem = band_of(s["shock"])
    mults = [d[1] for d in s["drivers"]]
    lo = LAB1_PCT * (max(mults) if mults else 1.0)
    hi = LAB1_PCT
    for m in mults: hi *= m
    W('    <article class="scn %s">\n' % s["verdict"])
    W('      <div class="top"><span class="n">%s</span><h3>%s</h3></div>\n' % (s["n"], s["tag"]))
    # the sparkline: six history months, then the draw month stacked on its bill
    W('      <svg viewBox="0 0 %d %d" role="img" aria-label="six months of billing, then the draw month">\n'
      % (SPW, SPH))
    bw = (SPW - 6 * 5) / 7.0
    base, plot = SPH - 13, SPH - 19
    for i in range(7):
        x = i * (bw + 5)
        if i < 6:
            v = rev[i]; h = (v / float(top)) * plot
            W('        <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="var(--o2)">'
              '<title>month %d: %s Toman</title></rect>\n' % (x, base - h, bw, max(h, 1.5), i + 1, tm(v)))
        else:
            hb = (rev[5] / float(top)) * plot
            ht = (tk / float(top)) * plot
            W('        <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="var(--o2)">'
              '<title>the bill: %s Toman</title></rect>\n' % (x, base - hb, bw, max(hb, 1.5), tm(rev[5])))
            W('        <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s">'
              '<title>the draw: %s Toman</title></rect>\n'
              % (x, base - hb - 2 - ht, bw, max(ht, 1.5),
                 {"g1": "var(--good)", "g2": "var(--warn)", "g3": "var(--crit)"}[cls], tm(tk)))
        W('        <text class="tk" x="%.1f" y="%d" text-anchor="middle" style="font-size:9px">%s</text>\n'
          % (x + bw / 2, SPH - 2, "draw" if i == 6 else str(i + 1)))
    W('      </svg>\n')
    W('      <div class="facts">\n')
    for k, v in [("tenure", "%d mo" % s["tenure"]),
                 ("coverage", "{:.2f}".format(s["cover"])),
                 ("zero months", str(s["zero"])),
                 ("prior bars", str(s["prebar"]))]:
        W('        <span>%s<b>%s</b></span>\n' % (k, v))
    W('      </div>\n')
    W('      <div class="drw">draw <b>%s</b> on a <b>%s</b> bill &rarr; the bill '
      'rises <b>%s&times;</b></div>\n' % (tm(tk), tm(rev[5]), "{:.2f}".format(s["shock"])))
    W('      <ul class="drv">\n')
    if not s["drivers"]:
        W('        <li><span class="m ok">1.00&times;</span><span>No measured driver fires.'
          '<em>the base rate is the estimate</em></span></li>\n')
    for label, mult, src in s["drivers"]:
        k = "hot" if mult >= 1.5 else ("mid" if mult > 1.05 else "ok")
        W('        <li><span class="m %s">%s&times;</span><span>%s<em>%s</em></span></li>\n'
          % (k, "{:.3f}".format(mult).rstrip("0").rstrip("."), label, src))
    W('      </ul>\n')
    rng = ("%s pct" % pct(lo, 3)) if abs(hi - lo) < 1e-9 else ("%s to %s pct" % (pct(lo, 3), pct(hi, 3)))
    W('      <div class="pd"><span class="v">%s</span>'
      '<span class="k">indicative, from the base rate<br>and the measured premiums</span></div>\n' % rng)
    W('      <p class="note">%s</p>\n' % s["note"])
    W('      <div class="sees"><b>the model reads</b><br>%s</div>\n' % s["sees"])
    W('    </article>\n')
W("""  </div>
  <p class="cap">Cards 04 and 05 are the pair to look at twice. Identical draw,
  identical rise, and one carries 1.668 while the other carries 1.001 &mdash;
  the only difference is which way the bill was already moving. That is the
  single most useful thing Part three produced, and no screen in the current
  design reads it.</p>
</section>
""")

# ================================================== 3. bill shock
W("""<section>
  <div class="head">
    <p class="eyebrow">Part three</p>
    <h2>Bill shock, and the two answers that were wrong</h2>
    <p>The question is narrow: a subscriber's bill jumps because a draw landed
    on it, so does the jump itself make them more likely to be barred. It took
    four passes to answer, and the first two answers were both wrong for
    reasons worth keeping.</p>
  </div>
""")

# --- 3a crude gradient
W("""  <div class="card">
    <h3>Pass one &mdash; the raw gradient</h3>
    <p class="cap" style="margin-top:6px">Bar rate by how far the bill moved,
    across all subscribers, 140401&ndash;140406.</p>
    <div class="svgbox">
""")
GW, GH = 790, 310
GL, GR, GT, GB = 210, 640, 18, 252
GRATIO = 690          # the ratio column, clear of the longest rate label
GMAX = max(r[4] for r in S5) * 1.18
def gx(v): return GL + v / GMAX * (GR - GL)
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="bar rate by shock band">\n' % (GW, GH))
for t in (0.2, 0.4, 0.6):
    W('      <line class="gl" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>\n' % (gx(t), GT, gx(t), GB))
    W('      <text class="tk" x="%.1f" y="%d" text-anchor="middle">%s pct</text>\n' % (gx(t), GB+17, t))
gh, ggap = 28, 11
RAMP = ["var(--crit)", "var(--sunk)", "var(--o1)", "var(--o2)", "var(--o3)", "var(--o4)"]
for i, (nm, rng, n, bars, rate, ratio) in enumerate(S5):
    y = GT + 8 + i * (gh + ggap)
    W('      <text class="an" x="%d" y="%.1f" text-anchor="end" fill="var(--ink-2)">%s</text>\n'
      % (GL-12, y+gh/2-2, nm))
    W('      <text class="tk" x="%d" y="%.1f" text-anchor="end">%s</text>\n' % (GL-12, y+gh/2+11, rng))
    W('      <rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" fill="%s" %s>'
      '<title>%s: %s subscriber-months, %s bars, %s pct</title></rect>\n'
      % (gx(0), y, max(gx(rate)-gx(0), 2), gh, RAMP[i],
         'stroke="var(--axis)" stroke-width="1"' if ratio == 1.00 else '',
         nm, f(n), f(bars), pct(rate)))
    W('      <text class="dl" x="%.1f" y="%.1f" fill="var(--ink)">%s pct</text>\n'
      % (gx(rate)+9, y+gh/2+5, pct(rate)))
    W('      <text class="dl" x="%d" y="%.1f" fill="var(--ink-3)">%s&times;</text>\n'
      % (GRATIO, y+gh/2+5, "{:.2f}".format(ratio)))
W('      <line class="ax" x1="%.1f" y1="%d" x2="%d" y2="%d"/>\n' % (gx(0), GB, GR, GB))
W('      <text class="tk" x="%d" y="%d">vs normal</text>\n' % (GRATIO, GT+2))
W('      <text class="tk" x="%.1f" y="%d">two-way bar rate in the two months after the bill</text>\n' % (gx(0), GB+40))
W('    </svg>\n    </div>\n')
W("""    <p class="cap"><b>Read the top row before the gradient.</b> The highest
    rate of any band belongs to subscribers whose bill <i>fell</i>, which is
    the opposite of what a shock story predicts. It was almost missed, because
    the first version of this query put the falling months inside the reference
    band and compared everything against them.</p>
  </div>
""")

# --- 3b paired
W("""  <div class="card">
    <h3>Pass two &mdash; compare each subscriber against themselves</h3>
    <p class="cap" style="margin-top:6px">A subscriber whose bill jumps may
    simply be a riskier subscriber. The fix is to use each person as their own
    control: one normal month, one shocked month, %s pairs.</p>
    <div class="tbl-s"><table>
      <thead><tr><th>Shock</th><th>Pairs</th><th>Their normal month</th>
      <th>Their shocked month</th><th>Premium</th><th>Discordant</th><th>McNemar</th></tr></thead>
      <tbody>
""" % f(1_169_169))
for nm, pr, a, b, prem, disc, p in S8:
    W('        <tr><td>%s</td><td>%s</td><td>%s pct</td><td>%s pct</td>'
      '<td><b>%s</b></td><td>%s</td><td>%s</td></tr>\n'
      % (nm, f(pr), pct(a), pct(b), "{:.3f}".format(prem), disc, p))
W("""      </tbody>
      <tfoot><tr><td colspan="7">Flat, flat, and <b>significantly safer</b> past
      three times normal. The conclusion drawn at this point was "a bigger bill
      does not make a subscriber default, premium 1.00" &mdash; and it was
      published before the next check was run. <b>It was wrong.</b></td></tr></tfoot>
    </table></div>
  </div>
""")

# --- 3c the confound
W("""  <div class="card">
    <h3>Why pass two could never have worked</h3>
    <p class="cap" style="margin-top:6px">Split the same paired test by
    <i>which</i> of the two months carried the raised bill.</p>
    <div class="tbl-s"><table>
      <thead><tr><th>The shocked month was</th><th>Pairs</th><th>Normal</th>
      <th>Shocked</th><th>Premium</th><th>Discordant</th></tr></thead>
      <tbody>
""")
for nm, pr, a, b, prem, disc in S9:
    W('        <tr><td>%s</td><td>%s</td><td>%s pct</td><td>%s pct</td>'
      '<td><b>%s&times;</b></td><td>%s</td></tr>\n'
      % (nm, f(pr), pct(a), pct(b), "{:.2f}".format(prem), disc))
W("""      </tbody>
      <tfoot><tr><td colspan="6">Opposite directions, both strongly significant,
      and <b>the pooled 0.97 was these two cancelling.</b> The cause is
      structural. With two months per subscriber, a raised month in one position
      is a normal month in the other, so "raised against normal" is
      <i>always also</i> "140405 against 140406" &mdash; and those two months
      are judged on different outcome windows. 140406 runs 1.33 to 1.38 times
      hotter whichever role it plays. The design was never identified; no amount
      of data would have fixed it.</td></tr></tfoot>
    </table></div>
    <p class="cap"><b>Withdrawn:</b> "premium 1.00, measured on 1,169,169 paired
    comparisons". It had already been written into the deck and had to come back
    out.</p>
  </div>
""")

# --- 3d direction
W("""  <div class="card">
    <h3>Pass three &mdash; hold the calendar still instead</h3>
    <p class="cap" style="margin-top:6px">Every row is bill month 140406, so no
    month effect can survive. What is controlled instead is <i>who</i> gets a
    raised bill: the comparison is made inside narrow strata of how large the
    bill normally is and which way it was already moving.</p>
    <div class="svgbox">
""")
DW, DH = 790, 330
DL, DR, DT, DB = 196, 700, 18, 266
DMAX = 1.9
def dx(v): return DL + v / DMAX * (DR - DL)
W('    <svg viewBox="0 0 %d %d" role="img" aria-label="premium by prior direction and shock size">\n' % (DW, DH))
for t in (0.5, 1.0, 1.5):
    W('      <line class="gl" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>\n' % (dx(t), DT, dx(t), DB))
    W('      <text class="tk" x="%.1f" y="%d" text-anchor="middle">%s&times;</text>\n' % (dx(t), DB+17, t))
W('      <line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--ink-3)" stroke-width="1.5" stroke-dasharray="4 3"/>\n'
  % (dx(1.0), DT, dx(1.0), DB+4))
bh2, grp = 20, 16
rows = S1011 + [("Pooled", S1011_POOLED[0], S1011_POOLED[1])]
for i, (nm, a, b) in enumerate(rows):
    y = DT + 10 + i * (2*bh2 + 4 + grp)
    if nm == "Pooled":
        W('      <line class="ax" x1="%d" y1="%.1f" x2="%d" y2="%.1f"/>\n' % (DL-96, y-10, DR, y-10))
    W('      <text class="an" x="%d" y="%.1f" text-anchor="end" fill="%s">%s</text>\n'
      % (DL-12, y+bh2+4, "var(--ink)" if nm == "Pooled" else "var(--ink-2)", nm))
    for j, (v, col, lab) in enumerate([(a, "var(--s1)", "rose up to 2x"), (b, "var(--s2)", "rose 2x or more")]):
        yy = y + j * (bh2 + 4)
        W('        <rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="2" fill="%s">'
          '<title>%s, %s: %s</title></rect>\n'
          % (dx(0), yy, max(dx(v)-dx(0), 2), bh2, col, nm, lab, "{:.3f}".format(v)))
        W('        <text class="dl" x="%.1f" y="%.1f" fill="var(--ink)" style="font-size:11.5px">%s</text>\n'
          % (dx(v)+8, yy+bh2-5, "{:.3f}".format(v)))
W('      <line class="ax" x1="%.1f" y1="%d" x2="%d" y2="%d"/>\n' % (dx(0), DB, DR, DB))
W('      <text class="tk" x="%.1f" y="%d">bar rate relative to a bill in its normal range</text>\n' % (dx(0), DB+40))
W('    </svg>\n    </div>\n')
W("""    <div class="legend">
      <span><i style="background:var(--s1)"></i>the bill rose by up to 2&times;</span>
      <span><i style="background:var(--s2)"></i>the bill rose by 2&times; or more</span>
    </div>
    <p class="cap"><b>A large rise matters, and it matters most to subscribers
    whose bill was already climbing.</b> For someone whose bill had been
    falling, a doubled month is a return to normal and carries no excess risk
    at all; for someone already on the way up it runs 1.668. The risk is in
    sustained escalation, not in one large bill. These figures are still
    understated: they were measured before the reference band was cleaned.</p>
  </div>
""")

# --- 3e corrected
W("""  <div class="card">
    <h3>Pass four &mdash; the corrected run</h3>
    <p class="cap" style="margin-top:6px">Two defects found in the query above,
    both biasing the premiums <i>down</i>.</p>
    <div class="split" style="margin-top:14px">
      <div class="panel unknown">
        <h3><span class="dot" style="background:var(--crit)"></span>The reference band held the worst cases</h3>
        <ul>
          <li>The control was <code>shock &lt; 1.25</code>, which swallowed every
          month where the bill <b>fell</b> &mdash; the riskiest months in the
          data, at %s pct against a normal %s pct.</li>
          <li>Fixed to <b>0.80&ndash;1.25</b>, with the falling months kept
          visible as a band of their own.</li>
        </ul>
      </div>
      <div class="panel unknown">
        <h3><span class="dot" style="background:var(--crit)"></span>A missing value was treated as a stratum</h3>
        <ul>
          <li><code>prior_trend IS NULL</code> means the first baseline month
          billed zero: a line that started or restarted inside the window, not
          a direction.</li>
          <li><b>%s of them</b>, barring at <b>%s pct</b> against %s pct for
          everyone else, and %s sat in the high-shock band because a bill
          appearing out of nothing reads as an enormous rise.</li>
        </ul>
      </div>
    </div>
    <div class="tbl-s" style="margin-top:16px"><table>
      <thead><tr><th>Band</th><th>Premium</th><th>95 pct interval</th></tr></thead>
      <tbody>
""" % (pct(S5[0][4]), pct(S5[1][4]), f(NEWLINE["n"]), "{:.3f}".format(NEWLINE["rate"]),
       "{:.3f}".format(NEWLINE["other_rate"]), f(73_789)))
for nm, v, lo2, hi2, _k in MH:
    ci = "&mdash;" if lo2 is None else ("%s &ndash; %s" % ("{:.3f}".format(lo2), "{:.3f}".format(hi2)))
    W('        <tr%s><td>%s</td><td><b>%s&times;</b></td><td>%s</td></tr>\n'
      % (' class="off"' if v == 1.0 else "", nm, "{:.3f}".format(v), ci))
W("""      </tbody>
      <tfoot><tr><td colspan="3">Mantel-Haenszel pooled over four bill-size bands
      and three prior-direction bands, one calendar month, new lines excluded.
      <b>%s defaults over %s million subscriber-months.</b> Crude and adjusted
      agree to three decimals (%s against %s) &mdash; <b>adjusting for month,
      bill size and prior direction moved the estimate from 1.97 to 1.91,
      essentially not at all.</b> That is itself the finding: the obvious
      confounders are not where the risk is. It does not prove causation;
      selection on something unobserved is still possible. The earlier interval
      of 0.30 to 12.09 was wrong, from summing per-stratum variances instead of
      using the Robins-Breslow-Greenland formula.</td></tr></tfoot>
    </table></div>
  </div>
""" % (f(MH_DEFAULTS), "{:.1f}".format(MH_MONTHS/1e6), "{:.3f}".format(MH_CRUDE),
       "{:.3f}".format(MH[3][1])))

# --- 3f by bill size + missing screen
W("""  <div class="split" style="margin-top:14px">
    <div class="panel">
      <h3>The premium falls as the bill grows</h3>
      <div class="tbl-s"><table>
        <thead><tr><th>Normal bill</th><th>Premium</th></tr></thead><tbody>
""")
for nm, v in BYSIZE:
    W('          <tr><td>%s</td><td><b>%s&times;</b></td></tr>\n' % (nm, "{:.2f}".format(v)))
W("""        </tbody>
        <tfoot><tr><td colspan="2">The reverse of the raw read, which had it the
        other way round because it was confounded by who gets a big bill. Above
        600,000 a month the rise carries no premium at all.</td></tr></tfoot>
      </table></div>
    </div>
    <div class="panel unknown">
      <h3><span class="dot" style="background:var(--crit)"></span>The screen nobody wrote</h3>
      <div class="tbl-s"><table>
        <thead><tr><th></th><th>n</th><th>Bars</th><th>Rate</th></tr></thead><tbody>
          <tr><td>A zero-billing month in the window</td><td>%s</td><td>%s</td><td><b>%s pct</b></td></tr>
          <tr><td>Everyone else</td><td>%s</td><td>%s</td><td>%s pct</td></tr>
        </tbody>
        <tfoot><tr><td colspan="4"><b>%s&times;.</b> New or restarted lines. The
        screen asks for revenue above the bar in 2 of 6 months, which a line
        that first appeared in month 4 satisfies, and nothing looks for the gap.
        Cheap to add, large effect, and it is card 06 in Part two.</td></tr></tfoot>
      </table></div>
    </div>
  </div>
</section>
""" % (f(NEWLINE["n"]), f(NEWLINE["bars"]), "{:.3f}".format(NEWLINE["rate"]),
       f(NEWLINE["other_n"]), f(NEWLINE["other_bars"]), "{:.3f}".format(NEWLINE["other_rate"]),
       "{:.1f}".format(NEWLINE["ratio"])))

# ================================================== 4. the model
W("""<section>
  <div class="head">
    <p class="eyebrow">Part four</p>
    <h2>What the model is, and what it is not yet</h2>
    <p>Everything below was fitted on the <b>four-month</b> label. It ranks
    well and it is honestly calibrated at the level. It has not been refit for
    the one-month product, and until it is, the pd column is not the DCB pd.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>Model</th><th>First run</th><th>After adding bar history</th><th>Gain</th></tr></thead>
      <tbody>
""")
for nm, a, b in AUC:
    cl = ' class="tot"' if nm.startswith("HistGB cal") else ""
    W('        <tr%s><td>%s</td><td>%s</td><td><b>%s</b></td><td>+%s</td></tr>\n'
      % (cl, nm, "{:.4f}".format(a), "{:.4f}".format(b), "{:.4f}".format(b-a)))
W("""      </tbody>
      <tfoot><tr><td colspan="4">The linear model gained twice what boosting did,
      because a prior bar is close to a straight additive signal. Removing the
      six pre_ columns costs <b>%s</b> of test AUC, which is 92 percent of what
      the refit bought. A <b>scale-free</b> variant &mdash; every Rial amount
      removed from the inputs &mdash; scores <b>%s</b>, costing 0.0048. Take
      that trade: scale-free features cannot drift with inflation, and twelve
      features in the full model already drift significantly.</td></tr></tfoot>
    </table></div>
  </div>
  <div class="card">
    <h3>Calibration is conservative exactly where the book is drawn</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>Decile group</th><th>Predicted</th><th>Observed</th><th>Ratio</th></tr></thead>
      <tbody>
""" % ("{:.4f}".format(PRE_GAIN), "{:.4f}".format(SCALEFREE)))
for nm, p, o, r in CALIB:
    W('        <tr><td>%s</td><td>%s pct</td><td>%s pct</td><td><b>%s</b></td></tr>\n'
      % (nm, pct(p), pct(o), "{:.3f}".format(r)))
W("""      </tbody>
      <tfoot><tr><td colspan="4">Level error is 1.68 percent, which is tight for
      a 0.5 percent event. But the model <b>over-predicts risk in the safest
      deciles</b>, which is where the book comes from. The error runs in the
      safe direction, so realised loss should land at or under the quoted
      figure &mdash; state it that way rather than quoting a point estimate.
      Observed risk is monotone across all ten deciles, so the <b>ranking</b>,
      which is what the book is cut on, is sound. The live set scores a mean pd
      of %s pct against TEST's observed %s pct, +15.7 percent: that is drift
      showing up in the level, not the ranking. <b>Trust the order, not the
      number.</b></td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (pct(DRIFT_LIVE), pct(DRIFT_TEST)))

# ================================================== 5. open
W("""<section>
  <div class="head">
    <p class="eyebrow">Part five</p>
    <h2>What is still open</h2>
    <p>Listed so that nothing on this page is read as more settled than it is.</p>
  </div>
  <div class="card">
    <div class="ask">
      <div class="q"><span class="n">01</span><div class="b">
        <h3>The model has not been refit on the one-month label</h3>
        <p>42_model_datasets.sql now builds the DCB calendar and the one-month
        rate is measured, but the notebook has not been run against it. Until
        it is, every pd on the deck is a four-month pd and the scenario cards
        here carry arithmetic instead of scores.</p></div></div>
      <div class="q"><span class="n">02</span><div class="b">
        <h3>Nobody in the data ever held credit</h3>
        <p>The largest unknown on the page, and the only thing that answers it
        is a capped pilot. A one-month term means the answer arrives in weeks
        rather than a year.</p></div></div>
      <div class="q"><span class="n">03</span><div class="b">
        <h3>Capping the draw below one month's bill shrinks limits for light billers</h3>
        <p>The rule is right on risk and the volume consequence is unmeasured.
        It needs the billing distribution of the scored set, which is a query
        rather than an assumption.</p></div></div>
      <div class="q"><span class="n">04</span><div class="b">
        <h3>The substitution share</h3>
        <p>Whether DCB spending replaces what a subscriber already buys or adds
        to it is unknown, and it decides whether the bill actually rises by the
        full draw. Everything on this page assumes it adds, which is the
        pessimistic reading.</p></div></div>
    </div>
  </div>
</section>

<footer>
  <span>Sources, in order of appearance: 42_model_datasets.sql (screen, windows,
  pre-window bar history), 52_one_month_label_choice.sql (the one-month rate and
  the coverage bands), 53_bill_shock.sql S1&ndash;S11 (every shock figure),
  train_model.ipynb and validate_model.ipynb (AUC, calibration, drift).</span>
  <span>All amounts in Toman; the database stores Rial and every figure here is
  the Rial value divided by ten. The nine profiles in Part two are constructed
  illustrations and are not individual subscribers.</span>
</footer>
</div>
""")

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_workbook.html"), "w", encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()), "bytes")

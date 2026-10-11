# -*- coding: utf-8 -*-
"""The manager dashboard in Persian, RTL, ready to present.

Same numbers as gen_dcb_manager.py - the model's grade mix from the refit.
The stylesheet is NOT shared with the Latin pages: Persian script connects,
so the letter-spacing those pages use on labels would break the joins, and
the line-height has to be looser for the descenders.
"""
import io, os, sys

# ---- the model's grade mix. pd is the FOUR-MONTH probability the model was
#      fitted on; it sets the ranking and the limit.
GRADES = [("A", 3_029_397, 0.001417, 400_000, "کم‌ریسک‌ترین"),
          ("B", 4_087_448, 0.003298, 300_000, ""),
          ("C", 1_085_787, 0.007387, 150_000, ""),
          ("D",   599_140, 0.013538, 100_000, ""),
          ("E",   542_951, 0.040000,       0, "رد می‌شود")]
SCORED   = 9_344_723
APPROVED = sum(g[1] for g in GRADES if g[3] > 0)
DECLINED = SCORED - APPROVED
OUTSTAND = sum(g[1] * g[3] for g in GRADES)
AVG_LIM  = OUTSTAND / APPROVED
CYCLES   = 12
ANNUAL   = OUTSTAND * CYCLES / 1e9
LOSS_LO, LOSS_HI = 0.0009, 0.0014
TARGET_BN = 15_000.0
AUC = 0.8278

FUNNEL = [("همه مشترکین دائمی", "نقطه شروع", 41_270_092, None),
          ("قبض‌شان آن‌قدر هست که وام را تحمل کند",
           "حداقل ۱۷۰٬۰۰۰ تومان در ۲ ماه از ۶ ماه", 10_087_975,
           "در هیچ دو ماهی ۱۷۰٬۰۰۰ تومان قبض نداشته‌اند"),
          ("هیچ‌وقت قطع یک‌طرفه نشده‌اند", "در تمام شش ماه", 9_437_240,
           "سرویس خروجی‌شان قطع شده بود"),
          ("هیچ‌وقت قطع دوطرفه نشده‌اند", "در تمام شش ماه", 9_344_723,
           "سرویس ورودی‌شان قطع شده بود"),
          ("امتیازشان برای وام‌دهی کافی است", "مدل پرریسک‌ترین رتبه را رد می‌کند",
           APPROVED, "در پرریسک‌ترین رتبه امتیاز گرفته‌اند")]

SHOCK = [("قبض تقریباً تکان نمی‌خورد", "کمتر از ۱٫۲۵ برابر", 1.000),
         ("بالا می‌رود، اما به دو برابر نمی‌رسد", "۱٫۲۵ تا ۲٫۰۰ برابر", 1.133),
         ("دو برابر یا بیشتر می‌شود", "۲٫۰۰ برابر و بالاتر", 1.907)]

STRESS = [("مطابق مدل", 1.00), ("با رانش جمعیت فعلی", 1.157),
          ("وام‌دهی در آستانه نوروز", 1.68), ("دو برابر نرخ مدل", 2.00)]

# Latin digits with a comma separator, which is what Iranian financial
# reporting uses. Set PERSIAN_DIGITS = True for Eastern Arabic numerals.
PERSIAN_DIGITS = True
_FA = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹",
       ",":"٬", ".":"٫"}
def _d(t):
    if not PERSIAN_DIGITS: return t
    return "".join(_FA.get(c, c) for c in t)
# <bdi> isolates a Latin number inside RTL prose so the digits, the comma and
# any adjacent punctuation do not get reordered by the bidi algorithm.
def f(n):    return "<bdi>" + _d("{:,}".format(int(round(n)))) + "</bdi>"
def one(x):  return "<bdi>" + _d("{:.1f}".format(x)) + "</bdi>"
def two(x):  return "<bdi>" + _d("{:.2f}".format(x)) + "</bdi>"
def bnf(x):  return "<bdi>" + _d("{:,.1f}".format(x)) + "</bdi>"
def pc(a,b): return "<bdi>" + _d("{:.0f}".format(100.0*a/b)) + "</bdi>"
def z(t):    return "<bdi>" + _d(t) + "</bdi>"

RISKW = [(g[0], g[1]*g[3]*g[2]) for g in GRADES if g[3] > 0]
RISKT = sum(w for _, w in RISKW)
LOSS_MID = ANNUAL * (LOSS_LO + LOSS_HI) / 2

out = io.StringIO(); W = out.write

W("""<title>اعتبار روی قبض</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* A Persian presentation surface. Same palette as the Latin pages; the
   typography is rebuilt, because Persian script connects and the Latin
   pages space their labels apart. */
:root{
  --plane:#f6f6f3; --surface:#fdfdfc; --raise:#eeeeea; --sunk:#e6e6e0;
  --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.09); --grid:#e1e0d9; --axis:#c3c2b7;
  --s1:#2a78d6; --s2:#eb6834;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --fa:"Vazirmatn","Noto Sans Arabic",Tahoma,"Iranian Sans",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}
*{box-sizing:border-box}
body{background:var(--plane);color:var(--ink);font-family:var(--fa);
  font-size:16px;line-height:1.85;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding-inline:22px;padding-block:36px 72px}
h1,h2,h3{margin:0;text-wrap:balance;line-height:1.5}
h1{font-size:clamp(27px,5vw,42px);font-weight:700}
h2{font-size:clamp(20px,3.2vw,26px);font-weight:700}
h3{font-size:16px;font-weight:600}
p{margin:0}
/* Latin digits inside Persian prose: isolate them so the bidi algorithm
   cannot reorder a number, its comma and the word beside it. */
bdi{font-family:inherit;font-variant-numeric:tabular-nums;unicode-bidi:isolate}
/* NO letter-spacing and NO uppercase anywhere: Persian letters join, and
   spacing them apart breaks the word into disconnected shapes. */
.eyebrow{font-size:13px;font-weight:500;color:var(--ink-3)}

header{display:flex;flex-direction:column;gap:14px;padding-bottom:10px}
.lede{color:var(--ink-2);font-size:17px;max-width:62ch}
.spec{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.chip{font-size:13.5px;background:var(--raise);border:1px solid var(--rule);
  border-radius:999px;padding:5px 14px;color:var(--ink-2)}
.chip b{color:var(--ink);font-weight:600}

section{margin-top:40px}
.head{border-top:2px solid var(--ink);padding-top:14px;margin-bottom:18px;
  display:flex;flex-direction:column;gap:7px}
.head p{color:var(--ink-2);font-size:15px;max-width:64ch}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:22px 20px}
.card + .card{margin-top:14px}
.cap{color:var(--ink-3);font-size:13.5px;line-height:1.85;margin-top:16px;max-width:70ch}
.cap b{color:var(--ink-2);font-weight:600}

.kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:8px;overflow:hidden}
@media (max-width:760px){.kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{background:var(--surface);padding:16px 17px 18px;display:flex;flex-direction:column;gap:6px}
.tile .k{font-size:12.5px;color:var(--ink-3);line-height:1.5}
.tile .v{font-size:clamp(20px,3.2vw,26px);font-weight:600;line-height:1.3}
.tile .v bdi{font-weight:600}
.tile .s{font-size:12.5px;color:var(--ink-3);line-height:1.6}

table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:480px}
.tbl-s{overflow-x:auto;margin-top:6px}
/* logical alignment, so the label column sits at the start in either direction */
th,td{text-align:end;padding:11px 12px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:start;white-space:normal}
thead th{font-size:12.5px;color:var(--ink-3);font-weight:500;
  border-bottom:1px solid var(--axis)}
tbody td{color:var(--ink-2)}
tbody td:first-child{color:var(--ink);font-weight:500}
tr.off td{color:var(--ink-3)}
tr.tot td{font-weight:700;color:var(--ink);border-top:1px solid var(--axis);border-bottom:none}
tfoot td{font-size:13.5px;color:var(--ink-3);white-space:normal;
  text-align:start;border-bottom:none;padding-top:14px;line-height:1.85}
tfoot b{color:var(--ink-2);font-weight:600}

.fun{display:flex;flex-direction:column;gap:3px}
.fstep{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:center;
  padding:12px 15px;border-radius:6px;background:var(--raise);min-width:0}
.fstep.keep{background:color-mix(in srgb,var(--s1) 14%,var(--surface))}
.fstep.last{background:color-mix(in srgb,var(--good) 16%,var(--surface))}
.fstep .t{font-size:15px;color:var(--ink);min-width:0}
.fstep .t em{font-style:normal;display:block;color:var(--ink-3);font-size:13px;margin-top:1px}
.fstep .v{font-size:18px;font-weight:700;white-space:nowrap}
.fdrop{display:grid;grid-template-columns:1fr auto;gap:14px;
  padding-block:5px;padding-inline-start:30px;padding-inline-end:15px;
  font-size:13px;color:var(--ink-3)}
.fdrop .v{white-space:nowrap}

.rule{display:flex;flex-wrap:wrap;gap:20px 36px;align-items:center;
  background:color-mix(in srgb,var(--good) 11%,var(--surface));
  border:1px solid color-mix(in srgb,var(--good) 40%,var(--rule));
  border-radius:8px;padding:26px 24px}
.rule .big{font-size:clamp(20px,3.4vw,27px);font-weight:700;line-height:1.6;
  flex:1 1 300px;min-width:0;text-wrap:balance}
.rule .why{font-size:14.5px;color:var(--ink-2);line-height:1.9;flex:1 1 280px;min-width:0}

.steps{display:flex;flex-direction:column;gap:0;margin-top:4px}
.stp{display:grid;grid-template-columns:30px 1fr;gap:14px;padding:16px 0;
  border-bottom:1px solid var(--rule)}
.stp:last-child{border-bottom:none}
.stp .n{font-family:var(--mono);font-size:15px;font-weight:600;color:var(--s1)}
.stp h3{margin-bottom:4px}
.stp p{font-size:14.5px;color:var(--ink-2);line-height:1.9}

.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.split{grid-template-columns:1fr}}
.split > *{min-width:0}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:20px 18px}
.panel.unknown{border-inline-start:3px solid var(--crit)}
.panel h3{display:flex;align-items:center;gap:9px;margin-bottom:12px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;background:var(--crit)}
.panel ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
.panel li{font-size:14.5px;color:var(--ink-2);line-height:1.9;
  padding-inline-start:16px;position:relative}
.panel li::before{content:"";position:absolute;inset-inline-start:0;top:12px;
  width:7px;height:1.5px;background:var(--ink-3)}
.panel li b{color:var(--ink);font-weight:600}
.gr{font-family:var(--mono);font-weight:600}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);
  color:var(--ink-3);font-size:13px;display:flex;flex-direction:column;gap:8px;line-height:1.85}
a{color:var(--s1)}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap" dir="rtl" lang="fa">
""")

# ------------------------------------------------------------------ header
W("""<header>
  <p class="eyebrow">اعتبار روی قبض &middot; آنچه هست و آنچه هزینه دارد</p>
  <h1>وام‌دادن به مشترک روی قبض ماه بعدش</h1>
  <p class="lede">مشترک روی قبض تلفن همراهش اعتبار می‌گیرد و در قبض ماه بعد
  بازپرداخت می‌کند. هر مشترک امتیازدهی می‌شود، سقف اعتبارش متناسب با امتیازش
  تعیین می‌شود، و پرریسک‌ترین‌ها رد می‌شوند.</p>
  <div class="spec">
    <span class="chip">دوره بازپرداخت <b>یک ماه</b></span>
    <span class="chip">سقف اعتبار <b>%s تا %s تومان</b></span>
    <span class="chip">تأییدشده <b>%s</b></span>
    <span class="chip">همه مبالغ <b>تومان</b></span>
  </div>
</header>

<div class="kpi" style="margin-top:26px">
  <div class="tile"><span class="k">مشترکین تأییدشده</span><span class="v">%s</span>
    <span class="s">%s درصد از کل امتیازدهی‌شده‌ها</span></div>
  <div class="tile"><span class="k">میانگین سقف اعتبار</span><span class="v">%s</span>
    <span class="s">بر اساس امتیاز خود مشترک</span></div>
  <div class="tile"><span class="k">اعطایی در یک سال</span><span class="v">%s میلیارد</span>
    <span class="s">%s درصد از هدف ۱۵٬۰۰۰ میلیاردی</span></div>
  <div class="tile"><span class="k">زیان مورد انتظار</span><span class="v">%s&ndash;%s میلیارد</span>
    <span class="s">در سال، با فرض اینکه هیچ وصولی نداشته باشیم</span></div>
</div>
<p class="cap">در هر لحظه فقط <b>%s میلیارد تومان</b> نزد مشترکین است؛
همان پول دوازده بار در سال برمی‌گردد و دوباره اعطا می‌شود.</p>
""" % (f(100_000), f(400_000), f(APPROVED), f(APPROVED), pc(APPROVED, SCORED),
       f(AVG_LIM), f(ANNUAL), pc(ANNUAL, TARGET_BN),
       one(ANNUAL*LOSS_LO), one(ANNUAL*LOSS_HI), bnf(OUTSTAND/1e9)))

# ------------------------------------------------------------------ funnel
W("""<section>
  <div class="head">
    <h2>چه کسانی واجد شرایط‌اند</h2>
    <p>چهار بررسی روی سابقه شش ماه گذشته، و بعد امتیاز مدل.</p>
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
    <p class="cap"><b>بررسی اول تقریباً تمام کار را انجام می‌دهد</b> و
    %s مشترک را کنار می‌گذارد. امتیاز مدل فقط %s نفر دیگر را حذف می‌کند.</p>
  </div>
</section>
""" % (f(41_270_092 - 10_087_975), f(DECLINED)))

# ------------------------------------------------------------------ grades
W("""<section>
  <div class="head">
    <h2>سقف اعتبار هر مشترک</h2>
    <p>رتبه، سقف اعتبار را تعیین می‌کند. کم‌ریسک‌ترین‌ها بیشترین سقف را
    می‌گیرند.</p>
  </div>
  <div class="card">
    <div class="tbl-s"><table>
      <thead><tr><th>رتبه</th><th>مشترکین</th><th>سقف اعتبار</th><th>احتمال نکول ۴ ماهه</th>
      <th>مانده در هر لحظه</th><th>سهم از زیان</th></tr></thead>
      <tbody>
""")
for name, n, pd, lim, note in GRADES:
    if lim == 0:
        W('        <tr class="off"><td><span class="gr">%s</span> &mdash; %s</td><td>%s</td>'
          '<td>رد می‌شود</td><td>%s درصد</td><td>&mdash;</td><td>&mdash;</td></tr>\n'
          % (name, note, f(n), two(pd*100)))
        continue
    share = dict(RISKW)[name] / RISKT
    W('        <tr><td><span class="gr">%s</span>%s</td><td>%s</td><td>%s</td>'
      '<td>%s درصد</td><td>%s میلیارد</td><td><b>%s درصد</b></td></tr>\n'
      % (name, (" &mdash; " + note) if note else "", f(n), f(lim), two(pd*100),
         bnf(n*lim/1e9), z("{:.0f}".format(100*share))))
W("""        <tr class="tot"><td>مجموع تأییدشده</td><td><b>%s</b></td>
            <td>میانگین %s</td><td></td><td><b>%s میلیارد</b></td>
            <td>۱۰۰ درصد</td></tr>
      </tbody>
      <tfoot><tr><td colspan="6"><b>رتبه B نیمی از کل زیان را به دوش می‌کشد</b>،
      در حالی که دومین گروه کم‌ریسک است: بزرگ‌ترین گروه است و سقف ۳۰۰٬۰۰۰ تومانی
      می‌گیرد.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (f(APPROVED), f(AVG_LIM), bnf(OUTSTAND/1e9)))

# ------------------------------------------------------------- bill shock
W("""<section>
  <div class="head">
    <h2>یک قاعده که سقف‌ها باید رعایتش کنند</h2>
    <p>اعتبار روی قبض ماه بعد می‌نشیند. اینکه قبض چقدر بالا بپرد، احتمال
    نکول را تعیین می‌کند.</p>
  </div>
  <div class="rule">
    <div class="big">هرگز بیشتر از قبض یک ماه مشترک به او وام ندهید.</div>
    <div class="why">زیر این خط، قبض کمتر از دو برابر بالا می‌رود و مشترک با
    نرخ عادی پرداخت می‌کند. روی این خط یا بالاتر، قبض دو برابر می‌شود و
    <b>احتمال نکول %s برابر</b> است.</div>
  </div>
  <div class="card" style="margin-top:14px">
    <div class="tbl-s"><table>
      <thead><tr><th>چه بر سر قبض مشترک می‌آید</th><th>چقدر بالا می‌رود</th>
      <th>نرخ بازماندن از پرداخت</th></tr></thead>
      <tbody>
""" % one(SHOCK[2][2] / SHOCK[1][2]))
for nm, rng, v in SHOCK:
    cls = ' class="tot"' if v > 1.5 else (' class="off"' if v == 1.0 else "")
    lab = "نرخ عادی" if v == 1.0 else ("%s برابر" % two(v))
    W('        <tr%s><td>%s</td><td>%s</td><td><b>%s</b></td></tr>\n' % (cls, nm, rng, lab))
W("""      </tbody>
      <tfoot><tr><td colspan="3">اندازه‌گیری‌شده روی %s میلیون مشترک‑ماه.
      جدول سقف‌ها این قاعده را از قبل رعایت می‌کند.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % z("4.0"))

# ------------------------------------------------------------- what it costs
W("""<section>
  <div class="head">
    <h2>هزینه محتمل طرح</h2>
    <p>مرحله به مرحله، تا بشود روی هر قدمش بحث کرد.</p>
  </div>
  <div class="card">
    <div class="steps">
      <div class="stp"><span class="n">۱</span><div>
        <h3>%s مشترک به‌طور میانگین %s تومان وام می‌گیرند</h3>
        <p>در هر لحظه <b>%s میلیارد تومان</b> نزد مشترکین است، و در طول یک
        سال <b>%s میلیارد تومان</b> اعطا می‌شود.</p></div></div>
      <div class="stp"><span class="n">۲</span><div>
        <h3>نرخ نکول یک‌ماهه بین ۰٫۰۹ تا ۰٫۱۴ درصد است</h3>
        <p>این بازه یک انتخاب است، نه عدم‌قطعیت: کف بازه یعنی وام فقط به
        کم‌ریسک‌ترین‌ها، سقف بازه یعنی وام به همه تأییدشده‌ها.</p></div></div>
      <div class="stp"><span class="n">۳</span><div>
        <h3>پس سالانه %s تا %s میلیارد تومان زیان می‌دهیم</h3>
        <p>با فرض <b>هیچ وصولی</b> از مشترک نکول‌کرده، که عمداً بدبینانه است.
        در برابر %s میلیارد تومان اعطایی، نقطه میانی حدود <b>۰٫۱۲ درصد</b>
        است.</p></div></div>
    </div>
  </div>
  <div class="card">
    <h3>اگر زیان بدتر از مدل دربیاید</h3>
    <div class="tbl-s"><table>
      <thead><tr><th>سناریو</th><th>ضریب</th><th>زیان سالانه</th>
      <th>نسبت به %s میلیارد اعطایی</th></tr></thead>
      <tbody>
""" % (f(APPROVED), f(AVG_LIM), bnf(OUTSTAND/1e9), f(ANNUAL),
       one(ANNUAL*LOSS_LO), one(ANNUAL*LOSS_HI), f(ANNUAL), f(ANNUAL)))
for nm, m in STRESS:
    cls = ' class="tot"' if m == 1.00 else ""
    W('        <tr%s><td>%s</td><td>%s&times;</td><td>%s میلیارد</td><td>%s درصد</td></tr>\n'
      % (cls, nm, two(m), one(LOSS_MID*m), two(100*LOSS_MID*m/ANNUAL)))
W("""      </tbody>
      <tfoot><tr><td colspan="4">حتی با <b>دو برابر</b> نرخ مدل، زیان زیر
      <b>%s میلیارد تومان</b> روی <b>%s میلیارد تومان</b> اعطایی می‌ماند.</td></tr></tfoot>
    </table></div>
  </div>
</section>
""" % (one(LOSS_MID*2), f(ANNUAL)))

# ------------------------------------------------------------- open
W("""<section>
  <div class="head">
    <h2>آنچه هنوز نمی‌دانیم</h2>
    <p>دو مورد که هنوز باز است.</p>
  </div>
  <div class="split">
    <div class="panel unknown">
      <h3><span class="dot"></span>هیچ مشترکی در این داده‌ها تا به حال اعتبار نگرفته است</h3>
      <ul>
        <li>امتیاز مدل رفتار مشترک را وقتی <b>وام نگرفته</b> توصیف می‌کند.</li>
        <li><b>تنها راه پاسخ، یک اجرای آزمایشی محدود است</b>؛ با دوره یک‌ماهه
        جواب ظرف چند هفته می‌رسد.</li>
      </ul>
    </div>
    <div class="panel unknown">
      <h3><span class="dot"></span>هدف ۱۵٬۰۰۰ میلیاردی، اعطای سالانه است یا مانده؟</h3>
      <ul>
        <li>با گردش ماهانه این دو عدد دوازده برابر فرق دارند.</li>
        <li><b>اعطای سالانه:</b> %s میلیارد، بیش از دو برابر هدف.
        <b>مانده در هر لحظه:</b> %s میلیارد، با فاصله زیاد تا هدف.</li>
      </ul>
    </div>
  </div>
</section>

<footer>
  <span>تعداد مشترکین از سوابق صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶. رتبه‌ها، سقف‌ها و
  احتمال نکول از مدل امتیازدهی ۱۴۰۵/۰۷/۱۴ با شاخص دقت %s. ارقام شوک قبض روی
  %s میلیون مشترک‑ماه.</span>
  <span>همه مبالغ به تومان. احتمال نکول ۴ ماهه از افق مدل می‌آید؛ ارقام ریالی
  بر پایه نرخ یک‌ماهه محاسبه شده‌اند.</span>
</footer>
</div>
""" % (f(ANNUAL), bnf(OUTSTAND/1e9), z("{:.4f}".format(AUC)), z("4.0")))

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_manager_fa.html"), "w", encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()), "bytes")

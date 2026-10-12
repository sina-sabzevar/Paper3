# -*- coding: utf-8 -*-
"""One executive slide: the scoring method, how many customers, three options
across three limit bands, and participation in one strip.

Sized to a single 16:9 screen. Type scales with vmin so it fills a projector
and still reads on a laptop; below 820px it falls back to a scrolling column.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- the model's decile ladder, with the riskiest decile split at today's
#      grade boundary so the base is the 8,801,772 the business approves now
LAD = [(934_472,0.000941),(1_868_944,0.001527),(2_803_416,0.001684),
       (3_737_889,0.002104),(4_672_361,0.002694),(5_606_833,0.003146),
       (6_541_306,0.004060),(7_475_778,0.005180),(8_410_250,0.008571),
       (9_344_723,0.029613)]
DEC = [(LAD[i][0]-(LAD[i-1][0] if i else 0), LAD[i][1]) for i in range(10)]
GRADE_E, APPROVED = 542_951, 8_801_772
RISKY_N  = APPROVED - 8_410_250
RISKY_PD = (DEC[9][0]*DEC[9][1] - GRADE_E*0.040) / RISKY_N
BANDS    = DEC[:9] + [(RISKY_N, RISKY_PD)]

SCORED, BASE, AUC = 9_344_723, 41_270_092, 0.8278
TARGET = 15_000.0
# representative limit per band, used for every money figure
MID   = {1: 200_000, 2: 400_000, 3: 750_000}
LABEL = {1: "۱۰۰ تا ۳۰۰ هزار", 2: "۳۰۰ تا ۵۰۰ هزار", 3: "۵۰۰ هزار تا ۱ میلیون"}
# which band each of the ten groups falls in, safest group first
OPT = [("کم‌ریسک",  "سقف‌ها پایین، تمرکز روی باند اول",
        [2,2,1,1,1,1,1,1,1,1]),
       ("محتاطانه", "یک دهک در باند بالا",
        [3,2,2,2,1,1,1,1,1,1]),
       ("گسترده",   "سه دهک در باند بالا",
        [3,3,3,2,2,2,2,1,1,1])]
TAKE = [0.10, 0.20, 0.30, 0.40]
# 56 D3: how many customers bill enough to carry each draw under the rule
CARRY = {200_000: 3_013_027, 300_000: 1_455_303, 500_000: 369_677}

def metrics(assign):
    cnt = {1:0, 2:0, 3:0}
    for i, b in enumerate(assign): cnt[b] += BANDS[i][0]
    out  = sum(BANDS[i][0]*MID[assign[i]] for i in range(10))
    pd1  = sum(BANDS[i][0]*MID[assign[i]]*BANDS[i][1] for i in range(10))/out/3.0
    ann  = out*12/1e9
    assert sum(cnt.values()) == APPROVED
    return dict(cnt=cnt, out=out/1e9, ann=ann, pd1=pd1, loss=ann*pd1)

MET = [metrics(a) for _, _, a in OPT]

_FA = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹",
       ",":"٬", ".":"٫"}
def fa(t):  return "".join(_FA.get(c, c) for c in str(t))
def f(n):   return fa("{:,}".format(int(round(n))))
def mi(n):  return fa("{:.1f}".format(n/1e6))          # in millions
def d1(x):  return fa("{:.1f}".format(x))
def d3(x):  return fa("{:.3f}".format(x))

out = io.StringIO(); W = out.write

W("""<title>سه گزینه اعطای اعتبار</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap">
<style>
/* One slide. Everything is sized from --u, a vmin-based unit, so the whole
   thing scales with the screen instead of being laid out at one size. */
:root{
  --plane:#ffffff; --panel:#f6f6f3; --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.10); --line:#e2e1db;
  --s1:#2a78d6; --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --fa:"Vazirmatn","Noto Sans Arabic",Tahoma,system-ui,sans-serif;
  --u:clamp(9px, 1.34vmin, 20px);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0e0e10; --panel:#191a1d; --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.12); --line:#2c2c2a;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0e0e10; --panel:#191a1d; --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.12); --line:#2c2c2a;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--plane);color:var(--ink);font-family:var(--fa);
  -webkit-font-smoothing:antialiased}
.slide{min-height:100%;display:flex;flex-direction:column;
  justify-content:space-between;gap:calc(var(--u)*1.25);padding:calc(var(--u)*2.2) calc(var(--u)*3);direction:rtl}

.hd{display:flex;align-items:baseline;justify-content:space-between;gap:calc(var(--u)*2);
  border-bottom:2px solid var(--ink);padding-bottom:calc(var(--u)*1.1)}
.hd h1{margin:0;font-size:calc(var(--u)*2.5);font-weight:700;letter-spacing:-0.01em}
.hd .sub{font-size:calc(var(--u)*1.15);color:var(--ink-3);white-space:nowrap}

/* the method, as one line of steps */
.flow{display:flex;align-items:stretch;gap:calc(var(--u)*0.7)}
.fx{flex:1 1 0;background:var(--panel);border:1px solid var(--rule);
  border-radius:calc(var(--u)*0.6);padding:calc(var(--u)*0.95) calc(var(--u)*1.1);
  display:flex;flex-direction:column;gap:calc(var(--u)*0.2);min-width:0}
.fx.on{background:color-mix(in srgb,var(--s1) 12%,var(--panel));border-color:color-mix(in srgb,var(--s1) 38%,var(--rule))}
.fx .n{font-size:calc(var(--u)*1.9);font-weight:700;line-height:1.15;white-space:nowrap}
.fx .t{font-size:calc(var(--u)*1.05);color:var(--ink-2);line-height:1.5}
.note{font-size:calc(var(--u)*1.02);color:var(--ink-3);line-height:1.62;margin:0}
.note b{color:var(--ink-2)}

/* the matrix */
table{width:100%;border-collapse:collapse;font-size:calc(var(--u)*1.25)}
th,td{padding:calc(var(--u)*0.66) calc(var(--u)*0.8);text-align:center;
  border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:start;white-space:normal}
thead th{font-size:calc(var(--u)*1.0);font-weight:500;color:var(--ink-3);
  border-bottom:1px solid var(--ink-3);line-height:1.45;white-space:normal}
tbody td{color:var(--ink-2)}
tbody tr td:first-child{color:var(--ink)}
.on1{font-size:calc(var(--u)*1.55);font-weight:700;color:var(--ink)}
.opt{font-size:calc(var(--u)*1.45);font-weight:700}
.opt em{display:block;font-style:normal;font-size:calc(var(--u)*0.98);
  font-weight:400;color:var(--ink-3);margin-top:calc(var(--u)*0.1)}
.band3{background:color-mix(in srgb,var(--crit) 9%,transparent)}
tbody tr:last-child td{border-bottom:none}

/* participation */
.two{display:grid;grid-template-columns:1.35fr 1fr;gap:calc(var(--u)*1.4);align-items:start}
.box{background:var(--panel);border:1px solid var(--rule);border-radius:calc(var(--u)*0.6);
  padding:calc(var(--u)*1.1) calc(var(--u)*1.3)}
.box h2{margin:0 0 calc(var(--u)*0.65);font-size:calc(var(--u)*1.2);font-weight:600;color:var(--ink-2)}
.box table{font-size:calc(var(--u)*1.1)}
.box th,.box td{padding:calc(var(--u)*0.42) calc(var(--u)*0.5);border-bottom:1px solid var(--line)}
.box tbody tr:last-child td{border-bottom:none}
.flag{border-inline-start:calc(var(--u)*0.3) solid var(--crit)}
.flag h2{color:var(--crit)}
.flag p{margin:0;font-size:calc(var(--u)*1.1);color:var(--ink-2);line-height:1.75}
.flag b{color:var(--ink)}
.ft{padding-top:calc(var(--u)*0.9);border-top:1px solid var(--rule);
  font-size:calc(var(--u)*0.95);color:var(--ink-3);line-height:1.6}

@media (max-width:820px){
  :root{--u:12px}
  html,body{height:auto}
  .slide{min-height:0;padding:20px 16px}
  .flow{flex-wrap:wrap}.fx{flex:1 1 45%}
  .two{grid-template-columns:1fr}
}
</style>

<div class="slide">
""")

# ----------------------------------------------------------------- header
W("""  <div class="hd">
    <h1>روش امتیازدهی و سه گزینه اعطای اعتبار</h1>
    <span class="sub">اعتبار روی قبض &middot; یک ماهه &middot; مهر ۱۴۰۵</span>
  </div>
""")

# ----------------------------------------------------------------- method
STEPS = [(mi(BASE) + " میلیون", "مشترک دائمی", False),
         (mi(SCORED) + " میلیون", "پس از غربال درآمد و سابقه قطعی", False),
         ("۳۹ ویژگی", "درآمد، پرداخت، سابقه قطعی، سابقه سال قبل", False),
         (f(APPROVED), "تأییدشده برای اعطای اعتبار", True)]
W('  <div class="flow">\n')
for n, t, on in STEPS:
    W('    <div class="fx%s"><span class="n">%s</span><span class="t">%s</span></div>\n'
      % (" on" if on else "", n, t))
W("""  </div>
  <p class="note">مدل به هر مشترک یک امتیاز می‌دهد و آن‌ها را از کم‌ریسک به پرریسک
  مرتب می‌کند. دقت مدل روی داده آزمون <b>%s</b> است. سقف اعتبار از روی همین ترتیب
  تعیین می‌شود &mdash; سه گزینه زیر فقط در این تعیین سقف با هم فرق دارند.</p>
""" % fa("{:.2f}".format(AUC)))

# ----------------------------------------------------------------- matrix
W("""  <table>
    <thead><tr>
      <th>گزینه</th><th>%s<br>تومان</th><th>%s<br>تومان</th><th>%s<br>تومان</th>
      <th>اعطایی در یک سال<br>میلیارد تومان</th>
      <th>نرخ نکول<br>یک‌ماهه</th>
      <th>زیان سالانه<br>میلیارد تومان</th>
    </tr></thead>
    <tbody>
""" % (LABEL[1], LABEL[2], LABEL[3]))
for (nm, tag, _), m in zip(OPT, MET):
    W('      <tr><td class="opt">%s<em>%s</em></td>' % (nm, tag))
    for b in (1, 2, 3):
        cls = ' class="band3"' if b == 3 and m["cnt"][b] else ""
        W('<td%s>%s</td>' % (cls, f(m["cnt"][b]) if m["cnt"][b] else "&mdash;"))
    W('<td class="on1">%s</td><td>%s درصد</td><td>%s</td></tr>\n'
      % (f(m["ann"]), d3(100*m["pd1"]), d1(m["loss"])))
W('''    </tbody>
  </table>
  <p class="note"><b>چرا نرخ نکول در گزینه کم‌ریسک بالاتر است؟</b> این نرخ وزن‌دار بر
  حسب <i>مبلغ</i> است، نه تعداد نفرات. در گزینه گسترده پول بیشتری به دست
  کم‌ریسک‌ترین دهک‌ها می‌رسد، پس نرخ هر تومان پایین‌تر می‌آید &mdash; ولی چون مبلغ
  کل بزرگ‌تر است، <b>زیان مطلق بیشتر می‌شود: %s در برابر %s میلیارد تومان.</b></p>
''' % (d1(MET[2]["loss"]), d1(MET[0]["loss"])))

# ------------------------------------------------- participation + the flag
W("""  <div class="two">
    <div class="box">
      <h2>اعطایی در یک سال به ازای نرخ مشارکت &mdash; میلیارد تومان</h2>
      <table><thead><tr><th>گزینه</th>%s</tr></thead><tbody>
""" % "".join("<th>%s درصد</th>" % fa(int(t*100)) for t in TAKE))
for (nm, _, _), m in zip(OPT, MET):
    W('        <tr><td>%s</td>%s</tr>\n'
      % (nm, "".join("<td>%s</td>" % f(m["ann"]*t) for t in TAKE)))
W("""      </tbody></table>
    </div>
    <div class="box flag">
      <h2>یک هشدار پیش از انتخاب</h2>
      <p>قاعده سقف می‌گوید وام باید از قبض یک ماه مشترک کمتر بماند، وگرنه احتمال
      نکول نزدیک دو برابر می‌شود. ولی فقط <b>%s مشترک</b> قبض بالای ۵۰۰ هزار تومان
      دارند. گزینه محتاطانه <b>%s</b> نفر و گزینه گسترده <b>%s</b> نفر را در باند
      ۵۰۰ هزار تا ۱ میلیون می‌گذارد.</p>
    </div>
  </div>
""" % (f(CARRY[500_000]), f(MET[1]["cnt"][3]), f(MET[2]["cnt"][3])))

W("""  <div class="ft">تعداد مشترکین از صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶ &middot;
  امتیاز و ترتیب ریسک از مدل بازآموزی‌شده ۱۴۰۵/۰۷/۱۴ &middot;
  ارقام ریالی با سقف میانی هر باند (۲۰۰، ۴۰۰ و ۷۵۰ هزار تومان) محاسبه شده‌اند &middot;
  نرخ نکول وزن‌دار بر حسب مبلغ در معرض، نه تعداد نفرات</div>
</div>
""")

io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_slide_fa.html"), "w", encoding="utf-8").write(out.getvalue())
print("written", len(out.getvalue()), "bytes")
for (nm,_,_), m in zip(OPT, MET):
    print("  %-10s %s / %s / %s  ->  %s bn, %s pct, %s bn"
          % (nm, f(m["cnt"][1]), f(m["cnt"][2]), f(m["cnt"][3]),
             f(m["ann"]), d3(100*m["pd1"]), d1(m["loss"])))

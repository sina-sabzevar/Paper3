# -*- coding: utf-8 -*-
"""One executive slide: the scoring method, how many customers, three options
across three limit bands, and participation in one strip.

Sized to a single 16:9 screen. Type scales with vmin so it fills a projector
and still reads on a laptop; below 820px it falls back to a scrolling column.
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dcb_schematic_svg as SCH

from dcb_numbers import *

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
  --u:clamp(9px, 1.19vmin, 20px);
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
html{scroll-snap-type:y mandatory}
.slide{height:100vh;min-height:100vh;scroll-snap-align:start;break-after:page;
  display:flex;flex-direction:column;
  justify-content:space-between;gap:calc(var(--u)*1.25);padding:calc(var(--u)*2.2) calc(var(--u)*3) calc(var(--u)*1.7);direction:rtl}
.slide:last-child{break-after:auto}

/* the schematic slide: the drawing takes whatever height the text leaves */
.schw{flex:1 1 auto;min-height:0;display:flex;align-items:center;justify-content:center}
.schw svg{display:block;width:100%;height:auto;max-height:100%;color:var(--ink-2)}
__SVGCSS__

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

.fam{display:flex;gap:calc(var(--u)*0.6)}
.fm{flex:1 1 0;min-width:0;border-top:2px solid var(--s1);padding-top:calc(var(--u)*0.5)}
.fm b{display:block;font-size:calc(var(--u)*1.12);font-weight:600;line-height:1.35}
.fm span{display:block;font-size:calc(var(--u)*0.92);color:var(--ink-3);
  line-height:1.5;margin-top:calc(var(--u)*0.15)}

/* the matrix */
table{width:100%;border-collapse:collapse;font-size:calc(var(--u)*1.18)}
@media (max-width:1400px){table{font-size:calc(var(--u)*1.08)}
  thead th{font-size:calc(var(--u)*0.9)}
  tr.grp th{font-size:calc(var(--u)*0.86)}}
th,td{padding:calc(var(--u)*0.6) calc(var(--u)*0.5);text-align:center;
  border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:start;white-space:normal;
  padding-inline-start:0;padding-inline-end:calc(var(--u)*0.9)}
tr.grp th{font-size:calc(var(--u)*0.95);font-weight:600;color:var(--ink-2);
  border-bottom:1px solid var(--line);padding-bottom:calc(var(--u)*0.28)}
tr.grp th[rowspan]{border-bottom:none}
.tk{display:block;font-size:calc(var(--u)*0.84);color:var(--ink-3);font-weight:400}
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
.two{display:grid;grid-template-columns:1fr 1.5fr;gap:calc(var(--u)*1.4);align-items:start}
.box{background:var(--panel);border:1px solid var(--rule);border-radius:calc(var(--u)*0.6);
  padding:calc(var(--u)*1.1) calc(var(--u)*1.3)}
.box h2{margin:0 0 calc(var(--u)*0.65);font-size:calc(var(--u)*1.2);font-weight:600;color:var(--ink-2)}
.box table{font-size:calc(var(--u)*1.1)}
.box td{text-align:start}
.box td.num{text-align:end;color:var(--ink);font-weight:600}
.box th,.box td{padding:calc(var(--u)*0.42) calc(var(--u)*0.5);border-bottom:1px solid var(--line)}
.box tbody tr:last-child td{border-bottom:none}
.flag{border-inline-start:calc(var(--u)*0.3) solid var(--crit)}
.flag h2{color:var(--crit)}
.flag p{margin:0;font-size:calc(var(--u)*1.1);color:var(--ink-2);line-height:1.75}
.flag b{color:var(--ink)}
.ft{padding-top:calc(var(--u)*0.9);border-top:1px solid var(--rule);
  font-size:calc(var(--u)*0.95);color:var(--ink-3);line-height:1.6}

/* a 720- or 768-tall screen cannot carry the same unit as a 1080 one, and the
   overflow there is uniform rather than from any one block */
@media (max-height:800px){:root{--u:clamp(8px, 1.09vmin, 20px)}}
@media (max-width:820px){
  :root{--u:12px}
  html,body{height:auto}
  .slide{min-height:0;padding:20px 16px}
  .flow{flex-wrap:wrap}.fx{flex:1 1 45%}
  .two{grid-template-columns:1fr}
}
</style>

<div class="slide">
  <div class="hd">
    <h1>مدل اعتبارسنجی &mdash; چطور کار می‌کند</h1>
    <span class="sub">اعتبار روی قبض، یک‌ماهه، مهر ۱۴۰۵</span>
  </div>
  <div class="schw">__SVG__</div>
  <p class="note">__CAP__</p>
  <div class="ft">__FN__</div>
</div>

<div class="slide">
""")

# ----------------------------------------------------------------- header
W("""  <div class="hd">
    <h1>سه گزینه اعطای اعتبار</h1>
    <span class="sub">اعتبار روی قبض، یک‌ماهه، مهر ۱۴۰۵</span>
  </div>
""")

# ----------------------------------------------------------------- method
FAMILIES = [("مصرف و درآمد", "درآمد هر ماه، روند، ماه‌های بدون مصرف"),
            ("رفتار پرداخت", "مجموع پرداختی و تعداد ماه‌های پرداخت"),
            ("بدهی و اعتبار باز", "مانده بدهی و اعتبار در دسترس"),
            ("سابقه قطع سرویس", "قطع یک‌طرفه و دوطرفه در سال قبل"),
            ("قدمت خط", "سن خط و ماه‌هایی که فعال بوده")]

STEPS = [(mi(BASE) + " میلیون", "مشترک دائمی", False),
         (mi(SCORED) + " میلیون", "پس از غربال درآمد و سابقه قطعی", False),
         ("امتیازدهی", "۳۹ ویژگی در ۵ خانواده، شرح زیر", False),
         (f(APPROVED), "تأییدشده برای اعطای اعتبار", True)]
W('  <div class="flow">\n')
for n, t, on in STEPS:
    W('    <div class="fx%s"><span class="n">%s</span><span class="t">%s</span></div>\n'
      % (" on" if on else "", n, t))
W("""  </div>
  <div class="fam">
""")
for t, d in FAMILIES:
    W('    <div class="fm"><b>%s</b><span>%s</span></div>\n' % (t, d))
W("""  </div>
  <p class="note"><b>۳۹ ویژگی</b>، همه از رفتار حساب خود مشترک &mdash; هیچ داده شخصی،
  مکانی یا جمعیتی در مدل نیست. دقت روی داده آزمون <b>%s</b>.
  <b>سابقه قطع سرویس سال قبل به‌تنهایی ۹۲ درصد بهبود مدل را می‌دهد.</b></p>
""" % fa("{:.2f}".format(AUC)))

# ----------------------------------------------------------------- matrix
W("""  <table>
    <thead>
      <tr class="grp">
        <th rowspan="2">گزینه</th>
        <th colspan="3">مشترکین تأییدشده و ضریب نفوذ هر باند</th>
        <th colspan="3">در هر بار اعطا</th>
        <th colspan="3">در یک سال &mdash; %s بار</th>
      </tr>
      <tr>
        <th>%s<span class="tk">نفوذ %s درصد</span></th>
        <th>%s<span class="tk">نفوذ %s درصد</span></th>
        <th>%s<span class="tk">نفوذ %s درصد</span></th>
        <th>وام‌گیرنده</th>
        <th>میانگین وام<span class="tk">تومان</span></th>
        <th>مبلغ کل<span class="tk">میلیارد</span></th>
        <th>اعطایی<span class="tk">میلیارد</span></th>
        <th>نرخ نکول<span class="tk">وزن‌دار بر مبلغ</span></th>
        <th>زیان<span class="tk">میلیارد</span></th>
      </tr>
    </thead>
    <tbody>
""" % (fa(ROUNDS), LABEL[1], fa(int(TAKE[1]*100)), LABEL[2], fa(int(TAKE[2]*100)),
       LABEL[3], fa(int(TAKE[3]*100))))
for (nm, tag, _), m in zip(OPT, MET):
    W('      <tr><td class="opt">%s<em>%s</em></td>' % (nm, tag))
    for b in (1, 2, 3):
        cls = ' class="band3"' if b == 3 and m["cnt"][b] else ""
        W('<td%s>%s</td>' % (cls, f(m["cnt"][b]) if m["cnt"][b] else "&mdash;"))
    W('<td>%s</td><td>%s</td><td>%s</td><td class="on1">%s</td>'
      '<td>%s درصد</td><td>%s</td></tr>\n'
      % (f(m["borrowers"]), f(m["avg"]), f(m["per_round"]), f(m["ann"]),
         d3(100*m["pd1"]), d1(m["loss"])))
W("""    </tbody>
  </table>
  <p class="note"><b>وام بزرگ‌تر، نفوذ کمتر.</b> برای همین گزینه گسترده کمترین
  وام‌گیرنده را دارد (%s در برابر %s در کم‌ریسک) و با این حال بیشترین مبلغ را
  می‌دهد. <b>نرخ نکول وزن‌دار بر حسب مبلغ است، نه تعداد نفرات</b>، پس در گزینه گسترده
  پایین‌تر می‌آید چون پول بیشتری به دست کم‌ریسک‌ترین دهک‌ها می‌رسد؛ زیان مطلق با این
  حال بالاتر می‌رود. <b>با این ضرایب، حتی گزینه گسترده فقط %s درصد هدف ۱۵٬۰۰۰
  میلیاردی را پوشش می‌دهد</b> &mdash; این فاصله با سقف اعتبار پر نمی‌شود، با نفوذ و
  دفعات وام پر می‌شود.</p>
""" % (f(MET[2]["borrowers"]), f(MET[0]["borrowers"]),
       fa("{:.0f}".format(100*MET[2]["ann"]/TARGET))))

# ------------------------------------------------- participation + the flag
W("""  <div class="two">
    <div class="box">
      <h2>چطور حساب شده</h2>
      <table><tbody>
        <tr><td>نفوذ باند ۱۰۰ تا ۳۰۰ هزار</td><td class="num">%s درصد</td></tr>
        <tr><td>نفوذ باند ۳۰۰ تا ۵۰۰ هزار</td><td class="num">%s درصد</td></tr>
        <tr><td>نفوذ باند ۵۰۰ هزار تا ۱ میلیون</td><td class="num">%s درصد</td></tr>
        <tr><td>دفعات وام در سال</td><td class="num">%s بار</td></tr>
        <tr><td>سقف میانی هر باند</td><td class="num">۲۰۰، ۴۰۰ و ۷۵۰ هزار</td></tr>
      </tbody></table>
    </div>
    <div class="box flag">
      <h2>یک هشدار پیش از انتخاب</h2>
      <p>قاعده سقف می‌گوید وام باید از قبض یک ماه مشترک کمتر بماند، وگرنه احتمال
      نکول نزدیک دو برابر می‌شود. ولی فقط <b>%s مشترک</b> قبض بالای ۵۰۰ هزار تومان
      دارند. گزینه محتاطانه <b>%s</b> نفر و گزینه گسترده <b>%s</b> نفر را در باند
      ۵۰۰ هزار تا ۱ میلیون می‌گذارد.</p>
    </div>
  </div>
""" % (fa(int(TAKE[1]*100)), fa(int(TAKE[2]*100)), fa(int(TAKE[3]*100)), fa(ROUNDS),
       f(CARRY[500_000]), f(MET[1]["cnt"][3]), f(MET[2]["cnt"][3])))

W("""  <div class="ft">تعداد مشترکین از صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶&#1563;
  امتیاز و ترتیب ریسک از مدل بازآموزی‌شده ۱۴۰۵/۰۷/۱۴&#1563;
  هر مقدار ریالی به‌صورت نسبت به میانه جمعیت هم وارد مدل می‌شود تا تورم امتیاز را
  جابه‌جا نکند&#1563; هر بار وام یک ماهه است&#1563; ضریب نفوذ و دفعات وام در سال، فرض است و اندازه‌گیری نشده</div>
</div>
""")

# fill the drawing in last, so the per-cent signs in its CSS never meet a
# format string
html = (out.getvalue().replace("__SVGCSS__", SCH.CSS.strip())
                      .replace("__SVG__", SCH.svg())
                      .replace("__CAP__", SCH.CAPTION)
                      .replace("__FN__", SCH.FOOTNOTE))
io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_slide_fa.html"), "w", encoding="utf-8").write(html)
print("written", len(html), "bytes")
for (nm,_,_), m in zip(OPT, MET):
    print("  %-10s %s / %s / %s  ->  %s bn, %s pct, %s bn"
          % (nm, f(m["cnt"][1]), f(m["cnt"][2]), f(m["cnt"][3]),
             f(m["ann"]), d3(100*m["pd1"]), d1(m["loss"])))

# -*- coding: utf-8 -*-
"""The Persian dashboard, editable in the browser.

Every piece of text and every number lives in DATA, a JSON island in the page.
The page renders itself from DATA, and saving regenerates the whole document
from DATA and republishes it - the live DOM is never serialised. Numbers are
plain text: editing a count does not recompute a total, which is deliberate
and stated on the page.
"""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dash_style_fa

GRADES = [("A", 3_029_397, 0.001417, 400_000, "کم‌ریسک‌ترین"),
          ("B", 4_087_448, 0.003298, 300_000, ""),
          ("C", 1_085_787, 0.007387, 150_000, ""),
          ("D",   599_140, 0.013538, 100_000, ""),
          ("E",   542_951, 0.040000,       0, "رد می‌شود")]
SCORED   = 9_344_723
APPROVED = sum(g[1] for g in GRADES if g[3] > 0)
OUTSTAND = sum(g[1] * g[3] for g in GRADES)
AVG_LIM  = OUTSTAND / APPROVED
ANNUAL   = OUTSTAND * 12 / 1e9
LOSS_LO, LOSS_HI = ANNUAL * 0.0009, ANNUAL * 0.0014
LOSS_MID = (LOSS_LO + LOSS_HI) / 2
RISKT    = sum(g[1] * g[3] * g[2] for g in GRADES if g[3] > 0)

# ---- the model's own decile ladder: (cumulative n, cumulative 4-month pd).
# The grade table is too coarse to place a cut at one million, the ladder is not.
LADDER = [(934_472,0.000941),(1_868_944,0.001527),(2_803_416,0.001684),
          (3_737_889,0.002104),(4_672_361,0.002694),(5_606_833,0.003146),
          (6_541_306,0.004060),(7_475_778,0.005180),(8_410_250,0.008571),
          (9_344_723,0.029613)]
DECILE = [(LADDER[i][0] - (LADDER[i-1][0] if i else 0), LADDER[i][1]) for i in range(10)]

# ---- 56 D7: where a FLAT ticket of each size lands the scored population.
# Only these four ticket sizes were measured, so the scenarios use only these.
D7 = {100_000:(729_051,5_709_462,2_906_210), 200_000:(68_125,2_944_902,6_331_696),
      300_000:(13_829,1_441_474,7_889_420), 500_000:(2_712,366_965,8_975_046)}
SHOCK_P = (1.000, 1.133, 1.907)          # 53: normal / under 2x / 2x or more

# Today's grade cut approves 8,801,772 and declines grade E. The decile ladder
# cannot reproduce that, so the riskiest decile is SPLIT: the part today
# approves becomes its own band, and grade E stays declined.
GRADE_APPROVED, GRADE_E = 8_801_772, 542_951
RISKY_N  = GRADE_APPROVED - 8_410_250                    # 391,522
# Their rate is not measured directly. Decile 10 carries n x marginal bads and
# grade E carries its own; what is left over belongs to this band. It assumes
# grade E sits inside decile 10, which is close but not exact - decile 9's
# marginal rate is 0.857 pct against a grade E boundary of 0.8 pct - so the
# figure is an estimate and the page says so.
RISKY_PD = (DECILE[9][0]*DECILE[9][1] - GRADE_E*0.040) / RISKY_N
DECILE10_PD = DECILE[9][1]                               # the pessimistic read

# nine deciles, then the risky band. Grade E is declined throughout.
BANDS = DECILE[:9] + [(RISKY_N, RISKY_PD)]

# The risky band always takes the smallest limit; the three scenarios differ
# only in what the nine clean deciles get.
SCEN = [("گسترده", "وضع فعلی",
         [500_000,500_000,300_000,300_000,300_000,300_000,300_000,300_000,100_000,100_000]),
        ("محتاطانه", "نیمی از حجم",
         [300_000,300_000,300_000,200_000,200_000,200_000,100_000,100_000,100_000,100_000]),
        ("سخت‌گیرانه", "تجمع روی ۱۰۰ هزار",
         [300_000,200_000,200_000,100_000,100_000,100_000,100_000,100_000,100_000,100_000])]

def scen_metrics(lim, bands=None):
    bands = bands if bands is not None else BANDS
    k = len(bands)
    out  = sum(bands[i][0]*lim[i] for i in range(k))
    appr = sum(bands[i][0] for i in range(k) if lim[i])
    ann  = out*12/1e9
    pd1  = sum(bands[i][0]*lim[i]*bands[i][1] for i in range(k))/out/3.0
    band = [0.0,0.0,0.0]
    for i in range(k):
        if not lim[i]: continue
        t = D7[lim[i]]; tot = float(sum(t))
        for j in range(3): band[j] += bands[i][0]*t[j]/tot
    prem = sum(x*q for x,q in zip(band, SHOCK_P))/sum(band)
    return dict(ge300=sum(bands[i][0] for i in range(k) if lim[i]>=300_000),
                at100=sum(bands[i][0] for i in range(k) if lim[i]==100_000),
                appr=appr, avg=out/appr, out=out/1e9, ann=ann, pd1=pd1,
                band=band, prem=prem, loss=ann*pd1, lossp=ann*pd1*prem)

MET = [scen_metrics(l) for _,_,l in SCEN]
# the same three with the risky band dropped, which is the comparison that
# answers "how much safer does the programme get if we decline them"
MET_NR = [scen_metrics(l[:9], BANDS[:9]) for _,_,l in SCEN]
TAKE = [0.10, 0.20, 0.30, 0.40]      # how many of the approved actually draw

_FA = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹",
       ",":"٬", ".":"٫"}
def fa(t):   return "".join(_FA.get(c, c) for c in str(t))
def f(n):    return fa("{:,}".format(int(round(n))))
def one(x):  return fa("{:.1f}".format(x))
def two(x):  return fa("{:.2f}".format(x))
def bnf(x):  return fa("{:,.1f}".format(x))

grows = []
for name, n, pd, lim, note in GRADES:
    dec = lim == 0
    grows.append([
        name + ((" — " + note) if note else ""),
        f(n),
        "رد می‌شود" if dec else f(lim),
        two(pd * 100) + " درصد",
        "—" if dec else bnf(n * lim / 1e9) + " میلیارد",
        "—" if dec else fa("{:.0f}".format(100 * n * lim * pd / RISKT)) + " درصد",
        "off" if dec else ""])
grows.append(["مجموع تأییدشده", f(APPROVED), "میانگین " + f(AVG_LIM), "",
              bnf(OUTSTAND / 1e9) + " میلیارد", "۱۰۰ درصد", "tot"])

DATA = {
 "eyebrow": "اعتبار روی قبض · آنچه هست و آنچه هزینه دارد",
 "h1": "وام‌دادن به مشترک روی قبض ماه بعدش",
 "lede": "مشترک روی قبض تلفن همراهش اعتبار می‌گیرد و در قبض ماه بعد بازپرداخت می‌کند. "
         "هر مشترک امتیازدهی می‌شود، سقف اعتبارش متناسب با امتیازش تعیین می‌شود، و "
         "پرریسک‌ترین‌ها رد می‌شوند.",
 "chips": [["دوره بازپرداخت", "یک ماه"], ["سقف اعتبار", "۱۰۰٬۰۰۰ تا ۴۰۰٬۰۰۰ تومان"],
           ["تأییدشده", f(APPROVED)], ["همه مبالغ", "تومان"]],
 "kpis": [["مشترکین تأییدشده", f(APPROVED), "۹۴ درصد از کل امتیازدهی‌شده‌ها"],
          ["میانگین سقف اعتبار (تومان)", f(AVG_LIM), "بر اساس امتیاز خود مشترک"],
          ["اعطایی در یک سال (میلیارد تومان)", f(ANNUAL),
           "۲۱۳ درصد از هدف ۱۵٬۰۰۰ میلیاردی"],
          ["زیان مورد انتظار (میلیارد تومان)", one(LOSS_LO) + " تا " + one(LOSS_HI),
           "در سال، با فرض اینکه هیچ وصولی نداشته باشیم"]],
 "kpiCap": "در هر لحظه فقط " + bnf(OUTSTAND / 1e9) + " میلیارد تومان نزد مشترکین است؛ "
           "همان پول دوازده بار در سال برمی‌گردد و دوباره اعطا می‌شود.",
 "funnel": {
   "h2": "چه کسانی واجد شرایط‌اند",
   "p": "چهار بررسی روی سابقه شش ماه گذشته، و بعد امتیاز مدل.",
   "steps": [["همه مشترکین دائمی", "نقطه شروع", f(41_270_092), ""],
             ["قبض‌شان آن‌قدر هست که وام را تحمل کند",
              "حداقل ۱۷۰٬۰۰۰ تومان در ۲ ماه از ۶ ماه", f(10_087_975), "keep"],
             ["هیچ‌وقت قطع یک‌طرفه نشده‌اند", "در تمام شش ماه", f(9_437_240), "keep"],
             ["هیچ‌وقت قطع دوطرفه نشده‌اند", "در تمام شش ماه", f(9_344_723), "keep"],
             ["امتیازشان برای وام‌دهی کافی است",
              "مدل پرریسک‌ترین رتبه را رد می‌کند", f(APPROVED), "last"]],
   "drops": ["در هیچ دو ماهی ۱۷۰٬۰۰۰ تومان قبض نداشته‌اند|" + f(41_270_092 - 10_087_975),
             "سرویس خروجی‌شان قطع شده بود|" + f(650_735),
             "سرویس ورودی‌شان قطع شده بود|" + f(92_517),
             "در پرریسک‌ترین رتبه امتیاز گرفته‌اند|" + f(SCORED - APPROVED)],
   "cap": "<b>بررسی اول تقریباً تمام کار را انجام می‌دهد</b> و " + f(41_270_092 - 10_087_975)
          + " مشترک را کنار می‌گذارد. امتیاز مدل فقط " + f(SCORED - APPROVED)
          + " نفر دیگر را حذف می‌کند." },
 "grades": {
   "h2": "سقف اعتبار هر مشترک",
   "p": "رتبه، سقف اعتبار را تعیین می‌کند. کم‌ریسک‌ترین‌ها بیشترین سقف را می‌گیرند.",
   "head": ["رتبه", "مشترکین", "سقف اعتبار", "احتمال نکول ۴ ماهه",
            "مانده در هر لحظه", "سهم از زیان"],
   "rows": grows,
   "foot": "<b>رتبه B نیمی از کل زیان را به دوش می‌کشد</b>، در حالی که دومین گروه "
           "کم‌ریسک است: بزرگ‌ترین گروه است و سقف ۳۰۰٬۰۰۰ تومانی می‌گیرد." },
 "rule": {
   "h2": "یک قاعده که سقف‌ها باید رعایتش کنند",
   "p": "اعتبار روی قبض ماه بعد می‌نشیند. اینکه قبض چقدر بالا بپرد، احتمال نکول را "
        "تعیین می‌کند.",
   "big": "هرگز بیشتر از قبض یک ماه مشترک به او وام ندهید.",
   "why": "زیر این خط، قبض کمتر از دو برابر بالا می‌رود و مشترک با نرخ عادی پرداخت "
          "می‌کند. روی این خط یا بالاتر، قبض دو برابر می‌شود و <b>احتمال نکول ۱٫۷ "
          "برابر</b> است.",
   "head": ["چه بر سر قبض مشترک می‌آید", "چقدر بالا می‌رود", "نرخ بازماندن از پرداخت"],
   "rows": [["قبض تقریباً تکان نمی‌خورد", "کمتر از ۱٫۲۵ برابر", "نرخ عادی", "off"],
            ["بالا می‌رود، اما به دو برابر نمی‌رسد", "۱٫۲۵ تا ۲٫۰۰ برابر", "۱٫۱۳ برابر", ""],
            ["دو برابر یا بیشتر می‌شود", "۲٫۰۰ برابر و بالاتر", "۱٫۹۱ برابر", "tot"]],
   "foot": "اندازه‌گیری‌شده روی ۴٫۰ میلیون مشترک‑ماه. جدول سقف‌ها این قاعده را از قبل "
           "رعایت می‌کند." },
 "scen": {
   "h2": "سه سناریوی سقف اعتبار",
   "p": "هر سه سناریو به همان " + f(MET[0]["appr"]) + " مشترک وام می‌دهند و فقط در "
        "مبلغی که به هر کس می‌دهند فرق دارند، تا مقایسه فقط روی تصمیمِ سقف باشد.",
   "cards": [[nm, tag, f(m["ann"]) + " میلیارد", "اعطایی در یک سال",
              one(m["lossp"]) + " میلیارد", "زیان سالانه با احتساب شوک قبض"]
             for (nm, tag, _), m in zip(SCEN, MET)],
   "head": ["سنجه", SCEN[0][0], SCEN[1][0], SCEN[2][0]],
   "rows": [["مشترکین تأییدشده"] + [f(m["appr"]) for m in MET] + [""],
            ["سقف بالای ۳۰۰ هزار می‌گیرند"] + [f(m["ge300"]) for m in MET] + [""],
            ["سقف ۱۰۰ هزار می‌گیرند"] + [f(m["at100"]) for m in MET] + [""],
            ["میانگین سقف اعتبار"] + [f(m["avg"]) for m in MET] + [""],
            ["مانده در هر لحظه (میلیارد تومان)"] + [f(m["out"]) for m in MET] + [""],
            ["اعطایی در یک سال (میلیارد تومان)"] + [f(m["ann"]) for m in MET] + ["tot"],
            ["نسبت به هدف ۱۵٬۰۰۰ میلیاردی"]
              + [fa("{:.0f}".format(100*m["ann"]/15000)) + " درصد" for m in MET] + [""],
            ["احتمال نکول یک‌ماهه"]
              + [fa("{:.3f}".format(100*m["pd1"])) + " درصد" for m in MET] + [""],
            ["در باند پرریسک شوک قبض"] + [f(m["band"][2]) for m in MET] + [""],
            ["ضریب شوک قبض"] + [fa("{:.2f}".format(m["prem"])) + " برابر" for m in MET] + [""],
            ["زیان پایه (میلیارد تومان)"] + [one(m["loss"]) for m in MET] + [""],
            ["زیان با شوک (میلیارد تومان)"] + [one(m["lossp"]) for m in MET] + ["tot"],
            ["زیان به ازای هر ۱۰۰۰ تومان اعطایی"]
              + [fa("{:.2f}".format(1000*m["lossp"]/m["ann"])) + " تومان" for m in MET] + [""]],
   "foot": "<b>نرخ نکول تقریباً ثابت می‌ماند: " + fa("{:.3f}".format(100*MET[1]["pd1"]))
           + " تا " + fa("{:.3f}".format(100*MET[0]["pd1"])) + " درصد.</b> سقف اعتبار "
           "تعیین نمی‌کند چه کسی نکول می‌کند &mdash; آن را <i>تأیید</i> تعیین می‌کند. "
           "چیزی که سقف عوض می‌کند، شوک قبض است: از "
           + fa("{:.2f}".format(MET[0]["prem"])) + " برابر در حالت گسترده به "
           + fa("{:.2f}".format(MET[2]["prem"])) + " برابر در حالت سخت‌گیرانه."
           "<br><br><b>قید مهم:</b> سهم باندهای شوک از اندازه‌گیری یک سقف ثابت روی "
           "<i>کل</i> جمعیت می‌آید، یعنی فرض می‌کند سقف بزرگ به یک مشترک تصادفی داده "
           "می‌شود. در عمل سقف بزرگ به دهک‌های کم‌ریسک می‌رسد که قبض بالاتری هم دارند، "
           "پس ارقام باند پرریسک و ضریب شوک <b>حد بالا هستند</b>. تفاوت میان سه سناریو "
           "قابل اتکاتر از خود سطح اعداد است.",
   "ladH3": "چه کسی چقدر می‌گیرد",
   "ladHead": ["گروه مشترکین", SCEN[0][0], SCEN[1][0], SCEN[2][0]],
   "ladRows": [["۱۰ درصد کم‌ریسک‌ترین" if i == 0 else "دهک " + fa(i+1)]
               + [f(l[i]) for _, _, l in SCEN] + [""] for i in range(9)]
              + [["گروه پرریسک · " + f(RISKY_N) + " نفر"]
                 + [f(l[9]) for _, _, l in SCEN] + ["tot"],
                 ["رتبه E · " + f(GRADE_E) + " نفر"] + ["رد می‌شود"]*3 + ["off"]],
   "ladFoot": "مشترکین بر اساس امتیاز مدل از کم‌ریسک به پرریسک مرتب شده‌اند. "
              "ارقام به تومان. گروه پرریسک در هر سه سناریو کمترین سقف را می‌گیرد.",
   "whyH3": "گروه پرریسک: " + f(RISKY_N) + " نفر",
   "why": "برای رسیدن به همان " + f(GRADE_APPROVED) + " مشترکی که امروز تأیید "
          "می‌شوند، پرریسک‌ترین دهک دو تکه شده است: <b>" + f(GRADE_E) + " نفر</b> که "
          "رتبه E هستند و امروز هم رد می‌شوند، و <b>" + f(RISKY_N) + " نفر</b> که امروز "
          "تأیید می‌شوند. این گروه دوم در هر سه سناریو کمترین سقف، یعنی ۱۰۰ هزار تومان، "
          "را می‌گیرد.<br><br>"
          "<b>نرخ نکول این گروه حدود " + fa("{:.2f}".format(100*RISKY_PD)) + " درصد "
          "چهارماهه است</b> &mdash; تقریباً "
          + fa("{:.0f}".format(RISKY_PD/0.0026)) + " برابر میانگین نه دهک بالاتر. این "
          "رقم تقریبی است: از کسر بدهای رتبه E از کل بدهای دهک آخر به دست آمده و فرض "
          "می‌کند رتبه E کاملاً داخل آن دهک است، که دقیق نیست. اگر این گروه به اندازه "
          "بقیه دهک خودشان پرریسک باشند (" + fa("{:.2f}".format(100*DECILE10_PD))
          + " درصد)، صرفه حذف‌شان از جدول زیر هم بیشتر است.",
   "dropH3": "اگر این گروه حذف شود",
   "drop": {
     "head": ["سناریو", "اعطایی از دست می‌رود", "کاهش نرخ نکول", "کاهش زیان سالانه"],
     "rows": [[SCEN[i][0],
                 f(MET[i]["ann"]-MET_NR[i]["ann"]) + " میلیارد ("
                   + fa("{:.1f}".format(100*(MET[i]["ann"]-MET_NR[i]["ann"])/MET[i]["ann"]))
                   + " درصد)",
                 fa("{:.0f}".format(100*(MET[i]["pd1"]-MET_NR[i]["pd1"])/MET[i]["pd1"]))
                   + " درصد",
                 one(MET[i]["lossp"]-MET_NR[i]["lossp"]) + " میلیارد ("
                   + fa("{:.0f}".format(100*(MET[i]["lossp"]-MET_NR[i]["lossp"])/MET[i]["lossp"]))
                   + " درصد)",
                 "tot" if i == 2 else ""] for i in range(3)],
     "foot": "<b>در هر سه سناریو، حذف این " + f(RISKY_N) + " نفر فقط "
               + f(MET[0]["ann"]-MET_NR[0]["ann"]) + " میلیارد از اعطای سالانه کم "
               "می‌کند ولی " + fa("{:.0f}".format(100*(MET[2]["lossp"]-MET_NR[2]["lossp"])/MET[2]["lossp"]))
               + " تا " + fa("{:.0f}".format(100*(MET[0]["lossp"]-MET_NR[0]["lossp"])/MET[0]["lossp"]))
               + " درصد از زیان.</b> ارزان‌ترین کاهش ریسکی است که روی این صفحه وجود دارد." },
   "cap": "<b>حالت سخت‌گیرانه هنوز " + fa("{:.0f}".format(100*MET[2]["ann"]/15000))
          + " درصد هدف ۱۵٬۰۰۰ میلیاردی را پوشش می‌دهد</b>، با "
          + fa("{:.1f}".format(MET[0]["lossp"]/MET[2]["lossp"]))
          + " برابر زیان کمتر از حالت گسترده. حالت گسترده "
          + fa("{:.1f}".format(MET[0]["ann"]/MET[2]["ann"]))
          + " برابر بیشتر وام می‌دهد ولی "
          + fa("{:.1f}".format(MET[0]["lossp"]/MET[2]["lossp"]))
          + " برابر بیشتر زیان می‌دهد." },
 "take": {
   "h2": "نرخ مشارکت",
   "p": "همه مشترکینی که تأیید می‌شوند از اعتبارشان استفاده نمی‌کنند. ارقام سناریوها "
        "فرض می‌کنند همه استفاده کنند؛ اینجا همان ارقام در نرخ‌های واقعی‌تر مشارکت "
        "آورده شده و بقیه مشترکین اصلاً وام نمی‌گیرند.",
   "lendH3": "اعطایی در یک سال (میلیارد تومان)",
   "lend": {
     "head": ["نرخ مشارکت"] + [nm for nm, _, _ in SCEN],
     "rows": [["{} درصد".format(fa(int(t*100)))]
              + [f(m["ann"]*t) for m in MET]
              + ["tot" if t == 0.40 else ""] for t in TAKE],
     "foot": "تعداد وام‌گیرنده در هر سه سناریو یکی است، چون هر سه به همان "
             + f(MET[0]["appr"]) + " مشترک وام می‌دهند: "
             + "، ".join(f(MET[0]["appr"]*t) + " نفر در " + fa(int(t*100)) + " درصد"
                          for t in TAKE) + "." },
   "lossH3": "زیان سالانه با احتساب شوک قبض (میلیارد تومان)",
   "loss": {
     "head": ["نرخ مشارکت"] + [nm for nm, _, _ in SCEN],
     "rows": [["{} درصد".format(fa(int(t*100)))]
              + [one(m["lossp"]*t) for m in MET]
              + ["tot" if t == 0.40 else ""] for t in TAKE],
     "foot": "نرخ نکول و ضریب شوک با مشارکت عوض نمی‌شوند؛ فقط حجم کم می‌شود، "
             "پس زیان دقیقاً به همان نسبت کم می‌شود." },
   "cap": "<b>در هیچ ترکیبی از این سه سناریو با مشارکت تا ۴۰ درصد، هدف ۱۵٬۰۰۰ میلیارد "
          "محقق نمی‌شود.</b> نزدیک‌ترین حالت، گسترده با ۴۰ درصد مشارکت است: "
          + f(MET[0]["ann"]*0.40) + " میلیارد، یعنی "
          + fa("{:.0f}".format(100*MET[0]["ann"]*0.40/15000)) + " درصد هدف. برای رسیدن "
          "به هدف، گسترده به <b>" + fa("{:.0f}".format(100*15000/MET[0]["ann"]))
          + " درصد</b> مشارکت نیاز دارد، محتاطانه به <b>"
          + fa("{:.0f}".format(100*15000/MET[1]["ann"])) + " درصد</b>، و سخت‌گیرانه "
          "<b>در هیچ نرخی نمی‌رسد</b> چون حتی با مشارکت کامل "
          + f(MET[2]["ann"]) + " میلیارد است."
          "<br><br><b>قید مهم:</b> فرض شده کسانی که وام می‌گیرند نمونه‌ای تصادفی از "
          "تأییدشده‌ها هستند. اگر وام‌گیرنده‌ها سیستماتیک پرریسک‌تر از بقیه باشند &mdash; "
          "که در وام‌دهی معمول است &mdash; نرخ نکول بالاتر از جدول سناریوها خواهد بود و "
          "ارقام زیان این جدول کف هستند، نه سقف." },
 "cost": {
   "h2": "هزینه محتمل طرح",
   "p": "مرحله به مرحله، تا بشود روی هر قدمش بحث کرد.",
   "steps": [["۱", f(APPROVED) + " مشترک به‌طور میانگین " + f(AVG_LIM) + " تومان وام می‌گیرند",
              "در هر لحظه <b>" + bnf(OUTSTAND/1e9) + " میلیارد تومان</b> نزد مشترکین است، و "
              "در طول یک سال <b>" + f(ANNUAL) + " میلیارد تومان</b> اعطا می‌شود."],
             ["۲", "نرخ نکول یک‌ماهه بین ۰٫۰۹ تا ۰٫۱۴ درصد است",
              "این بازه یک انتخاب است، نه عدم‌قطعیت: کف بازه یعنی وام فقط به "
              "کم‌ریسک‌ترین‌ها، سقف بازه یعنی وام به همه تأییدشده‌ها."],
             ["۳", "پس سالانه " + one(LOSS_LO) + " تا " + one(LOSS_HI)
              + " میلیارد تومان زیان می‌دهیم",
              "با فرض <b>هیچ وصولی</b> از مشترک نکول‌کرده، که عمداً بدبینانه است. در برابر "
              + f(ANNUAL) + " میلیارد تومان اعطایی، نقطه میانی حدود <b>۰٫۱۲ درصد</b> است."]],
   "stressH3": "اگر زیان بدتر از مدل دربیاید",
   "stressHead": ["سناریو", "ضریب", "زیان سالانه", "نسبت به اعطایی"],
   "stressRows": [[nm, two(m) + "×", one(LOSS_MID*m) + " میلیارد",
                   two(100*LOSS_MID*m/ANNUAL) + " درصد", "tot" if m == 1.0 else ""]
                  for nm, m in [("مطابق مدل", 1.00), ("با رانش جمعیت فعلی", 1.157),
                                ("وام‌دهی در آستانه نوروز", 1.68),
                                ("دو برابر نرخ مدل", 2.00)]],
   "stressFoot": "حتی با <b>دو برابر</b> نرخ مدل، زیان زیر <b>" + one(LOSS_MID*2)
                 + " میلیارد تومان</b> روی <b>" + f(ANNUAL)
                 + " میلیارد تومان</b> اعطایی می‌ماند." },
 "open": {
   "h2": "آنچه هنوز نمی‌دانیم",
   "p": "دو مورد که هنوز باز است.",
   "panels": [["هیچ مشترکی در این داده‌ها تا به حال اعتبار نگرفته است",
               ["امتیاز مدل رفتار مشترک را وقتی <b>وام نگرفته</b> توصیف می‌کند.",
                "<b>تنها راه پاسخ، یک اجرای آزمایشی محدود است</b>؛ با دوره یک‌ماهه "
                "جواب ظرف چند هفته می‌رسد."]],
              ["هدف ۱۵٬۰۰۰ میلیاردی، اعطای سالانه است یا مانده؟",
               ["با گردش ماهانه این دو عدد دوازده برابر فرق دارند.",
                "<b>اعطای سالانه:</b> " + f(ANNUAL) + " میلیارد، بیش از دو برابر هدف. "
                "<b>مانده در هر لحظه:</b> " + bnf(OUTSTAND/1e9) + " میلیارد، با فاصله "
                "زیاد تا هدف."]]] },
 "footer": ["تعداد مشترکین از سوابق صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶. رتبه‌ها، سقف‌ها و احتمال "
            "نکول از مدل امتیازدهی ۱۴۰۵/۰۷/۱۴ با شاخص دقت ۰٫۸۲۷۸. ارقام شوک قبض روی "
            "۴٫۰ میلیون مشترک‑ماه.",
            "همه مبالغ به تومان. احتمال نکول ۴ ماهه از افق مدل می‌آید؛ ارقام ریالی بر "
            "پایه نرخ یک‌ماهه محاسبه شده‌اند."],
}

EXTRA_CSS = """
/* the editing layer */
#bar{position:fixed;inset-block-end:16px;inset-inline-start:16px;z-index:50;
  display:flex;gap:8px;align-items:center;background:var(--surface);
  border:1px solid var(--rule);border-radius:999px;padding:7px 9px;
  box-shadow:0 6px 24px rgba(0,0,0,0.16)}
#bar button{font-family:var(--fa);font-size:13.5px;border-radius:999px;cursor:pointer;
  padding:7px 16px;border:1px solid transparent;background:var(--raise);color:var(--ink)}
#bar button.go{background:var(--s1);color:#fff}
#bar button:disabled{opacity:0.45;cursor:default}
#bar .msg{font-size:12.5px;color:var(--ink-3);padding-inline:6px;max-width:30ch}
body.editing [data-k]{outline:1px dashed color-mix(in srgb,var(--s1) 55%,transparent);
  outline-offset:3px;border-radius:3px}
body.editing [data-k]:hover{background:color-mix(in srgb,var(--s1) 8%,transparent)}
body.editing [data-k]:focus{outline:2px solid var(--s1);background:transparent}
.panel table{min-width:0}
/* the three scenarios */
.scards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:760px){.scards{grid-template-columns:1fr}}
.scard{background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:18px 18px 20px;display:flex;flex-direction:column;gap:4px;min-width:0}
.scard .tag{font-size:12.5px;color:var(--ink-3);margin-bottom:10px}
.scard .pair{display:flex;flex-direction:column;gap:1px;margin-top:9px}
.scard .pair .v{font-size:20px;font-weight:700;line-height:1.35}
.scard .pair .v.crit{color:var(--crit)}
.scard .pair .l{font-size:12px;color:var(--ink-3);line-height:1.6}
.hint{font-size:12.5px;color:var(--ink-3);margin-top:10px;line-height:1.85}
"""

HEAD = ('<title>اعتبار روی قبض</title>\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Vazirmatn:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700'
        '&family=IBM+Plex+Mono:wght@400;500;600&display=swap">\n')

APP = r"""
// ---------------------------------------------------------------- state
const D = JSON.parse(document.getElementById("dcb-data").textContent);
const root = document.getElementById("root");
let editing = false, dirty = false, artifact = null;

const get = p => p.split(".").reduce((o, k) => o[/^\d+$/.test(k) ? +k : k], D);
const set = (p, v) => { const k = p.split("."); const last = k.pop();
  k.reduce((o, s) => o[/^\d+$/.test(s) ? +s : s], D)[/^\d+$/.test(last) ? +last : last] = v; };

// `k` marks a field as editable; its value is written straight back into D
const E = (tag, cls, path, extra) =>
  "<" + tag + (cls ? ' class="' + cls + '"' : "") + ' data-k="' + path + '"'
  + (extra || "") + ">" + get(path) + "</" + tag + ">";

function render() {
  const h = [];
  h.push('<header>');
  h.push(E("p", "eyebrow", "eyebrow"));
  h.push(E("h1", "", "h1"));
  h.push(E("p", "lede", "lede"));
  h.push('<div class="spec">');
  D.chips.forEach((c, i) => h.push('<span class="chip">' + E("span", "", "chips." + i + ".0")
    + " <b" + ' data-k="chips.' + i + '.1">' + c[1] + "</b></span>"));
  h.push('</div></header>');

  h.push('<div class="kpi" style="margin-top:26px">');
  D.kpis.forEach((t, i) => h.push('<div class="tile">'
    + E("span", "k", "kpis." + i + ".0") + E("span", "v", "kpis." + i + ".1")
    + E("span", "s", "kpis." + i + ".2") + "</div>"));
  h.push("</div>");
  h.push(E("p", "cap", "kpiCap"));

  // ---- the funnel
  h.push('<section><div class="head">' + E("h2", "", "funnel.h2")
    + E("p", "", "funnel.p") + '</div><div class="card"><div class="fun">');
  D.funnel.steps.forEach((s, i) => {
    if (i > 0) { const d = D.funnel.drops[i - 1].split("|");
      h.push('<div class="fdrop"><span data-k="funnel.drops.' + (i - 1) + '">&minus; '
        + d[0] + '</span><span class="v">' + d[1] + "</span></div>"); }
    h.push('<div class="fstep ' + s[3] + '"><div class="t">'
      + E("span", "", "funnel.steps." + i + ".0") + E("em", "", "funnel.steps." + i + ".1")
      + "</div>" + E("div", "v", "funnel.steps." + i + ".2") + "</div>");
  });
  h.push("</div>" + E("p", "cap", "funnel.cap") + "</div></section>");

  h.push(section("grades", D.grades, 6));
  // ---- the rule
  h.push('<section><div class="head">' + E("h2", "", "rule.h2") + E("p", "", "rule.p")
    + '</div><div class="rule">' + E("div", "big", "rule.big")
    + E("div", "why", "rule.why") + '</div><div class="card" style="margin-top:14px">'
    + table("rule", D.rule, 3) + "</div></section>");

  // ---- the three scenarios
  h.push('<section><div class="head">' + E("h2", "", "scen.h2") + E("p", "", "scen.p")
    + '</div><div class="scards">');
  D.scen.cards.forEach((c, i) => {
    const b = "scen.cards." + i + ".";
    h.push('<div class="scard">'
      + E("h3", "", b + "0") + E("span", "tag", b + "1")
      + '<div class="pair">' + E("span", "v", b + "2") + E("span", "l", b + "3") + "</div>"
      + '<div class="pair">' + E("span", "v crit", b + "4") + E("span", "l", b + "5")
      + "</div></div>");
  });
  h.push('</div><div class="card" style="margin-top:14px">'
    + table("scen", D.scen, 3) + "</div>");
  h.push('<div class="card">' + E("h3", "", "scen.ladH3")
    + '<div class="tbl-s"><table><thead><tr>');
  D.scen.ladHead.forEach((c, i) => h.push('<th data-k="scen.ladHead.' + i + '">' + c + "</th>"));
  h.push("</tr></thead><tbody>");
  D.scen.ladRows.forEach((r, i) => {
    h.push('<tr class="' + (r[4] || "") + '">');
    for (let j = 0; j < 4; j++)
      h.push('<td data-k="scen.ladRows.' + i + "." + j + '">' + r[j] + "</td>");
    h.push("</tr>");
  });
  h.push('</tbody><tfoot><tr><td colspan="4" data-k="scen.ladFoot">' + D.scen.ladFoot
    + "</td></tr></tfoot></table></div></div>"
    + '<div class="panel unknown" style="margin-top:14px"><h3><span class="dot"></span>'
    + '<span data-k="scen.whyH3">' + D.scen.whyH3 + "</span></h3>"
    + E("p", "", "scen.why")
    + '<h3 style="margin-top:16px">' + '<span data-k="scen.dropH3">' + D.scen.dropH3
    + "</span></h3>" + table("scen.drop", D.scen.drop, 3) + "</div>"
    + E("p", "cap", "scen.cap") + "</section>");

  // ---- participation
  h.push('<section><div class="head">' + E("h2", "", "take.h2") + E("p", "", "take.p")
    + '</div><div class="split">'
    + '<div class="panel">' + E("h3", "", "take.lendH3")
    + table("take.lend", D.take.lend, 3) + "</div>"
    + '<div class="panel">' + E("h3", "", "take.lossH3")
    + table("take.loss", D.take.loss, 3) + "</div></div>"
    + E("p", "cap", "take.cap") + "</section>");

  // ---- the cost
  h.push('<section><div class="head">' + E("h2", "", "cost.h2") + E("p", "", "cost.p")
    + '</div><div class="card"><div class="steps">');
  D.cost.steps.forEach((s, i) => h.push('<div class="stp">'
    + E("span", "n", "cost.steps." + i + ".0") + "<div>"
    + E("h3", "", "cost.steps." + i + ".1") + E("p", "", "cost.steps." + i + ".2")
    + "</div></div>"));
  h.push('</div></div><div class="card">' + E("h3", "", "cost.stressH3")
    + '<div class="tbl-s"><table><thead><tr>');
  D.cost.stressHead.forEach((c, i) => h.push('<th data-k="cost.stressHead.' + i + '">' + c + "</th>"));
  h.push("</tr></thead><tbody>");
  D.cost.stressRows.forEach((r, i) => {
    h.push('<tr class="' + r[4] + '">');
    for (let j = 0; j < 4; j++) h.push('<td data-k="cost.stressRows.' + i + "." + j + '">' + r[j] + "</td>");
    h.push("</tr>");
  });
  h.push('</tbody><tfoot><tr><td colspan="4" data-k="cost.stressFoot">' + D.cost.stressFoot
    + "</td></tr></tfoot></table></div></div></section>");

  // ---- what is open
  h.push('<section><div class="head">' + E("h2", "", "open.h2") + E("p", "", "open.p")
    + '</div><div class="split">');
  D.open.panels.forEach((p, i) => {
    h.push('<div class="panel unknown"><h3><span class="dot"></span>'
      + '<span data-k="open.panels.' + i + '.0">' + p[0] + "</span></h3><ul>");
    p[1].forEach((li, j) => h.push('<li data-k="open.panels.' + i + ".1." + j + '">' + li + "</li>"));
    h.push("</ul></div>");
  });
  h.push("</div></section>");

  h.push("<footer>" + E("span", "", "footer.0") + E("span", "", "footer.1") + "</footer>");
  root.innerHTML = h.join("");
  if (editing) arm();
}

function table(key, o, cols) {
  const h = ['<div class="tbl-s"><table><thead><tr>'];
  cols = o.head.length - 1 >= cols ? o.head.length : cols + 1;   // label + data
  o.head.forEach((c, i) => h.push('<th data-k="' + key + '.head.' + i + '">' + c + "</th>"));
  h.push("</tr></thead><tbody>");
  o.rows.forEach((r, i) => {
    h.push('<tr class="' + (r[cols] || r[r.length - 1] || "") + '">');
    for (let j = 0; j < cols; j++)
      h.push('<td data-k="' + key + ".rows." + i + "." + j + '">' + (r[j] || "") + "</td>");
    h.push("</tr>");
  });
  h.push('</tbody><tfoot><tr><td colspan="' + cols + '" data-k="' + key + '.foot">'
    + o.foot + "</td></tr></tfoot></table></div>");
  return h.join("");
}
function section(key, o, cols) {
  return '<section><div class="head">' + E("h2", "", key + ".h2") + E("p", "", key + ".p")
    + '</div><div class="card">' + table(key, o, cols) + "</div></section>";
}

// ---------------------------------------------------------------- editing
function arm() {
  root.querySelectorAll("[data-k]").forEach(el => {
    el.setAttribute("contenteditable", "true");
    el.addEventListener("input", () => {
      const p = el.dataset.k, v = el.innerHTML.trim();
      if (p.indexOf("funnel.drops.") === 0) {
        const cur = get(p).split("|");
        set(p, v.replace(/^&minus;\s*/, "").replace(/^−\s*/, "") + "|" + cur[1]);
      } else set(p, v);
      dirty = true; paint();
    }, { passive: true });
  });
}
function paint() {
  document.body.classList.toggle("editing", editing);
  btnEdit.textContent = editing ? "پایان ویرایش" : "ویرایش متن و اعداد";
  btnSave.hidden = !editing;
  btnSave.disabled = !dirty || !artifact;
  msg.textContent = !artifact ? "ذخیره در دسترس نیست — فقط خواندن"
    : (dirty ? "تغییر ذخیره‌نشده دارید" : "");
}

// Rebuild the WHOLE document from D. The style and the app are read from their
// own tags, so only the data changes; the live DOM is never serialised.
function buildDoc() {
  const css = document.getElementById("dcb-css").outerHTML;
  const app = document.getElementById("dcb-app").outerHTML;
  const head = document.getElementById("dcb-head").innerHTML;
  const RESET = ':root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);'
    + 'padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui;'
    + 'background:#fafaf9}img{max-width:100%}[hidden]{display:none!important}';
  return '<!doctype html><html><head><meta charset=utf8>'
    + '<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
    + "<style>" + RESET + "</style></head><body>"
    + '<span id="dcb-head" hidden>' + head + "</span>"
    + css
    + '<script id="dcb-data" type="application/json">'
    + JSON.stringify(D).replace(/<\//g, "<\\/") + "<\/script>"
    + '<div class="wrap" dir="rtl" lang="fa"><div id="root"></div></div>'
    + '<div id="bar" hidden></div>'
    + app + "</body></html>";
}

const bar = document.getElementById("bar");
bar.innerHTML = '<button id="btnEdit"></button>'
  + '<button id="btnSave" class="go">ذخیره</button><span class="msg" id="msg"></span>';
const btnEdit = document.getElementById("btnEdit"),
      btnSave = document.getElementById("btnSave"),
      msg     = document.getElementById("msg");
bar.hidden = false;

btnEdit.onclick = () => { editing = !editing;
  if (editing) arm(); else root.querySelectorAll("[data-k]")
    .forEach(el => el.removeAttribute("contenteditable"));
  paint(); };
btnSave.onclick = async () => {
  if (!artifact) return;
  btnSave.disabled = true; msg.textContent = "در حال ذخیره…";
  try { await artifact.publish(buildDoc()); dirty = false; msg.textContent = "ذخیره شد"; }
  catch (e) { msg.textContent = (e && e.code === "conflict")
      ? "نسخه تازه‌تری ذخیره شده بود؛ صفحه به‌روز می‌شود"
      : "ذخیره نشد — دسترسی ویرایش ندارید"; }
  paint();
};

render(); paint();
// window.claude exists only inside the viewer; the page must render without it
(window.claude && window.claude.use ? window.claude.use("artifact")
                                    : Promise.resolve(null))
  .then(a => { artifact = a; paint(); })
  .catch(() => { artifact = null; paint(); });
"""

out = io.StringIO(); W = out.write
W('<span id="dcb-head" hidden>' + HEAD + "</span>\n")
W('<style id="dcb-css">' + dash_style_fa.CSS[len("<style>"):-len("</style>")]
  + EXTRA_CSS + "</style>\n")
W('<script id="dcb-data" type="application/json">'
  + json.dumps(DATA, ensure_ascii=False).replace("</", "<\\/") + "</script>\n")
W('<div class="wrap" dir="rtl" lang="fa"><div id="root"></div></div>\n')
W('<div id="bar" hidden></div>\n')
W('<script id="dcb-app">' + APP + "</script>\n")

html = out.getvalue()
# the head block is injected by the page itself; keep a real <title> for the tool
html = HEAD + html
io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "dcb_manager_fa.html"), "w", encoding="utf-8").write(html)
print("written", len(html), "bytes")

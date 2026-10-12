# -*- coding: utf-8 -*-
"""The deck as a NATIVE, editable PowerPoint: every number is a run of text
in a shape or a real table cell, so it can be corrected in PowerPoint.

Layout is in points on the 960 x 540 canvas, which is the 1920 x 1080 HTML
design halved. Figures come from dcb_numbers, the same module the HTML
slides read, so the two cannot quote different values.

The option table is written in REVERSED physical column order rather than
with rtl="1" on the table. A renderer that ignores the rtl flag lays the
columns out left to right and the table reads backwards; reversed physical
order is read identically by every renderer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx import Presentation
from pptx.util import Pt
from pptx.enum.text import MSO_ANCHOR
from dcb_numbers import *                                   # noqa: F401,F403
from pptx.dml.color import RGBColor
from pptx_fa import (P, W, H, FONT, INK, INK2, INK3, PLANE, PANEL, LINE, RULE,
                     RULE2,
                     S1, CRIT, MDLBG, OUTBG, OUTLN, BAND3,
                     text, rect, line, strip_table_style, cell_borders,
                     cell_fill, cell_text)
import dcb_schematic_svg as SCH

M      = 36.0                      # side margin
RIGHT  = W - M                     # 924
SUB    = "اعتبار روی قبض، یک‌ماهه، مهر ۱۴۰۵"


def header(sl, title):
    text(sl, RIGHT - 560, 18, 560, 30, [(title, 20, True, INK)], align="r")
    text(sl, M, 22, 300, 20, [(SUB, 9, False, INK3)], align="l")
    line(sl, M, 54, RIGHT, 54, INK, 1.4)


# =============================================================== slide 1
def slide_schematic(prs):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    header(sl, "مدل اعتبارسنجی — چطور کار می‌کند")

    # the SVG's 1200-unit content strip mapped onto the margins, and its
    # 556 units of height onto what the title and the footnotes leave
    s   = (RIGHT - M) / 1200.0
    y0  = 62.0
    X   = lambda v: RIGHT - (1240 - v) * s      # noqa: E731
    Y   = lambda v: y0 + v * s                  # noqa: E731
    wid = lambda a, b: (b - a) * s              # noqa: E731

    TTL, SUBS, TAG, SEC, AL, BIG = 13, 10.5, 9.5, 10, 9.5, 22

    def sec(yv, label):
        text(sl, RIGHT - 300, Y(yv) - 11, 300, 14, [(label, SEC, True, INK3)],
             align="r")
        line(sl, M, Y(yv + 10), RIGHT, Y(yv + 10), LINE, 0.75)

    def band(yv, hv, rows):
        """one row of the schematic: input box, model box, outcome box"""
        for (a, b, lines, bg, ln) in rows:
            rect(sl, X(a), Y(yv), wid(a, b), hv * s, bg, ln)
            text(sl, X(a), Y(yv), wid(a, b), hv * s, lines, align="ctr")

    # ---- 1 training
    sec(18, "۱   مدل چطور یاد گرفت")
    band(40, 124, [
        (SCH.IN0, SCH.IN1, [("رفتار ۶ ماههٔ مشترک", TTL, True, INK),
                            ("مهر تا اسفند ۱۴۰۴", SUBS, False, INK2),
                            ("۳۹ ویژگی از حساب خودش", TAG, False, INK3)], PANEL, LINE),
        (SCH.MD0, SCH.MD1, [("آموزش مدل", TTL, True, S1),
                            ("روی همین دوره", TAG, False, INK3)], MDLBG, S1),
        (SCH.OU0, SCH.OU1, [("نتیجهٔ ۶ ماه بعد", TTL, True, INK),
                            ("فروردین تا شهریور ۱۴۰۵", SUBS, False, INK2),
                            ("بد = مشترکی که به قطع دوطرفه رسید", TAG, False, INK3)],
         PANEL, LINE)])

    line(sl, X(SCH.IN0 - 4), Y(102), X(SCH.MD1 + 4), Y(102), INK2, 1.1, arrow=True)
    text(sl, X(SCH.IN0) - 60, Y(78), 120, 12, [("ویژگی‌ها", AL, False, INK3)])
    line(sl, X(SCH.OU1 + 4), Y(102), X(SCH.MD0 - 4), Y(102), INK2, 1.1, arrow=True)
    text(sl, X(SCH.OU1) - 60, Y(78), 120, 12, [("جوابِ درست", AL, False, INK3)])
    text(sl, X(SCH.OU1) - 90, Y(172), 280, 14,
         [("در این دوره جواب معلوم است — مدل همین را یاد می‌گیرد", TAG, False, INK3)])

    # ---- 2 scoring
    sec(214, "۲   امروز چطور کار می‌کند")
    band(236, 124, [
        (SCH.IN0, SCH.IN1, [("رفتار ۶ ماههٔ مشترک", TTL, True, INK),
                            ("فروردین تا شهریور ۱۴۰۵", SUBS, False, INK2),
                            ("همان ۳۹ ویژگی", TAG, False, INK3)], PANEL, LINE),
        (SCH.MD0, SCH.MD1, [("همان مدل", TTL, True, S1),
                            ("بدون تغییر", TAG, False, INK3)], MDLBG, S1),
        (SCH.OU0, SCH.OU1, [("احتمال نکول هر مشترک", TTL, True, INK),
                            ("برای هر یک از " + f(SCORED) + " مشترک", SUBS, False, INK2),
                            ("از " + mi(BASE) + " میلیون مشترک دائمی، پس از غربال",
                             TAG, False, INK3)], OUTBG, OUTLN)])

    line(sl, X(SCH.IN0 - 4), Y(298), X(SCH.MD1 + 4), Y(298), INK2, 1.1, arrow=True)
    text(sl, X(SCH.IN0) - 60, Y(274), 120, 12, [("ویژگی‌ها", AL, False, INK3)])
    line(sl, X(SCH.MD0 - 4), Y(298), X(SCH.OU1 + 4), Y(298), INK2, 1.1, arrow=True)
    text(sl, X(SCH.OU1) - 60, Y(274), 120, 12, [("پیش‌بینی", AL, False, INK3)])
    text(sl, X(SCH.OU1) - 90, Y(368), 280, 14,
         [("در این دوره جواب معلوم نیست — مدل آن را می‌گوید", TAG, False, INK3)])

    mdc = X((SCH.MD0 + SCH.MD1) / 2.0)
    line(sl, mdc, Y(164), mdc, Y(232), S1, 1.1, dash="dash", arrow=True)

    # ---- 3 decision
    sec(412, "۳   امتیاز چطور به تصمیم تبدیل می‌شود")
    rect(sl, X(820), Y(434), wid(820, 1240), 108 * s, PANEL, LINE)
    text(sl, X(820), Y(434), wid(820, 1240), 108 * s,
         [("۱۰ دهک، از کم‌ریسک به پرریسک", TTL, True, INK),
          ("هر دهک " + f(LAD[0][0]) + " مشترک", SUBS, False, INK2)])

    line(sl, X(816), Y(488), X(464), Y(488), INK2, 1.1, arrow=True)
    text(sl, X(816) - 200, Y(462), 200, 12, [("قاعدهٔ سقف", AL, False, INK3)])
    text(sl, X(816) - 220, Y(496), 220, 12,
         [("وام هر نفر کمتر از قبض یک ماهش", AL, False, INK3)])

    rect(sl, X(40), Y(434), wid(40, 460), 108 * s, OUTBG, OUTLN)
    text(sl, X(40), Y(434), wid(40, 460), 108 * s,
         [(f(APPROVED), BIG, True, S1),
          ("مشترک تأییدشده — سقف ۱۰۰ هزار تا ۱ میلیون تومان", SUBS, False, INK2)])

    # ---- the claim, and the caveats
    line(sl, M, 478, RIGHT, 478, RULE, 0.75)
    text(sl, M, 483, RIGHT - M, 24,
         [("تفاوت ساختاری دو ردیف بالا فقط در جهت یک فلش است: در آموزش، نتیجه وارد "
           "مدل می‌شود؛ در امتیازدهی، پیش‌بینی از مدل بیرون می‌آید. ورودی هر دو ردیف "
           "یکی است — ۶ ماه رفتار حساب و همان ۳۹ ویژگی. دقت مدل روی دادهٔ "
           "کنارگذاشته ۰٫۸۳ است.", 8.5, False, INK2)], align="r", wrap=True,
         anchor=MSO_ANCHOR.TOP, line_spacing=1.4)
    text(sl, M, 509, RIGHT - M, 30,
         [("۳۹ ویژگی، همه از رفتار حساب خود مشترک — هیچ داده شخصی، مکانی یا "
           "جمعیتی در مدل نیست؛ پنجرهٔ نتیجه ۶ ماه است: ۴ قبضی که اقساط رویشان "
           "می‌نشیند، به‌علاوهٔ ۲ ماه مهلت تا قسط آخر هم دیده شود؛ «قطع دوطرفه» حدود "
           "سه ماه بعد از شروع عدم پرداخت رخ می‌دهد، پس نشانهٔ دیررسی است و نرخ بد "
           "را کمتر از واقع برآورد می‌کند.", 7.5, False, INK3)], align="r",
         wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.4)
    return sl


# =============================================================== slide 2
# model card. Two models compared, the chosen one's numbers, how it was fitted,
# and the three things that stop the figures being read as point estimates.
MCOLW = [250, 374, 130, 134]          # logical: مدل | چیست | AUC | نتیجه
WARN  = RGBColor(0xFA, 0xB2, 0x19)


def slide_model(prs):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    text(sl, RIGHT - 640, 18, 640, 30,
         [("مدل‌ها \u2014 چه چیزی آزموده شد و چه چیزی انتخاب شد", 20, True, INK)],
         align="r")
    text(sl, M, 22, 300, 20, [("بازآموزی ۱۴۰۵/۰۷/۱۴", 9, False, INK3)], align="l")
    line(sl, M, 54, RIGHT, 54, INK, 1.4)

    # ---- the two models, side by side
    T_Y, HD_H, ROW_H = 62.0, 24.0, 46.0
    gf = sl.shapes.add_table(3, 4, P(M), P(T_Y), P(RIGHT - M), P(HD_H + 2 * ROW_H))
    tbl = gf.table
    strip_table_style(tbl._tbl)
    for logical, w in enumerate(MCOLW):
        tbl.columns[3 - logical].width = P(w)
    for r, h in enumerate([HD_H, ROW_H, ROW_H]):
        tbl.rows[r].height = P(h)
    mc = lambda r, logical: tbl.cell(r, 3 - logical)         # noqa: E731

    for r in range(3):
        for c in range(4):
            cell_fill(tbl.cell(r, c), None)
            cell_borders(tbl.cell(r, c), "", LINE)
    for logical, h in enumerate(["مدل", "چیست", "AUC روی دادهٔ اعتبارسنجی", "نتیجه"]):
        cell_text(mc(0, logical), [(h, 8.5, False, INK3)],
                  align="r" if logical == 0 else "ctr", pad=(2, 6, 2, 6), wrap=True)
        cell_borders(mc(0, logical), "B", INK3)

    rows = [(("کارت امتیازی لجستیک", INK),
             "رگرسیون لجستیک روی ویژگی‌های WOE \u2014 هر ویژگی به ۱۰ بازه تقسیم و "
             "با وزن شواهد جایگزین می‌شود",
             fa("{:.4f}".format(AUC_LOG_VA)),
             "مبنا. قابل توضیح به ازای هر مشترک، ولی ضعیف‌تر", None),
            (("گرادیان بوستینگ درختی", S1),
             "HistGradientBoosting \u2014 ۴۰۰ درخت کم‌عمق که هرکدام خطای قبلی را "
             "اصلاح می‌کند و برهم‌کنش ویژگی‌ها را خودش پیدا می‌کند",
             fa("{:.4f}".format(AUC_GB_VA)),
             "انتخاب شد \u2014 " + fa("{:.4f}".format(AUC_GB_VA - AUC_LOG_VA)) +
             " بهتر از مبنا", MDLBG)]
    for i, ((name, col), what, auc, verdict, bg) in enumerate(rows):
        r = 1 + i
        cell_text(mc(r, 0), [(name, 10.5, True, col)], align="r",
                  pad=(3, 6, 3, 6), wrap=True)
        cell_text(mc(r, 1), [(what, 8.5, False, INK2)], align="r",
                  pad=(3, 6, 3, 6), wrap=True)
        cell_text(mc(r, 2), [(auc, 10.5, bg is not None, INK)], pad=(3, 4, 3, 4))
        cell_text(mc(r, 3), [(verdict, 8.5, bg is not None, INK2 if bg is None else INK)],
                  align="ctr", pad=(3, 4, 3, 4), wrap=True)
        for j in range(4):
            if bg:
                cell_fill(mc(r, j), bg)
            cell_borders(mc(r, j), "B" if i == 0 else "", RULE2)

    # ---- how well it does
    KY = T_Y + HD_H + 2 * ROW_H + 10
    kpis = [(fa("{:.4f}".format(AUC)), "AUC روی دادهٔ کنارگذاشته"),
            (fa("{:.4f}".format(GINI)), "ضریب جینی"),
            (fa("{:.4f}".format(KS)), "آمارهٔ KS"),
            (fa("{:.1f}".format(100 * CAL_ERR)) + " درصد", "خطای سطح کالیبراسیون")]
    kw = (RIGHT - M - 3 * 8) / 4.0
    for i, (big, small) in enumerate(kpis):
        x = RIGHT - kw - i * (kw + 8)
        rect(sl, x, KY, kw, 40, PANEL, LINE)
        text(sl, x + 8, KY + 4, kw - 16, 19, [(big, 16, True, S1)], align="r")
        text(sl, x + 8, KY + 23, kw - 16, 13, [(small, 8.5, False, INK2)], align="r")

    # ---- what it leans on
    NY = KY + 50
    text(sl, M, NY, RIGHT - M, 40,
         [("بیشترین چیزی که مدل از آن یاد می‌گیرد: سابقهٔ قطع سرویس سال قبل. شش "
           "ستونی که قطعی‌های سال گذشته را می‌شمارند، به‌تنهایی " +
           fa("{:.4f}".format(PRE_TEST_GAIN)) + " از AUC دادهٔ کنارگذاشته را "
           "می‌سازند \u2014 " + fa(int(round(100 * PRE_TEST_GAIN / REFIT_GAIN))) +
           " درصد از کل بهبود " + fa("{:.4f}".format(REFIT_GAIN)) + " که بازآموزی "
           "داد. همین ستون‌ها پایدارترین ویژگی‌های مجموعه‌اند: PSI همهٔ آن‌ها زیر "
           "۰٫۰۰۰۳ است. مدل خطی دو برابر مدل درختی از آن‌ها سود برد \u2014 " +
           fa("{:.4f}".format(LOG_GAIN)) + " در برابر " +
           fa("{:.4f}".format(GB_GAIN)) + " \u2014 یعنی این سیگنال تقریباً "
           "جمع‌پذیر است و برای پیدا کردنش لازم نبود به درخت برسیم.",
           8.5, False, INK2)], align="r", wrap=True, anchor=MSO_ANCHOR.TOP,
         line_spacing=1.4)

    # ---- how it was fitted
    BY, BH = NY + 46, 104.0
    bw_r = 400.0
    bw_l = (RIGHT - M) - bw_r - 16
    rect(sl, RIGHT - bw_r, BY, bw_r, BH, PANEL, RULE)
    text(sl, RIGHT - bw_r + 12, BY + 8, bw_r - 24, 12,
         [("داده و تفکیک", 9.5, True, INK2)], align="r")
    dat = [("سطر آموزش", f(TRAIN_ROWS)),
           ("مورد بد در آن", f(TRAIN_BADS) + " \u2014 " +
            fa("{:.2f}".format(100 * BAD_RATE)) + " درصد"),
           ("ویژگی", fa(NFEAT)),
           ("تفکیک با هش روی شناسهٔ مشترک",
            fa(int(100 * (1 - VALID_FRAC))) + " و " + fa(int(100 * VALID_FRAC)) + " درصد"),
           ("کالیبراسیون", "ایزوتونیک، روی نیمی از اعتبارسنجی")]
    ir, il = RIGHT - 12, RIGHT - bw_r + 12
    for i, (lab, val) in enumerate(dat):
        yy = BY + 28 + i * 15
        text(sl, il + 170, yy, (ir - il) - 170, 11, [(lab, 8, False, INK2)], align="r")
        text(sl, il, yy, 170, 11, [(val, 8, True, INK)], align="l")

    rect(sl, M, BY, bw_l, BH, PANEL, RULE)
    text(sl, M + 12, BY + 8, bw_l - 24, 12,
         [("تنظیمات مدل انتخاب‌شده", 9.5, True, INK2)], align="r")
    cw = (bw_l - 24) / 3.0
    for i, (k, v) in enumerate(HP):
        col, row = i // 3, i % 3
        x = M + 12 + (2 - col) * cw
        yy = BY + 28 + row * 17
        text(sl, x, yy, cw - 10, 11, [(k, 8, False, INK3)], align="r")
        text(sl, x, yy, 60, 11, [(v, 8, True, INK)], align="l")
        line(sl, x, yy + 12, x + cw - 10, yy + 12, LINE, 0.5)

    # ---- and the three things that stop these being point estimates
    WY, WH = BY + BH + 10, 86.0
    ww = (RIGHT - M - 2 * 10) / 3.0
    warns = [("رتبه‌بندی را بیشتر از سطح باور کنید",
              fa(PSI_N) + " ویژگی رانش معنادار دارند، بیشترین با PSI " +
              fa("{:.2f}".format(PSI_MAX)) + ". مدل روی جمعیت زنده " +
              fa("{:.3f}".format(100 * LIVE_PD)) + " درصد می‌دهد در برابر " +
              fa("{:.3f}".format(100 * TEST_PD)) + " درصد روی آزمون. ترتیب ریسک "
              "در برابر این جابه‌جایی مقاوم است، عدد مطلق نه."),
             ("کالیبراسیون در دهک‌های امن محافظه‌کار است",
              "در سه دهک امن، ریسک مشاهده‌شده " + fa("{:.2f}".format(SAFE3_RATIO)) +
              " برابر چیزی است که مدل پیش‌بینی می‌کند \u2014 یعنی بیش از واقع "
              "برآورد می‌کند. جهتش به نفع ماست، ولی عدد را نقطه‌ای نخوانید."),
             ("سطح اعداد تأییدنشده است",
              "لیبل روی افق ۴ قبض بسته می‌شود، درحالی‌که نرخ یک‌ماههٔ "
              "اندازه‌گیری‌شده " + fa("{:.4f}".format(100 * RATE_1M)) + " درصد است. "
              "شکل نتیجه درست است؛ سطحش تا اجرای آزمایشی تأیید نمی‌شود.")]
    for i, (head, body) in enumerate(warns):
        x = RIGHT - ww - i * (ww + 10)
        rect(sl, x, WY, ww, WH, PANEL, RULE)
        line(sl, x + ww, WY, x + ww, WY + WH, WARN, 2.5)
        text(sl, x + 10, WY + 7, ww - 20, 12, [(head, 8.5, True, INK)], align="r",
             wrap=True, anchor=MSO_ANCHOR.TOP)
        text(sl, x + 10, WY + 22, ww - 20, WH - 30, [(body, 8, False, INK2)],
             align="r", wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.4)

    line(sl, M, 506, RIGHT, 506, RULE, 0.75)
    text(sl, M, 511, RIGHT - M, 24,
         [("مبنا و چالشگر روی همان تفکیک آموزش دیدند؛ انتخاب فقط بر اساس AUC روی "
           "دادهٔ اعتبارسنجی بود؛ دادهٔ کنارگذاشته تا آخر کنار ماند و یک بار خوانده "
           "شد؛ هیچ مشترکی در دو طرف تفکیک نیست، چون هش تابعی خالص از شناسهٔ اوست.",
           7.5, False, INK3)], align="r", wrap=True, anchor=MSO_ANCHOR.TOP)
    return sl


# =============================================================== slide 3
# logical order is the Persian reading order, rightmost first; the physical
# column index is 9 - logical, so the table reads correctly in any renderer
COLW = [155, 88, 82, 96, 84, 80, 64, 74, 109, 56]          # logical widths
GRP  = [("مشترکین تأییدشده و ضریب نفوذ هر باند", 1, 3),
        ("در هر بار اعطا", 4, 6),
        ("در یک سال — ۳ بار", 7, 9)]
HEAD = [("گزینه", None),
        ("۱۰۰ تا ۳۰۰ هزار", "نفوذ ۱۵ درصد"),
        ("۳۰۰ تا ۵۰۰ هزار", "نفوذ ۱۳ درصد"),
        ("۵۰۰ هزار تا ۱ میلیون", "نفوذ ۱۰ درصد"),
        ("وام‌گیرنده", None),
        ("میانگین وام", "تومان"),
        ("مبلغ کل", "میلیارد"),
        ("اعطایی", "میلیارد"),
        ("نرخ نکول", "وزن‌دار بر مبلغ"),
        ("زیان", "میلیارد")]
FAM = [("مصرف و درآمد", "درآمد هر ماه، روند، ماه‌های بدون مصرف"),
       ("رفتار پرداخت", "مجموع پرداختی و تعداد ماه‌های پرداخت"),
       ("بدهی و اعتبار باز", "مانده بدهی و اعتبار در دسترس"),
       ("سابقه قطع سرویس", "قطع یک‌طرفه و دوطرفه در سال قبل"),
       ("قدمت خط", "سن خط و ماه‌هایی که فعال بوده")]


def slide_options(prs):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    header(sl, "سه گزینه اعطای اعتبار")

    # ---- the funnel, four tiles, rightmost first
    tiles = [(mi(BASE) + " میلیون", "مشترک دائمی", False),
             (mi(SCORED) + " میلیون", "پس از غربال درآمد و سابقه قطعی", False),
             ("امتیازدهی", "۳۹ ویژگی در ۵ خانواده، شرح زیر", False),
             (f(APPROVED), "تأییدشده برای اعطای اعتبار", True)]
    tw = (RIGHT - M - 3 * 8) / 4.0
    for i, (big, small, on) in enumerate(tiles):
        x = RIGHT - tw - i * (tw + 8)
        rect(sl, x, 60, tw, 40, MDLBG if on else PANEL, S1 if on else LINE)
        text(sl, x + 8, 64, tw - 16, 19, [(big, 15, True, INK)], align="r")
        text(sl, x + 8, 83, tw - 16, 13, [(small, 8.5, False, INK2)], align="r")

    # ---- the five feature families
    fw = (RIGHT - M - 4 * 6) / 5.0
    for i, (name, detail) in enumerate(FAM):
        x = RIGHT - fw - i * (fw + 6)
        line(sl, x, 108, x + fw, 108, S1, 1.4)
        text(sl, x, 112, fw, 12, [(name, 9.5, True, INK)], align="r")
        text(sl, x, 125, fw, 12, [(detail, 8, False, INK3)], align="r")

    text(sl, M, 142, RIGHT - M, 12,
         [("۳۹ ویژگی، همه از رفتار حساب خود مشترک — هیچ داده شخصی، مکانی یا "
           "جمعیتی در مدل نیست. دقت روی داده آزمون ۰٫۸۳. سابقه قطع سرویس سال قبل "
           "به‌تنهایی ۹۲ درصد بهبود مدل را می‌دهد.", 8.5, False, INK2)], align="r")

    # ---- the matrix
    T_Y, GRP_H, HD_H, ROW_H = 158.0, 20.0, 38.0, 46.0
    gf = sl.shapes.add_table(5, 10, P(M), P(T_Y), P(RIGHT - M),
                             P(GRP_H + HD_H + 3 * ROW_H))
    tbl = gf.table
    strip_table_style(tbl._tbl)
    for logical, w in enumerate(COLW):
        tbl.columns[9 - logical].width = P(w)
    for r, h in enumerate([GRP_H, HD_H, ROW_H, ROW_H, ROW_H]):
        tbl.rows[r].height = P(h)
    cell = lambda r, logical: tbl.cell(r, 9 - logical)       # noqa: E731

    for r in range(5):
        for c in range(10):
            cell_fill(tbl.cell(r, c), None)
            cell_borders(tbl.cell(r, c), "", LINE)

    # group header
    cell(0, 0).merge(cell(1, 0))
    cell_text(cell(0, 0), [("گزینه", 9, True, INK3)], align="r", pad=(2, 0, 2, 6))
    for label, lo, hi in GRP:
        c = cell(0, hi).merge(cell(0, lo))
        cell_text(cell(0, hi), [(label, 8.5, True, INK2)])
        cell_borders(cell(0, hi), "B", LINE)

    # column header
    for logical, (label, sub) in enumerate(HEAD):
        if logical == 0:
            continue
        lines = [(label, 8, False, INK3)]
        if sub:
            lines.append((sub, 7, False, INK3))
        cell_text(cell(1, logical), lines)
        cell_borders(cell(1, logical), "B", INK3)
    cell_borders(cell(0, 0), "B", INK3)

    # body
    for i, ((name, note, _), m) in enumerate(zip(OPT, MET)):
        r = 2 + i
        cell_text(cell(r, 0), [(name, 11, True, INK),
                               (note, 8, False, INK3)], align="r",
                  pad=(3, 0, 3, 6), wrap=True)
        vals = [f(m["cnt"][1]), f(m["cnt"][2]),
                f(m["cnt"][3]) if m["cnt"][3] else "—",
                f(m["borrowers"]), f(m["avg"]), f(m["per_round"]),
                f(m["ann"]), d3(100 * m["pd1"]) + " درصد", d1(m["loss"])]
        for j, v in enumerate(vals, start=1):
            big = (j == 7)
            cell_text(cell(r, j), [(v, 11 if big else 9, big, INK if big else INK2)])
            if j == 3 and m["cnt"][3]:
                cell_fill(cell(r, j), BAND3)
        for j in range(10):
            cell_borders(cell(r, j), "B" if i < 2 else "", RULE2)

    # ---- what the table does not say on its own
    NY = T_Y + GRP_H + HD_H + 3 * ROW_H + 8
    text(sl, M, NY, RIGHT - M, 38,
         [("وام بزرگ‌تر، نفوذ کمتر. برای همین گزینه گسترده کمترین وام‌گیرنده را دارد "
           "(" + f(MET[2]["borrowers"]) + " در برابر " + f(MET[0]["borrowers"]) +
           " در کم‌ریسک) و با این حال بیشترین مبلغ را می‌دهد. نرخ نکول وزن‌دار بر حسب "
           "مبلغ است، نه تعداد نفرات، پس در گسترده پایین‌تر می‌آید چون پول بیشتری به "
           "دست کم‌ریسک‌ترین دهک‌ها می‌رسد؛ زیان مطلق با این حال بالاتر می‌رود.",
           8.5, False, INK2)], align="r", wrap=True, anchor=MSO_ANCHOR.TOP,
         line_spacing=1.4)
    text(sl, M, NY + 42, RIGHT - M, 16,
         [("با این ضرایب، حتی گزینه گسترده فقط " +
           fa(str(int(round(100 * MET[2]["ann"] / TARGET)))) + " درصد هدف " +
           f(TARGET) + " میلیاردی را پوشش می‌دهد — این فاصله با سقف اعتبار پر "
           "نمی‌شود، با نفوذ و دفعات وام پر می‌شود.", 8.5, True, INK)], align="r")

    # ---- assumptions, and the warning
    BY, BH = NY + 64, 80.0
    bw_r, bw_l = 340.0, (RIGHT - M) - 340.0 - 16
    rect(sl, RIGHT - bw_r, BY, bw_r, BH, PANEL, RULE)
    text(sl, RIGHT - bw_r + 12, BY + 8, bw_r - 24, 12,
         [("چطور حساب شده", 9.5, True, INK2)], align="r")
    rows = [("ضریب نفوذ، از باند پایین به بالا", "۱۵، ۱۳ و ۱۰ درصد"),
            ("دفعات وام در سال", "۳ بار"),
            ("سقف میانی هر باند", "۲۰۰، ۴۰۰ و ۷۵۰ هزار")]
    inner_r, inner_l = RIGHT - 12, RIGHT - bw_r + 12
    for i, (lab, val) in enumerate(rows):
        yy = BY + 26 + i * 17
        text(sl, inner_l + 140, yy, (inner_r - inner_l) - 140, 12,
             [(lab, 8.5, False, INK2)], align="r")
        text(sl, inner_l, yy, 130, 12, [(val, 8.5, True, INK)], align="l")
        if i < len(rows) - 1:
            line(sl, inner_l, yy + 14, inner_r, yy + 14, LINE, 0.5)

    LX = M
    rect(sl, LX, BY, bw_l, BH, PANEL, RULE)
    line(sl, LX + bw_l, BY, LX + bw_l, BY + BH, CRIT, 2.5)
    text(sl, LX + 12, BY + 8, bw_l - 24, 12,
         [("یک هشدار پیش از انتخاب", 9.5, True, CRIT)], align="r")
    text(sl, LX + 12, BY + 24, bw_l - 24, 54,
         [("قاعده سقف می‌گوید وام باید از قبض یک ماه مشترک کمتر بماند، وگرنه احتمال "
           "نکول نزدیک دو برابر می‌شود. ولی فقط " + f(CARRY[500_000]) + " مشترک قبض "
           "بالای ۵۰۰ هزار تومان دارند. گزینه محتاطانه " + f(MET[1]["cnt"][3]) +
           " نفر و گزینه گسترده " + f(MET[2]["cnt"][3]) + " نفر را در باند ۵۰۰ هزار "
           "تا ۱ میلیون می‌گذارد.", 9, False, INK2)],
         align="r", wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.45)

    line(sl, M, 506, RIGHT, 506, RULE, 0.75)
    text(sl, M, 512, RIGHT - M, 22,
         [("تعداد مشترکین از صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶؛ امتیاز و ترتیب ریسک از مدل "
           "بازآموزی‌شده ۱۴۰۵/۰۷/۱۴؛ هر مقدار ریالی به‌صورت نسبت به میانه جمعیت هم "
           "وارد مدل می‌شود تا تورم امتیاز را جابه‌جا نکند؛ هر بار وام یک ماهه است؛ "
           "ضریب نفوذ و دفعات وام در سال، فرض است و اندازه‌گیری نشده.",
           7.5, False, INK3)], align="r", wrap=True, anchor=MSO_ANCHOR.TOP)
    return sl


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = P(W), P(H)
    slide_schematic(prs)
    slide_model(prs)
    slide_options(prs)
    dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "outputs", "dcb_deck_fa_editable.pptx")
    prs.save(dst)
    print("wrote", dst, os.path.getsize(dst), "bytes")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""The options slide in the house style of the prepaid credit deck.

That deck's visual is one flat 2.5 MB bitmap with a handful of shapes on
top, so nothing could be reused from it. This rebuilds the same language -
numbered step cards with icon medallions and pill tags, a navy summary
band, and a navy-headed table - out of real shapes, so every number stays
editable.

The horizon is the five months left in the Jalali year: the 300k and 500k
caps are drawn twice, the 1M cap once. Figures come from dcb_numbers.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR
from dcb_numbers import *                                    # noqa: F401,F403
import pptx_fa as F
from pptx_fa import (P, W, H, text, rect, oval, line, strip_table_style,
                     cell_borders, cell_fill, cell_text)

F.FONT = "IRANSansXFaNum"            # the font the house deck is set in
EM     = F.EMOJI

# ---- the house palette, sampled off the prepaid slide
NAVY   = RGBColor(0x12, 0x35, 0x6E)
HDR    = RGBColor(0x11, 0x4A, 0x89)
BAND   = RGBColor(0x12, 0x3A, 0x74)
BLUE   = RGBColor(0x0D, 0x67, 0xC1)
PILL   = RGBColor(0xE7, 0xF0, 0xFC)
CARD   = RGBColor(0xFF, 0xFF, 0xFF)
CARDBD = RGBColor(0xCF, 0xE1, 0xF7)
PAGE   = RGBColor(0xF5, 0xFA, 0xFF)
ROW1   = RGBColor(0xFF, 0xFF, 0xFF)
ROW2   = RGBColor(0xEB, 0xF5, 0xFE)
PICK   = RGBColor(0xDD, 0xEC, 0xFC)
INK    = RGBColor(0x0F, 0x2F, 0x66)
INK2   = RGBColor(0x2B, 0x4C, 0x7E)
INK3   = RGBColor(0x6E, 0x88, 0xB4)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
GRID   = RGBColor(0xD6, 0xE5, 0xF6)

M, RIGHT = 28.0, 932.0
BASE_SUB = 26_500_000            # the base as the author set it on the slide

# ---- months 8..12: the two lower caps are drawn twice, the top cap once
ROUNDS_5M = {1: 2, 2: 2, 3: 1}


def five_month():
    out = []
    for (nm, note, assign) in OPT:
        amt = {1: 0.0, 2: 0.0, 3: 0.0}
        pdw = {1: 0.0, 2: 0.0, 3: 0.0}
        bor = {1: 0.0, 2: 0.0, 3: 0.0}
        cnt = {1: 0, 2: 0, 3: 0}
        for i, b in enumerate(assign):
            n, pd = BANDS[i]
            a = n * TAKE[b] * MID[b]
            amt[b] += a; pdw[b] += a * pd; bor[b] += n * TAKE[b]; cnt[b] += n
        tot   = sum(amt[b] * ROUNDS_5M[b] for b in (1, 2, 3))
        loans = sum(bor[b] * ROUNDS_5M[b] for b in (1, 2, 3))
        uniq  = sum(bor.values())
        pd1   = sum(pdw[b] * ROUNDS_5M[b] for b in (1, 2, 3)) / tot / 3.0
        out.append(dict(nm=nm, note=note, cnt=cnt, uniq=uniq, take=uniq / APPROVED,
                        loans=loans, tot=tot / 1e9, avg=tot / loans,
                        pd1=pd1, loss=tot / 1e9 * pd1))
    return out


FM = five_month()
FM[2]["nm"] = "پر ریسک"          # the name the author gave the widest option

CARDS = [("۱", "🔎", "غربال و واجد شرایط",
          "از " + fa("{:.1f}".format(BASE_SUB / 1e6)) + " میلیون مشترک دائمی، "
          + mi(SCORED) + " میلیون پس از غربال درآمد و سابقه قطعی وارد امتیازدهی می‌شوند.",
          ["درآمد ماهانه", "سابقه قطعی", "قدمت خط"]),
         ("۲", "🧠", "مدل‌سازی رفتار اعتباری",
          "آموزش روی رفتار حساب خود مشترک با " + fa(NFEAT) + " ویژگی در ۵ خانواده. "
          "دقت مدل روی دادهٔ کنارگذاشته " + fa("{:.2f}".format(AUC)) + " است.",
          ["HistGB", "WOE Logistic", "Isotonic"]),
         ("۳", "🎯", "تعیین سقف و اعطا",
          "رتبه‌بندی ۱۰ دهکی و قاعدهٔ سقف: وام هر نفر کمتر از قبض یک ماهش بماند، "
          "وگرنه احتمال نکول نزدیک دو برابر می‌شود.",
          ["۱۰۰ تا ۳۰۰", "۳۰۰ تا ۵۰۰", "۵۰۰ تا ۱٬۰۰۰ هزار"])]

COLW = [110, 86, 82, 92, 62, 82, 76, 84, 82, 82, 66]
# drawn as a band above the table rather than merged header cells: a merged
# cell comes out letter-spaced, which breaks Persian letter joining
GRP  = [("👥", "مشترکین تأییدشده به تفکیک باند سقف", 1, 3),
        ("💳", "در هر بار اعطا", 4, 6),
        ("📅", "تا پایان سال \u2014 مهر تا اسفند", 7, 10)]
ICON = ["🎯", "👤", "👤", "👤", "📈", "👥", "🪙", "🧾", "💰", "📉", "🧮"]
HEAD = ["گزینه", "۱۰۰ تا ۳۰۰ هزار", "۳۰۰ تا ۵۰۰ هزار", "۵۰۰ هزار تا ۱ میلیون",
        "ضریب نفوذ", "وام‌گیرنده", "میانگین وام", "تعداد کل وام",
        "اعطایی", "نرخ نکول", "زیان"]
UNIT = [None, "نفر", "نفر", "نفر", "از تأییدشده‌ها", "نفر", "تومان",
        "فقره", "میلیارد تومان", "وزن‌دار بر مبلغ", "میلیارد"]


def build(prs):
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    rect(sl, 0, 0, W, H, PAGE, None, radius=0)
    # the corner mark the house deck carries
    chev = sl.shapes.add_shape(F.MSO_SHAPE.CHEVRON, P(934), P(8), P(18), P(26))
    chev.rotation = 180
    chev.shadow.inherit = False
    F._no_theme_style(chev)
    chev.fill.solid(); chev.fill.fore_color.rgb = BLUE
    chev.line.fill.background()

    text(sl, RIGHT - 700, 14, 700, 24,
         [("اعطای اعتبار روی قبض مشترکین دائمی: از امتیازدهی تا سه گزینه اعطا",
           19, True, INK)], align="r")
    text(sl, RIGHT - 700, 38, 700, 14,
         [("مدل اعتبارسنجی اختصاصی   |   اعتبار یک‌ماهه روی قبض   |   "
           "افق مهر تا اسفند ۱۴۰۵", 9, False, INK3)], align="r")

    # ---------------------------------------------------------------- cards
    cw, cy, ch = (RIGHT - M - 24) / 3.0, 58.0, 118.0
    for i, (num, icon, title, body, pills) in enumerate(CARDS):
        x = RIGHT - cw - i * (cw + 12)
        rect(sl, x, cy, cw, ch, CARD, CARDBD, radius=0.09)
        oval(sl, x + 10, cy + 10, 26, 26, NAVY)
        text(sl, x + 10, cy + 10, 26, 26, [(num, 11, True, WHITE)])
        text(sl, x + 42, cy + 12, cw - 54, 16, [(title, 11.5, True, INK)], align="r")
        oval(sl, x + 12, cy + 46, 36, 36, PILL, CARDBD)
        text(sl, x + 12, cy + 46, 36, 36, [(icon, 15, False, BLUE, EM)])
        text(sl, x + 56, cy + 32, cw - 68, 46, [(body, 8, False, INK2)],
             align="r", wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.45)
        px = x + cw - 10
        for p in pills:
            pw = 11 + 4.6 * len(p)
            rect(sl, px - pw, cy + ch - 26, pw, 17, PILL, None, radius=0.42)
            text(sl, px - pw, cy + ch - 26, pw, 17, [(p, 7.5, True, NAVY)])
            px -= pw + 6

    # ---------------------------------------------------------------- band
    bw, by, bh = 470.0, 186.0, 38.0
    bx = (W - bw) / 2.0
    rect(sl, bx, by, bw, bh, BAND, None, radius=0.3)
    text(sl, bx + bw - 44, by, 34, bh, [("🏦", 15, False, WHITE, EM)])
    line(sl, bx + bw - 52, by + 8, bx + bw - 52, by + bh - 8, RGBColor(0x3E, 0x63, 0xA0), 1)
    text(sl, bx + 12, by + 5, bw - 72, 18,
         [(f(APPROVED) + "  مشترک تأییدشده برای اعطای اعتبار", 13, True, WHITE)],
         align="r")
    text(sl, bx + 12, by + 21, bw - 72, 13,
         [(f(FM[0]["tot"]) + " تا " + f(FM[2]["tot"]) +
           " میلیارد تومان اعطایی تا پایان سال، بسته به گزینه", 8,
           False, RGBColor(0xB9, 0xCF, 0xEE))], align="r")

    # ---------------------------------------------------------------- table
    TY, GH, HH, RH = 232.0, 25.0, 48.0, 44.0
    xs = [RIGHT]
    for w in COLW:
        xs.append(xs[-1] - w)

    rect(sl, M, TY, RIGHT - M, GH, NAVY, None, radius=0.34)
    line(sl, xs[1], TY + 5, xs[1], TY + GH - 5, RGBColor(0x45, 0x6A, 0xA5), 0.75)
    for icon, label, lo, hi in GRP:
        text(sl, xs[hi + 1], TY, xs[lo] - xs[hi + 1], GH,
             [[(icon + "  ", 8.5, False, WHITE, EM), (label, 8.5, True, WHITE)]])
        if hi < 10:
            line(sl, xs[hi + 1], TY + 5, xs[hi + 1], TY + GH - 5,
                 RGBColor(0x45, 0x6A, 0xA5), 0.75)

    TT = TY + GH + 3
    gf = sl.shapes.add_table(4, 11, P(M), P(TT), P(RIGHT - M), P(HH + 3 * RH))
    tbl = gf.table
    strip_table_style(tbl._tbl)
    for lo, w in enumerate(COLW):
        tbl.columns[10 - lo].width = P(w)
    for r, h in enumerate([HH, RH, RH, RH]):
        tbl.rows[r].height = P(h)
    c = lambda r, lo: tbl.cell(r, 10 - lo)                   # noqa: E731
    for r in range(4):
        for j in range(11):
            cell_fill(tbl.cell(r, j), None)
            cell_borders(tbl.cell(r, j), "", GRID)

    for lo in range(11):
        cell_fill(c(0, lo), HDR)
        lines = [(ICON[lo], 9, False, WHITE, EM), (HEAD[lo], 8.5, True, WHITE)]
        if UNIT[lo]:
            lines.append((UNIT[lo], 6.8, False, RGBColor(0xA9, 0xC6, 0xEA)))
        cell_text(c(0, lo), lines, pad=(3, 3, 3, 3), wrap=True)

    for i, m in enumerate(FM):
        r = 1 + i
        cell_fill(c(r, 0), NAVY)
        cell_text(c(r, 0), [(m["nm"], 11, True, WHITE),
                            (m["note"], 7.2, False, RGBColor(0xA9, 0xC6, 0xEA))],
                  align="r", pad=(3, 10, 3, 6), wrap=True)
        vals = [f(m["cnt"][1]), f(m["cnt"][2]),
                f(m["cnt"][3]) if m["cnt"][3] else "\u2014",
                d1(100 * m["take"]) + " درصد", f(m["uniq"]), f(m["avg"]),
                f(m["loans"]), f(m["tot"]), d3(100 * m["pd1"]) + " درصد",
                d2(m["loss"])]
        for j, v in enumerate(vals, start=1):
            key = (j == 8)
            cell_fill(c(r, j), PICK if key else (ROW1 if i % 2 == 0 else ROW2))
            cell_text(c(r, j), [(v, 11.5 if key else 9, key, INK if key else INK2)],
                      pad=(2, 3, 2, 3))
        for j in range(11):
            cell_borders(c(r, j), "B" if i < 2 else "", GRID)

    # ---------------------------------------------------------------- notes
    AY = TT + HH + 3 * RH + 10
    rect(sl, M, AY, RIGHT - M, 30, PILL, CARDBD, radius=0.3)
    text(sl, RIGHT - 34, AY, 26, 30, [("🔁", 12, False, BLUE, EM)])
    text(sl, M + 12, AY, RIGHT - M - 56, 30,
         [("تکرار وام تا پایان سال: سقف‌های ۳۰۰ و ۵۰۰ هزار دو بار، سقف ۱ میلیون "
           "یک بار  &nbsp;|&nbsp;  ضریب نفوذ به تفکیک باند ۱۵، ۱۳ و ۱۰ درصد  "
           "&nbsp;|&nbsp;  سقف میانی هر باند ۲۰۰، ۴۰۰ و ۷۵۰ هزار تومان"
           .replace("&nbsp;", " "), 8.5, True, NAVY)], align="r")

    text(sl, M, AY + 36, RIGHT - M, 26,
         [[("⚠️  ", 7.5, False, INK3, EM), ("قاعدهٔ سقف می‌گوید وام باید از قبض یک ماه مشترک کمتر بماند، ولی فقط "
           + f(CARRY[500_000]) + " مشترک قبض بالای ۵۰۰ هزار تومان دارند؛ ضریب نفوذ "
           "و دفعات وام فرض است و اندازه‌گیری نشده؛ نرخ نکول وزن‌دار بر حسب مبلغ است، "
           "نه تعداد نفرات؛ برای مقایسه، با ۳ بار وام در سال اعطایی "
           + f(MET[0]["ann"]) + "، " + f(MET[1]["ann"]) + " و " + f(MET[2]["ann"]) +
           " میلیارد می‌شود.", 7.5, False, INK3)]],
         align="r", wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.4)
    return sl


def d2(x):
    return fa("{:.2f}".format(x))


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = P(W), P(H)
    build(prs)
    dst = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "outputs", "dcb_slide_fa_styled.pptx")
    prs.save(dst)
    print("wrote", dst, os.path.getsize(dst), "bytes")


if __name__ == "__main__":
    main()

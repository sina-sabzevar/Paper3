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
from pptx_fa import (P, W, H, text, rect, oval, line, icon, strip_table_style,
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


def by_band():
    """One block per option, rows per cap band, as the prepaid slide lays it
    out. Bands inside one option ARE additive, so a total row is honest here
    in a way it never was across the three options."""
    out = []
    for (nm, note, assign), m in zip(OPT, FM):
        rows = []
        for b in (1, 2, 3):
            n  = sum(BANDS[i][0] for i, a in enumerate(assign) if a == b)
            pw = sum(BANDS[i][0] * BANDS[i][1] for i, a in enumerate(assign) if a == b)
            if not n:
                rows.append(dict(b=b, n=0)); continue
            bor   = n * TAKE[b]
            once  = bor * MID[b] / 1e9
            tot   = once * ROUNDS_5M[b]
            pd1   = (pw / n) / 3.0
            rows.append(dict(b=b, n=n, take=TAKE[b], bor=bor, once=once,
                             rep=ROUNDS_5M[b], tot=tot, pd1=pd1, loss=tot * pd1))
        live = [r for r in rows if r["n"]]
        tn   = sum(r["n"] for r in live)
        tbor = sum(r["bor"] for r in live)
        tt   = sum(r["tot"] for r in live)
        tl   = sum(r["loss"] for r in live)
        out.append(dict(nm=m["nm"], note=note, rows=rows,
                        tot=dict(n=tn, bor=tbor, take=tbor / APPROVED,
                                 once=sum(r["once"] for r in live),
                                 tot=tt, loss=tl, pd1=tl / tt)))
    return out


BB = by_band()

CARDS = [("۱", "screen", "غربال و واجد شرایط",
          "از " + fa("{:.1f}".format(BASE_SUB / 1e6)) + " میلیون مشترک دائمی، "
          + mi(SCORED) + " میلیون پس از غربال درآمد و سابقه قطعی وارد امتیازدهی می‌شوند.",
          ["درآمد ماهانه", "سابقه قطعی", "قدمت خط"]),
         ("۲", "brain", "مدل‌سازی رفتار اعتباری",
          "آموزش روی رفتار حساب خود مشترک با " + fa(NFEAT) + " ویژگی در ۵ خانواده. "
          "دقت مدل روی دادهٔ کنارگذاشته " + fa("{:.2f}".format(AUC)) + " است.",
          ["HistGB", "WOE Logistic", "Isotonic"]),
         ("۳", "card", "تعیین سقف و اعطا",
          "رتبه‌بندی ۱۰ دهکی و قاعدهٔ سقف: وام هر نفر کمتر از قبض یک ماهش بماند، "
          "وگرنه احتمال نکول نزدیک دو برابر می‌شود.",
          ["۱۰۰ تا ۳۰۰", "۳۰۰ تا ۵۰۰", "۵۰۰ تا ۱٬۰۰۰ هزار"])]

COLW = [150, 118, 76, 110, 104, 68, 110, 92, 76]
ICON = ["card_w", "people", "percent", "users", "coins", "repeat",
        "bag", "percent", "calc"]
HEAD = ["سقف وام", "مشترکین تأییدشده", "ضریب نفوذ", "وام‌گیرنده",
        "مبلغ هر بار اعطا", "ضریب تکرار", "مبلغ تا پایان سال", "نرخ نکول", "زیان"]
UNIT = [None, "نفر", "از باند", "نفر", "میلیارد تومان", "تا اسفند",
        "میلیارد تومان", "وزن‌دار بر مبلغ", "میلیارد تومان"]


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

    rect(sl, M, 16, 210, 28, BAND, None, radius=0.34)
    icon(sl, "net_w", M + 24, 30, 16)
    text(sl, M + 10, 16, 168, 28,
         [[(f(APPROVED), 12, True, WHITE),
           ("  تأییدشده", 8, False, RGBColor(0xB9, 0xCF, 0xEE))]], align="r")
    text(sl, RIGHT - 660, 14, 660, 24,
         [("اعطای اعتبار روی قبض مشترکین دائمی: از امتیازدهی تا سه گزینه اعطا",
           19, True, INK)], align="r")
    text(sl, RIGHT - 660, 38, 660, 14,
         [("مدل اعتبارسنجی اختصاصی   |   اعتبار یک‌ماهه روی قبض   |   "
           "افق مهر تا اسفند ۱۴۰۵", 9, False, INK3)], align="r")

    # ---------------------------------------------------------------- cards
    cw, cy, ch = (RIGHT - M - 24) / 3.0, 52.0, 68.0
    for i, (num, ic, title, body, pills) in enumerate(CARDS):
        x = RIGHT - cw - i * (cw + 12)
        rect(sl, x, cy, cw, ch, CARD, CARDBD, radius=0.09)
        oval(sl, x + 9, cy + 8, 20, 20, NAVY)
        text(sl, x + 9, cy + 8, 20, 20, [(num, 9, True, WHITE)])
        oval(sl, x + 9, cy + 34, 26, 26, PILL, CARDBD)
        icon(sl, ic, x + 22, cy + 47, 15)
        text(sl, x + 34, cy + 7, cw - 46, 14, [(title, 10, True, INK)], align="r")
        text(sl, x + 42, cy + 22, cw - 54, 24, [(body, 7.2, False, INK2)],
             align="r", wrap=True, anchor=MSO_ANCHOR.TOP, line_spacing=1.35)
        px = x + cw - 9
        for p in pills:
            pw = 9 + 4.2 * len(p)
            rect(sl, px - pw, cy + ch - 18, pw, 14, PILL, None, radius=0.42)
            text(sl, px - pw, cy + ch - 18, pw, 14, [(p, 6.8, True, NAVY)])
            px -= pw + 5

    # ---------------------------------------------------------------- table
    TY, HH, TH, RH, SH = 126.0, 35.0, 20.0, 19.0, 21.0
    BLK = TH + 3 * RH + SH
    nrow = 1 + 3 * 5
    gf = sl.shapes.add_table(nrow, 9, P(M), P(TY), P(RIGHT - M),
                             P(HH + 3 * (TH + 3 * RH + SH)))
    tbl = gf.table
    strip_table_style(tbl._tbl)
    for lo, w in enumerate(COLW):
        tbl.columns[8 - lo].width = P(w)
    heights = [HH] + [TH, RH, RH, RH, SH] * 3
    for r, h in enumerate(heights):
        tbl.rows[r].height = P(h)
    c = lambda r, lo: tbl.cell(r, 8 - lo)                    # noqa: E731
    xs = [RIGHT]                       # the right edge of each logical column
    for w in COLW:
        xs.append(xs[-1] - w)
    for r in range(nrow):
        for j in range(9):
            cell_fill(tbl.cell(r, j), None)
            cell_borders(tbl.cell(r, j), "", GRID)

    for lo in range(9):
        cell_fill(c(0, lo), HDR)
        lines = [(HEAD[lo], 8.5, True, WHITE)]
        if UNIT[lo]:
            lines.append((UNIT[lo], 6.8, False, RGBColor(0xA9, 0xC6, 0xEA)))
        cell_text(c(0, lo), lines, pad=(3, 3, 3, 3), wrap=True,
                  anchor=MSO_ANCHOR.BOTTOM)
        icon(sl, ICON[lo], (xs[lo] + xs[lo + 1]) / 2.0, TY + 9, 11)

    DASH = "\u2014"
    for k, blk in enumerate(BB):
        top = 1 + k * 5
        # the scenario strip. A merged cell comes out letter-spaced, so the
        # label sits in the rightmost cell of a row filled right across.
        for j in range(9):
            cell_fill(tbl.cell(top, j), NAVY)
            cell_borders(tbl.cell(top, j), "", NAVY)
            cell_text(tbl.cell(top, j), [(" ", 1, False, WHITE)], pad=(0, 0, 0, 0))
        for i, r in enumerate(blk["rows"]):
            rr = top + 1 + i
            fill = ROW1 if i % 2 == 0 else ROW2
            cell_fill(c(rr, 0), fill)
            cell_text(c(rr, 0), [(LABEL[r["b"]] + " تومان", 7.5, True, INK)],
                      align="r", pad=(1, 24, 1, 6))
            icon(sl, "person", RIGHT - 13, TY + HH + k * BLK + TH + i * RH + RH / 2,
                 11)
            vals = ([DASH] * 8 if not r["n"] else
                    [f(r["n"]), fa(int(round(100 * r["take"]))) + " درصد",
                     f(r["bor"]), d1(r["once"]), fa(r["rep"]) + " بار",
                     d1(r["tot"]), d3(100 * r["pd1"]) + " درصد", d2(r["loss"])])
            for j, v in enumerate(vals, start=1):
                key = (j == 6)
                cell_fill(c(rr, j), PICK if (key and r["n"]) else fill)
                cell_text(c(rr, j), [(v, 9.5 if key else 7.5, key,
                                      INK if key else INK2)], pad=(1, 3, 1, 3))
            for j in range(9):
                cell_borders(c(rr, j), "B", GRID)

        t = blk["tot"]
        sr = top + 4
        for j in range(9):
            cell_fill(tbl.cell(sr, j), HDR)
            cell_borders(tbl.cell(sr, j), "", HDR)
        cell_text(c(sr, 0), [("مجموع گزینه " + blk["nm"], 9, True, WHITE)],
                  align="r", pad=(1, 26, 1, 6))
        icon(sl, "calc", RIGHT - 14, TY + HH + k * BLK + TH + 3 * RH + SH / 2, 12)
        for j, v in enumerate([f(t["n"]), d1(100 * t["take"]) + " درصد",
                               f(t["bor"]), d1(t["once"]), DASH, d1(t["tot"]),
                               d3(100 * t["pd1"]) + " درصد", d2(t["loss"])], start=1):
            cell_text(c(sr, j), [(v, 10 if j == 6 else 8, True, WHITE)],
                      pad=(1, 3, 1, 3))

    for k, blk in enumerate(BB):                 # laid over the navy strips
        ty = TY + HH + k * BLK
        text(sl, M + 10, ty, RIGHT - M - 20, TH,
             [[("گزینه " + fa(k + 1) + "  ", 8, False, RGBColor(0xA9, 0xC6, 0xEA)),
               (blk["nm"], 9.5, True, WHITE),
               ("   " + blk["note"], 7.5, False, RGBColor(0xA9, 0xC6, 0xEA))]],
             align="r")

    # ---------------------------------------------------------------- notes
    AY = 462.0
    rect(sl, M, AY, RIGHT - M, 30, PILL, CARDBD, radius=0.3)
    icon(sl, "repeat_b", RIGHT - 21, AY + 15, 14)
    text(sl, M + 12, AY, RIGHT - M - 56, 30,
         [("تکرار وام تا پایان سال: سقف‌های ۳۰۰ و ۵۰۰ هزار دو بار، سقف ۱ میلیون "
           "یک بار  &nbsp;|&nbsp;  ضریب نفوذ به تفکیک باند ۱۵، ۱۳ و ۱۰ درصد  "
           "&nbsp;|&nbsp;  سقف میانی هر باند ۲۰۰، ۴۰۰ و ۷۵۰ هزار تومان"
           .replace("&nbsp;", " "), 8.5, True, NAVY)], align="r")

    text(sl, M, AY + 32, RIGHT - M, 30,
         [[("", 1, False, INK3), ("قاعدهٔ سقف می‌گوید وام باید از قبض یک ماه مشترک کمتر بماند، ولی فقط "
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

# -*- coding: utf-8 -*-
"""The deck as a .pptx.

Each slide goes in as one full-bleed 3840x2160 render of the HTML slide.
That is deliberate: LibreOffice cannot open a .pptx in this sandbox, so a
native-shape deck could not be proof-read before it was handed over, and
pptxgenjs writes tables without rtl="1", which lays Persian columns out
left to right. A render carries the typography and the RTL exactly as the
HTML does. The cost is that the text is not editable in PowerPoint - the
HTML stays the editable source.

Speaker notes and alt text carry the slide's words so the file is not a
black box to a screen reader or to a text dump.
"""
import os, subprocess, sys
from pptx import Presentation
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT  = os.path.join(ROOT, "outputs")
DECK = os.path.join(OUT, "dcb_slide_fa.html")
PPTX = os.path.join(OUT, "dcb_deck_fa.pptx")

NOTES = [
 ("مدل اعتبارسنجی — چطور کار می‌کند",
  "مدل روی یک دورهٔ گذشته آموزش دیده که نتیجه‌اش معلوم است: ویژگی‌ها از مهر تا "
  "اسفند ۱۴۰۴ و نتیجه از فروردین تا شهریور ۱۴۰۵. بد یعنی مشترکی که در آن پنجره "
  "به قطع دوطرفه رسید. امروز همان مدل روی ۶ ماه آخر هر مشترک اجرا می‌شود و "
  "احتمال نکول را می‌دهد. تفاوت ساختاری دو ردیف فقط جهت یک فلش است: در آموزش "
  "نتیجه وارد مدل می‌شود، در امتیازدهی پیش‌بینی از مدل بیرون می‌آید. "
  "۹٬۳۴۴٬۷۲۳ مشترک امتیاز می‌گیرند، در ۱۰ دهک مرتب می‌شوند، و با قاعدهٔ سقف "
  "(وام هر نفر کمتر از قبض یک ماهش) ۸٬۸۰۱٬۷۷۲ نفر تأیید می‌شوند. "
  "دقت مدل روی دادهٔ کنارگذاشته ۰٫۸۳."),
 ("مدل‌ها — چه چیزی آزموده شد و چه چیزی انتخاب شد",
  "دو مدل روی همان تفکیک آموزش دیدند. مبنا یک کارت امتیازی لجستیک روی "
  "ویژگی‌های WOE با AUC ۰٫۷۸۴۳ روی دادهٔ اعتبارسنجی؛ چالشگر گرادیان بوستینگ "
  "درختی (HistGradientBoosting، ۴۰۰ درخت، عمق ۵) با ۰٫۸۱۵۷. چالشگر ۰٫۰۳۱۴ بهتر "
  "بود و انتخاب شد. روی دادهٔ کنارگذاشته: AUC ۰٫۸۲۷۸، جینی ۰٫۶۵۵۷، KS ۰٫۵۱۵۱، "
  "خطای سطح کالیبراسیون ۱٫۷ درصد. آموزش روی ۸٬۷۰۱٬۰۸۵ سطر با ۴۵٬۳۶۱ مورد بد "
  "(۰٫۵۲ درصد) و ۳۹ ویژگی؛ تفکیک ۷۰ به ۳۰ با هش روی شناسهٔ مشترک؛ کالیبراسیون "
  "ایزوتونیک روی نیمی از اعتبارسنجی. بیشترین سهم از سابقهٔ قطع سرویس سال قبل "
  "است: ۰٫۰۲۳۹ از AUC، یعنی ۹۲ درصد کل بهبود بازآموزی. سه هشدار: رانش در ۱۲ "
  "ویژگی پس رتبه‌بندی معتبرتر از سطح است؛ کالیبراسیون در دهک‌های امن "
  "محافظه‌کار است؛ و سطح اعداد تا اجرای آزمایشی تأیید نمی‌شود."),
 ("سه گزینه اعطای اعتبار",
  "سه گزینه روی همان ۸٬۸۰۱٬۷۷۲ مشترک تأییدشده. ضریب نفوذ به تفکیک باند است: "
  "۱۵ درصد در ۱۰۰ تا ۳۰۰ هزار، ۱۳ درصد در ۳۰۰ تا ۵۰۰ هزار، ۱۰ درصد در ۵۰۰ هزار "
  "تا ۱ میلیون. با ۳ بار وام در سال: کم‌ریسک ۹۱۶ میلیارد و زیان ۱٫۱؛ محتاطانه "
  "۱٬۱۰۳ میلیارد و زیان ۱٫۲؛ گسترده ۱٬۴۱۷ میلیارد و زیان ۱٫۴. "
  "نرخ نکول وزن‌دار بر حسب مبلغ است نه تعداد نفرات، برای همین در گزینه گسترده "
  "پایین‌تر می‌آید. حتی گسترده فقط ۹ درصد هدف ۱۵٬۰۰۰ میلیاردی را پوشش می‌دهد. "
  "هشدار: فقط ۳۶۹٬۶۷۷ مشترک قبض بالای ۵۰۰ هزار تومان دارند."),
]

def main():
    node = "/opt/node22/bin/node" if os.path.exists("/opt/node22/bin/node") else "node"
    shots = subprocess.run(
        [node, os.path.join(HERE, "shoot_slides.mjs"), DECK, OUT, "dcb_slide_fa_"],
        check=True, capture_output=True, text=True).stdout.split()
    if len(shots) != len(NOTES):
        sys.exit("deck has %d slides but %d sets of notes" % (len(shots), len(NOTES)))

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    for png, (title, note) in zip(shots, NOTES):
        s   = prs.slides.add_slide(blank)
        pic = s.shapes.add_picture(png, 0, 0, prs.slide_width, prs.slide_height)
        # alt text, so the slide is not silent to a screen reader
        cNvPr = pic._element.nvPicPr.cNvPr
        cNvPr.set("name", title)
        cNvPr.set("descr", note)
        s.notes_slide.notes_text_frame.text = title + "\n\n" + note
    prs.save(PPTX)
    print("wrote", PPTX, os.path.getsize(PPTX), "bytes,", len(prs.slides.__iter__.__self__._sldIdLst), "slides")

if __name__ == "__main__":
    main()

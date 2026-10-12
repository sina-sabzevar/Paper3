# -*- coding: utf-8 -*-
"""The model schematic, as one inline SVG, shared by the standalone page and
by the first slide of the deck so the two cannot drift apart.

The thing prose cannot carry is that the model is fitted on a PAST window
whose answer is already known, and then the same recipe is run on the six
months ending today, where it is not. So the picture is two parallel rows
over the same three columns, and the only structural difference between
them is which way the left arrow points: in training the outcome goes IN,
in scoring the prediction comes OUT. A third strip carries the score to
the approved count, which is where the options table picks it up.
"""
import io

_FA = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹",
       ",":"٬", ".":"٫"}
def fa(t): return "".join(_FA.get(c, c) for c in str(t))
def f(n):  return fa("{:,}".format(int(n)))

APPROVED, DECILE, SCORED, BASE = 8_801_772, 934_472, 9_344_723, 41_270_092

# ---- geometry. Three columns shared by both rows, so the two rows line up
#      and the comparison is readable at a glance.
L, R       =  40, 1240                 # content edges
IN0, IN1   = 920, 1240                 # ورودی
MD0, MD1   = 550,  790                 # مدل
OU0, OU1   =  40,  420                 # خروجی
INC, MDC, OUC = (IN0+IN1)//2, (MD0+MD1)//2, (OU0+OU1)//2
GR, GL = (MD1+IN0)//2, (OU1+MD0)//2    # the two gaps
H = 556

# svg-only rules. The host page owns the palette variables.
CSS = r"""
/* every rule is scoped to the svg: the deck slide that embeds this drawing
   has its own .sub and must not inherit the drawing's */
svg text{font-family:var(--fa);direction:rtl}
svg .bx{fill:var(--panel);stroke:var(--line);stroke-width:1}
svg .mdl{fill:color-mix(in srgb,var(--s1) 13%,var(--panel));
     stroke:var(--s1);stroke-width:1.5}
svg .out{fill:color-mix(in srgb,var(--s1) 9%,var(--panel));
     stroke:color-mix(in srgb,var(--s1) 45%,var(--line));stroke-width:1.5}
svg .ar{stroke:var(--ink-2);stroke-width:1.6;fill:none}
svg .dash{stroke:var(--s1);stroke-width:1.4;stroke-dasharray:5 4;fill:none;opacity:.75}
svg .srule{stroke:var(--line);stroke-width:1}
svg .ttl{font-size:15.5px;font-weight:600;fill:var(--ink)}
svg .sub{font-size:12.5px;fill:var(--ink-2)}
svg .tag{font-size:11.5px;fill:var(--ink-3)}
svg .al{font-size:11.5px;fill:var(--ink-3)}
svg .sec{font-size:12.5px;font-weight:600;fill:var(--ink-3)}
svg .big{font-size:25px;font-weight:700;fill:var(--s1)}
svg .mt{font-size:15.5px;font-weight:600;fill:var(--s1)}
"""

CAPTION = ("تفاوت ساختاری دو ردیف بالا فقط در جهت یک فلش است: "
  "<b>در آموزش، نتیجه وارد مدل می‌شود؛ در امتیازدهی، پیش‌بینی از مدل بیرون می‌آید.</b> "
  "ورودی هر دو ردیف یکی است &mdash; ۶ ماه رفتار حساب و همان ۳۹ ویژگی &mdash; و همین "
  "است که اجازه می‌دهد عملکرد اندازه‌گیری‌شده روی گذشته به امروز تعمیم داده شود. "
  "دقت مدل روی دادهٔ کنارگذاشته <b>۰٫۸۳</b> است.")

FOOTNOTE = ("۳۹ ویژگی، همه از رفتار حساب خود مشترک &mdash; مصرف و درآمد، رفتار "
  "پرداخت، بدهی و اعتبار باز، سابقهٔ قطع سرویس، قدمت خط. هیچ داده شخصی، مکانی یا "
  "جمعیتی در مدل نیست&#1563; پنجرهٔ نتیجه ۶ ماه است: ۴ قبضی که اقساط رویشان "
  "می‌نشیند، به‌علاوهٔ ۲ ماه مهلت تا قسط آخر هم دیده شود&#1563; «قطع دوطرفه» "
  "حدود سه ماه بعد از شروع عدم پرداخت رخ می‌دهد، پس نشانهٔ دیررسی است: خرابی‌های "
  "اواخر پنجره دیده نمی‌شوند و نرخ بد کمتر از واقع برآورد می‌شود&#1563; "
  "مدل، درخت‌های تصمیم تقویت‌شده با کالیبراسیون است.")

ARIA = ("مدل روی رفتار شش ماههٔ ۱۴۰۴ و نتیجهٔ شش ماه بعد آموزش دیده، سپس همان "
  "مدل روی رفتار شش ماه آخر اجرا می‌شود و احتمال نکول هر مشترک را می‌دهد؛ "
  "مشترکین در ده دهک مرتب می‌شوند و با قاعدهٔ سقف، هشت میلیون و هشتصد هزار "
  "نفر تأیید می‌شوند")


def svg():
    out = io.StringIO(); W = out.write
    def box(x0, x1, y, h, cls="bx"):
        W('<rect class="%s" x="%d" y="%d" width="%d" height="%d" rx="8"/>'
          % (cls, x0, y, x1-x0, h))
    def t(x, y, s, cls="sub"):
        W('<text class="%s" x="%d" y="%d" text-anchor="middle">%s</text>' % (cls, x, y, s))
    def arrow(x0, x1, y):
        W('<line class="ar" x1="%d" y1="%d" x2="%d" y2="%d" marker-end="url(#ar)"/>'
          % (x0, y, x1, y))
    def sec(y, s):
        W('<text class="sec" x="%d" y="%d" text-anchor="start">%s</text>' % (R, y, s))
        W('<line class="srule" x1="%d" y1="%d" x2="%d" y2="%d"/>' % (L, y+10, R, y+10))

    W('<svg viewBox="0 0 1280 %d" role="img" aria-label="%s">' % (H, ARIA))
    W('<defs><marker id="ar" viewBox="0 0 10 10" refX="9.5" refY="5"'
      ' markerWidth="6" markerHeight="6" orient="auto">'
      '<path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>')

    # ---------- ۱ آموزش ----------
    sec(18, "۱   مدل چطور یاد گرفت")
    box(IN0, IN1, 40, 124)
    t(INC,  78, "رفتار ۶ ماههٔ مشترک", "ttl")
    t(INC, 102, "مهر تا اسفند ۱۴۰۴")
    t(INC, 126, "۳۹ ویژگی از حساب خودش", "tag")

    box(MD0, MD1, 40, 124, "mdl")
    t(MDC,  94, "آموزش مدل", "mt")
    t(MDC, 118, "روی همین دوره", "tag")

    box(OU0, OU1, 40, 124)
    t(OUC,  78, "نتیجهٔ ۶ ماه بعد", "ttl")
    t(OUC, 102, "فروردین تا شهریور ۱۴۰۵")
    t(OUC, 126, "بد = مشترکی که به قطع دوطرفه رسید", "tag")

    arrow(IN0-4, MD1+4, 102); t(GR, 86, "ویژگی‌ها", "al")
    arrow(OU1+4, MD0-4, 102); t(GL, 86, "جوابِ درست", "al")
    t(OUC, 182, "در این دوره جواب معلوم است &mdash; مدل همین را یاد می‌گیرد", "tag")

    # ---------- ۲ امتیازدهی ----------
    sec(214, "۲   امروز چطور کار می‌کند")
    box(IN0, IN1, 236, 124)
    t(INC, 274, "رفتار ۶ ماههٔ مشترک", "ttl")
    t(INC, 298, "فروردین تا شهریور ۱۴۰۵")
    t(INC, 322, "همان ۳۹ ویژگی", "tag")

    box(MD0, MD1, 236, 124, "mdl")
    t(MDC, 290, "همان مدل", "mt")
    t(MDC, 314, "بدون تغییر", "tag")

    box(OU0, OU1, 236, 124, "out")
    t(OUC, 274, "احتمال نکول هر مشترک", "ttl")
    t(OUC, 298, "برای هر یک از " + f(SCORED) + " مشترک")
    t(OUC, 322, "از " + fa("{:.1f}".format(BASE/1e6)) +
                " میلیون مشترک دائمی، پس از غربال", "tag")

    arrow(IN0-4, MD1+4, 298); t(GR, 282, "ویژگی‌ها", "al")
    arrow(MD0-4, OU1+4, 298); t(GL, 282, "پیش‌بینی", "al")
    t(OUC, 378, "در این دوره جواب معلوم نیست &mdash; مدل آن را می‌گوید", "tag")

    W('<line class="dash" x1="%d" y1="164" x2="%d" y2="232" marker-end="url(#ar)"/>'
      % (MDC, MDC))

    # ---------- ۳ تصمیم ----------
    sec(412, "۳   امتیاز چطور به تصمیم تبدیل می‌شود")
    box(820, 1240, 434, 108)
    t(1030, 474, "۱۰ دهک، از کم‌ریسک به پرریسک", "ttl")
    t(1030, 500, "هر دهک " + f(DECILE) + " مشترک")

    arrow(816, 464, 488)
    t(660, 472, "قاعدهٔ سقف", "al")
    t(660, 506, "وام هر نفر کمتر از قبض یک ماهش", "al")

    box(40, 460, 434, 108, "out")
    t(250, 478, f(APPROVED), "big")
    t(250, 506, "مشترک تأییدشده &mdash; سقف ۱۰۰ هزار تا ۱ میلیون تومان")

    W('</svg>')
    return out.getvalue()

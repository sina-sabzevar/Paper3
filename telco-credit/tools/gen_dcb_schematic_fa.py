# -*- coding: utf-8 -*-
"""The standalone schematic page. The drawing itself lives in
dcb_schematic_svg so the deck's first slide draws exactly the same thing.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dcb_schematic_svg as S

HTML = """<title>شماتیک مدل اعتبارسنجی</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&amp;display=swap">
<style>
:root{
  --plane:#ffffff; --panel:#f6f6f3; --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.10); --line:#d9d8d2; --s1:#2a78d6;
  --fa:"Vazirmatn","Noto Sans Arabic",Tahoma,system-ui,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0e0e10; --panel:#191a1d; --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.12); --line:#34342f; --s1:#3987e5;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0e0e10; --panel:#191a1d; --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.12); --line:#34342f; --s1:#3987e5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);font-family:var(--fa);
  direction:rtl;-webkit-font-smoothing:antialiased;
  padding:clamp(20px,3.4vw,52px) clamp(16px,3.4vw,56px)}
h1{margin:0 0 4px;font-size:clamp(19px,2.4vw,27px);font-weight:700}
.lede{margin:0 0 clamp(16px,2vw,26px);font-size:clamp(13px,1.25vw,15px);
  color:var(--ink-3);line-height:1.75;max-width:70ch}
figure{margin:0}
svg{display:block;width:100%;max-width:1280px;height:auto;color:var(--ink-2)}
__SVGCSS__
figcaption{margin-top:clamp(14px,1.8vw,24px);font-size:clamp(12px,1.15vw,14px);
  color:var(--ink-2);line-height:1.85;max-width:88ch;
  padding-top:14px;border-top:1px solid var(--rule)}
figcaption b{color:var(--ink)}
.fn{margin:10px 0 0;font-size:clamp(11px,1.05vw,12.5px);color:var(--ink-3);line-height:1.8}
</style>

<h1>مدل اعتبارسنجی &mdash; شماتیک</h1>
<p class="lede">مدل روی یک دورهٔ گذشته ساخته شده که می‌دانیم آخرش چه شد؛ بعد
همان دستور روی ۶ ماه آخر هر مشترک اجرا می‌شود.</p>
<figure>
__SVG__
<figcaption>__CAP__</figcaption>
<p class="fn">__FN__</p>
</figure>
"""

html = (HTML.replace("__SVGCSS__", S.CSS.strip())
            .replace("__SVG__", S.svg())
            .replace("__CAP__", S.CAPTION)
            .replace("__FN__", S.FOOTNOTE))

dst = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "outputs", "dcb_schematic_fa.html")
open(dst, "w", encoding="utf-8").write(html)
print("wrote", os.path.normpath(dst), len(html), "bytes")

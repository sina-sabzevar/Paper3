# -*- coding: utf-8 -*-
"""The shared look for the DCB pages. One copy, so the deck and the workbook
cannot drift apart. EXTRA is for styles only one page needs; it lands inside
the same <style> block, after the shared rules."""

_SHARED = r"""
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Layout: a presentation surface - wide bands, big figures, one idea per band,
   readable from across a meeting room. */
:root{
  --plane:#f6f6f3; --surface:#fdfdfc; --raise:#eeeeea; --sunk:#e6e6e0;
  --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.09); --grid:#e1e0d9; --axis:#c3c2b7;
  --s1:#2a78d6; --s2:#eb6834;
  --o1:#86b6ef; --o2:#3987e5; --o3:#256abf; --o4:#104281;
  --good:#0ca30c; --good-ink:#006300; --warn:#fab219; --crit:#d03b3b;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --good:#0ca30c; --good-ink:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --o1:#184f95; --o2:#2a78d6; --o3:#86b6ef; --o4:#cde2fb;
  --good:#0ca30c; --good-ink:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}
*{box-sizing:border-box}
body{background:var(--plane);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.5;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding-inline:22px;padding-block:36px 72px}
h1,h2,h3{margin:0;text-wrap:balance}
h1{font-size:clamp(30px,5.4vw,46px);font-weight:700;letter-spacing:-0.025em;line-height:1.08}
h2{font-size:clamp(20px,3.2vw,26px);font-weight:600;letter-spacing:-0.015em}
h3{font-size:15px;font-weight:600}
p{margin:0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.eyebrow{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:0.12em;
  text-transform:uppercase;color:var(--ink-3)}

header{display:flex;flex-direction:column;gap:14px;padding-bottom:10px}
.lede{color:var(--ink-2);font-size:17px;max-width:64ch}
.spec{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.chip{font-family:var(--mono);font-size:12.5px;background:var(--raise);
  border:1px solid var(--rule);border-radius:999px;padding:4px 12px;color:var(--ink-2)}
.chip b{color:var(--ink);font-weight:600}

section{margin-top:40px}
.head{border-top:2px solid var(--ink);padding-top:14px;margin-bottom:18px;
  display:flex;flex-direction:column;gap:7px}
.head p{color:var(--ink-2);font-size:15px;max-width:66ch}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:22px 20px}
.card + .card{margin-top:14px}
.cap{color:var(--ink-3);font-size:13px;line-height:1.55;margin-top:16px;max-width:72ch}
.cap b{color:var(--ink-2);font-weight:500}

.hero{background:var(--surface);border:1px solid var(--rule);border-radius:8px;
  padding:26px 22px;display:flex;flex-wrap:wrap;gap:26px 40px;align-items:flex-end}
.hero .big{display:flex;flex-direction:column;gap:4px}
.hero .big .v{font-family:var(--mono);font-size:clamp(38px,8vw,64px);font-weight:600;
  letter-spacing:-0.03em;line-height:0.98}
.hero .big .k{font-size:14px;color:var(--ink-2)}
.hero .sub{color:var(--ink-2);font-size:15px;max-width:38ch;flex:1 1 280px}

.kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);}
.kpi.k6{grid-template-columns:repeat(3,minmax(0,1fr))}
.kpi{
  border:1px solid var(--rule);border-radius:8px;overflow:hidden}
@media (max-width:760px){.kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{background:var(--surface);padding:16px 17px 18px;display:flex;flex-direction:column;gap:6px}
.tile .k{font-family:var(--mono);font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:var(--ink-3)}
.tile .v{font-family:var(--mono);font-size:clamp(21px,3.2vw,27px);font-weight:600;letter-spacing:-0.02em;line-height:1}
.tile .s{font-size:12.5px;color:var(--ink-3);line-height:1.4}

table{border-collapse:collapse;width:100%;font-size:14px;min-width:420px}
.tbl-s{overflow-x:auto;margin-top:6px}
th,td{text-align:right;padding:9px 11px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:0.07em;text-transform:uppercase;
  color:var(--ink-3);font-weight:500;border-bottom:1px solid var(--axis)}
tbody td{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--ink-2)}
tbody td:first-child{font-family:var(--sans);color:var(--ink);font-weight:500}
tr.off td{color:var(--ink-3)}
tr.tot td{font-weight:600;color:var(--ink);border-top:1px solid var(--axis);border-bottom:none}
tfoot td{font-family:var(--sans);font-size:13px;color:var(--ink-3);white-space:normal;
  text-align:left;border-bottom:none;padding-top:12px;line-height:1.55}
tfoot b{color:var(--ink-2);font-weight:500}

/* the ticket-by-bill grid */
.grid{display:grid;gap:2px;margin-top:4px;min-width:430px}
.gcell{padding:9px 6px;border-radius:4px;text-align:center;
  font-family:var(--mono);font-size:12.5px;line-height:1.35}
.gcell b{display:block;font-weight:600;font-size:13px}
.gcell .sh{font-size:11px;opacity:0.75}
.ghead{padding:6px;text-align:center;font-family:var(--mono);font-size:10.5px;
  letter-spacing:0.06em;text-transform:uppercase;color:var(--ink-3)}
.grow{padding:9px 8px;font-family:var(--mono);font-size:12px;text-align:right;
  color:var(--ink-2);white-space:nowrap}
.grow em{font-style:normal;color:var(--ink-3);font-size:10.5px;display:block}
.g1{background:color-mix(in srgb,var(--good) 16%,var(--surface));color:var(--ink)}
.g2{background:color-mix(in srgb,var(--warn) 26%,var(--surface));color:var(--ink)}
.g3{background:color-mix(in srgb,var(--crit) 20%,var(--surface));color:var(--ink)}
.glegend{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:12px;font-size:12.5px;color:var(--ink-2)}
.glegend span{display:flex;align-items:center;gap:7px}
.glegend i{width:12px;height:12px;border-radius:3px;display:block}
.svgbox{overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.gl{stroke:var(--grid);stroke-width:1}
.ax{stroke:var(--axis);stroke-width:1}
.tk{fill:var(--ink-3);font-family:var(--mono);font-size:11px}
.dl{font-family:var(--mono);font-size:12.5px;font-weight:600}
.an{font-family:var(--sans);font-size:12px;fill:var(--ink-3)}

.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.split{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:20px 18px}
.panel.known{border-left:3px solid var(--good)}
.panel.unknown{border-left:3px solid var(--crit)}
.panel h3{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.panel ul{margin:0;padding-left:0;list-style:none;display:flex;flex-direction:column;gap:11px}
.panel li{font-size:14px;color:var(--ink-2);line-height:1.5;padding-left:16px;position:relative}
.panel li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:1.5px;background:var(--ink-3)}
.panel li b{color:var(--ink);font-weight:600}

.ask{display:flex;flex-direction:column;gap:0}
.q{display:flex;gap:16px;padding:16px 0;border-bottom:1px solid var(--rule)}
.q:last-child{border-bottom:none}
.q .n{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ink-3);flex:0 0 24px;padding-top:2px}
.q .b{min-width:0}
.q .b h3{margin-bottom:4px}
.q .b p{font-size:14px;color:var(--ink-2)}
a{color:var(--s1)}
code{font-family:var(--mono);font-size:13px;background:var(--raise);padding:1px 5px;border-radius:4px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);color:var(--ink-3);font-size:12.5px;
  display:flex;flex-direction:column;gap:6px}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
__EXTRA__</style>

<div class="wrap">
"""

def head(title, extra=""):
    return "<title>" + title + "</title>" + _SHARED.replace("__EXTRA__", extra)

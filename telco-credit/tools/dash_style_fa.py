# -*- coding: utf-8 -*-
"""The Persian look, kept in one place so the static page and the
editable one cannot drift apart. Persian script connects, so there is no
letter-spacing anywhere, and every edge rule is a logical property."""

CSS = r"""<style>
/* A Persian presentation surface. Same palette as the Latin pages; the
   typography is rebuilt, because Persian script connects and the Latin
   pages space their labels apart. */
:root{
  --plane:#f6f6f3; --surface:#fdfdfc; --raise:#eeeeea; --sunk:#e6e6e0;
  --ink:#0b0b0b; --ink-2:#4e4d4a; --ink-3:#86857f;
  --rule:rgba(11,11,11,0.09); --grid:#e1e0d9; --axis:#c3c2b7;
  --s1:#2a78d6; --s2:#eb6834;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --fa:"Vazirmatn","Noto Sans Arabic",Tahoma,"Iranian Sans",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --plane:#0c0c0d; --surface:#17171a; --raise:#202024; --sunk:#131316;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-3:#8a8980;
  --rule:rgba(255,255,255,0.10); --grid:#2c2c2a; --axis:#3a3a37;
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}
*{box-sizing:border-box}
body{background:var(--plane);color:var(--ink);font-family:var(--fa);
  font-size:16px;line-height:1.85;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding-inline:22px;padding-block:36px 72px}
h1,h2,h3{margin:0;text-wrap:balance;line-height:1.5}
h1{font-size:clamp(27px,5vw,42px);font-weight:700}
h2{font-size:clamp(20px,3.2vw,26px);font-weight:700}
h3{font-size:16px;font-weight:600}
p{margin:0}
/* Latin digits inside Persian prose: isolate them so the bidi algorithm
   cannot reorder a number, its comma and the word beside it. */
bdi{font-family:inherit;font-variant-numeric:tabular-nums;unicode-bidi:isolate}
/* NO letter-spacing and NO uppercase anywhere: Persian letters join, and
   spacing them apart breaks the word into disconnected shapes. */
.eyebrow{font-size:13px;font-weight:500;color:var(--ink-3)}

header{display:flex;flex-direction:column;gap:14px;padding-bottom:10px}
.lede{color:var(--ink-2);font-size:17px;max-width:62ch}
.spec{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.chip{font-size:13.5px;background:var(--raise);border:1px solid var(--rule);
  border-radius:999px;padding:5px 14px;color:var(--ink-2)}
.chip b{color:var(--ink);font-weight:600}

section{margin-top:40px}
.head{border-top:2px solid var(--ink);padding-top:14px;margin-bottom:18px;
  display:flex;flex-direction:column;gap:7px}
.head p{color:var(--ink-2);font-size:15px;max-width:64ch}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:22px 20px}
.card + .card{margin-top:14px}
.cap{color:var(--ink-3);font-size:13.5px;line-height:1.85;margin-top:16px;max-width:70ch}
.cap b{color:var(--ink-2);font-weight:600}

.kpi{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:8px;overflow:hidden}
@media (max-width:760px){.kpi{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tile{background:var(--surface);padding:16px 17px 18px;display:flex;flex-direction:column;gap:6px}
.tile{justify-content:flex-start}
.tile .k{font-size:12.5px;color:var(--ink-3);line-height:1.5;min-height:2.6em}
.tile .v{font-size:clamp(20px,3.2vw,26px);font-weight:600;line-height:1.3}
.tile .v bdi{font-weight:600}
.tile .s{font-size:12.5px;color:var(--ink-3);line-height:1.6}

table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:480px}
.tbl-s{overflow-x:auto;margin-top:6px}
/* logical alignment, so the label column sits at the start in either direction */
th,td{text-align:end;padding:11px 12px;border-bottom:1px solid var(--rule);white-space:nowrap}
th:first-child,td:first-child{text-align:start;white-space:normal}
thead th{font-size:12.5px;color:var(--ink-3);font-weight:500;
  border-bottom:1px solid var(--axis)}
tbody td{color:var(--ink-2)}
tbody td:first-child{color:var(--ink);font-weight:500}
tr.off td{color:var(--ink-3)}
tr.tot td{font-weight:700;color:var(--ink);border-top:1px solid var(--axis);border-bottom:none}
tfoot td{font-size:13.5px;color:var(--ink-3);white-space:normal;
  text-align:start;border-bottom:none;padding-top:14px;line-height:1.85}
tfoot b{color:var(--ink-2);font-weight:600}

.fun{display:flex;flex-direction:column;gap:3px}
.fstep{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:center;
  padding:12px 15px;border-radius:6px;background:var(--raise);min-width:0}
.fstep.keep{background:color-mix(in srgb,var(--s1) 14%,var(--surface))}
.fstep.last{background:color-mix(in srgb,var(--good) 16%,var(--surface))}
.fstep .t{font-size:15px;color:var(--ink);min-width:0}
.fstep .t em{font-style:normal;display:block;color:var(--ink-3);font-size:13px;margin-top:1px}
.fstep .v{font-size:18px;font-weight:700;white-space:nowrap}
.fdrop{display:grid;grid-template-columns:1fr auto;gap:14px;
  padding-block:5px;padding-inline-start:30px;padding-inline-end:15px;
  font-size:13px;color:var(--ink-3)}
.fdrop .v{white-space:nowrap}

.rule{display:flex;flex-wrap:wrap;gap:20px 36px;align-items:center;
  background:color-mix(in srgb,var(--good) 11%,var(--surface));
  border:1px solid color-mix(in srgb,var(--good) 40%,var(--rule));
  border-radius:8px;padding:26px 24px}
.rule .big{font-size:clamp(20px,3.4vw,27px);font-weight:700;line-height:1.6;
  flex:1 1 300px;min-width:0;text-wrap:balance}
.rule .why{font-size:14.5px;color:var(--ink-2);line-height:1.9;flex:1 1 280px;min-width:0}

.steps{display:flex;flex-direction:column;gap:0;margin-top:4px}
.stp{display:grid;grid-template-columns:30px 1fr;gap:14px;padding:16px 0;
  border-bottom:1px solid var(--rule)}
.stp:last-child{border-bottom:none}
.stp .n{font-family:var(--mono);font-size:15px;font-weight:600;color:var(--s1)}
.stp h3{margin-bottom:4px}
.stp p{font-size:14.5px;color:var(--ink-2);line-height:1.9}

.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.split{grid-template-columns:1fr}}
.split > *{min-width:0}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:20px 18px}
.panel.unknown{border-inline-start:3px solid var(--crit)}
.panel h3{display:flex;align-items:center;gap:9px;margin-bottom:12px}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;background:var(--crit)}
.panel ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
.panel li{font-size:14.5px;color:var(--ink-2);line-height:1.9;
  padding-inline-start:16px;position:relative}
.panel li::before{content:"";position:absolute;inset-inline-start:0;top:12px;
  width:7px;height:1.5px;background:var(--ink-3)}
.panel li b{color:var(--ink);font-weight:600}
.gr{font-family:var(--mono);font-weight:600}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);
  color:var(--ink-3);font-size:13px;display:flex;flex-direction:column;gap:8px;line-height:1.85}
a{color:var(--s1)}
:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>"""

// Persian RTL deck for the DCB programme. Same figures as the dashboards.
//
// Tahoma is written into the file on purpose: it ships with Windows and
// Office and shapes Persian correctly everywhere this will be opened. The
// QA render here substitutes Noto Sans Arabic for it.
//
// Tables are written with their columns REVERSED. PowerPoint has no
// table-level RTL that pptxgenjs exposes, so the label column is placed last
// in order to land on the right, where a Persian reader starts.
const pptxgen = require("pptxgenjs");
const path = require("path");

const OUT = path.join(__dirname, "..", "outputs", "dcb_fa.pptx");

// ---- the project palette, carried over from the dashboards
const THEME = {
  name: "DCB", headFontFace: "Tahoma", bodyFontFace: "Tahoma",
  colors: { dk1:"0B0B0B", lt1:"FFFFFF", dk2:"4E4D4A", lt2:"F6F6F3",
            accent1:"2A78D6", accent2:"EB6834", accent3:"0CA30C",
            accent4:"FAB219", accent5:"D03B3B", accent6:"86857F",
            hlink:"2A78D6", folHlink:"86857F" } };
const INK="0B0B0B", INK2="4E4D4A", INK3="86857F", PLANE="F6F6F3",
      LINE="DEDEDA", BLUE="2A78D6", GOOD="0CA30C", WARN="FAB219",
      CRIT="D03B3B", DARK="141416", DARKI="FFFFFF", DARK2="C3C2B7";

// ---- Persian digits, separators and the figures themselves
const FA = "۰۱۲۳۴۵۶۷۸۹";
const fa = t => String(t).replace(/[0-9]/g, d => FA[+d]).replace(/,/g,"٬").replace(/\./g,"٫");
const n  = v => fa(v.toLocaleString("en-US"));
const d1 = v => fa(v.toFixed(1));
const d2 = v => fa(v.toFixed(2));

const GRADES=[["A",3029397,0.001417,400000,"کم‌ریسک‌ترین"],["B",4087448,0.003298,300000,""],
              ["C",1085787,0.007387,150000,""],["D",599140,0.013538,100000,""],
              ["E",542951,0.040000,0,"رد می‌شود"]];
const SCORED=9344723;
const APPROVED=GRADES.filter(g=>g[3]>0).reduce((s,g)=>s+g[1],0);
const OUTST=GRADES.reduce((s,g)=>s+g[1]*g[3],0);
const AVGLIM=OUTST/APPROVED, ANNUAL=OUTST*12/1e9;
const LOSS_LO=ANNUAL*0.0009, LOSS_HI=ANNUAL*0.0014, LOSS_MID=(LOSS_LO+LOSS_HI)/2;
const RISKT=GRADES.filter(g=>g[3]>0).reduce((s,g)=>s+g[1]*g[3]*g[2],0);

const FUNNEL=[["همه مشترکین دائمی","نقطه شروع",41270092],
  ["قبض کافی دارند","۱۷۰٬۰۰۰ تومان در ۲ ماه از ۶ ماه",10087975],
  ["قطع یک‌طرفه نشده‌اند","در تمام شش ماه",9437240],
  ["قطع دوطرفه نشده‌اند","در تمام شش ماه",9344723],
  ["امتیازشان کافی است","مدل پرریسک‌ترین رتبه را رد می‌کند",APPROVED]];

const SHOCK=[["قبض تقریباً تکان نمی‌خورد","کمتر از ۱٫۲۵","۱٫۰۰",INK3],
             ["بالا می‌رود، زیر دو برابر","۱٫۲۵ تا ۲٫۰۰","۱٫۱۳",WARN],
             ["دو برابر یا بیشتر","۲٫۰۰ و بالاتر","۱٫۹۱",CRIT]];
const STRESS=[["مطابق مدل",1.00],["با رانش جمعیت فعلی",1.157],
              ["وام‌دهی در آستانه نوروز",1.68],["دو برابر نرخ مدل",2.00]];

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                 // 13.3 x 7.5
pres.rtlMode = true;
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Sina Sabzevar";
pres.title  = "اعتبار روی قبض";

const R = { rtlMode:true, align:"right", isTextBox:true };   // every text run
const M = 0.62;                                              // side margin
const W = 13.3 - 2*M;

pres.defineSlideMaster({ title:"DARK", background:{ color:DARK } });
pres.defineSlideMaster({ title:"LIGHT", background:{ color:"FFFFFF" },
  objects:[{ text:{ text:"اعتبار روی قبض · ۱۴۰۵",
    options:{ x:M, y:6.92, w:4, h:0.3, fontSize:10, color:INK3, ...R, align:"left", margin:0 } } }],
  slideNumber:{ x:12.3, y:6.92, w:0.4, h:0.3, fontSize:10, color:INK3, align:"right" } });

// a title that sits in the same place on every content slide
function head(s, t, sub) {
  s.addText(t, { x:M, y:0.42, w:W, h:0.6, fontSize:30, bold:true, color:INK, ...R, margin:0 });
  if (sub) s.addText(sub, { x:M, y:1.08, w:W, h:0.42, fontSize:14, color:INK2, ...R, margin:0 });
}
// a table, with its columns reversed so the labels land on the right
function rtlTable(s, header, rows, opts) {
  const rev = a => a.slice().reverse();
  const head = rev(header).map(c => ({ text:c,
    options:{ bold:true, color:INK3, fontSize:11, align:"right", fill:{color:"FFFFFF"} } }));
  const body = rows.map(r => rev(r).map(c => {
    const o = (typeof c === "object") ? c : { text:c, options:{} };
    return { text:o.text, options:{ color:INK2, fontSize:12.5, align:"right", ...(o.options||{}) } };
  }));
  s.addTable([head, ...body], { rtlMode:true, border:{type:"solid",color:LINE,pt:0.5},
    fontFace:"Tahoma", valign:"middle", ...opts });
}

// ------------------------------------------------- 1. title
let s = pres.addSlide({ masterName:"DARK" });
s.addText("اعتبار روی قبض", { x:M, y:1.95, w:W, h:1.15, fontSize:52, bold:true,
  color:DARKI, ...R, margin:0 });
s.addText("وام‌دادن به مشترک روی قبض ماه بعدش", { x:M, y:3.1, w:W, h:0.6,
  fontSize:22, color:DARK2, ...R, margin:0 });
s.addText("مشترک روی قبض تلفن همراهش اعتبار می‌گیرد و در قبض ماه بعد بازپرداخت می‌کند. "
  + "هر مشترک امتیازدهی می‌شود، سقف اعتبارش متناسب با امتیازش تعیین می‌شود، "
  + "و پرریسک‌ترین‌ها رد می‌شوند.",
  { x:M, y:3.85, w:8.4, h:1.1, fontSize:14, color:DARK2, lineSpacing:26, ...R, margin:0 });
[["دوره بازپرداخت","یک ماه"],["سقف اعتبار","۱۰۰ تا ۴۰۰ هزار تومان"],
 ["مشترکین تأییدشده",n(APPROVED)]].forEach(([k,v],i)=>{
  const x = M + i*(W/3);
  s.addText(k, { x, y:5.35, w:W/3-0.3, h:0.28, fontSize:11, color:INK3, ...R, margin:0 });
  s.addText(v, { x, y:5.63, w:W/3-0.3, h:0.4, fontSize:17, bold:true, color:DARKI, ...R, margin:0 });
});
s.addNotes("طرح اعتبار روی قبض. دوره یک‌ماهه، سقف بین ۱۰۰ تا ۴۰۰ هزار تومان، "
  + "بر پایه مدل امتیازدهی بازآموزی‌شده در مهر ۱۴۰۵.");

// ------------------------------------------------- 2. the headline numbers
s = pres.addSlide({ masterName:"LIGHT" });
head(s, "اعداد کلیدی");
const KPI=[["مشترکین تأییدشده",n(APPROVED),"۹۴ درصد از کل امتیازدهی‌شده‌ها",BLUE],
           ["میانگین سقف اعتبار (تومان)",n(Math.round(AVGLIM)),"بر اساس امتیاز خود مشترک",BLUE],
           ["اعطایی در یک سال (میلیارد تومان)",n(Math.round(ANNUAL)),
            "۲۱۳ درصد از هدف ۱۵٬۰۰۰ میلیاردی",GOOD],
           ["زیان مورد انتظار (میلیارد تومان)",d1(LOSS_LO)+" تا "+d1(LOSS_HI),
            "در سال، با فرض هیچ وصولی",CRIT]];
KPI.forEach(([k,v,sub,col],i)=>{
  const w=(W-3*0.26)/4, x=M+i*(w+0.26);
  s.addShape(pres.ShapeType.roundRect, { x, y:1.85, w, h:2.35, rectRadius:0.07,
    fill:{ color:PLANE }, line:{ color:LINE, width:0.75 },
    shadow:{ type:"outer", color:"000000", opacity:0.05, blur:8, offset:1, angle:90 } });
  s.addText(k, { x:x+0.22, y:2.02, w:w-0.44, h:0.52, fontSize:11, color:INK3,
    lineSpacing:15, valign:"top", ...R, margin:0 });
  s.addText(v, { x:x+0.22, y:2.58, w:w-0.44, h:0.68, fontSize:24, bold:true, color:col,
    valign:"middle", ...R, margin:0 });
  s.addText(sub, { x:x+0.22, y:3.32, w:w-0.44, h:0.72, fontSize:11, color:INK3,
    lineSpacing:16, valign:"top", ...R, margin:0 });
});
s.addText([{ text:"در هر لحظه فقط ", options:{ color:INK2 } },
           { text:n(Math.round(OUTST/1e8)/10)+" میلیارد تومان", options:{ bold:true, color:INK } },
           { text:" نزد مشترکین است؛ همان پول دوازده بار در سال برمی‌گردد و دوباره اعطا می‌شود.",
             options:{ color:INK2 } }],
  { x:M, y:4.55, w:W, h:0.5, fontSize:15, ...R, margin:0 });
s.addNotes("تفاوت مانده و اعطای سالانه دوازده برابر است. هدف ۱۵٬۰۰۰ میلیاردی باید روشن شود "
  + "که کدام‌یک را می‌گوید.");

// ------------------------------------------------- 3. the funnel
s = pres.addSlide({ masterName:"LIGHT" });
head(s, "چه کسانی واجد شرایط‌اند", "چهار بررسی روی سابقه شش ماه گذشته، و بعد امتیاز مدل");
const FMAX=FUNNEL[0][2];
FUNNEL.forEach(([t,sub,v],i)=>{
  const y=1.78+i*0.95, bw=(v/FMAX)*6.1;
  s.addShape(pres.ShapeType.roundRect, { x:M+W-bw, y, w:Math.max(bw,0.3), h:0.78,
    rectRadius:0.05, fill:{ color: i===FUNNEL.length-1 ? GOOD : (i===0 ? INK3 : BLUE),
    transparency: i===FUNNEL.length-1 ? 0 : (i===0 ? 70 : 82) },
    line:{ color: i===FUNNEL.length-1 ? GOOD : BLUE, width:0.75 } });
  s.addText(t, { x:M+0.2, y:y+0.06, w:W-6.5, h:0.34, fontSize:15, bold:true, color:INK, ...R, margin:0 });
  s.addText(sub, { x:M+0.2, y:y+0.4, w:W-6.5, h:0.3, fontSize:11, color:INK3, ...R, margin:0 });
  s.addText(n(v), { x:M+W-bw-0.02, y:y+0.18, w:Math.max(bw,0.3)-0.18, h:0.45, fontSize:17,
    bold:true, color:INK, ...R, margin:0 });
});
s.addText("بررسی اول تقریباً تمام کار را انجام می‌دهد و " + n(41270092-10087975)
  + " مشترک را کنار می‌گذارد. امتیاز مدل فقط " + n(SCORED-APPROVED) + " نفر دیگر را حذف می‌کند.",
  { x:M, y:6.42, w:W, h:0.45, fontSize:13, color:INK3, ...R, margin:0 });
s.addNotes("حد درآمدی یک غربال ظرفیت است، نه ریسک. پایین‌آوردنش حجم را زیاد می‌کند "
  + "بدون اینکه نرخ زیان را بالا ببرد.");

// ------------------------------------------------- 4. the grades
s = pres.addSlide({ masterName:"LIGHT" });
head(s, "سقف اعتبار هر مشترک", "رتبه، سقف را تعیین می‌کند. کم‌ریسک‌ترین‌ها بیشترین سقف را می‌گیرند");
const grows = GRADES.map(([g,c,pd,lim,note])=>{
  const dec = lim===0;
  const share = dec ? "—" : fa(Math.round(100*c*lim*pd/RISKT));
  return [{ text: g + (note ? " — "+note : ""),
            options:{ bold:true, color: dec?INK3:INK } },
          { text:n(c), options:{ color: dec?INK3:INK2 } },
          { text: dec ? "رد می‌شود" : n(lim), options:{ color: dec?INK3:INK2 } },
          { text:d2(pd*100), options:{ color: dec?INK3:INK2 } },
          { text: dec ? "—" : d1(c*lim/1e9), options:{ color: dec?INK3:INK2 } },
          { text: share, options:{ bold:!dec, color: dec?INK3:INK } }];
});
grows.push([{ text:"مجموع تأییدشده", options:{ bold:true, color:INK } },
            { text:n(APPROVED), options:{ bold:true, color:INK } },
            { text:"میانگین "+n(Math.round(AVGLIM)), options:{ bold:true, color:INK } },
            { text:"", options:{} },
            { text:d1(OUTST/1e9), options:{ bold:true, color:INK } },
            { text:"۱۰۰", options:{ bold:true, color:INK } }]);
rtlTable(s, ["رتبه","مشترکین","سقف اعتبار (تومان)","احتمال نکول ۴ ماهه (درصد)",
             "مانده در هر لحظه (میلیارد تومان)","سهم از زیان (درصد)"],
  grows, { x:M, y:1.75, w:W, colW:[1.5,1.9,1.75,1.75,1.5,3.65], rowH:0.46 });
s.addText([{ text:"رتبه B نیمی از کل زیان را به دوش می‌کشد", options:{ bold:true, color:INK } },
           { text:"، در حالی که دومین گروه کم‌ریسک است: بزرگ‌ترین گروه است و سقف ۳۰۰٬۰۰۰ تومانی می‌گیرد.",
             options:{ color:INK3 } }],
  { x:M, y:5.5, w:W, h:0.5, fontSize:13, ...R, margin:0 });
s.addNotes("ریسک هر مشترک با ریسک پرتفو یکی نیست. ستون سقف اعتبار جایی است که این تعیین می‌شود.");

// ------------------------------------------------- 5. the limit rule
s = pres.addSlide({ masterName:"LIGHT" });
head(s, "یک قاعده که سقف‌ها باید رعایتش کنند");
s.addShape(pres.ShapeType.roundRect, { x:M, y:1.6, w:W, h:1.35, rectRadius:0.07,
  fill:{ color:GOOD, transparency:90 }, line:{ color:GOOD, width:1 } });
s.addText("هرگز بیشتر از قبض یک ماه مشترک به او وام ندهید", { x:M+0.35, y:1.85, w:W-0.7,
  h:0.85, fontSize:27, bold:true, color:INK, ...R, margin:0 });
s.addText("زیر این خط قبض کمتر از دو برابر بالا می‌رود و مشترک با نرخ عادی پرداخت می‌کند. "
  + "روی این خط یا بالاتر، قبض دو برابر می‌شود و احتمال نکول ۱٫۷ برابر است.",
  { x:M, y:3.12, w:W, h:0.5, fontSize:14, color:INK2, ...R, margin:0 });
rtlTable(s, ["چه بر سر قبض می‌آید","قبض چند برابر می‌شود","احتمال نکول (برابر نرخ عادی)"],
  SHOCK.map(([a,b,c,col])=>[{ text:a, options:{ bold:true, color:INK } },
                            { text:b, options:{} },
                            { text:c, options:{ bold:true, color:col } }]),
  { x:M, y:3.85, w:W, colW:[3.4,3.4,5.2], rowH:0.55 });
s.addText("اندازه‌گیری‌شده روی ۴٫۰ میلیون مشترک‑ماه. جدول سقف‌ها این قاعده را از قبل رعایت می‌کند.",
  { x:M, y:6.2, w:W, h:0.4, fontSize:13, color:INK3, ...R, margin:0 });
s.addNotes("این تیزترین اثر اندازه‌گیری‌شده در کل پروژه است و دقیقاً روی نقطه «وام برابر قبض» می‌افتد.");

// ------------------------------------------------- 6. the cost
s = pres.addSlide({ masterName:"LIGHT" });
head(s, "هزینه محتمل طرح", "مرحله به مرحله، تا بشود روی هر قدمش بحث کرد");
const STEPS=[["۱", n(APPROVED)+" مشترک، میانگین "+n(Math.round(AVGLIM))+" تومان",
  "در هر لحظه "+d1(OUTST/1e9)+" میلیارد تومان نزد مشترکین، و "+n(Math.round(ANNUAL))
  +" میلیارد تومان در طول یک سال."],
 ["۲","نرخ نکول یک‌ماهه ۰٫۰۹ تا ۰٫۱۴ درصد",
  "این بازه یک انتخاب است، نه عدم‌قطعیت: کف بازه یعنی وام فقط به کم‌ریسک‌ترین‌ها."],
 ["۳","زیان سالانه "+d1(LOSS_LO)+" تا "+d1(LOSS_HI)+" میلیارد تومان",
  "با فرض هیچ وصولی از مشترک نکول‌کرده، که عمداً بدبینانه است."]];
STEPS.forEach(([num,t,sub],i)=>{
  const y=1.72+i*1.0;
  s.addShape(pres.ShapeType.ellipse, { x:M+W-0.42, y:y+0.04, w:0.42, h:0.42,
    fill:{ color:BLUE, transparency:85 }, line:{ color:BLUE, width:0.75 } });
  s.addText(num, { x:M+W-0.42, y:y+0.07, w:0.42, h:0.36, fontSize:13, bold:true,
    color:BLUE, align:"center", rtlMode:true, isTextBox:true, margin:0 });
  s.addText(t, { x:M, y:y, w:W-0.6, h:0.4, fontSize:17, bold:true, color:INK, ...R, margin:0 });
  s.addText(sub, { x:M, y:y+0.42, w:W-0.6, h:0.42, fontSize:12.5, color:INK2, ...R, margin:0 });
});
rtlTable(s, ["سناریو","ضریب","زیان سالانه (میلیارد تومان)","نسبت به اعطایی (درصد)"],
  STRESS.map(([t,m])=>[{ text:t, options:{ bold:m===1, color:m===1?INK:INK2 } },
                       { text:d2(m)+"×", options:{} },
                       { text:d1(LOSS_MID*m), options:{ bold:true, color: m>=1.68?CRIT:INK } },
                       { text:d2(100*LOSS_MID*m/ANNUAL), options:{} }]),
  { x:M, y:4.78, w:W, colW:[3.6,2.4,3.0,3.0], rowH:0.40 });
s.addNotes("ریسک این محصول در سمت زیان نیست، در سمت حجم است.");

// ------------------------------------------------- 7. what is open
s = pres.addSlide({ masterName:"DARK" });
s.addText("آنچه هنوز باز است", { x:M, y:0.72, w:W, h:0.7, fontSize:32, bold:true,
  color:DARKI, ...R, margin:0 });
const OPEN=[["هیچ مشترکی در این داده‌ها اعتبار نگرفته است",
  "امتیاز مدل رفتار مشترک را وقتی وام نگرفته توصیف می‌کند. تنها راه پاسخ، یک اجرای آزمایشی "
  + "محدود است؛ با دوره یک‌ماهه جواب ظرف چند هفته می‌رسد."],
 ["هدف ۱۵٬۰۰۰ میلیاردی، اعطای سالانه است یا مانده؟",
  "با گردش ماهانه این دو عدد دوازده برابر فرق دارند. اعطای سالانه: "
  + n(Math.round(ANNUAL)) + " میلیارد، بیش از دو برابر هدف. مانده در هر لحظه: "
  + d1(OUTST/1e9) + " میلیارد، با فاصله زیاد تا هدف."]];
OPEN.forEach(([t,b],i)=>{
  const y=1.95+i*2.1;
  s.addShape(pres.ShapeType.roundRect, { x:M, y, w:W, h:1.72, rectRadius:0.06,
    fill:{ color:"FFFFFF", transparency:94 }, line:{ color:CRIT, width:1 } });
  s.addText(t, { x:M+0.35, y:y+0.22, w:W-0.7, h:0.45, fontSize:19, bold:true,
    color:DARKI, ...R, margin:0 });
  s.addText(b, { x:M+0.35, y:y+0.72, w:W-0.7, h:0.85, fontSize:13.5, color:DARK2,
    lineSpacing:24, ...R, margin:0 });
});
s.addText("تعداد مشترکین از سوابق صورتحساب ۱۴۰۵۰۱ تا ۱۴۰۵۰۶. رتبه‌ها، سقف‌ها و احتمال نکول "
  + "از مدل امتیازدهی ۱۴۰۵/۰۷/۱۴. همه مبالغ به تومان.",
  { x:M, y:6.55, w:W, h:0.5, fontSize:10.5, color:INK3, ...R, margin:0 });
s.addNotes("هر دو مورد تصمیم را عوض می‌کنند، نه حساب‌وکتاب را.");

pres.writeFile({ fileName: OUT }).then(()=>console.log("written", OUT));

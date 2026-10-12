# -*- coding: utf-8 -*-
"""Every number the deck states, and the Persian numeral helpers, in one
place. The HTML slides and the PowerPoint build from this, so the two
cannot quote different figures.
"""
# ---- the model's decile ladder, with the riskiest decile split at today's
#      grade boundary so the base is the 8,801,772 the business approves now
LAD = [(934_472,0.000941),(1_868_944,0.001527),(2_803_416,0.001684),
       (3_737_889,0.002104),(4_672_361,0.002694),(5_606_833,0.003146),
       (6_541_306,0.004060),(7_475_778,0.005180),(8_410_250,0.008571),
       (9_344_723,0.029613)]
DEC = [(LAD[i][0]-(LAD[i-1][0] if i else 0), LAD[i][1]) for i in range(10)]
GRADE_E, APPROVED = 542_951, 8_801_772
RISKY_N  = APPROVED - 8_410_250
RISKY_PD = (DEC[9][0]*DEC[9][1] - GRADE_E*0.040) / RISKY_N
BANDS    = DEC[:9] + [(RISKY_N, RISKY_PD)]

SCORED, BASE, AUC = 9_344_723, 41_270_092, 0.8278
TARGET = 15_000.0
# representative limit per band, used for every money figure
MID   = {1: 200_000, 2: 400_000, 3: 750_000}
LABEL = {1: "۱۰۰ تا ۳۰۰ هزار", 2: "۳۰۰ تا ۵۰۰ هزار", 3: "۵۰۰ هزار تا ۱ میلیون"}
# which band each of the ten groups falls in, safest group first
OPT = [("کم‌ریسک",  "سقف‌ها پایین، تمرکز روی باند اول",
        [2,2,1,1,1,1,1,1,1,1]),
       ("محتاطانه", "یک دهک در باند بالا",
        [3,2,2,2,1,1,1,1,1,1]),
       ("گسترده",   "سه دهک در باند بالا",
        [3,3,3,2,2,2,2,1,1,1])]
# ضریب نفوذ به تفکیک باند: وام بزرگ‌تر، نفوذ کمتر
TAKE   = {1: 0.15, 2: 0.13, 3: 0.10}
ROUNDS = 3
# 56 D3: how many customers bill enough to carry each draw under the rule
CARRY = {200_000: 3_013_027, 300_000: 1_455_303, 500_000: 369_677}

def metrics(assign):
    cnt = {1:0, 2:0, 3:0}
    for i, b in enumerate(assign): cnt[b] += BANDS[i][0]
    assert sum(cnt.values()) == APPROVED
    # each band has its own take-up, so the borrower count AND the exposure
    # mix differ between options, and the rate has to follow them
    borrowers = sum(BANDS[i][0]*TAKE[assign[i]] for i in range(10))
    per_round = sum(BANDS[i][0]*TAKE[assign[i]]*MID[assign[i]] for i in range(10))
    pd1 = sum(BANDS[i][0]*TAKE[assign[i]]*MID[assign[i]]*BANDS[i][1]
              for i in range(10))/per_round/3.0
    ann = per_round*ROUNDS/1e9
    return dict(cnt=cnt, borrowers=borrowers, avg=per_round/borrowers,
                per_round=per_round/1e9, ann=ann, pd1=pd1, loss=ann*pd1)

MET = [metrics(a) for _, _, a in OPT]

_FA = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹",
       ",":"٬", ".":"٫"}
def fa(t):  return "".join(_FA.get(c, c) for c in str(t))
def f(n):   return fa("{:,}".format(int(round(n))))
def mi(n):  return fa("{:.1f}".format(n/1e6))          # in millions
def d1(x):  return fa("{:.1f}".format(x))
def d3(x):  return fa("{:.3f}".format(x))

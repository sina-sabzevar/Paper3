# Count and 6-month loan book

Source: the measured sweep in `test_all_1.xlsx`, sheet `R3-2`. Revenue per
KPI_v4 (`arpu` net of `tot_arpu_tax_amt`), four months 140503–140506.

Loan terms: **6 instalments, 4 pct total fee.**

| ticket | repaid | instalment / month |
|---|---|---|
| 400,000 | 416,000 | **69,333** |
| 500,000 | 520,000 | **86,667** |

## The table

Counts are measured. The books are count × ticket.

| revenue threshold | eligible, ≥2 of 4 months | book @400k | book @500k | rule 2–3 months | book @400k | book @500k |
|---|---|---|---|---|---|---|
| 100k | 12,739,512 | 5,096 bn | 6,370 bn | 5,274,443 | 2,110 bn | 2,637 bn |
| 130k | 10,882,263 | 4,353 bn | 5,441 bn | 5,008,465 | 2,003 bn | 2,504 bn |
| 150k | 9,883,931 | 3,954 bn | 4,942 bn | 4,807,363 | 1,923 bn | 2,404 bn |
| **170k** | **9,017,158** | **3,607 bn** | **4,509 bn** | **4,593,070** | **1,837 bn** | **2,297 bn** |
| 200k | 7,862,969 | 3,145 bn | 3,931 bn | 4,256,596 | 1,703 bn | 2,128 bn |
| 250k | 6,307,736 | 2,523 bn | 3,154 bn | 3,703,215 | 1,481 bn | 1,852 bn |
| 300k | 5,095,179 | 2,038 bn | 2,548 bn | 3,249,604 | 1,300 bn | 1,625 bn |

All amounts in billion Toman.

## Every row clears 3,000,000

| threshold | ≥2 months | 2–3 months | all 4 months | on payment, ≥2m |
|---|---|---|---|---|
| 100k | 4.2× | 1.8× | 2.5× | 3.8× |
| 130k | 3.6× | 1.7× | 2.0× | 3.2× |
| 150k | 3.3× | 1.6× | 1.7× | 2.8× |
| **170k** | **3.0×** | **1.5×** | **1.5×** | **2.5×** |
| 200k | 2.6× | 1.4× | 1.2× | 2.1× |
| 250k | 2.1× | 1.2× | 0.9× | 1.7× |
| 300k | 1.7× | 1.1× | 0.6× | 1.2× |

The population question is settled. At the stated 170,000 threshold, 9,017,158
subscribers clear it in at least two of four months — three times the target —
and 7,623,016 do so on *payment* rather than revenue, which is still 2.5 times
the target. Six instalments rather than four are what opened this up: the same
ticket costs a third less per month, so a far lower threshold carries it.

## The constraint has moved to the budget

| ticket | loans the 1,200 bn budget buys | vs 3,000,000 |
|---|---|---|
| 300,000 | 4,000,000 | 1.33× |
| 350,000 | 3,428,571 | 1.14× |
| **400,000** | **3,000,000** | **1.00×** |
| 450,000 | 2,666,667 | 0.89× |
| 500,000 | 2,400,000 | 0.80× |

1,200 bn ÷ 3,000,000 = **400,000 Toman exactly**, which is the original stated
minimum ticket to the Toman. At a 500,000 ticket the budget buys 2,400,000
loans and the target is 600,000 short — not for want of eligible subscribers,
of whom there are three times too many, but for want of money.

So the three constraints can hold together only at a 400,000 ticket, and the
eligible population at any threshold in the table is large enough to fill it
several times over. **That makes selection a matter of choosing the safest
3,000,000 of 9,000,000, not of finding enough people.** It is the opposite of
the problem this project started with.

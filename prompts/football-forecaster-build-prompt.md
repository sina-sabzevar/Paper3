# Build task: local football match-outcome forecaster (model + web app)

You are building a complete, working project on this machine, unattended, start to finish.
I am away and cannot answer questions. Where this document is silent, choose the simpler
option, write down the choice in `STATUS.md`, and keep going. Do not stop to ask.

---

## 0. The one rule that matters most

**Never fabricate data, numbers, or results.**

If a download fails, a scrape is blocked, or a model will not converge: log it, write it in
`STATUS.md`, skip that phase, and continue with the next one. A project that honestly reports
"Phase 6 failed, here is the traceback" is a success. A project that quietly invents plausible
accuracy figures is a total failure and worse than nothing. Every number in `RESULTS.md` must
be traceable to code that actually ran on this machine.

If you cannot complete a phase, the correct action is always: record the failure, move on.

---

## 1. What this is

A system that predicts the outcome of **real football matches** (home win / draw / away win),
trained on historical results, and evaluated honestly against two baselines.

This forecasts **real-world fixtures**, not EA Sports FC game simulations. Player attributes
from the game may later be used as *features*, but the prediction target is always the real
result of a real match.

Runs entirely locally. No cloud services. No paid APIs. **No API keys of any kind** — every
data source specified below is free and unauthenticated. Do not introduce a source that needs
a key, a login, or a Kaggle token.

---

## 2. Success criteria

The project is done when all of these are true:

1. `make all` runs end to end on a clean checkout and exits 0.
2. `make serve` starts a web app on `http://localhost:8000` that loads and shows real numbers.
3. `RESULTS.md` contains a metrics table produced by code that actually ran.
4. `pytest` passes.
5. `STATUS.md` records what was done, what failed, and every judgement call you made.

**Calibrate your expectations, and say so in the report:** beating bookmaker closing odds is
very hard — the closing line is close to efficient, and most published academic models do not
beat it. Do not treat failing to beat it as failure, and absolutely do not tune until you
appear to beat it. The realistic target is: *clearly beat the Elo baseline, and land within a
small margin of the market line.* Report the real gap either way.

---

## 3. Stack

- Python 3.11+, virtual environment (`uv` if available, else `venv` + pip)
- Data: `soccerdata` (https://github.com/probberechts/soccerdata), which wraps
  football-data.co.uk and Club Elo
- Storage: Parquet files on disk under `data/`; no database server
- Models: `statsmodels` / `scipy` for the Poisson model, `lightgbm` for the GBM
- App: `FastAPI` + `uvicorn`, serving a **single static HTML page** — no npm, no Node, no
  build step, no React. Charts are rendered server-side to PNG with `matplotlib` and served
  as static files. This keeps the unattended run from breaking on a toolchain.
- Tests: `pytest`

Do not add dependencies beyond what a phase actually needs.

---

## 4. Layout

```
football-forecaster/
├── README.md              how to install and run
├── STATUS.md              your running log — update after EVERY phase
├── RESULTS.md             the metrics table and honest interpretation
├── pyproject.toml
├── config.yaml            leagues, seasons, paths, model params
├── Makefile               data | features | train | backtest | report | serve | all
├── src/ff/
│   ├── config.py          loads config.yaml
│   ├── ingest/
│   │   ├── footballdata.py   results + closing odds
│   │   └── clubelo.py        Elo ratings
│   ├── features.py
│   ├── models/
│   │   ├── market.py         de-vigged bookmaker probabilities (benchmark)
│   │   ├── baseline_elo.py   Elo -> probabilities
│   │   ├── dixon_coles.py    bivariate Poisson goals model
│   │   └── gbm.py            LightGBM multiclass
│   ├── backtest.py        walk-forward evaluation
│   ├── metrics.py         log-loss, RPS, Brier, calibration
│   ├── report.py          writes RESULTS.md + matplotlib figures
│   └── api.py             FastAPI app
├── web/index.html         the dashboard
├── tests/
├── data/                  gitignored: raw/ interim/ processed/
└── reports/figures/       gitignored except .gitkeep
```

---

## 5. Phases

Work through these in order. **After each phase: run the tests, `git add -A && git commit`,
and append a dated entry to `STATUS.md`.** Committing per phase means a later failure never
destroys earlier work.

### Phase 0 — Scaffold
Create the layout, `pyproject.toml`, `.gitignore` (ignore `data/`, `reports/figures/*.png`,
`.venv/`, `__pycache__/`), `config.yaml`, `Makefile`, `git init`. Verify the env installs.

### Phase 1 — Ingest results and odds
Via `soccerdata`'s football-data.co.uk reader, pull **the 5 big European leagues** (England,
Spain, Italy, Germany, France — top tier) for **the last 12 completed seasons**. Persist raw
downloads to `data/raw/` and a tidy match table to `data/interim/matches.parquet`.

Requirements:
- **Cache every network call to disk and check the cache first.** A re-run must not re-download.
- Be polite: sequential requests, a short delay between them. Never parallelise scraping.
- Resumable: if it dies at league 4 of 5, re-running continues rather than restarting.
- Keep the **closing odds** columns. They are the benchmark and the project is much weaker
  without them.

### Phase 2 — Data validation
Write `scripts/validate_data.py` producing `reports/data_quality.md`: row counts per
league-season, date range, missing-value counts per column, duplicate fixtures, any season
with an implausible match count. Print it. Do not silently drop rows — record every exclusion
and its reason.

### Phase 3 — Features
Build `data/processed/features.parquet`, one row per match.

**The as-of rule, which you must not violate:** every feature for a match kicking off at time
T may only use information available strictly *before* T. Compute features by walking forward
through time. After building the table, write a test that asserts no feature for match T uses
any row with a date >= T. Leakage here silently invents a good-looking model and it is the
single most common way this kind of project goes wrong.

Features:
- Elo rating of each side before the match, and the difference (Phase 1b: Club Elo)
- Rolling form over last 5 and 10 matches: points, goals for/against, goal difference
- Separate home-form and away-form
- Days of rest since each side's previous match
- Matchday index within the season; flag for newly promoted sides
- Head-to-head record over the previous 3 meetings

Do **not** add weather, FC player ratings, lineups, or "morale" proxies in v1. They are Phase
11 and only if everything else is finished.

### Phase 4 — Baselines
Two reference points, both of which the models are measured against:
- `market.py`: convert closing odds to probabilities and **remove the overround** (normalise
  the implied probabilities to sum to 1). This is the benchmark, not a model — it is what a
  well-informed market believed.
- `baseline_elo.py`: map the pre-match Elo difference to home/draw/away probabilities via an
  ordered logistic fit on the training window only.

### Phase 5 — Dixon-Coles goals model
Bivariate Poisson with team attack/defence parameters, home advantage, the Dixon-Coles
low-score correction, and exponential time-decay weighting of older matches. Derive the 1X2
probabilities by summing the score matrix.

### Phase 6 — Gradient boosting
LightGBM, 3-class (home/draw/away), on the Phase 3 features plus the Dixon-Coles output as a
feature. Tune only via time-series cross-validation inside the training window — never on the
test window.

### Phase 7 — Walk-forward backtest
`backtest.py`. Train on all matches up to season S, predict season S+1, step forward, repeat
across the last 5 seasons.

**Never use a random train/test split.** It leaks the future into the past and makes every
number meaningless.

Metrics in `metrics.py`, computed for every model and both baselines:
- Multiclass **log-loss**
- **Ranked Probability Score (RPS)** — the standard metric for ordered 3-outcome football
  forecasts; implement it explicitly and unit-test it against a hand-worked example
- Brier score
- Accuracy (report it, but note in the text that it is the least informative of these)
- **Calibration**: reliability curve, 10 bins, per model

Also report the *number of matches* each metric was computed over.

### Phase 8 — Report
`report.py` writes `RESULTS.md`: the metrics table (models as rows, metrics as columns, both
baselines included), plus figures to `reports/figures/`:
- Reliability diagram, all models on one axis
- RPS by season, showing stability over time
- Feature importance for the GBM

Then write two honest paragraphs: what beat what, by how much, and where the model is weak.
State plainly whether the market line was beaten. **If it was not, say so** — that is the
expected result and pretending otherwise destroys the project's credibility.

### Phase 9 — Web app
FastAPI in `api.py`:
- `GET /` serves `web/index.html`
- `GET /api/metrics` returns the backtest table as JSON
- `GET /api/predictions?season=&league=` returns per-match predicted probabilities vs. actual
- `GET /api/figures/{name}.png` serves the matplotlib output
- `/health` returns 200

`web/index.html`: one plain page, no framework, no build step. A metrics table, the figures,
and a filterable list of matches showing predicted probabilities against the real outcome.
Clean and readable; dark and light themes via `prefers-color-scheme`. It must work with
JavaScript doing nothing more than `fetch` and DOM updates.

**Verify it actually runs**: start uvicorn, curl `/health` and `/api/metrics`, confirm 200 and
non-empty JSON, then shut it down. Record the check in `STATUS.md`.

### Phase 10 — Finish
- `README.md`: what it does, install, `make all`, how to read the results, **and a "Limitations"
  section** — what the model cannot do, what data it lacks, why beating the closing line is hard.
- `pytest` green: tests for RPS, the de-vig, the as-of/no-leakage assertion, and feature-builder
  edge cases (first matchday of a season, a promoted team with no history).
- Final `STATUS.md` entry summarising what works, what failed, and what you would do next.

### Phase 11 — Only if everything above is finished and green
In this order, one at a time, committing after each: stadium coordinates + Open-Meteo
historical weather (https://open-meteo.com/en/docs/historical-weather-api — free, no key);
FBref xG-based form features via `soccerdata` (rate-limit carefully); EA FC player ratings via
`soccerdata`'s SoFIFA reader. Re-run the backtest after each addition and record whether it
actually helped. **If an addition does not improve RPS, say so and keep it out of the default
model.**

---

## 6. Scope discipline

Do not add: user accounts, a database server, Docker, CI, cloud deploy, live-odds scraping,
betting-strategy or staking simulation, a JS framework, or any model beyond those specified.
If you find yourself with spare time, improve the tests and the report instead.

A finished, honest, modest system beats an unfinished ambitious one. That judgement is the
whole point of the exercise.

---

## 7. What I want to find when I get back

1. `STATUS.md` — what happened, in order, including the failures.
2. `RESULTS.md` — a real metrics table with real numbers and honest interpretation.
3. A running `make serve` that I can open in a browser.
4. A git log with one commit per phase.

Begin with Phase 0. Work straight through. Do not wait for me.

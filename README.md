# PEAD breakout timing: does post-earnings drift wait for the earnings-day high?

Round 1 research assessment for the quant team. Research question, data, method, results and an honest conclusion are in **[docs/report.md](docs/report.md)** (also `docs/report.pdf`), and in interactive form with the code that draws every table and figure in **[notebooks/report.ipynb](notebooks/report.ipynb)**. Both are generated from one source of text (`scripts/report_content.py`) so they cannot disagree. The proposal as submitted is in `docs/proposal_as_submitted.md`; the execution plan written after the design review is `docs/PLAN.md`.

**One-line answer.** After top-decile earnings-day reactions, abnormal returns after a close above the earnings-day high are indistinguishable from the unconditional path (-0.7 bp/day, 95% CI [-3.0, +1.6]); a rule that waits for the breakout earns less than buying at the next open (-0.92% in 2005-2014, about zero after). The hypothesis is rejected; the small early-sample drift is not tradable net of spreads.

## Repository layout

```
src/pead/            library code
  preflight.py       key loading (env only), geo guard, disk guard, key masking
  massive_client.py  Massive REST client: header-only auth, backoff, pagination
  edgar.py           SEC EDGAR submissions client (acceptance timestamps, Item 2.02)
  prices.py          split adjustment from the Splits table, trading calendar
  panel.py           common-stock + SPY panel with returns and rolling stats
  events.py          day-0 assignment, CIK->ticker mapping, filters, real-time selection
  backtest.py        vectorised rules A/B/C/D, legs, calendar-time series, bootstrap, Newey-West
  analysis.py        matched-path primary statistic and summary helpers
scripts/             stage scripts (run in order by scripts/run_all.py)
  report_content.py  the report text, tables and figure specs (single source)
  build_notebook.py  executes notebooks/report.ipynb and writes docs/report.md from it
  render_report.py   docs/report.md -> report.html (figures embedded) -> report.pdf via Chrome
notebooks/report.ipynb  executed notebook report (renders on GitHub; needs only outputs/)
tests/               pytest data-quality and no-leakage checks
outputs/tables/      every table cited in the report (CSV)
outputs/figures/     figures
logs/decision_log.csv       research decision log (deliverable 3)
logs/experiment_record.csv  experiment record, failed variants included (deliverable 4)
docs/                report, plan, proposal
data/raw, data/processed    git-ignored (licensed data; ~2 GB)
```

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). macOS/Linux:

```bash
uv python install 3.12    # only if Python 3.12 is not already present
uv sync
cp .env.example .env      # then put your own key in MASSIVE_API_KEY=... and your name/email in EDGAR_USER_AGENT
```

The key is read only from the environment (via the git-ignored `.env`), sent only as an `Authorization: Bearer` header, never written to URLs, logs or exceptions (`src/pead/preflight.py::mask`), and `tests/test_secrets.py` fails if the key value ever appears in a tracked file. `REQUIRE_HK_IP=1` in `.env` makes the client refuse to call the API unless the public IP resolves to Hong Kong (the client account rules); set `0` to disable.

## Reproduce the main analysis

```bash
.venv/bin/python scripts/run_all.py
```

Stages (each is idempotent and skips existing outputs): `download_market.py` (Daily Market Summary 2004-2026 unadjusted, All Tickers, Splits; ~6,000 calls, ~30 min), `download_edgar.py` (SEC EDGAR submissions for 9,679 CIKs, ~30 min at 9 req/s), `build_panel.py`, `build_events.py`, `run_main.py 10 40`, `run_grid.py`, `run_robustness.py`, `make_figures.py`, `export_aggregates.py`. Then `build_notebook.py` re-executes the notebook and rewrites `docs/report.md` from the committed tables only (no licensed data needed), and `render_report.py` produces the HTML and PDF. Total runtime about 70 minutes, peak RAM about 3 GB, disk about 2 GB. `scripts/probe_access.py` records which endpoints the account can reach.

```bash
.venv/bin/python scripts/run_all.py             # downloads + panel + events; analysis stages skip because their outputs are committed
.venv/bin/python scripts/run_all.py --analysis  # recompute every table and figure from data/processed (overwrites the committed CSV/PNG files)
.venv/bin/python scripts/build_notebook.py && .venv/bin/python scripts/render_report.py   # regenerate the notebook, report.md, html and pdf
```

`--force` also re-invokes the download scripts, which resume and only re-fetch the current year. Re-running `scripts/run_robustness.py` refreshes rows R00-R16 of the experiment record in place.

### What you can check without any data or key

Every number in the report is in `outputs/tables/*.csv`, and `notebooks/report.ipynb` and `docs/report.md` are regenerated from those CSVs alone by `scripts/build_notebook.py`. `python -m pytest -q` on a fresh clone runs the unit tests for split adjustment (`tests/test_prices.py`), the EDGAR parser on a committed fixture (`tests/test_edgar.py`) and the secret scan (`tests/test_secrets.py`); the event-construction tests, the grouped-bar integrity test and the live API cross-check skip visibly until the data exist (`RUN_API_TESTS=1` enables the live check).

Tests: `.venv/bin/python -m pytest -q`.

## Parameters and design choices

| Choice | Value | Why it exists | Considered | How chosen | Sensitivity |
|---|---|---|---|---|---|
| Max wait W | 10 (default), grid 5/10/15/20 | how long a breakout may take | grid | default pre-registered; 2005-2014 picks 15 by lower CI | none: conclusion identical in all cells |
| Holding H | 40 (default), grid 20/40/60 | horizon of drift | grid | as above | none |
| Selection cut | trailing-4-quarter 90th pct of AR0 | "strong report" | fixed 5%, z0 >= 2 | real-time computability | none |
| Min price | $5 (unadjusted, day -1) | penny-stock noise | - | convention | not varied |
| Min liquidity | median $ volume 60d >= $1M | tradability | - | convention | terciles reported |
| History | >= 120 bars | volatility estimate, no fresh IPOs | - | convention | not varied |
| Benchmark | SPY excess | simplicity | EW universe (not run) | transparency | matched-path statistic is benchmark-free |
| Breakout level | day-0 high | the hypothesis | D1 close0, D2 1.03 x high0, D3 day-1 high | hypothesis | all behave alike |
| Fill | next open after signal close | attainability | market-on-close | conservatism | MOC reported |
| Costs | Corwin-Schultz half-spread + 5 bp per side | tradability verdict | - | literature | by liquidity tercile |

## Assistance and source disclosure

**Academic papers consulted.** Ball and Brown (1968); Bernard and Thomas (1989, 1990); Foster, Olsen and Shevlin (1984); Chan, Jegadeesh and Lakonishok (1996); Frazzini (2006); Grinblatt and Han (2005); George and Hwang (2004); Huddart, Lang and Yetman (2009); DellaVigna and Pollet (2009); Hirshleifer, Lim and Teoh (2009); Corwin and Schultz (2012); Martineau (2022). Full references in the report.

**External datasets.** SEC EDGAR submissions API (https://data.sec.gov/submissions/), public domain, accessed 13 September 2026 with a descriptive User-Agent at under 10 requests per second. No other external data.

**Massive account.** The analysis used my own personally purchased Massive subscription (Stocks plan with full history), not the club's temporary key; Benzinga partner data was not entitled on it. No API key or raw licensed data is in this repository or its history.

**Existing repositories, code, tutorials or articles consulted.** Massive REST documentation (massive.com/docs, including the llms.txt dumps) and the SEC EDGAR developer notes. No third-party analysis code was copied.

**AI tools.** Claude Code (Anthropic, model Claude Fable 5.1) was used throughout, under my direction and review, for: reviewing the submitted proposal against the brief and the API documentation (a multi-perspective review whose findings are summarised in `docs/PLAN.md`); designing the revised test; writing all code in `src/`, `scripts/` and `tests/`; running the downloads and analyses; producing the tables and figures; drafting `docs/report.md`, this README, and the two CSV logs, whose timestamps are the real times the decisions were made. I reviewed the design decisions, the code and the results, and I am responsible for and able to defend every part of the submission.

**Assistance from other people.** None.

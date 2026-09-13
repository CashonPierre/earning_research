# Execution plan — PEAD breakout timing (Round 1 research assessment)

Written 2026-09-13 02:05 HKT after reviewing the submitted proposal against the club brief and the live Massive API. Deadline: 2026-09-14 23:59 HKT. This file is the contract for the autonomous run; every deviation goes in `logs/decision_log.csv`.

## 0. What the review changed (summary of verified findings)
1. **Rule A beats Rule B mechanically on every breakout event** (A = run-up × post-breakout leg; B = post-breakout leg only), so "B > A" is a test of a momentum filter, not of *when* drift occurs. The primary test becomes a **within-event decomposition** of per-day abnormal return before vs after the breakout, with controls. B vs A stays as a secondary result with this explanation.
2. **Day-0 timing cannot come from Massive 8-K endpoints** (date only, no time, no item). Source is **SEC EDGAR submissions `acceptanceDateTime`** for 8-Ks with Item 2.02 (downloaded: 321,077 rows, 9,679 CIKs). Benzinga Earnings is not entitled on this key (HTTP 403). Massive 8-K Disclosures start 2020 and tag only a handful of earnings releases per day, so they are not used.
3. **Within-quarter decile ranking is look-ahead**; selection uses a threshold known at day 0 (trailing four seasons' 90th percentile).
4. **Execution prices were unspecified**; all entries are at the **next open after the signal close**; a market-on-close variant is reported as implementation shortfall.
5. **Delistings come from All Tickers `active=false`** (Ticker Events only has symbol changes). Survivorship is handled by mapping events through CIK, not current ticker.
6. **NBBO is infeasible** on this disk; costs use the **Corwin-Schultz** high-low spread plus a fixed 5 bp per side.
7. Prices are stored **unadjusted** with explicit split adjustment from the Splits table (validated against vendor-adjusted bars), so the price filter is point-in-time.
8. The anchor ("earnings-day high") is trivial for gap-and-go events that close at the high; **range placement of the day-0 close is a design variable**, reported before any return result.
9. Reference literature added: Foster-Olsen-Shevlin 1984 and Chan-Jegadeesh-Lakonishok 1996 (announcement-return sorts), George-Hwang 2004 and Huddart-Lang-Yetman 2009 (anchoring at highs), Grinblatt-Han 2005, Bernard-Thomas 1990 (timing), DellaVigna-Pollet 2009 and Hirshleifer-Lim-Teoh 2009 (attention), Corwin-Schultz 2012 (spreads).

## 1. Data (done)
- `data/raw/grouped/{year}.parquet`: Daily Market Summary, `adjusted=false`, every weekday 2004-01-01..2026-09-11 (5,988 calls; ~35-55 MB/year). Date key = requested path date, never the `t` field. SPY is the benchmark row.
- `data/raw/tickers.parquet`: All Tickers, active and delisted, market=stocks (36,588 rows; 11,929 US common stocks, 6,609 delisted; 95.6% of delisted have a CIK).
- `data/raw/splits.parquet`: 27,541 splits/stock dividends 1978-2026.
- `data/raw/edgar_8k_202.parquet`: Item 2.02 8-K/8-K/A filings with UTC acceptance time and ET conversion; `edgar_coverage.parquet` per-CIK counts.
- Raw data is git-ignored (licensed); only derived tables and figures are committed.

## 2. Event construction (`src/pead/events.py`)
- Map CIK -> US common-stock tickers; for each filing pick the ticker that has bars on days -1 and 0; if several (dual class), keep the one with the larger trailing dollar volume.
- Trading calendar = dates on which SPY has a bar.
- Day 0: acceptance time in America/New_York. `< 09:30` -> same date (next trading day if a non-trading date); `>= 16:00` -> next trading day; `09:30-16:00` -> flagged `intraday`, excluded from the main sample, included in a robustness run. (EDGAR filings accepted after 17:30 ET carry the next filing date; we use the acceptance timestamp, so this does not matter.)
- One event per CIK per day 0; drop 8-K/A and any filing within 20 trading days after an earlier kept event for the same company.
- Timing validation: share of events whose |abnormal return| on the assigned day 0 exceeds that on days -1 and +1; reported in the report.
- Sample: day 0 from 2005-01-03 to 2026-06-12 (so a 60-day window ends by 2026-09-11).

## 3. Universe filters (pre-event data only)
Type CS, US locale, primary exchange XNYS/XNAS/XASE (from the ticker master; not point-in-time, stated as a limitation), unadjusted close on day -1 >= $5, median dollar volume over days -60..-1 >= $1 million, at least 120 bars before day 0.

## 4. Variables
- Daily abnormal return = split-adjusted close-to-close return minus SPY return. Day-0 abnormal return AR0 = from close(-1) to close(0).
- **Selection ("strong report")**: AR0 >= 90th percentile of AR0 across all filtered events whose day 0 fell in the previous four calendar quarters (expanding from at least two quarters at the start). Robustness: fixed AR0 >= +5%; standardised z0 = AR0 / std of abnormal returns over days -60..-1 with z0 >= 2.
- Range placement: (close0 - low0) / (high0 - low0), in terciles.

## 5. Rules and controls (window measured in trading days after day 0; H = holding length, W = max wait)
- **Rule A**: buy at open of day 1, sell at close of day H.
- **Rule B**: signal = first day k in 1..W with adjusted close > adjusted day-0 high; buy at open of day k+1 (k+1 <= H), sell at close of day H; zero return while flat; no trade if no signal.
- **Rule C (fixed delay)**: buy at open of day m+1 where m = median breakout day of Rule B in the selection period; unconditional on price.
- **Rule D (unanchored levels)**: same as B but the trigger level is (D1) close0, (D2) high0 x 1.03, (D3) the day-1 high (a post-event high that is not the earnings-day high).
- **Decomposition (primary)** for each selected event: pre-breakout leg CAR(1..k) and post-breakout leg CAR(k+1..H) for breakout events; CAR(1..H) for non-breakout events; per-day abnormal return in each leg.
- Ex-ante predictions written before results: H1 (timing) post-breakout per-day AR > pre-breakout per-day AR and > per-day AR of non-breakout events. H0: per-day AR is flat across legs. If D1-D3 show the same pattern as B, the day-0 high is not a special anchor (generic continuation).
- Delisting inside the window: exit at the last available close; count reported.

## 6. Statistics
- Calendar-time daily portfolios (equal weight across open positions) for A, B, C, D; paired difference series kept on days with >= 10 open positions; Newey-West t (lag = H).
- Season = calendar quarter of day 0. Season-block bootstrap (5,000 draws) 95% CIs for every headline number; count of seasons with B > A.
- Event-time mean CAR path with season-clustered CIs; CAR aligned on breakout day for breakout events.
- Exposure-aware metrics: stock-days invested, CAR per stock-day, daily volatility, Sharpe-like ratio.

## 7. Parameter protocol
Grid W in {5, 10, 15, 20} x H in {20, 40, 60}. Pre-registered default (10, 40). Selection period 2005-2014 chooses the cell with the largest season-bootstrap lower CI bound of the primary statistic (post-breakout minus pre-breakout per-day AR); the hold-out period 2015-2026 is reported for that cell and for the default; the full grid is disclosed for both periods. Other choices ($5, $1M, 90th pct, 60-day windows, 5 bp) are fixed a priori and listed in a parameter table with sensitivity.

## 8. Costs
Corwin-Schultz spread from daily high/low over days -25..-6 (floored at zero), half-spread per side plus 5 bp per side; charged at entry and exit for every rule; gross and net reported. Two-row verdict: hypothesis (gross) and tradability (net).

## 9. Robustness (MUST): range-placement terciles; liquidity terciles; sub-periods; exclude day-1 breakouts; W/H grid; unanchored triggers; fixed-delay control; matched non-earnings placebo (same-quarter non-earnings day with AR in the same decile and same range tercile, no 8-K within 5 days); pre-earnings placebo window; short-side mirror (bottom decile, close below day-0 low, gross only); intraday-included variant; market-on-close entry variant. SHOULD: EW-universe benchmark; Friday vs other; first post-entry day excluded. NICE: nearness to 52-week high; beta-adjusted returns.

## 10. Tests (`tests/`)
Secrets (key never in repo, header-only auth), split adjustment conventions, grouped-bar integrity, EDGAR extraction and timezone, event construction (entry date > signal date > day 0; no future data in filters), API cross-check (optional, live).

## 11. Outputs (`outputs/`)
`tables/*.csv` + `tables/*.md`, `figures/*.png`: sample construction funnel; timing validation; range placement and breakout-day histograms; decomposition table; rule comparison table (gross/net, exposure metrics); grid tables (selection and hold-out); control and placebo tables; CAR figures.

## 12. Report (`docs/report.md`)
Sections mapped one-to-one to the brief's list, including "how the project differed from the proposal" (five required elements for each change) and a pre-registered decision table mapping outcomes to the brief's acceptable conclusions.

## 13. Logs
`logs/decision_log.csv` (timestamp_hkt, stage, observation_or_problem, action_or_experiment, result, decision) and `logs/experiment_record.csv` (experiment_id, timestamp_hkt, hypothesis_version, universe, period, data_and_features, rule_or_model, key_parameters, main_result, retained, reason), appended with real timestamps as work happens, failures included.

## 14. README
Setup (uv sync, .env), run order (`scripts/run_all.py`), tests, outputs, parameter table, and the disclosure section: papers, external data (SEC EDGAR), AI tools (Claude Code: proposal review, code, analysis runs, report drafting; candidate reviewed and is responsible), own Massive subscription used, no other person.

## 15. Planned timeline (HKT) and cut lines

*Written at 02:05 before execution. The run was much faster than planned; actual completion times per stage are in `STATUS.md` and the logs.*
02:15-03:30 events + universe + selection; 03:30-05:00 backtest engine, decomposition, controls, statistics; 05:00-06:30 grid, costs, MUST robustness; 06:30-08:00 figures, tables, report, README; 08:00-09:00 tests, final commit, private GitHub push. Cut order if behind: NICE items, then SHOULD items, then matched non-earnings placebo (keep pre-earnings placebo), then short-side mirror. Margin: at least 12 hours before the deadline for the candidate to read, question and submit.

## 16. Risks and resume protocol
- Usage-limit pauses: pipeline stages are idempotent scripts with file outputs; `STATUS.md` records the next stage; a desktop scheduled task re-launches a session every two hours that resumes from `STATUS.md` unless `logs/session.lock` is fresh.
- Mac sleep: `caffeinate -dimsu` runs for 48 hours.
- Key exposure: header-only auth, `.env` git-ignored, secret-scan test before every commit.
- Disk: ~4 GiB free; no raw JSON; parquet only.

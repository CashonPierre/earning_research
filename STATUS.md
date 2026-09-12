# Run status (machine-readable checklist for resume)

Deadline: 2026-09-14 23:59 HKT. Plan: docs/PLAN.md. Update this file after every stage.

| stage | status | output | updated_hkt |
|---|---|---|---|
| 1 data download (grouped, tickers, splits, EDGAR) | DONE | data/raw/* | 2026-09-13 01:36 |
| 2 events + universe + selection | TODO | data/processed/events.parquet | |
| 3 backtest engine + decomposition + controls | TODO | outputs/tables/main_*.csv | |
| 4 statistics (NW, season bootstrap) | TODO | outputs/tables/stats_*.csv | |
| 5 parameter grid (selection vs hold-out) | TODO | outputs/tables/grid_*.csv | |
| 6 costs | TODO | outputs/tables/costs_*.csv | |
| 7 robustness MUST | TODO | outputs/tables/robust_*.csv | |
| 8 figures | TODO | outputs/figures/*.png | |
| 9 report | TODO | docs/report.md | |
| 10 README + disclosure | TODO | README.md | |
| 11 tests green + final commit + GitHub push | TODO | | |

NEXT: stage 2. OVERALL: IN_PROGRESS

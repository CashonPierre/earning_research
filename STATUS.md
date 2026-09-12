# Run status (machine-readable checklist for resume)

Deadline: 2026-09-14 23:59 HKT. Plan: docs/PLAN.md. Update this file after every stage.

| stage | status | output | updated_hkt |
|---|---|---|---|
| 1 data download (grouped, tickers, splits, EDGAR) | DONE | data/raw/* | 2026-09-13 01:36 |
| 2 events + universe + selection | DONE | data/processed/events.parquet | 2026-09-13 02:20 |
| 3 backtest engine + decomposition + controls | DONE | outputs/tables/main_*.csv | 2026-09-13 02:30 |
| 4 statistics (NW, season bootstrap) | DONE | outputs/tables/stats_*.csv | 2026-09-13 02:30 |
| 5 parameter grid (selection vs hold-out) | DONE | outputs/tables/grid_*.csv | 2026-09-13 02:45 |
| 6 costs | DONE | outputs/tables/costs_*.csv | 2026-09-13 02:55 |
| 7 robustness MUST | DONE | outputs/tables/robust_*.csv | 2026-09-13 02:55 |
| 8 figures | DONE | outputs/figures/*.png | 2026-09-13 03:00 |
| 9 report | DONE | docs/report.md | 2026-09-13 03:15 |
| 10 README + disclosure | DONE | README.md | 2026-09-13 03:20 |
| 11 tests green + final commit + GitHub push | DONE | | 2026-09-13 03:35 |

NEXT: none. Candidate to review docs/report.md, make the GitHub repo public, and submit. OVERALL: COMPLETE

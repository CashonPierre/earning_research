# Run status (machine-readable checklist for resume)

Deadline: 2026-09-14 23:59 HKT. Plan: docs/PLAN.md. Update this file after every stage.

| stage | status | output | updated_hkt |
|---|---|---|---|
| 1 data download (grouped, tickers, splits, EDGAR) | DONE | data/raw/* | 2026-09-13 01:36 |
| 2 events + universe + selection | DONE | data/processed/events.parquet | 2026-09-13 02:10 |
| 3 backtest engine + decomposition + controls | DONE | outputs/tables/main_*.csv | 2026-09-13 02:13 |
| 4 statistics (NW, season bootstrap) | DONE | outputs/tables/calendar_time_W10_H40.csv | 2026-09-13 02:13 |
| 5 parameter grid (selection vs hold-out) | DONE | outputs/tables/grid_*.csv | 2026-09-13 02:15 |
| 6 costs | DONE | outputs/tables/costs_*.csv | 2026-09-13 02:17 |
| 7 robustness MUST | DONE | outputs/tables/robustness_W10_H40.csv | 2026-09-13 02:17 |
| 8 figures | DONE | outputs/figures/*.png | 2026-09-13 02:17 |
| 9 report | DONE | docs/report.md | 2026-09-13 02:21 |
| 10 README + disclosure | DONE | README.md | 2026-09-13 02:22 |
| 11 tests green + final commit + GitHub push | DONE | | 2026-09-13 02:22 |
| 12 plain-language rewrite, notebook report, aggregate exports | DONE | notebooks/report.ipynb, docs/report.md | 2026-09-13 23:01 |
| 13 review fixes: corrected matched control, sensitivities R13-R16, costs by period | DONE | outputs/tables/robustness_W10_H40.csv, costs_W10_H40.csv | 2026-09-13 23:23 |
| 14 final rebuild, tests, commit, push | DONE |  | 2026-09-13 23:23 |

NEXT: none. Candidate to review docs/report.md, make the GitHub repo public, and submit. OVERALL: COMPLETE

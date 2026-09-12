"""Run every stage in order; each stage skips work whose outputs already exist."""
import pathlib, subprocess, sys
PY = sys.executable
STAGES = [
    ("scripts/download_market.py", ["data/raw/grouped/2026.parquet", "data/raw/tickers.parquet", "data/raw/splits.parquet"]),
    ("scripts/download_edgar.py", ["data/raw/edgar_8k_202.parquet"]),
    ("scripts/build_panel.py", ["data/processed/panel.parquet"]),
    ("scripts/build_events.py", ["data/processed/events.parquet"]),
    ("scripts/run_main.py 10 40", ["outputs/tables/main_summary_W10_H40.csv"]),
    ("scripts/run_grid.py", ["outputs/tables/grid_results.csv"]),
    ("scripts/run_robustness.py", ["outputs/tables/robustness_W10_H40.csv"]),
    ("scripts/make_figures.py", ["outputs/figures/fig6_calendar_time.png"]),
]
force = "--force" in sys.argv
for cmd, outs in STAGES:
    if not force and all(pathlib.Path(o).exists() for o in outs):
        print(f"skip {cmd} (outputs exist)"); continue
    print(f"run  {cmd}", flush=True)
    subprocess.run([PY, *cmd.split()], check=True)
print("all stages complete")

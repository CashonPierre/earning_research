"""Run every stage in order; each stage skips work whose outputs already exist."""
import os, pathlib, subprocess, sys
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
    ("scripts/export_aggregates.py", ["outputs/tables/decomposition_W10_H40.csv"]),
]
os.chdir(pathlib.Path(__file__).resolve().parents[1])
force = "--force" in sys.argv            # re-run everything, downloads included
analysis = "--analysis" in sys.argv      # keep downloads and builds, re-run analysis stages (index >= 4)
for i, (cmd, outs) in enumerate(STAGES):
    if not (force or (analysis and i >= 4)) and all(pathlib.Path(o).exists() for o in outs):
        print(f"skip {cmd} (outputs exist)"); continue
    print(f"run  {cmd}", flush=True)
    subprocess.run([PY, *cmd.split()], check=True)
print("all stages complete")
print("Usage: run_all.py [--analysis | --force]. On a fresh clone the committed outputs make every stage skip; use --analysis to recompute from data/processed, --force to redo downloads too.")

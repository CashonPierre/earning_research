"""Stage 8b: export small aggregate tables (no per-security prices) so the notebook report can be
re-run from the committed outputs without the git-ignored data."""
import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])  # always run from the repo root
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from pead.backtest import Windows, run_rules, season_bootstrap
SEL_END = "2014-12-31"; W, H = 10, 40; OUT = pathlib.Path("outputs/tables"); OUT.mkdir(parents=True, exist_ok=True)
ev = pd.read_parquet("data/processed/events.parquet"); sel = ev[ev.selected].reset_index(drop=True)
import json
m_fixed = json.load(open("outputs/tables/main_meta_W10_H40.json"))["m_fixed"]
win = Windows(sel); res = run_rules(win, W, H, m_fixed=m_fixed); path = win.event_time_path(60)
keep = res.valid_A.to_numpy()  # same filter as run_main: drop events with no bar at open(1)
sel = sel[keep].reset_index(drop=True); res = res[keep].reset_index(drop=True); path = path[keep]
q = sel.quarter.to_numpy(); selmask = (sel.d0 <= SEL_END).to_numpy()
def season_ci(mat, groups, n_boot=2000, seed=0):
    rng = np.random.default_rng(seed); g = pd.Series(groups); keys = g.unique(); idx = [np.where(g.values == k)[0] for k in keys]
    sums = np.array([mat[i].sum(axis=0) for i in idx]); cnts = np.array([len(i) for i in idx], dtype=float)
    draws = rng.integers(0, len(keys), size=(n_boot, len(keys))); boot = sums[draws].sum(axis=1) / cnts[draws].sum(axis=1)[:, None]
    return np.quantile(boot, 0.025, axis=0), np.quantile(boot, 0.975, axis=0)
# 1. CAR path means by period
rows = []
for lab, m in (("all_2005_2026", np.ones(len(sel), bool)), ("selection_2005_2014", selmask), ("holdout_2015_2026", ~selmask)):
    car = np.cumsum(path[m], axis=1); lo, hi = season_ci(car, q[m])
    for d in range(60): rows.append({"period": lab, "day": d + 1, "mean_car_pct": car[:, d].mean() * 100, "ci_lo_pct": lo[d] * 100, "ci_hi_pct": hi[d] * 100, "n_events": int(m.sum())})
pd.DataFrame(rows).to_csv(OUT / "car_path_means.csv", index=False)
# 2. breakout-aligned daily AR and matched unconditional path
k = res.k_B.to_numpy(); ent = res.entry_B.to_numpy(); has = ~np.isnan(ent); tau = np.arange(-5, 21)
seasons = {s: path[q == s].mean(axis=0) for s in np.unique(q)}
al = np.full((has.sum(), len(tau)), np.nan); ctrl = np.full_like(al, np.nan)
for r, i in enumerate(np.where(has)[0]):
    kk = int(k[i])
    for j, t in enumerate(tau):
        d = kk + t
        if 1 <= d <= 60: al[r, j] = path[i, d - 1]; ctrl[r, j] = seasons[q[i]][d - 1]
pd.DataFrame({"tau": tau, "breakout_events_mean_ar_bp": np.nanmean(al, axis=0) * 1e4, "matched_unconditional_mean_ar_bp": np.nanmean(ctrl, axis=0) * 1e4, "n_obs": (~np.isnan(al)).sum(axis=0)}).to_csv(OUT / "breakout_aligned_means.csv", index=False)
# 3. event descriptives (aggregates only)
d = {"n_selected_events": len(sel), "n_tickers": sel.ticker.nunique(), "n_quarters": sel.quarter.nunique(), "share_amc": (sel.timing == "amc").mean(), "share_friday_day0": (sel.weekday0 == 4).mean(),
     "median_ar0": sel.ar0.median(), "mean_ar0": sel.ar0.mean(), "median_threshold": sel.threshold.median(), "median_overnight_gap": sel.gap0.median(), "share_close_in_top_fifth_of_range": (sel.range_pos >= 0.8).mean(),
     "median_dollar_volume_60d_musd": sel.med60_dv_m1.median() / 1e6, "median_price_day_minus1": sel.close_unadj_m1.median(),
     "share_events_in_now_delisted_tickers": sel.ticker.isin(pd.read_parquet("data/raw/tickers.parquet").query("active==False").ticker).mean(),
     "share_breakout_within_W": res.entered_B.mean(), "share_day1_breakouts_among_breakouts": float((res.k_B == 1).sum() / res.entered_B.sum()), "n_early_exit_delisted_in_window": int(res.early_exit.sum())}
pd.Series(d, name="value").rename_axis("statistic").to_csv(OUT / "event_descriptives.csv")
sel.d0.dt.year.value_counts().sort_index().rename_axis("year").rename("n_selected_events").to_csv(OUT / "events_per_year.csv")
cnt, edges = np.histogram(sel.range_pos.dropna(), bins=25, range=(0, 1)); pd.DataFrame({"bin_left": edges[:-1], "bin_right": edges[1:], "n_events": cnt}).to_csv(OUT / "range_pos_hist.csv", index=False)
# 4. decomposition table: breakout vs non-breakout events, by period
rows = []
for per, m in (("all_2005_2026", np.ones(len(res), bool)), ("selection_2005_2014", selmask[res.index]), ("holdout_2015_2026", ~selmask[res.index])):
    r = res[m]
    for grp, mm in (("all events", np.ones(len(r), bool)), ("breakout within W", r.entered_B.to_numpy()), ("no breakout within W", ~r.entered_B.to_numpy())):
        rr = r[mm]; qq = rr.quarter.to_numpy()
        row = {"period": per, "group": grp, "n": len(rr), "share": len(rr) / len(r)}
        for nm, v in (("CAR_A", rr.ret_A), ("CAR_B", rr.ret_B), ("run_up_open1_to_entry", rr.leg_pre), ("post_entry_leg", rr.leg_post), ("perday_A", rr.perday_A), ("perday_post_entry", rr.perday_post)):
            vv = v.to_numpy()
            if np.isnan(vv).all(): row[nm] = np.nan; continue
            b = season_bootstrap(vv, qq); row[nm], row[f"{nm}_lo"], row[f"{nm}_hi"] = b["point"], b["ci_lo"], b["ci_hi"]
        rows.append(row)
pd.DataFrame(rows).to_csv(OUT / "decomposition_W10_H40.csv", index=False)
print("exported:", sorted(p.name for p in OUT.glob("*.csv")))

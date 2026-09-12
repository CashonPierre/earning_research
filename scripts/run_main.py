"""Stage 3/4: default cell (W=10, H=40): main tables, decomposition, controls, calendar-time stats."""
import json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from pead.backtest import Windows, run_rules, calendar_time, newey_west_t, season_bootstrap, season_share

W, H = int(sys.argv[1]) if len(sys.argv) > 1 else 10, int(sys.argv[2]) if len(sys.argv) > 2 else 40
SEL_END = "2014-12-31"
OUT = pathlib.Path("outputs/tables"); OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()
ev = pd.read_parquet("data/processed/events.parquet")
sel = ev[ev.selected].reset_index(drop=True)
win = Windows(sel)
print(f"windows built for {len(sel)} events in {time.time()-t0:.0f}s")
# fixed delay m = median breakout day in the selection period
tmp = run_rules(win, W, H)
sel_mask = (sel.d0 <= SEL_END).to_numpy()
m_fixed = int(np.nanmedian(tmp.loc[sel_mask & tmp.entered_B.to_numpy(), "k_B"]))
res = run_rules(win, W, H, m_fixed=m_fixed)
res["d0"] = sel.d0.to_numpy(); res["period"] = np.where(sel.d0 <= SEL_END, "selection_2005_2014", "holdout_2015_2026")
res["range_tercile"] = pd.qcut(sel.range_pos, 3, labels=["low", "mid", "high"]).astype(str).to_numpy()
res["liq_tercile"] = pd.qcut(sel.med60_dv_m1, 3, labels=["low", "mid", "high"]).astype(str).to_numpy()
res["spread_cs"] = win.corwin_schultz()
res = res[res.valid_A].copy()
res.to_parquet(f"data/processed/results_W{W}_H{H}.parquet", index=False)

def summarise(r, label):
    q = r.quarter.to_numpy()
    rows = []
    def add(name, v, extra=None):
        b = season_bootstrap(v, q); sh, ns = season_share(v, q)
        rows.append({"period": label, "statistic": name, "mean": b["point"], "ci_lo": b["ci_lo"], "ci_hi": b["ci_hi"], "share_seasons_pos": sh, "n_events": int(np.sum(~np.isnan(v))), "n_seasons": ns, **(extra or {})})
    add("CAR_A (open1->closeH)", r.ret_A.to_numpy())
    add("CAR_B (breakout entry, 0 if flat)", r.ret_B.to_numpy())
    add("B minus A", (r.ret_B - r.ret_A).to_numpy())
    add("CAR_C fixed delay m", r.ret_C.to_numpy(), {"m_fixed": m_fixed})
    add("C minus A", (r.ret_C - r.ret_A).to_numpy())
    for d in ("D1", "D2", "D3"):
        add(f"CAR_{d}", r[f"ret_{d}"].to_numpy(), {"share_entered": float(r[f"entered_{d}"].mean())})
        add(f"{d} minus A", (r[f"ret_{d}"] - r.ret_A).to_numpy())
    add("per-day AR pre-breakout leg (breakout events)", r.perday_pre.to_numpy())
    add("per-day AR post-breakout leg (breakout events)", r.perday_post.to_numpy())
    add("per-day AR non-breakout events (1..H)", r.perday_nonbreak.to_numpy())
    add("per-day AR all events (Rule A)", r.perday_A.to_numpy())
    # primary statistic: post minus pre per-day AR on breakout events (paired within event)
    add("PRIMARY: post minus pre per-day AR (breakout events)", (r.perday_post - r.perday_pre).to_numpy())
    # post-breakout per-day minus non-breakout per-day (two samples)
    b = season_bootstrap(r.perday_post.to_numpy(), q, values2=r.perday_nonbreak.to_numpy(), groups2=q)
    rows.append({"period": label, "statistic": "post-breakout per-day minus non-breakout per-day", "mean": b["point"], "ci_lo": b["ci_lo"], "ci_hi": b["ci_hi"], "n_events": int(r.entered_B.sum()), "n_seasons": b["n_seasons"]})
    out = pd.DataFrame(rows)
    out["share_B_entered"] = float(r.entered_B.mean()); out["median_k_B"] = float(np.nanmedian(r.k_B)); out["n_early_exit"] = int(r.early_exit.sum())
    return out

summ = pd.concat([summarise(res, "all_2005_2026"), summarise(res[res.period == "selection_2005_2014"], "selection_2005_2014"), summarise(res[res.period == "holdout_2015_2026"], "holdout_2015_2026")])
summ.to_csv(OUT / f"main_summary_W{W}_H{H}.csv", index=False)
print(summ[["period", "statistic", "mean", "ci_lo", "ci_hi", "share_seasons_pos", "n_events"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
# breakout-day distribution and range placement
kd = res.k_B.value_counts(dropna=False).sort_index(); kd.index = [("none" if pd.isna(i) else int(i)) for i in kd.index]
kd.rename_axis("k_B").rename("n_events").to_csv(OUT / f"breakout_day_hist_W{W}_H{H}.csv")
strat = []
for col in ("range_tercile", "liq_tercile", "period"):
    for g, r in res.groupby(col):
        q = r.quarter.to_numpy()
        prim = season_bootstrap((r.perday_post - r.perday_pre).to_numpy(), q); ba = season_bootstrap((r.ret_B - r.ret_A).to_numpy(), q)
        strat.append({"split": col, "group": g, "n": len(r), "share_entered_B": r.entered_B.mean(), "median_k": np.nanmedian(r.k_B), "CAR_A": r.ret_A.mean(), "CAR_B": r.ret_B.mean(), "B_minus_A": ba["point"], "B_minus_A_lo": ba["ci_lo"], "B_minus_A_hi": ba["ci_hi"], "primary_post_minus_pre": prim["point"], "primary_lo": prim["ci_lo"], "primary_hi": prim["ci_hi"]})
pd.DataFrame(strat).to_csv(OUT / f"stratified_W{W}_H{H}.csv", index=False)
print(pd.DataFrame(strat).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
# calendar-time
entry_A = np.ones(len(win.ev)); entry_B = run_rules(win, W, H).entry_B.to_numpy()
ct = calendar_time(win, entry_A, entry_B, H)
ct_rows = []
for lab, mask in (("all", np.ones(len(ct), bool)), ("selection", (ct.index <= sel[sel.d0 <= SEL_END].idx0.max() + H)), ("holdout", (ct.index > sel[sel.d0 <= SEL_END].idx0.max() + H))):
    for s in ("rA", "rB", "d"):
        mu, se, t = newey_west_t(ct.loc[mask, s].to_numpy(), lag=H)
        ct_rows.append({"period": lab, "series": s, "mean_daily_bp": mu * 1e4, "nw_se_bp": se * 1e4, "nw_t": t, "n_days": int(mask.sum()), "ann_sharpe": mu / ct.loc[mask, s].std() * np.sqrt(252)})
pd.DataFrame(ct_rows).to_csv(OUT / f"calendar_time_W{W}_H{H}.csv", index=False)
ct.to_csv(OUT / f"calendar_time_series_W{W}_H{H}.csv")
print(pd.DataFrame(ct_rows).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
json.dump({"W": W, "H": H, "m_fixed": m_fixed, "n_events": int(len(res)), "seconds": time.time() - t0}, open(OUT / f"main_meta_W{W}_H{H}.json", "w"))
print(f"done {time.time()-t0:.0f}s")

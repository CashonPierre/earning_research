"""Stages 6-7: costs and robustness variants. Re-runs replace their own rows in logs/experiment_record.csv (idempotent)."""
import csv, datetime as dt, json, pathlib, sys, time, zoneinfo
import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])  # always run from the repo root
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from pead.backtest import Windows, run_rules, season_bootstrap
from pead.analysis import cell_stats
HKT = zoneinfo.ZoneInfo("Asia/Hong_Kong"); SEL_END = "2014-12-31"; OUT = pathlib.Path("outputs/tables")
W, H = 10, 40
ev = pd.read_parquet("data/processed/events.parquet")
rows, exp = [], []
def now(): return dt.datetime.now(HKT).strftime("%Y-%m-%d %H:%M")
def record(exp_id, hyp, universe, period, feats, rule, params, result, retained, reason):
    exp.append({"experiment_id": exp_id, "timestamp_hkt": now(), "hypothesis_version": hyp, "universe": universe, "period": period, "data_and_features": feats, "rule_or_model": rule, "key_parameters": params, "main_result": result, "retained": retained, "reason": reason})
def fmt(r): return f"B-A {r['B_minus_A']:+.4f} [{r['B_minus_A_lo']:+.4f},{r['B_minus_A_hi']:+.4f}]; PRIMARY {r['PRIMARY_post_minus_matched']*1e4:+.1f}bp/d [{r['PRIMARY_lo']*1e4:+.1f},{r['PRIMARY_hi']*1e4:+.1f}]; CAR_A {r['CAR_A']:+.4f}; entered {r['share_entered_B']:.2f}"
def variant(label, events, exp_id, note, **kw):
    sign = -1.0 if kw.get("short") else 1.0
    t0 = time.time(); w = Windows(events.reset_index(drop=True))
    selmask = (w.ev.d0 <= SEL_END).to_numpy()
    tmp = run_rules(w, W, H, **kw); m = int(np.nanmedian(tmp.loc[selmask & tmp.entered_B.to_numpy(), "k_B"])) if tmp.entered_B.any() else 2
    res = run_rules(w, W, H, m_fixed=m, **kw); res = res[res.valid_A]
    for per, mask in (("all", np.ones(len(res), bool)), ("selection", selmask[res.index]), ("holdout", ~selmask[res.index])):
        r = cell_stats(w, res[mask], H, f"{label} | {per}", {"variant": label, "period": per, "W": W, "H": H, "m_fixed": m}, sign=sign); rows.append(r)
        if per == "all":
            record(exp_id, "H1: drift concentrated after close > day-0 high", f"{len(w.ev)} events", "2005-2026", note, f"A open(1)->close(H); B breakout entry; C fixed delay {m}; D1-D3 unanchored", f"W={W},H={H}", fmt(r), "yes", "robustness variant reported in full")
    print(f"{label}: {fmt(rows[-3])} ({time.time()-t0:.0f}s)", flush=True)
    return w, res
sel = ev[ev.selected]
w_base, res_base = variant("base top-decile trailing threshold", sel, "R00", "EDGAR 2.02 timing; AR0 >= trailing-4Q 90th pct")
# selected grid cell
gc = json.load(open("outputs/tables/grid_selected_cell.json")); W, H = int(gc["W"]), int(gc["H"]); variant(f"grid-selected cell W={W} H={H}", sel, "R01", "cell chosen on 2005-2014 lower CI of the primary statistic"); W, H = 10, 40
variant("trigger from day 2 (exclude day-1 breakouts)", sel, "R02", "first_day=2", first_day=2)
variant("market-on-close entry for signal rules", sel, "R03", "B/C/D enter at close(k) instead of open(k+1)", moc=True)
variant("selection: fixed AR0 >= 5%", ev[ev.selected_fixed5], "R04", "fixed cutoff instead of trailing percentile")
variant("selection: z0 >= 2", ev[ev.selected_z2], "R05", "AR0 standardised by trailing 60d std")
intr = ev[ev.passes_filters & ev.in_sample_period & ev.threshold.notna() & (ev.ar0 >= ev.threshold)]
variant("intraday filings included", intr, "R06", "adds 09:30-16:00 acceptance times with day 0 = filing date")
plc = sel.copy(); plc["idx0"] = plc["idx0"] - 60
variant("placebo: pseudo day 0 = 60 sessions before the event", plc, "R07", "same stocks, no news; anchor = pseudo-day high")
short_ev = ev[ev.selected_bottom]
variant("short-side mirror (bottom decile, close < day-0 low), gross", short_ev, "R08", "mirrored rules, returns negated", short=True)
# sensitivity of the a-priori choices: selection percentile and filters (subsets of the same machinery)
def select_pct(ev, pct):
    pool = ev[ev.passes_filters & (ev.timing != "intraday")]
    qs = sorted(ev.quarter.unique()); by_q = {q: g.ar0.to_numpy() for q, g in pool.groupby("quarter")}; thr = {}
    for i, q in enumerate(qs):
        prev = [by_q[x] for x in qs[max(0, i - 4):i] if x in by_q]
        arr = np.concatenate(prev) if len(prev) >= 2 else np.array([])
        thr[q] = float(np.quantile(arr, pct)) if len(arr) >= 200 else np.nan
    t = ev.quarter.map(thr)
    return ev[ev.passes_filters & (ev.timing != "intraday") & ev.in_sample_period & t.notna() & (ev.ar0 >= t)]
base_ok = ev.passes_filters & (ev.timing != "intraday") & ev.in_sample_period
variant("selection: overnight gap-up >= 2 std", ev[base_ok & (ev.gap0 / ev.std60_ab_m1 >= 2)], "R17", "strong = opening gap at least 2 trailing daily std devs (candidate's preferred definition)")
variant("selection: overnight gap-up >= 5%", ev[base_ok & (ev.gap0 >= 0.05)], "R18", "strong = opening gap of at least 5%")
variant("selection: trailing 85th percentile", select_pct(ev, 0.85), "R13", "looser cut-off than the 90th percentile")
variant("selection: trailing 95th percentile", select_pct(ev, 0.95), "R14", "stricter cut-off than the 90th percentile")
variant("filter: price >= $10 on day -1", sel[sel.close_unadj_m1 >= 10], "R15", "stricter price filter (subset of base)")
variant("filter: median dollar volume >= $5M", sel[sel.med60_dv_m1 >= 5e6], "R16", "stricter liquidity filter (subset of base)")
# Friday vs other, liquidity and range terciles (base results)
for exp_id, lab, mask in (("R10", "Friday day 0", w_base.ev.weekday0.to_numpy() == 4), ("R10b", "Mon-Thu day 0", w_base.ev.weekday0.to_numpy() != 4)):
    r = cell_stats(w_base, res_base[mask[res_base.index]], H, f"{lab} | all", {"variant": lab, "period": "all", "W": W, "H": H}); rows.append(r); print(f"{lab}: {fmt(r)}")
    record(exp_id, "attention moderator (DellaVigna-Pollet)", f"{int(mask.sum())} events", "2005-2026", "day-0 weekday", "base rules", f"W={W},H={H}", fmt(r), "yes", "reported as a curiosity: one of many splits, sign opposite to the attention prediction")
for exp_id, col, src in (("R11", "liquidity tercile", pd.qcut(w_base.ev.med60_dv_m1, 3, labels=["low", "mid", "high"]).astype(str).to_numpy()), ("R12", "range-placement tercile", pd.qcut(w_base.ev.range_pos, 3, labels=["low", "mid", "high"]).astype(str).to_numpy())):
    parts = []
    for g in ("low", "mid", "high"):
        mask = src == g; r = cell_stats(w_base, res_base[mask[res_base.index]], H, f"{col} {g} | all", {"variant": f"{col} {g}", "period": "all", "W": W, "H": H}); rows.append(r); parts.append(f"{g}: B-A {r['B_minus_A']:+.4f}, entered {r['share_entered_B']:.2f}")
    record(exp_id, "where does B's shortfall concentrate?", "base events split in thirds", "2005-2026", col, "base rules", f"W={W},H={H}", "; ".join(parts), "yes", "heterogeneity reported in full")
# ---- does longer consolidation help? (candidate's question)
def hold_variable(w, res, mult=3, lo=10, hi=50):
    """Hold for mult x consolidation days after the breakout entry (clamped), instead of a fixed H.
    Returns the season-bootstrapped primary statistic (post-entry per-day AR minus the matched same-span path)."""
    E = len(w.ev); k = res.k_B.to_numpy(); ent = res.entry_B.to_numpy(); has = ~np.isnan(ent)
    L = np.clip(mult * np.nan_to_num(k, nan=1), lo, hi); x = np.minimum(60, np.nan_to_num(ent, nan=1) + L - 1).astype(int)
    post = np.full(len(res), np.nan); ctrl = np.full(len(res), np.nan)
    q_all = w.ev.quarter.to_numpy(); idx = res.index.to_numpy(); cache = {}
    for i in np.where(has)[0]:
        e, xx = int(ent[i]), int(x[i])
        if (e, xx) not in cache:
            cache[(e, xx)] = pd.Series(w.span_ab(np.full(E, float(e)), xx) / (xx - e + 1)).groupby(q_all).mean()
        ctrl[i] = cache[(e, xx)].get(q_all[idx[i]], np.nan)
    for xx in np.unique(x[has]):
        m = has & (x == xx); ee = np.full(E, np.nan); ee[idx[m]] = ent[m]; sp = w.span_ab(ee, int(xx)); post[m] = sp[idx[m]] / (xx - ent[m] + 1)
    b = season_bootstrap(post - ctrl, res.quarter.to_numpy())
    return b, float(np.nanmean(post) * 1e4), float(np.nanmean(ctrl) * 1e4), float(np.nanmean(x[has] - ent[has] + 1))
kb = res_base.k_B.to_numpy(); buckets = (("k = 1", kb == 1), ("k = 2-3", (kb >= 2) & (kb <= 3)), ("k = 4-6", (kb >= 4) & (kb <= 6)), ("k = 7-10", (kb >= 7) & (kb <= 10)))
parts = []
for lab, m in buckets:
    r = cell_stats(w_base, res_base[m], H, f"consolidation {lab} | all", {"variant": f"consolidation {lab}", "period": "all", "W": W, "H": H}); rows.append(r)
    parts.append(f"{lab}: n={r['n_events']}, post {r['perday_post']*1e4:+.1f} vs matched {r['matched_control_perday']*1e4:+.1f} bp/d, diff {r['PRIMARY_post_minus_matched']*1e4:+.1f} [{r['PRIMARY_lo']*1e4:+.1f},{r['PRIMARY_hi']*1e4:+.1f}]")
    print(f"consolidation {lab}: {parts[-1]}")
record("R19", "does longer consolidation before the breakout mean more drift after it?", "base breakout cases split by breakout day k", "2005-2026", "k_B", "base rules, W=10, H=40", "buckets 1 / 2-3 / 4-6 / 7-10", "; ".join(parts), "yes", "heterogeneity by consolidation length, reported in full")
for mult in (2, 3):
    b, pp, cc, avgL = hold_variable(w_base, res_base, mult=mult)
    lab = f"hold {mult}x consolidation days after entry (10..50)"
    rows.append({"label": lab + " | all", "variant": lab, "period": "all", "W": W, "H": "variable", "n_events": int(res_base.entered_B.sum()), "share_entered_B": float(res_base.entered_B.mean()), "perday_post": pp / 1e4, "matched_control_perday": cc / 1e4, "PRIMARY_post_minus_matched": b["point"], "PRIMARY_lo": b["ci_lo"], "PRIMARY_hi": b["ci_hi"], "avg_hold_days": avgL})
    print(f"{lab}: post {pp:+.1f} vs matched {cc:+.1f} bp/d, diff {b['point']*1e4:+.1f} [{b['ci_lo']*1e4:+.1f},{b['ci_hi']*1e4:+.1f}], avg hold {avgL:.1f} days")
    record(f"R2{mult-2}", "hold proportional to consolidation length", "base breakout cases", "2005-2026", "k_B", f"enter open(k+1), hold {mult}k days (min 10, max 50), exit close", f"W={W}", f"post {pp:+.1f} vs matched {cc:+.1f} bp/d; diff {b['point']*1e4:+.1f} [{b['ci_lo']*1e4:+.1f},{b['ci_hi']*1e4:+.1f}]; avg hold {avgL:.0f} d", "yes", "candidate-proposed variant; no improvement over the normal path")
# ---- costs on base cell
cs_spread = w_base.corwin_schultz()
res = res_base.copy(); res["spread"] = cs_spread[res.index]
res["liq_tercile"] = pd.qcut(w_base.ev.med60_dv_m1, 3, labels=["low", "mid", "high"]).astype(str).to_numpy()[res.index]
per_side = res["spread"].fillna(res["spread"].median()) / 2 + 0.0005
res["cost_A"] = 2 * per_side; res["cost_B"] = 2 * per_side * res["entered_B"]
res["net_A"] = res["ret_A"] - res["cost_A"]; res["net_B"] = res["ret_B"] - res["cost_B"]
crow = []
res["d0"] = w_base.ev.d0.to_numpy()[res.index]
for lab, r in [("all", res), ("selection_2005_2014", res[res.d0 <= SEL_END]), ("holdout_2015_2026", res[res.d0 > SEL_END])] + [(f"liq {g}", r) for g, r in res.groupby("liq_tercile")]:
    q = r.quarter.to_numpy(); d = {"group": lab, "n": len(r), "median_spread": float(r.spread.median()), "mean_spread": float(r.spread.mean()), "gross_A": r.ret_A.mean(), "net_A": r.net_A.mean(), "gross_B": r.ret_B.mean(), "net_B": r.net_B.mean()}
    for nm, v in (("net_A", r.net_A), ("net_B", r.net_B), ("net_B_minus_net_A", r.net_B - r.net_A)):
        b = season_bootstrap(v.to_numpy(), q); d[f"{nm}_lo"], d[f"{nm}_hi"] = b["ci_lo"], b["ci_hi"]
    crow.append(d)
cdf = pd.DataFrame(crow); cdf.to_csv(OUT / "costs_W10_H40.csv", index=False); print(cdf.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
record("R09", "tradability", f"{len(res)} events", "2005-2026", "Corwin-Schultz spread days -25..-6, half-spread + 5bp per side", "A and B net of costs", f"W={W},H={H}", f"net A {res.net_A.mean():+.4f}, net B {res.net_B.mean():+.4f}, median spread {res.spread.median():.4f}", "yes", "costs reported separately from the hypothesis test")
pd.DataFrame(rows).to_csv(OUT / "robustness_W10_H40.csv", index=False)
rec = pathlib.Path("logs/experiment_record.csv")
old = pd.read_csv(rec, dtype=str) if rec.exists() else pd.DataFrame(columns=list(exp[0].keys()))
new = pd.DataFrame(exp)
merged = pd.concat([old[~old.experiment_id.isin(new.experiment_id)], new], ignore_index=True)
merged["_p"] = merged.experiment_id.str[0]; merged["_k"] = merged.experiment_id.str.extract(r"(\d+)").astype(float); merged = merged.sort_values(["_p", "_k", "experiment_id"]).drop(columns=["_p", "_k"])
merged.to_csv(rec, index=False)  # idempotent: re-runs replace their own rows instead of appending
print("early exits (delisted inside window) in base:", int(res_base.early_exit.sum()))

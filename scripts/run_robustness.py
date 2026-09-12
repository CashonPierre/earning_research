"""Stages 6-7: costs and robustness variants. Appends every run to logs/experiment_record.csv."""
import csv, datetime as dt, json, pathlib, sys, time, zoneinfo
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
    t0 = time.time(); w = Windows(events.reset_index(drop=True))
    selmask = (w.ev.d0 <= SEL_END).to_numpy()
    tmp = run_rules(w, W, H, **kw); m = int(np.nanmedian(tmp.loc[selmask & tmp.entered_B.to_numpy(), "k_B"])) if tmp.entered_B.any() else 2
    res = run_rules(w, W, H, m_fixed=m, **kw); res = res[res.valid_A]
    for per, mask in (("all", np.ones(len(res), bool)), ("selection", selmask[res.index]), ("holdout", ~selmask[res.index])):
        r = cell_stats(w, res[mask], H, f"{label} | {per}", {"variant": label, "period": per, "W": W, "H": H, "m_fixed": m}); rows.append(r)
        if per == "all":
            record(exp_id, "H1: drift concentrated after close > day-0 high", f"{len(w.ev)} events", "2005-2026", note, f"A open(1)->close(H); B breakout entry; C fixed delay {m}; D1-D3 unanchored", f"W={W},H={H}", fmt(r), "yes", "robustness variant reported in full")
    print(f"{label}: {fmt(rows[-3])} ({time.time()-t0:.0f}s)", flush=True)
    return w, res
sel = ev[ev.selected]
w_base, res_base = variant("base top-decile trailing threshold", sel, "R00", "EDGAR 2.02 timing; AR0 >= trailing-4Q 90th pct")
variant("selected grid cell W=15", sel, "R01", "same as base", ) if False else None
# selected grid cell
W, H = 15, 40; variant("grid-selected cell W=15 H=40", sel, "R01", "cell chosen on 2005-2014 lower CI"); W, H = 10, 40
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
# Friday vs other (base results)
for lab, mask in (("Friday day 0", w_base.ev.weekday0.to_numpy() == 4), ("Mon-Thu day 0", w_base.ev.weekday0.to_numpy() != 4)):
    r = cell_stats(w_base, res_base[mask[res_base.index]], H, f"{lab} | all", {"variant": lab, "period": "all", "W": W, "H": H}); rows.append(r); print(f"{lab}: {fmt(r)}")
# ---- costs on base cell
cs_spread = w_base.corwin_schultz()
res = res_base.copy(); res["spread"] = cs_spread[res.index]
res["liq_tercile"] = pd.qcut(w_base.ev.med60_dv_m1, 3, labels=["low", "mid", "high"]).astype(str).to_numpy()[res.index]
per_side = res["spread"].fillna(res["spread"].median()) / 2 + 0.0005
res["cost_A"] = 2 * per_side; res["cost_B"] = 2 * per_side * res["entered_B"]
res["net_A"] = res["ret_A"] - res["cost_A"]; res["net_B"] = res["ret_B"] - res["cost_B"]
crow = []
for lab, r in [("all", res)] + [(f"liq {g}", r) for g, r in res.groupby("liq_tercile")] + [(p, res[res.d0 <= SEL_END] if p == "selection" else res[res.d0 > SEL_END]) for p in ("selection", "holdout")] if False else [("all", res)] + [(f"liq {g}", r) for g, r in res.groupby("liq_tercile")]:
    q = r.quarter.to_numpy(); d = {"group": lab, "n": len(r), "median_spread": float(r.spread.median()), "mean_spread": float(r.spread.mean()), "gross_A": r.ret_A.mean(), "net_A": r.net_A.mean(), "gross_B": r.ret_B.mean(), "net_B": r.net_B.mean()}
    for nm, v in (("net_A", r.net_A), ("net_B", r.net_B), ("net_B_minus_net_A", r.net_B - r.net_A)):
        b = season_bootstrap(v.to_numpy(), q); d[f"{nm}_lo"], d[f"{nm}_hi"] = b["ci_lo"], b["ci_hi"]
    crow.append(d)
cdf = pd.DataFrame(crow); cdf.to_csv(OUT / "costs_W10_H40.csv", index=False); print(cdf.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
record("R09", "tradability", f"{len(res)} events", "2005-2026", "Corwin-Schultz spread days -25..-6, half-spread + 5bp per side", "A and B net of costs", f"W={W},H={H}", f"net A {res.net_A.mean():+.4f}, net B {res.net_B.mean():+.4f}, median spread {res.spread.median():.4f}", "yes", "costs reported separately from the hypothesis test")
pd.DataFrame(rows).to_csv(OUT / "robustness_W10_H40.csv", index=False)
with open("logs/experiment_record.csv", "a", newline="") as f:
    wtr = csv.DictWriter(f, fieldnames=list(exp[0].keys())); wtr.writerows(exp)
print("early exits (delisted inside window) in base:", int(res_base.early_exit.sum()))

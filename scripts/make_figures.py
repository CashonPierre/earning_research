"""Stage 8: figures for the report (matplotlib, Agg)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from pead.backtest import Windows, run_rules
SEL_END = "2014-12-31"; W, H = 10, 40; FIG = pathlib.Path("outputs/figures"); FIG.mkdir(parents=True, exist_ok=True)
ev = pd.read_parquet("data/processed/events.parquet"); sel = ev[ev.selected].reset_index(drop=True)
win = Windows(sel); res = run_rules(win, W, H, m_fixed=2)
path = win.event_time_path(60); q = sel.quarter.to_numpy(); selmask = (sel.d0 <= SEL_END).to_numpy()
def season_ci(mat, groups, n_boot=2000, seed=0):
    rng = np.random.default_rng(seed); g = pd.Series(groups); keys = g.unique(); idx = [np.where(g.values == k)[0] for k in keys]
    sums = np.array([mat[i].sum(axis=0) for i in idx]); cnts = np.array([len(i) for i in idx], dtype=float)
    draws = rng.integers(0, len(keys), size=(n_boot, len(keys))); boot = sums[draws].sum(axis=1) / cnts[draws].sum(axis=1)[:, None]
    return np.quantile(boot, 0.025, axis=0), np.quantile(boot, 0.975, axis=0)
# 1. event-time CAR paths
fig, ax = plt.subplots(figsize=(8, 4.5))
for lab, m, c in (("all 2005-2026", np.ones(len(sel), bool), "k"), ("2005-2014", selmask, "tab:blue"), ("2015-2026", ~selmask, "tab:red")):
    car = np.cumsum(path[m], axis=1); mu = car.mean(axis=0) * 100; lo, hi = season_ci(car, q[m]); x = np.arange(1, 61)
    ax.plot(x, mu, color=c, label=f"{lab} (n={m.sum()})"); ax.fill_between(x, lo * 100, hi * 100, color=c, alpha=0.12)
ax.axhline(0, color="gray", lw=0.8); ax.set_xlabel("trading days after day 0"); ax.set_ylabel("cumulative abnormal return, % (Rule A path)"); ax.legend(); ax.set_title("Post-announcement CAR of top-decile day-0 reactions (season-bootstrap 95% CI)")
fig.tight_layout(); fig.savefig(FIG / "fig1_car_paths.png", dpi=150); plt.close(fig)
# 2. daily AR aligned on breakout day vs matched unconditional path
k = res.k_B.to_numpy(); ent = res.entry_B.to_numpy(); has = ~np.isnan(ent)
tau = np.arange(-5, 21); al = np.full((has.sum(), len(tau)), np.nan); ctrl = np.full_like(al, np.nan)
seasons = {s: path[q == s].mean(axis=0) for s in np.unique(q)}
for r, i in enumerate(np.where(has)[0]):
    kk = int(k[i])
    for j, t in enumerate(tau):
        d = kk + t
        if 1 <= d <= 60:
            al[r, j] = path[i, d - 1]; ctrl[r, j] = seasons[q[i]][d - 1]
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(tau, np.nanmean(al, axis=0) * 1e4, "o-", color="tab:red", label="breakout events, daily AR (bp)")
ax.plot(tau, np.nanmean(ctrl, axis=0) * 1e4, "s--", color="gray", label="matched unconditional path (same season and event day)")
ax.axvline(0, color="k", lw=0.8, ls=":"); ax.axvline(1, color="tab:green", lw=0.8, ls=":"); ax.text(1.1, ax.get_ylim()[1] * 0.9, "entry open", color="tab:green", fontsize=8)
ax.set_xlabel("trading days relative to breakout day k (close > day-0 high)"); ax.set_ylabel("mean daily abnormal return, bp"); ax.legend(); ax.set_title(f"Daily abnormal returns around the breakout (W={W}, H={H}; n={has.sum()})")
fig.tight_layout(); fig.savefig(FIG / "fig2_breakout_aligned.png", dpi=150); plt.close(fig)
# zoom on post-entry days only
fig, ax = plt.subplots(figsize=(8, 4)); post = tau >= 1
ax.bar(tau[post] - 0.2, np.nanmean(al[:, post], axis=0) * 1e4, 0.4, color="tab:red", label="breakout events"); ax.bar(tau[post] + 0.2, np.nanmean(ctrl[:, post], axis=0) * 1e4, 0.4, color="gray", label="matched unconditional")
ax.axhline(0, color="k", lw=0.8); ax.set_xlabel("days after breakout"); ax.set_ylabel("mean daily AR, bp"); ax.legend(); ax.set_title("After the breakout: no excess drift relative to the unconditional path")
fig.tight_layout(); fig.savefig(FIG / "fig3_post_breakout_bars.png", dpi=150); plt.close(fig)
# 4. breakout day histogram and range placement
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
kk = res.k_B.dropna().astype(int); axes[0].bar(*np.unique(kk, return_counts=True), color="tab:blue"); axes[0].set_xlabel("breakout day k (W=10)"); axes[0].set_ylabel("events"); axes[0].set_title(f"Breakout day; {(~has).sum()} of {len(res)} never break out")
axes[1].hist(sel.range_pos.dropna(), bins=25, color="tab:orange"); axes[1].set_xlabel("day-0 close position in day-0 range (0=low, 1=high)"); axes[1].set_title("Range placement of the day-0 close")
fig.tight_layout(); fig.savefig(FIG / "fig4_breakout_day_and_range.png", dpi=150); plt.close(fig)
# 5. grid heatmaps
g = pd.read_csv("outputs/tables/grid_results.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, per in zip(axes, ("selection_2005_2014", "holdout_2015_2026")):
    pv = g[g.label == per].pivot(index="W", columns="H", values="B_minus_A") * 100
    im = ax.imshow(pv.values, cmap="RdBu", vmin=-1.5, vmax=1.5, aspect="auto"); ax.set_xticks(range(len(pv.columns))); ax.set_xticklabels(pv.columns); ax.set_yticks(range(len(pv.index))); ax.set_yticklabels(pv.index)
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]): ax.text(j, i, f"{pv.values[i, j]:+.2f}", ha="center", va="center", fontsize=9)
    ax.set_xlabel("holding length H"); ax.set_ylabel("max wait W"); ax.set_title(f"Rule B minus Rule A, % ({per})")
fig.colorbar(im, ax=axes, shrink=0.8); fig.savefig(FIG / "fig5_grid_B_minus_A.png", dpi=150, bbox_inches="tight"); plt.close(fig)
# 6. calendar-time cumulative
ct = pd.read_csv("outputs/tables/calendar_time_series_W10_H40.csv", index_col=0)
cal = pd.DatetimeIndex(sorted(pd.read_parquet("data/processed/panel.parquet", columns=["ticker", "date"]).query("ticker == 'SPY'").date.unique()))
ct["date"] = cal[ct.index.to_numpy()]
fig, ax = plt.subplots(figsize=(8, 4.5))
for s, lab, c in (("rA", "Rule A book", "tab:blue"), ("rB", "Rule B book", "tab:red"), ("d", "B minus A", "k")): ax.plot(ct.date, ct[s].cumsum() * 100, color=c, label=lab)
ax.axhline(0, color="gray", lw=0.8); ax.set_ylabel("cumulative daily abnormal return, % (equal-weight, days with >= 10 positions)"); ax.legend(); ax.set_title("Calendar-time portfolios (W=10, H=40)")
fig.tight_layout(); fig.savefig(FIG / "fig6_calendar_time.png", dpi=150); plt.close(fig)
print("figures written:", sorted(p.name for p in FIG.glob("*.png")))

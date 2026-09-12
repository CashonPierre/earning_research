"""Shared summary helpers for grid and robustness runs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import Windows, run_rules, season_bootstrap


def matched_control(win: Windows, res: pd.DataFrame, H: int) -> np.ndarray:
    """For each breakout event with entry day e=k+1, the unconditional mean per-day abnormal return of ALL
    events in the same season over event days e..H (Rule A path). Removes the mechanical conditioning
    of the post-breakout leg while matching event time and season."""
    path = win.event_time_path(H)  # E x H daily AR, day 1..H
    q = win.ev["quarter"].to_numpy()
    out = np.full(len(res), np.nan)
    cum = {}
    for s in np.unique(q):
        m = path[q == s].mean(axis=0)            # mean daily AR by event day for that season
        cum[s] = np.concatenate([[0.0], np.cumsum(m)])  # cum[d] = sum of days 1..d
    ent = res["entry_B"].to_numpy()
    for i in range(len(res)):
        if np.isnan(ent[i]):
            continue
        e = int(ent[i]); c = cum[q[i]]
        out[i] = (c[H] - c[e - 1]) / (H - e + 1)
    return out


def cell_stats(win: Windows, res: pd.DataFrame, H: int, label: str, extra: dict | None = None) -> dict:
    q = res["quarter"].to_numpy()
    ctrl = matched_control(win, res, H) if "entry_B" in res else None
    r = {"label": label, "n_events": int(len(res)), "share_entered_B": float(res["entered_B"].mean()), "median_k": float(np.nanmedian(res["k_B"]))}
    for name, v in (("CAR_A", res["ret_A"]), ("CAR_B", res["ret_B"]), ("B_minus_A", res["ret_B"] - res["ret_A"]),
                    ("C_minus_A", res["ret_C"] - res["ret_A"] if "ret_C" in res else pd.Series(np.nan, index=res.index)),
                    ("D1_minus_A", res["ret_D1"] - res["ret_A"]), ("D2_minus_A", res["ret_D2"] - res["ret_A"]), ("D3_minus_A", res["ret_D3"] - res["ret_A"]),
                    ("perday_post", res["perday_post"]), ("perday_A", res["perday_A"])):
        b = season_bootstrap(v.to_numpy(), q)
        r[name], r[f"{name}_lo"], r[f"{name}_hi"] = b["point"], b["ci_lo"], b["ci_hi"]
    if ctrl is not None:
        d = res["perday_post"].to_numpy() - ctrl
        b = season_bootstrap(d, q)
        r["PRIMARY_post_minus_matched"], r["PRIMARY_lo"], r["PRIMARY_hi"] = b["point"], b["ci_lo"], b["ci_hi"]
        r["matched_control_perday"] = float(np.nanmean(ctrl))
    r.update(extra or {})
    return r

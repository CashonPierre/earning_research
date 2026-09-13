"""Shared summary helpers for grid and robustness runs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import Windows, run_rules, season_bootstrap


def matched_control(win: Windows, res: pd.DataFrame, H: int, sign: float = 1.0) -> np.ndarray:
    """For each breakout event with entry day e = k+1, the mean per-day abnormal return that ALL selected
    events in the same season earned over the identical span open(e) -> close(H). Same span basis as the
    treated leg (so the overnight gap into the entry day is excluded from both), matched on season and
    event time; this removes the mechanical conditioning of the pre-breakout leg.
    `res` may be any subset of win.ev; rows are aligned through res.index."""
    q_all = win.ev["quarter"].to_numpy()
    E = len(win.ev)
    idx = res.index.to_numpy()
    ent = res["entry_B"].to_numpy()
    out = np.full(len(res), np.nan)
    cache = {}
    for e in np.unique(ent[~np.isnan(ent)]).astype(int):
        span = sign * win.span_ab(np.full(E, float(e)), H) / (H - e + 1)
        cache[e] = pd.Series(span).groupby(q_all).mean()
    for j, (i, e) in enumerate(zip(idx, ent)):
        if np.isnan(e):
            continue
        out[j] = cache[int(e)].get(q_all[i], np.nan)
    return out


def cell_stats(win: Windows, res: pd.DataFrame, H: int, label: str, extra: dict | None = None, sign: float = 1.0) -> dict:
    q = res["quarter"].to_numpy()
    ctrl = matched_control(win, res, H, sign=sign) if "entry_B" in res else None
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

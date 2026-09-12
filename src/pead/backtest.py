"""Vectorised event-window backtest for Rule A, Rule B and the controls.

Conventions (trading days relative to day 0 = reaction session):
- Rule A: enter open(1), exit close(H).
- Rule B: k = first day in 1..W with adj close > adj high(0); enter open(k+1) if k+1 <= H; exit close(H); flat otherwise.
- Rule C: fixed delay m (median k of Rule B in the selection period): enter open(m+1) unconditionally.
- Rule D: like B with an unanchored level: D1 close(0); D2 high(0)*1.03; D3 high(1) (trigger from day 2).
- Abnormal = stock return minus SPY return over the same open/close span. A position whose bars end
  (delisting) exits at its last close and earns 0 afterwards.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import load_panel

HMAX = 60
PRE = 26  # bars before day 0 kept in the window (for the Corwin-Schultz spread over days -25..-6)


class Windows:
    """Per-event matrices; column j corresponds to day j - PRE (so day 0 is column PRE)."""

    def __init__(self, ev: pd.DataFrame, hmax: int = HMAX, pre: int = PRE):
        need = ["ticker", "idx", "adj_open", "adj_high", "adj_low", "adj_close"]
        panel = load_panel(need)
        tickers = sorted(set(ev["ticker"]) | {"SPY"})
        panel = panel[panel["ticker"].isin(tickers)]
        code = {t: i for i, t in enumerate(tickers)}
        n_days = int(panel["idx"].max()) + 1
        rows = panel["ticker"].map(code).to_numpy()
        cols = panel["idx"].to_numpy()
        self.arr = {}
        for f in ("adj_open", "adj_high", "adj_low", "adj_close"):
            a = np.full((len(tickers), n_days), np.nan, dtype="float32")
            a[rows, cols] = panel[f].to_numpy()
            self.arr[f] = a
        del panel
        self.pre, self.hmax = pre, hmax
        offs = np.arange(-pre, hmax + 1)
        base = ev["idx0"].to_numpy()
        c = base[:, None] + offs[None, :]
        ok = (c >= 0) & (c < n_days)
        cc = np.clip(c, 0, n_days - 1)
        r = ev["ticker"].map(code).to_numpy()
        spy = code["SPY"]

        def take(f, rr):
            a = self.arr[f][rr[:, None] if rr.ndim == 1 else rr, cc].astype("float64")
            a[~ok] = np.nan
            return a

        self.open, self.high, self.low, self.close = (take(f, r) for f in ("adj_open", "adj_high", "adj_low", "adj_close"))
        spy_r = np.full(len(ev), spy)
        self.spy_open, self.spy_close = take("adj_open", spy_r), take("adj_close", spy_r)
        self.idx0 = base
        self.ev = ev.reset_index(drop=True)
        # forward-filled closes for delisting handling and the last valid day
        cl = pd.DataFrame(self.close)
        self.close_ff = cl.ffill(axis=1).to_numpy()
        valid = ~np.isnan(self.close)
        j = np.where(valid, np.arange(self.close.shape[1])[None, :], -1)
        self.last_valid_col = j.max(axis=1)
        del self.arr

    def col(self, day: int) -> int:
        return self.pre + day

    # ---------------------------------------------------------------- helpers
    def span_ab(self, entry_day: np.ndarray, exit_day: int) -> np.ndarray:
        """Abnormal return from open(entry_day) to close(exit_day), honouring early exits; NaN if no entry."""
        E = len(entry_day)
        out = np.full(E, np.nan)
        has = ~np.isnan(entry_day)
        ed = np.where(has, entry_day, 1).astype(int)
        ce = self.col(ed)
        cx = np.minimum(self.col(exit_day), self.last_valid_col)
        po = self.open[np.arange(E), ce]
        px = self.close_ff[np.arange(E), cx]
        so = self.spy_open[np.arange(E), ce]
        sx = self.spy_close[np.arange(E), cx]
        r = (px / po - 1.0) - (sx / so - 1.0)
        ok = has & (cx >= ce) & ~np.isnan(po)
        out[ok] = r[ok]
        return out

    def span_ab_close(self, entry_day: np.ndarray, exit_day: int) -> np.ndarray:
        """Abnormal return from close(entry_day) to close(exit_day) (market-on-close entry variant)."""
        E = len(entry_day)
        out = np.full(E, np.nan)
        has = ~np.isnan(entry_day)
        ed = np.where(has, entry_day, 0).astype(int)
        ce = self.col(ed)
        cx = np.minimum(self.col(exit_day), self.last_valid_col)
        pe = self.close[np.arange(E), ce]
        px = self.close_ff[np.arange(E), cx]
        se = self.spy_close[np.arange(E), ce]
        sx = self.spy_close[np.arange(E), cx]
        r = (px / pe - 1.0) - (sx / se - 1.0)
        ok = has & (cx > ce) & ~np.isnan(pe)
        out[ok] = r[ok]
        return out

    def event_time_path(self, H: int) -> np.ndarray:
        """E x H matrix of Rule-A daily abnormal returns (day 1 = open->close, then close->close)."""
        m, _ = self.daily_ab(np.ones(len(self.ev)), H)
        return m

    def daily_ab(self, entry_day: np.ndarray, H: int) -> np.ndarray:
        """E x H matrix of daily abnormal returns for a position entered at open(entry_day), 0 when flat."""
        E = len(entry_day)
        days = np.arange(1, H + 1)
        cols = self.col(days)
        c_prev = cols - 1
        cl = self.close_ff[:, cols]
        cl_prev = self.close_ff[:, c_prev]
        op = self.open[:, cols]
        scl, scl_prev, sop = self.spy_close[:, cols], self.spy_close[:, c_prev], self.spy_open[:, cols]
        cc = (cl / cl_prev - 1.0) - (scl / scl_prev - 1.0)          # close-to-close abnormal
        oc = (cl / op - 1.0) - (scl / sop - 1.0)                     # entry-day open-to-close abnormal
        ed = entry_day[:, None]
        active = (days[None, :] >= ed) & (cols[None, :] <= self.last_valid_col[:, None]) & ~np.isnan(ed)
        m = np.where(days[None, :] == ed, oc, cc)
        m = np.where(active, m, 0.0)
        m = np.nan_to_num(m, nan=0.0)
        return m, active

    def breakout_day(self, level: np.ndarray, W: int, first_day: int = 1, below: bool = False) -> np.ndarray:
        """First day k in first_day..W with close > level (or < level if below); NaN if none."""
        days = np.arange(first_day, W + 1)
        cl = self.close[:, self.col(days)]
        hit = (cl < level[:, None]) if below else (cl > level[:, None])
        any_hit = hit.any(axis=1)
        k = np.where(any_hit, days[np.argmax(hit, axis=1)], np.nan)
        return k

    def corwin_schultz(self, d_from: int = -25, d_to: int = -6) -> np.ndarray:
        """Corwin-Schultz (2012) spread estimate per event from daily high/low over days d_from..d_to."""
        c = self.col(np.arange(d_from, d_to + 1))
        H, L = self.high[:, c], self.low[:, c]
        with np.errstate(invalid="ignore", divide="ignore"):
            b = np.log(H / L) ** 2
            beta = b[:, :-1] + b[:, 1:]
            hh = np.maximum(H[:, :-1], H[:, 1:])
            ll = np.minimum(L[:, :-1], L[:, 1:])
            gamma = np.log(hh / ll) ** 2
            k = 3 - 2 * np.sqrt(2)
            alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
            s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
        s = np.where(np.isnan(s), np.nan, np.maximum(s, 0.0))
        return np.nanmean(s, axis=1)


def run_rules(win: Windows, W: int, H: int, m_fixed: int | None = None, first_day: int = 1, short: bool = False, moc: bool = False) -> pd.DataFrame:
    """Per-event results for one (W, H) cell. short=True mirrors the rules (trigger below day-0 low, returns negated).
    moc=True enters at the signal close instead of the next open (Rule A at close(1))."""
    ev = win.ev
    E = len(ev)
    high0 = win.close[:, win.col(0)] * 0 + win.high[:, win.col(0)]
    close0 = win.close[:, win.col(0)]
    high1 = win.high[:, win.col(1)]
    one = np.ones(E)
    low0 = win.low[:, win.col(0)]
    sign = -1.0 if short else 1.0
    kB = win.breakout_day(low0 if short else high0, W, first_day=first_day, below=short)
    entB = np.where(~np.isnan(kB) & (kB + 1 <= H), kB + 1, np.nan)
    span = (lambda e, h: win.span_ab_close(e - 1, h)) if moc else win.span_ab
    out = pd.DataFrame({"event_id": ev["event_id"].to_numpy(), "quarter": ev["quarter"].to_numpy(), "W": W, "H": H,
                        "k_B": kB, "entry_B": entB})
    out["ret_A"] = sign * win.span_ab(one, H)  # Rule A always enters at open(1); moc affects only signal-based entries
    rB = sign * span(entB, H)
    out["ret_B"] = np.where(np.isnan(entB), 0.0, np.nan_to_num(rB, nan=0.0))
    out["entered_B"] = ~np.isnan(entB) & ~np.isnan(rB)
    # legs: pre = open(1) -> open(k+1); post = open(k+1) -> close(H)
    Ei = np.arange(E)
    ce = win.col(np.where(np.isnan(entB), 1, entB).astype(int))
    po1 = win.open[:, win.col(1)]
    pok = win.open[Ei, ce]
    so1 = win.spy_open[:, win.col(1)]
    sok = win.spy_open[Ei, ce]
    pre = sign * ((pok / po1 - 1.0) - (sok / so1 - 1.0))
    out["leg_pre"] = np.where(out["entered_B"], pre, np.nan)
    out["leg_post"] = np.where(out["entered_B"], rB, np.nan)
    out["days_pre"] = np.where(out["entered_B"], kB, np.nan)          # sessions open(1)->open(k+1) = k
    out["days_post"] = np.where(out["entered_B"], H - kB, np.nan)     # sessions open(k+1)->close(H)
    out["perday_pre"] = out["leg_pre"] / out["days_pre"]
    out["perday_post"] = out["leg_post"] / out["days_post"]
    out["perday_A"] = out["ret_A"] / H
    out["perday_nonbreak"] = np.where(out["entered_B"], np.nan, out["ret_A"] / H)
    # controls
    if m_fixed is not None:
        entC = np.full(E, float(m_fixed + 1))
        out["ret_C"] = sign * np.nan_to_num(span(entC, H), nan=0.0)
    low1 = win.low[:, win.col(1)]
    levels = (("D1", close0, 1), ("D2", low0 * 0.97, 1), ("D3", low1, 2)) if short else (("D1", close0, 1), ("D2", high0 * 1.03, 1), ("D3", high1, 2))
    for name, level, fd in levels:
        k = win.breakout_day(level, W, first_day=max(fd, first_day), below=short)
        ent = np.where(~np.isnan(k) & (k + 1 <= H), k + 1, np.nan)
        r = sign * span(ent, H)
        out[f"k_{name}"] = k
        out[f"ret_{name}"] = np.where(np.isnan(ent), 0.0, np.nan_to_num(r, nan=0.0))
        out[f"entered_{name}"] = ~np.isnan(ent) & ~np.isnan(r)
    out["early_exit"] = win.last_valid_col < win.col(H)
    out["valid_A"] = ~np.isnan(out["ret_A"])
    return out


def calendar_time(win: Windows, entry_A: np.ndarray, entry_B: np.ndarray, H: int, min_breadth: int = 10) -> pd.DataFrame:
    """Daily equal-weight abnormal returns of the A and B books on the trading calendar."""
    mA, actA = win.daily_ab(entry_A, H)
    mB, _ = win.daily_ab(entry_B, H)
    days = np.arange(1, H + 1)
    cal_idx = (win.idx0[:, None] + days[None, :]).ravel()
    df = pd.DataFrame({"idx": cal_idx, "rA": mA.ravel(), "rB": mB.ravel(), "act": actA.ravel()})
    df = df[df["act"]]
    g = df.groupby("idx")
    s = pd.DataFrame({"rA": g["rA"].mean(), "rB": g["rB"].mean(), "n": g.size()})
    s["d"] = s["rB"] - s["rA"]
    return s[s["n"] >= min_breadth]


# ------------------------------------------------------------------ statistics
def newey_west_t(x: np.ndarray, lag: int) -> tuple[float, float, float]:
    x = np.asarray(x, dtype="float64")
    x = x[~np.isnan(x)]
    n = len(x)
    mu = x.mean()
    e = x - mu
    var = (e @ e) / n
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        var += 2 * w * (e[L:] @ e[:-L]) / n
    se = np.sqrt(var / n)
    return mu, se, mu / se if se > 0 else np.nan


def season_bootstrap(values: np.ndarray, groups: np.ndarray, n_boot: int = 5000, seed: int = 0, stat=None, values2=None, groups2=None):
    """Bootstrap the mean (or a difference of two means) by resampling season blocks with replacement.
    values/groups define sample 1; values2/groups2 an optional second sample whose mean is subtracted."""
    rng = np.random.default_rng(seed)

    def per_group(v, g):
        d = pd.DataFrame({"v": v, "g": g}).dropna()
        agg = d.groupby("g")["v"].agg(["sum", "count"])
        return agg

    a1 = per_group(values, groups)
    seasons = sorted(set(a1.index) | (set(per_group(values2, groups2).index) if values2 is not None else set()))
    S = len(seasons)
    s1 = a1.reindex(seasons).fillna(0.0)
    sums1, cnt1 = s1["sum"].to_numpy(), s1["count"].to_numpy()
    if values2 is not None:
        s2 = per_group(values2, groups2).reindex(seasons).fillna(0.0)
        sums2, cnt2 = s2["sum"].to_numpy(), s2["count"].to_numpy()
    draws = rng.integers(0, S, size=(n_boot, S))
    m1 = sums1[draws].sum(axis=1) / np.maximum(cnt1[draws].sum(axis=1), 1)
    if values2 is not None:
        m2 = sums2[draws].sum(axis=1) / np.maximum(cnt2[draws].sum(axis=1), 1)
        boot = m1 - m2
        point = sums1.sum() / cnt1.sum() - sums2.sum() / cnt2.sum()
    else:
        boot = m1
        point = sums1.sum() / cnt1.sum()
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return {"point": float(point), "ci_lo": float(lo), "ci_hi": float(hi), "n_seasons": int(S)}


def season_share(values: np.ndarray, groups: np.ndarray) -> tuple[float, int]:
    d = pd.DataFrame({"v": values, "g": groups}).dropna().groupby("g")["v"].mean()
    return float((d > 0).mean()), int(len(d))

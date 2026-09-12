"""Construct earnings events from EDGAR Item 2.02 8-K acceptance timestamps.

Day-0 rule (America/New_York): acceptance before 09:30 -> day 0 = first trading day on or after
the acceptance date ('bmo'); at or after 16:00 -> first trading day after ('amc'); between
09:30 and 16:00 -> 'intraday' (flagged, excluded from the main sample).
"""
from __future__ import annotations

import logging
import pathlib

import numpy as np
import pandas as pd

from .panel import EXCHANGES, common_stock_master, load_panel

log = logging.getLogger(__name__)
RAW = pathlib.Path("data/raw")
PROC = pathlib.Path("data/processed")
PARAMS = {"min_price": 5.0, "min_med60_dv": 1_000_000.0, "min_history_bars": 120, "select_pct": 0.90,
          "min_threshold_quarters": 2, "min_threshold_events": 200, "dedupe_days": 20,
          "sample_start": "2005-01-03", "sample_end": "2026-06-12"}


def assign_day0(edgar: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.DataFrame:
    e = edgar[edgar["form"] == "8-K"].copy()
    et = e["accepted_et"]
    minutes = et.dt.hour * 60 + et.dt.minute
    e["timing"] = np.where(minutes < 9 * 60 + 30, "bmo", np.where(minutes >= 16 * 60, "amc", "intraday"))
    day = pd.to_datetime(et.dt.date)
    pos_ge = np.searchsorted(cal.values, day.values, side="left")   # first trading day >= day
    pos_gt = np.searchsorted(cal.values, day.values, side="right")  # first trading day > day
    e["idx0"] = np.where(e["timing"] == "amc", pos_gt, pos_ge).astype("int64")
    e = e[e["idx0"] < len(cal)]
    e["d0"] = cal[e["idx0"].to_numpy()]
    return e


def build_events(out: pathlib.Path = PROC / "events.parquet") -> tuple[pd.DataFrame, dict]:
    p = PARAMS
    panel = load_panel(["ticker", "date", "idx", "close_unadj", "adj_open", "adj_high", "adj_low", "adj_close", "ab_ret", "med60_dv", "std60_ab", "nbars"])
    cal = pd.DatetimeIndex(sorted(panel.loc[panel["ticker"] == "SPY", "date"].unique()))
    funnel = {}
    edgar = pd.read_parquet(RAW / "edgar_8k_202.parquet")
    funnel["edgar_item202_rows"] = len(edgar)
    ev = assign_day0(edgar, cal)
    funnel["8k_not_amended"] = len(ev)
    ev = ev[(ev["d0"] >= "2004-09-01")]
    ev = ev.drop_duplicates(["cik", "idx0"])
    funnel["unique_cik_day0"] = len(ev)
    # CIK -> candidate tickers with validity intervals
    cs = common_stock_master()
    cand = ev.merge(cs[["cik", "ticker", "primary_exchange", "valid_from", "valid_to"]], on="cik", how="inner")
    cand = cand[(cand["d0"] > cand["valid_from"]) & (cand["d0"] <= cand["valid_to"])]
    funnel["with_candidate_ticker"] = cand.drop_duplicates(["cik", "idx0"]).shape[0]
    # attach day 0 and day -1 panel rows
    p0 = panel.rename(columns={c: f"{c}0" for c in panel.columns if c not in ("ticker", "idx")})
    pm = panel.rename(columns={c: f"{c}_m1" for c in panel.columns if c not in ("ticker", "idx")})
    cand["idx_m1"] = cand["idx0"] - 1
    cand = cand.merge(p0, on=["ticker", "idx"] if "idx" in cand else None, how="inner") if False else cand.merge(p0.rename(columns={"idx": "idx0"}), on=["ticker", "idx0"], how="inner")
    cand = cand.merge(pm.rename(columns={"idx": "idx_m1"}), on=["ticker", "idx_m1"], how="inner")
    cand = cand[cand["ab_ret0"].notna()]
    # one ticker per (cik, day 0): the most liquid share class
    cand = cand.sort_values(["cik", "idx0", "med60_dv_m1"], ascending=[True, True, False])
    ev = cand.drop_duplicates(["cik", "idx0"]).copy()
    funnel["matched_to_prices"] = len(ev)
    # drop follow-up filings within dedupe_days of a kept event for the same company
    ev = ev.sort_values(["cik", "idx0"]).reset_index(drop=True)
    keep = np.ones(len(ev), dtype=bool)
    last_kept = {}
    for i, (cik, idx0) in enumerate(zip(ev["cik"].to_numpy(), ev["idx0"].to_numpy())):
        lk = last_kept.get(cik)
        if lk is not None and idx0 - lk <= p["dedupe_days"]:
            keep[i] = False
        else:
            last_kept[cik] = idx0
    ev = ev[keep].copy()
    funnel["after_dedupe_20d"] = len(ev)
    # derived event variables
    ev["ar0"] = ev["ab_ret0"].astype("float64")
    ev["z0"] = ev["ar0"] / ev["std60_ab_m1"].astype("float64")
    rng = (ev["adj_high0"] - ev["adj_low0"]).astype("float64")
    ev["range_pos"] = np.where(rng > 0, (ev["adj_close0"] - ev["adj_low0"]) / rng, np.nan)
    ev["gap0"] = ev["adj_open0"] / ev["adj_close_m1"] - 1.0
    ev["quarter"] = ev["d0"].dt.to_period("Q").astype(str)
    ev["weekday0"] = ev["d0"].dt.dayofweek
    # filters (all from day -1 or static master fields)
    f_exch = ev["primary_exchange"].isin(EXCHANGES)
    f_price = ev["close_unadj_m1"] >= p["min_price"]
    f_liq = ev["med60_dv_m1"] >= p["min_med60_dv"]
    f_hist = ev["nbars_m1"] >= p["min_history_bars"]
    f_time = ev["timing"] != "intraday"
    ev["passes_filters"] = f_exch & f_price & f_liq & f_hist
    funnel["exchange_filter"] = int(f_exch.sum())
    funnel["plus_price_filter"] = int((f_exch & f_price).sum())
    funnel["plus_liquidity_filter"] = int((f_exch & f_price & f_liq).sum())
    funnel["plus_history_filter"] = int(ev["passes_filters"].sum())
    funnel["plus_not_intraday"] = int((ev["passes_filters"] & f_time).sum())
    # real-time selection threshold: 90th pct of AR0 among filtered, non-intraday events in the previous 4 quarters
    pool = ev[ev["passes_filters"] & f_time]
    qs = sorted(ev["quarter"].unique())
    thr = {}
    by_q = {q: g["ar0"].to_numpy() for q, g in pool.groupby("quarter")}
    for i, q in enumerate(qs):
        prev = [by_q[x] for x in qs[max(0, i - 4):i] if x in by_q]
        if len(prev) >= p["min_threshold_quarters"]:
            arr = np.concatenate(prev)
            thr[q] = float(np.quantile(arr, p["select_pct"])) if len(arr) >= p["min_threshold_events"] else np.nan
        else:
            thr[q] = np.nan
    ev["threshold"] = ev["quarter"].map(thr)
    in_sample = (ev["d0"] >= p["sample_start"]) & (ev["d0"] <= p["sample_end"])
    ev["in_sample_period"] = in_sample
    ev["selected"] = ev["passes_filters"] & f_time & in_sample & ev["threshold"].notna() & (ev["ar0"] >= ev["threshold"])
    ev["selected_fixed5"] = ev["passes_filters"] & f_time & in_sample & (ev["ar0"] >= 0.05)
    ev["selected_z2"] = ev["passes_filters"] & f_time & in_sample & (ev["z0"] >= 2.0)
    ev["selected_bottom"] = ev["passes_filters"] & f_time & in_sample & ev["threshold"].notna() & (ev["ar0"] <= ev.groupby("quarter")["ar0"].transform(lambda s: np.nan))  # placeholder, set below
    # bottom decile threshold for the short-side mirror (10th pct of trailing pool)
    thr_lo = {}
    for i, q in enumerate(qs):
        prev = [by_q[x] for x in qs[max(0, i - 4):i] if x in by_q]
        if len(prev) >= p["min_threshold_quarters"]:
            arr = np.concatenate(prev)
            thr_lo[q] = float(np.quantile(arr, 1 - p["select_pct"])) if len(arr) >= p["min_threshold_events"] else np.nan
        else:
            thr_lo[q] = np.nan
    ev["threshold_lo"] = ev["quarter"].map(thr_lo)
    ev["selected_bottom"] = ev["passes_filters"] & f_time & in_sample & ev["threshold_lo"].notna() & (ev["ar0"] <= ev["threshold_lo"])
    funnel["in_sample_period_filtered"] = int((ev["passes_filters"] & f_time & in_sample).sum())
    funnel["selected_top_decile_trailing"] = int(ev["selected"].sum())
    funnel["selected_fixed_5pct"] = int(ev["selected_fixed5"].sum())
    funnel["selected_z0_ge_2"] = int(ev["selected_z2"].sum())
    funnel["selected_bottom_decile"] = int(ev["selected_bottom"].sum())
    ev["event_id"] = np.arange(len(ev), dtype="int64")
    cols = ["event_id", "cik", "ticker", "accession", "accepted_et", "timing", "d0", "idx0", "quarter", "weekday0", "primary_exchange",
            "close_unadj_m1", "med60_dv_m1", "std60_ab_m1", "nbars_m1", "adj_close_m1", "adj_open0", "adj_high0", "adj_low0", "adj_close0",
            "ar0", "z0", "gap0", "range_pos", "passes_filters", "in_sample_period", "threshold", "threshold_lo", "selected", "selected_fixed5", "selected_z2", "selected_bottom"]
    ev = ev[cols].reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(out, compression="zstd", index=False)
    return ev, funnel


def timing_validation(ev: pd.DataFrame) -> pd.DataFrame:
    """Share of filtered events whose |abnormal return| peaks on the assigned day 0 rather than day -1 or +1."""
    panel = load_panel(["ticker", "idx", "ab_ret"])
    base = ev[ev["passes_filters"]][["event_id", "ticker", "idx0", "timing"]].copy()
    rows = []
    for off in (-1, 0, 1):
        m = base.assign(idx=base["idx0"] + off).merge(panel, on=["ticker", "idx"], how="left")
        rows.append(m.set_index("event_id")["ab_ret"].abs().rename(f"a{off}"))
    a = pd.concat(rows, axis=1).join(base.set_index("event_id")["timing"])
    a["peak_on_d0"] = (a["a0"] >= a["a-1"]) & (a["a0"] >= a["a1"])
    a["peak_on_dm1"] = (a["a-1"] > a["a0"]) & (a["a-1"] >= a["a1"])
    a["peak_on_d1"] = (a["a1"] > a["a0"]) & (a["a1"] > a["a-1"])
    t = a.groupby("timing")[["peak_on_d0", "peak_on_dm1", "peak_on_d1"]].mean()
    t["n"] = a.groupby("timing").size()
    t.loc["all"] = list(a[["peak_on_d0", "peak_on_dm1", "peak_on_d1"]].mean()) + [len(a)]
    return t

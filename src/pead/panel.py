"""Build the analysis panel: US common stocks + SPY, split-adjusted, with returns and
pre-event rolling statistics. Output: data/processed/panel.parquet.

Columns: ticker, date, idx (trading-day index from the SPY calendar), close_unadj, adj_open,
adj_high, adj_low, adj_close, volume, dollar_vol (vwap x volume, split-invariant), ret
(adjusted close-to-close, NaN across gaps), spy_ret, ab_ret, med60_dv (median dollar volume
over the trailing 60 bars incl. current), std60_ab (std of ab_ret over trailing 60 bars),
nbars (number of bars up to and including this one).
"""
from __future__ import annotations

import logging
import pathlib

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import prices

log = logging.getLogger(__name__)
RAW = pathlib.Path("data/raw")
PROC = pathlib.Path("data/processed")
EXCHANGES = ("XNYS", "XNAS", "XASE")


def common_stock_master() -> pd.DataFrame:
    tk = pd.read_parquet(RAW / "tickers.parquet")
    cs = tk[(tk["type"] == "CS") & (tk["market"] == "stocks") & (tk["locale"] == "us")].copy()
    cs["delisted"] = pd.to_datetime(cs["delisted_utc"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    cs["cik"] = cs["cik"].astype("string").str.zfill(10)
    # Symbols get reused: give each master row a validity interval bounded by earlier namesakes.
    cs = cs.sort_values(["ticker", "delisted"], na_position="last")
    cs["valid_to"] = cs["delisted"].fillna(pd.Timestamp("2100-01-01"))
    cs["valid_from"] = cs.groupby("ticker")["valid_to"].shift(1).fillna(pd.Timestamp("1900-01-01"))
    return cs.reset_index(drop=True)


def build_panel(out: pathlib.Path = PROC / "panel.parquet") -> pd.DataFrame:
    cs = common_stock_master()
    keep = set(cs["ticker"]) | {"SPY"}
    frames = []
    for f in sorted((RAW / "grouped").glob("*.parquet")):
        t = pq.read_table(f, columns=["ticker", "date", "open", "high", "low", "close", "volume", "vwap"]).to_pandas()
        t["ticker"] = t["ticker"].astype(str)
        t = t[t["ticker"].isin(keep)]
        frames.append(t)
        log.info("%s: %d rows kept", f.name, len(t))
    df = pd.concat(frames, ignore_index=True)
    del frames
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"]).reset_index(drop=True)
    cal = prices.trading_days(df)
    idx_map = pd.Series(np.arange(len(cal), dtype="int32"), index=cal)
    df["idx"] = idx_map.reindex(df["date"]).to_numpy()
    df = df[~np.isnan(df["idx"])].copy()
    df["idx"] = df["idx"].astype("int32")
    # explicit split adjustment
    splits = prices.load_splits()
    df = prices.adjust(df, splits)
    df["close_unadj"] = df["close"].astype("float32")
    for c in ("open", "high", "low", "close"):
        df[f"adj_{c}"] = df[f"adj_{c}"].astype("float32")
    df["dollar_vol"] = (df["vwap"].fillna(df["close"]).astype("float64") * df["volume"]).astype("float32")
    df = df.drop(columns=["open", "high", "low", "close", "vwap", "adj_vwap", "adj_volume", "adj_factor"])
    # returns (NaN across gaps in the calendar)
    g = df.groupby("ticker", sort=False)
    prev_close = g["adj_close"].shift(1)
    prev_idx = g["idx"].shift(1)
    ret = df["adj_close"] / prev_close - 1.0
    ret[(df["idx"] - prev_idx) != 1] = np.nan
    df["ret"] = ret.astype("float32")
    spy = df.loc[df["ticker"] == "SPY", ["date", "ret"]].rename(columns={"ret": "spy_ret"})
    df = df.merge(spy, on="date", how="left")
    df["ab_ret"] = (df["ret"] - df["spy_ret"]).astype("float32")
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = df.groupby("ticker", sort=False)
    df["med60_dv"] = g["dollar_vol"].transform(lambda s: s.rolling(60, min_periods=40).median()).astype("float32")
    df["std60_ab"] = g["ab_ret"].transform(lambda s: s.rolling(60, min_periods=40).std()).astype("float32")
    df["nbars"] = (g.cumcount() + 1).astype("int32")
    out.parent.mkdir(parents=True, exist_ok=True)
    df["ticker"] = df["ticker"].astype("category")
    df.to_parquet(out, compression="zstd", index=False)
    log.info("panel saved: %d rows, %d tickers, %s..%s, %.0f MB", len(df), df["ticker"].nunique(), cal[0].date(), cal[-1].date(), out.stat().st_size / 1e6)
    return df


def load_panel(columns: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_parquet(PROC / "panel.parquet", columns=columns)
    df["ticker"] = df["ticker"].astype(str)
    return df

"""Load unadjusted daily bars and apply split adjustments explicitly.

Adjustment convention (matches the vendor's docs for /stocks/v1/splits): for a price on date D,
multiply by the product of split_from/split_to over every split with execution_date > D.
This puts all history on today's share basis, so consecutive-day ratios are true price
returns (dividends excluded, which is stated as a limitation).
"""
from __future__ import annotations

import pathlib
from typing import Iterable

import numpy as np
import pandas as pd

RAW = pathlib.Path("data/raw")
PRICE_COLS = ("open", "high", "low", "close", "vwap")


def load_grouped(years: Iterable[int] | None = None, columns: list[str] | None = None) -> pd.DataFrame:
    files = sorted(p for p in (RAW / "grouped").glob("*.parquet") if not p.name.startswith("._"))  # skip ExFAT/AppleDouble sidecars
    if years is not None:
        ys = {int(y) for y in years}
        files = [f for f in files if int(f.stem) in ys]
    df = pd.concat([pd.read_parquet(f, columns=columns) for f in files], ignore_index=True)
    df["ticker"] = df["ticker"].astype(str)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def trading_days(df: pd.DataFrame, anchor: str = "SPY") -> pd.DatetimeIndex:
    """Trading calendar = dates on which the anchor ETF has a bar."""
    d = df.loc[df["ticker"] == anchor, "date"].unique()
    return pd.DatetimeIndex(sorted(d))


def load_splits() -> pd.DataFrame:
    s = pd.read_parquet(RAW / "splits.parquet")
    s["execution_date"] = pd.to_datetime(s["execution_date"])
    s = s[(s["split_from"] > 0) & (s["split_to"] > 0)].copy()
    s["factor"] = s["split_from"] / s["split_to"]
    return s.sort_values(["ticker", "execution_date"]).reset_index(drop=True)


def cumulative_factor(dates: pd.Series, ticker_splits: pd.DataFrame) -> np.ndarray:
    """For each date, product of factors of splits executed strictly after that date."""
    if ticker_splits.empty:
        return np.ones(len(dates), dtype="float64")
    ex = ticker_splits["execution_date"].to_numpy()
    f = ticker_splits["factor"].to_numpy()
    # suffix products: cum[i] = prod(f[i:])
    suffix = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])
    # splits executed ON date D already apply to D's prices, so require ex > D strictly
    idx = np.searchsorted(ex, dates.to_numpy(), side="right")
    return suffix[idx]


def adjust(df: pd.DataFrame, splits: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add adj_* price columns and adj_volume to an unadjusted bar frame."""
    splits = load_splits() if splits is None else splits
    out = df.copy()
    fac = np.ones(len(out), dtype="float64")
    by_split = {t: g for t, g in splits.groupby("ticker")}
    for t, idx in out.groupby("ticker").indices.items():
        g = by_split.get(t)
        if g is not None:
            fac[idx] = cumulative_factor(out["date"].iloc[idx], g)
    out["adj_factor"] = fac
    for c in PRICE_COLS:
        if c in out:
            out[f"adj_{c}"] = out[c].astype("float64") * fac
    if "volume" in out:
        out["adj_volume"] = out["volume"] / fac
    return out

"""Unit tests for split adjustment and grouped-bar integrity (no API needed)."""
import numpy as np
import pandas as pd
import pytest

from pead import prices


def _splits(rows):
    s = pd.DataFrame(rows, columns=["ticker", "execution_date", "split_from", "split_to"])
    s["execution_date"] = pd.to_datetime(s["execution_date"])
    s["factor"] = s["split_from"] / s["split_to"]
    return s.sort_values(["ticker", "execution_date"]).reset_index(drop=True)


def test_cumulative_factor_conventions():
    s = _splits([("X", "2020-08-31", 1, 4), ("X", "2014-06-09", 1, 7)])
    dates = pd.Series(pd.to_datetime(["2014-06-06", "2014-06-09", "2020-08-28", "2020-08-31", "2021-01-04"]))
    f = prices.cumulative_factor(dates, s[s.ticker == "X"])
    # before both splits: 1/28; on/after 2014-06-09 but before 2020-08-31: 1/4; on/after 2020-08-31: 1
    assert np.allclose(f, [1 / 28, 1 / 4, 1 / 4, 1.0, 1.0])


def test_same_day_double_split_is_order_invariant():
    a = _splits([("Y", "2026-02-03", 1, 1.017391), ("Y", "2026-02-03", 1, 1.003623)])
    b = a.iloc[::-1].reset_index(drop=True)
    d = pd.Series(pd.to_datetime(["2026-02-02"]))
    assert np.isclose(prices.cumulative_factor(d, a)[0], prices.cumulative_factor(d, b)[0])
    assert np.isclose(prices.cumulative_factor(d, a)[0], 1 / (1.017391 * 1.003623))


def test_adjust_returns_are_continuous_across_split():
    bars = pd.DataFrame({"ticker": ["Z"] * 4, "date": pd.to_datetime(["2004-12-17", "2004-12-20", "2004-12-21", "2004-12-22"]),
                         "close": [72.05, 72.01, 38.21, 38.14], "volume": [1e6, 1e6, 2e6, 2e6]})
    s = _splits([("Z", "2004-12-21", 1, 2)])
    adj = prices.adjust(bars, s)
    r = adj["adj_close"].pct_change().abs().max()
    assert r < 0.07, "split day should not show a 47% move after adjustment"
    assert np.isclose(adj["adj_volume"].iloc[0], 2e6)


@pytest.fixture(scope="module")
def grouped_2004():
    try:
        return prices.load_grouped([2004])
    except Exception:
        pytest.skip("data/raw/grouped/2004.parquet not downloaded")


def test_grouped_bars_integrity(grouped_2004):
    df = grouped_2004
    assert not df.duplicated(["ticker", "date"]).any(), "duplicate (ticker, date) rows"
    days = prices.trading_days(df)
    assert 250 <= len(days) <= 253, f"unexpected number of trading days: {len(days)}"
    bad_range = ((df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))).mean()
    assert bad_range < 0.002, f"{bad_range:.4%} of bars have high/low inconsistent with open/close"
    assert (df["close"] > 0).all()

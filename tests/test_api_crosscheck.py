"""Integration checks against the live API. Skipped unless RUN_API_TESTS=1 and a key is set.

Compares our explicitly split-adjusted closes (from unadjusted grouped bars + splits table)
with the vendor's adjusted per-ticker aggregates for a few split tickers.
"""
import os

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()
pytestmark = pytest.mark.skipif(os.environ.get("RUN_API_TESTS") != "1" or not os.environ.get("MASSIVE_API_KEY"), reason="live API test disabled")


def test_adjusted_close_matches_vendor_on_split_tickers():
    from pead import prices
    from pead.massive_client import MassiveClient

    s = prices.load_splits()
    df = prices.load_grouped(range(2004, 2009), columns=["date", "ticker", "close", "volume"])
    adj = prices.adjust(df, s)
    c = MassiveClient()
    for t in ["AAPL", "CCBG", "JJSF"]:
        rows = list(c.paginate(f"/v2/aggs/ticker/{t}/range/1/day/2004-01-01/2008-12-31", {"adjusted": "true", "limit": 50000}))
        v = pd.DataFrame(rows)
        v["date"] = pd.to_datetime(v["t"], unit="ms").dt.normalize()
        m = adj[adj.ticker == t].merge(v[["date", "c"]], on="date")
        rel = (m["adj_close"] / m["c"] - 1).abs()
        assert rel.quantile(0.99) < 0.015, f"{t}: p99 relative difference {rel.quantile(0.99):.4f}"
        assert rel.median() < 0.002, f"{t}: median relative difference {rel.median():.4f}"

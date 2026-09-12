import json
import pathlib

import pandas as pd

from pead.edgar import earnings_8ks

FIX = pathlib.Path(__file__).parent / "fixtures" / "edgar_CIK0000320193_recent.json"


def test_earnings_8k_extraction_and_timezone():
    j = json.loads(FIX.read_text())
    df = pd.DataFrame(j["filings"]["recent"])
    df["cik"] = "0000320193"
    out = earnings_8ks(df)
    assert not out.empty
    assert set(out["form"]).issubset({"8-K", "8-K/A"})
    assert out["items"].str.contains("2.02").all()
    # Apple reports after the close: acceptance should be after 16:00 Eastern
    row = out[out["filing_date"].astype(str) == "2026-07-30"].iloc[0]
    assert row["accepted_et"].hour >= 16
    assert str(row["accepted_et"].tzinfo) == "America/New_York"

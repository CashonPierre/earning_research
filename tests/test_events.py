"""Event-construction checks: no look-ahead in timing, filters, or entries."""
import pathlib

import numpy as np
import pandas as pd
import pytest

P = pathlib.Path("data/processed")


@pytest.fixture(scope="module")
def ev():
    if not (P / "events.parquet").exists():
        pytest.skip("events not built")
    return pd.read_parquet(P / "events.parquet")


def test_day0_after_acceptance(ev):
    acc_date = pd.to_datetime(ev["accepted_et"].dt.tz_localize(None).dt.date)
    assert (ev["d0"] >= acc_date).all(), "day 0 precedes the filing acceptance date"
    amc = ev[ev["timing"] == "amc"]
    assert (amc["d0"] > pd.to_datetime(amc["accepted_et"].dt.tz_localize(None).dt.date)).all(), "after-close filings must map to the next session"


def test_selection_threshold_uses_only_past_quarters(ev):
    s = ev[ev["selected"]]
    assert s["threshold"].notna().all()
    # threshold must not vary within a quarter and must be <= the event's own AR0
    assert (s.groupby("quarter")["threshold"].nunique() == 1).all()
    assert (s["ar0"] >= s["threshold"]).all()


def test_filters_are_pre_event(ev):
    s = ev[ev["selected"]]
    assert (s["close_unadj_m1"] >= 5).all() and (s["med60_dv_m1"] >= 1e6).all() and (s["nbars_m1"] >= 120).all()
    assert (s["timing"] != "intraday").all()


def test_one_event_per_company_per_day(ev):
    assert not ev.duplicated(["cik", "d0"]).any()


def test_entries_follow_signals():
    f = P / "results_W10_H40.parquet"
    if not f.exists():
        pytest.skip("results not built")
    r = pd.read_parquet(f)
    e = r[r["entered_B"]]
    assert (e["entry_B"] == e["k_B"] + 1).all(), "Rule B must enter the session after the signal close"
    assert (e["k_B"] >= 1).all() and (e["entry_B"] <= e["H"]).all()
    assert np.isclose(r.loc[~r["entered_B"], "ret_B"], 0).all(), "flat events must earn zero"

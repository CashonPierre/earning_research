"""One read-only call per question, to learn what this Massive account can see.

Prints counts and dates only; never prints the key or raw licensed rows.
Writes outputs/probe_access.json for the decision log.
"""
from __future__ import annotations

import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])  # always run from the repo root
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from pead.massive_client import MassiveClient, MassiveError  # noqa: E402

out: dict = {"run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "probes": {}}
c = MassiveClient()


def probe(name, fn):
    t0 = time.time()
    try:
        res = fn()
        out["probes"][name] = {"ok": True, "result": res, "secs": round(time.time() - t0, 2)}
        print(f"OK   {name}: {res}")
    except Exception as e:  # noqa: BLE001
        msg = f'{type(e).__name__}: {str(e)[:200]}'
        out["probes"][name] = {"ok": False, "error": msg, "secs": round(time.time() - t0, 2)}
        print(f"FAIL {name}: {msg}")


def grouped(date):
    rows = c.grouped_daily(date)
    spy = [r for r in rows if r.get("T") == "SPY"]
    return {"date": date, "n_tickers": len(rows), "spy_close": spy[0]["c"] if spy else None}


probe("grouped_2004-01-05", lambda: grouped("2004-01-05"))
probe("grouped_2010-05-03", lambda: grouped("2010-05-03"))
probe("grouped_2016-01-04", lambda: grouped("2016-01-04"))
probe("grouped_2026-09-11", lambda: grouped("2026-09-11"))
probe("grouped_unadjusted_2020-08-28", lambda: {**grouped("2020-08-28"), "note": "AAPL 4:1 split effective 2020-08-31"})
probe("tickers_pit_2012_CS", lambda: {"first": next(iter(c.tickers(date="2012-01-03", active=True, type_="CS", limit=1)))["ticker"]})
probe("tickers_delisted_count_sample", lambda: {"n_first_page": len(list(c.paginate("/v3/reference/tickers", {"active": "false", "type": "CS", "market": "stocks", "limit": 1000}, max_pages=1)))})
probe("splits_recent", lambda: {"n": len(list(c.paginate("/stocks/v1/splits", {"limit": 5, "execution_date.gte": "2024-01-01"}, max_pages=1)))})
probe("dividends_recent", lambda: {"n": len(list(c.paginate("/stocks/v1/dividends", {"limit": 5, "ticker": "AAPL"}, max_pages=1)))})
probe("benzinga_earnings_2024-01-25", lambda: {"n": len(list(c.paginate("/benzinga/v1/earnings", {"date": "2024-01-25", "limit": 1000}, max_pages=1)))})
probe("benzinga_earnings_2011-01-25", lambda: {"n": len(list(c.paginate("/benzinga/v1/earnings", {"date": "2011-01-25", "limit": 1000}, max_pages=1)))})

def disc(params):
    page = c.get("/stocks/filings/8-K/vX/disclosures", params)
    rows = page.get("results") or []
    cats = sorted({(r.get("primary_category"), r.get("secondary_category"), r.get("tertiary_category")) for r in rows})[:6]
    return {"n": len(rows), "has_next": bool(page.get("next_url")), "min_date": min((r["filing_date"] for r in rows), default=None), "max_date": max((r["filing_date"] for r in rows), default=None), "cats_sample": cats}

probe("eightk_disc_nofilter_desc", lambda: disc({"limit": 5}))
probe("eightk_disc_nofilter_asc", lambda: disc({"limit": 5, "sort": "filing_date.asc"}))
probe("eightk_disc_2024-01-25_all", lambda: disc({"filing_date": "2024-01-25", "limit": 1000}))
probe("eightk_disc_2024-01-25_quarterly", lambda: disc({"filing_date": "2024-01-25", "tertiary_category": "quarterly_results", "limit": 1000}))
probe("eightk_disc_2015-01-27_all", lambda: disc({"filing_date": "2015-01-27", "limit": 1000}))
probe("eightk_disc_2006-01-25_all", lambda: disc({"filing_date": "2006-01-25", "limit": 1000}))
probe("taxonomy", lambda: {"n": len((c.get("/stocks/taxonomies/vX/disclosures", {"limit": 1000}).get("results") or []))})
probe("eightk_text_2024-01-25", lambda: {"n": len((c.get("/stocks/filings/8-K/vX/text", {"filing_date": "2024-01-25", "limit": 100}).get("results") or []))})

probe("sec_index_8k_2012-01-25", lambda: {"n": len(list(c.paginate("/stocks/filings/vX/index", {"form_type": "8-K", "filing_date": "2012-01-25", "limit": 10000}, max_pages=1)))})
probe("income_statements_AAPL", lambda: {"n": len(list(c.paginate("/stocks/financials/v1/income-statements", {"ticker": "AAPL", "limit": 5}, max_pages=1)))})
probe("quotes_one_page", lambda: {"n": len(list(c.paginate("/v3/quotes/AAPL", {"timestamp": "2024-01-25", "limit": 5}, max_pages=1)))})
out["total_calls"] = c.calls
pathlib.Path("outputs").mkdir(exist_ok=True)
pathlib.Path("outputs/probe_access.json").write_text(json.dumps(out, indent=1))
print("calls:", c.calls)

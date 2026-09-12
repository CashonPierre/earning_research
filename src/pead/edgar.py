"""SEC EDGAR submissions API: free, public, point-in-time filing timestamps.

For each CIK, https://data.sec.gov/submissions/CIK##########.json lists every filing with
accessionNumber, filingDate, acceptanceDateTime (UTC, to the second) and `items`
(e.g. "2.02,9.01" for an earnings-release 8-K). Older filings live in the paginated files
listed under filings.files. SEC asks for a descriptive User-Agent and <= 10 requests/s.

Why this matters: Massive's 8-K endpoints expose only filing_date, but classifying a report
as before-open / after-close needs the time of day. acceptanceDateTime is the moment EDGAR
accepted the filing; it can lag the press release by minutes to hours, which we measure
against Benzinga's reported time where both are available.
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from typing import Iterable

import pandas as pd
import requests

log = logging.getLogger(__name__)
SUBMISSIONS = "https://data.sec.gov/submissions/{name}"
_MIN_INTERVAL = 0.112  # ~9 req/s across ALL threads, under the SEC limit of 10/s


class RateLimiter:
    """Thread-safe minimum spacing between request start times."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            start = max(now, self._next)
            self._next = start + self.min_interval
        delay = start - now
        if delay > 0:
            time.sleep(delay)


class EdgarClient:
    def __init__(self, user_agent: str, cache_dir: str | pathlib.Path = "data/raw/edgar", cache_json: bool = False):
        if "@" not in user_agent:
            raise ValueError("SEC requires a User-Agent with contact info, e.g. 'name email@domain'")
        self._local = threading.local()
        self._ua = user_agent
        self._limiter = RateLimiter(_MIN_INTERVAL)
        self.cache = pathlib.Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.cache_json = cache_json  # raw JSON is ~100 KB per CIK; off by default to save disk

    @property
    def _s(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": self._ua, "Accept-Encoding": "gzip, deflate"})
            self._local.session = s
        return s

    def _get_json(self, name: str) -> dict | None:
        f = self.cache / name
        if f.exists():
            return json.loads(f.read_text())
        for attempt in range(5):
            self._limiter.wait()
            r = self._s.get(SUBMISSIONS.format(name=name), timeout=30)
            if r.status_code == 200:
                if self.cache_json:
                    f.write_text(r.text)
                return r.json()
            if r.status_code == 404:
                return None
            time.sleep(2**attempt)
        log.warning("EDGAR gave HTTP %s for %s", r.status_code, name)
        return None

    def filings(self, cik: str | int) -> pd.DataFrame:
        """All filings for one CIK (recent + older pages) as a DataFrame."""
        cik10 = f"{int(cik):010d}"
        j = self._get_json(f"CIK{cik10}.json")
        if not j:
            return pd.DataFrame()
        frames = [pd.DataFrame(j["filings"]["recent"])]
        for extra in j["filings"].get("files", []):
            k = self._get_json(extra["name"])
            if k:
                frames.append(pd.DataFrame(k))
        df = pd.concat(frames, ignore_index=True)
        df["cik"] = cik10
        return df


def earnings_8ks(df: pd.DataFrame) -> pd.DataFrame:
    """Keep 8-K / 8-K/A filings whose items include 2.02 (Results of Operations).

    Returns columns: cik, accession, form, filing_date, accepted_utc, accepted_et, items,
    report_date. accepted_et is tz-aware US/Eastern; the caller decides the day-0 rule.
    """
    if df.empty:
        return df
    m = df["form"].isin(["8-K", "8-K/A"]) & df["items"].fillna("").str.contains(r"(?:^|,)\s*2\.02(?:,|$)", regex=True)
    out = df.loc[m, ["cik", "accessionNumber", "form", "filingDate", "acceptanceDateTime", "items", "reportDate"]].copy()
    out.columns = ["cik", "accession", "form", "filing_date", "accepted_utc", "items", "report_date"]
    out["accepted_utc"] = pd.to_datetime(out["accepted_utc"], utc=True)
    out["accepted_et"] = out["accepted_utc"].dt.tz_convert("America/New_York")
    out["filing_date"] = pd.to_datetime(out["filing_date"]).dt.date
    out["report_date"] = pd.to_datetime(out["report_date"], errors="coerce").dt.date
    return out.sort_values("accepted_utc").reset_index(drop=True)


def fetch_earnings_8ks(client: EdgarClient, ciks: Iterable[str | int]) -> pd.DataFrame:
    frames = []
    for i, cik in enumerate(ciks):
        try:
            frames.append(earnings_8ks(client.filings(cik)))
        except Exception as e:  # noqa: BLE001
            log.warning("CIK %s failed: %s", cik, e)
        if i and i % 200 == 0:
            log.info("EDGAR: %d CIKs done", i)
    return pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()

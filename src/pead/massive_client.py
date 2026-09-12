"""Thin client for the Massive REST API (https://api.massive.com).

Design rules
- The key is sent only in the Authorization header, never as a query parameter, so it
  cannot leak through URLs, logs, or next_url cursors.
- Every request re-validates the Hong Kong geo guard (cached, see preflight.py).
- 429 and 5xx responses are retried with exponential backoff and Retry-After.
- Pagination follows `next_url` until exhausted.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any, Iterator

import requests

from . import preflight

log = logging.getLogger(__name__)
BASE = "https://api.massive.com"


class MassiveError(RuntimeError):
    pass


class MassiveClient:
    def __init__(self, max_retries: int = 8, timeout: float = 60.0, min_interval: float = 0.0):
        self._key = preflight.load_api_key()
        self._s = requests.Session()
        self._s.headers.update({"Authorization": f"Bearer {self._key}", "User-Agent": "pead-research/0.1"})
        self.max_retries = max_retries
        self.timeout = timeout
        self.min_interval = min_interval  # seconds between requests (0 = no throttle)
        self._last_call = 0.0
        self.calls = 0
        preflight.require_hk_ip(force=True)

    # ------------------------------------------------------------------ core
    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        params = {k: v for k, v in (params or {}).items() if v is not None}
        if "apiKey" in params:
            raise MassiveError("never pass the key as a query parameter")
        for attempt in range(self.max_retries + 1):
            preflight.require_hk_ip()
            if self.min_interval:
                wait = self._last_call + self.min_interval - time.time()
                if wait > 0:
                    time.sleep(wait)
            try:
                r = self._s.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise MassiveError(preflight.mask(f"network error after retries: {e}")) from None
                time.sleep(min(60, 2**attempt + random.random()))
                continue
            self._last_call = time.time()
            self.calls += 1
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                retry_after = r.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60, 2**attempt + random.random())
                log.warning("HTTP %s on %s; sleeping %.1fs (attempt %d)", r.status_code, preflight.mask(r.url), delay, attempt + 1)
                time.sleep(delay)
                continue
            raise MassiveError(preflight.mask(f"HTTP {r.status_code} for {r.url}: {r.text[:300]}"))
        raise MassiveError("unreachable")

    def paginate(self, path: str, params: dict[str, Any] | None = None, max_pages: int | None = None) -> Iterator[dict[str, Any]]:
        """Yield every item in `results` across pages, following next_url."""
        page = self.get(path, params)
        n = 0
        while True:
            for item in page.get("results") or []:
                yield item
            n += 1
            nxt = page.get("next_url")
            if not nxt or (max_pages and n >= max_pages):
                return
            page = self.get(nxt)  # cursor URL; auth stays in the header

    # ------------------------------------------------------------- endpoints
    def grouped_daily(self, date: str, adjusted: bool = True, include_otc: bool = False) -> list[dict[str, Any]]:
        """Daily Market Summary: all US tickers for one trading date."""
        j = self.get(f"/v2/aggs/grouped/locale/us/market/stocks/{date}", {"adjusted": str(adjusted).lower(), "include_otc": str(include_otc).lower()})
        return j.get("results") or []

    def tickers(self, date: str | None = None, active: bool | None = None, type_: str | None = None, market: str = "stocks", limit: int = 1000) -> Iterator[dict[str, Any]]:
        return self.paginate("/v3/reference/tickers", {"date": date, "active": None if active is None else str(active).lower(), "type": type_, "market": market, "limit": limit})

    def ticker_details(self, ticker: str, date: str | None = None) -> dict[str, Any]:
        return self.get(f"/v3/reference/tickers/{ticker}", {"date": date}).get("results") or {}

    def splits(self, **filters: Any) -> Iterator[dict[str, Any]]:
        return self.paginate("/stocks/v1/splits", {"limit": 1000, **filters})

    def dividends(self, **filters: Any) -> Iterator[dict[str, Any]]:
        return self.paginate("/stocks/v1/dividends", {"limit": 1000, **filters})

    def eightk_disclosures(self, **filters: Any) -> Iterator[dict[str, Any]]:
        return self.paginate("/stocks/filings/8-K/vX/disclosures", {"limit": 1000, **filters})

    def sec_index(self, **filters: Any) -> Iterator[dict[str, Any]]:
        return self.paginate("/stocks/filings/vX/index", {"limit": 10000, **filters})

    def benzinga_earnings(self, **filters: Any) -> Iterator[dict[str, Any]]:
        return self.paginate("/benzinga/v1/earnings", {"limit": 50000, **filters})

    def market_holidays(self) -> list[dict[str, Any]]:
        return self.get("/v1/marketstatus/upcoming") or []

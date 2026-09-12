"""Pre-flight guards that run before any Massive API call.

1. Geo guard: the assessment brief requires all Massive API usage to originate from a
   Hong Kong IP address with no VPN, and treats violations as disqualifying even when
   accidental. We therefore refuse to make any API call unless a public IP lookup
   reports country == "HK". The check is cached for GEO_TTL_SECONDS and re-run during
   long downloads so a VPN that reconnects mid-run also aborts the job.
2. Disk guard: the working disk is small; refuse to start a download if free space is
   below MIN_FREE_GIB.
3. Key guard: the key comes only from the MASSIVE_API_KEY environment variable
   (loaded from a git-ignored .env). It is never logged or included in URLs.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

GEO_TTL_SECONDS = 600
MIN_FREE_GIB = 1.0
_GEO_SOURCES = (
    "https://ipinfo.io/json",      # {"country": "HK", ...}
    "https://ipapi.co/json/",      # {"country_code": "HK", ...}
)


class PreflightError(RuntimeError):
    pass


@dataclass
class GeoResult:
    country: str
    org: str
    source: str
    checked_at: float


_last_geo: GeoResult | None = None


def lookup_geo(timeout: float = 8.0) -> GeoResult:
    last_err: Exception | None = None
    for url in _GEO_SOURCES:
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "pead-preflight"})
            r.raise_for_status()
            j = r.json()
            country = (j.get("country") or j.get("country_code") or "").upper()
            org = j.get("org") or j.get("asn") or ""
            if country:
                return GeoResult(country=country, org=str(org), source=url, checked_at=time.time())
        except Exception as e:  # noqa: BLE001 - try the next source
            last_err = e
    raise PreflightError(f"could not determine public IP country: {last_err}")


def require_hk_ip(force: bool = False) -> GeoResult:
    """Raise PreflightError unless the public IP is in Hong Kong (or REQUIRE_HK_IP=0)."""
    global _last_geo
    load_dotenv(override=False)
    if os.environ.get("REQUIRE_HK_IP", "1") == "0":
        return GeoResult(country="SKIPPED", org="", source="REQUIRE_HK_IP=0", checked_at=time.time())
    if not force and _last_geo and time.time() - _last_geo.checked_at < GEO_TTL_SECONDS:
        return _last_geo
    geo = lookup_geo()
    if geo.country != "HK":
        raise PreflightError(
            f"public IP country is {geo.country} ({geo.org}); the brief requires a Hong Kong IP "
            "with no VPN. Refusing to call the Massive API. Disconnect the VPN and retry."
        )
    _last_geo = geo
    return geo


def require_disk(path: str = ".", min_free_gib: float = MIN_FREE_GIB) -> float:
    free_gib = shutil.disk_usage(path).free / 2**30
    if free_gib < min_free_gib:
        raise PreflightError(f"only {free_gib:.2f} GiB free at {path}; need at least {min_free_gib} GiB")
    return free_gib


def load_api_key() -> str:
    load_dotenv(override=False)
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if not key:
        raise PreflightError("MASSIVE_API_KEY is not set. Put it in the git-ignored .env file.")
    return key


def mask(text: str) -> str:
    """Remove the API key from any string before it is logged or raised."""
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    return text.replace(key, "<MASSIVE_API_KEY>") if key else text

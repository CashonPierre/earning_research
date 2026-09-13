"""Download the full-market daily bars (unadjusted), the ticker master, and the splits table.

- Daily Market Summary, adjusted=false, one call per weekday 2004-01-01 .. END. Unadjusted
  prices are the point-in-time record; we apply split adjustments ourselves from the splits
  table and validate against a sample of vendor-adjusted bars (tests/test_prices.py, tests/test_api_crosscheck.py).
- Written as one parquet per year under data/raw/grouped/ (float32 prices, int64 volume,
  dictionary-encoded ticker). Completed years are skipped on re-run (resume).
- Ticker master: /v3/reference/tickers for active=true and active=false, market=stocks,
  all types, saved to data/raw/tickers.parquet (includes cik, type, primary_exchange,
  delisted_utc).
- Splits: /stocks/v1/splits, all history, data/raw/splits.parquet.
Progress goes to logs/download.log. Never prints the key.
"""
from __future__ import annotations

import os, pathlib as _pl; os.chdir(_pl.Path(__file__).resolve().parents[1])  # always run from the repo root
import concurrent.futures as cf
import datetime as dt
import logging
import pathlib
import sys
import time

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from pead import preflight  # noqa: E402
from pead.massive_client import MassiveClient, MassiveError  # noqa: E402

START = dt.date(2004, 1, 1)
END = dt.date(2026, 9, 11)
THREADS = 6
RAW = pathlib.Path("data/raw")
(RAW / "grouped").mkdir(parents=True, exist_ok=True)
pathlib.Path("logs").mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler("logs/download.log"), logging.StreamHandler()])
log = logging.getLogger("download")

COLS = {"T": "ticker", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap", "n": "trades", "t": "t_ms"}


def weekdays(a: dt.date, b: dt.date):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += dt.timedelta(days=1)


def fetch_day(c: MassiveClient, d: dt.date):
    for attempt in range(3):
        try:
            rows = c.grouped_daily(d.isoformat(), adjusted=False, include_otc=False)
            return d, rows
        except MassiveError as e:
            log.warning("%s attempt %d failed: %s", d, attempt + 1, str(e)[:120])
            time.sleep(5)
    return d, None


def download_grouped(c: MassiveClient):
    for year in range(START.year, END.year + 1):
        out = RAW / "grouped" / f"{year}.parquet"
        if out.exists() and year < END.year:
            log.info("%d exists, skipping", year)
            continue
        a, b = max(START, dt.date(year, 1, 1)), min(END, dt.date(year, 12, 31))
        days = list(weekdays(a, b))
        frames, empty, failed = [], 0, []
        t0 = time.time()
        with cf.ThreadPoolExecutor(THREADS) as ex:
            for d, rows in ex.map(lambda d: fetch_day(c, d), days):
                if rows is None:
                    failed.append(d)
                    continue
                if not rows:
                    empty += 1
                    continue
                df = pd.DataFrame(rows).rename(columns=COLS)
                for col in COLS.values():
                    if col not in df:
                        df[col] = pd.NA
                df = df[list(COLS.values())]
                df["date"] = pd.Timestamp(d)
                frames.append(df)
        preflight.require_disk(".", 0.5)
        if not frames:
            log.error("%d: no data at all", year)
            continue
        y = pd.concat(frames, ignore_index=True)
        y["ticker"] = y["ticker"].astype("category")
        for col in ("open", "high", "low", "close", "vwap"):
            y[col] = pd.to_numeric(y[col], errors="coerce").astype("float32")
        y["volume"] = pd.to_numeric(y["volume"], errors="coerce").astype("float64")
        y["trades"] = pd.to_numeric(y["trades"], errors="coerce").astype("Int64")
        y["t_ms"] = pd.to_numeric(y["t_ms"], errors="coerce").astype("Int64")
        y.to_parquet(out, compression="zstd", index=False)
        log.info("%d: %d days ok, %d empty (holidays), %d FAILED %s, %d rows, %.1f MB, %.0fs, calls so far %d",
                 year, len(frames), empty, len(failed), [d.isoformat() for d in failed][:5], len(y), out.stat().st_size / 1e6, time.time() - t0, c.calls)


def download_tickers(c: MassiveClient):
    out = RAW / "tickers.parquet"
    if out.exists():
        log.info("tickers exist, skipping")
        return
    rows = []
    for active in (True, False):
        n0 = len(rows)
        rows.extend(c.tickers(active=active, market="stocks", limit=1000))
        log.info("tickers active=%s: %d", active, len(rows) - n0)
    df = pd.DataFrame(rows)
    df.to_parquet(out, compression="zstd", index=False)
    log.info("tickers saved: %d rows, cols %s", len(df), list(df.columns))


def download_splits(c: MassiveClient):
    out = RAW / "splits.parquet"
    if out.exists():
        log.info("splits exist, skipping")
        return
    rows = list(c.splits(sort="execution_date.asc"))
    df = pd.DataFrame(rows)
    df.to_parquet(out, compression="zstd", index=False)
    log.info("splits saved: %d rows, %s .. %s", len(df), df["execution_date"].min() if len(df) else None, df["execution_date"].max() if len(df) else None)


if __name__ == "__main__":
    preflight.require_disk(".", 1.0)
    c = MassiveClient()
    download_tickers(c)
    download_splits(c)
    download_grouped(c)
    log.info("DONE. total calls %d", c.calls)

"""Pull Item 2.02 (earnings release) 8-K acceptance timestamps from SEC EDGAR for every
US common stock (active or delisted) in the Massive ticker master that has a CIK.

Output: data/raw/edgar_8k_202.parquet with one row per 8-K/8-K/A whose items include 2.02.
Also: data/raw/edgar_coverage.parquet with per-CIK counts (all filings, 8-Ks, 2.02 8-Ks) so the
report can state coverage. Checkpoints every 500 CIKs; resume skips CIKs already done.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging
import pathlib
import sys
import threading
import time

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from pead.edgar import EdgarClient, earnings_8ks  # noqa: E402

UA = "HKUST student research assessment woody.lei@bit.com"
RAW = pathlib.Path("data/raw")
OUT = RAW / "edgar_8k_202.parquet"
COV = RAW / "edgar_coverage.parquet"
pathlib.Path("logs").mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler("logs/download_edgar.log"), logging.StreamHandler()])
log = logging.getLogger("edgar")

tk = pd.read_parquet(RAW / "tickers.parquet")
cs = tk[(tk["type"] == "CS") & (tk["market"] == "stocks") & (tk["locale"] == "us")]
ciks = sorted({str(c).zfill(10) for c in cs["cik"].dropna().astype(str) if str(c).strip() and str(c) != "nan"})
log.info("CS tickers: %d (active %d); with CIK: %d unique CIKs", len(cs), int(cs["active"].sum()), len(ciks))

done_rows, cov_rows = [], []
done = set()
if OUT.exists() and COV.exists():
    prev = pd.read_parquet(OUT); prevc = pd.read_parquet(COV)
    done_rows.append(prev); cov_rows.append(prevc); done = set(prevc["cik"])
    log.info("resuming: %d CIKs already done", len(done))

client = EdgarClient(UA, cache_json=False)
THREADS = 8
todo = [c for c in ciks if c not in done]
lock = threading.Lock()
t0 = time.time(); n = 0


def work(cik):
    try:
        df = client.filings(cik)
        e = earnings_8ks(df) if not df.empty else df
        cov = {"cik": cik, "n_filings": len(df), "n_8k": int(df["form"].isin(["8-K", "8-K/A"]).sum()) if not df.empty else 0, "n_202": len(e), "found": not df.empty}
        return cik, e, cov
    except Exception as ex:  # noqa: BLE001
        log.warning("CIK %s failed: %s", cik, str(ex)[:120])
        return cik, None, {"cik": cik, "n_filings": 0, "n_8k": 0, "n_202": 0, "found": False}


def checkpoint():
    pd.concat(done_rows, ignore_index=True).to_parquet(OUT, compression="zstd", index=False)
    pd.concat(cov_rows, ignore_index=True).to_parquet(COV, compression="zstd", index=False)


with cf.ThreadPoolExecutor(THREADS) as ex:
    for cik, e, cov in ex.map(work, todo):
        with lock:
            cov_rows.append(pd.DataFrame([cov]))
            if e is not None and not e.empty:
                done_rows.append(e)
            n += 1
            if n % 500 == 0:
                checkpoint()
                rate = n / (time.time() - t0)
                log.info("%d/%d CIKs done, %.1f/s, %d 2.02 rows so far, ETA %.0f min", n, len(todo), rate, sum(len(x) for x in done_rows), (len(todo) - n) / rate / 60)
checkpoint()
log.info("DONE: %d CIKs, %d Item 2.02 8-K rows, %.0f min", n, sum(len(x) for x in done_rows), (time.time() - t0) / 60)

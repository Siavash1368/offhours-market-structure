"""Earnings announcement dates and times from Yahoo Finance via yfinance.

`Ticker.get_earnings_dates(limit=n)` returns timestamps in US/Eastern. Timing rule (config):
  after close   time >= 16:00 ET   -> event night is the evening of that date
  before open   time <  09:30 ET   -> event night is the evening before (not used in A3)
  otherwise     during the session or unknown (Yahoo often stores 00:00 when time is unknown)
Rows with a 00:00 timestamp are classified "unknown" and excluded from A3.

Cached per ticker as data/raw/earnings/<TICKER>.parquet.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

import pandas as pd

from offhours.config import RAW, cfg
from offhours.data.prices import to_yahoo

log = logging.getLogger(__name__)
CACHE = RAW / "earnings"


def download(symbols: list[str], limit: int = 48) -> list[str]:
    """Cache earnings dates for each symbol (limit=48 quarters reaches back to ~2014)."""
    import yfinance as yf

    c = cfg()["earnings"]
    CACHE.mkdir(parents=True, exist_ok=True)
    nodata_file = CACHE / "_no_data.txt"
    nodata = set(nodata_file.read_text().split()) if nodata_file.exists() else set()
    todo = sorted({to_yahoo(s) for s in symbols} - nodata)
    todo = [t for t in todo if not (CACHE / f"{t}.parquet").exists()]
    log.info("earnings: %d tickers to download", len(todo))
    missing = []
    for i, t in enumerate(todo, 1):
        df = None
        for attempt in range(3):
            try:
                df = yf.Ticker(t).get_earnings_dates(limit=limit)
                break
            except Exception as exc:
                msg = str(exc).lower()
                if "no earnings dates" in msg or "delisted" in msg or "not found" in msg:
                    break
                log.warning("earnings %s failed (%s); retry %d", t, exc, attempt + 1)
                time.sleep(2 ** (attempt + 2))
        if df is None or df.empty:
            missing.append(t)
        else:
            df = df.reset_index().rename(columns={"Earnings Date": "timestamp"})
            df["timestamp"] = df["timestamp"].astype(str)
            df["downloaded"] = dt.date.today().isoformat()
            df.to_parquet(CACHE / f"{t}.parquet", index=False)
        if i % 100 == 0:
            log.info("earnings: %d / %d", i, len(todo))
        time.sleep(c["sleep_seconds"])
    with open(nodata_file, "a") as f:
        for t in missing:
            f.write(t + "\n")
    return missing


def classify_timing(ts: pd.Series) -> pd.Series:
    """'after_close', 'before_open', 'during' or 'unknown' from US/Eastern timestamps."""
    c = cfg()["earnings"]
    t = ts.dt.strftime("%H:%M")
    out = pd.Series("during", index=ts.index)
    out[t >= c["after_close_from"]] = "after_close"
    out[t < c["before_open_until"]] = "before_open"
    out[t == "00:00"] = "unknown"
    return out


def load() -> pd.DataFrame:
    """ticker, timestamp (ET, naive), date, timing, eps fields."""
    frames = []
    for path in sorted(CACHE.glob("*.parquet")):
        df = pd.read_parquet(path)
        df["ticker"] = path.stem
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/New_York")
    df["timing"] = classify_timing(ts)
    df["timestamp"] = ts.dt.tz_localize(None)
    df["date"] = df["timestamp"].dt.normalize()
    df = df.rename(columns={"EPS Estimate": "eps_estimate", "Reported EPS": "eps_reported",
                            "Surprise(%)": "surprise_pct"})
    return df.drop_duplicates(["ticker", "date"])

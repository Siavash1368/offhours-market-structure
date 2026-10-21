"""Daily OHLCV from Yahoo Finance via yfinance.

`auto_adjust=False`: Open/High/Low/Close are split-adjusted but not dividend-adjusted, Volume is
split-adjusted, `Adj Close` is split- and dividend-adjusted. Yahoo's Open is the official opening
price. Volume is consolidated volume as reported by Yahoo (exchanges + TRFs); suppressed
non-business-day TRF reports (e.g. Sunday-night overnight trades) are not in it.

FINRA shares are as traded, so `measures.unadjust_volume` divides split-adjusted volume by the
cumulative split factor after each date before any share-count ratio is taken.

Each ticker is cached as data/raw/prices/<TICKER>.parquet with the download date in a column.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

import pandas as pd

from offhours.config import RAW, cfg

log = logging.getLogger(__name__)
CACHE = RAW / "prices"
COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]


def to_yahoo(symbol: str) -> str:
    """FINRA/CQS class suffixes use '.' or ' ' (BRK.B); Yahoo uses '-' (BRK-B)."""
    return symbol.strip().replace(".", "-").replace(" ", "-").replace("/", "-")


def _path(symbol: str):
    return CACHE / f"{to_yahoo(symbol)}.parquet"


def download(symbols: list[str], start: str, end: str) -> list[str]:
    """Cache daily bars for symbols not yet cached. Returns symbols Yahoo had no data for."""
    import yfinance as yf

    c = cfg()["prices"]
    CACHE.mkdir(parents=True, exist_ok=True)
    nodata_file = CACHE / "_no_data.txt"
    nodata = set(nodata_file.read_text().split()) if nodata_file.exists() else set()
    todo = sorted({s for s in symbols if not _path(s).exists() and to_yahoo(s) not in nodata})
    log.info("prices: %d symbols to download", len(todo))
    missing = []
    for i in range(0, len(todo), c["batch_size"]):
        batch = todo[i : i + c["batch_size"]]
        tickers = [to_yahoo(s) for s in batch]
        for attempt in range(4):
            try:
                df = yf.download(
                    tickers,
                    start=start,
                    end=end,
                    auto_adjust=False,
                    actions=True,
                    group_by="ticker",
                    progress=False,
                    threads=False,
                )
                break
            except Exception as exc:  # network / rate limit
                log.warning("yfinance batch failed (%s); retry %d", exc, attempt + 1)
                time.sleep(2 ** (attempt + 2))
        else:
            raise RuntimeError("yfinance download failed repeatedly")
        have = df.columns.levels[0] if isinstance(df.columns, pd.MultiIndex) else []
        for t in tickers:
            sub = df[t] if t in have else None
            if sub is None or sub["Close"].dropna().empty:
                missing.append(t)
                continue
            sub = sub.dropna(subset=["Close"]).reindex(columns=COLUMNS)
            sub.index.name = "date"
            sub = sub.reset_index()
            sub["downloaded"] = dt.date.today().isoformat()
            sub.to_parquet(CACHE / f"{t}.parquet", index=False)
        log.info("prices: %d / %d", min(i + c["batch_size"], len(todo)), len(todo))
        time.sleep(c["sleep_seconds"])
    with open(nodata_file, "a") as f:
        for t in missing:
            f.write(t + "\n")
    return missing


def load() -> pd.DataFrame:
    """All cached tickers stacked (yahoo ticker in column `ticker`)."""
    frames = []
    for path in sorted(CACHE.glob("*.parquet")):
        df = pd.read_parquet(path)
        df["ticker"] = path.stem
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
            "Dividends": "dividends",
            "Stock Splits": "split",
        }
    )
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df

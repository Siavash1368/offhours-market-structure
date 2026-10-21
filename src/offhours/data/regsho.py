"""FINRA Reg SHO daily short-sale volume, consolidated NMS file (CNMSshvolYYYYMMDD.txt).

Pipe-delimited: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market. `TotalVolume` is
the volume reported to FINRA facilities (TRFs and ADF), i.e. off-exchange volume, not consolidated
volume. Fractional shares appear as decimals. Files exist for trading days only; other days return
403/404 and are recorded as missing (not cached as empty files).
"""

from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

from offhours.config import RAW, cfg
from offhours.data.http import request

log = logging.getLogger(__name__)
CACHE = RAW / "regsho"


def _path(day: dt.date):
    return CACHE / f"CNMSshvol{day:%Y%m%d}.txt"


def download(start: str, end: str) -> list[str]:
    """Cache one file per weekday between start and end. Returns dates with no file."""
    c = cfg()["regsho"]
    CACHE.mkdir(parents=True, exist_ok=True)
    missing_log = CACHE / "_no_file_dates.txt"
    known_missing = set(missing_log.read_text().split()) if missing_log.exists() else set()
    missing = []
    for day in pd.bdate_range(start, end).date:
        if _path(day).exists() or day.isoformat() in known_missing:
            continue
        url = c["url_template"].format(date=f"{day:%Y%m%d}")
        resp = request("GET", url, sleep=c["sleep_seconds"], ok_statuses=(200, 403, 404))
        if resp.status_code == 200 and resp.content.startswith(b"Date|"):
            _path(day).write_bytes(resp.content)
        else:
            missing.append(day.isoformat())
    # Only remember missing dates that are safely in the past (files appear the same evening).
    cutoff = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    with open(missing_log, "a") as f:
        for d in missing:
            if d < cutoff:
                f.write(d + "\n")
    log.info("Reg SHO: %d dates without a file", len(missing))
    return missing


def load() -> pd.DataFrame:
    """All cached days stacked: date, symbol, short_volume, short_exempt, total_volume."""
    frames = []
    for path in sorted(CACHE.glob("CNMSshvol*.txt")):
        text = path.read_text()
        # The last line of some files is a record count; keep only rows with 6 fields.
        df = pd.read_csv(io.StringIO(text), sep="|", dtype={"Date": str, "Symbol": str})
        frames.append(df[df["Market"].notna()])
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(
        columns={
            "Date": "date",
            "Symbol": "symbol",
            "ShortVolume": "short_volume",
            "ShortExemptVolume": "short_exempt",
            "TotalVolume": "total_volume",
        }
    ).drop(columns="Market")
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df

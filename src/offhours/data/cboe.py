"""Cboe U.S. equities historical market volume: daily consolidated NMS volume by market center.

Source: https://www.cboe.com/markets/us/equities/market-statistics/historical-market-volume
Yearly files market_history_<YYYY>.csv on cdn.cboe.com. Per Cboe, the data cover all U.S. equity
exchanges and the FINRA TRFs, "based on UTDF and CTS consolidated data feeds" (the SIPs), by tape.
Cboe asks published work to cite "Cboe Exchange, Inc." as the source.

Columns: Day, Market Participant, Tape A/B/C/Total Shares, Notional, Trade Count.
Daily NMS total = sum of Total Shares across market centers. SIP-based, so it excludes TRF reports
suppressed from dissemination (e.g. Sunday-evening overnight trades, SEC memo footnote 2).

The current year's file grows daily. It is cached once like every raw file; delete it by hand
to refresh. robots.txt disallows /*market_statistics/volume_reports/, which is not used here.
"""

from __future__ import annotations

import datetime as dt
import io
import logging

import pandas as pd

from offhours.config import RAW
from offhours.data.http import request

log = logging.getLogger(__name__)
CACHE = RAW / "cboe"
URL = ("https://cdn.cboe.com/resources/us/equities/market-statistics/historical-market-volume/"
       "market_history_{year}.csv")


def download(years: list[int]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    for y in years:
        path = CACHE / f"market_history_{y}.csv"
        if path.exists():
            continue
        resp = request("GET", URL.format(year=y), sleep=1.0)
        if not resp.text.startswith("Day,"):
            raise RuntimeError(f"unexpected Cboe file for {y}")
        path.write_text(resp.text)
        (CACHE / f"market_history_{y}.downloaded").write_text(dt.date.today().isoformat())


def load() -> pd.DataFrame:
    """date, nms_shares, nms_notional, trf_shares, n_centers (one row per trading day)."""
    frames = [pd.read_csv(io.StringIO(p.read_text()))
              for p in sorted(CACHE.glob("market_history_[0-9][0-9][0-9][0-9].csv"))]
    d = pd.concat(frames, ignore_index=True)
    d["date"] = pd.to_datetime(d["Day"])
    d["is_trf"] = d["Market Participant"].str.contains("TRF")
    g = d.groupby("date")
    out = pd.DataFrame({
        "nms_shares": g["Total Shares"].sum(),
        "nms_notional": g["Total Notional"].sum(),
        "trf_shares": d[d["is_trf"]].groupby("date")["Total Shares"].sum(),
        "n_centers": g["Market Participant"].nunique(),
    }).reset_index()
    return out

"""Parquet store and DuckDB views built from the cached raw files.

Tables (data/processed/<name>.parquet), one DuckDB view per table in data/processed/offhours.duckdb:

  ats_overnight   symbol x overnight ATS x week x tier: shares, trades, notional
  ats_symbol      Tier 1 symbol x week: shares on all ATSs
  otc_symbol      Tier 1 symbol x week: non-ATS OTC shares
  ats_venue       ATS x week x tier: venue totals (all symbols in the tier)
  regsho_daily    symbol x day: off-exchange short volume and total volume
  prices_daily    ticker x day: OHLCV, unadjusted volume, night/day returns
  earnings        ticker x announcement date: timing class
  universe        Tier 1 symbols seen in the sample, ETP flag, yahoo ticker (A2, A3)
  symbols_overnight  every symbol traded on an overnight venue, both tiers, ETP flag (A1)
  nms_volume_daily   Cboe consolidated NMS share and dollar volume per trading day
"""

from __future__ import annotations

import json
import logging

import duckdb
import pandas as pd

from offhours import measures
from offhours.config import DUCKDB_PATH, PROCESSED
from offhours.data import cboe, earnings, finra_ats, prices, regsho, symbols

log = logging.getLogger(__name__)

SCHEMAS: dict[str, dict[str, list[str]]] = {
    "ats_overnight": {"cols": ["week", "tier", "mpid", "symbol", "shares", "trades", "notional"],
                      "key": ["week", "tier", "mpid", "symbol"]},
    "ats_symbol": {"cols": ["week", "symbol", "shares", "trades", "notional"],
                   "key": ["week", "symbol"]},
    "otc_symbol": {"cols": ["week", "symbol", "shares", "trades", "notional"],
                   "key": ["week", "symbol"]},
    "ats_venue": {"cols": ["week", "tier", "mpid", "participant_name", "shares", "notional"],
                  "key": ["week", "tier", "mpid"]},
    "regsho_daily": {"cols": ["date", "symbol", "short_volume", "total_volume"],
                     "key": ["date", "symbol"]},
    "prices_daily": {"cols": ["ticker", "date", "open", "close", "volume", "volume_raw",
                              "r_night", "r_day", "r_cc"],
                     "key": ["ticker", "date"]},
    "earnings": {"cols": ["ticker", "date", "timestamp", "timing"], "key": ["ticker", "date"]},
    "universe": {"cols": ["symbol", "ticker", "issue_name", "is_etp", "etp_source"],
                 "key": ["symbol"]},
    "symbols_overnight": {"cols": ["symbol", "issue_name", "is_etp", "etp_source", "tier"],
                          "key": ["symbol"]},
    "nms_volume_daily": {"cols": ["date", "nms_shares", "nms_notional"], "key": ["date"]},
}


def check_schema(name: str, df: pd.DataFrame) -> None:
    """Required columns present and the key unique; raises ValueError otherwise."""
    spec = SCHEMAS[name]
    missing = [c for c in spec["cols"] if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")
    dups = df.duplicated(spec["key"]).sum()
    if dups:
        raise ValueError(f"{name}: {dups} duplicate rows on key {spec['key']}")


MERGED_DUPLICATES: dict[str, int] = {}


def collapse_duplicates(
    name: str, df: pd.DataFrame, sum_cols: tuple[str, ...] = ("shares", "trades", "notional")
) -> pd.DataFrame:
    """Sum rows that share the table key, keeping the first value of other columns.

    FINRA occasionally publishes two rows for one symbol x venue x week that differ only in
    the encoding of the issue name (e.g. LND, BLUE, T2, week of 2024-07-01). The venue total
    counts both, so summing keeps the identity symbol sum = venue total. The number of merged
    rows is recorded in MERGED_DUPLICATES and reported in data_audit.md.
    """
    key = SCHEMAS[name]["key"]
    dup = df.duplicated(key, keep=False)
    MERGED_DUPLICATES[name] = int(dup.sum())
    if not dup.any():
        return df
    agg = {c: ("sum" if c in sum_cols else "first") for c in df.columns if c not in key}
    return df.groupby(key, as_index=False, sort=False).agg(agg)


def _write(name: str, df: pd.DataFrame) -> None:
    check_schema(name, df)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    log.info("store: %s %d rows", name, len(df))


def build() -> None:
    """Rebuild every Parquet table from data/raw and refresh the DuckDB views."""
    sym = finra_ats.load("ATS_W_SMBL_FIRM")
    ovn = collapse_duplicates("ats_overnight", sym[["week", "tier", "mpid", "symbol",
                                                    "issue_name", "shares", "trades", "notional"]])
    _write("ats_overnight", ovn)

    cols = ["week", "symbol", "issue_name", "shares", "trades", "notional"]
    ats = collapse_duplicates("ats_symbol", finra_ats.load("ATS_W_SMBL", tiers=("T1",))[cols])
    _write("ats_symbol", ats)
    otc = collapse_duplicates("otc_symbol", finra_ats.load("OTC_W_SMBL", tiers=("T1",))[cols])
    _write("otc_symbol", otc)

    ven = finra_ats.load("ATS_W_FIRM")
    ven = collapse_duplicates("ats_venue", ven[["week", "tier", "mpid", "participant_name",
                                                "shares", "trades", "notional"]])
    _write("ats_venue", ven)

    universe = (
        ats.sort_values("week").groupby("symbol", as_index=False)["issue_name"].last()
    )
    universe = symbols.etp_flags(universe)
    universe["ticker"] = universe["symbol"].map(prices.to_yahoo)
    _write("universe", universe)

    # Every symbol traded on an overnight venue, both tiers (for market-level A1 facts).
    # `tier` = the tier of the symbol's most recent overnight row.
    so = (ovn.sort_values("week").groupby("symbol", as_index=False)
          .agg(issue_name=("issue_name", "last"), tier=("tier", "last")))
    _write("symbols_overnight", symbols.etp_flags(so))

    _write("nms_volume_daily", cboe.load())

    _write("regsho_daily", regsho.load())

    px = prices.load()
    px["volume_raw"] = measures.unadjust_volume(px)
    px["close_raw"] = measures.unadjust_price(px, "close")
    px = measures.night_day_returns(px)
    _write("prices_daily", px)

    _write("earnings", earnings.load())
    (PROCESSED / "store_meta.json").write_text(
        json.dumps({"merged_duplicate_rows": MERGED_DUPLICATES}, indent=1))
    refresh_views()


def refresh_views() -> None:
    con = duckdb.connect(str(DUCKDB_PATH))
    for name in SCHEMAS:
        path = (PROCESSED / f"{name}.parquet").as_posix()
        con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    con.close()


def read(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / f"{name}.parquet")


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DUCKDB_PATH), read_only=True)

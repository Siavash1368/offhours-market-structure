"""ETP flags from the Nasdaq Trader symbol directories, with a name-based fallback.

nasdaqlisted.txt and otherlisted.txt (pipe-delimited, current listings only) carry an `ETF` Y/N
column. Symbols no longer listed are classified from the FINRA issue name; the fallback is
recorded in the `etp_source` column so the audit can count it.
"""

from __future__ import annotations

import datetime as dt
import io
import re

import pandas as pd

from offhours.config import RAW, cfg
from offhours.data.http import request

CACHE = RAW / "symbols"
ETP_NAME = re.compile(
    r"\b(ETF|ETN|FUND|TRUST|SHARES|ISHARES|SPDR|PROSHARES|DIREXION|INVESCO QQQ|PORTFOLIO|INDEX)\b",
    re.I,
)


def download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    c = cfg()["symbols"]
    for key in ("nasdaq_listed", "other_listed"):
        path = CACHE / f"{key}.txt"
        if not path.exists():
            resp = request("GET", c[key], sleep=0.5)
            path.write_text(resp.text)
            (CACHE / f"{key}.downloaded").write_text(dt.date.today().isoformat())


def load_directory() -> pd.DataFrame:
    """symbol, security_name, etf (bool) from both directories."""
    a = pd.read_csv(io.StringIO((CACHE / "nasdaq_listed.txt").read_text()), sep="|", dtype=str)
    b = pd.read_csv(io.StringIO((CACHE / "other_listed.txt").read_text()), sep="|", dtype=str)
    a = a.rename(columns={"Symbol": "symbol", "Security Name": "security_name", "ETF": "etf"})
    b = b.rename(columns={"CQS Symbol": "symbol", "Security Name": "security_name", "ETF": "etf"})
    df = pd.concat([a[["symbol", "security_name", "etf"]], b[["symbol", "security_name", "etf"]]])
    df = df[df["symbol"].notna() & ~df["symbol"].str.startswith("File Creation")]
    df["etf"] = df["etf"].eq("Y")
    return df.drop_duplicates("symbol")


def etp_flags(finra_symbols: pd.DataFrame) -> pd.DataFrame:
    """Add `is_etp` and `etp_source` to a frame with columns symbol, issue_name."""
    directory = load_directory().set_index("symbol")["etf"]
    out = finra_symbols.copy()
    in_dir = out["symbol"].isin(directory.index)
    out["is_etp"] = out["symbol"].map(directory)
    out["etp_source"] = "nasdaqtrader"
    by_name = out["issue_name"].fillna("").str.contains(ETP_NAME)
    out.loc[~in_dir, "is_etp"] = by_name[~in_dir]
    out.loc[~in_dir, "etp_source"] = "issue_name"
    out["is_etp"] = out["is_etp"].astype(bool)
    return out

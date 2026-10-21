"""Shared helpers for the analysis modules: weekly aggregation of prices, month windows, I/O."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from offhours.config import TABLES


def week_start(dates: pd.Series) -> pd.Series:
    """Monday of the FINRA week that contains each date."""
    d = pd.to_datetime(dates)
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize()


def complete_weeks_in_month(weeks: pd.Series, month: str) -> list[pd.Timestamp]:
    """Weeks whose Monday and Friday both fall in `month` (YYYY-MM)."""
    w = pd.Series(pd.to_datetime(weeks.unique()))
    fri = w + pd.Timedelta(days=4)
    keep = (w.dt.strftime("%Y-%m") == month) & (fri.dt.strftime("%Y-%m") == month)
    return sorted(w[keep])


def weekly_prices(px: pd.DataFrame) -> pd.DataFrame:
    """Ticker-week aggregates from daily bars.

    volume_raw_w   sum of as-traded daily volume over the week's trading days
    dollar_vol_w   sum of close x volume (split-invariant)
    close_w        last close of the week (split-adjusted); close_raw_w as traded
    ret_w          weekly log return, sum of daily close-to-close log returns
    abs_ret_w      |ret_w|
    rv_w           realized volatility sqrt(sum r_cc^2)
    n_days         trading days in the week
    """
    d = px.copy()
    d["week"] = week_start(d["date"])
    d["dollar_vol"] = d["close"] * d["volume"]
    d["r2"] = d["r_cc"] ** 2
    g = d.sort_values("date").groupby(["ticker", "week"])
    out = g.agg(
        volume_raw_w=("volume_raw", "sum"),
        dollar_vol_w=("dollar_vol", "sum"),
        close_w=("close", "last"),
        close_raw_w=("close_raw", "last"),
        ret_w=("r_cc", "sum"),
        rv2=("r2", "sum"),
        n_days=("date", "count"),
    ).reset_index()
    out["rv_w"] = np.sqrt(out.pop("rv2"))
    out["abs_ret_w"] = out["ret_w"].abs()
    return out


def save_table(df: pd.DataFrame, name: str, index: bool = False) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES / f"{name}.csv", index=index)


def save_json(obj: dict, name: str) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / f"{name}.json").write_text(json.dumps(obj, indent=1, default=str))

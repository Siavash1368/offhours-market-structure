"""Measures: returns, split-unadjusted volume, overnight share, concentration, WPC.

Each function states its formula, reference and assumptions. Inputs are plain pandas objects so
the functions can be unit-tested on hand-made examples (tests/test_measures.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------------------------
# Prices and volume
# ---------------------------------------------------------------------------------------------


def split_factor(df: pd.DataFrame) -> pd.Series:
    """Cumulative split factor after each date: F_it = prod_{s > t} split_is.

    `split` is 0 (Yahoo's "no split") or the ratio (new shares per old share) on the ex-date.
    The product of ratios strictly after t = (product over all dates) / (product up to t).
    Requires columns ticker, date, split; returns a Series aligned to df.index.
    """
    d = df.sort_values(["ticker", "date"])
    log_r = np.log(d["split"].fillna(0).replace(0, 1.0))
    g = log_r.groupby(d["ticker"])
    return np.exp(g.transform("sum") - g.cumsum()).reindex(df.index)


def unadjust_volume(df: pd.DataFrame) -> pd.Series:
    """Convert split-adjusted daily volume back to shares as traded.

    Formula: Yahoo reports V^adj_it = V_it * F_it with F_it from `split_factor`, so
    V_it = V^adj_it / F_it.

    Assumption: Yahoo applies all later splits to past volume (auto_adjust=False still
    split-adjusts OHLCV). Reference: Yahoo Finance adjustment convention.
    """
    return df["volume"] / split_factor(df)


def unadjust_price(df: pd.DataFrame, col: str = "close") -> pd.Series:
    """Price as traded: P_it = P^adj_it * F_it (F_it from `split_factor`)."""
    return df[col] * split_factor(df)


def night_day_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Close-to-open (night) and open-to-close (day) log returns.

    r_n,t+1 = ln(Open_{t+1} / Close_t)    night return ending at the open of day t+1
    r_d,t+1 = ln(Close_{t+1} / Open_{t+1}) day return of day t+1
    r_cc,t+1 = r_n,t+1 + r_d,t+1 = ln(Close_{t+1} / Close_t)

    Prices are split-adjusted but not dividend-adjusted (yfinance auto_adjust=False), so a split
    does not create a jump; ex-dividend nights show a small negative night return equal to about
    the dividend yield. Assumes rows are trading days in date order within each ticker.
    Output is aligned to day t+1 (the date of the open).
    """
    d = df.sort_values(["ticker", "date"]).copy()
    prev_close = d.groupby("ticker")["close"].shift(1)
    d["r_night"] = np.log(d["open"] / prev_close)
    d["r_day"] = np.log(d["close"] / d["open"])
    d["r_cc"] = d["r_night"] + d["r_day"]
    return d


# ---------------------------------------------------------------------------------------------
# Overnight share and concentration
# ---------------------------------------------------------------------------------------------


def overnight_share(overnight_shares: pd.Series, total_shares: pd.Series) -> pd.Series:
    """Overnight share_{it} = overnight-ATS shares_{it} / total shares_{it} (stock-week).

    Numerator: weekly shares on the overnight-only ATSs (FINRA weekly file). Denominator:
    consolidated daily volume (price source) summed over the trading days of the FINRA week,
    with overnight shares added back when they are not already in it.

    Assumption: the denominator excludes suppressed Sunday-night TRF reports and possibly part of
    the other overnight prints (Yahoo's daily volume convention is not documented), so the share
    is measured with error. Values outside [0, 1] are set to NaN and logged by the caller.
    """
    s = overnight_shares / total_shares
    return s.where((s >= 0) & (s <= 1))


def top_k_share(volume: pd.Series, k: int) -> float:
    """Share of total volume in the k largest units: sum of top-k v_i / sum v_i."""
    v = volume.dropna().sort_values(ascending=False)
    total = v.sum()
    return float(v.iloc[:k].sum() / total) if total > 0 else np.nan


def herfindahl(volume: pd.Series) -> float:
    """Herfindahl-Hirschman index of volume shares: H = sum_i s_i^2, s_i = v_i / sum_j v_j.

    Ranges from 1/N (equal split over N units) to 1 (all volume in one unit). Reported on the
    0-1 scale (multiply by 10,000 for the antitrust convention).
    Reference: Hirschman (1964), "The paternity of an index", AER 54(5).
    """
    v = volume.dropna()
    total = v.sum()
    if total <= 0:
        return np.nan
    s = v / total
    return float((s**2).sum())


# ---------------------------------------------------------------------------------------------
# Price discovery
# ---------------------------------------------------------------------------------------------


def weighted_price_contribution(
    r_window: pd.Series, r_total: pd.Series, groups: pd.Series | None = None
) -> pd.Series | float:
    """Weighted price contribution (WPC) of a sub-window to the total return.

    Formula (van Bommel 2011, eq. 2; Barclay and Warner 1993):

        WPC = sum_i  w_i * (r_window,i / r_total,i),   w_i = |r_total,i| / sum_j |r_total,j|

    which simplifies to  WPC = sum_i sign(r_total,i) * r_window,i / sum_j |r_total,j|.

    Here r_window = night return ln(Open_{t+1}/Close_t) and r_total = close-to-close return
    ln(Close_{t+1}/Close_t), so WPC is the fraction of the event's price change that is already
    in the opening price. WPC = 1: all of the move happens by the open; WPC < 1: the day session
    adds to it; WPC > 1: the open overshoots and the day reverses.

    Assumptions: returns are log returns that add up (r_total = r_night + r_day). Observations
    with r_total = 0 get zero weight. Weighting by |r_total| lets large moves dominate, which is
    the point (they carry the information) but also makes WPC sensitive to a few events; the
    caller reports bootstrap confidence intervals.
    References: Barclay, M. and Warner, J. (1993), "Stealth trading and volatility", JFE 34;
    van Bommel, J. (2011), "Measuring price discovery: the variance ratio, the R^2, and the
    weighted price contribution", Finance Research Letters 8(3).
    """
    df = pd.DataFrame({"w": r_window, "t": r_total}).dropna()
    num = np.sign(df["t"]) * df["w"]
    den = df["t"].abs()
    if groups is None:
        return float(num.sum() / den.sum()) if den.sum() > 0 else np.nan
    g = groups.reindex(df.index)
    return num.groupby(g).sum() / den.groupby(g).sum()


def bootstrap_wpc(
    r_window: pd.Series,
    r_total: pd.Series,
    cluster: pd.Series,
    n_boot: int = 999,
    seed: int = 0,
) -> tuple[float, float, float]:
    """WPC with a cluster (block) bootstrap 95% interval: (estimate, lo, hi).

    Resamples clusters (e.g. stocks) with replacement, recomputes WPC each time and takes the
    2.5th and 97.5th percentiles. Assumes independence across clusters, arbitrary dependence
    within a cluster.
    """
    df = pd.DataFrame({"w": r_window, "t": r_total, "c": cluster}).dropna()
    df["num"] = np.sign(df["t"]) * df["w"]
    df["den"] = df["t"].abs()
    agg = df.groupby("c")[["num", "den"]].sum()
    est = agg["num"].sum() / agg["den"].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(agg), size=(n_boot, len(agg)))
    num = agg["num"].to_numpy()[idx].sum(axis=1)
    den = agg["den"].to_numpy()[idx].sum(axis=1)
    draws = num / den
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(est), float(lo), float(hi)


def wpc_gap_change(
    a: pd.DataFrame, b: pd.DataFrame, n_boot: int = 999, seed: int = 0
) -> tuple[float, float, float]:
    """Change in the high-minus-low WPC gap between two periods, with a bootstrap 95% interval.

    Each frame has columns r_w (window return), r_t (total return), cluster (stock) and
    group (1 = low, 3 = high). Gap_P = WPC_P(group 3) - WPC_P(group 1);
    returns (Gap_b - Gap_a, lo, hi). Stocks are resampled with replacement within each period
    independently (the periods are treated as independent samples; a stock's group is fixed).
    Assumptions as in `weighted_price_contribution`, plus independence across stocks.
    """
    rng = np.random.default_rng(seed)

    def per_stock(df):
        d = df.assign(num=np.sign(df["r_t"]) * df["r_w"], den=df["r_t"].abs())
        return d.groupby(["group", "cluster"])[["num", "den"]].sum()

    def gap_draws(df):
        ps = per_stock(df)
        out = []
        for g in (1, 3):
            arr = ps.loc[g].to_numpy()
            idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
            s = arr[idx].sum(axis=1)
            out.append(s[:, 0] / s[:, 1])
        full = {g: ps.loc[g].sum() for g in (1, 3)}
        point = full[3]["num"] / full[3]["den"] - full[1]["num"] / full[1]["den"]
        return point, out[1] - out[0]

    pa, da = gap_draws(a)
    pb, db = gap_draws(b)
    lo, hi = np.percentile(db - da, [2.5, 97.5])
    return float(pb - pa), float(lo), float(hi)


def realized_volatility(daily_returns: pd.Series) -> float:
    """Weekly realized volatility: sqrt(sum_t r_t^2) over the trading days of the week.

    Uses close-to-close log returns; no mean adjustment (the mean is negligible at daily
    frequency). Reference: Andersen, Bollerslev, Diebold and Labys (2003), Econometrica 71(2).
    """
    r = daily_returns.dropna()
    return float(np.sqrt((r**2).sum())) if len(r) else np.nan

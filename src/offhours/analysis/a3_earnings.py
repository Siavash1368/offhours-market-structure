"""A3. Price discovery around after-close earnings announcements (NMS Tier 1 common stocks).

Event: stock i announces after the close (>= 16:00 ET) on trading day t. Returns:

    r_n = ln(Open_{t+1} / Close_t)      night return (includes 4-8 pm, 8 pm-4 am, 4-9:30 am)
    r_d = ln(Close_{t+1} / Open_{t+1})  next-day session return

1. Opening-price efficiency (Barclay and Hendershott 2003 use the same idea for after-hours
   trading; see also Jiang, Likitapiwat and McInish 2012):

       r_d = a + b r_n + c (r_n x I) + d I + e

   I = overnight-trading intensity, the stock's average overnight-ATS share of weekly volume over
   the 4 FINRA weeks before the event week (in percent; pre-determined, so this week's overnight
   trading cannot feed back into it). b < 0 means the opening price overshoots and partly
   reverses; b > 0 means it underreacts and the day continues the move. c > 0 with b < 0, or
   c < 0 with b > 0, means more overnight trading goes with a smaller correction, i.e. a more
   efficient open. Standard errors clustered by stock and by date (two-way).

2. Weighted price contribution of the night over Close_t -> Close_{t+1} (measures.
   weighted_price_contribution), by tercile of I, with stock-cluster bootstrap intervals.

3. Baseline: the same on non-earnings nights for the same stocks, excluding nights within one
   trading day of any announcement, and a pooled model with earnings-night interactions.

Assumptions and limits: daily data cannot isolate the 8 pm-4 am window, so r_n mixes the
after-hours (4-8 pm), overnight and pre-market sessions; I is measured weekly and on ATS volume
only; stocks with more overnight trading differ in many ways (size, retail ownership, volatility),
so c is an association. The robustness module adds size controls and a pre-2021 placebo.
Nights with |r_n| or |r_d| > 0.5 (data errors or extreme events) are dropped and counted.
References: Barclay, M. and Hendershott, T. (2003), "Price discovery and trading after hours",
RFS 16(4); Jiang, C., Likitapiwat, T. and McInish, T. (2012), "Information content of earnings
announcements: evidence from after-hours trading", JFQA 47(6).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from offhours import measures, store
from offhours.analysis.common import save_json, save_table, week_start
from offhours.analysis.tables import side_by_side, tidy
from offhours.config import TABLES

log = logging.getLogger(__name__)
MAX_ABS_RET = 0.5
LABELS = {
    "r_n": "night return r_n",
    "r_n_x_I": "r_n x intensity (pp)",
    "I": "intensity (pp)",
    "r_n_x_size": "r_n x log dollar volume",
    "size": "log dollar volume",
    "r_n_x_T2": "r_n x tercile 2",
    "r_n_x_T3": "r_n x tercile 3 (highest)",
    "T2": "tercile 2",
    "T3": "tercile 3",
    "r_n_x_E": "r_n x earnings night",
    "r_n_x_I_x_E": "r_n x intensity x earnings",
    "I_x_E": "intensity x earnings",
    "E": "earnings night",
    "const": "constant",
}


def nights(px: pd.DataFrame) -> pd.DataFrame:
    """One row per stock-night, indexed by the announcement-side date t (prev trading day)."""
    d = px.sort_values(["ticker", "date"])[["ticker", "date", "r_night", "r_day", "r_cc",
                                            "close", "volume"]].copy()
    d["t"] = d.groupby("ticker")["date"].shift(1)
    d = d.dropna(subset=["t", "r_night", "r_day"])
    d = d.rename(columns={"date": "t1", "r_night": "r_n", "r_day": "r_d"})
    return d


def weekly_intensity(panel: pd.DataFrame) -> pd.DataFrame:
    """Pre-event intensity by ticker and week W: mean ovn_share over weeks W-4..W-1 (>= 3 obs)."""
    p = panel[["ticker", "week", "ovn_share", "ovn_shares", "dollar_vol_w"]].copy()
    p = p.sort_values(["ticker", "week"]).set_index("week")
    out = []
    for tkr, g in p.groupby("ticker"):
        g = g.asfreq("W-MON")  # fill missing weeks with NaN so the window is calendar-based
        roll = g["ovn_share"].rolling(4, min_periods=3).mean().shift(1)
        roll_sh = g["ovn_shares"].rolling(4, min_periods=3).mean().shift(1)
        size = np.log(g["dollar_vol_w"].rolling(4, min_periods=3).mean().shift(1).clip(lower=1))
        out.append(pd.DataFrame({"ticker": tkr, "I": roll, "I_shares": roll_sh, "size": size}))
    res = pd.concat(out).reset_index().rename(columns={"index": "week"})
    return res.dropna(subset=["I"])


def validated_after_close(ern: pd.DataFrame, px: pd.DataFrame,
                          drop_contradicting: bool) -> pd.DataFrame:
    """After-close announcements (ticker, t); optionally without flag-contradicting events.

    Contradicting = |night t-1->t| > |night t->t+1| (earnings_check.classify). Dropped events
    are also excluded from the baseline, since their true timing is uncertain.
    """
    from offhours.analysis import earnings_check

    ac = ern[ern["timing"] == "after_close"][["ticker", "date"]].rename(columns={"date": "t"})
    if not drop_contradicting:
        return ac.assign(contradicts=False)
    v = earnings_check.classify(earnings_check.event_returns(px, ern))
    v = v.loc[v["timing"] == "after_close", ["ticker", "t", "contradicts"]]
    out = ac.merge(v, on=["ticker", "t"], how="left")
    out["contradicts"] = out["contradicts"].fillna(False).astype(bool)
    return out


def build_events(panel: pd.DataFrame, px: pd.DataFrame, ern: pd.DataFrame,
                 drop_contradicting: bool | None = None) -> pd.DataFrame:
    """Stock-nights with intensity, earnings flags and terciles; restricted to the FINRA sample."""
    from offhours.config import cfg

    if drop_contradicting is None:
        drop_contradicting = cfg()["earnings"].get("drop_contradicting", False)
    n = nights(px)
    n["week"] = week_start(n["t"])
    inten = weekly_intensity(panel)
    n = n.merge(inten, on=["ticker", "week"], how="inner")

    ac = validated_after_close(ern, px, drop_contradicting)
    ac["E"] = 1.0
    n = n.merge(ac, on=["ticker", "t"], how="left")
    n["E"] = n["E"].fillna(0.0)
    n["contradicts"] = n["contradicts"].fillna(False).astype(bool)

    # Exclude from the baseline any night within one trading day of an announcement (any timing,
    # including flag-contradicting ones, which are dropped only after this step).
    any_e = ern[["ticker", "date"]].rename(columns={"date": "d"})
    n = n.sort_values(["ticker", "t"])
    n["pos"] = n.groupby("ticker").cumcount()
    near = set()
    pos_by_date = n.set_index(["ticker", "t"])["pos"]
    for tkr, dt_ in any_e.itertuples(index=False):
        if (tkr, dt_) in pos_by_date.index:
            p = pos_by_date[(tkr, dt_)]
            near.update({(tkr, p - 1), (tkr, p), (tkr, p + 1)})
    n["near_event"] = [(a, b) in near for a, b in zip(n["ticker"], n["pos"], strict=True)]
    n["sample"] = np.where(n["E"] == 1, "earnings", np.where(n["near_event"], "near", "baseline"))
    n = n[n["sample"] != "near"].drop(columns=["pos", "near_event"])

    dropped_contradicting = int((n["contradicts"] & (n["E"] == 1)).sum())
    n = n[~n["contradicts"]].drop(columns="contradicts")

    big = (n["r_n"].abs() > MAX_ABS_RET) | (n["r_d"].abs() > MAX_ABS_RET)
    dropped_extreme = int(big.sum())
    n = n[~big].copy()

    # Terciles of intensity, cut on the earnings-event distribution so groups are comparable.
    cuts = n.loc[n["E"] == 1, "I"].quantile([1 / 3, 2 / 3]).to_numpy()
    n["tercile"] = np.select([n["I"] <= cuts[0], n["I"] <= cuts[1]], [1, 2], 3)
    n.attrs.update({"dropped_contradicting": dropped_contradicting,
                    "dropped_extreme": dropped_extreme, "tercile_cuts": cuts.tolist()})
    return n


def _design(df: pd.DataFrame, spec: str) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["const"] = 1.0
    X["r_n"] = df["r_n"]
    if spec in ("intensity", "intensity_size", "pooled"):
        X["r_n_x_I"] = df["r_n"] * df["I"]
        X["I"] = df["I"]
    if spec == "intensity_size":
        X["r_n_x_size"] = df["r_n"] * df["size"]
        X["size"] = df["size"]
    if spec == "tercile":
        for k in (2, 3):
            X[f"T{k}"] = (df["tercile"] == k).astype(float)
            X[f"r_n_x_T{k}"] = df["r_n"] * X[f"T{k}"]
    if spec == "pooled":
        X["E"] = df["E"]
        X["r_n_x_E"] = df["r_n"] * df["E"]
        X["I_x_E"] = df["I"] * df["E"]
        X["r_n_x_I_x_E"] = df["r_n"] * df["I"] * df["E"]
    return X


def efficiency_regression(df: pd.DataFrame, spec: str):
    """OLS of r_d on the design, SEs clustered by stock (entity) and date (time)."""
    d = df.dropna(subset=["r_n", "r_d", "I"] + (["size"] if spec == "intensity_size" else []))
    d = d.set_index(["ticker", "t"])
    X = _design(d, spec)
    return PanelOLS(d["r_d"], X).fit(cov_type="clustered", cluster_entity=True,
                                     cluster_time=True), d


def wpc_table(df: pd.DataFrame, n_boot: int = 999) -> pd.DataFrame:
    rows = []
    for (sample, terc), g in df.groupby(["sample", "tercile"]):
        est, lo, hi = measures.bootstrap_wpc(g["r_n"], g["r_cc"], g["ticker"], n_boot=n_boot)
        rows.append({"sample": sample, "tercile": int(terc), "wpc_night": est, "ci_lo": lo,
                     "ci_hi": hi, "n_nights": len(g), "n_stocks": g["ticker"].nunique(),
                     "mean_I": g["I"].mean()})
    for sample, g in df.groupby("sample"):
        est, lo, hi = measures.bootstrap_wpc(g["r_n"], g["r_cc"], g["ticker"], n_boot=n_boot)
        rows.append({"sample": sample, "tercile": 0, "wpc_night": est, "ci_lo": lo, "ci_hi": hi,
                     "n_nights": len(g), "n_stocks": g["ticker"].nunique(),
                     "mean_I": g["I"].mean()})
    return pd.DataFrame(rows).sort_values(["sample", "tercile"])


def stats_row(res, d, label) -> dict:
    return {"Sample": label, "Observations": int(res.nobs),
            "Stocks": int(d.index.get_level_values(0).nunique()),
            "Dates": int(d.index.get_level_values(1).nunique()), "R2": float(res.rsquared)}


def load_inputs():
    from offhours.analysis.a2_panel import build_panel

    panel = build_panel()
    px = store.read("prices_daily")
    ern = store.read("earnings")
    return panel, px, ern


def run() -> dict:
    panel, px, ern = load_inputs()
    ev = build_events(panel, px[px["ticker"].isin(set(panel["ticker"]))], ern)
    meta = dict(ev.attrs)  # drop counts and tercile cuts, kept before any further filtering
    # Common stocks only (ETPs have no earnings; keep baseline comparable).
    common = set(panel.loc[panel["is_etp"] == 0, "ticker"])
    ev = ev[ev["ticker"].isin(common)]
    save_table(ev.assign(t=ev["t"].dt.date, t1=ev["t1"].dt.date)
               [["ticker", "t", "t1", "sample", "E", "r_n", "r_d", "r_cc", "I", "I_shares",
                 "size", "tercile"]].query("E == 1"), "a3_event_list")

    earn = ev[ev["sample"] == "earnings"]
    base = ev[ev["sample"] == "baseline"]
    models, stats = [], []
    for spec, sub, label, name in [
        ("base", earn, "earnings", "(1) Earnings"),
        ("intensity", earn, "earnings", "(2) Earnings"),
        ("tercile", earn, "earnings", "(3) Earnings"),
        ("intensity_size", earn, "earnings", "(4) Earnings"),
        ("intensity", base, "non-earnings", "(5) Non-earnings"),
        ("pooled", ev, "pooled", "(6) Pooled"),
    ]:
        res, d = efficiency_regression(sub, spec)
        models.append(tidy(res, name))
        stats.append(stats_row(res, d, label))
    save_table(pd.concat(models), "a3_efficiency")
    md = side_by_side(models, stats, LABELS)
    cuts = meta.get("tercile_cuts", [np.nan, np.nan])
    note = (
        "\n\nDependent variable: next-day session return r_d = ln(Close_{t+1}/Open_{t+1}). "
        "Intensity = average overnight-ATS share of weekly volume over the 4 weeks before the "
        f"event week, in percentage points. Tercile cut-offs (earnings events): "
        f"{cuts[0]:.3f} and {cuts[1]:.3f} pp. Standard errors clustered by stock and date. "
        "*** p<0.01, ** p<0.05, * p<0.10. Source: `src/offhours/analysis/a3_earnings.py`."
    )
    (TABLES / "a3_efficiency.md").write_text(
        "# Table A3a. Opening-price efficiency: r_d on r_n\n\n" + md + note + "\n")

    wpc = wpc_table(ev)
    save_table(wpc, "a3_wpc")
    from offhours import figures

    figures.a3_figures(ev, wpc)

    m2 = models[1].set_index("term")
    m5 = models[4].set_index("term")
    m6 = models[5].set_index("term")
    summary = {
        "n_earnings_events": int(len(earn)),
        "n_earnings_stocks": int(earn["ticker"].nunique()),
        "n_baseline_nights": int(len(base)),
        "dropped_extreme": int(meta.get("dropped_extreme", 0)),
        "dropped_flag_contradicting": int(meta.get("dropped_contradicting", 0)),
        "event_dates": [str(earn["t"].min().date()), str(earn["t"].max().date())],
        "tercile_cuts_pp": cuts,
        "b_rn_earnings": float(models[0].set_index("term").loc["r_n", "coef"]),
        "p_rn_earnings": float(models[0].set_index("term").loc["r_n", "p"]),
        "c_rn_x_I_earnings": float(m2.loc["r_n_x_I", "coef"]),
        "p_rn_x_I_earnings": float(m2.loc["r_n_x_I", "p"]),
        "c_rn_x_I_baseline": float(m5.loc["r_n_x_I", "coef"]),
        "p_rn_x_I_baseline": float(m5.loc["r_n_x_I", "p"]),
        "triple_rn_x_I_x_E": float(m6.loc["r_n_x_I_x_E", "coef"]),
        "p_triple": float(m6.loc["r_n_x_I_x_E", "p"]),
        "wpc": wpc.to_dict(orient="records"),
    }
    save_json(summary, "a3_summary")
    log.info("A3 done:\n%s\n%s", md, wpc.to_string())
    return summary

"""A2. Who trades overnight? Stock-week panel of overnight share on stock characteristics.

Tier 1 only (cleaner prices and earnings data; 2-week publication delay). Tier 2 is most of
overnight share volume (reports/tables/a1_tier_coverage.csv), so results describe Tier 1 stocks.

Model (main specification):

    ovn_share_it = b1 log_price_i,t-1 + b2 log_dvol_i,t-1 + b3 rv_i,t-1 + b4 absret_i,t-1
                   + b5 earn_it + b6 short_share_i,t-1 + a_i + d_t + e_it

  ovn_share_it   overnight-ATS shares / consolidated shares, stock i, FINRA week t, in percent
  log_price      log closing price (as traded) at the end of week t-1
  log_dvol       log dollar volume in week t-1 (size proxy; market cap is not in the public data)
  rv             realized volatility of daily close-to-close log returns in week t-1, in percent
  absret         |weekly log return| in week t-1, in percent
  earn           1 if the stock announces earnings in week t (scheduled, so not caused by e_it)
  short_share    off-exchange short volume / off-exchange volume (Reg SHO), week t-1, in percent
  a_i, d_t       stock and week fixed effects

Estimator: linearmodels.PanelOLS (within transformation). Standard errors clustered by stock and
by week (Cameron, Gelbach and Miller 2011, JBES 29(2)), which allows arbitrary correlation within
a stock over time and across stocks within a week.

Alongside: pooled OLS (adds an ETP dummy, no fixed effects) and stock-FE-only (no week effects).

Assumptions and interpretation: lagging the regressors one week avoids mechanical feedback from
this week's overnight trading to the regressors, but omitted stock-week shocks (news, retail
attention) can still drive both. Coefficients are conditional associations, not causal effects.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

from offhours import measures, store
from offhours.analysis.common import save_json, save_table, week_start, weekly_prices
from offhours.analysis.tables import side_by_side, tidy
from offhours.config import TABLES

log = logging.getLogger(__name__)

REGRESSORS = ["log_price_l1", "log_dvol_l1", "rv_l1", "absret_l1", "earn_week", "short_share_l1"]
LABELS = {
    "log_price_l1": "log price (t-1)",
    "log_dvol_l1": "log dollar volume (t-1)",
    "rv_l1": "realized vol., % (t-1)",
    "absret_l1": "|weekly return|, % (t-1)",
    "earn_week": "earnings week",
    "short_share_l1": "off-exch. short share, % (t-1)",
    "is_etp": "ETP",
    "const": "constant",
}


def build_panel(d: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Stock-week panel for Tier 1 symbols with price data in the sample weeks.

    Rows exist for every symbol-week with at least one trading day in the price data; overnight
    shares are zero when the FINRA file has no overnight-venue row for the symbol-week.
    """
    d = d or {}

    def get(key: str, table: str) -> pd.DataFrame:
        return d[key] if key in d else store.read(table)

    uni = get("uni", "universe")
    ovn = get("ovn", "ats_overnight")
    px = get("px", "prices_daily")
    weeks = ovn["week"].drop_duplicates()

    w = weekly_prices(px[px["ticker"].isin(set(uni["ticker"]))])
    w = w.merge(uni[["symbol", "ticker", "is_etp"]], on="ticker", how="inner")
    w = w[w["week"].between(weeks.min() - pd.Timedelta(weeks=5), weeks.max())]

    o = (ovn[ovn["tier"] == "T1"].groupby(["symbol", "week"])
         .agg(ovn_shares=("shares", "sum"), ovn_notional=("notional", "sum")).reset_index())
    p = w.merge(o, on=["symbol", "week"], how="left")
    p[["ovn_shares", "ovn_notional"]] = p[["ovn_shares", "ovn_notional"]].fillna(0.0)

    # Reg SHO: weekly off-exchange short share.
    rs = get("regsho", "regsho_daily")
    rs = rs.assign(week=week_start(rs["date"]))
    rsw = rs.groupby(["symbol", "week"])[["short_volume", "total_volume"]].sum().reset_index()
    rsw["short_share"] = 100 * rsw["short_volume"] / rsw["total_volume"]
    p = p.merge(rsw[["symbol", "week", "short_share"]], on=["symbol", "week"], how="left")

    # Earnings weeks (any timing).
    e = get("earnings", "earnings")
    e = e.assign(week=week_start(e["date"]))[["ticker", "week"]].drop_duplicates()
    e["earn_week"] = 1.0
    p = p.merge(e, on=["ticker", "week"], how="left")
    p["earn_week"] = p["earn_week"].fillna(0.0)

    p["ovn_share_raw"] = p["ovn_shares"] / p["volume_raw_w"]
    p["violation"] = p["ovn_shares"] > p["volume_raw_w"]
    p["ovn_share"] = 100 * measures.overnight_share(p["ovn_shares"], p["volume_raw_w"])
    p["ovn_share_dollar"] = 100 * measures.overnight_share(p["ovn_notional"], p["dollar_vol_w"])

    p = p.sort_values(["symbol", "week"])
    g = p.groupby("symbol")
    # Lag only to the immediately preceding calendar week; gaps give NaN.
    prev_week = g["week"].shift(1)
    consecutive = (p["week"] - prev_week) == pd.Timedelta(weeks=1)
    p["log_price_l1"] = np.log(g["close_raw_w"].shift(1)).where(consecutive)
    p["log_dvol_l1"] = np.log(g["dollar_vol_w"].shift(1).clip(lower=1)).where(consecutive)
    p["rv_l1"] = (100 * g["rv_w"].shift(1)).where(consecutive)
    p["absret_l1"] = (100 * g["abs_ret_w"].shift(1)).where(consecutive)
    p["short_share_l1"] = g["short_share"].shift(1).where(consecutive)
    p["is_etp"] = p["is_etp"].astype(float)
    return p[p["week"].isin(set(weeks))].reset_index(drop=True)


def estimate(panel: pd.DataFrame) -> dict:
    """Pooled OLS, stock FE, stock + week FE; all clustered by stock and week."""
    df = panel.dropna(subset=["ovn_share", *REGRESSORS]).copy()
    df = df.set_index(["symbol", "week"])
    y = df["ovn_share"]
    X = df[REGRESSORS]

    pooled = PanelOLS(y, sm.add_constant(df[[*REGRESSORS, "is_etp"]])).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    fe_i = PanelOLS(y, X, entity_effects=True, drop_absorbed=True).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    fe_it = PanelOLS(y, X, entity_effects=True, time_effects=True, drop_absorbed=True).fit(
        cov_type="clustered", cluster_entity=True, cluster_time=True)
    return {"pooled": pooled, "stock_fe": fe_i, "two_way_fe": fe_it, "data": df}


def fit_stats(res, df: pd.DataFrame, fe: str) -> dict:
    """Fit statistics; R2 is overall for pooled OLS and within-stock for FE models."""
    return {
        "Fixed effects": fe,
        "Observations": int(res.nobs),
        "Stocks": int(df.index.get_level_values(0).nunique()),
        "Weeks": int(df.index.get_level_values(1).nunique()),
        "R2 (overall if no FE, else within)": float(res.rsquared_within if fe != "none"
                                                    else res.rsquared),
    }


def winsorize(s: pd.Series, lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    """Clip a series at its lo and hi quantiles (pooled over the estimation sample)."""
    return s.clip(s.quantile(lo), s.quantile(hi))


def diagnostics(panel: pd.DataFrame) -> tuple[list[pd.DataFrame], list[dict]]:
    """Two-way FE model on alternative samples and outcomes (added after inspecting results).

    (D1) outcome and continuous regressors winsorized at the 1st/99th percentiles;
    (D2) common stocks only; (D3) ETPs only (earnings week dropped: always 0);
    (D4) extensive margin, outcome = 100 x 1{any overnight-venue shares} (linear probability,
         in percentage points).
    All: stock and week fixed effects, standard errors clustered by stock and week.
    """
    base = panel.dropna(subset=["ovn_share", *REGRESSORS]).copy()
    cont = ["log_price_l1", "log_dvol_l1", "rv_l1", "absret_l1", "short_share_l1"]
    specs = []
    w = base.copy()
    for c in ["ovn_share", *cont]:
        w[c] = winsorize(w[c])
    specs.append(("(D1) Winsorized 1/99", w, "ovn_share", REGRESSORS))
    specs.append(("(D2) Common stocks", base[base["is_etp"] == 0], "ovn_share", REGRESSORS))
    specs.append(("(D3) ETPs", base[base["is_etp"] == 1], "ovn_share",
                  [r for r in REGRESSORS if r != "earn_week"]))
    ext = base.assign(any_ovn=100.0 * (base["ovn_shares"] > 0))
    specs.append(("(D4) Any overnight trading (LPM)", ext, "any_ovn", REGRESSORS))
    tidies, stats = [], []
    for name, df, y, X in specs:
        d = df.set_index(["symbol", "week"])
        res = PanelOLS(d[y], d[X], entity_effects=True, time_effects=True,
                       drop_absorbed=True).fit(cov_type="clustered", cluster_entity=True,
                                               cluster_time=True)
        tidies.append(tidy(res, name))
        s = fit_stats(res, d, "stock, week")
        s["Mean of outcome"] = float(d[y].mean())
        stats.append(s)
    return tidies, stats


def etp_vs_common(panel: pd.DataFrame, weeks: int = 13) -> pd.DataFrame:
    """Stock-level overnight share by ETP flag over the last `weeks` weeks (Tier 1 only)."""
    p = panel[panel["week"] > panel["week"].max() - pd.Timedelta(weeks=weeks)]
    g = p.groupby("is_etp")
    return pd.DataFrame({
        "stock_weeks": g.size(),
        "symbols": g["symbol"].nunique(),
        "mean_ovn_share_pct": g["ovn_share"].mean(),
        "median_ovn_share_pct": g["ovn_share"].median(),
        "volume_weighted_ovn_share_pct": 100 * g["ovn_shares"].sum() / g["volume_raw_w"].sum(),
        "share_with_any_ovn": g["ovn_shares"].apply(lambda s: (s > 0).mean()),
    }).reset_index()


def run(panel: pd.DataFrame | None = None) -> dict:
    panel = build_panel() if panel is None else panel
    save_table(etp_vs_common(panel), "a2_etp_vs_common_tier1")
    viol = panel[panel["violation"]]
    log.info("A2: %d stock-weeks; %d with overnight shares > consolidated volume",
             len(panel), len(viol))
    save_table(viol[["symbol", "week", "ovn_shares", "volume_raw_w", "ovn_share_raw"]]
               .sort_values("ovn_share_raw", ascending=False), "a2_denominator_violations")

    r = estimate(panel)
    models = [("(1) Pooled OLS", r["pooled"], "none"),
              ("(2) Stock FE", r["stock_fe"], "stock"),
              ("(3) Stock + week FE", r["two_way_fe"], "stock, week")]
    tidies = [tidy(res, name) for name, res, _ in models]
    stats = [fit_stats(res, r["data"], fe) for _, res, fe in models]
    for s in stats:
        s["Mean of outcome"] = float(r["data"]["ovn_share"].mean())
    save_table(pd.concat(tidies), "a2_regressions")
    md = side_by_side(tidies, stats, LABELS, fmt="{:.4f}")
    note = (
        "\n\nNMS Tier 1 stocks and ETPs. Dependent variable: overnight-ATS share of consolidated "
        "weekly share volume, in percentage points (mean shown; median 0). Standard errors (in "
        "parentheses) clustered by stock and week. *** p<0.01, ** p<0.05, * p<0.10. Source: "
        "`src/offhours/analysis/a2_panel.py`."
    )
    (TABLES / "a2_regressions.md").write_text(
        "# Table A2. Who trades overnight? Stock-week panel\n\n" + md + note + "\n")

    d_tidies, d_stats = diagnostics(panel)
    save_table(pd.concat(d_tidies), "a2_diagnostics")
    d_md = side_by_side(d_tidies, d_stats, LABELS, fmt="{:.4f}")
    d_note = (
        "\n\nDiagnostics for Table A2, column (3) specification (stock and week fixed effects, "
        "standard errors clustered by stock and week). **Added after inspecting the main "
        "results and the outcome distribution** (65% zeros; the top 0.1% of stock-weeks carry "
        "about a fifth of the outcome's sum), so they are not pre-specified. D1 winsorizes the "
        "outcome and continuous regressors at the 1st/99th percentiles; D2/D3 split common "
        "stocks and ETPs; D4 is a linear probability model for any overnight-venue trading, "
        "in percentage points. Source: `src/offhours/analysis/a2_panel.py` (`diagnostics`)."
    )
    (TABLES / "a2_diagnostics.md").write_text(
        "# Table A2b. Diagnostics\n\n" + d_md + d_note + "\n")

    d = r["data"]
    desc = d[["ovn_share", *REGRESSORS, "is_etp"]].describe().T
    save_table(desc.reset_index().rename(columns={"index": "variable"}), "a2_descriptives")

    # Standardized effect of the main FE model: coefficient x within-stock SD of the regressor.
    within_sd = d[REGRESSORS].groupby(level=0).transform(lambda s: s - s.mean()).std()
    fe = r["two_way_fe"]
    std_eff = (fe.params * within_sd).rename("effect_of_1sd_within_change_pp")
    summary = {
        "n_obs": int(fe.nobs),
        "n_stocks": int(d.index.get_level_values(0).nunique()),
        "n_weeks": int(d.index.get_level_values(1).nunique()),
        "mean_ovn_share_pct": float(d["ovn_share"].mean()),
        "share_stock_weeks_with_ovn": float((d["ovn_share"] > 0).mean()),
        "n_denominator_violations": int(len(viol)),
        "panel_rows_before_dropna": int(len(panel)),
        "coef_two_way": fe.params.to_dict(),
        "p_two_way": fe.pvalues.to_dict(),
        "std_effect_two_way_pp": std_eff.to_dict(),
        "etp_coef_pooled": float(r["pooled"].params["is_etp"]),
        "etp_p_pooled": float(r["pooled"].pvalues["is_etp"]),
        "r2_within_two_way": float(fe.rsquared_within),
        # Effects relative to the outcome mean (two-way FE; earnings dummy: 0 -> 1;
        # continuous regressors: one within-stock SD; ETP: pooled OLS coefficient).
        "relative_to_mean_two_way": {
            "earn_week": float(fe.params["earn_week"] / d["ovn_share"].mean()),
            **{k: float(v / d["ovn_share"].mean()) for k, v in std_eff.items()
               if k != "earn_week"},
        },
        "etp_pooled_relative_to_mean": float(r["pooled"].params["is_etp"]
                                             / d["ovn_share"].mean()),
        "share_of_outcome_sum_top_0p1pct": float(
            d["ovn_share"].nlargest(max(1, len(d) // 1000)).sum() / d["ovn_share"].sum()),
        "diagnostics": {t["model"].iloc[0]: t.set_index("term")[["coef", "p"]].to_dict("index")
                        for t in d_tidies},
    }
    save_json(summary, "a2_summary")
    log.info("A2 done:\n%s", md)
    return summary

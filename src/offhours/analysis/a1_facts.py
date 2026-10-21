"""A1. Stylized facts on overnight ATS volume and reconciliation to the SEC staff memo.

All market-level facts use NMS Tier 1 + Tier 2 (Tier 2 is most of overnight share volume) and
are restricted to weeks for which both tiers are published (Tier 2 has a 4-week delay, Tier 1 a
2-week delay). Denominator: Cboe consolidated NMS volume (data/cboe.py), summed over the trading
days of each FINRA week. Numerator: overnight-ATS volume only; non-ATS overnight volume is not
public by session.

Outputs (reports/tables/):
  a1_weekly.csv            week-level series
  a1_venue_shares.csv      venue market shares of overnight-ATS volume by quarter
  a1_tier_coverage.csv     Tier 1 share of overnight-ATS shares and dollars, by venue and period
  a1_summary.json          headline numbers for the note
  a1_reconciliation.csv    memo target, our comparable figure, gap, tolerance
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from offhours import measures, store
from offhours.analysis.common import complete_weeks_in_month, save_json, save_table, week_start
from offhours.config import load_yaml, overnight_mpids

log = logging.getLogger(__name__)


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "ovn": store.read("ats_overnight"),
        "venue": store.read("ats_venue"),
        "sym": store.read("symbols_overnight"),
        "nms": store.read("nms_volume_daily"),
        "px": store.read("prices_daily"),
        "uni": store.read("universe"),
    }


def both_tier_weeks(venue: pd.DataFrame) -> pd.Series:
    """Weeks with venue totals published for both T1 and T2."""
    tiers = venue.groupby("week")["tier"].nunique()
    return pd.Series(sorted(tiers[tiers == 2].index))


def nms_weekly(nms: pd.DataFrame) -> pd.DataFrame:
    w = nms.assign(week=week_start(nms["date"])).groupby("week")
    return pd.DataFrame({"nms_shares_w": w["nms_shares"].sum(),
                         "nms_notional_w": w["nms_notional"].sum(),
                         "n_days": w["date"].count()})


def weekly_series(d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    weeks = set(both_tier_weeks(d["venue"]))
    ovn = d["ovn"][d["ovn"]["week"].isin(weeks)]
    ven = d["venue"][d["venue"]["week"].isin(weeks)]

    by_venue = ovn.pivot_table(index="week", columns=["tier", "mpid"], values="shares",
                               aggfunc="sum", fill_value=0)
    by_venue.columns = [f"shares_{t}_{m}" for t, m in by_venue.columns]
    out = by_venue.join(nms_weekly(d["nms"]), how="left")
    g = ovn.groupby("week")
    out["ovn_shares"] = g["shares"].sum()
    out["ovn_notional"] = g["notional"].sum()
    out["ovn_shares_T1"] = ovn[ovn["tier"] == "T1"].groupby("week")["shares"].sum()
    out["ovn_symbols"] = ovn[ovn["shares"] > 0].groupby("week")["symbol"].nunique()
    out["ovn_adv"] = out["ovn_shares"] / out["n_days"]
    out["ovn_share_of_nms"] = out["ovn_shares"] / out["nms_shares_w"]
    out["ovn_dollar_share_of_nms"] = out["ovn_notional"] / out["nms_notional_w"]
    out["t1_share_of_ovn"] = out["ovn_shares_T1"] / out["ovn_shares"]

    out["all_ats_shares"] = ven.groupby("week")["shares"].sum()
    out["ovn_share_of_all_ats"] = out["ovn_shares"] / out["all_ats_shares"]

    sym = ovn.groupby(["week", "symbol"])["shares"].sum()
    by_week = sym.groupby(level="week")
    out["top10_share"] = by_week.apply(lambda v: measures.top_k_share(v, 10))
    out["top100_share"] = by_week.apply(lambda v: measures.top_k_share(v, 100))
    out["hhi_symbols"] = by_week.apply(measures.herfindahl)

    etp = set(d["sym"].loc[d["sym"]["is_etp"], "symbol"])
    out["etp_share_of_ovn"] = ovn[ovn["symbol"].isin(etp)].groupby("week")["shares"].sum() \
        / out["ovn_shares"]
    out["etp_dollar_share_of_ovn"] = ovn[ovn["symbol"].isin(etp)].groupby("week")[
        "notional"].sum() / out["ovn_notional"]
    return out.reset_index().rename(columns={"index": "week"}).sort_values("week")


def venue_shares(ovn: pd.DataFrame, weeks: set | None = None) -> pd.DataFrame:
    if weeks is not None:
        ovn = ovn[ovn["week"].isin(weeks)]
    q = ovn.assign(quarter=ovn["week"].dt.to_period("Q").astype(str))
    tab = q.pivot_table(index="quarter", columns="mpid", values="shares", aggfunc="sum",
                        fill_value=0)
    share = tab.div(tab.sum(axis=1), axis=0)
    share["total_shares"] = tab.sum(axis=1)
    return share.reset_index()


def tier_coverage(ovn: pd.DataFrame, weeks: pd.Series, month: str) -> pd.DataFrame:
    """Tier 1 share of overnight-ATS shares and dollars, by venue, for three periods."""
    periods = {
        "full sample (both-tier weeks)": set(weeks),
        f"{month} (complete weeks)": set(complete_weeks_in_month(weeks, month)),
        "last 13 both-tier weeks": set(weeks.iloc[-13:]),
    }
    rows = []
    for label, wk in periods.items():
        o = ovn[ovn["week"].isin(wk)]
        for venue, g in [*o.groupby("mpid"), ("ALL", o)]:
            t1 = g[g["tier"] == "T1"]
            rows.append({"period": label, "venue": venue, "weeks": len(wk),
                         "t1_share_of_shares": t1["shares"].sum() / g["shares"].sum(),
                         "t1_share_of_dollars": t1["notional"].sum() / g["notional"].sum(),
                         "shares_total": g["shares"].sum(), "dollars_total": g["notional"].sum()})
    return pd.DataFrame(rows)


def reconcile(d: dict[str, pd.DataFrame], weekly: pd.DataFrame) -> pd.DataFrame:
    """Comparable figures for each memo target (both tiers). See configs/reconciliation_targets."""
    t = load_yaml("reconciliation_targets")
    month = t["period"]["month"]
    not_repro = t.get("not_reproducible") or {}
    weeks = complete_weeks_in_month(weekly["week"], month)
    wk = weekly[weekly["week"].isin(weeks)]
    n_days = wk["n_days"].sum()
    ovn = d["ovn"][d["ovn"]["week"].isin(weeks)]
    rows = []

    def add(key, ours, target, tol_rel=None, tol_abs=None, note=""):
        if key in not_repro:
            rows.append({"target": key, "memo_value": target, "ours": np.nan, "gap": np.nan,
                         "gap_rel": np.nan, "tolerance_rel": tol_rel, "tolerance_abs": tol_abs,
                         "within_tolerance": False, "note": "not reproducible with public data"})
            return
        gap = ours - target
        rel = gap / target if target else np.nan
        ok = abs(rel) <= tol_rel if tol_rel is not None else abs(gap) <= tol_abs
        rows.append({"target": key, "memo_value": target, "ours": ours, "gap": gap,
                     "gap_rel": rel, "tolerance_rel": tol_rel, "tolerance_abs": tol_abs,
                     "within_tolerance": bool(ok), "note": note})

    tg = t["targets"]
    weeks_txt = f"{len(weeks)} complete weeks, {int(n_days)} trade dates, T1+T2"
    add("ats_adv_overnight", ovn["shares"].sum() / n_days, tg["ats_adv_overnight"]["value"],
        tol_rel=tg["ats_adv_overnight"]["tolerance_rel"], note=weeks_txt)
    for m, v in tg["venue_adv"]["values"].items():
        add(f"venue_adv_{m}", ovn.loc[ovn["mpid"] == m, "shares"].sum() / n_days, v,
            tol_rel=tg["venue_adv"]["tolerance_rel"], note=weeks_txt)
    add("ats_advt_overnight", ovn["notional"].sum() / n_days, tg["ats_advt_overnight"]["value"],
        tol_rel=tg["ats_advt_overnight"]["tolerance_rel"], note=weeks_txt)

    prev = f"{int(month[:4]) - 1}{month[4:]}"
    weeks_prev = complete_weeks_in_month(weekly["week"], prev)
    wp = weekly[weekly["week"].isin(weeks_prev)]
    if len(wp):
        adv_prev = wp["ovn_shares"].sum() / wp["n_days"].sum()
        add("ats_adv_yoy_growth", ovn["shares"].sum() / n_days / adv_prev - 1,
            tg["ats_adv_yoy_growth"]["value"], tol_abs=tg["ats_adv_yoy_growth"]["tolerance_abs"],
            note=f"base {prev}: {len(weeks_prev)} complete weeks, T1+T2")

    add("overnight_share_of_nms_volume", np.nan, tg["overnight_share_of_nms_volume"]["value"],
        tol_abs=tg["overnight_share_of_nms_volume"]["tolerance_abs"])
    add("top10_share_overnight", wk["top10_share"].mean(), tg["top10_share_overnight"]["value"],
        tol_abs=tg["top10_share_overnight"]["tolerance_abs"],
        note="weekly (not daily) top-10, ATS only, T1+T2")
    add("top100_share_overnight", wk["top100_share"].mean(),
        tg["top100_share_overnight"]["value"],
        tol_abs=tg["top100_share_overnight"]["tolerance_abs"],
        note="weekly (not daily) top-100, ATS only, T1+T2")
    add("top10_share_rth", np.nan, tg["top10_share_rth"]["value"],
        tol_abs=tg["top10_share_rth"]["tolerance_abs"])
    return pd.DataFrame(rows)


def summary(weekly: pd.DataFrame, venues: pd.DataFrame, cover: pd.DataFrame) -> dict:
    w = weekly.dropna(subset=["n_days"])
    first, last = w.head(13), w.tail(13)
    month = load_yaml("reconciliation_targets")["period"]["month"]
    m = w[w["week"].isin(complete_weeks_in_month(w["week"], month))]
    full = cover[cover["period"].str.startswith("full") & (cover["venue"] == "ALL")].iloc[0]
    return {
        "tiers": "NMS Tier 1 + Tier 2 (weeks with both tiers published)",
        "sample_first_week": w["week"].min().date().isoformat(),
        "sample_last_week": w["week"].max().date().isoformat(),
        "n_weeks": int(len(w)),
        "ovn_adv_first13w": float(first["ovn_shares"].sum() / first["n_days"].sum()),
        "ovn_adv_last13w": float(last["ovn_shares"].sum() / last["n_days"].sum()),
        "ovn_share_of_nms_first13w": float(first["ovn_shares"].sum()
                                           / first["nms_shares_w"].sum()),
        "ovn_share_of_nms_last13w": float(last["ovn_shares"].sum() / last["nms_shares_w"].sum()),
        "ovn_dollar_share_of_nms_last13w": float(last["ovn_notional"].sum()
                                                 / last["nms_notional_w"].sum()),
        # Descriptive only (not a reconciliation): ATS-only overnight share of Cboe NMS volume in
        # the memo month; the memo's 0.9% also includes non-ATS overnight volume.
        "ats_only_ovn_share_of_nms_recon_month": float(m["ovn_shares"].sum()
                                                       / m["nms_shares_w"].sum()),
        "top10_share_last13w": float(last["top10_share"].mean()),
        "top100_share_last13w": float(last["top100_share"].mean()),
        "hhi_last13w": float(last["hhi_symbols"].mean()),
        "etp_share_of_ovn_last13w": float((last["etp_share_of_ovn"] * last["ovn_shares"]).sum()
                                          / last["ovn_shares"].sum()),
        "ovn_symbols_last13w_mean": float(last["ovn_symbols"].mean()),
        "ovn_share_of_all_ats_last13w": float(last["ovn_shares"].sum()
                                              / last["all_ats_shares"].sum()),
        "t1_share_of_ovn_shares_full": float(full["t1_share_of_shares"]),
        "t1_share_of_ovn_dollars_full": float(full["t1_share_of_dollars"]),
        "venue_shares_last_quarter": venues.iloc[-1].drop("quarter").to_dict(),
        "last_quarter": venues.iloc[-1]["quarter"],
        "nms_volume_source": "Cboe Exchange, Inc., U.S. equities historical market volume",
    }


def run() -> None:
    d = load_inputs()
    weekly = weekly_series(d)
    save_table(weekly, "a1_weekly")
    weeks = both_tier_weeks(d["venue"])
    venues = venue_shares(d["ovn"], set(weeks))
    save_table(venues, "a1_venue_shares")
    month = load_yaml("reconciliation_targets")["period"]["month"]
    cover = tier_coverage(d["ovn"][d["ovn"]["mpid"].isin(overnight_mpids())], weeks, month)
    save_table(cover, "a1_tier_coverage")
    rec = reconcile(d, weekly)
    save_table(rec, "a1_reconciliation")
    save_json(summary(weekly, venues, cover), "a1_summary")
    from offhours import figures

    figures.a1_figures(weekly, venues)
    log.info("A1 reconciliation:\n%s", rec.to_string())

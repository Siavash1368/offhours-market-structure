"""Validate Yahoo's earnings timing flags (after close / before open) against returns.

For an announcement on trading day t the flag decides which night carries the news:

    after close (AMC):  news night  = t -> t+1,  r_n(t+1) = ln(Open_{t+1} / Close_t)
                        other night = t-1 -> t,  r_n(t)   = ln(Open_t / Close_{t-1})
    before open (BMO):  news night  = t-1 -> t;  other night = t -> t+1

Primary test (symmetric, compares like with like): the flag CONTRADICTS the returns when
|other night| > |news night|. Ratio R = |news night| / |other night|; R > 2 is "clearly
consistent", R < 1/2 "clearly contradicting", between them "ambiguous".

Also reported (the literal form of the request):
    AMC: |r_n(t+1)| > |r_d(t)|, with r_d(t) = ln(Close_t / Open_t), the session before the news.
    BMO: |r_d(t)| > |r_n(t+1)|, the session after the open vs the following night. This is a
         weak test: BMO news is mostly priced in the night into t, so it is shown for
         completeness only.

Rule applied before A3 (config earnings.drop_contradicting): AMC events that contradict their
flag under the primary test are DROPPED, not reclassified. Moving an event to the other night
because its returns look that way would select events on the variables being studied. Dropping
also selects on |r_n|, so A3 is re-estimated on the unfiltered events (robustness R5).
Limitations: on low-news announcements both nights are noise, so some "contradictions" are
chance; the share among events with a clear move (max of the two nights above its stock's
typical night) is reported separately.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from offhours import store
from offhours.analysis.common import save_json, save_table

log = logging.getLogger(__name__)


def event_returns(px: pd.DataFrame, ern: pd.DataFrame) -> pd.DataFrame:
    """Per announcement (ticker, t, timing): r_n(t), r_d(t), r_n(t+1), r_d(t+1), r_d(t-1)."""
    d = px.sort_values(["ticker", "date"])[["ticker", "date", "r_night", "r_day"]].copy()
    g = d.groupby("ticker")
    d["rn_next"] = g["r_night"].shift(-1)
    d["rd_prev"] = g["r_day"].shift(1)
    d["typical_night"] = g["r_night"].transform(lambda s: s.abs().median())
    e = ern[ern["timing"].isin(["after_close", "before_open"])][["ticker", "date", "timing"]]
    out = e.merge(d.rename(columns={"date": "t"}), left_on=["ticker", "date"],
                  right_on=["ticker", "t"], how="inner").drop(columns="date")
    out = out.rename(columns={"r_night": "rn_t", "r_day": "rd_t"})
    return out.dropna(subset=["rn_t", "rd_t", "rn_next"])


def classify(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.copy()
    amc = ev["timing"] == "after_close"
    ev["news_night"] = np.where(amc, ev["rn_next"], ev["rn_t"]).astype(float)
    ev["other_night"] = np.where(amc, ev["rn_t"], ev["rn_next"]).astype(float)
    ev["ratio"] = ev["news_night"].abs() / ev["other_night"].abs().replace(0, np.nan)
    ev["contradicts"] = ev["other_night"].abs() > ev["news_night"].abs()
    ev["class"] = np.select([ev["ratio"] > 2, ev["ratio"] < 0.5], ["clear_consistent",
                            "clear_contradiction"], "ambiguous")
    big = np.maximum(ev["news_night"].abs(), ev["other_night"].abs())
    ev["clear_move"] = big > 3 * ev["typical_night"]
    # Literal tests.
    ev["literal_ok"] = np.where(amc, ev["rn_next"].abs() > ev["rd_t"].abs(),
                                ev["rd_t"].abs() > ev["rn_next"].abs())
    return ev


def summarize(ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for timing, g in ev.groupby("timing"):
        for subset, s in (("all", g), ("clear move", g[g["clear_move"]])):
            rows.append({
                "timing": timing, "subset": subset, "events": len(s),
                "share_contradicting": s["contradicts"].mean(),
                "share_clear_contradiction": (s["class"] == "clear_contradiction").mean(),
                "share_clear_consistent": (s["class"] == "clear_consistent").mean(),
                "median_abs_news_night": s["news_night"].abs().median(),
                "median_abs_other_night": s["other_night"].abs().median(),
                "share_failing_literal_test": 1 - s["literal_ok"].mean(),
            })
    return pd.DataFrame(rows)


def run(start: str | None = None) -> dict:
    px = store.read("prices_daily")
    ern = store.read("earnings")
    ev = classify(event_returns(px, ern))
    if start:
        ev = ev[ev["t"] >= start]
    summ = summarize(ev)
    save_table(summ, "earnings_timing_check")
    save_table(ev.loc[ev["contradicts"], ["ticker", "t", "timing", "news_night", "other_night",
                                          "ratio", "class"]].assign(t=lambda d: d["t"].dt.date),
               "earnings_timing_contradictions")
    ev[["ticker", "t", "timing", "contradicts", "class", "clear_move"]].to_parquet(
        store.PROCESSED / "earnings_timing_validated.parquet", index=False)
    amc = ev[ev["timing"] == "after_close"]
    out = {
        "events_checked": int(len(ev)),
        "amc_events": int(len(amc)),
        "amc_share_contradicting": float(amc["contradicts"].mean()),
        "amc_dropped_for_a3": int(amc["contradicts"].sum()),
        "bmo_share_contradicting": float(ev.loc[ev["timing"] == "before_open",
                                                "contradicts"].mean()),
        "rule": "Drop AMC events with |night t-1->t| > |night t->t+1| from A3; no "
                "reclassification; A3 also reported unfiltered (R5).",
        "table": "reports/tables/earnings_timing_check.csv",
    }
    save_json(out, "earnings_timing_summary")
    log.info("earnings timing check:\n%s", summ.to_string())
    return out

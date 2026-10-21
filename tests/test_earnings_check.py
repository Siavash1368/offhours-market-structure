"""Earnings timing-flag validation on hand-made returns."""

import pandas as pd

from offhours.analysis import earnings_check as ec


def _px(nights, days):
    d = pd.bdate_range("2024-01-02", periods=len(nights))
    return pd.DataFrame({"ticker": "X", "date": d, "r_night": nights, "r_day": days})


def test_after_close_consistent_and_contradicting():
    # Day index 2 is t. Night into t (index 2) small, night after t (index 3) large.
    px = _px([0.001, 0.002, 0.003, 0.08, 0.001], [0.004, 0.005, 0.006, 0.01, 0.002])
    t = px["date"].iloc[2]
    ern = pd.DataFrame({"ticker": ["X"], "date": [t], "timing": ["after_close"]})
    ev = ec.classify(ec.event_returns(px, ern))
    assert not ev["contradicts"].iloc[0]
    assert ev["class"].iloc[0] == "clear_consistent"
    assert ev["literal_ok"].iloc[0]  # |0.08| > |day t 0.006|

    # Same returns flagged before-open: the news night would be t-1 -> t (0.003) -> contradicts.
    ern["timing"] = "before_open"
    ev = ec.classify(ec.event_returns(px, ern))
    assert ev["contradicts"].iloc[0]
    assert ev["class"].iloc[0] == "clear_contradiction"


def test_summary_shares():
    px = _px([0.0, 0.01, 0.05, 0.001, 0.0, 0.0], [0.0] * 6)
    d = px["date"]
    ern = pd.DataFrame({"ticker": "X", "date": [d.iloc[1], d.iloc[3]],
                        "timing": ["after_close", "after_close"]})
    ev = ec.classify(ec.event_returns(px, ern))
    # Event at index 1: news night idx2 (0.05) vs other idx1 (0.01) -> consistent.
    # Event at index 3: news night idx4 (0.0) vs other idx3 (0.001) -> contradicts.
    assert list(ev["contradicts"]) == [False, True]
    s = ec.summarize(ev)
    assert s.loc[s["subset"] == "all", "share_contradicting"].iloc[0] == 0.5

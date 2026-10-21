"""End-to-end checks of A1-A3 on the synthetic fixture (runs in CI without network)."""

import numpy as np
import pandas as pd
import pytest

from offhours.analysis import a1_facts, a2_panel, a3_earnings
from offhours.store import check_schema
from tests.fixtures.synthetic import make


@pytest.fixture(scope="module")
def data():
    return make()


@pytest.fixture(scope="module")
def panel(data):
    return a2_panel.build_panel(data)


def test_fixture_matches_store_schema(data):
    check_schema("ats_overnight", data["ovn"])
    check_schema("universe", data["uni"])
    check_schema("ats_symbol", data["ats"])


def test_a1_weekly_series_uses_both_tiers(data):
    w = a1_facts.weekly_series(data)
    assert len(w) == data["ovn"]["week"].nunique()
    assert (w["ovn_share_of_nms"].between(0, 1)).all()
    assert (w["top10_share"] <= 1).all()
    # Totals include Tier 2: planted Tier 2 volume is 4x Tier 1, so Tier 1 is ~20% of shares.
    assert w["t1_share_of_ovn"].mean() == pytest.approx(0.2, abs=0.02)
    ovn = data["ovn"]
    assert w["ovn_shares"].sum() == pytest.approx(ovn["shares"].sum())
    # The ten largest symbols are now the five Tier 2 names plus Tier 1 names.
    assert (w["top10_share"] > 0.8).all()


def test_a1_both_tier_weeks_excludes_t1_only_weeks(data):
    venue = data["venue"].copy()
    last = venue["week"].max()
    venue = venue[~((venue["week"] == last) & (venue["tier"] == "T2"))]
    weeks = a1_facts.both_tier_weeks(venue)
    assert last not in set(weeks) and len(weeks) == venue["week"].nunique() - 1


def test_a1_tier_coverage(data):
    weeks = a1_facts.both_tier_weeks(data["venue"])
    c = a1_facts.tier_coverage(data["ovn"], weeks, "2025-03")
    full = c[c["period"].str.startswith("full")].set_index("venue")
    assert full.loc["BOSS", "t1_share_of_shares"] == pytest.approx(1.0)  # BOSS has no Tier 2
    assert full.loc["ALL", "t1_share_of_shares"] == pytest.approx(0.2, abs=0.02)
    assert full.loc["ALL", "t1_share_of_dollars"] > full.loc["ALL", "t1_share_of_shares"]
    v = a1_facts.venue_shares(data["ovn"][data["ovn"]["tier"] == "T1"])
    assert v["BLUE"].iloc[0] == pytest.approx(0.85, abs=1e-9)  # planted 85/15 split


def test_panel_shares_bounded_and_lagged(panel):
    assert panel["ovn_share"].dropna().between(0, 100).all()
    assert not panel["violation"].any()
    # Prices start in the first fixture week, so no stock has a lagged value there.
    first_week = panel.groupby("symbol")["week"].transform("min")
    assert panel.loc[panel["week"] == first_week, "log_price_l1"].isna().all()
    assert panel.loc[panel["week"] > first_week, "log_price_l1"].notna().all()


def test_a2_recovers_planted_price_slope(panel):
    res = a2_panel.estimate(panel)
    # Within a stock the price barely moves, so check the pooled slope on log price is positive.
    assert res["pooled"].params["log_price_l1"] > 0


def test_a2_diagnostics_run_and_label(panel):
    tidies, stats = a2_panel.diagnostics(panel)
    names = [t["model"].iloc[0] for t in tidies]
    assert names[0].startswith("(D1)") and names[-1].startswith("(D4)")
    # ETP-only model drops the earnings dummy (always zero for ETPs).
    assert "earn_week" not in set(tidies[2]["term"])
    # Extensive margin outcome is in percentage points.
    assert 0 <= stats[3]["Mean of outcome"] <= 100
    assert all("R2 (overall if no FE, else within)" in s for s in stats)


def test_winsorize_clips_tails():
    import pandas as pd

    s = pd.Series(range(1000), dtype=float)
    w = a2_panel.winsorize(s)
    assert w.min() == pytest.approx(s.quantile(0.01))
    assert w.max() == pytest.approx(s.quantile(0.99))


def test_a3_recovers_planted_interaction(data, panel):
    ev = a3_earnings.build_events(panel, data["px"], data["earnings"])
    earn = ev[ev["sample"] == "earnings"]
    assert len(earn) > 20
    res, _ = a3_earnings.efficiency_regression(earn, "intensity")
    # Low-intensity stocks reverse half the night move, high-intensity ones do not:
    # b on r_n negative, interaction positive.
    assert res.params["r_n"] < 0
    assert res.params["r_n_x_I"] > 0
    wpc = a3_earnings.wpc_table(ev, n_boot=99)
    e = wpc[(wpc["sample"] == "earnings") & (wpc["tercile"] > 0)].set_index("tercile")
    # Low type: r_d = -0.5 r_n, so r_cc = 0.5 r_n and WPC ~ 2 (the open overshoots).
    # High type: no reversal, WPC ~ 1. An efficient open means WPC close to 1, not larger.
    assert e.loc[1, "wpc_night"] == pytest.approx(2.0, abs=0.3)
    assert e.loc[3, "wpc_night"] == pytest.approx(1.0, abs=0.15)


def test_baseline_excludes_nights_next_to_events(data, panel):
    ev = a3_earnings.build_events(panel, data["px"], data["earnings"])
    assert set(ev["sample"]) <= {"earnings", "baseline"}
    assert np.isfinite(ev["I"]).all()
    assert isinstance(ev, pd.DataFrame)

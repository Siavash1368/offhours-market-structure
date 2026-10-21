"""Unit tests for offhours.measures on small examples that can be checked by hand."""

import numpy as np
import pandas as pd
import pytest

from offhours import measures


def test_herfindahl_bounds():
    assert measures.herfindahl(pd.Series([1, 1, 1, 1])) == pytest.approx(0.25)
    assert measures.herfindahl(pd.Series([5, 0, 0])) == pytest.approx(1.0)
    # shares 0.5, 0.3, 0.2 -> 0.25 + 0.09 + 0.04
    assert measures.herfindahl(pd.Series([50, 30, 20])) == pytest.approx(0.38)


def test_top_k_share():
    v = pd.Series([10, 40, 20, 30])
    assert measures.top_k_share(v, 1) == pytest.approx(0.4)
    assert measures.top_k_share(v, 2) == pytest.approx(0.7)
    assert measures.top_k_share(v, 10) == pytest.approx(1.0)


def test_wpc_all_at_open_is_one():
    # Whole close-to-close move happens overnight -> WPC = 1.
    r_total = pd.Series([0.05, -0.02, 0.01])
    assert measures.weighted_price_contribution(r_total, r_total) == pytest.approx(1.0)


def test_wpc_hand_example():
    # Event 1: night +0.04, total +0.05. Event 2: night -0.03, total -0.01 (open overshoots).
    # WPC = [sign(+.05)*.04 + sign(-.01)*(-.03)] / (.05 + .01) = (.04 + .03) / .06
    r_night = pd.Series([0.04, -0.03])
    r_total = pd.Series([0.05, -0.01])
    got = measures.weighted_price_contribution(r_night, r_total)
    assert got == pytest.approx(0.07 / 0.06)


def test_wpc_equals_weighted_ratio_definition():
    rng = np.random.default_rng(1)
    r_n = pd.Series(rng.normal(0, 0.02, 200))
    r_t = r_n + pd.Series(rng.normal(0, 0.02, 200))
    w = r_t.abs() / r_t.abs().sum()
    direct = float((w * (r_n / r_t)).sum())
    assert measures.weighted_price_contribution(r_n, r_t) == pytest.approx(direct)


def test_wpc_by_group():
    r_n = pd.Series([0.02, 0.01, -0.01, 0.03])
    r_t = pd.Series([0.02, 0.02, -0.02, 0.03])
    g = pd.Series(["a", "a", "b", "b"])
    out = measures.weighted_price_contribution(r_n, r_t, g)
    assert out["a"] == pytest.approx(0.03 / 0.04)
    assert out["b"] == pytest.approx(0.04 / 0.05)


def test_bootstrap_wpc_interval_contains_estimate():
    rng = np.random.default_rng(2)
    n = 300
    r_n = pd.Series(rng.normal(0, 0.02, n))
    r_t = r_n + pd.Series(rng.normal(0, 0.01, n))
    c = pd.Series(np.repeat(np.arange(30), 10))
    est, lo, hi = measures.bootstrap_wpc(r_n, r_t, c, n_boot=200)
    assert lo <= est <= hi
    assert est == pytest.approx(measures.weighted_price_contribution(r_n, r_t))


def test_unadjust_volume_and_price_for_a_split():
    # 10-for-1 split effective on day 3: Yahoo shows pre-split volume x10 and price /10.
    df = pd.DataFrame({
        "ticker": ["X"] * 4,
        "date": pd.date_range("2024-06-06", periods=4),
        "volume": [1000.0, 2000.0, 300.0, 400.0],
        "close": [12.0, 12.5, 12.2, 12.4],
        "split": [0.0, 0.0, 10.0, 0.0],
    })
    np.testing.assert_allclose(measures.unadjust_volume(df), [100, 200, 300, 400])
    np.testing.assert_allclose(measures.unadjust_price(df), [120, 125, 12.2, 12.4])


def test_night_day_returns_add_up():
    df = pd.DataFrame({
        "ticker": ["X"] * 3,
        "date": pd.date_range("2024-01-02", periods=3),
        "open": [100.0, 103.0, 101.0],
        "close": [102.0, 104.0, 99.0],
    })
    out = measures.night_day_returns(df)
    assert out["r_night"].iloc[1] == pytest.approx(np.log(103 / 102))
    assert out["r_day"].iloc[1] == pytest.approx(np.log(104 / 103))
    assert out["r_cc"].iloc[2] == pytest.approx(np.log(99 / 104))
    assert np.isnan(out["r_night"].iloc[0])


def test_overnight_share_drops_impossible_values():
    s = measures.overnight_share(pd.Series([10, 50, 5]), pd.Series([100, 40, 0]))
    assert s.iloc[0] == pytest.approx(0.1)
    assert np.isnan(s.iloc[1]) and np.isnan(s.iloc[2])


def test_wpc_gap_change_recovers_known_values():
    # Group 1: open captures all (WPC 1). Group 3: night = 2x total (WPC 2). Gap = 1 in both
    # periods, so the change is 0; doubling group 3's night in period b raises the gap by 2.
    def make(mult3):
        rows = []
        for stock in range(20):
            g = 1 if stock < 10 else 3
            for e in range(5):
                t = 0.01 * (1 + e) * (1 if e % 2 else -1)
                w = t if g == 1 else mult3 * t
                rows.append({"r_w": w, "r_t": t, "cluster": stock, "group": g})
        return pd.DataFrame(rows)

    est, lo, hi = measures.wpc_gap_change(make(2.0), make(2.0), n_boot=99)
    assert est == pytest.approx(0.0) and lo <= 0 <= hi
    est, _, _ = measures.wpc_gap_change(make(2.0), make(4.0), n_boot=99)
    assert est == pytest.approx(2.0)


def test_realized_volatility():
    assert measures.realized_volatility(pd.Series([0.03, -0.04])) == pytest.approx(0.05)

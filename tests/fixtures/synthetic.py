"""Tiny synthetic dataset with the same schema as the Parquet store (no network needed).

30 stocks + 4 ETPs, 30 FINRA weeks from 2025-01-06, daily prices with known structure:
  - overnight share rises with log price (planted A2 slope),
  - after-close earnings every 8 weeks per stock,
  - for high-intensity stocks the next-day return does not reverse the night return; for
    low-intensity stocks it reverses half of it (planted A3 interaction).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_STOCKS, N_ETP, N_WEEKS = 30, 4, 30
START = pd.Timestamp("2025-01-06")


def make(seed: int = 0) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    symbols = [f"S{i:02d}" for i in range(N_STOCKS)] + [f"E{i}" for i in range(N_ETP)]
    is_etp = [s.startswith("E") for s in symbols]
    uni = pd.DataFrame({"symbol": symbols, "ticker": symbols, "issue_name": symbols,
                        "is_etp": is_etp, "etp_source": "synthetic"})

    days = pd.bdate_range(START, periods=N_WEEKS * 5)
    base_price = np.exp(rng.uniform(np.log(10), np.log(500), len(symbols)))
    # Intensity type: stock i's overnight share grows with its index.
    ovn_rate = np.linspace(0.001, 0.03, len(symbols))
    high_type = ovn_rate > np.median(ovn_rate)

    px_rows, ern_rows = [], []
    for i, s in enumerate(symbols):
        close_prev = base_price[i]
        for k, d in enumerate(days):
            earn_day = (not is_etp[i]) and (k % 40 == (i % 40)) and k > 25
            sd = 0.04 if earn_day else 0.01
            r_n = rng.normal(0, sd)
            reversal = 0.0 if high_type[i] else -0.5
            r_d = reversal * r_n + rng.normal(0, 0.005) if earn_day else rng.normal(0, 0.01)
            op = close_prev * np.exp(r_n)
            cl = op * np.exp(r_d)
            px_rows.append({"ticker": s, "date": d, "open": op, "high": max(op, cl),
                            "low": min(op, cl), "close": cl, "adj_close": cl,
                            "volume": float(rng.integers(1e6, 5e6)), "dividends": 0.0,
                            "split": 0.0})
            close_prev = cl
            if earn_day:
                # Announcement after the close of the previous trading day.
                ern_rows.append({"ticker": s, "date": days[k - 1],
                                 "timestamp": days[k - 1] + pd.Timedelta(hours=16, minutes=5),
                                 "timing": "after_close"})
    px = pd.DataFrame(px_rows)
    px["volume_raw"] = px["volume"]
    px["close_raw"] = px["close"]
    from offhours.measures import night_day_returns

    px = night_day_returns(px)

    weeks = pd.date_range(START, periods=N_WEEKS, freq="W-MON")
    vol_w = (px.assign(week=px["date"] - pd.to_timedelta(px["date"].dt.weekday, unit="D"))
             .groupby(["ticker", "week"])["volume"].sum())
    ovn_rows, ats_rows = [], []
    for i, s in enumerate(symbols):
        for w in weeks:
            tot = vol_w[(s, w)]
            # Planted A2 relation: share rises with log price.
            share = ovn_rate[i] * (1 + 0.2 * (np.log(base_price[i]) - 4)) * rng.uniform(0.8, 1.2)
            share = max(share, 0.0)
            for m, frac in (("BLUE", 0.85), ("BOSS", 0.15)):
                sh = share * tot * frac
                ovn_rows.append({"week": w, "tier": "T1", "mpid": m, "symbol": s,
                                 "issue_name": s, "shares": sh, "trades": sh / 50,
                                 "notional": sh * base_price[i]})
            ats_rows.append({"week": w, "symbol": s, "issue_name": s, "shares": 0.1 * tot,
                             "trades": tot / 500, "notional": 0.1 * tot * base_price[i]})
    # Tier 2: five small stocks traded only on BLUE, with 4x the Tier 1 overnight share count.
    t2_total = sum(r["shares"] for r in ovn_rows) / N_WEEKS * 4 / 5
    for j in range(5):
        for w in weeks:
            sh = t2_total * rng.uniform(0.9, 1.1)
            ovn_rows.append({"week": w, "tier": "T2", "mpid": "BLUE", "symbol": f"T2_{j}",
                             "issue_name": f"T2_{j}", "shares": sh, "trades": sh / 50,
                             "notional": sh * 2.0})
    ovn = pd.DataFrame(ovn_rows)
    ats = pd.DataFrame(ats_rows)
    sym = (ovn.groupby("symbol", as_index=False).agg(issue_name=("issue_name", "last"),
                                                       tier=("tier", "last")))
    sym["is_etp"] = sym["symbol"].str.startswith("E")
    sym["etp_source"] = "synthetic"
    nms = px.groupby("date", as_index=False).agg(nms_shares=("volume", "sum"))
    nms["nms_shares"] *= 3  # NMS volume larger than the fixture's priced stocks
    nms["nms_notional"] = nms["nms_shares"] * 50.0
    rs = px[["ticker", "date", "volume"]].rename(columns={"ticker": "symbol"})
    rs["total_volume"] = 0.4 * rs["volume"]
    rs["short_volume"] = rs["total_volume"] * rng.uniform(0.3, 0.6, len(rs))
    rs = rs.drop(columns="volume")
    ven = (ovn.groupby(["week", "tier", "mpid"], as_index=False)[["shares", "trades", "notional"]]
           .sum().assign(participant_name=lambda d: d["mpid"]))
    return {"uni": uni, "px": px, "ovn": ovn, "ats": ats, "regsho": rs,
            "earnings": pd.DataFrame(ern_rows), "venue": ven, "high_type": high_type,
            "symbols": symbols, "sym": sym, "nms": nms}

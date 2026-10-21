"""Write reports/data_audit.md: row counts, coverage, missing weeks, venues, venue hours."""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from offhours import store
from offhours.analysis.common import week_start
from offhours.config import PROCESSED, RAW, REPORTS, load_yaml


def _missing_weeks(weeks: pd.Series, start: str, end: str) -> list[str]:
    expected = pd.date_range(start, end, freq="W-MON")
    have = set(pd.to_datetime(weeks.unique()))
    return [w.date().isoformat() for w in expected if w not in have]


def write_audit() -> dict:
    sample = json.loads((PROCESSED / "sample.json").read_text())
    s, e = sample["start_week"], sample["end_week"]
    ovn, ats, otc = store.read("ats_overnight"), store.read("ats_symbol"), store.read("otc_symbol")
    ven, uni = store.read("ats_venue"), store.read("universe")
    rs, px, er = store.read("regsho_daily"), store.read("prices_daily"), store.read("earnings")

    lines = ["# Data audit", "", f"Generated {dt.date.today().isoformat()} by "
             "`src/offhours/analysis/audit.py` from the Parquet store.", "",
             f"Sample weeks: **{s}** to **{e}** (FINRA week-start Mondays; latest NMS Tier 1 week "
             "published at build time).", "", "## Tables", "",
             "| Table | Rows | First | Last | Symbols/tickers |", "|---|---|---|---|---|"]
    info = {}
    for name, df, dcol, scol in [
        ("ats_overnight", ovn, "week", "symbol"), ("ats_symbol (T1)", ats, "week", "symbol"),
        ("otc_symbol (T1)", otc, "week", "symbol"), ("ats_venue", ven, "week", "mpid"),
        ("regsho_daily", rs, "date", "symbol"), ("prices_daily", px, "date", "ticker"),
        ("earnings", er, "date", "ticker"), ("universe", uni, None, "symbol"),
    ]:
        first = df[dcol].min().date() if dcol else ""
        last = df[dcol].max().date() if dcol else ""
        lines.append(f"| {name} | {len(df):,} | {first} | {last} | {df[scol].nunique():,} |")
        info[name] = len(df)

    lines += ["", "## Missing weeks", ""]
    for tier in ("T1", "T2"):
        t = ven[ven["tier"] == tier]
        end = e if tier == "T1" else t["week"].max().date().isoformat()
        miss = _missing_weeks(t["week"], s, end)
        lines.append(f"- {tier} venue totals (ATS_W_FIRM), {s} to {end}: "
                     f"{len(miss)} missing {miss[:10]}")
    for m in sorted(ovn["mpid"].unique()):
        w = ovn.loc[(ovn["mpid"] == m) & (ovn["tier"] == "T1"), "week"]
        lines.append(f"- {m} (T1): first week {w.min().date()}, last {w.max().date()}, "
                     f"{w.nunique()} weeks with data, "
                     f"{len(_missing_weeks(w, w.min().date().isoformat(), e))} gaps after first")
    rs_days = rs["date"].dt.normalize().unique()
    nofile = (RAW / "regsho" / "_no_file_dates.txt")
    lines.append(f"- Reg SHO: {len(rs_days):,} trading days; weekdays with no file "
                 f"(holidays): {len(nofile.read_text().split()) if nofile.exists() else 0}")

    lines += ["", "## Venues found in the FINRA weekly file (Tier 1, sample period)", "",
              "| MPID | Participant name | Overnight venue | Sample shares (bn) |",
              "|---|---|---|---|"]
    venues_cfg = load_yaml("overnight_venues")["venues"]
    vt = (ven[ven["tier"] == "T1"].groupby(["mpid"])
          .agg(name=("participant_name", "last"), shares=("shares", "sum"))
          .sort_values("shares", ascending=False))
    for m, r in vt.iterrows():
        lines.append(f"| {m} | {r['name']} | {'yes' if m in venues_cfg else ''} | "
                     f"{r['shares'] / 1e9:,.2f} |")

    lines += ["", "## Overnight venues: operating hours (Form ATS-N)", "",
              "| MPID | Venue | Matching hours (ET) | Outside 8 pm-4 am | Source |",
              "|---|---|---|---|---|"]
    for m, v in venues_cfg.items():
        lines.append(f"| {m} | {v['name']} | {v['matching_hours_et']} | "
                     f"{v['outside_8pm_4am']} | {v['source']} |")

    # Symbol coverage: Tier 1 symbols with price data, earnings data, ETP source.
    have_px = set(px["ticker"])
    have_er = set(er["ticker"])
    common = uni[~uni["is_etp"]]
    lines += ["", "## Symbol coverage", "",
              f"- Tier 1 symbols in the sample: {len(uni):,} "
              f"({int(uni['is_etp'].sum()):,} ETPs, {len(common):,} other)",
              f"- ETP flag source: {uni['etp_source'].value_counts().to_dict()}",
              f"- With Yahoo price data: {uni['ticker'].isin(have_px).sum():,} "
              f"({uni['ticker'].isin(have_px).mean():.1%})",
              f"- Common stocks with Yahoo earnings dates: {common['ticker'].isin(have_er).sum():,}"
              f" ({common['ticker'].isin(have_er).mean():.1%})",
              f"- Earnings timing classes: {er['timing'].value_counts().to_dict()}"]
    t1_ovn = ovn[ovn["tier"] == "T1"]
    share_priced = t1_ovn.merge(uni[["symbol", "ticker"]], on="symbol")
    share_priced = share_priced.loc[share_priced["ticker"].isin(have_px), "shares"].sum()
    lines.append(f"- Share of Tier 1 overnight-venue volume in symbols with price data: "
                 f"{share_priced / t1_ovn['shares'].sum():.1%}")

    # Denominator test, summary (details in tables/a2_denominator_violations.csv after A2).
    pxw = px.assign(week=week_start(px["date"])).groupby(["ticker", "week"])["volume_raw"].sum()
    o = t1_ovn.merge(uni[["symbol", "ticker"]], on="symbol").groupby(["ticker", "week"])[
        "shares"].sum()
    j = pd.concat([o.rename("ovn"), pxw.rename("tot")], axis=1, join="inner")
    viol = j[j["ovn"] > j["tot"]]
    meta_path = PROCESSED / "store_meta.json"
    merged = (json.loads(meta_path.read_text())["merged_duplicate_rows"]
              if meta_path.exists() else {})
    so = store.read("symbols_overnight")
    nms = store.read("nms_volume_daily")
    lines += ["", "## Source quirks and other tables", "",
              f"- Rows sharing a table key in the FINRA files, merged by summing (store.py "
              f"`collapse_duplicates`): {merged}. Example: LND on BLUE, Tier 2, week of "
              "2024-07-01, two rows differing only in the encoding of the issue name.",
              f"- Overnight symbols, both tiers: {len(so):,} ({int(so['is_etp'].sum()):,} ETPs; "
              f"ETP flag source {so['etp_source'].value_counts().to_dict()}).",
              f"- Cboe consolidated NMS volume: {len(nms):,} trading days, "
              f"{nms['date'].min().date()} to {nms['date'].max().date()} "
              "(source: Cboe Exchange, Inc.)."]

    lines += ["", "## Denominator check", "",
              f"- Stock-weeks with overnight-venue shares and price data: {len(j):,}",
              f"- Overnight-venue shares exceed consolidated weekly volume: **{len(viol):,}** "
              f"({len(viol) / max(len(j), 1):.3%}); listed in "
              "`reports/tables/a2_denominator_violations.csv`",
              "", "Downloaded: FINRA weekly files and Yahoo data on the dates recorded in each "
              "cached file (`downloaded` field)."]
    (REPORTS / "data_audit.md").write_text("\n".join(lines) + "\n")
    info["denominator_violations"] = int(len(viol))
    info["stock_weeks_checked"] = int(len(j))
    return info

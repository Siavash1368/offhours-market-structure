"""Data-integrity and definition checks behind the reconciliation, written to
reports/tables/checks.json as {check_id: {"status": "pass"|"fail"|"info", ...evidence}}.

A reconciliation gap may be marked as explained (xfail) only if its entry in
configs/reconciliation_targets.yaml names a check here that has status "pass"
(tests/test_reconciliation.py enforces this).

Checks
  pull_complete_live      Live re-pull of every record for each overnight MPID, both tiers, for
                          the reconciliation month's weeks: rows == API record-total, and summed
                          symbol rows == the venue (ATS_W_FIRM) total, shares and notional.
  pull_complete_cached    Same identity for every cached overnight venue-week-tier; cached files
                          that carry a record-total must match it.
  week_convention         Each reconciliation week: trading days (SPY calendar), venues'
                          lastReportedDate, and whether the week lies wholly inside the month.
  tier_coverage           Tier 2 share of overnight-venue shares in the reconciliation month.
  window_bound            Whether the one trade date missing from complete weeks (e.g. Aug 31)
                          could close the ADV gap, bounding it by adjacent weekly averages.
  definitions             Side-by-side definitions (memo vs public weekly data); "info" only.
"""

from __future__ import annotations

import gzip
import json
import logging
from collections import defaultdict

import pandas as pd

from offhours.config import RAW, TABLES, load_yaml, overnight_mpids
from offhours.data import finra_ats

log = logging.getLogger(__name__)
CHECK_CACHE = RAW / "finra_checks"


def _live_records(week: str, tier: str, mpid: str) -> dict:
    """Every record for one venue-week-tier (all summary types), cached on first pull."""
    path = CHECK_CACHE / tier / week / f"ALL_{mpid}.json.gz"
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    rows, total = finra_ats.fetch_all({"weekStartDate": week, "tierIdentifier": tier,
                                       "MPID": mpid})
    payload = {"downloaded": pd.Timestamp.today().date().isoformat(), "record_total": total,
               "records": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    return payload


def month_weeks(month: str) -> tuple[list[str], list[str]]:
    """(complete weeks inside the month, weeks overlapping the month) as Monday ISO dates."""
    start = pd.Timestamp(f"{month}-01")
    end = start + pd.offsets.MonthEnd(0)
    mondays = pd.date_range(start - pd.Timedelta(days=6), end, freq="W-MON")
    overlap = [m for m in mondays if m + pd.Timedelta(days=4) >= start and m <= end]
    complete = [m for m in overlap if m >= start and m + pd.Timedelta(days=4) <= end]
    return [m.date().isoformat() for m in complete], [m.date().isoformat() for m in overlap]


def trading_days() -> pd.DatetimeIndex:
    spy = pd.read_parquet(RAW / "prices" / "SPY.parquet")
    return pd.DatetimeIndex(pd.to_datetime(spy["date"]).dt.tz_localize(None)).normalize()


def check_pull_complete_live(month: str) -> dict:
    _, weeks = month_weeks(month)
    rows = []
    for week in weeks:
        for tier in ("T1", "T2"):
            for m in overnight_mpids():
                p = _live_records(week, tier, m)
                by = defaultdict(lambda: [0, 0.0, 0])
                for r in p["records"]:
                    b = by[r["summaryTypeCode"]]
                    b[0] += r["totalWeeklyShareQuantity"] or 0
                    b[1] += r["totalNotionalSum"] or 0.0
                    b[2] += 1
                sym, firm = by.get("ATS_W_SMBL_FIRM", [0, 0.0, 0]), by.get("ATS_W_FIRM")
                rows.append({
                    "week": week, "tier": tier, "mpid": m, "rows": len(p["records"]),
                    "record_total": p["record_total"],
                    "types": sorted(by), "symbol_rows": sym[2],
                    "symbol_shares": sym[0], "firm_shares": firm[0] if firm else 0,
                    "symbol_notional": round(sym[1], 2),
                    "firm_notional": round(firm[1], 2) if firm else 0.0,
                })
    df = pd.DataFrame(rows)
    ok_rows = (df["rows"] == df["record_total"]).all()
    ok_sum = ((df["symbol_shares"] == df["firm_shares"]).all()
              and ((df["symbol_notional"] - df["firm_notional"]).abs() < 1.0).all())
    return {"status": "pass" if ok_rows and ok_sum else "fail",
            "rows_equal_record_total": bool(ok_rows), "symbol_sum_equals_venue_total":
            bool(ok_sum), "n_venue_weeks": len(df), "detail": df.to_dict(orient="records")}


def check_pull_complete_cached() -> dict:
    """Symbol rows sum to venue totals for every cached overnight venue-week-tier.

    Reads one snapshot of the file list (so a download running at the same time cannot make
    the two sides cover different weeks) and checks only week-tiers whose venue-total file is
    in the snapshot. A venue-week-tier with symbol rows but no venue total, or the reverse,
    counts as a mismatch.
    """
    mpids = set(overnight_mpids())
    sym_sum: dict[tuple, int] = defaultdict(int)
    ven_tot: dict[tuple, int] = {}
    mismatched_totals = 0
    files = sorted((RAW / "finra_ats").glob("*/*/*.json.gz"))
    weeks_with_firm = {(p.parent.parent.name, p.parent.name) for p in files
                       if p.name == "ATS_W_FIRM.json.gz"}
    checked = 0
    for path in files:
        tier, week = path.parent.parent.name, path.parent.name
        is_sym = path.name.startswith("ATS_W_SMBL_FIRM_")
        if (tier, week) not in weeks_with_firm or not (is_sym or path.name == "ATS_W_FIRM.json.gz"):
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            p = json.load(f)
        checked += 1
        if "record_total" in p and p["record_total"] != len(p["records"]):
            mismatched_totals += 1
        for r in p["records"]:
            if r["MPID"] not in mpids:
                continue
            key = (week, tier, r["MPID"])
            if is_sym:
                sym_sum[key] += r["totalWeeklyShareQuantity"] or 0
            else:
                ven_tot[key] = r["totalWeeklyShareQuantity"] or 0
    keys = set(sym_sum) | set(ven_tot)
    bad = [{"week": k[0], "tier": k[1], "mpid": k[2], "symbol_sum": sym_sum.get(k, 0),
            "venue_total": ven_tot.get(k, 0)} for k in sorted(keys)
           if sym_sum.get(k, 0) != ven_tot.get(k, 0)]
    return {"status": "pass" if not bad and mismatched_totals == 0 else "fail",
            "venue_week_tiers": len(keys), "sum_mismatches": len(bad),
            "files_checked": checked, "record_total_mismatches": mismatched_totals,
            "mismatch_examples": bad[:10]}


def check_week_convention(month: str) -> dict:
    complete, overlap = month_weeks(month)
    days = trading_days()
    in_month = days[days.strftime("%Y-%m") == month]
    rows = []
    for week in overlap:
        w = pd.Timestamp(week)
        n = int(((days >= w) & (days <= w + pd.Timedelta(days=4))).sum())
        last = {}
        for tier in ("T1", "T2"):
            for m in overnight_mpids():
                recs = _live_records(week, tier, m)["records"]
                firm = [r for r in recs if r["summaryTypeCode"] == "ATS_W_FIRM"]
                if firm:
                    last[f"{tier}_{m}"] = firm[0]["lastReportedDate"]
        rows.append({"week": week, "trading_days": n, "complete_in_month": week in complete,
                     "lastReportedDate": last})
    full = all(r["trading_days"] == 5 for r in rows if r["complete_in_month"])
    covered = sum(r["trading_days"] for r in rows if r["complete_in_month"])
    return {"status": "pass" if full else "fail", "month": month,
            "trading_days_in_month": int(len(in_month)),
            "trading_days_in_complete_weeks": covered, "weeks": rows,
            "convention": ("FINRA week = Monday-Friday trade dates. An overnight session is "
                           "reported for the next trade date (BOATS Form ATS-N Part III Item 21:"
                           " Sunday-night trades reported by 04:15 Monday), so a week holds the "
                           "Sunday-night to Thursday-night sessions. lastReportedDate is 'the "
                           "last time a firm sent an update' (API spec v0.4), so dates after "
                           "Friday mean later corrections, not later trades.")}


def check_tier_coverage(month: str) -> dict:
    complete, _ = month_weeks(month)
    tot = defaultdict(float)
    for week in complete:
        for tier in ("T1", "T2"):
            for m in overnight_mpids():
                for r in _live_records(week, tier, m)["records"]:
                    if r["summaryTypeCode"] == "ATS_W_FIRM":
                        tot[(tier, m)] += r["totalWeeklyShareQuantity"]
    per = {m: tot[("T2", m)] / max(tot[("T1", m)] + tot[("T2", m)], 1) for m in overnight_mpids()}
    all_t2 = sum(v for (t, _), v in tot.items() if t == "T2") / sum(tot.values())
    return {"status": "pass", "t2_share_of_shares": per, "t2_share_all_venues": all_t2,
            "note": "Reconciliation must sum T1 and T2; T1 alone understates overnight shares."}


def check_window_bound(month: str, weekly: dict[str, float], target: float,
                       tol_rel: float) -> dict:
    """Bound the month ADV if the missing trade dates traded at the min or max adjacent rate.

    weekly: {week: overnight shares per trade date} for overlapping weeks.
    """
    complete, overlap = month_weeks(month)
    days = trading_days()
    in_month = days[days.strftime("%Y-%m") == month]
    covered = [d for d in in_month if any(
        pd.Timestamp(w) <= d <= pd.Timestamp(w) + pd.Timedelta(days=4) for w in complete)]
    missing = len(in_month) - len(covered)
    base = sum(weekly[w] * int(((days >= pd.Timestamp(w))
                                & (days <= pd.Timestamp(w) + pd.Timedelta(days=4))).sum())
               for w in complete)
    rates = [weekly[w] for w in overlap if w in weekly]
    lo = (base + missing * min(rates)) / len(in_month)
    hi = (base + missing * max(rates)) / len(in_month)
    can_close = (hi >= target * (1 - tol_rel)) and (lo <= target * (1 + tol_rel))
    return {"status": "pass", "missing_trade_dates": missing, "adv_complete_weeks":
            base / len(covered), "adv_bound_low": lo, "adv_bound_high": hi, "target": target,
            "window_can_close_gap": bool(can_close)}


DEFINITIONS = [
    {"item": "Data source", "memo": "SIP trade messages (exchanges) + FINRA TRF media-eligible "
     "trade reports via CAT, incl. suppressed reports (p. 4)",
     "ours": "ATS self-reported weekly shares under FINRA Rule 4552 (API spec v0.4: 'shares "
     "reported by each ATS')"},
    {"item": "Sides counted", "memo": "Executed volume, one count per trade report",
     "ours": "Not documented by FINRA. A double count would put us ~70% above the memo, not "
             "13% below, so one count per trade is the working assumption."},
    {"item": "Window", "memo": "Executions 8:00 pm-4:00 am ET (p. 3)",
     "ours": "All volume on overnight-only ATSs; MOON from 7:30 pm, IEOS from 6:00 pm on "
             "holiday sessions (Form ATS-N)"},
    {"item": "Venues", "memo": "Table 1: ATS row = BOATS + Bruce + IBKR Eos + MOON",
     "ours": "Same four MPIDs: BLUE, BOSS, IEOS, MOON"},
    {"item": "Securities", "memo": "All NMS stocks", "ours": "NMS Tier 1 + Tier 2"},
    {"item": "Period", "memo": "Trade dates in Aug 2026 (8 pm prior day to 8 pm), 21 dates",
     "ours": "Complete FINRA weeks inside Aug 2026 (Aug 3-28), 20 trade dates"},
    {"item": "Revisions", "memo": "SIP corrections/cancellations reconciled; TRF reports not "
     "reversed, cancelled or broken", "ours": "As published; lastUpdateDate recorded per file"},
]


def run(month: str | None = None, weekly_adv: dict[str, float] | None = None) -> dict:
    t = load_yaml("reconciliation_targets")
    month = month or t["period"]["month"]
    out = {
        "pull_complete_live": check_pull_complete_live(month),
        "pull_complete_cached": check_pull_complete_cached(),
        "week_convention": check_week_convention(month),
        "tier_coverage": check_tier_coverage(month),
        "definitions": {"status": "info", "rows": DEFINITIONS},
    }
    if weekly_adv is None:
        _, overlap = month_weeks(month)
        days = trading_days()
        weekly_adv = {}
        for w in overlap:
            s = sum(r["totalWeeklyShareQuantity"] for tier in ("T1", "T2")
                    for m in overnight_mpids() for r in _live_records(w, tier, m)["records"]
                    if r["summaryTypeCode"] == "ATS_W_FIRM")
            ws = pd.Timestamp(w)
            n = int(((days >= ws) & (days <= ws + pd.Timedelta(days=4))).sum())
            weekly_adv[w] = s / n
    tg = t["targets"]["ats_adv_overnight"]
    out["window_bound"] = check_window_bound(month, weekly_adv, tg["value"], tg["tolerance_rel"])
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / "checks.json").write_text(json.dumps(out, indent=1, default=str))
    for k, v in out.items():
        log.info("check %s: %s", k, v["status"])
    return out

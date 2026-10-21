"""FINRA OTC Transparency weekly data (group otcMarket, dataset weeklySummary).

Public access, no credentials (checked 2026-10-20). The API returns at most 5,000 records per call
(`record-max-limit` header) and allows sorting only when both partition keys, `weekStartDate`
and `tierIdentifier`, are equality filters, so every call here fixes one week and one tier.

Record types used (field `summaryTypeCode`):
  ATS_W_SMBL_FIRM  shares/trades by symbol x ATS x week     (pulled for overnight venues only)
  ATS_W_SMBL       shares/trades by symbol x week, all ATSs
  OTC_W_SMBL       shares/trades by symbol x week, non-ATS OTC
  ATS_W_FIRM       shares/trades by ATS x week, all symbols in the tier

Tiers: `T1` = NMS Tier 1 (2-week publication delay), `T2` = NMS Tier 2 (4-week delay).
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
from pathlib import Path

import pandas as pd

from offhours.config import RAW, cfg, overnight_mpids
from offhours.data.http import request

log = logging.getLogger(__name__)
CACHE = RAW / "finra_ats"

FIELDS = {
    "weekStartDate": "week",
    "tierIdentifier": "tier",
    "summaryTypeCode": "summary_type",
    "MPID": "mpid",
    "marketParticipantName": "participant_name",
    "issueSymbolIdentifier": "symbol",
    "issueName": "issue_name",
    "totalWeeklyShareQuantity": "shares",
    "totalWeeklyTradeCount": "trades",
    "totalNotionalSum": "notional",
    "lastUpdateDate": "last_update",
}


def _post(filters: dict[str, str], limit: int, offset: int = 0) -> tuple[list[dict], int]:
    c = cfg()["finra_api"]
    body = {
        "limit": limit,
        "offset": offset,
        "compareFilters": [
            {"compareType": "equal", "fieldName": k, "fieldValue": v} for k, v in filters.items()
        ],
    }
    resp = request(
        "POST",
        c["url"],
        json=body,
        headers={"Accept": "application/json"},
        sleep=c["sleep_seconds"],
        max_retries=c["max_retries"],
        ok_statuses=(200, 204),  # 204 No Content = no matching records
    )
    if resp.status_code == 204 or not resp.content:
        return [], 0
    total = int(resp.headers.get("record-total", 0) or 0)
    return resp.json(), total


def fetch_all(filters: dict[str, str]) -> tuple[list[dict], int]:
    """All records matching equality filters, paging by offset; returns (rows, record-total).

    Raises if fewer rows arrive than the API's `record-total` header promises, so a pull can
    never be silently truncated at the 5,000-row page cap.
    """
    limit = cfg()["finra_api"]["page_limit"]
    rows, total = _post(filters, limit)
    while len(rows) < total:
        page, _ = _post(filters, limit, offset=len(rows))
        if not page:
            break
        rows.extend(page)
    if len(rows) != total:
        raise RuntimeError(f"FINRA pull {filters}: {len(rows)} rows, record-total {total}")
    return rows, total


def _cache_path(week: str, tier: str, summary_type: str, mpid: str | None) -> Path:
    name = summary_type + (f"_{mpid}" if mpid else "") + ".json.gz"
    return CACHE / tier / week / name


def get_week(week: str, tier: str, summary_type: str, mpid: str | None = None) -> list[dict]:
    """Records for one week/tier/type (and MPID), from cache or the API."""
    path = _cache_path(week, tier, summary_type, mpid)
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)["records"]
    filters = {"weekStartDate": week, "tierIdentifier": tier, "summaryTypeCode": summary_type}
    if mpid:
        filters["MPID"] = mpid
    records, total = fetch_all(filters)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"downloaded": dt.date.today().isoformat(), "filters": filters,
               "record_total": total, "records": records}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    return records


def latest_published_week(tier: str = "T1", today: dt.date | None = None) -> str:
    """Most recent Monday with ATS_W_FIRM records for the tier (checked live, not cached)."""
    today = today or dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    for k in range(0, 12):
        week = (monday - dt.timedelta(weeks=k)).isoformat()
        _, total = _post(
            {"weekStartDate": week, "tierIdentifier": tier, "summaryTypeCode": "ATS_W_FIRM"}, 1
        )
        if total > 0:
            return week
    raise RuntimeError(f"no published {tier} week in the last 12 weeks")


def weeks_between(start: str, end: str) -> list[str]:
    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    s -= dt.timedelta(days=s.weekday())
    return [(s + dt.timedelta(weeks=k)).isoformat() for k in range((e - s).days // 7 + 1)]


def download(start_week: str, end_week: str) -> None:
    """Cache every needed (week, tier, type, MPID) combination between two Mondays.

    The T2 end week is capped at the latest published T2 week so that an unpublished week is
    never cached as empty.
    """
    mpids = overnight_mpids()
    t2_end = min(end_week, latest_published_week("T2"))
    plan = []
    for week in weeks_between(start_week, end_week):
        plan += [(week, "T1", "ATS_W_SMBL_FIRM", m) for m in mpids]
        plan += [(week, "T1", t, None) for t in ("ATS_W_SMBL", "OTC_W_SMBL", "ATS_W_FIRM")]
        if week <= t2_end:
            plan += [(week, "T2", "ATS_W_SMBL_FIRM", m) for m in mpids]
            plan += [(week, "T2", "ATS_W_FIRM", None)]
    todo = [p for p in plan if not _cache_path(*p).exists()]
    log.info("FINRA weekly: %d requests planned, %d not cached", len(plan), len(todo))
    for i, p in enumerate(todo, 1):
        get_week(*p)
        if i % 50 == 0:
            log.info("FINRA weekly: %d / %d", i, len(todo))


def load(summary_type: str, tiers: tuple[str, ...] = ("T1", "T2")) -> pd.DataFrame:
    """All cached records of one summary type as a tidy DataFrame (one row per record)."""
    frames = []
    for tier in tiers:
        for path in sorted((CACHE / tier).glob(f"*/{summary_type}*.json.gz")):
            if summary_type == "ATS_W_SMBL" and "FIRM" in path.name:
                continue
            with gzip.open(path, "rt", encoding="utf-8") as f:
                payload = json.load(f)
            if payload["records"]:
                df = pd.DataFrame(payload["records"])
                df["downloaded"] = payload["downloaded"]
                frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[*FIELDS.values(), "downloaded"])
    df = pd.concat(frames, ignore_index=True)
    df = df[[c for c in FIELDS if c in df.columns] + ["downloaded"]].rename(columns=FIELDS)
    df["week"] = pd.to_datetime(df["week"])
    for c in ("shares", "trades", "notional"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

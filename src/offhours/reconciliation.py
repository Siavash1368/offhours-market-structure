"""Status of each reconciliation target, shared by the tests and the README/note generator.

Statuses (configs/reconciliation_targets.yaml explains the rules):
  pass              within tolerance
  explained         outside tolerance; documented_gaps entry with `verified_by` naming a check in
                    reports/tables/checks.json whose status is "pass"
  open              outside tolerance; listed under open_gaps (investigated, not explained)
  not_reproducible  listed under not_reproducible (public data cannot build the figure)
  fail              outside tolerance and none of the above
"""

from __future__ import annotations

import json

import pandas as pd

from offhours.config import TABLES, load_yaml

REC = TABLES / "a1_reconciliation.csv"
CHECKS = TABLES / "checks.json"


def load_rows() -> list[dict]:
    return pd.read_csv(REC).to_dict(orient="records") if REC.exists() else []


def load_checks() -> dict:
    return json.loads(CHECKS.read_text()) if CHECKS.exists() else {}


def describe(row: dict) -> str:
    tol = (f"rel tol {row['tolerance_rel']:.0%}" if pd.notna(row.get("tolerance_rel"))
           else f"abs tol {row['tolerance_abs']}")
    if pd.isna(row.get("ours")):
        return f"{row['target']}: memo {row['memo_value']:.4g}, ours n/a, {tol}"
    return (f"{row['target']}: memo {row['memo_value']:.4g}, ours {row['ours']:.4g}, "
            f"gap {row['gap']:+.4g} ({row['gap_rel']:+.1%}), {tol}")


def status(row: dict, cfg: dict | None = None, checks: dict | None = None) -> tuple[str, str]:
    """(status, message) for one row of a1_reconciliation.csv."""
    cfg = cfg if cfg is not None else load_yaml("reconciliation_targets")
    checks = checks if checks is not None else load_checks()
    target, msg = row["target"], describe(row)
    not_repro = cfg.get("not_reproducible") or {}
    if target in not_repro:
        return "not_reproducible", f"NOT REPRODUCIBLE {msg}. {not_repro[target]}"
    if row["within_tolerance"]:
        return "pass", msg
    doc = (cfg.get("documented_gaps") or {}).get(target)
    if doc and doc.get("verified_by"):
        st = checks.get(doc["verified_by"], {}).get("status")
        if st == "pass":
            return "explained", (f"EXPLAINED {msg}. Verified by check '{doc['verified_by']}'. "
                                 f"{doc.get('reason', '')}")
    open_gaps = cfg.get("open_gaps") or {}
    if target in open_gaps:
        return "open", f"OPEN GAP {msg}. {open_gaps[target]}"
    why = "no documented explanation"
    if doc:
        why = (f"documented reason has no passing verifying check "
               f"(verified_by={doc.get('verified_by')!r}): {doc.get('reason', '')}")
    return "fail", f"UNEXPLAINED {msg}. {why}"


def statuses() -> pd.DataFrame:
    cfg, checks = load_yaml("reconciliation_targets"), load_checks()
    out = []
    for row in load_rows():
        st, msg = status(row, cfg, checks)
        out.append({**row, "status": st, "message": msg})
    return pd.DataFrame(out)


def listed_targets(cfg: dict | None = None) -> dict[str, str]:
    """Targets that must be disclosed in README and note: open gaps and not-reproducible ones."""
    cfg = cfg if cfg is not None else load_yaml("reconciliation_targets")
    out = {k: "open gap" for k in (cfg.get("open_gaps") or {})}
    out.update({k: "not reproducible" for k in (cfg.get("not_reproducible") or {})})
    return out

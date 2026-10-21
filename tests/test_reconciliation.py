"""Reconciliation of A1 figures to the SEC staff memo (Sept 2026).

Reads reports/tables/a1_reconciliation.csv (written by the a1 phase, committed, so this also runs
in CI) and reports/tables/checks.json. Status rules live in src/offhours/reconciliation.py and
configs/reconciliation_targets.yaml:

  pass              within tolerance                      -> passes
  explained         verified by a passing named check     -> xfail(strict=True), "EXPLAINED ..."
  open              investigated, not explained           -> xfail(strict=True), "OPEN GAP ..."
  not_reproducible  public data cannot build the figure   -> skipped, "NOT REPRODUCIBLE ..."
  anything else                                           -> fails, "UNEXPLAINED ..."

strict=True: if an explained or open gap ever falls within tolerance, the test fails (XPASS) so
the YAML gets updated. The gap is printed in every case (`pytest -rxs -s`).
"""

import numbers

import pytest

from offhours import reconciliation as rc
from offhours.config import load_yaml


def test_targets_are_numbers():
    """Guards against YAML reading values such as 111.5e6 as strings."""
    for name, spec in load_yaml("reconciliation_targets")["targets"].items():
        values = spec.get("values", {"value": spec.get("value")})
        for k, v in values.items():
            assert isinstance(v, numbers.Number), f"{name}.{k} is {type(v).__name__}: {v!r}"
        for k in ("tolerance_rel", "tolerance_abs"):
            if k in spec:
                assert isinstance(spec[k], numbers.Number), f"{name}.{k} not numeric"


def _row(target, within, ours=1.0):
    return {"target": target, "memo_value": 1.0, "ours": ours, "gap": ours - 1.0,
            "gap_rel": ours - 1.0, "tolerance_rel": 0.1, "tolerance_abs": None,
            "within_tolerance": within}


def test_status_rules():
    cfg = {"documented_gaps": {"a": {"reason": "r", "verified_by": "c_ok"},
                               "b": {"reason": "r"},
                               "c": {"reason": "r", "verified_by": "c_bad"}},
           "open_gaps": {"o": "why", "c": "why"},
           "not_reproducible": {"n": "why"}}
    checks = {"c_ok": {"status": "pass"}, "c_bad": {"status": "fail"}}
    s = lambda t, w=False: rc.status(_row(t, w, 1.5), cfg, checks)[0]  # noqa: E731
    assert s("p", True) == "pass"
    assert s("a") == "explained"
    assert s("b") == "fail"           # reason without a verifying check
    assert s("c") == "open"           # verifying check failed, but listed as open
    assert s("o") == "open"
    assert s("n") == "not_reproducible"
    assert s("z") == "fail"
    assert rc.status(_row("o", False, 1.5), cfg, checks)[1].startswith("OPEN GAP")


@pytest.mark.parametrize("row", rc.load_rows(), ids=lambda r: r["target"])
def test_gap_within_tolerance(row, request):
    st, msg = rc.status(row)
    print(msg)
    if st == "not_reproducible":
        pytest.skip(msg)
    if st in ("explained", "open"):
        request.applymarker(pytest.mark.xfail(strict=True, reason=msg))
    assert row["within_tolerance"], msg

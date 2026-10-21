"""Command line entry point.

    python -m offhours.pipeline --phase {data,store,a1,a2,a3,robust,report,all}

Every download step reads from data/raw/ when the file is cached and only fetches what is missing.
"""

from __future__ import annotations

import argparse
import json
import logging

import pandas as pd

from offhours.config import PROCESSED, cfg, ensure_dirs

log = logging.getLogger("offhours")


def resolve_sample() -> dict:
    """Sample start and end weeks; the end week is the latest FINRA Tier 1 week, saved once."""
    from offhours.data import finra_ats

    path = PROCESSED / "sample.json"
    if path.exists():
        return json.loads(path.read_text())
    s = cfg()["sample"]
    end = s["end_week"] or finra_ats.latest_published_week("T1")
    sample = {"start_week": s["start_week"], "end_week": end}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sample, indent=1))
    return sample


def phase_data() -> None:
    from offhours.data import cboe, earnings, finra_ats, prices, regsho, symbols

    sample = resolve_sample()
    log.info("sample weeks %s to %s", sample["start_week"], sample["end_week"])
    symbols.download()
    first_year = int(sample["start_week"][:4]) - 1  # prior year for the Y/Y reconciliation base
    cboe.download(list(range(first_year, int(sample["end_week"][:4]) + 1)))
    finra_ats.download(sample["start_week"], sample["end_week"])

    week_end = (pd.Timestamp(sample["end_week"]) + pd.Timedelta(days=6)).date().isoformat()
    regsho.download(cfg()["regsho"]["start_date"], week_end)

    t1 = finra_ats.load("ATS_W_SMBL", tiers=("T1",))
    names = t1.sort_values("week").groupby("symbol")["issue_name"].last().reset_index()
    flags = symbols.etp_flags(names)
    end_px = (pd.Timestamp(week_end) + pd.Timedelta(days=1)).date().isoformat()
    prices.download(flags["symbol"].tolist(), cfg()["sample"]["price_start"], end_px)
    earnings.download(flags.loc[~flags["is_etp"], "symbol"].tolist())


def phase_store() -> None:
    from offhours import store

    store.build()
    from offhours.analysis import audit, checks, earnings_check

    audit.write_audit()
    checks.run()  # pull completeness, week convention, tiers -> reports/tables/checks.json
    earnings_check.run(start=cfg()["sample"]["placebo_start"])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", required=True,
                   choices=["data", "store", "a1", "a2", "a3", "robust", "report", "all"])
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ensure_dirs()

    steps = {
        "data": phase_data,
        "store": phase_store,
        "a1": lambda: __import__("offhours.analysis.a1_facts", fromlist=["run"]).run(),
        "a2": lambda: __import__("offhours.analysis.a2_panel", fromlist=["run"]).run(),
        "a3": lambda: __import__("offhours.analysis.a3_earnings", fromlist=["run"]).run(),
        "robust": lambda: __import__("offhours.analysis.robustness", fromlist=["run"]).run(),
        "report": lambda: __import__("offhours.report", fromlist=["run"]).run(),
    }
    order = ["data", "store", "a1", "a2", "a3", "robust", "report"]
    for name in order if args.phase == "all" else [args.phase]:
        log.info("=== phase %s ===", name)
        steps[name]()


if __name__ == "__main__":
    main()

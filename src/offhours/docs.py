"""Fill the generated blocks in README.md and reports/note/note.md from output tables.

Blocks are delimited by
    <!-- BEGIN GENERATED:<name> -->  ...  <!-- END GENERATED:<name> -->
and rewritten in place; text outside the markers is left alone. Every number in a block comes
from a file in reports/tables/, named in the block.

Blocks
  coverage   Tier 1 share of overnight-ATS volume, shares and dollars, by venue
             (reports/tables/a1_tier_coverage.csv)
  gaps       open reconciliation gaps and targets not reproducible with public data
             (configs/reconciliation_targets.yaml, reports/tables/a1_reconciliation.csv)
"""

from __future__ import annotations

import re

import pandas as pd

from offhours import reconciliation as rc
from offhours.config import REPORTS, ROOT, TABLES, load_yaml

README = ROOT / "README.md"
NOTE = REPORTS / "note" / "note.md"


def _replace(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- BEGIN GENERATED:{name} -->\n).*?(<!-- END GENERATED:{name} -->)",
                     re.S)
    if not pat.search(text):
        raise ValueError(f"block {name} not found")
    return pat.sub(lambda m: m.group(1) + body.rstrip() + "\n" + m.group(2), text)


def coverage_block() -> str:
    path = TABLES / "a1_tier_coverage.csv"
    if not path.exists():
        return "_Tier coverage table not built yet: run `python -m offhours.pipeline --phase a1`._"
    c = pd.read_csv(path)
    lines = ["Tier 1 share of overnight-ATS volume (A2 and A3 use Tier 1 only; A1 uses both "
             "tiers). Source: `reports/tables/a1_tier_coverage.csv`.", "",
             "| Period | Venue | Tier 1 share of shares | Tier 1 share of dollars |",
             "|---|---|---|---|"]
    for _, r in c.iterrows():
        lines.append(f"| {r['period']} | {r['venue']} | {r['t1_share_of_shares']:.1%} | "
                     f"{r['t1_share_of_dollars']:.1%} |")
    return "\n".join(lines)


def gaps_block() -> str:
    cfg = load_yaml("reconciliation_targets")
    listed = rc.listed_targets(cfg)
    st = rc.statuses()
    by_target = st.set_index("target") if len(st) else pd.DataFrame()
    lines = ["Reconciliation targets from the SEC staff memo (Sept 2026) that this repo does not "
             "match. Gaps: `reports/tables/a1_reconciliation.csv`; reasons: "
             "`configs/reconciliation_targets.yaml`; checks: `reports/tables/checks.json`.", ""]
    if not listed:
        return "\n".join([*lines, "None."])
    reasons = {**(cfg.get("open_gaps") or {}), **(cfg.get("not_reproducible") or {})}
    for target, kind in listed.items():
        measured = ""
        if target in by_target.index and pd.notna(by_target.loc[target, "ours"]):
            r = by_target.loc[target]
            measured = (f" Memo {r['memo_value']:.4g}, ours {r['ours']:.4g} "
                        f"({r['gap_rel']:+.1%}).")
        lines.append(f"- `{target}` ({kind}).{measured} {' '.join(reasons[target].split())}")
    return "\n".join(lines)


SUMMARY = """\
Main results (every number generated from `reports/tables/` by `src/offhours/report.py`):

- **Growth.** Overnight-ATS volume rose from {adv_first}M to {adv_last}M shares per night
  ({adv_growth_x}x) between the first and last 13 of {a1_weeks} weeks ({a1_first_week} to
  {a1_last_week}); {share_nms_last} of NMS share volume and {dshare_nms_last} of dollar volume
  in the last 13 weeks.
- **Concentration.** Top-10 symbols: {top10_last} of overnight volume; ETPs {etp_share_last};
  Blue Ocean {vs_BLUE} of overnight-ATS volume in {last_quarter}.
- **Reconciliation to the SEC staff memo.** {rec_pass} of {rec_reproducible} reproducible figures
  within pre-set tolerances; {rec_open} open gaps; {rec_nr} not reproducible (below).
- **Who trades overnight (Tier 1 panel, {a2_obs} stock-weeks).** Overnight share {a2_earn_pct}
  higher in earnings weeks; lower with a higher off-exchange short share; little explained
  within stocks.
- **Price discovery ({a3_events} after-close earnings events).** Opening prices capture more of
  the move in stocks with more overnight trading ({wpc_earnings_3} vs {wpc_earnings_1}), but the
  same gap existed in 2018-2020 (change {pl_gap}, 95% CI {pl_gap_lo} to {pl_gap_hi}): it
  reflects stock type, not overnight trading.

Documents: [research note](reports/note/note.md), [two-page brief](reports/note/brief.md),
[data audit](reports/data_audit.md), [build log](reports/build_log.md).
"""


def summary_block() -> str:
    from offhours import report

    return report.render(SUMMARY, report.facts())


def update() -> None:
    blocks = {"coverage": coverage_block(), "gaps": gaps_block(), "summary": summary_block()}
    for path in (README, NOTE):
        text = path.read_text(encoding="utf-8")
        for name, body in blocks.items():
            if f"BEGIN GENERATED:{name}" in text:
                text = _replace(text, name, body)
        path.write_text(text, encoding="utf-8")

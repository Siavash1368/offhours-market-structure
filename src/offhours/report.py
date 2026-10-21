"""Write the note, the brief and headline_figures.md from the output tables.

Every number in reports/note/note.md, reports/note/brief.md and reports/headline_figures.md comes
from `facts()`, which reads only files in reports/tables/ (plus Parquet row counts from the
local store, saved to reports/tables/store_counts.json). Templates live in
src/offhours/templates/ and reference facts as {name}; an unknown name raises an error, so no
number can be typed into the prose by hand. Each fact records its source file.
"""

from __future__ import annotations

import json
import os
import string
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from offhours.config import PROCESSED, REPORTS, ROOT, TABLES, load_yaml

TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class Fact:
    text: str      # formatted for the prose
    value: float   # raw value
    source: str    # file it came from (repo-relative)


def _j(name: str) -> dict:
    return json.loads((TABLES / name).read_text())


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def store_counts() -> dict:
    """Row counts of the Parquet store (local data needed); cached in store_counts.json."""
    path = TABLES / "store_counts.json"
    if (PROCESSED / "ats_overnight.parquet").exists():
        import pyarrow.parquet as pq

        counts = {p.stem: pq.ParquetFile(p).metadata.num_rows
                  for p in sorted(PROCESSED.glob("*.parquet"))}
        path.write_text(json.dumps(counts, indent=1))
    return json.loads(path.read_text())


def facts() -> dict[str, Fact]:
    f: dict[str, Fact] = {}

    def add(name, value, fmt, source):
        if fmt == "p":  # p-values: two decimals, "<0.01" / "<0.001" below that
            text = ("< 0.001" if value < 0.001 else "< 0.01" if value < 0.005
                    else f"= {value:.2f}")
        else:
            text = fmt.format(value)
        f[name] = Fact(text, float(value), f"reports/tables/{source}")

    pct = "{:.1%}"
    # Store and data.
    sc = store_counts()
    add("rows_ovn", sc["ats_overnight"], "{:,.0f}", "store_counts.json")
    add("rows_regsho", sc["regsho_daily"], "{:,.0f}", "store_counts.json")
    add("rows_prices", sc["prices_daily"], "{:,.0f}", "store_counts.json")
    add("rows_all", sum(sc.values()), "{:,.0f}", "store_counts.json")
    add("rows_all_m", sum(sc.values()) / 1e6, "{:.1f}", "store_counts.json")

    # A1.
    a1 = _j("a1_summary.json")
    add("a1_weeks", a1["n_weeks"], "{:,.0f}", "a1_summary.json")
    f["a1_first_week"] = Fact(a1["sample_first_week"], 0, "reports/tables/a1_summary.json")
    f["a1_last_week"] = Fact(a1["sample_last_week"], 0, "reports/tables/a1_summary.json")
    add("adv_first", a1["ovn_adv_first13w"] / 1e6, "{:.1f}", "a1_summary.json")
    add("adv_last", a1["ovn_adv_last13w"] / 1e6, "{:.0f}", "a1_summary.json")
    add("adv_growth_x", a1["ovn_adv_last13w"] / a1["ovn_adv_first13w"], "{:.0f}",
        "a1_summary.json")
    add("share_nms_first", a1["ovn_share_of_nms_first13w"], "{:.2%}", "a1_summary.json")
    add("share_nms_last", a1["ovn_share_of_nms_last13w"], "{:.2%}", "a1_summary.json")
    add("dshare_nms_last", a1["ovn_dollar_share_of_nms_last13w"], "{:.2%}", "a1_summary.json")
    add("ats_only_share_recon", a1["ats_only_ovn_share_of_nms_recon_month"], "{:.2%}",
        "a1_summary.json")
    add("top10_last", a1["top10_share_last13w"], pct, "a1_summary.json")
    add("top100_last", a1["top100_share_last13w"], pct, "a1_summary.json")
    add("hhi_last", a1["hhi_last13w"], "{:.3f}", "a1_summary.json")
    add("etp_share_last", a1["etp_share_of_ovn_last13w"], pct, "a1_summary.json")
    add("ovn_symbols_last", a1["ovn_symbols_last13w_mean"], "{:,.0f}", "a1_summary.json")
    add("ovn_of_all_ats_last", a1["ovn_share_of_all_ats_last13w"], pct, "a1_summary.json")
    add("t1_sh_shares", a1["t1_share_of_ovn_shares_full"], pct, "a1_summary.json")
    add("t1_sh_dollars", a1["t1_share_of_ovn_dollars_full"], pct, "a1_summary.json")
    add("t2_sh_shares", 1 - a1["t1_share_of_ovn_shares_full"], pct, "a1_summary.json")
    vs = a1["venue_shares_last_quarter"]
    for m in ("BLUE", "BOSS", "IEOS", "MOON"):
        add(f"vs_{m}", vs[m], pct, "a1_summary.json")
    f["last_quarter"] = Fact(a1["last_quarter"], 0, "reports/tables/a1_summary.json")

    # Reconciliation.
    from offhours import reconciliation as rc

    st = rc.statuses()
    add("rec_n", len(st), "{:.0f}", "a1_reconciliation.csv")
    add("rec_pass", (st["status"] == "pass").sum(), "{:.0f}", "a1_reconciliation.csv")
    add("rec_open", (st["status"] == "open").sum(), "{:.0f}", "a1_reconciliation.csv")
    add("rec_nr", (st["status"] == "not_reproducible").sum(), "{:.0f}", "a1_reconciliation.csv")
    add("rec_reproducible", (st["status"] != "not_reproducible").sum(), "{:.0f}",
        "a1_reconciliation.csv")
    r = st.set_index("target")
    add("rec_adv_ours", r.loc["ats_adv_overnight", "ours"] / 1e6, "{:.1f}",
        "a1_reconciliation.csv")
    add("rec_adv_memo", r.loc["ats_adv_overnight", "memo_value"] / 1e6, "{:.1f}",
        "a1_reconciliation.csv")
    add("rec_adv_gap", r.loc["ats_adv_overnight", "gap_rel"], "{:+.1%}", "a1_reconciliation.csv")
    add("rec_advt_gap", r.loc["ats_advt_overnight", "gap_rel"], "{:+.1%}",
        "a1_reconciliation.csv")
    add("rec_adv_short", -r.loc["ats_adv_overnight", "gap_rel"], "{:.1%}",
        "a1_reconciliation.csv")
    add("rec_advt_short", -r.loc["ats_advt_overnight", "gap_rel"], "{:.1%}",
        "a1_reconciliation.csv")
    add("rec_top10_ours", r.loc["top10_share_overnight", "ours"], pct, "a1_reconciliation.csv")
    add("rec_top10_memo", r.loc["top10_share_overnight", "memo_value"], pct,
        "a1_reconciliation.csv")
    add("rec_yoy_ours", r.loc["ats_adv_yoy_growth", "ours"], "{:+.0%}", "a1_reconciliation.csv")
    add("rec_yoy_memo", r.loc["ats_adv_yoy_growth", "memo_value"], "{:+.0%}",
        "a1_reconciliation.csv")
    ck = _j("checks.json")
    add("ck_venue_weeks", ck["pull_complete_cached"]["venue_week_tiers"], "{:,.0f}",
        "checks.json")

    # Earnings timing.
    et = _j("earnings_timing_summary.json")
    add("et_amc", et["amc_events"], "{:,.0f}", "earnings_timing_summary.json")
    add("et_amc_contra", et["amc_share_contradicting"], pct, "earnings_timing_summary.json")

    # A2.
    a2 = _j("a2_summary.json")
    add("a2_obs", a2["n_obs"], "{:,.0f}", "a2_summary.json")
    add("a2_stocks", a2["n_stocks"], "{:,.0f}", "a2_summary.json")
    add("a2_weeks", a2["n_weeks"], "{:,.0f}", "a2_summary.json")
    add("a2_mean", a2["mean_ovn_share_pct"], "{:.3f}", "a2_summary.json")
    add("a2_zero", 1 - a2["share_stock_weeks_with_ovn"], "{:.0%}", "a2_summary.json")
    add("a2_top_tail", a2["share_of_outcome_sum_top_0p1pct"], "{:.0%}", "a2_summary.json")
    rel = a2["relative_to_mean_two_way"]
    add("a2_earn_rel", rel["earn_week"], "{:+.0%}", "a2_summary.json")
    add("a2_earn_pct", rel["earn_week"], "{:.0%}", "a2_summary.json")
    add("a2_short_rel", rel["short_share_l1"], "{:+.0%}", "a2_summary.json")
    add("a2_short_pct", -rel["short_share_l1"], "{:.0%}", "a2_summary.json")
    add("a2_price_rel", rel["log_price_l1"], "{:+.0%}", "a2_summary.json")
    add("a2_etp_rel", a2["etp_pooled_relative_to_mean"], "{:.1f}", "a2_summary.json")
    add("a2_r2", a2["r2_within_two_way"], "{:.3f}", "a2_summary.json")
    add("a2_earn_p", a2["p_two_way"]["earn_week"], "p", "a2_summary.json")
    d4 = a2["diagnostics"]["(D4) Any overnight trading (LPM)"]
    add("a2_d4_earn", d4["earn_week"]["coef"], "{:.1f}", "a2_summary.json")

    # A3.
    a3 = _j("a3_summary.json")
    add("a3_events", a3["n_earnings_events"], "{:,.0f}", "a3_summary.json")
    add("a3_stocks", a3["n_earnings_stocks"], "{:,.0f}", "a3_summary.json")
    add("a3_base", a3["n_baseline_nights"], "{:,.0f}", "a3_summary.json")
    add("a3_dropped_flag", a3["dropped_flag_contradicting"], "{:,.0f}", "a3_summary.json")
    add("a3_b", a3["b_rn_earnings"], "{:+.3f}", "a3_summary.json")
    add("a3_b_p", a3["p_rn_earnings"], "p", "a3_summary.json")
    add("a3_c", a3["c_rn_x_I_earnings"], "{:+.3f}", "a3_summary.json")
    add("a3_c_p", a3["p_rn_x_I_earnings"], "p", "a3_summary.json")
    add("a3_triple", a3["triple_rn_x_I_x_E"], "{:+.3f}", "a3_summary.json")
    add("a3_triple_p", a3["p_triple"], "p", "a3_summary.json")
    eff = _csv("a3_efficiency.csv").set_index(["model", "term"])
    add("a3_base_b", eff.loc[("(5) Non-earnings", "r_n"), "coef"], "{:+.3f}",
        "a3_efficiency.csv")
    add("a3_size_c", eff.loc[("(4) Earnings", "r_n_x_I"), "coef"], "{:+.3f}",
        "a3_efficiency.csv")
    add("a3_size_c_p", eff.loc[("(4) Earnings", "r_n_x_I"), "p"], "p", "a3_efficiency.csv")
    w = _csv("a3_wpc.csv").set_index(["sample", "tercile"])
    for s in ("earnings", "baseline"):
        for t in (1, 2, 3):
            add(f"wpc_{s}_{t}", w.loc[(s, t), "wpc_night"], "{:.2f}", "a3_wpc.csv")
    add("wpc_earn_all", w.loc[("earnings", 0), "wpc_night"], "{:.2f}", "a3_wpc.csv")
    add("wpc_base_all", w.loc[("baseline", 0), "wpc_night"], "{:.2f}", "a3_wpc.csv")
    ev = _csv("a3_event_list.csv")
    add("a3_corr_size", ev["I"].rank().corr(ev["size"].rank()), "{:.2f}", "a3_event_list.csv")
    add("a3_zero_I", (ev["I"] == 0).mean(), "{:.0%}", "a3_event_list.csv")

    # Robustness.
    rb = _csv("robustness.csv")
    def rrow(check, group_prefix):
        return rb[(rb["check"] == check) & rb["group"].str.startswith(group_prefix)].iloc[0]
    for k, g in (("1", "size tercile 1"), ("2", "size tercile 2"), ("3", "size tercile 3")):
        row = rrow("R1 size tercile", g)
        add(f"r1_c{k}", row["coef"], "{:+.2f}", "robustness.csv")
        add(f"r1_p{k}", row["p"], "p", "robustness.csv")
    row = rrow("R3 excl. outage weeks", "")
    add("r3_c", row["coef"], "{:+.3f}", "robustness.csv")
    add("r3_p", row["p"], "p", "robustness.csv")
    row = rrow("R4 alt. intensity", "percentile")
    add("r4_rank_p", row["p"], "p", "robustness.csv")
    row = rrow("R5 no timing-flag filter", "")
    add("r5_c", row["coef"], "{:+.3f}", "robustness.csv")
    add("r5_p", row["p"], "p", "robustness.csv")
    pw = _csv("robustness_placebo_wpc.csv")
    for per, key in (("2018-2020 (placebo)", "pre"), ("2023 onward", "post")):
        for t in (1, 3):
            add(f"pl_{key}_{t}", pw[(pw["period"] == per) & (pw["type_tercile"] == t)]
                ["wpc_night"].iloc[0], "{:.2f}", "robustness_placebo_wpc.csv")
    gap = pw[pw["period"].str.startswith("change")].iloc[0]
    add("pl_gap", gap["wpc_night"], "{:+.3f}", "robustness_placebo_wpc.csv")
    add("pl_gap_lo", gap["ci_lo"], "{:+.3f}", "robustness_placebo_wpc.csv")
    add("pl_gap_hi", gap["ci_hi"], "{:+.3f}", "robustness_placebo_wpc.csv")
    return f


def render(template: str, f: dict[str, Fact]) -> str:
    """Fill {name} placeholders; raises KeyError on an unknown fact."""
    names = {n for _, n, _, _ in string.Formatter().parse(template) if n}
    missing = names - set(f)
    if missing:
        raise KeyError(f"unknown facts in template: {sorted(missing)}")
    return template.format(**{k: v.text for k, v in f.items()})


def sources_table(f: dict[str, Fact], used: set[str]) -> str:
    by_src: dict[str, list[str]] = {}
    for k in sorted(used):
        by_src.setdefault(f[k].source, []).append(k)
    return "\n".join(f"- `{src}`: {', '.join(v)}" for src, v in sorted(by_src.items()))


def _used(template: str) -> set[str]:
    return {n for _, n, _, _ in string.Formatter().parse(template) if n}


HEADLINE_ITEMS = [
    # (claim template, facts used, code that produced it)
    ("Built a reproducible Python/DuckDB pipeline over public FINRA, Cboe and market data "
     "({rows_all_m}M rows, incl. {rows_ovn} FINRA overnight-venue symbol-week records and "
     "{rows_regsho} Reg SHO short-volume records).",
     "src/offhours/data/*.py, src/offhours/store.py"),
    ("Reconciled weekly FINRA ATS data to the SEC staff's Sept 2026 overnight-trading memo: "
     "{rec_pass} of {rec_reproducible} reproducible figures within tolerances fixed in "
     "advance; the remaining gaps ({rec_adv_gap} in shares) documented as open after ruling out "
     "data-pull errors (consistency checks on {ck_venue_weeks} venue-week-tier totals).",
     "src/offhours/analysis/a1_facts.py, src/offhours/analysis/checks.py, "
     "src/offhours/reconciliation.py"),
    ("Measured the growth of overnight ATS trading in NMS stocks from {adv_first}M to "
     "{adv_last}M shares per night ({adv_growth_x}x; first vs last 13 weeks of "
     "{a1_first_week} to {a1_last_week}); "
     "Tier 2 stocks are {t2_sh_shares} of overnight shares but Tier 1 is {t1_sh_dollars} of "
     "overnight dollars.",
     "src/offhours/analysis/a1_facts.py"),
    ("Estimated a two-way fixed-effects panel ({a2_obs} stock-weeks, {a2_stocks} stocks): "
     "overnight trading share is {a2_earn_pct} higher in earnings weeks (association).",
     "src/offhours/analysis/a2_panel.py"),
    ("Event study of {a3_events} after-close earnings announcements; a 2018-2020 placebo "
     "indicated the apparent link between overnight trading and opening-price efficiency "
     "reflects stock type (change in gap {pl_gap}, 95% CI [{pl_gap_lo}, {pl_gap_hi}]).",
     "src/offhours/analysis/a3_earnings.py, src/offhours/analysis/robustness.py, "
     "src/offhours/measures.py"),
]


def headline_figures(f: dict[str, Fact]) -> str:
    lines = ["# Headline figures", "",
             "Generated by `src/offhours/report.py` from `reports/tables/`. Every number is "
             "produced by code in this repository; the file and code behind each are listed. "
             "Independent research on public data; results are associations.", ""]
    for i, (tmpl, code) in enumerate(HEADLINE_ITEMS, 1):
        used = _used(tmpl)
        files = sorted({f[k].source for k in used})
        lines += [f"## {i}", "", render(tmpl, f), "",
                  f"- Numbers: {', '.join(f'`{k}` = {f[k].text}' for k in sorted(used))}",
                  f"- Files: {', '.join(f'`{x}`' for x in files)}",
                  f"- Code: `{code}`", ""]
    lines += ["## Limits", "",
              "- Weekly, ATS-only public data; no CAT or order-level data.",
              "- A2 and A3 cover NMS Tier 1 only.",
              "- Reconciliation gaps listed in README.md (\"Known gaps\")."]
    return "\n".join(lines) + "\n"


def run() -> None:
    f = facts()
    note_dir = REPORTS / "note"
    note_dir.mkdir(parents=True, exist_ok=True)
    for name in ("note", "brief"):
        tmpl = (TEMPLATES / f"{name}.md").read_text(encoding="utf-8")
        body = render(tmpl, f)
        body += ("\n\n---\n\n*Every number above is generated by `src/offhours/report.py` "
                 "from these files:*\n\n" + sources_table(f, _used(tmpl)) + "\n")
        (note_dir / f"{name}.md").write_text(body, encoding="utf-8")
    headline = headline_figures(f)
    (REPORTS / "headline_figures.md").write_text(headline, encoding="utf-8")
    # Optional identical copy at a local path (e.g. outside version control), set in .env.
    copy = os.environ.get("OFFHOURS_FIGURES_COPY")
    if copy:
        (ROOT / copy).write_text(headline, encoding="utf-8")
    from offhours import docs

    docs.update()
    load_yaml.cache_clear()

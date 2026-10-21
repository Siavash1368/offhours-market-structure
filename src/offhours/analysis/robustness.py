"""Robustness checks for A3, run in a fixed order (R1 to R5).

R1  Size terciles: the intensity interaction within terciles of pre-event dollar volume.
R2  Pre-period placebo: 2018-2020 after-close earnings events, stocks classified by their *later*
    (2023 onward) average overnight share. If high-intensity stocks already had more efficient
    opens before overnight ATSs mattered, the A3 association reflects stock type.
    The same time-invariant classification is applied to 2023+ events for a like-for-like
    comparison (difference-in-differences style contrast, descriptive only).
R3  Excluding events whose event week or 4-week intensity window contains a known
    overnight-venue outage week (configs/outages.yaml).
R4  Alternative intensity measures: log(1 + average overnight shares) and the cross-sectional
    percentile rank of intensity within the event week.
R5  Without the earnings timing-flag filter (earnings_check): all after-close events, since
    dropping flag-contradicting events selects on |r_n|.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from offhours import measures
from offhours.analysis import a3_earnings as a3
from offhours.analysis.common import save_json, save_table, week_start
from offhours.config import TABLES, load_yaml

log = logging.getLogger(__name__)


def _fit(df: pd.DataFrame, cols: dict[str, pd.Series]):
    d = df.set_index(["ticker", "t"])
    X = pd.DataFrame({k: v.to_numpy() for k, v in cols.items()}, index=d.index)
    X.insert(0, "const", 1.0)
    return PanelOLS(d["r_d"], X).fit(cov_type="clustered", cluster_entity=True,
                                     cluster_time=True)


def _coef(res, term: str) -> dict:
    return {"coef": float(res.params[term]), "se": float(res.std_errors[term]),
            "p": float(res.pvalues[term]), "n": int(res.nobs)}


def intensity_fit(df: pd.DataFrame, col: str = "I"):
    df = df.dropna(subset=[col])
    return _fit(df, {"r_n": df["r_n"], "r_n_x_I": df["r_n"] * df[col], "I": df[col]})


def tercile_fit(df: pd.DataFrame, terc: str = "tercile"):
    t2 = (df[terc] == 2).astype(float)
    t3 = (df[terc] == 3).astype(float)
    return _fit(df, {"r_n": df["r_n"], "r_n_x_T2": df["r_n"] * t2, "r_n_x_T3": df["r_n"] * t3,
                     "T2": t2, "T3": t3})


def r1_size(earn: pd.DataFrame) -> list[dict]:
    e = earn.dropna(subset=["size"]).copy()
    e["size_t"] = pd.qcut(e["size"], 3, labels=[1, 2, 3]).astype(int)
    rows = []
    for k, g in e.groupby("size_t"):
        res = intensity_fit(g)
        wpc = measures.weighted_price_contribution(g["r_n"], g["r_cc"], g["tercile"])
        rows.append({"check": "R1 size tercile", "group": f"size tercile {k}",
                     **_coef(res, "r_n_x_I"), "b_rn": float(res.params["r_n"]),
                     **{f"wpc_I_tercile_{int(i)}": float(v) for i, v in wpc.items()}})
    return rows


def stock_type_classification(panel: pd.DataFrame) -> pd.Series:
    """Tercile (1-3) of each common stock's mean overnight share over the whole FINRA sample."""
    m = panel[panel["is_etp"] == 0].groupby("ticker")["ovn_share"].mean().dropna()
    return pd.Series(pd.qcut(m.rank(method="first"), 3, labels=[1, 2, 3]).astype(int),
                     index=m.index, name="type_tercile")


def r2_placebo(panel, px, ern) -> tuple[list[dict], pd.DataFrame]:
    cls = stock_type_classification(panel)
    px = px[px["ticker"].isin(cls.index)]
    n = a3.nights(px)
    # Same timing-flag filter as the main A3 sample, in both periods.
    drop = load_yaml("config")["earnings"].get("drop_contradicting", False)
    ac = a3.validated_after_close(ern, px, drop)
    ac = ac[~ac["contradicts"]].drop(columns="contradicts")
    ev = n.merge(ac, on=["ticker", "t"], how="inner")
    ev = ev[(ev["r_n"].abs() <= a3.MAX_ABS_RET) & (ev["r_d"].abs() <= a3.MAX_ABS_RET)]
    ev["type_tercile"] = ev["ticker"].map(cls)
    s = load_yaml("config")["sample"]
    periods = {
        "2018-2020 (placebo)": (s["placebo_start"], s["placebo_end"]),
        "2023 onward": (s["start_week"], "2100-01-01"),
    }
    rows, wpc_rows, samples = [], [], {}
    for label, (a, b) in periods.items():
        g = ev[(ev["t"] >= a) & (ev["t"] <= b)]
        samples[label] = g
        if len(g) < 100:
            log.warning("R2: only %d events in %s", len(g), label)
            continue
        res = tercile_fit(g, "type_tercile")
        rows.append({"check": "R2 placebo", "group": label, **_coef(res, "r_n_x_T3"),
                     "b_rn": float(res.params["r_n"]),
                     "coef_T2": float(res.params["r_n_x_T2"]),
                     "n_stocks": int(g["ticker"].nunique())})
        for k, gg in g.groupby("type_tercile"):
            est, lo, hi = measures.bootstrap_wpc(gg["r_n"], gg["r_cc"], gg["ticker"], n_boot=499)
            wpc_rows.append({"period": label, "type_tercile": int(k), "wpc_night": est,
                             "ci_lo": lo, "ci_hi": hi, "n_events": len(gg)})
    labels = list(periods)
    if all(lbl in samples and len(samples[lbl]) >= 100 for lbl in labels):
        def frame(g):
            return pd.DataFrame({"r_w": g["r_n"], "r_t": g["r_cc"], "cluster": g["ticker"],
                                 "group": g["type_tercile"]})
        est, lo, hi = measures.wpc_gap_change(frame(samples[labels[0]]),
                                              frame(samples[labels[1]]))
        wpc_rows.append({"period": f"change in top-minus-bottom gap, {labels[1]} vs "
                                   f"{labels[0]}", "type_tercile": 0, "wpc_night": est,
                         "ci_lo": lo, "ci_hi": hi, "n_events": sum(map(len, samples.values()))})
    return rows, pd.DataFrame(wpc_rows)


def r3_outages(earn: pd.DataFrame) -> list[dict]:
    weeks = []
    for o in load_yaml("outages")["outages"]:
        weeks += [pd.Timestamp(w) for w in o["weeks"]]
    bad = set()
    for w in weeks:
        bad.update(w + pd.Timedelta(weeks=k) for k in range(0, 5))  # event week + 4 after
    ew = week_start(earn["t"])
    keep = earn[~ew.isin(bad)]
    res = intensity_fit(keep)
    return [{"check": "R3 excl. outage weeks", "group": f"{len(earn) - len(keep)} events dropped",
             **_coef(res, "r_n_x_I"), "b_rn": float(res.params["r_n"])}]


def r4_alternatives(earn: pd.DataFrame) -> list[dict]:
    e = earn.copy()
    e["I_logshares"] = np.log1p(e["I_shares"])
    e["I_rank"] = e.groupby(week_start(e["t"]))["I"].rank(pct=True)
    rows = []
    for col, label in [("I_logshares", "log(1 + avg overnight shares)"),
                       ("I_rank", "percentile rank within event week")]:
        res = intensity_fit(e, col)
        rows.append({"check": "R4 alt. intensity", "group": label, **_coef(res, "r_n_x_I"),
                     "b_rn": float(res.params["r_n"])})
    return rows


def run() -> dict:
    panel, px, ern = a3.load_inputs()
    px = px[px["ticker"].isin(set(panel["ticker"]))]
    ev = a3.build_events(panel, px, ern)
    common = set(panel.loc[panel["is_etp"] == 0, "ticker"])
    ev = ev[ev["ticker"].isin(common)]
    earn = ev[ev["sample"] == "earnings"]

    base_res = intensity_fit(earn)
    rows = [{"check": "A3 main (for reference)", "group": "all earnings events",
             **_coef(base_res, "r_n_x_I"), "b_rn": float(base_res.params["r_n"])}]
    rows += r1_size(earn)
    placebo_rows, placebo_wpc = r2_placebo(panel, px, ern)
    rows += placebo_rows
    rows += r3_outages(earn)
    rows += r4_alternatives(earn)

    # R5: without dropping after-close events whose returns contradict the timing flag.
    unf = a3.build_events(panel, px, ern, drop_contradicting=False)
    unf = unf[unf["ticker"].isin(common) & (unf["sample"] == "earnings")]
    res = intensity_fit(unf)
    rows.append({"check": "R5 no timing-flag filter", "group": "all after-close events",
                 **_coef(res, "r_n_x_I"), "b_rn": float(res.params["r_n"])})
    out = pd.DataFrame(rows)
    save_table(out, "robustness")
    save_table(placebo_wpc, "robustness_placebo_wpc")

    lines = ["# Robustness checks (A3)", "",
             "Coefficient shown: r_n x intensity (R1, R3, R4) or r_n x top stock-type tercile "
             "(R2). Standard errors clustered by stock and date. Source: "
             "`src/offhours/analysis/robustness.py`.", "",
             "| Check | Group | coef | se | p | N | b on r_n |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['check']} | {r['group']} | {r['coef']:.4f} | {r['se']:.4f} | "
                     f"{r['p']:.3f} | {r['n']:,} | {r['b_rn']:.4f} |")
    lines += ["", "## R2 placebo: night WPC by stock-type tercile", "",
              placebo_wpc.to_markdown(index=False, floatfmt=".3f") if len(placebo_wpc) else ""]
    (TABLES / "robustness.md").write_text("\n".join(lines) + "\n")
    summary = {"rows": rows, "placebo_wpc": placebo_wpc.to_dict(orient="records")}
    save_json(summary, "robustness_summary")
    log.info("robustness:\n%s", out.to_string())
    return summary

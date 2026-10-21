"""Regression tables: tidy coefficient frames and side-by-side Markdown tables."""

from __future__ import annotations

import numpy as np
import pandas as pd


def stars(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def tidy(res, model: str) -> pd.DataFrame:
    """Coefficient table from a statsmodels or linearmodels result."""
    params = res.params
    se = res.std_errors if hasattr(res, "std_errors") else res.bse
    p = res.pvalues
    out = pd.DataFrame({"model": model, "term": params.index, "coef": params.values,
                        "se": se.values, "p": p.values})
    out["t"] = out["coef"] / out["se"]
    return out


def side_by_side(
    tidies: list[pd.DataFrame],
    stats: list[dict],
    labels: dict[str, str] | None = None,
    fmt: str = "{:.3f}",
) -> str:
    """Markdown table: one column per model, coef with stars over (se); stats rows at bottom."""
    labels = labels or {}
    models = [t["model"].iloc[0] for t in tidies]
    terms: list[str] = []
    for t in tidies:
        terms += [x for x in t["term"] if x not in terms]
    lines = ["| | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for term in terms:
        c_row, s_row = [], []
        for t in tidies:
            r = t[t["term"] == term]
            if r.empty:
                c_row.append("")
                s_row.append("")
            else:
                r = r.iloc[0]
                c_row.append(fmt.format(r["coef"]) + stars(r["p"]))
                s_row.append("(" + fmt.format(r["se"]) + ")")
        lines.append(f"| {labels.get(term, term)} | " + " | ".join(c_row) + " |")
        lines.append("| | " + " | ".join(s_row) + " |")
    for key in stats[0]:
        vals = []
        for s in stats:
            v = s.get(key, "")
            if isinstance(v, (float, np.floating)):
                v = f"{v:.3f}"
            elif isinstance(v, (int, np.integer)):
                v = f"{v:,}"
            vals.append(str(v))
        lines.append(f"| {key} | " + " | ".join(vals) + " |")
    return "\n".join(lines)

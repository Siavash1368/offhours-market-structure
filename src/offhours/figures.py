"""Figures for the note (PNG, reports/figures/). Plain matplotlib, one figure per function."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from offhours.config import FIGURES, load_yaml  # noqa: E402

VENUE_COLORS = {"BLUE": "#1f4e79", "BOSS": "#c55a11", "IEOS": "#548235", "MOON": "#7f6000"}
TERC_COLORS = {1: "#9dc3e6", 2: "#2e75b6", 3: "#1f4e79"}

plt.rcParams.update({"figure.dpi": 150, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})


def _save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{name}.png")
    plt.close(fig)


def _mark_outages(ax) -> None:
    for o in load_yaml("outages")["outages"]:
        for w in o["weeks"]:
            ax.axvline(pd.Timestamp(w), color="grey", lw=0.6, ls=":")
    for r in load_yaml("outages")["regimes"]:
        ax.axvspan(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]), color="grey", alpha=0.08)


def a1_figures(weekly: pd.DataFrame, venues: pd.DataFrame) -> None:
    w = weekly.dropna(subset=["n_days"]).copy()

    # Figure 1: overnight ADV by venue (Tier 1 + Tier 2), stacked.
    fig, ax = plt.subplots(figsize=(7, 3.2))
    cols = {}
    for m in VENUE_COLORS:
        c = [x for x in w.columns if x.startswith("shares_") and x.endswith(f"_{m}")]
        if c:
            cols[m] = w[c].sum(axis=1) / w["n_days"] / 1e6
    ax.stackplot(w["week"], *cols.values(), labels=list(cols),
                 colors=[VENUE_COLORS[m] for m in cols])
    _mark_outages(ax)
    ax.set_ylabel("Average daily shares (millions)")
    ax.set_title("Overnight ATS volume by venue, NMS Tier 1 + Tier 2 (weekly)")
    ax.legend(loc="upper left", frameon=False, ncol=4)
    _save(fig, "fig1_overnight_adv_by_venue")

    # Figure 2: share of Tier 1 consolidated volume and top-10 concentration.
    fig, ax1 = plt.subplots(figsize=(7, 3.2))
    ax1.plot(w["week"], 100 * w["ovn_share_of_nms"], color="#1f4e79",
             label="Overnight-ATS share of NMS share volume (left)")
    ax1.set_ylabel("% of NMS volume (Cboe)")
    ax2 = ax1.twinx()
    ax2.plot(w["week"], 100 * w["top10_share"], color="#c55a11", lw=1,
             label="Top-10 symbols' share of overnight volume (right)")
    ax2.set_ylabel("% of overnight volume")
    ax2.grid(False)
    _mark_outages(ax1)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)
    ax1.set_title("Overnight share of volume and concentration (Tier 1 + Tier 2)")
    fig.text(0.01, 0.01, "NMS volume: Cboe Exchange, Inc.", fontsize=6, color="grey")
    _save(fig, "fig2_share_and_concentration")

    # Figure 3: venue market shares by quarter.
    fig, ax = plt.subplots(figsize=(7, 3))
    v = venues.set_index("quarter")[[m for m in VENUE_COLORS if m in venues.columns]]
    bottom = np.zeros(len(v))
    for m in v.columns:
        ax.bar(v.index, 100 * v[m], bottom=bottom, color=VENUE_COLORS[m], label=m)
        bottom += 100 * v[m].to_numpy()
    ax.set_ylabel("% of overnight-ATS shares")
    ax.set_title("Overnight venue market shares by quarter", pad=22)
    ax.legend(frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.tick_params(axis="x", rotation=45)
    _save(fig, "fig3_venue_shares")


def a3_figures(ev: pd.DataFrame, wpc: pd.DataFrame) -> None:
    # Figure 4: binned scatter r_d on r_n for earnings events, by intensity tercile.
    earn = ev[ev["sample"] == "earnings"]
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for k, g in earn.groupby("tercile"):
        bins = pd.qcut(g["r_n"], 20, duplicates="drop")
        b = g.groupby(bins, observed=True)[["r_n", "r_d"]].mean()
        ax.plot(100 * b["r_n"], 100 * b["r_d"], "o-", ms=3, lw=0.8, color=TERC_COLORS[int(k)],
                label=f"intensity tercile {int(k)}")
    ax.axhline(0, color="k", lw=0.5)
    ax.axvline(0, color="k", lw=0.5)
    ax.set_xlabel("Night return r_n (%), 20 bins")
    ax.set_ylabel("Next-day return r_d (%)")
    ax.set_title("After-close earnings: does the open over- or under-shoot?")
    ax.legend(frameon=False)
    _save(fig, "fig4_binscatter_earnings")

    # Figure 5: WPC of the night by tercile, earnings vs baseline.
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    d = wpc[wpc["tercile"] > 0]
    for j, (sample, color) in enumerate([("earnings", "#1f4e79"), ("baseline", "#a5a5a5")]):
        g = d[d["sample"] == sample]
        x = g["tercile"].to_numpy() + (j - 0.5) * 0.35
        ax.bar(x, g["wpc_night"], width=0.35, color=color, label=sample)
        ax.errorbar(x, g["wpc_night"], yerr=[g["wpc_night"] - g["ci_lo"],
                                             g["ci_hi"] - g["wpc_night"]],
                    fmt="none", color="k", lw=0.8, capsize=2)
    ax.axhline(1, color="k", lw=0.5, ls="--")
    ax.set_xticks([1, 2, 3], ["low", "middle", "high"])
    ax.set_xlabel("Overnight-trading intensity tercile (pre-event 4 weeks)")
    ax.set_ylabel("WPC of night (close to open)")
    ax.set_title("Share of the close-to-close move in the opening price")
    ax.legend(frameon=False)
    _save(fig, "fig5_wpc_by_tercile")

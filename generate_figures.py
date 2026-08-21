"""
UIFPI — Figure Generation
Creates all charts needed for the research paper and SSEF poster.
Saves 4 PNG files at 300 DPI to figures/.

Figures:
  fig1 — UIFPI vs Official CPI per country (2×4 grid)
  fig2 — Granger causality significance/lead times bar chart (calendar-true US spec)
  fig4 — Directional prediction accuracy vs AR1 baseline
  fig5 — Country sample map

fig3 (formal vs informal pass-through) was removed 2026-08-20: the paper
makes no pass-through/magnitude claim in this draft (see paper §7.1, §8
item 2) pending re-estimation on the calendar-true CPI construction.
"""

import json
import os
import sqlite3
import warnings
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DB_PATH    = "uifpi.db"
INDEX_CSV_FALLBACK = "uifpi_index.csv"  # used when uifpi.db is unavailable (not tracked in git)
CPI_DIR    = "cpi_data"
FIG_DIR    = "figures"
RESULTS_DIR = "analysis_results"

COUNTRIES = [
    "Singapore", "Malaysia", "Indonesia", "Thailand",
    "India", "United States", "United Kingdom", "Australia",
]

COUNTRY_CPI_FILES = {
    "Singapore":     "monthly_cpi_sg.json",
    "Malaysia":      None,
    "Indonesia":     "monthly_cpi_id.json",
    "Thailand":      "monthly_cpi_th.json",
    "India":         "monthly_cpi_in.json",
    "United States": "monthly_cpi_us.json",
    "United Kingdom":"monthly_cpi_gb.json",
    "Australia":     "monthly_cpi_au.json",
}

DEVELOPMENT_STATUS = {
    "Singapore":     "Developed",
    "Malaysia":      "Emerging",
    "Indonesia":     "Emerging",
    "Thailand":      "Emerging",
    "India":         "Emerging",
    "United States": "Developed",
    "United Kingdom":"Developed",
    "Australia":     "Developed",
}

COUNTRY_COORDS = {
    "Singapore":     (103.8,  1.4),
    "Malaysia":      (109.7,  4.2),
    "Indonesia":     (117.9, -0.8),
    "Thailand":      (101.0, 13.8),
    "India":         ( 78.9, 20.6),
    "United States": (-95.7, 37.1),
    "United Kingdom":( -3.4, 55.4),
    "Australia":     (133.8,-25.3),
}

# Colours
FORMAL_COLOUR   = "#2196F3"   # blue
INFORMAL_COLOUR = "#FF9800"   # orange
COMBINED_COLOUR = "#4CAF50"   # green
CPI_COLOUR      = "#F44336"   # red
DEVELOPED_COL   = "#1565C0"
EMERGING_COL    = "#E65100"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_cpi(country: str) -> Optional[pd.Series]:
    cpi_file = COUNTRY_CPI_FILES.get(country)
    if not cpi_file:
        return None
    path = os.path.join(CPI_DIR, cpi_file)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = json.load(f)
    rows = raw.get("data", [])
    if not rows:
        return None
    s = pd.Series(
        {r["period"]: float(r["cpi"]) for r in rows},
        name="cpi",
    )
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def load_index(country: str) -> Optional[pd.DataFrame]:
    if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT year_month, formal_index, informal_index, uifpi_combined "
            "FROM uifpi_index WHERE country = ? ORDER BY year_month",
            conn, params=[country],
        )
        conn.close()
    elif os.path.exists(INDEX_CSV_FALLBACK):
        # uifpi.db is gitignored and not always present locally; fall back to
        # the flat CSV export of the same uifpi_index table (kept in sync by
        # the monthly ingest). Same columns, same source of truth.
        full = pd.read_csv(INDEX_CSV_FALLBACK)
        df = full[full["country"] == country][
            ["year_month", "formal_index", "informal_index", "uifpi_combined"]
        ].sort_values("year_month")
    else:
        return None
    if df.empty:
        return None
    df["dt"] = pd.to_datetime(df["year_month"])
    return df.set_index("dt")


def load_granger_results() -> dict:
    path = os.path.join(RESULTS_DIR, "granger_results.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def load_gap_robustness() -> dict:
    """Calendar-true US Granger spec (analysis_results/gap_robustness.json).
    granger_results.json's "United States" entry is the deprecated
    gap-mixing spec (F=6.0336, p=0.021) — do not use it as the headline.
    """
    path = os.path.join(RESULTS_DIR, "gap_robustness.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def granger_results_calendar_true() -> dict:
    """Per-country Granger results with the United States entry patched to
    the calendar-true spec. India/Malaysia/etc. in granger_results.json are
    already the correct, non-deprecated values — only the US entry used the
    gap-mixing method that was superseded on 2026-07-06.
    """
    granger = load_granger_results()
    gap = load_gap_robustness()
    ct = gap.get("specs", {}).get("calendar_true")
    if ct:
        us = dict(granger.get("United States", {}))
        us["granger_p_value"] = ct["p_analytic"]
        us["granger_f_statistic"] = ct["F"]
        us["n_obs"] = ct["n"]
        us["lead_months"] = 1
        us["aic_lag"] = None  # calendar-true is a fixed lag-1 spec, not AIC-selected
        us["permutation_p_shuffle"] = ct.get("p_permutation", {}).get("shuffle")
        us["permutation_p_block"] = ct.get("p_permutation", {}).get("block")
        # Deprecated gap-mixing pass-through is not carried forward — the
        # paper makes no pass-through/magnitude claim in this draft.
        for k in ("pass_through_formal", "pass_through_se", "pass_through_p_value",
                  "pass_through_ci_low", "pass_through_ci_high", "pass_through_significant"):
            us[k] = None
        us["granger_significant"] = None  # not a clean true/false — see fig2 colour logic
        us["note"] = "calendar-true spec (analysis_results/gap_robustness.json); analytic p<0.05 but not confirmed by permutation checks — not a validated finding"
        granger["United States"] = us
    return granger


def load_benchmark_results() -> dict:
    path = os.path.join(RESULTS_DIR, "benchmark_comparison.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Normalise series to 100 at first observation
# ---------------------------------------------------------------------------

def normalise(s: pd.Series) -> pd.Series:
    s = s.dropna()
    if s.empty:
        return s
    base = s.iloc[0]
    if base == 0:
        base = 1.0
    return (s / base) * 100


# ---------------------------------------------------------------------------
# Figure 1 — UIFPI vs CPI per country
# ---------------------------------------------------------------------------

def fig1_index_comparison():
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    axes = axes.flatten()

    for idx, country in enumerate(COUNTRIES):
        ax = axes[idx]
        index_df = load_index(country)
        cpi_s    = load_cpi(country)

        has_data = False

        if index_df is not None and not index_df.empty:
            u = normalise(index_df["uifpi_combined"])
            f = normalise(index_df["formal_index"])
            i = normalise(index_df["informal_index"])
            if not u.empty:
                ax.plot(u.index, u.values, color=COMBINED_COLOUR, lw=2.0,
                        label="UIFPI Combined", zorder=3)
                has_data = True
            if not f.empty and f.nunique() > 1:
                ax.plot(f.index, f.values, color=FORMAL_COLOUR, lw=1.2,
                        ls="--", alpha=0.7, label="Formal")
            if not i.empty and i.nunique() > 1:
                ax.plot(i.index, i.values, color=INFORMAL_COLOUR, lw=1.2,
                        ls=":", alpha=0.7, label="Informal")

        if cpi_s is not None:
            c = normalise(cpi_s)
            ax.plot(c.index, c.values, color=CPI_COLOUR, lw=2.0,
                    marker="o", ms=4, label="Official CPI", zorder=3)
            has_data = True

        if not has_data:
            ax.text(0.5, 0.5, "No data available",
                    ha="center", va="center", transform=ax.transAxes,
                    color="grey", fontsize=9)

        ax.set_title(f"UIFPI vs Official CPI — {country}", fontsize=8.5, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("Index (base = 100)", fontsize=7)
        ax.tick_params(axis="x", labelsize=6, rotation=30)
        ax.tick_params(axis="y", labelsize=7)
        ax.set_xlim(pd.Timestamp("2017-01-01"), pd.Timestamp("2026-12-31"))
        ax.axhline(100, color="black", lw=0.5, ls="--", alpha=0.3)
        ax.grid(axis="y", alpha=0.25)

        if idx == 0:
            ax.legend(fontsize=6.5, loc="upper left")

    # shared legend
    handles = [
        mpatches.Patch(color=COMBINED_COLOUR, label="UIFPI Combined"),
        mpatches.Patch(color=FORMAL_COLOUR,   label="Formal Sector"),
        mpatches.Patch(color=INFORMAL_COLOUR, label="Informal Sector"),
        mpatches.Patch(color=CPI_COLOUR,      label="Official CPI"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, 0.0))

    fig.suptitle("UIFPI vs Official CPI: Indexed Price Levels (Base = 100)",
                 fontsize=12, fontweight="bold", y=1.01)
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    out = os.path.join(FIG_DIR, "fig1_index_comparison.png")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Figure 2 — Granger lead times
# ---------------------------------------------------------------------------

def fig2_lead_times():
    granger = granger_results_calendar_true()

    countries  = []
    lead_times = []
    p_values   = []
    not_validated = []  # True when analytic p<0.05 but permutation checks don't confirm it
    for c in COUNTRIES:
        r = granger.get(c, {})
        countries.append(c)
        lt = r.get("lead_months")
        pv = r.get("granger_p_value")
        lead_times.append(lt if lt is not None else 0)
        p_values.append(pv if pv is not None else 1.0)

        perm_shuffle = r.get("permutation_p_shuffle")
        perm_block = r.get("permutation_p_block")
        if pv is not None and perm_shuffle is not None and perm_block is not None:
            # confirmed-significant only if analytic AND both permutation
            # checks clear 0.05 — otherwise it's not a clean rejection
            not_validated.append(max(pv, perm_shuffle, perm_block) >= 0.05)
        else:
            not_validated.append(False)

    # bar colours by significance; a distinct hatched "not validated" bucket
    # is used when the analytic p clears 0.05 but permutation checks don't
    # confirm it (this applies to the US calendar-true result: p=0.0499
    # analytic vs 0.052/0.069 permutation) — this must not read as a clean
    # "significant" green bar per the paper's own framing (§6.1, §7.1, §9).
    colours = []
    hatches = []
    for pv, nv in zip(p_values, not_validated):
        if nv:
            colours.append("#FFC107")   # amber — same family as "marginal"
            hatches.append("//")
        elif pv < 0.05:
            colours.append("#4CAF50")   # green
            hatches.append(None)
        elif pv < 0.10:
            colours.append("#FFC107")   # yellow
            hatches.append(None)
        else:
            colours.append("#F44336")   # red
            hatches.append(None)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(countries))
    bars = ax.bar(x, lead_times, color=colours, edgecolor="white", linewidth=0.5)
    for bar, h in zip(bars, hatches):
        if h:
            bar.set_hatch(h)
            bar.set_edgecolor("#7A5C00")

    # annotate data status / not-validated caveat
    for i, (lt, pv, nv) in enumerate(zip(lead_times, p_values, not_validated)):
        if pv >= 1.0 - 1e-9:
            ax.text(x[i], 0.1, "insuff.\ndata", ha="center", va="bottom",
                    fontsize=7, color="grey")
        elif nv:
            ax.text(x[i], lead_times[i] + 0.08, "not validated\n(permutation p ≥ .05)",
                    ha="center", va="bottom", fontsize=6.5, color="#7A5C00")

    ax.set_xticks(x)
    ax.set_xticklabels(countries, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Lead Time (months)", fontsize=10)
    ax.set_title("Granger Causality by Country: UIFPI → Official CPI\n(calendar-true spec, United States)",
                 fontsize=11, fontweight="bold")
    ax.set_ylim(0, max(max(lead_times) + 1, 4))

    # legend
    legend_elements = [
        mpatches.Patch(facecolor="#4CAF50", label="p < 0.05 (significant, permutation-confirmed)"),
        mpatches.Patch(facecolor="#FFC107", hatch="//", edgecolor="#7A5C00",
                        label="Analytic p < 0.05, not confirmed by permutation\n(most interesting, not validated)"),
        mpatches.Patch(facecolor="#FFC107", label="p < 0.10 (marginal)"),
        mpatches.Patch(facecolor="#F44336", label="Not significant"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=7)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out = os.path.join(FIG_DIR, "fig2_lead_times.png")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Figure 4 — Directional prediction accuracy
# ---------------------------------------------------------------------------

def fig4_benchmark():
    benchmark = load_benchmark_results()

    countries_b, ar1_acc, uifpi_acc = [], [], []
    for c in COUNTRIES:
        r = benchmark.get(c, {})
        if "skip" in r:
            continue
        a = r.get("ar1_accuracy")
        u = r.get("uifpi_accuracy")
        if a is None or u is None:
            continue
        countries_b.append(c)
        ar1_acc.append(a)
        uifpi_acc.append(u)

    if not countries_b:
        # placeholder
        countries_b = ["Pending data collection"]
        ar1_acc     = [0.5]
        uifpi_acc   = [0.5]
        no_data = True
    else:
        no_data = False

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(countries_b))
    w = 0.35
    ax.bar(x - w / 2, ar1_acc,   width=w, color="#607D8B", label="AR(1) Naive Baseline", alpha=0.85)
    ax.bar(x + w / 2, uifpi_acc, width=w, color=COMBINED_COLOUR, label="UIFPI Model",    alpha=0.85)

    ax.axhline(0.5, color="black", ls="--", lw=1.5, label="Random chance (50%)")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(countries_b, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Directional Accuracy", fontsize=10)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1))
    ax.set_title("Directional Prediction Accuracy: UIFPI vs AR(1) Baseline",
                 fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    if no_data:
        ax.text(0.5, 0.7, "Benchmark results pending full data collection\n"
                           "(requires ≥5 common years of UIFPI + CPI data)",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=10, color="grey",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    plt.tight_layout()
    out = os.path.join(FIG_DIR, "fig4_benchmark.png")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Figure 5 — Country sample map
# ---------------------------------------------------------------------------

def fig5_country_map():
    try:
        import geopandas as gpd
        from matplotlib.lines import Line2D

        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        fig, ax = plt.subplots(figsize=(14, 7))
        world.plot(ax=ax, color="#E8E8E8", edgecolor="#AAAAAA", linewidth=0.3)

        for country, (lon, lat) in COUNTRY_COORDS.items():
            status = DEVELOPMENT_STATUS[country]
            colour = DEVELOPED_COL if status == "Developed" else EMERGING_COL
            ax.scatter(lon, lat, s=200, color=colour, edgecolors="white",
                       linewidth=1.5, zorder=5)
            # label placement tweaks
            offset_x = 3
            offset_y = 3
            if country == "Malaysia":
                offset_y = -6
            elif country == "Singapore":
                offset_x = 4; offset_y = -6
            elif country == "Indonesia":
                offset_y = -7
            ax.annotate(
                country,
                xy=(lon, lat), xytext=(lon + offset_x, lat + offset_y),
                fontsize=7.5, fontweight="bold", color="#222222",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="grey"),
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          alpha=0.75, edgecolor="none"),
            )

        ax.set_xlim(-170, 170)
        ax.set_ylim(-60, 80)
        ax.set_title("UIFPI Country Sample: 8 Countries Across Developed and Emerging Economies",
                     fontsize=11, fontweight="bold")
        ax.axis("off")

        legend_elements = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor=DEVELOPED_COL,
                   markersize=10, label="Developed (4)"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=EMERGING_COL,
                   markersize=10, label="Emerging (4)"),
        ]
        ax.legend(handles=legend_elements, loc="lower left", fontsize=9)

    except Exception:
        # Fallback: scatter on blank axes
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 80)
        ax.set_facecolor("#D6EAF8")
        ax.set_xlabel("Longitude", fontsize=9)
        ax.set_ylabel("Latitude",  fontsize=9)
        ax.set_title("UIFPI Country Sample: 8 Countries Across Developed and Emerging Economies",
                     fontsize=11, fontweight="bold")
        ax.grid(alpha=0.3)

        for country, (lon, lat) in COUNTRY_COORDS.items():
            status = DEVELOPMENT_STATUS[country]
            colour = DEVELOPED_COL if status == "Developed" else EMERGING_COL
            ax.scatter(lon, lat, s=200, color=colour, edgecolors="white",
                       linewidth=1.5, zorder=5)
            ax.annotate(country, xy=(lon, lat), xytext=(lon + 2, lat + 3),
                        fontsize=8, fontweight="bold")

        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor=DEVELOPED_COL,
                   markersize=10, label="Developed (4)"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=EMERGING_COL,
                   markersize=10, label="Emerging (4)"),
        ]
        ax.legend(handles=legend_elements, loc="lower left", fontsize=9)

    plt.tight_layout()
    out = os.path.join(FIG_DIR, "fig5_country_map.png")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    print("Generating figures...")

    fig1_index_comparison()
    fig2_lead_times()
    fig4_benchmark()
    fig5_country_map()

    # verify
    expected = [
        "fig1_index_comparison.png",
        "fig2_lead_times.png",
        "fig4_benchmark.png",
        "fig5_country_map.png",
    ]
    print("\nFigure check:")
    for fname in expected:
        path = os.path.join(FIG_DIR, fname)
        status = "✓" if os.path.exists(path) else "✗"
        size   = os.path.getsize(path) if os.path.exists(path) else 0
        print(f"  {status} {fname} ({size:,} bytes)")

    print("\nAll figures saved to figures/")


if __name__ == "__main__":
    main()

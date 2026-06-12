"""
UIFPI — Dashboard Data Exporter
Reads uifpi_index.csv and analysis_results/granger_results.json,
then writes three JSON files consumed by the Next.js dashboard.

Outputs (in dashboard_data/):
  index_series.json    — per-country monthly time series (UIFPI + CPI)
  country_summary.json — per-country lead time, significance, pass-through
  latest_values.json   — most recent UIFPI and CPI per country

Run order: after granger_analysis.py.
"""

import json
import math
import os
import sys
from typing import Union

import pandas as pd

INDEX_CSV    = "uifpi_index.csv"
GRANGER_JSON = "analysis_results/granger_results.json"
OUT_DIR      = "dashboard_data"


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_round(v, digits=2):
    """Round to digits decimal places; return None for NaN/Inf."""
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, digits)
    except (TypeError, ValueError):
        return None


def load_index(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        print(f"  ⚠  {csv_path} not found — run index_builder.py first.")
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df["year_month"] = df["year_month"].astype(str)
    df = df.sort_values(["country", "year_month"])
    return df


def load_granger(json_path: str) -> dict:
    if not os.path.exists(json_path):
        print(f"  ⚠  {json_path} not found — run granger_analysis.py first.")
        return {}
    with open(json_path) as f:
        return json.load(f)


# ── Builder functions ─────────────────────────────────────────────────────────

def build_index_series(index_df: pd.DataFrame, granger: dict) -> dict:
    """
    Per-country monthly time series combining UIFPI values with CPI where
    available from the Granger results.

    Schema:
    {
      "Singapore": [
        {"month": "2025-01", "uifpi": 100.0, "formal": 100.0,
         "informal": 100.0, "cpi": 102.3, "item_count": 412},
        ...
      ],
      ...
    }
    """
    series: dict = {}

    for country, group in index_df.groupby("country"):
        # Pull CPI series from granger results if present
        cpi_series: dict = {}
        if country in granger:
            for obs in granger[country].get("data", []):
                if "month" in obs and "cpi" in obs:
                    cpi_series[obs["month"]] = obs["cpi"]

        rows = []
        for _, row in group.iterrows():
            ym = row["year_month"]
            rows.append({
                "month":      ym,
                "uifpi":      safe_round(row.get("uifpi_combined")),
                "formal":     safe_round(row.get("formal_index")),
                "informal":   safe_round(row.get("informal_index")),
                "cpi":        safe_round(cpi_series.get(ym)),
                "item_count": int(row["item_count"]) if pd.notna(row.get("item_count")) else 0,
            })
        series[country] = rows

    return series


def build_country_summary(granger: dict, index_df: pd.DataFrame) -> dict:
    """
    Per-country summary of statistical findings.

    Schema:
    {
      "Singapore": {
        "granger_significant":  true,
        "lead_months":          2,
        "pass_through_rate":    0.43,
        "pass_through_pvalue":  0.012,
        "months_of_data":       14,
        "base_month":           "2025-01",
        "latest_uifpi":         108.3,
        "status":               "ok"   // or "insufficient_data"
      },
      ...
    }
    """
    summary: dict = {}

    countries = set(index_df["country"].unique()) | set(granger.keys())

    for country in sorted(countries):
        g = granger.get(country, {})
        c_df = index_df[index_df["country"] == country].sort_values("year_month")

        months_of_data = len(c_df)
        base_month = c_df["year_month"].iloc[0] if months_of_data else None
        latest_uifpi = safe_round(c_df["uifpi_combined"].iloc[-1]) if months_of_data else None

        status = g.get("status", "no_granger_data")

        summary[country] = {
            "granger_significant": g.get("granger_significant"),
            "lead_months":         g.get("lead_months"),
            "pass_through_rate":   safe_round(g.get("pass_through_rate")),
            "pass_through_pvalue": safe_round(g.get("pass_through_pvalue"), 4),
            "months_of_data":      months_of_data,
            "base_month":          base_month,
            "latest_uifpi":        latest_uifpi,
            "status":              status,
        }

    return summary


def build_latest_values(index_df: pd.DataFrame, granger: dict) -> dict:
    """
    Most recent UIFPI and CPI per country, for a top-of-page summary card.

    Schema:
    {
      "Singapore": {
        "month":    "2026-05",
        "uifpi":    112.4,
        "formal":   110.1,
        "informal": 115.8,
        "cpi":      103.7,
        "yoy_change_pct": 8.2     // uifpi change vs 12 months prior, or null
      },
      ...
    }
    """
    latest: dict = {}

    for country, group in index_df.groupby("country"):
        group = group.sort_values("year_month")
        if group.empty:
            continue

        last = group.iloc[-1]

        # YoY change in UIFPI
        yoy_change = None
        if len(group) >= 13:
            prev_uifpi = group.iloc[-13]["uifpi_combined"]
            curr_uifpi = last["uifpi_combined"]
            if pd.notna(prev_uifpi) and pd.notna(curr_uifpi) and prev_uifpi > 0:
                yoy_change = safe_round((curr_uifpi / prev_uifpi - 1) * 100)

        # Most recent CPI from granger data
        cpi_val = None
        if country in granger:
            data = granger[country].get("data", [])
            if data:
                # Take the last obs that has a cpi value
                for obs in reversed(data):
                    if obs.get("cpi") is not None:
                        cpi_val = safe_round(obs["cpi"])
                        break

        latest[country] = {
            "month":          last["year_month"],
            "uifpi":          safe_round(last.get("uifpi_combined")),
            "formal":         safe_round(last.get("formal_index")),
            "informal":       safe_round(last.get("informal_index")),
            "cpi":            cpi_val,
            "yoy_change_pct": yoy_change,
        }

    return latest


# ── Writer ────────────────────────────────────────────────────────────────────

def write_json(obj: Union[dict, list], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {path}  ({os.path.getsize(path):,} bytes)")


# ── Entry point ───────────────────────────────────────────────────────────────

def run(
    index_csv:   str = INDEX_CSV,
    granger_json: str = GRANGER_JSON,
    out_dir:     str = OUT_DIR,
) -> None:
    print("\nDashboard Data Exporter")
    print("─" * 60)

    print("Loading index data …")
    index_df = load_index(index_csv)

    print("Loading Granger results …")
    granger = load_granger(granger_json)

    if index_df.empty and not granger:
        print("  ⚠  No data available — nothing to export.")
        sys.exit(0)

    countries = sorted(
        set(index_df["country"].unique()) if not index_df.empty else set()
    )
    print(f"  {len(index_df):,} index rows across {len(countries)} countries")
    print(f"  {len(granger)} countries have Granger results\n")

    print("Building index_series.json …")
    index_series = build_index_series(index_df, granger)
    write_json(index_series, os.path.join(out_dir, "index_series.json"))

    print("Building country_summary.json …")
    country_summary = build_country_summary(granger, index_df)
    write_json(country_summary, os.path.join(out_dir, "country_summary.json"))

    print("Building latest_values.json …")
    latest_values = build_latest_values(index_df, granger)
    write_json(latest_values, os.path.join(out_dir, "latest_values.json"))

    print(f"\nAll dashboard JSON written to {out_dir}/")


if __name__ == "__main__":
    run()

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
import sqlite3
import sys
from typing import Optional, Union

import pandas as pd

from data_quality import QUARANTINED_SLICES

INDEX_CSV    = "uifpi_index.csv"
GRANGER_JSON = "analysis_results/granger_results.json"
DB_PATH      = "uifpi.db"
OUT_DIR      = "dashboard_data"
# Next.js dashboard reads JSON from this path at build time (see
# dashboard/lib/data.ts). Keep both in sync so Vercel deployments pick up
# new numbers without a manual copy.
DASHBOARD_PUBLIC_DATA = os.path.join("dashboard", "public", "data")

# Mirrors granger_analysis.COUNTRY_TO_CODE — the 10 active panel countries.
# Kept here so the exporter doesn't have to import from granger_analysis
# (which pulls statsmodels at import time).
COUNTRY_TO_CODE = {
    "Singapore": "SG", "Malaysia": "MY", "Indonesia": "ID",
    "Thailand": "TH", "India": "IN", "United States": "US",
    "United Kingdom": "GB", "Australia": "AU",
    "Vietnam": "VN", "United Arab Emirates": "AE",
}

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


def load_monthly_cpi(db_path: str = DB_PATH) -> dict:
    """Per-country dict of {year_month: cpi_value}, loaded directly from the
    monthly_cpi table. Replicates granger_analysis.load_cpi_from_db so the
    dashboard's CPI line matches the series the Granger test consumed.

    Jan-only series (SG/TH/ID — World Bank annual) are reindexed to monthly
    and linearly interpolated, matching the granger loader's behavior.
    """
    result: dict = {}
    if not os.path.exists(db_path):
        return result
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='monthly_cpi'"
        )
        if not cur.fetchone():
            return result
        for country, code in COUNTRY_TO_CODE.items():
            df = pd.read_sql_query(
                "SELECT year_month, cpi_value FROM monthly_cpi "
                "WHERE country_code=? AND cpi_value IS NOT NULL "
                "ORDER BY year_month",
                conn, params=(code,),
            )
            if df.empty:
                continue
            s = pd.Series(
                df["cpi_value"].values,
                index=pd.PeriodIndex(df["year_month"], freq="M"),
            ).sort_index()
            if all(p.month == 1 for p in s.index):
                full_range = pd.period_range(
                    s.index.min(), s.index.max(), freq="M"
                )
                s = s.reindex(full_range).interpolate(method="index")
            result[country] = {
                str(p): float(v) for p, v in s.items() if pd.notna(v)
            }
    finally:
        conn.close()
    return result


# ── Builder functions ─────────────────────────────────────────────────────────

def build_index_series(index_df: pd.DataFrame, cpi_lookup: dict) -> dict:
    """
    Per-country monthly time series combining UIFPI values with CPI from
    the monthly_cpi table. CPI months that fall outside the UIFPI date
    range are appended so the chart can render the full CPI history even
    when UIFPI coverage is shorter (or the other way around — e.g. US
    UIFPI runs past the latest OECD HICP month, so the CPI line ends
    cleanly while UIFPI continues).

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

    all_countries = (
        set(index_df["country"].unique()) | set(cpi_lookup.keys())
    )

    for country in sorted(all_countries):
        group = index_df[index_df["country"] == country]
        cpi_series = cpi_lookup.get(country, {})

        uifpi_months = set(group["year_month"].astype(str))
        cpi_only_months = sorted(set(cpi_series.keys()) - uifpi_months)

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
        for ym in cpi_only_months:
            rows.append({
                "month":      ym,
                "uifpi":      None,
                "formal":     None,
                "informal":   None,
                "cpi":        safe_round(cpi_series.get(ym)),
                "item_count": 0,
            })
        rows.sort(key=lambda r: r["month"])
        series[country] = rows

    return series


# Same fallback rates index_builder.py uses to backfill price_usd when it's
# null. Single source of truth in fx_rates.py.
from fx_rates import FALLBACK_RATES


def _empty_country_stats() -> dict:
    return {
        "items_formal": 0,
        "items_informal": 0,
        "restaurants_formal": 0,
        "restaurants_informal": 0,
        "avg_price_formal_usd": None,
        "avg_price_informal_usd": None,
    }


# DB-level sector value → output JSON field-name suffix. The taxonomy
# was renamed from formal/informal to chain/independent (2026-06-21) but
# the JSON schema keys (items_formal, items_informal, etc.) are kept for
# backward compatibility with existing consumers of country_summary.json.
# Sources excluded from ALL dashboard aggregates — keep in sync with
# index_builder.EXCLUDED_SOURCES (DoorDash dilutes the US Granger signal;
# raw rows stay in `prices`). See CLAUDE.md.
EXCLUDED_SOURCES = ("wayback-doordash",)

DB_SECTOR_TO_FIELD = {"chain": "formal", "independent": "informal"}


def load_price_counts(db_path: str = DB_PATH) -> dict:
    """Per-country, per-sector item count, distinct-restaurant count, and
    mean price_usd. Backfills null price_usd from `price` + `currency`
    using the same FALLBACK_RATES as index_builder.py.
    """
    counts: dict = {}
    if not os.path.exists(db_path):
        return counts
    try:
        conn = sqlite3.connect(db_path)
        placeholders = ",".join("?" for _ in EXCLUDED_SOURCES)
        cur = conn.execute(
            "SELECT country, sector, restaurant_name, price, currency, "
            "price_usd, source "
            "FROM prices "
            "WHERE price IS NOT NULL AND price > 0 "
            f"AND source NOT IN ({placeholders})",
            EXCLUDED_SOURCES,
        )
        agg: dict = {}
        quarantined_dropped = 0
        for country, sector, restaurant, price, currency, price_usd, source in cur.fetchall():
            if not country:
                continue
            if (country, source) in QUARANTINED_SLICES:
                quarantined_dropped += 1
                continue
            sector_key = (sector or "").lower()
            if sector_key not in DB_SECTOR_TO_FIELD:
                continue
            usd = price_usd
            if usd is None or usd <= 0:
                rate = FALLBACK_RATES.get((currency or "").upper())
                if rate and rate > 0:
                    usd = price / rate
            bucket = agg.setdefault((country, sector_key),
                                    {"items": 0, "restaurants": set(),
                                     "usd_sum": 0.0, "usd_n": 0})
            bucket["items"] += 1
            if restaurant:
                bucket["restaurants"].add(restaurant)
            if usd and usd > 0:
                bucket["usd_sum"] += usd
                bucket["usd_n"]   += 1
        conn.close()
        if quarantined_dropped > 0:
            print(f"  Quarantined {quarantined_dropped:,} rows: "
                  f"{list(QUARANTINED_SLICES)} (kept in raw DB)")

        for (country, sector_key), b in agg.items():
            field = DB_SECTOR_TO_FIELD[sector_key]
            row = counts.setdefault(country, _empty_country_stats())
            row[f"items_{field}"]       = b["items"]
            row[f"restaurants_{field}"] = len(b["restaurants"])
            row[f"avg_price_{field}_usd"] = (
                round(b["usd_sum"] / b["usd_n"], 2) if b["usd_n"] else None
            )
    except Exception as e:
        print(f"  ⚠  price-count query failed: {e}")
    return counts


def build_country_summary(granger: dict, index_df: pd.DataFrame,
                           cpi_lookup: dict,
                           price_counts: Optional[dict] = None) -> dict:
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
    if price_counts is None:
        price_counts = load_price_counts()

    countries = set(index_df["country"].unique()) | set(granger.keys()) | set(price_counts.keys())

    for country in sorted(countries):
        g = granger.get(country, {})
        c_df = index_df[index_df["country"] == country].sort_values("year_month")

        months_of_data = len(c_df)
        base_month = c_df["year_month"].iloc[0] if months_of_data else None

        # Prefer the latest row with a real uifpi value over a newer-but-null
        # row (mirrors build_latest_values so the homepage card and country
        # page agree).
        with_uifpi = c_df[c_df["uifpi_combined"].notna()] if months_of_data else c_df
        latest_uifpi = (
            safe_round(with_uifpi["uifpi_combined"].iloc[-1])
            if not with_uifpi.empty else None
        )

        # Latest CPI value for this country, taken from monthly_cpi.
        latest_cpi = None
        cpi_series = cpi_lookup.get(country, {})
        if cpi_series:
            latest_cpi = safe_round(cpi_series[max(cpi_series.keys())])

        status = g.get("status", "no_granger_data")
        pc = price_counts.get(country, _empty_country_stats())

        summary[country] = {
            "granger_significant":      g.get("granger_significant"),
            "granger_p_value":          safe_round(g.get("granger_p_value"), 4),
            "lead_months":              g.get("lead_months"),
            # The Next.js country page reads pass_through_formal /
            # pass_through_informal directly. granger_analysis.py only
            # produces pass_through_formal for now; surface both for shape.
            "pass_through_formal":      safe_round(g.get("pass_through_formal"), 4),
            "pass_through_informal":    safe_round(g.get("pass_through_informal"), 4),
            "pass_through_significant": g.get("pass_through_significant"),
            "r_squared":                safe_round(g.get("r_squared"), 4),
            "n_obs":                    g.get("n_obs"),
            "months_of_data":           months_of_data,
            "base_month":               base_month,
            "latest_uifpi":             latest_uifpi,
            "latest_cpi":               latest_cpi,
            "items_formal":             pc["items_formal"],
            "items_informal":           pc["items_informal"],
            "restaurants_formal":       pc["restaurants_formal"],
            "restaurants_informal":     pc["restaurants_informal"],
            "avg_price_formal_usd":     pc["avg_price_formal_usd"],
            "avg_price_informal_usd":   pc["avg_price_informal_usd"],
            "status":                   status,
        }

    return summary


def build_latest_values(index_df: pd.DataFrame, cpi_lookup: dict,
                         price_counts: Optional[dict] = None) -> dict:
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
    price_counts = price_counts or {}

    for country, group in index_df.groupby("country"):
        group = group.sort_values("year_month")
        if group.empty:
            continue

        # Prefer the most recent row that actually has a uifpi value over a
        # newer-but-null row (e.g. when this month's basket hasn't matured
        # enough for the stable-basket fallback to produce an index).
        with_values = group[group["uifpi_combined"].notna()]
        last = with_values.iloc[-1] if not with_values.empty else group.iloc[-1]

        # YoY change in UIFPI. Two guards:
        #   1. Look up the row from exactly 12 calendar months prior by
        #      year_month string, not iloc[-13] (the index has gaps; iloc
        #      would compare last with whatever happened to be 13 rows
        #      back, which for Singapore was 2019-06 vs 2026-06 — a
        #      ~7-year delta yielding +612%).
        #   2. Skip when either anchor used the mean-price fallback — the
        #      basket changed completely, so the ratio is not a price
        #      relative and the yoy number would be misleading.
        yoy_change = None
        try:
            curr_period = pd.Period(last["year_month"], freq="M")
            prev_period = (curr_period - 12).strftime("%Y-%m")
            prev_rows = group[group["year_month"] == prev_period]
            if not prev_rows.empty:
                prev_row = prev_rows.iloc[-1]
                prev_note = str(prev_row.get("coverage_note") or "")
                last_note = str(last.get("coverage_note") or "")
                fallback_used = ("mean-price fallback" in prev_note
                                 or "mean-price fallback" in last_note)
                prev_uifpi = prev_row["uifpi_combined"]
                curr_uifpi = last["uifpi_combined"]
                if (not fallback_used
                        and pd.notna(prev_uifpi) and pd.notna(curr_uifpi)
                        and prev_uifpi > 0):
                    yoy_change = safe_round((curr_uifpi / prev_uifpi - 1) * 100)
        except Exception:
            yoy_change = None

        # Most recent CPI from monthly_cpi.
        cpi_val = None
        cpi_series = cpi_lookup.get(country, {})
        if cpi_series:
            cpi_val = safe_round(cpi_series[max(cpi_series.keys())])

        pc = price_counts.get(country, {})
        latest[country] = {
            "month":          last["year_month"],
            "uifpi":          safe_round(last.get("uifpi_combined")),
            "formal":         safe_round(last.get("formal_index")),
            "informal":       safe_round(last.get("informal_index")),
            "cpi":            cpi_val,
            "yoy_change_pct": yoy_change,
            "items_formal":   pc.get("items_formal", 0),
            "items_informal": pc.get("items_informal", 0),
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

    price_counts = load_price_counts()
    cpi_lookup = load_monthly_cpi()
    cpi_coverage = {c: len(s) for c, s in cpi_lookup.items()}
    print(f"  CPI series loaded for {len(cpi_lookup)} countries "
          f"({cpi_coverage})")

    print("Building index_series.json …")
    index_series = build_index_series(index_df, cpi_lookup)
    write_json(index_series, os.path.join(out_dir, "index_series.json"))
    write_json(index_series, os.path.join(DASHBOARD_PUBLIC_DATA, "index_series.json"))

    print("Building country_summary.json …")
    country_summary = build_country_summary(granger, index_df, cpi_lookup, price_counts)
    write_json(country_summary, os.path.join(out_dir, "country_summary.json"))
    write_json(country_summary, os.path.join(DASHBOARD_PUBLIC_DATA, "country_summary.json"))

    print("Building latest_values.json …")
    latest_values = build_latest_values(index_df, cpi_lookup, price_counts)
    write_json(latest_values, os.path.join(out_dir, "latest_values.json"))
    write_json(latest_values, os.path.join(DASHBOARD_PUBLIC_DATA, "latest_values.json"))


    print(f"\nAll dashboard JSON written to {out_dir}/ and {DASHBOARD_PUBLIC_DATA}/")


if __name__ == "__main__":
    run()

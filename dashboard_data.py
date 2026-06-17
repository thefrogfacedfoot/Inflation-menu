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

INDEX_CSV    = "uifpi_index.csv"
GRANGER_JSON = "analysis_results/granger_results.json"
DB_PATH      = "uifpi.db"
OUT_DIR      = "dashboard_data"
# Next.js dashboard reads JSON from this path at build time (see
# dashboard/lib/data.ts). Keep both in sync so Vercel deployments pick up
# new numbers without a manual copy.
DASHBOARD_PUBLIC_DATA = os.path.join("dashboard", "public", "data")

# Proxy-only countries get an additional floor_data.json export with
# Numbeo / Big Mac / World Bank CPI series. No item-level UIFPI.
PROXY_COUNTRIES = [
    # (country_name, iso2, iso3, local_currency)
    ("Mexico", "MX", "MEX", "MXN"),
]


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


# Same fallback rates index_builder.py uses to backfill price_usd when it's
# null. Kept in sync so the dashboard averages reflect what the index uses.
FALLBACK_RATES = {
    "SGD": 1.35, "MYR": 4.70, "IDR": 15_750.0, "THB": 36.0,
    "INR": 83.5, "USD": 1.0, "GBP": 0.79, "AUD": 1.55,
}


def _empty_country_stats() -> dict:
    return {
        "items_formal": 0,
        "items_informal": 0,
        "restaurants_formal": 0,
        "restaurants_informal": 0,
        "avg_price_formal_usd": None,
        "avg_price_informal_usd": None,
    }


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
        cur = conn.execute(
            "SELECT country, sector, restaurant_name, price, currency, price_usd "
            "FROM prices "
            "WHERE price IS NOT NULL AND price > 0"
        )
        agg: dict = {}
        for country, sector, restaurant, price, currency, price_usd in cur.fetchall():
            if not country:
                continue
            sector_key = (sector or "").lower()
            if sector_key not in ("formal", "informal"):
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

        for (country, sector_key), b in agg.items():
            row = counts.setdefault(country, _empty_country_stats())
            row[f"items_{sector_key}"]       = b["items"]
            row[f"restaurants_{sector_key}"] = len(b["restaurants"])
            row[f"avg_price_{sector_key}_usd"] = (
                round(b["usd_sum"] / b["usd_n"], 2) if b["usd_n"] else None
            )
    except Exception as e:
        print(f"  ⚠  price-count query failed: {e}")
    return counts


def build_country_summary(granger: dict, index_df: pd.DataFrame,
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

        # Latest CPI value for this country, if granger data carries one.
        latest_cpi = None
        for obs in reversed(g.get("data", []) or []):
            if obs.get("cpi") is not None:
                latest_cpi = safe_round(obs["cpi"])
                break

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


def build_latest_values(index_df: pd.DataFrame, granger: dict,
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

def build_floor_data(db_path: str = DB_PATH) -> dict:
    """Per-proxy-country export of Numbeo, Big Mac, and World Bank CPI
    series. Consumed by the dashboard's proxy-country page (Mexico).

    Schema:
    {
      "Mexico": {
        "iso2":     "MX",
        "currency": "MXN",
        "numbeo_inexpensive": [{"year": 2018, "value": 8.42}, ...],
        "numbeo_midrange":    [{"year": 2018, "value": 30.10}, ...],
        "bigmac_usd":         [{"year": "2018-01-01", "value": 2.50}, ...],
        "wb_cpi":             [{"year": "2018-01", "value": 102.1}, ...]
      }
    }
    """
    out: dict = {}
    if not os.path.exists(db_path):
        return out
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for country, iso2, iso3, currency in PROXY_COUNTRIES:
            # Numbeo: 'Meal, Inexpensive Restaurant' & 'Meal for 2 People...'
            # Values are USD-normalised in the table; the dashboard renders
            # them as USD-equivalent local-currency proxies.
            inexp = cur.execute(
                "SELECT year, value FROM numbeo_index "
                "WHERE iso2 = ? AND indicator LIKE 'Meal, Inexpensive%' "
                "ORDER BY year",
                (iso2,)
            ).fetchall()
            midrange = cur.execute(
                "SELECT year, value FROM numbeo_index "
                "WHERE iso2 = ? AND indicator LIKE 'Meal for 2 People%' "
                "ORDER BY year",
                (iso2,)
            ).fetchall()
            bigmac = cur.execute(
                "SELECT date, dollar_price FROM bigmac_index "
                "WHERE iso3 = ? AND dollar_price IS NOT NULL "
                "ORDER BY date",
                (iso3,)
            ).fetchall()
            cpi = cur.execute(
                "SELECT year_month, cpi_value FROM monthly_cpi "
                "WHERE country_code = ? AND cpi_value IS NOT NULL "
                "ORDER BY year_month",
                (iso2,)
            ).fetchall()
            out[country] = {
                "iso2":     iso2,
                "currency": currency,
                "numbeo_inexpensive": [
                    {"year": y, "value": safe_round(v, 2)} for y, v in inexp
                ],
                "numbeo_midrange": [
                    {"year": y, "value": safe_round(v, 2)} for y, v in midrange
                ],
                "bigmac_usd": [
                    {"year": d, "value": safe_round(v, 2)} for d, v in bigmac
                ],
                "wb_cpi": [
                    {"year": ym, "value": safe_round(v, 1)} for ym, v in cpi
                ],
            }
        conn.close()
    except Exception as e:
        print(f"  ⚠  floor-data query failed: {e}")
    return out


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

    print("Building index_series.json …")
    index_series = build_index_series(index_df, granger)
    write_json(index_series, os.path.join(out_dir, "index_series.json"))
    write_json(index_series, os.path.join(DASHBOARD_PUBLIC_DATA, "index_series.json"))

    print("Building country_summary.json …")
    country_summary = build_country_summary(granger, index_df, price_counts)
    write_json(country_summary, os.path.join(out_dir, "country_summary.json"))
    write_json(country_summary, os.path.join(DASHBOARD_PUBLIC_DATA, "country_summary.json"))

    print("Building latest_values.json …")
    latest_values = build_latest_values(index_df, granger, price_counts)
    write_json(latest_values, os.path.join(out_dir, "latest_values.json"))
    write_json(latest_values, os.path.join(DASHBOARD_PUBLIC_DATA, "latest_values.json"))

    print("Building floor_data.json …")
    floor_data = build_floor_data()
    write_json(floor_data, os.path.join(out_dir, "floor_data.json"))
    write_json(floor_data, os.path.join(DASHBOARD_PUBLIC_DATA, "floor_data.json"))

    print(f"\nAll dashboard JSON written to {out_dir}/ and {DASHBOARD_PUBLIC_DATA}/")


if __name__ == "__main__":
    run()

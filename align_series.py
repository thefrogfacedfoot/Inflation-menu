"""
UIFPI — Series Alignment for Granger Causality Testing
Merges uifpi_index and monthly_cpi on year_month per country.
Computes overlapping observations and flags countries with < 24 months.

Outputs:
  aligned_series.csv               — merged monthly data
  analysis_results/alignment_summary.json — overlap stats

Usage:
    python align_series.py [--min-overlap 12] [--export-csv]
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

DB_PATH     = "uifpi.db"
ALIGNED_CSV = "aligned_series.csv"
SUMMARY_JSON = "analysis_results/alignment_summary.json"
MIN_GRANGER  = 24   # minimum monthly observations for Granger test

# Map uifpi_index.country (full name) ↔ monthly_cpi.country_code (2-letter)
COUNTRY_TO_CODE: Dict[str, str] = {
    "Singapore":     "SG",
    "Malaysia":      "MY",
    "Indonesia":     "ID",
    "Thailand":      "TH",
    "India":         "IN",
    "United States": "US",
    "United Kingdom": "GB",
    "Australia":     "AU",
}
CODE_TO_COUNTRY = {v: k for k, v in COUNTRY_TO_CODE.items()}


# ─────────────────────────────────────────────────────────────────────────────
# DB loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_uifpi(conn: sqlite3.Connection) -> Dict[str, Dict[str, float]]:
    """
    Load uifpi_index table.
    Returns {country_name: {year_month: uifpi_combined}}
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='uifpi_index'"
    )
    if not cur.fetchone():
        return {}
    cur = conn.execute(
        "SELECT country, year_month, uifpi_combined "
        "FROM uifpi_index WHERE uifpi_combined IS NOT NULL"
    )
    result: Dict[str, Dict[str, float]] = {}
    for country, ym, val in cur.fetchall():
        result.setdefault(country, {})[ym] = float(val)
    return result


def load_cpi(conn: sqlite3.Connection) -> Dict[str, Dict[str, Tuple[Optional[float], Optional[float]]]]:
    """
    Load monthly_cpi table.
    Returns {country_code: {year_month: (cpi_value, cpi_food)}}
    """
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_cpi'"
    )
    if not cur.fetchone():
        return {}
    cur = conn.execute(
        "SELECT country_code, year_month, cpi_value, cpi_food "
        "FROM monthly_cpi WHERE cpi_value IS NOT NULL"
    )
    result: Dict[str, Dict[str, Tuple]] = {}
    for code, ym, cpi, food in cur.fetchall():
        result.setdefault(code, {})[ym] = (
            float(cpi) if cpi is not None else None,
            float(food) if food is not None else None,
        )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Percent change helper
# ─────────────────────────────────────────────────────────────────────────────

def pct_change(series: Dict[str, float]) -> Dict[str, float]:
    """Compute month-on-month % change for a {year_month: value} dict."""
    sorted_periods = sorted(series.keys())
    result: Dict[str, float] = {}
    for i in range(1, len(sorted_periods)):
        prev = series[sorted_periods[i - 1]]
        curr = series[sorted_periods[i]]
        if prev and prev != 0:
            result[sorted_periods[i]] = round((curr - prev) / prev * 100, 6)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Alignment
# ─────────────────────────────────────────────────────────────────────────────

def align_country(
    country_name: str,
    uifpi_series: Dict[str, float],
    cpi_series: Dict[str, Tuple[Optional[float], Optional[float]]],
) -> List[Dict[str, Any]]:
    """
    Merge UIFPI and CPI on year_month for one country.
    Returns list of aligned row dicts (only months where BOTH values exist).
    """
    uifpi_changes = pct_change(uifpi_series)
    cpi_all       = {ym: v for ym, (v, _) in cpi_series.items() if v is not None}
    cpi_changes   = pct_change(cpi_all)

    # Build union of all periods that appear in UIFPI
    rows = []
    for ym in sorted(uifpi_series.keys()):
        uifpi_val = uifpi_series.get(ym)
        cpi_pair  = cpi_series.get(ym)
        cpi_val   = cpi_pair[0] if cpi_pair else None
        cpi_food  = cpi_pair[1] if cpi_pair else None

        rows.append({
            "year_month":     ym,
            "country":        country_name,
            "country_code":   COUNTRY_TO_CODE.get(country_name, "??"),
            "uifpi_value":    uifpi_val,
            "cpi_value":      cpi_val,
            "cpi_food":       cpi_food,
            "uifpi_change":   uifpi_changes.get(ym),
            "cpi_change":     cpi_changes.get(ym),
            "both_present":   "yes" if (uifpi_val is not None and cpi_val is not None) else "no",
        })
    return rows


def count_overlap(rows: List[Dict[str, Any]]) -> int:
    return sum(1 for r in rows if r["both_present"] == "yes")


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(all_rows: List[Dict[str, Any]]):
    fields = [
        "year_month", "country", "country_code",
        "uifpi_value", "cpi_value", "cpi_food",
        "uifpi_change", "cpi_change", "both_present",
    ]
    with open(ALIGNED_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Aligned series written → {ALIGNED_CSV}  ({len(all_rows)} rows total)")


def save_summary(summary: List[Dict[str, Any]]):
    Path(SUMMARY_JSON).parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Alignment summary written → {SUMMARY_JSON}")


# ─────────────────────────────────────────────────────────────────────────────
# Console print
# ─────────────────────────────────────────────────────────────────────────────

def print_alignment_table(summary: List[Dict[str, Any]], min_overlap: int):
    print(f"\n{'='*76}")
    print(f"{'SERIES ALIGNMENT SUMMARY':^76}")
    print(f"  Granger threshold: {min_overlap} overlapping months")
    print(f"{'='*76}")
    print(f"{'Country':<22} {'CC':4} {'UIFPI':>7} {'CPI':>7} "
          f"{'Overlap':>8} {'Granger?':>10}  CPI source range")
    print(f"{'─'*76}")

    for row in summary:
        uifpi_n  = row["uifpi_months"]
        cpi_n    = row["cpi_months"]
        overlap  = row["overlap_months"]
        granger  = "✓ YES" if overlap >= min_overlap else f"✗ need {min_overlap - overlap} more"
        cpi_range = f"{row['cpi_min']} – {row['cpi_max']}" if row['cpi_min'] else "no CPI data"
        print(f"{row['country']:<22} {row['country_code']:4} "
              f"{uifpi_n:>7} {cpi_n:>7} {overlap:>8} {granger:>10}  {cpi_range}")

    print(f"{'─'*76}")
    ready = sum(1 for r in summary if r["overlap_months"] >= min_overlap)
    print(f"\nCountries ready for Granger testing: {ready} / {len(summary)}")

    if ready == 0 and all(r["uifpi_months"] == 0 for r in summary):
        print("\nNote: UIFPI index is empty (uifpi_index table has no rows).")
        print("Run index_builder.py after collecting price data to populate it.")

    print(f"{'='*76}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Align UIFPI and CPI series")
    parser.add_argument("--min-overlap", type=int, default=MIN_GRANGER,
                        help=f"Min overlap months for Granger (default {MIN_GRANGER})")
    parser.add_argument("--export-csv",  action="store_true",
                        help="Write aligned_series.csv (default: always write)")
    args = parser.parse_args()

    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn  = sqlite3.connect(DB_PATH)
    uifpi = load_uifpi(conn)
    cpi   = load_cpi(conn)
    conn.close()

    all_countries = sorted(COUNTRY_TO_CODE.keys())
    all_rows: List[Dict[str, Any]] = []
    summary: List[Dict[str, Any]]  = []

    for country in all_countries:
        code       = COUNTRY_TO_CODE[country]
        uifpi_data = uifpi.get(country, {})
        cpi_data   = cpi.get(code, {})

        rows = align_country(country, uifpi_data, cpi_data)
        all_rows.extend(rows)

        overlap  = count_overlap(rows)
        uifpi_n  = len(uifpi_data)
        cpi_n    = len(cpi_data)
        cpi_periods = sorted(cpi_data.keys())

        summary.append({
            "country":          country,
            "country_code":     code,
            "uifpi_months":     uifpi_n,
            "cpi_months":       cpi_n,
            "overlap_months":   overlap,
            "granger_ready":    overlap >= args.min_overlap,
            "min_overlap_required": args.min_overlap,
            "cpi_min":          cpi_periods[0]  if cpi_periods else None,
            "cpi_max":          cpi_periods[-1] if cpi_periods else None,
            "uifpi_min":        min(uifpi_data)  if uifpi_data else None,
            "uifpi_max":        max(uifpi_data)  if uifpi_data else None,
        })

    # Always export (--export-csv flag kept for backwards compatibility)
    export_csv(all_rows)
    save_summary(summary)
    print_alignment_table(summary, args.min_overlap)


if __name__ == "__main__":
    main()

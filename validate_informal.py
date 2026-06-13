"""
UIFPI — Informal Price Validator
Quality-checks the informal_prices table:
  1. Outlier detection (±3 SD within country × category)
  2. Formal / informal price ratio analysis per country
  3. Exports validation_informal.csv with a per-row flag column
  4. Prints a console summary

Usage:
    python validate_informal.py [--export-csv] [--show-outliers]
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH    = "uifpi.db"
OUTPUT_CSV = "analysis_results/validation_informal.csv"

# Minimum items needed in a (country, language) group to compute SD
MIN_GROUP_SIZE = 3

# Z-score threshold for outlier flagging
OUTLIER_SD = 3.0

# If an informal price is more than this multiple of formal median → suspicious
MAX_INFORMAL_FORMAL_RATIO = 4.0


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_informal_prices(conn: sqlite3.Connection) -> List[dict]:
    """Return all rows from informal_prices as list of dicts."""
    cur = conn.execute("""
        SELECT id, image_filename, country_code, item_name,
               price_local, currency_symbol, price_usd,
               language, confidence, source, collection_date
        FROM informal_prices
        WHERE price_usd IS NOT NULL AND price_usd > 0
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_formal_prices(conn: sqlite3.Connection) -> List[dict]:
    """Return formal sector prices from the main prices table."""
    cur = conn.execute("""
        SELECT country, price_usd, category
        FROM prices
        WHERE sector = 'formal'
          AND price_usd IS NOT NULL AND price_usd > 0
    """)
    if cur.description is None:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# Statistics helpers
# ─────────────────────────────────────────────────────────────────────────────

def mean(values: List[float]) -> float:
    return sum(values) / len(values)


def stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def median(values: List[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def z_score(value: float, group_mean: float, group_sd: float) -> Optional[float]:
    if group_sd == 0:
        return None
    return (value - group_mean) / group_sd


# ─────────────────────────────────────────────────────────────────────────────
# Outlier detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_outliers(rows: List[dict]) -> List[dict]:
    """
    Add 'outlier', 'z_score', 'group_mean', 'group_sd' fields to each row.
    Groups are formed by (country_code, language).
    """
    # Build groups
    groups: Dict[Tuple[str, str], List[float]] = {}
    for r in rows:
        key = (r["country_code"] or "?", r["language"] or "unknown")
        groups.setdefault(key, []).append(float(r["price_usd"]))

    group_stats: Dict[Tuple[str, str], Tuple[float, float]] = {}
    for key, prices in groups.items():
        if len(prices) >= MIN_GROUP_SIZE:
            m = mean(prices)
            sd = stdev(prices)
            group_stats[key] = (m, sd)

    enriched = []
    for r in rows:
        row = dict(r)
        key = (r["country_code"] or "?", r["language"] or "unknown")
        if key in group_stats:
            m, sd = group_stats[key]
            z = z_score(float(r["price_usd"]), m, sd)
            row["group_mean"] = round(m, 4)
            row["group_sd"]   = round(sd, 4)
            row["z_score"]    = round(z, 3) if z is not None else None
            row["outlier"]    = (
                "yes" if (z is not None and abs(z) > OUTLIER_SD) else "no"
            )
        else:
            row["group_mean"] = None
            row["group_sd"]   = None
            row["z_score"]    = None
            row["outlier"]    = "insufficient_data"
        enriched.append(row)
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# Formal / informal ratio
# ─────────────────────────────────────────────────────────────────────────────

def compute_ratios(informal_rows: List[dict],
                   formal_rows: List[dict]) -> Dict[str, dict]:
    """
    For each country_code, compute:
      - informal_median_usd
      - formal_median_usd
      - ratio  (informal / formal)
      - flag   (True if ratio > MAX_INFORMAL_FORMAL_RATIO or < 0.05)
    """
    # Build country → list of informal USD prices
    inf_by_country: Dict[str, List[float]] = {}
    for r in informal_rows:
        cc = r.get("country_code") or "?"
        inf_by_country.setdefault(cc, []).append(float(r["price_usd"]))

    # Build country → list of formal USD prices
    formal_by_country: Dict[str, List[float]] = {}
    for r in formal_rows:
        # map full country name to code
        name_to_code = {
            "Singapore": "sg", "Malaysia": "my", "Indonesia": "id",
            "Thailand": "th", "India": "in", "United States": "us",
            "United Kingdom": "gb", "Australia": "au",
        }
        cc = name_to_code.get(r.get("country", ""), "?")
        formal_by_country.setdefault(cc, []).append(float(r["price_usd"]))

    result = {}
    all_codes = set(inf_by_country) | set(formal_by_country)
    for cc in sorted(all_codes):
        inf_prices    = inf_by_country.get(cc, [])
        formal_prices = formal_by_country.get(cc, [])
        inf_med    = median(inf_prices)    if inf_prices    else None
        formal_med = median(formal_prices) if formal_prices else None

        if inf_med and formal_med and formal_med > 0:
            ratio = inf_med / formal_med
            flag  = ratio > MAX_INFORMAL_FORMAL_RATIO or ratio < 0.05
        else:
            ratio = None
            flag  = None

        result[cc] = {
            "country_code":         cc,
            "informal_count":       len(inf_prices),
            "informal_median_usd":  round(inf_med, 4)    if inf_med    else None,
            "formal_count":         len(formal_prices),
            "formal_median_usd":    round(formal_med, 4) if formal_med else None,
            "ratio":                round(ratio, 3)       if ratio      else None,
            "ratio_flag":           flag,
        }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def export_validation_csv(enriched_rows: List[dict]):
    Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id", "image_filename", "country_code", "item_name",
        "price_local", "currency_symbol", "price_usd",
        "language", "confidence", "source", "collection_date",
        "group_mean", "group_sd", "z_score", "outlier",
    ]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_rows)
    print(f"Validation CSV written → {OUTPUT_CSV}  ({len(enriched_rows)} rows)")


# ─────────────────────────────────────────────────────────────────────────────
# Console summary
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(enriched_rows: List[dict], ratios: Dict[str, dict],
                  show_outliers: bool):
    total    = len(enriched_rows)
    outliers = sum(1 for r in enriched_rows if r.get("outlier") == "yes")
    insuff   = sum(1 for r in enriched_rows if r.get("outlier") == "insufficient_data")

    print(f"\n{'='*60}")
    print(f"INFORMAL PRICE VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total items          : {total}")
    print(f"Outliers (|z|>{OUTLIER_SD})   : {outliers} ({100*outliers/total:.1f}% of total)" if total else "")
    print(f"Insufficient data    : {insuff}")
    print(f"Clean items          : {total - outliers - insuff}")

    # Confidence breakdown
    conf_counts: Dict[str, int] = {}
    for r in enriched_rows:
        c = r.get("confidence") or "unknown"
        conf_counts[c] = conf_counts.get(c, 0) + 1
    print(f"\nConfidence breakdown:")
    for c, n in sorted(conf_counts.items()):
        print(f"  {c:12} : {n}")

    # By country
    cc_counts: Dict[str, int] = {}
    for r in enriched_rows:
        cc = r.get("country_code") or "?"
        cc_counts[cc] = cc_counts.get(cc, 0) + 1
    print(f"\nItems by country:")
    for cc, n in sorted(cc_counts.items()):
        print(f"  {cc:6} : {n}")

    # Formal/informal ratios
    if ratios:
        print(f"\nFormal / Informal price ratios (USD medians):")
        print(f"{'CC':6} {'inf_n':6} {'inf_med':10} {'for_n':6} {'for_med':10} {'ratio':8} {'flag':5}")
        print("─" * 60)
        for cc, d in sorted(ratios.items()):
            r = d["ratio"]
            ratio_str = f"{r:.3f}" if r else "N/A"
            flag_str  = "⚠" if d.get("ratio_flag") else ""
            print(f"{cc:6} {d['informal_count']:6} "
                  f"{str(d['informal_median_usd'] or '—'):10} "
                  f"{d['formal_count']:6} "
                  f"{str(d['formal_median_usd'] or '—'):10} "
                  f"{ratio_str:8} {flag_str}")

    if show_outliers and outliers:
        print(f"\nOutlier items (|z| > {OUTLIER_SD}):")
        print(f"{'cc':5} {'item':30} {'price_usd':10} {'z':8} {'conf':8}")
        print("─" * 65)
        for r in enriched_rows:
            if r.get("outlier") == "yes":
                z = r.get("z_score")
                print(f"{r['country_code']:5} "
                      f"{str(r['item_name'])[:30]:30} "
                      f"{r['price_usd']:10.4f} "
                      f"{z:8.2f} "
                      f"{r.get('confidence',''):8}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate UIFPI informal prices")
    parser.add_argument("--export-csv",    action="store_true",
                        help="Write analysis_results/validation_informal.csv")
    parser.add_argument("--show-outliers", action="store_true",
                        help="Print each outlier row in the summary")
    args = parser.parse_args()

    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # Check table exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='informal_prices'"
    )
    if not cur.fetchone():
        print("informal_prices table does not exist — run image_processor.py first.")
        conn.close()
        sys.exit(0)

    informal_rows = get_informal_prices(conn)
    formal_rows   = get_formal_prices(conn)
    conn.close()

    if not informal_rows:
        print("No informal_prices rows found (with valid price_usd).")
        return

    print(f"Loaded {len(informal_rows)} informal items, "
          f"{len(formal_rows)} formal items")

    enriched = detect_outliers(informal_rows)
    ratios   = compute_ratios(informal_rows, formal_rows)

    if args.export_csv:
        export_validation_csv(enriched)

    print_summary(enriched, ratios, args.show_outliers)


if __name__ == "__main__":
    main()

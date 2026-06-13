"""
UIFPI — Informal Price Merger
Merges validated informal_prices into the main prices table,
then reruns index_builder.py to regenerate the UIFPI index.

Steps:
  1. Read all rows from informal_prices where processed=1
  2. Skip rows already present in prices (by image_filename + item_name)
  3. Insert into prices with sector='informal', appropriate currency fields
  4. Optionally rerun index_builder.py

Usage:
    python merge_informal.py [--dry-run] [--skip-rebuild] [--country sg]
"""

import argparse
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = "uifpi.db"

COUNTRY_FULL: Dict[str, str] = {
    "sg": "Singapore", "my": "Malaysia",  "id": "Indonesia",
    "th": "Thailand",  "in": "India",     "us": "United States",
    "gb": "United Kingdom", "au": "Australia",
}

COUNTRY_CURRENCY: Dict[str, str] = {
    "sg": "SGD", "my": "MYR", "id": "IDR", "th": "THB",
    "in": "INR", "us": "USD", "gb": "GBP", "au": "AUD",
}

# NLP category guess from item_name keywords
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "RICE_DISH":    ["rice", "nasi", "khao", "biryani", "fried rice", "nasi goreng"],
    "NOODLE_DISH":  ["noodle", "mee", "mie", "pasta", "pad thai", "laksa",
                     "pho", "ramen", "kuay teow", "kway teow"],
    "SOUP_STEW":    ["soup", "stew", "curry", "laksa", "tom yum", "soto",
                     "bak kut", "congee", "porridge"],
    "BREAD_PASTRY": ["bread", "roti", "prata", "toast", "bun", "cake", "pastry"],
    "MEAT_DISH":    ["chicken", "beef", "pork", "mutton", "lamb", "duck",
                     "satay", "ayam", "daging"],
    "SEAFOOD":      ["fish", "prawn", "shrimp", "crab", "squid", "seafood",
                     "ikan", "udang"],
    "VEGETABLE":    ["vegetable", "veg", "tofu", "tempeh", "kangkung"],
    "BEVERAGE":     ["coffee", "tea", "juice", "drink", "kopi", "teh",
                     "water", "milk", "sugar cane"],
    "SNACK":        ["snack", "fritter", "popiah", "dumpling", "dim sum",
                     "goreng"],
}


def guess_category(item_name: str) -> str:
    name_lower = (item_name or "").lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return cat
    return "OTHER"


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_prices_columns(conn: sqlite3.Connection):
    """
    The prices table may not have a source_image column yet.
    Add it if missing so we can deduplicate on re-runs.
    """
    cur = conn.execute("PRAGMA table_info(prices)")
    existing = {row[1] for row in cur.fetchall()}
    if "source_image" not in existing:
        conn.execute("ALTER TABLE prices ADD COLUMN source_image TEXT")
        conn.commit()


def already_merged(conn: sqlite3.Connection, image_filename: str,
                   item_name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM prices WHERE source_image=? AND item_name=? LIMIT 1",
        (image_filename, item_name),
    )
    return cur.fetchone() is not None


def get_informal_rows(conn: sqlite3.Connection,
                      country_filter: Optional[str]) -> List[dict]:
    query = """
        SELECT id, image_filename, country, country_code, item_name,
               price_local, currency_symbol, price_usd,
               language, confidence, source, collection_date
        FROM informal_prices
        WHERE processed = 1
          AND price_usd IS NOT NULL AND price_usd > 0
          AND item_name IS NOT NULL AND item_name != ''
    """
    params: list = []
    if country_filter:
        query += " AND country_code = ?"
        params.append(country_filter)

    cur = conn.execute(query, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def insert_price_row(conn: sqlite3.Connection, row: dict) -> bool:
    """Insert one informal row into the prices table. Returns True if inserted."""
    country_code = row.get("country_code", "sg")
    country      = row.get("country") or COUNTRY_FULL.get(country_code, country_code)
    currency     = row.get("currency_symbol") or COUNTRY_CURRENCY.get(country_code, "USD")
    category     = guess_category(row.get("item_name", ""))
    cdate        = row.get("collection_date") or str(date.today())
    # Build a YYYY-MM period from collection_date
    period       = cdate[:7] if cdate else str(date.today())[:7]

    try:
        conn.execute("""
            INSERT INTO prices
              (country, item_name, price, currency, price_usd, category,
               sector, source, date_collected, period,
               language, confidence, source_image)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            country,
            row.get("item_name"),
            row.get("price_local"),
            currency,
            row.get("price_usd"),
            category,
            "informal",
            row.get("source", "image"),
            cdate,
            period,
            row.get("language"),
            row.get("confidence"),
            row.get("image_filename"),
        ))
        return True
    except sqlite3.OperationalError as e:
        # If prices table is missing a column, print and skip
        print(f"  DB error inserting {row.get('item_name')}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def merge(dry_run: bool = False, skip_rebuild: bool = False,
          country_filter: Optional[str] = None):

    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # Check informal_prices exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='informal_prices'"
    )
    if not cur.fetchone():
        print("informal_prices table not found — run image_processor.py first.")
        conn.close()
        sys.exit(0)

    # Check prices table exists
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
    )
    if not cur.fetchone():
        print("prices table not found — run migrate_db.py first.")
        conn.close()
        sys.exit(1)

    ensure_prices_columns(conn)

    informal_rows = get_informal_rows(conn, country_filter)
    print(f"Informal rows available: {len(informal_rows)}")

    new_count     = 0
    skipped_count = 0

    for row in informal_rows:
        fname     = row.get("image_filename", "")
        item_name = row.get("item_name", "")

        if already_merged(conn, fname, item_name):
            skipped_count += 1
            continue

        if dry_run:
            print(f"  [dry-run] would insert: {row.get('country_code')} | "
                  f"{item_name} | ${row.get('price_usd'):.4f}")
            new_count += 1
            continue

        inserted = insert_price_row(conn, row)
        if inserted:
            new_count += 1

    if not dry_run:
        conn.commit()

    conn.close()

    print(f"\n{'─'*50}")
    print(f"Rows inserted  : {new_count}")
    print(f"Rows skipped   : {skipped_count} (already in prices table)")
    if dry_run:
        print(f"[Dry run — no changes written]")
    print(f"{'─'*50}")

    if dry_run or skip_rebuild or new_count == 0:
        if new_count == 0:
            print("Nothing new to merge — index rebuild skipped.")
        return

    # ── Rebuild the UIFPI index ──────────────────────────────────────────────
    print("\nRebuilding UIFPI index (running index_builder.py) …")
    result = subprocess.run(
        [sys.executable, "index_builder.py"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("index_builder.py completed successfully.")
        if result.stdout.strip():
            print(result.stdout[-2000:])   # last 2000 chars to avoid flooding
    else:
        print(f"index_builder.py failed (exit {result.returncode}):")
        print(result.stderr[-2000:])


# ─────────────────────────────────────────────────────────────────────────────
# Summary helper (post-merge check)
# ─────────────────────────────────────────────────────────────────────────────

def show_prices_summary():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute("""
        SELECT sector, country, COUNT(*) as n
        FROM prices
        GROUP BY sector, country
        ORDER BY sector, n DESC
    """)
    rows = cur.fetchall()
    conn.close()

    print(f"\n{'sector':10} {'country':20} {'items':8}")
    print("─" * 42)
    for r in rows:
        print(f"{r[0]:10} {r[1]:20} {r[2]:8}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Merge informal prices into UIFPI DB")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Preview inserts without writing to DB")
    parser.add_argument("--skip-rebuild", action="store_true",
                        help="Skip index_builder.py rerun after merge")
    parser.add_argument("--country",      default=None,
                        help="Filter to one country code: sg, my, id, …")
    parser.add_argument("--summary",      action="store_true",
                        help="Print prices table summary and exit")
    args = parser.parse_args()

    if args.summary:
        show_prices_summary()
        return

    merge(
        dry_run=args.dry_run,
        skip_rebuild=args.skip_rebuild,
        country_filter=args.country,
    )


if __name__ == "__main__":
    main()

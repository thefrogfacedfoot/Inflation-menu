"""
UIFPI — Gemini Vision Image Processor
Sends each unprocessed image in image_log.csv to the Gemini Vision API,
extracts structured price data, and stores results in the informal_prices
table of uifpi.db.

Uses the Gemini REST API directly (requests + base64) to avoid the
google-generativeai SDK which fails to build on macOS LibreSSL Python 3.9.

Usage:
    python image_processor.py [--limit N] [--country sg] [--dry-run]
"""

import argparse
import base64
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

IMAGES_DIR   = Path("images")
LOG_FILE     = IMAGES_DIR / "image_log.csv"
FAILED_FILE  = IMAGES_DIR / "failed_images.txt"
DB_PATH      = "uifpi.db"

GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_URL   = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

# 1 USD = rate units of local currency — divide to convert to USD.
from fx_rates import FALLBACK_RATES

COUNTRY_CURRENCY: Dict[str, str] = {
    "sg": "SGD", "my": "MYR", "id": "IDR", "th": "THB",
    "in": "INR", "us": "USD", "gb": "GBP", "au": "AUD",
}

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS informal_prices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    image_filename   TEXT NOT NULL,
    country          TEXT,
    country_code     TEXT,
    item_name        TEXT,
    price_local      REAL,
    currency_symbol  TEXT,
    price_usd        REAL,
    language         TEXT,
    confidence       TEXT,
    source           TEXT,
    collection_date  TEXT,
    processed        INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (date('now'))
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Gemini API
# ─────────────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """
You are a price data extraction assistant for an economic research project.
Examine this image of a food vendor menu board, signboard, price list, or
similar display.

Extract ALL food/drink items and their prices that you can see.

Return ONLY a valid JSON array. Each element must have exactly these fields:
  "item_name"      : string — name of the food/drink item
  "price_local"    : number — price as shown (numeric only, no currency symbols)
  "currency_symbol": string — currency symbol or code if visible (e.g. "$", "S$", "RM", "Rp", "฿", "₹")
  "language"       : string — language of the text (e.g. "English", "Malay", "Indonesian", "Thai", "Hindi", "Chinese")
  "confidence"     : string — your confidence: "high", "medium", or "low"

Rules:
- If you see no prices, return an empty array: []
- Do not include items without a visible price
- Do not add any text before or after the JSON array
- Use null for currency_symbol if not visible

Example output:
[
  {"item_name": "Chicken Rice", "price_local": 3.5, "currency_symbol": "S$", "language": "English", "confidence": "high"},
  {"item_name": "Nasi Lemak", "price_local": 4.0, "currency_symbol": "S$", "language": "English", "confidence": "high"}
]
"""


def call_gemini(image_path: Path, api_key: str,
                max_retries: int = 3) -> Optional[List[Dict[str, Any]]]:
    """
    Send one image to the Gemini Vision API and return a list of price dicts.
    Returns None on unrecoverable failure.
    """
    # Read and encode image
    try:
        img_bytes = image_path.read_bytes()
    except FileNotFoundError:
        print(f"  [Gemini] File not found: {image_path}")
        return None

    b64 = base64.b64encode(img_bytes).decode("utf-8")
    suffix = image_path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
                ".gif": "image/gif"}
    mime = mime_map.get(suffix, "image/jpeg")

    payload = {
        "contents": [{
            "parts": [
                {"text": EXTRACTION_PROMPT},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                GEMINI_URL,
                params={"key": api_key},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"  [Gemini] Rate limited, waiting {wait}s …")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"  [Gemini] HTTP {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                print("  [Gemini] No candidates in response")
                return []

            text = (candidates[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", ""))

            # Strip markdown fences if present
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]

            try:
                items = json.loads(text.strip())
                if isinstance(items, list):
                    return items
                return []
            except json.JSONDecodeError:
                print(f"  [Gemini] JSON parse error on: {text[:100]!r}")
                return []

        except requests.RequestException as e:
            print(f"  [Gemini] Request error (attempt {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Price conversion
# ─────────────────────────────────────────────────────────────────────────────

def to_usd(price_local: Optional[float], country_code: str,
           currency_symbol: Optional[str]) -> Optional[float]:
    """Convert a local price to USD using FALLBACK_RATES."""
    if price_local is None:
        return None
    # Try to match from currency symbol first
    if currency_symbol:
        sym = currency_symbol.upper().replace("$", "USD")
        for code, rate in FALLBACK_RATES.items():
            if code in sym:
                return round(price_local / rate, 4)
    # Fallback to country code
    currency = COUNTRY_CURRENCY.get(country_code, "USD")
    rate = FALLBACK_RATES.get(currency, 1.0)
    return round(price_local / rate, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Log file I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_log() -> List[Dict[str, str]]:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE) as f:
        return list(csv.DictReader(f))


def update_log_row(rows: List[Dict[str, str]], filename: str,
                   item_count: int):
    """Mark a row as processed=1 and set item_count in the in-memory list."""
    for row in rows:
        if row.get("filename") == filename:
            row["processed"] = "1"
            row["item_count"] = str(item_count)
            break


def save_log(rows: List[Dict[str, str]]):
    fields = ["filename", "country", "country_code", "source",
              "date_collected", "url", "processed", "item_count"]
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_failed(image_filename: str, reason: str):
    with open(FAILED_FILE, "a") as f:
        f.write(f"{image_filename}\t{reason}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main processing loop
# ─────────────────────────────────────────────────────────────────────────────

def process_images(limit: Optional[int] = None, country_filter: Optional[str] = None,
                   dry_run: bool = False):
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set in .env or environment.")
        sys.exit(1)

    rows = load_log()
    unprocessed = [r for r in rows if r.get("processed") == "0"]
    if country_filter:
        unprocessed = [r for r in unprocessed
                       if r.get("country_code") == country_filter]
    if limit:
        unprocessed = unprocessed[:limit]

    print(f"Images to process: {len(unprocessed)}")
    if dry_run:
        print("[Dry run] No API calls will be made.")
        return

    conn      = get_db()
    cursor    = conn.cursor()
    total_new = 0
    failures  = 0

    for i, log_row in enumerate(unprocessed, 1):
        fname      = log_row.get("filename", "")
        country    = log_row.get("country", "")
        country_code = log_row.get("country_code", "sg")
        source     = log_row.get("source", "")
        cdate      = log_row.get("date_collected", str(date.today()))

        # manual images live at their absolute path, others under images/
        if source == "manual":
            raw_url = log_row.get("url", "")
            if raw_url.startswith("file://"):
                image_path = Path(raw_url[7:])
            else:
                image_path = IMAGES_DIR / fname
        else:
            image_path = IMAGES_DIR / fname

        print(f"\n[{i}/{len(unprocessed)}] {fname}")

        if not image_path.exists():
            print(f"  File missing: {image_path}")
            append_failed(fname, "file_missing")
            failures += 1
            update_log_row(rows, fname, 0)
            continue

        items = call_gemini(image_path, api_key)
        if items is None:
            print(f"  API failure — logged to {FAILED_FILE}")
            append_failed(fname, "api_failure")
            failures += 1
            continue

        print(f"  Extracted {len(items)} items")
        saved = 0
        for item in items:
            try:
                price_local = item.get("price_local")
                if isinstance(price_local, str):
                    price_local = float(price_local.replace(",", ""))
                price_usd = to_usd(price_local, country_code,
                                   item.get("currency_symbol"))
                cursor.execute("""
                    INSERT INTO informal_prices
                      (image_filename, country, country_code, item_name,
                       price_local, currency_symbol, price_usd, language,
                       confidence, source, collection_date, processed)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,1)
                """, (
                    fname, country, country_code,
                    item.get("item_name", ""),
                    price_local,
                    item.get("currency_symbol"),
                    price_usd,
                    item.get("language", ""),
                    item.get("confidence", ""),
                    source, cdate,
                ))
                saved += 1
            except Exception as e:
                print(f"  DB insert error: {e}")

        conn.commit()
        update_log_row(rows, fname, saved)
        total_new += saved

        # polite delay between API calls
        time.sleep(0.5)

    conn.close()
    save_log(rows)

    print(f"\n{'─'*50}")
    print(f"Images processed : {len(unprocessed) - failures}")
    print(f"Images failed    : {failures}")
    print(f"Items stored     : {total_new}")
    print(f"DB               : {DB_PATH} → informal_prices table")
    if failures:
        print(f"Failed log       : {FAILED_FILE}")
    print(f"{'─'*50}")


# ─────────────────────────────────────────────────────────────────────────────
# Inventory helper
# ─────────────────────────────────────────────────────────────────────────────

def show_inventory():
    """Print current state of the informal_prices table."""
    if not Path(DB_PATH).exists():
        print("Database not found.")
        return
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='informal_prices'")
    if not cur.fetchone():
        print("informal_prices table does not exist yet.")
        conn.close()
        return
    cur.execute("SELECT COUNT(*) FROM informal_prices")
    total = cur.fetchone()[0]
    cur.execute("""
        SELECT country_code, COUNT(*) as n, COUNT(DISTINCT image_filename) as imgs
        FROM informal_prices GROUP BY country_code ORDER BY n DESC
    """)
    rows = cur.fetchall()
    conn.close()
    print(f"\ninformal_prices: {total} total items")
    print(f"{'country':8} {'items':8} {'images':8}")
    print("─" * 26)
    for r in rows:
        print(f"{r[0]:8} {r[1]:8} {r[2]:8}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UIFPI Gemini Vision image processor")
    parser.add_argument("--limit",   type=int, default=None,
                        help="Max images to process this run")
    parser.add_argument("--country", default=None,
                        help="Filter to one country code: sg, my, id, ...")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse log but make no API calls")
    parser.add_argument("--inventory", action="store_true",
                        help="Show DB inventory and exit")
    args = parser.parse_args()

    if args.inventory:
        show_inventory()
        return

    process_images(
        limit=args.limit,
        country_filter=args.country,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

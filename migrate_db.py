"""
Migration: populates price_usd for all rows using live exchange rates.
Safe to run repeatedly — only updates NULL/0 price_usd rows.
"""
import sqlite3
import sys
import urllib.request
import urllib.error
import json

DB_PATH = 'uifpi.db'
BATCH_SIZE = 500
RATE_API = 'https://api.exchangerate-api.com/v4/latest/USD'

FALLBACK_RATES = {
    'USD': 1.0,
    'SGD': 1.35,
    'MYR': 4.70,
    'GBP': 0.79,
    'AUD': 1.55,
    'INR': 83.5,
    'IDR': 15900.0,
    'THB': 36.0,
    'PHP': 57.0,
}


def fetch_rates():
    try:
        with urllib.request.urlopen(RATE_API, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            rates = data.get('rates', {})
            print(f"  Fetched {len(rates)} rates from API")
            return rates
    except (urllib.error.URLError, Exception) as e:
        print(f"  API unavailable ({e}), using fallback rates")
        return FALLBACK_RATES


def migrate(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure column exists
    try:
        cur.execute('ALTER TABLE prices ADD COLUMN price_usd REAL')
        conn.commit()
        print("Added price_usd column")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    print("Fetching exchange rates...")
    rates = fetch_rates()

    cur.execute(
        "SELECT id, currency, price FROM prices WHERE price_usd IS NULL OR price_usd = 0"
    )
    rows = cur.fetchall()
    print(f"Rows needing price_usd: {len(rows)}")

    updated = 0
    skipped_currencies = set()
    batch = []

    for row_id, currency, price in rows:
        if currency == 'USD':
            usd = price
        elif currency in rates:
            usd = price / rates[currency]
        else:
            skipped_currencies.add(currency)
            continue

        batch.append((round(usd, 6), row_id))

        if len(batch) >= BATCH_SIZE:
            cur.executemany("UPDATE prices SET price_usd = ? WHERE id = ?", batch)
            conn.commit()
            updated += len(batch)
            print(f"  ...committed {updated} rows")
            batch = []

    if batch:
        cur.executemany("UPDATE prices SET price_usd = ? WHERE id = ?", batch)
        conn.commit()
        updated += len(batch)

    cur.execute("SELECT COUNT(*) FROM prices WHERE price_usd IS NOT NULL AND price_usd > 0")
    final = cur.fetchone()[0]

    print(f"\nRows updated: {updated}")
    print(f"Total rows with price_usd populated: {final}")
    if skipped_currencies:
        print(f"Currencies not found in rate table: {skipped_currencies}")
    else:
        print("All currencies converted successfully")

    conn.close()


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(path)

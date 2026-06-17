"""
Always-on floor datasets: load the unconditional macro / cross-country
benchmarks for every roster country (and Vietnam as proxy-only).

Sources:
  1. World Bank API     - FP.CPI.TOTL (annual CPI, 2018-present)
  2. Big Mac Index      - The Economist's monthly CSV on GitHub
  3. Numbeo             - 'Restaurants Price Index' yearly snapshots (2018+)
                          and 'Inexpensive Restaurant Meal' price rankings

Tables created/used:
  monthly_cpi      (existing) — World Bank annual CPI back-filled where sparse
  bigmac_index     (new)      — country, date, dollar_price, ...
  numbeo_index     (new)      — country, year, indicator, value, source_url

Idempotent: each run upserts on its natural key. Country roster:
  US, IN, ID, TH, AU, PH, SG, MX  (formal roster)
  VN                              (proxy-only)
"""
import csv
import io
import json
import os
import re
import sqlite3
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, 'uifpi.db')
HDR  = {'User-Agent': 'UIFPI-research-pipeline (academic; contact via repo issues)'}

ROSTER = [
    # (country, iso2, iso3, currency)
    ('United States', 'US', 'USA', 'USD'),
    ('India',         'IN', 'IND', 'INR'),
    ('Indonesia',     'ID', 'IDN', 'IDR'),
    ('Thailand',      'TH', 'THA', 'THB'),
    ('Australia',     'AU', 'AUS', 'AUD'),
    ('Philippines',   'PH', 'PHL', 'PHP'),
    ('Singapore',     'SG', 'SGP', 'SGD'),
    ('Mexico',        'MX', 'MEX', 'MXN'),
    ('Vietnam',       'VN', 'VNM', 'VND'),  # proxy-only
    # Added 2026-06-18 — formal-sector roster expansion (BR/DE/ZA cleared
    # Phase 0 threshold) plus GB/MY backfill (already item-level countries
    # with monthly CPI but no Numbeo / Big Mac coverage).
    ('United Kingdom','GB', 'GBR', 'GBP'),
    ('Malaysia',      'MY', 'MYS', 'MYR'),
    ('Brazil',        'BR', 'BRA', 'BRL'),
    ('Germany',       'DE', 'DEU', 'EUR'),
    ('South Africa',  'ZA', 'ZAF', 'ZAR'),
]

# Numbeo "items" we want (their item-id integers from the URL):
# 1 = inexpensive restaurant meal (informal proxy)
# 2 = mid-range meal for two (formal proxy)
# Combined indices live on the rankings page via displayColumn= param;
# 4 = Restaurants Price Index, 8 = Local Purchasing Power Index
NUMBEO_ITEMS = [
    (1, 'Meal, Inexpensive Restaurant'),
    (2, 'Meal for 2 People, Mid-range Restaurant, Three-course'),
    (4, 'McMeal at McDonalds (or Equivalent Combo Meal)'),
    (5, 'Domestic Beer (0.5 liter draught)'),
]
NUMBEO_RANKING_COLS = [
    (4, 'Restaurants Price Index'),
    (5, 'Restaurant Price Index + Groceries Price Index'),
]


# ── Schema ────────────────────────────────────────────────────────────────────

def init_schema(conn):
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bigmac_index (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            iso3          TEXT NOT NULL,
            country       TEXT,
            date          TEXT NOT NULL,
            local_price   REAL,
            dollar_ex     REAL,
            dollar_price  REAL,
            source        TEXT DEFAULT 'economist',
            UNIQUE(iso3, date)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS numbeo_index (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            country      TEXT NOT NULL,
            iso2         TEXT,
            year         INTEGER NOT NULL,
            indicator    TEXT NOT NULL,
            indicator_id INTEGER,
            value        REAL,
            currency     TEXT,
            source_url   TEXT,
            UNIQUE(country, year, indicator)
        )
    """)
    conn.commit()


# ── World Bank ───────────────────────────────────────────────────────────────

def load_worldbank_cpi(conn):
    """Backfill monthly_cpi with annual CPI from World Bank for any country
    whose existing series is < 8 years long."""
    print("\n=== World Bank CPI (FP.CPI.TOTL) ===")
    c = conn.cursor()
    loaded = 0
    for country, iso2, iso3, _cur in ROSTER:
        # How many years of monthly data do we already have?
        existing = c.execute(
            "SELECT COUNT(DISTINCT substr(year_month,1,4)) FROM monthly_cpi "
            "WHERE country_code = ?", (iso2,)
        ).fetchone()[0]
        if existing >= 8:
            print(f"  {country:<14} {iso2}  already has {existing} years — skip")
            continue
        # Fetch annual series 2015-2025
        url = (f'https://api.worldbank.org/v2/country/{iso3}/indicator/'
               f'FP.CPI.TOTL?format=json&date=2015:2025&per_page=200')
        try:
            r = requests.get(url, headers=HDR, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list) or len(data) < 2:
                print(f"  {country:<14} {iso2}  unexpected payload — skip")
                continue
            rows = [d for d in data[1] if d.get('value') is not None]
            if not rows:
                print(f"  {country:<14} {iso2}  no values — skip")
                continue
            # Each annual value: expand to 12 monthly rows tagged as annual_interp
            n_before = c.execute(
                "SELECT COUNT(*) FROM monthly_cpi WHERE country_code = ?",
                (iso2,)
            ).fetchone()[0]
            for d in rows:
                year = int(d['date'])
                val = float(d['value'])
                for m in range(1, 13):
                    ym = f'{year:04d}-{m:02d}'
                    c.execute(
                        "INSERT OR IGNORE INTO monthly_cpi "
                        "(country_code, year, month, year_month, cpi_value, "
                        " source, date_downloaded) VALUES "
                        "(?, ?, ?, ?, ?, ?, ?)",
                        (iso2, year, m, ym, val, 'worldbank_annual',
                         datetime.now().isoformat()[:19])
                    )
            conn.commit()
            n_after = c.execute(
                "SELECT COUNT(*) FROM monthly_cpi WHERE country_code = ?",
                (iso2,)
            ).fetchone()[0]
            added = n_after - n_before
            loaded += added
            print(f"  {country:<14} {iso2}  +{added} rows ({len(rows)} years)")
        except Exception as e:
            print(f"  {country:<14} {iso2}  ERR {str(e)[:60]}")
        time.sleep(1.0)
    print(f"  World Bank: {loaded} new rows inserted")


# ── Big Mac Index ────────────────────────────────────────────────────────────

BIGMAC_URL = ('https://raw.githubusercontent.com/TheEconomist/big-mac-data/'
              'master/output-data/big-mac-full-index.csv')

def load_bigmac(conn):
    print("\n=== Big Mac index (Economist) ===")
    iso3s = {r[2] for r in ROSTER}
    try:
        r = requests.get(BIGMAC_URL, headers=HDR, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"  fetch failed: {e}")
        return
    reader = csv.DictReader(io.StringIO(r.text))
    c = conn.cursor()
    n = 0
    for row in reader:
        iso3 = (row.get('iso_a3') or '').upper()
        if iso3 not in iso3s:
            continue
        try:
            date = row.get('date', '')[:10]
            local = float(row['local_price']) if row.get('local_price') else None
            dx    = float(row['dollar_ex']) if row.get('dollar_ex') else None
            dp    = float(row['dollar_price']) if row.get('dollar_price') else None
        except (TypeError, ValueError):
            continue
        country = row.get('name') or row.get('country', '')
        c.execute(
            "INSERT OR REPLACE INTO bigmac_index "
            "(iso3, country, date, local_price, dollar_ex, dollar_price, source) "
            "VALUES (?, ?, ?, ?, ?, ?, 'economist')",
            (iso3, country, date, local, dx, dp)
        )
        n += 1
    conn.commit()
    print(f"  Big Mac: {n} rows inserted/refreshed across {len(iso3s)} countries")
    # Show per-country coverage
    for country, iso2, iso3, _cur in ROSTER:
        rng = c.execute(
            "SELECT MIN(date), MAX(date), COUNT(*) FROM bigmac_index "
            "WHERE iso3 = ?", (iso3,)
        ).fetchone()
        print(f"    {country:<14} {iso3}  {rng[2]:>3} obs  {rng[0]} → {rng[1]}")


# ── Numbeo ────────────────────────────────────────────────────────────────────

NUMBEO_BASE = 'https://www.numbeo.com'

def load_numbeo(conn):
    """Load Numbeo per-item country rankings for each year 2018-2025 and
    each item in NUMBEO_ITEMS. Numbeo's rankings page is country × item ×
    year — perfect for cross-country panel data."""
    print("\n=== Numbeo item rankings ===")
    c = conn.cursor()
    target_countries = {r[0]: (r[1], r[3]) for r in ROSTER}
    n_total = 0
    for year in range(2018, 2026):
        for item_id, item_name in NUMBEO_ITEMS:
            url = (f'{NUMBEO_BASE}/cost-of-living/country_price_rankings'
                   f'?itemId={item_id}&title={year}')
            try:
                r = requests.get(url, headers=HDR, timeout=30)
                if r.status_code != 200:
                    print(f"  {year} item {item_id}  HTTP {r.status_code}")
                    time.sleep(1.5); continue
            except Exception as e:
                print(f"  {year} item {item_id}  ERR {str(e)[:50]}")
                time.sleep(2.0); continue
            soup = BeautifulSoup(r.text, 'html.parser')
            # Numbeo rankings page has no table headers — the data table is
            # just the one with the most <tr> rows (~99 countries).
            tables = soup.find_all('table')
            if not tables:
                print(f"  {year} item {item_id}  no tables on page")
                time.sleep(1.0); continue
            table = max(tables, key=lambda t: len(t.find_all('tr')))
            n_year = 0
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 4:
                    continue
                # Layout: [rank, country, flag/empty, price]
                country_cell = tds[1].get_text(strip=True)
                price_cell   = tds[3].get_text(strip=True)
                if country_cell not in target_countries:
                    continue
                iso2, cur = target_countries[country_cell]
                # Numbeo writes "12.50 $" / "1,234.56 ₹" — pull the number
                m = re.search(r'([\d.,]+)', price_cell.replace(',', ''))
                if not m:
                    continue
                try:
                    val = float(m.group(1))
                except ValueError:
                    continue
                c.execute(
                    "INSERT OR REPLACE INTO numbeo_index "
                    "(country, iso2, year, indicator, indicator_id, value, "
                    " currency, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (country_cell, iso2, year, item_name, item_id,
                     val, 'USD', url)
                )
                n_year += 1
                n_total += 1
            conn.commit()
            print(f"  {year} item {item_id:<2} '{item_name[:40]:<40}'  +{n_year}")
            time.sleep(1.5)
    print(f"  Numbeo total rows: {n_total}")


def main():
    print("Floor datasets loader")
    print(f"Roster: {', '.join(r[0] for r in ROSTER)}")
    conn = sqlite3.connect(DB)
    init_schema(conn)
    load_worldbank_cpi(conn)
    load_bigmac(conn)
    load_numbeo(conn)
    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()

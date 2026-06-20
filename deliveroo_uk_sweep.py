#!/usr/bin/env python3
"""
One-shot Deliveroo UK sweep.

The generic historical_html_scraper does a 36-quarter-window CDX walk,
which the broad `deliveroo.co.uk/menu/*` pattern stalls under Wayback's
throttling (saw 42 min on a single sweep with no results inserted).
This script does ONE CDX query per city-narrow pattern, picks a
size-stratified sample, fetches, and inserts via parse_deliveroo_uk.

Inserts into the same `prices` table with source='wayback-deliveroo'.
Logs per-page yields. Idempotent: skips URLs already in the table.
"""
import sqlite3
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import historical_html_scraper as h

BASE = Path(__file__).resolve().parent
DB = BASE / 'uifpi.db'
CDX = 'http://web.archive.org/cdx/search/cdx'
WBM = 'https://web.archive.org/web'
HDR = {'User-Agent': 'UIFPI-research-pipeline (academic; contact via repo issues)'}

# Narrower per-city patterns to avoid the broad pattern's throttle. Each
# query is a single CDX hit, not a 36-window walk.
PATTERNS = [
    'deliveroo.co.uk/menu/london/*',
    'deliveroo.co.uk/menu/manchester/*',
    'deliveroo.co.uk/menu/birmingham/*',
    'deliveroo.co.uk/menu/edinburgh/*',
    'deliveroo.co.uk/menu/glasgow/*',
    'deliveroo.co.uk/menu/bristol/*',
    'deliveroo.co.uk/menu/leeds/*',
    'deliveroo.co.uk/menu/liverpool/*',
]

WINDOW_FROM = '20180101'
WINDOW_TO   = '20260601'
CDX_LIMIT   = 1000           # smaller than the 30 K used by the probe
CDX_TIMEOUT = 60
PER_PATTERN_FETCHES = 20     # cap per pattern → up to 8 × 20 = 160 attempts
FETCH_TIMEOUT = 45
FETCH_DELAY = 1.5
CDX_DELAY = 3.0


def query_cdx(pattern: str) -> list:
    """Single CDX query; collapse on urlkey so each URL appears once."""
    params = {
        'url': pattern,
        'from': WINDOW_FROM, 'to': WINDOW_TO,
        'output': 'json', 'fl': 'timestamp,original,length',
        'filter': ['statuscode:200', 'mimetype:text/html'],
        'collapse': 'urlkey',
        'limit': CDX_LIMIT,
    }
    try:
        r = requests.get(CDX, params=params, headers=HDR, timeout=CDX_TIMEOUT)
        if r.status_code != 200:
            print(f"  CDX {pattern} HTTP {r.status_code}")
            return []
        data = r.json()
        return data[1:] if len(data) > 1 else []
    except Exception as e:
        print(f"  CDX {pattern} err: {str(e)[:60]}")
        return []


def fetch_snapshot(ts: str, url: str) -> str:
    raw = f'{WBM}/{ts}id_/{url}'
    try:
        r = requests.get(raw, headers=HDR, timeout=FETCH_TIMEOUT)
        return r.text if r.status_code == 200 else ''
    except Exception:
        return ''


def restaurant_name_from_url(url: str) -> str:
    """Last meaningful path segment after stripping action segments."""
    return h._restaurant_from_url(url, 'deliveroo-uk')


def main() -> int:
    print(f"Deliveroo UK sweep — {len(PATTERNS)} city patterns")
    print(f"Per pattern: ≤{PER_PATTERN_FETCHES} fetches, sampled by size desc\n")

    conn = sqlite3.connect(str(DB), timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    cur = conn.cursor()

    # URLs already attempted (in `prices` or known empty) — skip
    have = set(cur.execute(
        "SELECT DISTINCT url FROM prices WHERE source='wayback-deliveroo'"
    ).fetchall())
    have = {h[0] for h in have}

    total_fetches = 0
    total_hits = 0
    total_rows = 0
    yields: dict = defaultdict(list)   # ts_ym → [(url, items)]

    for pat_i, pattern in enumerate(PATTERNS, 1):
        print(f"[{pat_i}/{len(PATTERNS)}] CDX {pattern}")
        rows = query_cdx(pattern)
        if not rows:
            print(f"  no rows"); time.sleep(CDX_DELAY); continue
        print(f"  CDX returned {len(rows)} captures (collapsed by urlkey)")
        # Sort by length desc — bigger pages more likely to have a menu
        rows.sort(key=lambda r: -int(r[2]) if str(r[2]).isdigit() else 0)
        picked = rows[:PER_PATTERN_FETCHES]
        time.sleep(CDX_DELAY)

        for snap in picked:
            ts, url, sz = snap[0], snap[1], snap[2]
            if url in have:
                continue
            try:
                collection_date = datetime.strptime(
                    ts[:8], '%Y%m%d').strftime('%Y-%m-%d')
            except Exception:
                collection_date = ts[:10]
            time.sleep(FETCH_DELAY)
            html = fetch_snapshot(ts, url)
            total_fetches += 1
            if not html:
                print(f"  [{total_fetches:>3}] {ts[:8]} fetch fail  {url[-60:]}")
                continue
            items = h.parse_deliveroo_uk(html, 'GBP')
            rest = restaurant_name_from_url(url)
            if not items:
                print(f"  [{total_fetches:>3}] {ts[:8]} 0 items     {url[-60:]}")
                continue
            total_hits += 1
            yields[collection_date[:7]].append((url, len(items)))
            for name, price, currency in items:
                cur.execute(
                    "INSERT INTO prices "
                    "(restaurant_name, item_name, price, currency, country, "
                    " sector, source, collection_date, url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rest[:100], name[:200], price, currency or 'GBP',
                     'United Kingdom', 'formal', 'wayback-deliveroo',
                     collection_date, url)
                )
            conn.commit()
            total_rows += len(items)
            print(f"  [{total_fetches:>3}] {ts[:8]} {len(items):>3} items {rest[:30]}")

    conn.close()
    print(f"\n=== Summary ===")
    print(f"  Fetches attempted: {total_fetches}")
    print(f"  Hit pages:         {total_hits}")
    print(f"  Rows inserted:     {total_rows}")
    print(f"  Distinct months:   {len(yields)}")
    print(f"\n  Per-month yield:")
    for ym in sorted(yields):
        pages = yields[ym]
        total = sum(n for _, n in pages)
        print(f"    {ym}: {len(pages)} pages, {total} items")
    return 0


if __name__ == '__main__':
    sys.exit(main())

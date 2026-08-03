"""
Backfill readable restaurant names for wayback-doordash US rows.

271 of 324 (84%) wayback-doordash US restaurant_name buckets are
unreadable: 132 are bare numeric store IDs (URL had no SEO slug, e.g.
doordash.com/store/100933/) and 138 are 'junkbucket <hash>' placeholders
(URL was a $-price-filter page with no store identity at all, e.g.
doordash.com/store/$0.15 -- see _restaurant_from_url's docstring in
historical_html_scraper.py).

Found 2026-08-01 while building task-2 US candidate list: both URL shapes
still serve a real store's menu page, and that page's JSON-LD root object
is {"@type": "Restaurant", "name": "..."} regardless of what the URL
looked like. See extract_doordash_restaurant_name() in
historical_html_scraper.py. Already wired into run_target() and
doordash_us_2023_sweep.py for future sweeps; this script re-fetches each
already-unreadable URL once and updates existing rows.

Usage:
  python3 backfill_doordash_us_names.py --sample 10           # dry run, no DB writes
  python3 backfill_doordash_us_names.py --apply                # full backfill, writes DB
  python3 backfill_doordash_us_names.py --apply --limit 10     # writes DB, first 10 only
"""
import argparse
import re
import sqlite3
import time
from datetime import datetime

import requests

from historical_html_scraper import (
    CDX, CDX_BACKOFF, CDX_RETRIES, CDX_TIMEOUT, DB, FETCH_DELAY, HDR,
    extract_doordash_restaurant_name, fetch_snapshot,
)

SOURCE  = 'wayback-doordash'
COUNTRY = 'United States'
LABEL   = 'doordash-us'

UNREADABLE = re.compile(
    r'^\d+ \(doordash-us\)$|^junkbucket [0-9a-f]{8} \(doordash-us\)$'
)


def get_snapshot_for_url(url):
    params = {
        'url': url, 'output': 'json', 'fl': 'timestamp,original',
        'filter': 'statuscode:200', 'limit': 1,
    }
    for attempt in range(CDX_RETRIES + 1):
        try:
            r = requests.get(CDX, params=params, headers=HDR, timeout=CDX_TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                if len(data) < 2:
                    return None
                return data[1][0]
        except Exception:
            pass
        if attempt < CDX_RETRIES:
            time.sleep(CDX_BACKOFF)
    return None


def backfill(limit, apply_writes):
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    rows = conn.execute(
        "SELECT DISTINCT url, restaurant_name FROM prices "
        "WHERE source = ? AND country = ? ORDER BY url",
        (SOURCE, COUNTRY),
    ).fetchall()
    rows = [(u, n) for u, n in rows if UNREADABLE.match(n)]
    if limit:
        rows = rows[:limit]

    print(f"{len(rows)} unreadable-name URL(s) to process "
          f"({'APPLY' if apply_writes else 'DRY RUN — no DB writes'})")

    updated = 0
    unresolved = 0
    for i, (url, old_name) in enumerate(rows):
        print(f"[{i+1}/{len(rows)}] {url[:80]}")
        ts = get_snapshot_for_url(url)
        if not ts:
            print("    no CDX snapshot found — skip")
            unresolved += 1
            time.sleep(FETCH_DELAY)
            continue
        time.sleep(FETCH_DELAY)
        html = fetch_snapshot(ts, url)
        if not html:
            print("    fetch failed — skip")
            unresolved += 1
            continue
        new_name_raw = extract_doordash_restaurant_name(html)
        if not new_name_raw:
            print("    JSON-LD Restaurant name not found — skip")
            unresolved += 1
            continue
        new_name = f'{new_name_raw} ({LABEL})'[:100]
        print(f"    before: {old_name!r}")
        print(f"    after:  {new_name!r}")
        if apply_writes:
            conn.execute(
                "UPDATE prices SET restaurant_name = ? "
                "WHERE source = ? AND country = ? AND url = ?",
                (new_name, SOURCE, COUNTRY, url),
            )
            conn.commit()
        updated += 1

    conn.close()
    print(f"\nDone. {updated} name(s) {'updated' if apply_writes else 'would be updated'}, "
          f"{unresolved} unresolved.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=None,
                     help='Dry-run on the first N unreadable URLs (no DB writes).')
    ap.add_argument('--limit', type=int, default=None,
                     help='With --apply, only process the first N unreadable URLs.')
    ap.add_argument('--apply', action='store_true',
                     help='Actually write updates to the DB (default is dry run).')
    args = ap.parse_args()

    if args.sample is not None and args.apply:
        raise SystemExit('--sample is dry-run only; use --limit with --apply')

    limit = args.sample if args.sample is not None else args.limit
    apply_writes = args.apply

    if apply_writes:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = f'{DB}.backup_pre_doordash_us_name_backfill_{ts}'
        # sqlite3's .backup API (not a plain file copy) — WAL-safe with
        # other processes actively writing to this DB concurrently.
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(backup)
        src.backup(dst)
        dst.close(); src.close()
        print(f"DB backed up to {backup}")

    backfill(limit, apply_writes)


if __name__ == '__main__':
    main()

"""
Backfill readable restaurant names for wayback-grabfood Malaysia rows.

historical_html_scraper.py's URL-slug fallback (_restaurant_from_url) grabs
the LAST path segment of a GrabFood URL as the restaurant_name proxy — but
for GrabFood, the last segment is the store ID (e.g. 'MYDD03581'), not the
slug. The 268 rows swept before this fix all landed with raw-ID names like
'MYDD03581 (grabfood-my)'.

The fix (see historical_html_scraper.extract_grabfood_restaurant_name)
already applies to new sweeps. This script re-fetches each already-swept
URL once, pulls the true name from the same NEXT_DATA
pageRestaurantDetail.entities.<ID>.name field, and updates existing rows.

Usage:
  python3 backfill_grabfood_my_names.py --sample 10           # dry run, no DB writes
  python3 backfill_grabfood_my_names.py --apply                # full backfill, writes DB
  python3 backfill_grabfood_my_names.py --apply --limit 10     # writes DB, first 10 only
"""
import argparse
import shutil
import sqlite3
import time
from datetime import datetime

import requests

from historical_html_scraper import (
    CDX, CDX_BACKOFF, CDX_RETRIES, CDX_TIMEOUT, DB, FETCH_DELAY, HDR, WBM,
    extract_grabfood_restaurant_name, fetch_snapshot,
)

SOURCE  = 'wayback-grabfood'
COUNTRY = 'Malaysia'
LABEL   = 'grabfood-my'


def get_snapshot_for_url(url):
    """One cheap CDX lookup for an exact (already-known-archived) URL.
    Any 200-status snapshot works — a restaurant's name doesn't change
    between snapshots, so we don't need the specific one originally used.
    Retries with backoff like the pattern-search CDX calls elsewhere in
    historical_html_scraper.py — a single-attempt lookup surfaced a
    transient failure on the 10-row dry run that a retry resolved.
    """
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
                return data[1][0]  # timestamp
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
    if limit:
        rows = rows[:limit]

    print(f"{len(rows)} distinct URL(s) to process "
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
        new_name_raw = extract_grabfood_restaurant_name(html)
        if not new_name_raw:
            print("    NEXT_DATA name not found — skip")
            unresolved += 1
            continue
        new_name = f'{new_name_raw} ({LABEL})'[:100]
        changed = new_name != old_name
        print(f"    before: {old_name!r}")
        print(f"    after:  {new_name!r}" + ('' if changed else '  (unchanged)'))
        if changed and apply_writes:
            conn.execute(
                "UPDATE prices SET restaurant_name = ? "
                "WHERE source = ? AND country = ? AND url = ?",
                (new_name, SOURCE, COUNTRY, url),
            )
            conn.commit()
        if changed:
            updated += 1

    conn.close()
    print(f"\nDone. {updated} name(s) {'updated' if apply_writes else 'would be updated'}, "
          f"{unresolved} unresolved, {len(rows) - updated - unresolved} already correct/unchanged.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=None,
                     help='Dry-run on the first N distinct URLs (no DB writes).')
    ap.add_argument('--limit', type=int, default=None,
                     help='With --apply, only process the first N distinct URLs.')
    ap.add_argument('--apply', action='store_true',
                     help='Actually write updates to the DB (default is dry run).')
    args = ap.parse_args()

    if args.sample is not None and args.apply:
        raise SystemExit('--sample is dry-run only; use --limit with --apply')

    limit = args.sample if args.sample is not None else args.limit
    apply_writes = args.apply

    if apply_writes:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = f'{DB}.backup_pre_grabfood_my_name_backfill_{ts}'
        shutil.copy2(DB, backup)
        print(f"DB backed up to {backup}")

    backfill(limit, apply_writes)


if __name__ == '__main__':
    main()

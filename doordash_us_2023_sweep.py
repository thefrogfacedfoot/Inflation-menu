#!/usr/bin/env python3
"""
DoorDash US wayback sweep, 2023+ prioritized.

Context: the 2026-07-26 full-history sweep (per_period=60, max_per_target=
1200, walking 2018->2026 chronologically) was killed after 322 snapshots,
97% of which were "0 items" -- and every processed snapshot was dated 2018
or 2021, because get_distributed_snapshots() walks quarters in ascending
order and never reached 2023+ before dying. The structural probe that
justified this target (2026-06-21, 70-630 JSON-LD hits/snapshot) sampled
only 3 pages and didn't pin down which years actually carry JSON-LD.

This script queries ONLY 2023-01-01 onward, so we can find out whether the
yield is genuinely better in more recent years before re-spending the full
per-period=60/max=1200 budget on another chronological walk that might
spend most of its time on years that don't parse.

Progress tracking is DB-only (already_have() by url) -- deliberately does
NOT touch historical_html_progress.json, so it can run standalone without
the shared-file race that clobbered tonight's earlier attempt (see
historical_html_scraper.py's load_progress/save_progress locking fix).

Usage:
  python3 doordash_us_2023_sweep.py --test          # ~50-candidate probe, no DB budget spent beyond that
  python3 doordash_us_2023_sweep.py --full           # full 2023+ budget (per-period 60, max 1200)
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import historical_html_scraper as h

PATTERN    = 'doordash.com/store/*'
CURRENCY   = 'USD'
SOURCE_KEY = 'wayback-doordash'
COUNTRY    = 'United States'
SECTOR     = 'chain'
LABEL      = 'doordash-us'

FROM_YEAR = 2023
TO_YEAR   = 2026

TEST_LIMIT = 50
FULL_PER_PERIOD = 60
FULL_MAX = 1200

# CDN image-transform paths that ride under doordash.com/store/* but are
# never menu pages -- confirmed 2026-07-31: 35 of 50 raw 2023-Q1 CDX
# candidates were these (7.9% raw hit rate vs. 13.3% per distinct store).
# One hit (store 1005893) even had a `format=auto` variant that re-parsed
# the same menu a second time under a different URL -- same duplicate
# shape as the Deliveroo UK dedup issue. Filtered out before a URL is
# ever counted against --per-period, not just skipped at fetch time, so
# the budget doesn't get eaten by junk that was always going to be junk.
JUNK_MARKERS = ('height=', 'width=', 'quality=', 'format=', '/media/')


def is_junk(url):
    return any(m in url for m in JUNK_MARKERS)


def fetch_candidates(per_period, max_snapshots):
    """2023+-only candidate walk -- same CDX windowing/collapse logic as
    historical_html_scraper.get_distributed_snapshots, restricted to
    FROM_YEAR..TO_YEAR, with JUNK_MARKERS filtered out before counting
    against per_period (so a filtered quarter still fills its full quota
    with real candidates instead of coming up short)."""
    out = []
    seen = set()
    junk_skipped = 0
    for start, end in h._period_windows(FROM_YEAR, TO_YEAR):
        params = {
            'url':    PATTERN, 'from': start, 'to': end,
            'output': 'json',  'fl':   'timestamp,original',
            'filter': ['statuscode:200', 'mimetype:text/html'],
            'collapse': 'urlkey',
            'limit':  per_period * 8,   # wider than the unfiltered walk's
                                         # *4, since junk rows now get
                                         # discarded instead of counted
        }
        rows = None
        for attempt in range(h.CDX_RETRIES + 1):
            try:
                r = requests.get(h.CDX, params=params, headers=h.HDR,
                                  timeout=h.CDX_TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    rows = data[1:] if len(data) > 1 else []
                    break
                if attempt < h.CDX_RETRIES:
                    time.sleep(h.CDX_BACKOFF)
            except Exception:
                if attempt < h.CDX_RETRIES:
                    time.sleep(h.CDX_BACKOFF)
        if rows is None:
            rows = []
        taken = 0
        for row in rows:
            ts, orig = row[0], row[1]
            if orig in seen:
                continue
            seen.add(orig)
            if is_junk(orig):
                junk_skipped += 1
                continue
            out.append({'timestamp': ts, 'url': orig})
            taken += 1
            if taken >= per_period:
                break
        if max_snapshots and len(out) >= max_snapshots:
            break
        time.sleep(h.CDX_DELAY)
    return out, junk_skipped


def process(candidates, conn, fetch_delay):
    attempts = 0
    hits = 0
    rows_inserted = 0
    zero_item_count = 0
    fetch_fail_count = 0
    parse_err_count = 0

    for i, snap in enumerate(candidates):
        ts, url = snap['timestamp'], snap['url']
        if h.already_have(conn, url):
            continue
        print(f"  [{i+1}/{len(candidates)}] {ts[:8]} {url[:70]} … ",
              end='', flush=True)
        time.sleep(fetch_delay)
        html = h.fetch_snapshot(ts, url)
        if html is None:
            print("fetch fail")
            fetch_fail_count += 1
            continue
        attempts += 1
        try:
            items = h.parse_doordash(html, CURRENCY)
        except Exception as e:
            print(f"parse err {str(e)[:30]}")
            parse_err_count += 1
            continue

        rest_name = h._restaurant_from_url(url, LABEL)
        try:
            collection_date = datetime.strptime(
                ts[:8], '%Y%m%d').strftime('%Y-%m-%d')
        except Exception:
            collection_date = ts[:10]

        n = 0
        if items:
            for name, price, cur in items:
                conn.execute(
                    "INSERT INTO prices "
                    "(restaurant_name, item_name, price, currency, country, "
                    " sector, source, collection_date, url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rest_name[:100], name[:200], price, cur or CURRENCY,
                     COUNTRY, SECTOR, SOURCE_KEY, collection_date, url)
                )
                n += 1
            conn.commit()
        rows_inserted += n
        if n > 0:
            hits += 1
            print(f"{n} items")
        else:
            zero_item_count += 1
            print("0 items")

    return {
        'attempts': attempts, 'hits': hits, 'rows': rows_inserted,
        'zero_item': zero_item_count, 'fetch_fail': fetch_fail_count,
        'parse_err': parse_err_count,
    }


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--test', action='store_true',
                       help=f'~{TEST_LIMIT}-candidate probe of 2023+ yield')
    mode.add_argument('--full', action='store_true',
                       help='full 2023+ budget (per-period 60, max 1200)')
    ap.add_argument('--fetch-delay', type=float, default=h.FETCH_DELAY)
    args = ap.parse_args()

    conn = sqlite3.connect(h.DB, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')

    if args.test:
        print(f"DoorDash US 2023+ test probe (junk-filtered) — up to "
              f"{TEST_LIMIT} candidates from {FROM_YEAR}-01-01 onward")
        candidates, junk_skipped = fetch_candidates(per_period=TEST_LIMIT, max_snapshots=TEST_LIMIT)
    else:
        print(f"DoorDash US 2023+ full sweep (junk-filtered) — "
              f"per_period={FULL_PER_PERIOD}, max={FULL_MAX}, "
              f"{FROM_YEAR}-01-01 onward")
        candidates, junk_skipped = fetch_candidates(per_period=FULL_PER_PERIOD, max_snapshots=FULL_MAX)

    seen_total = len(candidates) + junk_skipped
    print(f"  Found {len(candidates)} real candidate snapshots, "
          f"{junk_skipped} junk (CDN-asset) URLs filtered out "
          f"({100 * junk_skipped / seen_total:.1f}% of {seen_total} seen)"
          if seen_total else "  Found 0 candidates")

    stats = process(candidates, conn, args.fetch_delay)
    conn.close()

    print(f"\n=== Summary ({'test' if args.test else 'full'}) ===")
    print(f"  Real candidates:           {len(candidates)}")
    print(f"  Junk filtered out:         {junk_skipped}")
    print(f"  Attempts (fetched+parsed): {stats['attempts']}")
    print(f"  Hits (>0 items):           {stats['hits']}")
    print(f"  Zero-item:                 {stats['zero_item']}")
    print(f"  Fetch failures:            {stats['fetch_fail']}")
    print(f"  Parse errors:              {stats['parse_err']}")
    print(f"  Rows inserted:             {stats['rows']}")
    if stats['attempts']:
        rate = 100 * stats['hits'] / stats['attempts']
        print(f"  Hit rate:                  {rate:.1f}%")
    return 0


if __name__ == '__main__':
    sys.exit(main())

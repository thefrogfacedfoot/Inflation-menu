"""
Build a live-target candidate shortlist for DoorDash US from the wayback
sweep pool, for manual review before anything is added to
live_scraper.TARGETS. Same pipeline as build_uk_deliveroo_candidates.py.

Build -> filter -> dedupe -> live-probe:
  1. Pull distinct (base_url, restaurant_name, item_count) from
     wayback-doordash/United States rows in `prices` (base_url = url with
     query string stripped).
  2. Drop rows whose restaurant_name is still an unresolved bare-numeric-ID
     or junkbucket placeholder -- 64 of 806 stores (see
     backfill_doordash_us_names.py's UNREADABLE regex) never got a real
     name back from either the URL slug or extract_doordash_restaurant_name();
     there's no restaurant identity to show for review on these.
  3. Drop known grocery/convenience chains via data_quality.is_grocery_or_retail.
  4. Drop anything whose base_url or name already matches an existing
     United States / doordash entry in live_scraper.TARGETS.
  5. Live-probe the remaining candidates' base_url with the same
     Playwright heuristics verify_targets.py uses for existing TARGETS.
  6. Save every candidate that probes OK/OK_TITLE_ONLY to a JSON file for
     manual review. Does NOT write to live_scraper.py or uifpi.db.

Usage:
  python3 build_us_doordash_candidates.py --out candidates_us_doordash.json
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, '.')
from live_scraper import TARGETS
from verify_targets import verify_one
from data_quality import is_grocery_or_retail

DB = 'uifpi.db'
SOURCE = 'wayback-doordash'
COUNTRY = 'United States'

# Same regex backfill_doordash_us_names.py uses to find unresolved names --
# bare numeric store ID or junkbucket-<hash> placeholder, e.g.
# "1028266 (doordash-us)" or "junkbucket 3a1f9c2e (doordash-us)".
UNREADABLE = re.compile(
    r'^\d+ \(doordash-us\)$|^junkbucket [0-9a-f]{8} \(doordash-us\)$'
)


def base_url(u):
    return u.split('?', 1)[0]


def build_pool(conn):
    rows = conn.execute(
        "SELECT restaurant_name, url FROM prices "
        "WHERE source = ? AND country = ?", (SOURCE, COUNTRY),
    ).fetchall()
    by_base = {}
    for name, url in rows:
        b = base_url(url)
        by_base.setdefault(b, {'name': name, 'item_count': 0})
        by_base[b]['item_count'] += 1
    return by_base


def existing_target_keys():
    urls, names = set(), set()
    for t in TARGETS:
        name, url, sector, source, currency, country = t
        if country == COUNTRY and source == 'doordash':
            urls.add(base_url(url).lower())
            names.add(name.lower())
    return urls, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='candidates_us_doordash.json')
    ap.add_argument('--top', type=int, default=50,
                     help='Max candidates to live-probe (ranked by item_count desc)')
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    pool = build_pool(conn)
    print(f"Pool before filtering: {len(pool)} distinct stores")

    pool = {b: v for b, v in pool.items() if not UNREADABLE.match(v['name'])}
    print(f"After unresolved-name (numeric/junkbucket) filter: {len(pool)}")

    pool = {b: v for b, v in pool.items() if not is_grocery_or_retail(v['name'])}
    print(f"After grocery/convenience filter: {len(pool)}")

    existing_urls, existing_names = existing_target_keys()
    pool = {b: v for b, v in pool.items()
            if b.lower() not in existing_urls and v['name'].lower() not in existing_names}
    print(f"After dedup against live_scraper.TARGETS: {len(pool)}")

    ranked = sorted(pool.items(), key=lambda kv: -kv[1]['item_count'])[:args.top]
    print(f"Live-probing top {len(ranked)} by item_count...")

    results = []
    for i, (b, v) in enumerate(ranked, 1):
        target = (v['name'], b, 'chain', 'doordash', 'USD', COUNTRY)
        rec = verify_one(target)
        print(f"  [{i}/{len(ranked)}] {rec['status']:<14} {v['name'][:45]:<45} "
              f"item_count={v['item_count']}")
        if rec['status'] in ('OK', 'OK_TITLE_ONLY'):
            results.append({
                'name': v['name'],
                'url': b,
                'item_count_wayback': v['item_count'],
                'live_probe_status': rec['status'],
                'live_probe_reason': rec['reason'],
            })

    payload = {
        'generated_at': datetime.now().isoformat(),
        'source_pool': SOURCE,
        'country': COUNTRY,
        'pool_size_after_filters': len(pool),
        'probed': len(ranked),
        'passed': len(results),
        'candidates': results,
    }
    with open(args.out, 'w') as fh:
        json.dump(payload, fh, indent=2)
    print(f"\n{len(results)}/{len(ranked)} passed live-probe -> {args.out}")


if __name__ == '__main__':
    main()

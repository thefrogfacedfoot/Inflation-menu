"""
Build a live-target candidate shortlist for Deliveroo UK from the wayback
sweep pool, for manual review before anything is added to live_scraper.TARGETS.

Build -> dedupe -> live-probe:
  1. Pull distinct (base_url, restaurant_name, item_count) from
     wayback-deliveroo/United Kingdom rows in `prices` (base_url = url with
     the day/time/geohash/category_id query string stripped -- matches
     deliveroo_uk_sweep.py's own store-level dedup key).
  2. Drop known grocery/convenience chains (Sainsbury's, Morrisons, Co-op,
     Asda, Waitrose, Wilko, Iceland, Aldi, Lidl, Gopuff, ...) -- these are
     supermarket SKU dumps (thousands of items), not restaurant menus, and
     would swamp a restaurant-price panel.
  3. Drop anything whose base_url or name already matches an existing
     United Kingdom / deliveroo entry in live_scraper.TARGETS.
  4. Live-probe the remaining candidates' base_url (the wayback URL's
     query-stripped form IS the live Deliveroo URL -- Deliveroo doesn't
     version its store slugs) with the same Playwright heuristics
     verify_targets.py uses for existing TARGETS.
  5. Save every candidate that probes OK/OK_TITLE_ONLY to a JSON file for
     manual review. Does NOT write to live_scraper.py or uifpi.db.

Usage:
  python3 build_uk_deliveroo_candidates.py --only-new --out candidates_uk_deliveroo.json
    --only-new  restrict the pool to stores added by the most recent
                continuation sweep (diffs against a given backup file)
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, '.')
from live_scraper import TARGETS
from verify_targets import verify_one
from data_quality import is_grocery_or_retail

DB = 'uifpi.db'
SOURCE = 'wayback-deliveroo'
COUNTRY = 'United Kingdom'


def base_url(u):
    return u.split('?', 1)[0]


def build_pool(conn, only_new_since=None):
    rows = conn.execute(
        "SELECT restaurant_name, url FROM prices "
        "WHERE source = ? AND country = ?", (SOURCE, COUNTRY),
    ).fetchall()
    by_base = {}
    for name, url in rows:
        b = base_url(url)
        by_base.setdefault(b, {'name': name, 'item_count': 0})
        by_base[b]['item_count'] += 1

    if only_new_since:
        old_conn = sqlite3.connect(only_new_since)
        old_rows = old_conn.execute(
            "SELECT url FROM prices WHERE source = ? AND country = ?",
            (SOURCE, COUNTRY),
        ).fetchall()
        old_bases = {base_url(u) for (u,) in old_rows}
        by_base = {b: v for b, v in by_base.items() if b not in old_bases}

    return by_base


def existing_target_keys():
    """base_url and name markers already in live_scraper.TARGETS for UK/deliveroo."""
    urls, names = set(), set()
    for t in TARGETS:
        name, url, sector, source, currency, country = t
        if country == COUNTRY and source == 'deliveroo':
            urls.add(base_url(url).lower())
            names.add(name.lower())
    return urls, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-new', metavar='BACKUP_DB',
                     help='Restrict pool to stores absent from this backup DB file')
    ap.add_argument('--out', default='candidates_uk_deliveroo.json')
    ap.add_argument('--top', type=int, default=50,
                     help='Max candidates to live-probe (ranked by item_count desc)')
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    pool = build_pool(conn, only_new_since=args.only_new)
    print(f"Pool before filtering: {len(pool)} distinct stores")

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
        target = (v['name'], b, 'chain', 'deliveroo', 'GBP', COUNTRY)
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

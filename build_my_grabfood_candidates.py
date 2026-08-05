"""
Build a live-target candidate shortlist for GrabFood Malaysia from the
wayback sweep pool, for manual review before anything is added to
live_scraper.TARGETS.

Build -> filter -> dedupe -> live-probe (single authoritative stage, not
the generic-heuristic-then-recheck split build_uk_deliveroo_candidates.py
uses): GrabFood requires a seeded delivery-location cookie or a bare
page.goto() silently serves the generic country landing page on the SAME
url (no visible redirect, HTTP 200) -- confirmed 2026-08-03. verify_targets.
verify_one()'s plain navigation is not a valid probe for this platform, so
there is no cheap-but-correct first pass to run before the real one; the
warmup+retry navigation dominates cost either way, so this goes straight
to reverify_my_grabfood_candidates.recheck_one() (mirrors live_scraper.
scrape_grabfood's own navigation, then confirms with the real parser) for
every candidate instead of a crude regex-threshold heuristic.

  1. Pull distinct (base_url, restaurant_name, item_count) from
     wayback-grabfood/Malaysia rows in `prices` (base_url = url with query
     string stripped).
  2. Drop rows whose restaurant_name is still the raw-store-ID fallback
     (extract_grabfood_restaurant_name() found nothing in NEXT_DATA, so
     _restaurant_from_url() used the URL's ID segment instead, e.g.
     "1 C3JUECE3UFN2TN (grabfood-my)") -- these have no real identity to
     show for review, unlike the human-readable slugs/NEXT_DATA names.
  3. Drop known grocery/convenience chains via data_quality.is_grocery_or_retail.
  4. Drop anything whose base_url or name already matches an existing
     Malaysia / grabfood entry in live_scraper.TARGETS.
  5. Live-probe the remaining candidates' base_url with recheck_one()
     (warmup, up to 3 nav attempts re-warming on landing-page redirect,
     then parse_grabfood on the rendered HTML).
  6. Save every candidate with verdict CONFIRMED_LIVE to a JSON file for
     manual review. Does NOT write to live_scraper.py or uifpi.db.

Usage:
  python3 build_my_grabfood_candidates.py --out candidates_my_grabfood.json
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, '.')
from live_scraper import TARGETS
from data_quality import is_grocery_or_retail
from reverify_my_grabfood_candidates import recheck_one

DB = 'uifpi.db'
SOURCE = 'wayback-grabfood'
COUNTRY = 'Malaysia'

# Raw-store-ID fallback names, e.g. "1 C3JUECE3UFN2TN (grabfood-my)" --
# see _restaurant_from_url()'s docstring in historical_html_scraper.py.
ID_FALLBACK = re.compile(r'^\d\s+[A-Z0-9]{8,}\s*\(grabfood-my\)$')


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
        if country == COUNTRY and source == 'grabfood':
            urls.add(base_url(url).lower())
            names.add(name.lower())
    return urls, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='candidates_my_grabfood.json')
    ap.add_argument('--top', type=int, default=50,
                     help='Max candidates to live-probe (ranked by item_count desc)')
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    pool = build_pool(conn)
    print(f"Pool before filtering: {len(pool)} distinct stores")

    pool = {b: v for b, v in pool.items() if not ID_FALLBACK.match(v['name'])}
    print(f"After raw-store-ID fallback filter: {len(pool)}")

    pool = {b: v for b, v in pool.items() if not is_grocery_or_retail(v['name'])}
    print(f"After grocery/convenience filter: {len(pool)}")

    existing_urls, existing_names = existing_target_keys()
    pool = {b: v for b, v in pool.items()
            if b.lower() not in existing_urls and v['name'].lower() not in existing_names}
    print(f"After dedup against live_scraper.TARGETS: {len(pool)}")

    ranked = sorted(pool.items(), key=lambda kv: -kv[1]['item_count'])[:args.top]
    print(f"Live-probing top {len(ranked)} by item_count (warmup + real parser)...")

    results = []
    for i, (b, v) in enumerate(ranked, 1):
        rec = recheck_one(v['name'], b)
        print(f"  [{i}/{len(ranked)}] {rec['verdict']:<16} "
              f"real_items={rec.get('real_item_count', 0):<4} "
              f"{v['name'][:45]:<45} item_count_wayback={v['item_count']}")
        if rec['verdict'] == 'CONFIRMED_LIVE':
            results.append({
                'name': v['name'],
                'url': b,
                'item_count_wayback': v['item_count'],
                'recheck': rec,
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

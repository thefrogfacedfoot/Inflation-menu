"""
One-off resume of the MY GrabFood cooldown probe from the 29/380 confirmed
point (candidates_my_grabfood.json: pool_size_after_filters=380, probed=48,
passed=29, generated_at 2026-08-06T18:05). Re-derives the same ranked pool
(build_my_grabfood_candidates.py's build->filter->rank logic, verified
stable: rank 39/43/44 match the file's last three CONFIRMED_LIVE entries)
and probes ranks 49-58 (the next 10), stopping immediately on 5 consecutive
DEAD_REDIRECTED (same penalty-guard rule as candidates_my_grabfood_full_
retry_20260805.log). Appends new CONFIRMED_LIVE entries to the existing
JSON and updates probed/passed. Does NOT write to live_scraper.py or
uifpi.db.
"""
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')
from live_scraper import TARGETS
from data_quality import is_grocery_or_retail
from reverify_my_grabfood_candidates import recheck_one

DB = 'uifpi.db'
SOURCE = 'wayback-grabfood'
COUNTRY = 'Malaysia'
OUT = Path('candidates_my_grabfood.json')
ID_FALLBACK = re.compile(r'^\d\s+[A-Z0-9]{8,}\s*\(grabfood-my\)$')

START_RANK = 49
BATCH = 10


def base_url(u):
    return u.split('?', 1)[0]


def build_ranked_pool(conn):
    rows = conn.execute(
        "SELECT restaurant_name, url FROM prices WHERE source=? AND country=?",
        (SOURCE, COUNTRY),
    ).fetchall()
    by_base = {}
    for name, url in rows:
        b = base_url(url)
        by_base.setdefault(b, {'name': name, 'item_count': 0})
        by_base[b]['item_count'] += 1
    pool = {b: v for b, v in by_base.items() if not ID_FALLBACK.match(v['name'])}
    pool = {b: v for b, v in pool.items() if not is_grocery_or_retail(v['name'])}
    existing_urls, existing_names = set(), set()
    for t in TARGETS:
        name, url, sector, source, currency, country = t
        if country == COUNTRY and source == 'grabfood':
            existing_urls.add(base_url(url).lower())
            existing_names.add(name.lower())
    pool = {b: v for b, v in pool.items()
            if b.lower() not in existing_urls and v['name'].lower() not in existing_names}
    return sorted(pool.items(), key=lambda kv: -kv[1]['item_count'])


def main():
    conn = sqlite3.connect(DB)
    ranked = build_ranked_pool(conn)
    print(f"Reconstructed pool: {len(ranked)} (expect 380)")
    if len(ranked) != 380:
        print("!! Pool size drifted from the recorded 380 -- stopping without probing "
              "(ranking may no longer line up with the recorded probed=48).")
        return 1

    data = json.loads(OUT.read_text())
    print(f"Existing file: probed={data['probed']} passed={data['passed']} "
          f"candidates_stored={len(data['candidates'])}")

    batch = ranked[START_RANK - 1: START_RANK - 1 + BATCH]
    print(f"Probing ranks {START_RANK}-{START_RANK + len(batch) - 1} "
          f"({len(batch)} candidates)\n")

    consecutive_dead = 0
    new_confirmed = 0
    processed = 0
    stopped_reason = None

    for i, (b, v) in enumerate(batch, START_RANK):
        rec = recheck_one(v['name'], b)
        processed += 1
        print(f"[{i}/{len(ranked)}] {rec['verdict']:<16} "
              f"real_items={rec.get('real_item_count', 0):<4} "
              f"{v['name'][:50]:<50} item_count_wayback={v['item_count']}")

        if rec['verdict'] == 'CONFIRMED_LIVE':
            consecutive_dead = 0
            data['candidates'].append({
                'name': v['name'],
                'url': b,
                'item_count_wayback': v['item_count'],
                'recheck': rec,
            })
            new_confirmed += 1
        elif rec['verdict'] == 'DEAD_REDIRECTED':
            consecutive_dead += 1
            if consecutive_dead >= 5:
                stopped_reason = (f"penalty suspected: {consecutive_dead} consecutive "
                                   f"DEAD_REDIRECTED landing-page redirects")
                print(f"\nPenalty guard: {consecutive_dead} consecutive DEAD_REDIRECTED -- stopping")
                break
        else:
            consecutive_dead = 0

    data['probed'] = data['probed'] + processed
    data['passed'] = data['passed'] + new_confirmed
    data['generated_at'] = datetime.now().isoformat()
    OUT.write_text(json.dumps(data, indent=2))

    print(f"\nBatch summary")
    print(f"  processed_this_run={processed}")
    print(f"  new_confirmed_this_run={new_confirmed}")
    print(f"  total_probed={data['probed']}")
    print(f"  total_confirmed={data['passed']}")
    print(f"  stopped_reason={stopped_reason or 'batch complete (no penalty triggered)'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

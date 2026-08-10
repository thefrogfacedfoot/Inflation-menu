"""
Live-probe driver for the 2026-08-10 TARGETS expansion push (103 -> 200 goal).

Reuses the two authoritative rechecks already in the repo rather than
inventing a third heuristic:
  * Deliveroo UK  -> reverify_uk_deliveroo_candidates.recheck_one
                     (final-URL slug check + real parse_deliveroo_uk items)
  * GrabFood      -> generalised copy of
                     reverify_my_grabfood_candidates.recheck_one, which
                     replicates live_scraper.scrape_grabfood's warmup +
                     location-cookie seed + landing-shell retry loop, then
                     requires real parse_grabfood items.

Both were built to catch the failure mode that produced the UK
49%-false-positive result: a dead store silently serving a generic
listing/landing page that still passes a naive "page has prices" check.

Pools (all ranked by wayback item_count desc, deduped against TARGETS,
grocery/retail filtered, /restaurant/ only for GrabFood):
  uk   wayback-deliveroo / United Kingdom   (807 unprobed)
  my   wayback-grabfood  / Malaysia         (ranks 59+, 322 unprobed)
  sg   wayback-grabfood  / Singapore        (12)
  vn   wayback-grabfood  / Vietnam          (98)

Writes results incrementally to probe_expansion_20260810.json after every
probe, so the run is resumable and interruptible. Does NOT write to
live_scraper.py or uifpi.db (DB is opened read-only).

Usage:
  python3 probe_expansion_20260810.py --pool uk --limit 150
  python3 probe_expansion_20260810.py --pool my --limit 80
  python3 probe_expansion_20260810.py --pool reverify-my   # re-probe the 34
"""
import argparse
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import (
    COUNTRY_LOCALE, BROWSER_LAUNCH_ARGS, USER_AGENTS, _STEALTH,
    _warmup, _looks_like_grabfood_landing, _looks_like_block, _human_mouse_jitter,
    TARGETS,
)
from historical_html_scraper import parse_grabfood
from reverify_uk_deliveroo_candidates import recheck_one as uk_recheck
from data_quality import is_grocery_or_retail

DB = 'file:uifpi.db?mode=ro'
# Per-pool result file. Runs against different platforms are launched
# concurrently, and load/save here is a whole-file read-modify-write, so a
# shared file would let one run clobber the other's results.
OUT = Path('probe_expansion_20260810.json')

# Names/slugs that mark a store the platform itself has retired.
INACTIVE = re.compile(r'\[inactv|-inactive-|\(inactive\)', re.I)
# Many GrabFood rows carry the store id instead of a name ("4 C2D3FFK2UCA3E6",
# "SGDD06431", "VNGFVN000006ic") because the wayback parser could not recover
# one. Rather than pattern-matching which names are id-shaped, GrabFood pools
# just take the name from the URL slug -- it is the authoritative human name
# for every food.grab.com /restaurant/<slug>/<id> URL, id-fallback or not.

# Grocery/retail that data_quality.GROCERY_RETAIL_NAME_MARKERS misses:
# either the sweep stored a misspelt name ("morrisosns"), or the DB name is
# an id-fallback so the chain is only visible in the URL slug. Applied to
# BOTH name and url.
EXTRA_GROCERY = re.compile(
    r'morrisosn|morriso|amazon\s*-?\s*fresh|one\s*-?\s*stop|food\s*-?\s*warehouse|'
    r'farmfoods|heron\s*-?\s*foods|home\s*-?\s*bargains|poundstretcher|savers|'
    r'holland\s*&?\s*-?\s*barrett|bestway|premier\s*-?\s*store|pharmacy|off\s*-?\s*licence|'
    r'don-?don-?donki|donki|fairprice|cold-?storage|aeon|guardian|watsons|'
    r'bee-?cheng-?hiang|vinmart|winmart|bach-?hoa|convenience',
    re.I,
)

# Inter-probe pacing for food.grab.com. Raised from 3-7s after the 2026-08-10
# throttling incident (11 live then 10 straight false "dead").
GRABFOOD_SLEEP = (8, 16)

POOLS = {
    'uk': dict(source='wayback-deliveroo', country='United Kingdom',
               platform='deliveroo', currency='GBP'),
    'my': dict(source='wayback-grabfood', country='Malaysia',
               platform='grabfood', currency='MYR'),
    'sg': dict(source='wayback-grabfood', country='Singapore',
               platform='grabfood', currency='SGD'),
    'vn': dict(source='wayback-grabfood', country='Vietnam',
               platform='grabfood', currency='VND'),
}


def base_url(u):
    return u.split('?', 1)[0]


# --------------------------------------------------------------------------
# GrabFood recheck, generalised over country/currency.
# Body is reverify_my_grabfood_candidates.recheck_one with COUNTRY/'MYR'
# lifted into parameters -- same navigation, same landing detection, same
# "real parse_grabfood items" bar.
# --------------------------------------------------------------------------
def grabfood_recheck(url, country, currency, timeout_ms=45_000):
    locale, tz = COUNTRY_LOCALE.get(country, ('en-SG', 'Asia/Singapore'))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_LAUNCH_ARGS)
        try:
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent=random.choice(USER_AGENTS), locale=locale, timezone_id=tz,
            )
            page = context.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass

            _warmup(page, 'grabfood', country)

            http_status = None
            still_landing = True
            for attempt in range(1, 4):
                try:
                    resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
                    http_status = resp.status if resp else None
                except Exception as e:
                    browser.close()
                    return {'verdict': 'NAV_ERROR', 'detail': str(e)[:200],
                            'real_item_count': 0}
                page.wait_for_timeout(random.randint(3_000, 5_000))
                _human_mouse_jitter(page)

                if _looks_like_block(page, http_status):
                    browser.close()
                    return {'verdict': 'BLOCKED', 'http_status': http_status,
                            'real_item_count': 0}

                still_landing = _looks_like_grabfood_landing(page)
                if not still_landing:
                    break
                if attempt < 3:
                    _warmup(page, 'grabfood', country)
                    page.wait_for_timeout(random.randint(5_000, 7_500))

            page.wait_for_timeout(2_000)
            final_url = page.url
            html = page.content()
            browser.close()
        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            raise

    items = parse_grabfood(html, currency)
    if still_landing:
        verdict = 'DEAD_REDIRECTED'
    elif not items:
        verdict = 'DEAD_NO_ITEMS'
    else:
        verdict = 'CONFIRMED_LIVE'
    return {
        'verdict': verdict,
        'http_status': http_status,
        'final_url': final_url,
        'real_item_count': len(items),
        'sample_items': [f'{pr} {c} {n[:40]}' for n, pr, c in items[:5]],
    }


def name_from_slug(url):
    """Recover a readable name from a GrabFood /restaurant/<slug>/<id> URL."""
    from urllib.parse import unquote
    try:
        slug = url.rstrip('/').rsplit('/', 2)[-2]
    except Exception:
        return None
    slug = unquote(slug)
    slug = re.sub(r'-delivery$', '', slug)
    return slug.replace('-', ' ').strip().title() or None


def already_probed_urls(pool_key):
    """URLs a previous expansion run already spent a live probe on.

    Must be an explicit URL set, not a rank offset: this script's pool recipe
    differs from the earlier one (it recovers names from the URL slug instead
    of dropping id-fallback rows), so the ranking is NOT the same list and
    "skip the first 58" would both re-probe and wrongly skip stores.
    """
    seen = set()
    if pool_key == 'uk':
        d = json.loads(Path('candidates_uk_deliveroo.json').read_text())
        for k in ('confirmed_live', 'dead_on_recheck'):
            for c in d.get(k, []):
                seen.add(base_url(c['url']).lower())
    elif pool_key == 'my':
        # Rebuild the ORIGINAL recipe's ranking (build_my_grabfood_candidates /
        # resume_my_grabfood_batch: drop id-fallback names, grocery filter,
        # TARGETS dedupe) and take its first 58 -- the ranks that run probed.
        conn = sqlite3.connect(DB, uri=True)
        rows = conn.execute(
            "SELECT restaurant_name, url FROM prices WHERE source=? AND country=?",
            ('wayback-grabfood', 'Malaysia'),
        ).fetchall()
        by = {}
        for name, url in rows:
            b = base_url(url)
            by.setdefault(b, {'name': name, 'item_count': 0})
            by[b]['item_count'] += 1
        orig_fallback = re.compile(r'^\d\s+[A-Z0-9]{8,}\s*\(grabfood-my\)$')
        by = {b: v for b, v in by.items() if not orig_fallback.match(v['name'])}
        by = {b: v for b, v in by.items() if not is_grocery_or_retail(v['name'])}
        eu = {base_url(t[1]).lower() for t in TARGETS
              if t[5] == 'Malaysia' and t[3] == 'grabfood'}
        en = {t[0].lower() for t in TARGETS
              if t[5] == 'Malaysia' and t[3] == 'grabfood'}
        by = {b: v for b, v in by.items()
              if b.lower() not in eu and v['name'].lower() not in en}
        ranked = sorted(by.items(), key=lambda kv: -kv[1]['item_count'])
        if len(ranked) != 380:
            raise SystemExit(
                f'MY original-recipe pool is {len(ranked)}, expected 380 -- the '
                'recorded probed=58 prefix no longer identifies the same stores; '
                'refusing to guess which are already probed.')
        seen = {b.lower() for b, _ in ranked[:58]}
    return seen


def build_pool(cfg):
    conn = sqlite3.connect(DB, uri=True)
    rows = conn.execute(
        "SELECT restaurant_name, url FROM prices WHERE source=? AND country=?",
        (cfg['source'], cfg['country']),
    ).fetchall()
    by = {}
    for name, url in rows:
        b = base_url(url)
        by.setdefault(b, {'name': name, 'item_count': 0})
        by[b]['item_count'] += 1

    out = {}
    for b, v in by.items():
        if is_grocery_or_retail(v['name']) or is_grocery_or_retail(b):
            continue
        if EXTRA_GROCERY.search(v['name']) or EXTRA_GROCERY.search(b):
            continue
        if INACTIVE.search(v['name']) or INACTIVE.search(b):
            continue
        if cfg['platform'] == 'grabfood':
            if '/restaurant/' not in b:
                continue  # /chain/ URLs are a known-dead shape -- never probe
            better = name_from_slug(b)
            if not better:
                continue
            v = {**v, 'name': better}
        out[b] = v

    ex_u = {base_url(t[1]).lower() for t in TARGETS
            if t[5] == cfg['country'] and t[3] == cfg['platform']}
    ex_n = {t[0].lower() for t in TARGETS
            if t[5] == cfg['country'] and t[3] == cfg['platform']}
    out = {b: v for b, v in out.items()
           if b.lower() not in ex_u and v['name'].lower() not in ex_n}
    return sorted(out.items(), key=lambda kv: -kv[1]['item_count'])


def drop_trailing_dead(rec, n):
    """Remove the trailing run of DEAD_REDIRECTED records so a throttled
    window is re-probed later instead of being trusted as a real verdict."""
    removed = 0
    while rec['probed'] and removed < n:
        if rec['probed'][-1]['recheck']['verdict'] != 'DEAD_REDIRECTED':
            break
        rec['probed'].pop()
        removed += 1
    return removed


def load_results():
    if OUT.exists():
        return json.loads(OUT.read_text())
    return {'started_at': datetime.now().isoformat(), 'pools': {}}


def save_results(data):
    data['updated_at'] = datetime.now().isoformat()
    OUT.write_text(json.dumps(data, indent=2))


def run_pool(pool_key, limit, dead_guard):
    cfg = POOLS[pool_key]
    data = load_results()
    rec = data['pools'].setdefault(pool_key, {'probed': [], 'confirmed': 0})
    done = {base_url(r['url']).lower() for r in rec['probed']}

    ranked = build_pool(cfg)
    prior = already_probed_urls(pool_key)
    skip = done | prior
    print(f"[{pool_key}] pool={len(ranked)} probed_by_earlier_runs={len(prior)} "
          f"probed_this_run={len(done)}")
    queue = [(b, v) for b, v in ranked if b.lower() not in skip][:limit]
    print(f"[{pool_key}] probing {len(queue)}\n")

    consecutive_dead = 0
    for i, (b, v) in enumerate(queue, 1):
        t0 = time.time()
        try:
            if cfg['platform'] == 'deliveroo':
                r = uk_recheck(v['name'], b)
            else:
                r = grabfood_recheck(b, cfg['country'], cfg['currency'])
        except Exception as e:
            r = {'verdict': 'PROBE_ERROR', 'detail': str(e)[:200], 'real_item_count': 0}
        r.setdefault('real_item_count', 0)

        rec['probed'].append({
            'name': v['name'], 'url': b,
            'item_count_wayback': v['item_count'],
            'sector_hint': None, 'recheck': r,
            'elapsed_s': round(time.time() - t0, 1),
        })
        if r['verdict'] == 'CONFIRMED_LIVE':
            rec['confirmed'] += 1
        save_results(data)

        print(f"[{pool_key} {i}/{len(queue)}] {r['verdict']:<16} "
              f"items={r['real_item_count']:<4} {v['name'][:48]:<50} "
              f"wb={v['item_count']}")

        # Platform penalty guard: a run of landing-page redirects on GrabFood
        # means the IP is being throttled, not that the stores are dead.
        # Those verdicts are artefacts, so DISCARD them rather than recording
        # them -- otherwise a throttled window permanently marks live stores
        # dead (observed 2026-08-10: 11 straight live, then 10 straight
        # "dead" stores that had 192-200 items three days earlier).
        if cfg['platform'] == 'grabfood':
            if r['verdict'] == 'DEAD_REDIRECTED':
                consecutive_dead += 1
                if consecutive_dead >= dead_guard:
                    dropped = drop_trailing_dead(rec, consecutive_dead)
                    save_results(data)
                    print(f"\n[{pool_key}] penalty guard: {consecutive_dead} "
                          f"consecutive DEAD_REDIRECTED -- discarded {dropped} "
                          f"suspect verdicts for re-probe, cooling down 300s")
                    time.sleep(300)
                    consecutive_dead = 0
            else:
                consecutive_dead = 0
            time.sleep(random.uniform(*GRABFOOD_SLEEP))
        else:
            time.sleep(random.uniform(1, 3))

    conf = sum(1 for p in rec['probed'] if p['recheck']['verdict'] == 'CONFIRMED_LIVE')
    print(f"\n[{pool_key}] total probed={len(rec['probed'])} confirmed={conf} "
          f"hit_rate={conf / max(1, len(rec['probed'])):.1%}")
    save_results(data)


def run_reverify_my(dead_guard=6):
    """Re-probe the 34 already-CONFIRMED_LIVE MY candidates (stale 3-4 days).

    Carries the same penalty guard as run_pool: without it a throttled window
    silently converts live stores into DEAD_REDIRECTED verdicts.
    """
    data = load_results()
    rec = data['pools'].setdefault('reverify-my', {'probed': [], 'confirmed': 0})
    consecutive_dead = 0
    done = {base_url(r['url']).lower() for r in rec['probed']}
    cands = [c for c in json.loads(Path('candidates_my_grabfood.json').read_text())['candidates']
             if base_url(c['url']).lower() not in done]
    print(f"[reverify-my] re-probing {len(cands)} previously-confirmed candidates\n")
    for i, c in enumerate(cands, 1):
        t0 = time.time()
        try:
            r = grabfood_recheck(base_url(c['url']), 'Malaysia', 'MYR')
        except Exception as e:
            r = {'verdict': 'PROBE_ERROR', 'detail': str(e)[:200], 'real_item_count': 0}
        r.setdefault('real_item_count', 0)
        rec['probed'].append({
            'name': c['name'], 'url': base_url(c['url']),
            'item_count_wayback': c.get('item_count_wayback'),
            'prev_item_count': c['recheck'].get('real_item_count'),
            'recheck': r, 'elapsed_s': round(time.time() - t0, 1),
        })
        if r['verdict'] == 'CONFIRMED_LIVE':
            rec['confirmed'] += 1
        save_results(data)
        print(f"[reverify-my {i}/{len(cands)}] {r['verdict']:<16} "
              f"items={r['real_item_count']:<4} (was {c['recheck'].get('real_item_count')}) "
              f"{c['name'][:45]}")

        if r['verdict'] == 'DEAD_REDIRECTED':
            consecutive_dead += 1
            if consecutive_dead >= dead_guard:
                dropped = drop_trailing_dead(rec, consecutive_dead)
                save_results(data)
                print(f"\n[reverify-my] penalty guard: {consecutive_dead} consecutive "
                      f"DEAD_REDIRECTED -- discarded {dropped} suspect verdicts "
                      f"for re-probe, cooling down 300s")
                time.sleep(300)
                consecutive_dead = 0
        else:
            consecutive_dead = 0
        time.sleep(random.uniform(*GRABFOOD_SLEEP))
    conf = sum(1 for p in rec['probed'] if p['recheck']['verdict'] == 'CONFIRMED_LIVE')
    print(f"\n[reverify-my] probed={len(rec['probed'])} still_live={conf}")
    save_results(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pool', required=True,
                    choices=list(POOLS) + ['reverify-my'])
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--dead-guard', type=int, default=6)
    a = ap.parse_args()
    global OUT
    OUT = Path(f'probe_expansion_20260810_{a.pool}.json')
    if a.pool == 'reverify-my':
        run_reverify_my()
    else:
        run_pool(a.pool, a.limit, a.dead_guard)


if __name__ == '__main__':
    main()

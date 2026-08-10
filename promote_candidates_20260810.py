"""
Turn confirmed live-probe results into live_scraper.TARGETS tuples.

Reads every probe_expansion_20260810_*.json / probe_direct_20260810_*.json
result file, keeps only CONFIRMED_LIVE rows, then applies the quality gates
that the probe itself cannot judge:

  1. Retail leakage -- petrol-station forecourts and convenience shops pass a
     "menu has priced items" probe but are not restaurants (e.g. "bp
     canonmills", 16 items). Dropped.
  2. Duplicate stores -- the same outlet listed under two slugs
     ("pure pizza morningside" / "...morningside drive", identical item
     counts). Keeps the higher item count.
  3. Sector label -- the repo has no chain/independent classifier; the
     existing labels were assigned by hand. This derives one from the data:
     a brand with >= CHAIN_MIN_OUTLETS distinct outlets in that country's
     wayback pool is 'chain', otherwise 'independent'. Names already carrying
     a hand-assigned label in TARGETS inherit it, so the new rows stay
     consistent with the old ones.

Prints the full proposed list for review. Only writes live_scraper.py when
run with --apply, and always takes a timestamped .bak first.

Usage:
  python3 promote_candidates_20260810.py               # review (default)
  python3 promote_candidates_20260810.py --apply
"""
import argparse
import glob
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')
from live_scraper import TARGETS

DB = 'file:uifpi.db?mode=ro'
CHAIN_MIN_OUTLETS = 3

# Minimum real items for a candidate to be worth a nightly scrape slot.
# Direct chain sites need a higher bar: several "passed" the probe on a single
# junk row scraped out of a banner (Miller's Ale House -> 1 item
# "Raise Your Cups $7.00"; Red Rooster -> 1 item "NEW $25.00"), which is a
# priced DOM node, not a menu.
MIN_ITEMS = {'deliveroo': 5, 'grabfood': 5, 'direct': 15}

# Hard cap on total TARGETS entries after promotion.
TARGET_CAP = 250

# Passed the probe but excluded by explicit decision.
EXCLUDE_NAMES = {
    # 62 items, but the scraped names are the size variants ("Standard",
    # "Large", "Medium") with no product name, so every pizza collapses onto
    # the same basket key and corrupts basket-level pricing.
    'pizza hut australia',
}

# US direct entries that have NEVER produced a row (verified 2026-08-10
# against `prices`), retired from TARGETS by decision. Whataburger was also
# duplicated: active here and already present in the dead-target graveyard.
US_RETIRE = [
    "Captain D's", 'Cava', "Denny's", 'IHOP', 'Olive Garden',
    'Outback Steakhouse', 'Sonic Drive-In', "Wendy's", 'Whataburger',
    'White Castle', "Zaxby's",
]

PLATFORM_META = {
    'uk': ('deliveroo', 'GBP', 'United Kingdom', 'wayback-deliveroo'),
    'my': ('grabfood', 'MYR', 'Malaysia', 'wayback-grabfood'),
    'sg': ('grabfood', 'SGD', 'Singapore', 'wayback-grabfood'),
    'vn': ('grabfood', 'VND', 'Vietnam', 'wayback-grabfood'),
    'reverify-my': ('grabfood', 'MYR', 'Malaysia', 'wayback-grabfood'),
}

# Forecourts / convenience shops / non-restaurant retail that still expose a
# priced item list.
NOT_A_RESTAURANT = re.compile(
    r'\b(bp|shell|esso|texaco|gulf|jet)\b|petrol|forecourt|garage|'
    r'newsagent|off licence|off-licence|vape|pharmacy|chemist',
    re.I,
)

SUFFIX = re.compile(r'\s*\((?:deliveroo-uk|grabfood-\w+)\)\s*$', re.I)


def clean_name(raw):
    return SUFFIX.sub('', raw).strip()


def title_name(raw, platform):
    n = clean_name(raw)
    if platform == 'deliveroo':
        n = n.title()
    tag = {'deliveroo': ' (Deliveroo)', 'grabfood': ''}[platform]
    return n + tag


# Brands known to be multi-outlet chains that the outlet-count heuristic
# under-counts, because the wayback pool only sampled one or two of their
# stores. Without this, national chains land in 'independent' and skew the
# sector split that index_builder's INFORMAL_WEIGHTS blend depends on.
KNOWN_CHAINS = re.compile(
    r'\b(subway|mcdonald|kfc|burger king|domino|pizza hut|pizzaexpress|pizza express|'
    r'papa john|taco bell|nando|wagamama|greggs|costa|starbucks|tim hortons|'
    r'little dessert shop|creams|pepes piri piri|pepe.s|morleys|german doner|'
    r'shake shack|five guys|leon|itsu|yo sushi|mooboo|chatime|gong cha|t4|'
    r'krispy kreme|dunkin|baskin|cinnabon|auntie anne|wingstop|popeyes|'
    r'chicken treat|red rooster|oporto|schnitz|grill.d|boost juice|'
    r'marrybrown|secret recipe|oldtown|pappa rich|papparich|texas chicken|'
    r'the coffee bean|old chang kee|toast box|ya kun|breadtalk|paradise dynasty|'
    r'crystal jade|putien|song fa|tealive|zus coffee|richiamo)\b',
    re.I,
)


def brand_key(name):
    """First two significant tokens -- 'subway acocks green' -> 'subway acocks'.

    Two tokens, not one: a single token collapses distinct brands onto the
    same key ('pizza hut' and 'pizza pilgrims' both -> 'pizza'), which made
    Pizza Hut inherit Pizza Pilgrims' 'independent' label.
    """
    toks = [t for t in re.split(r'[^a-z0-9]+', clean_name(name).lower()) if t]
    toks = [t for t in toks if not t.isdigit()]
    if not toks:
        return ''
    return ' '.join(toks[:2])


def outlet_counts(source, country):
    """Distinct outlets per brand in that country's wayback pool."""
    conn = sqlite3.connect(DB, uri=True)
    rows = conn.execute(
        "SELECT DISTINCT restaurant_name, url FROM prices WHERE source=? AND country=?",
        (source, country)).fetchall()
    seen = defaultdict(set)
    for name, url in rows:
        seen[brand_key(name)].add(url.split('?', 1)[0].lower())
    return {k: len(v) for k, v in seen.items()}


def existing_sector_by_brand():
    """Inherit hand-assigned labels so new rows agree with the old ones."""
    out = {}
    for t in TARGETS:
        out.setdefault(brand_key(t[0]), Counter())[t[2]] += 1
    return {k: c.most_common(1)[0][0] for k, c in out.items()}


DIRECT_META = {'us': ('direct', 'USD', 'United States'),
               'au': ('direct', 'AUD', 'Australia')}


def load_confirmed():
    """All CONFIRMED_LIVE probe rows, keyed by base URL."""
    by_url = {}

    def add(url, name, items, pool, platform):
        url = url.split('?', 1)[0]
        prev = by_url.get(url)
        if prev is None or items > prev['items']:
            by_url[url] = {'name': name, 'url': url, 'items': items,
                           'pool': pool, 'platform': platform}

    for path in sorted(glob.glob('probe_expansion_20260810_*.json')):
        pool_data = json.loads(Path(path).read_text())
        for pool, rec in pool_data.get('pools', {}).items():
            if pool not in PLATFORM_META:
                continue
            for p in rec['probed']:
                if p['recheck']['verdict'] == 'CONFIRMED_LIVE':
                    add(p['url'], p['name'], p['recheck']['real_item_count'],
                        pool, PLATFORM_META[pool][0])

    for path in sorted(glob.glob('probe_direct_20260810_*.json')):
        cc = Path(path).stem.rsplit('_', 1)[-1]
        if cc not in DIRECT_META:
            continue
        for r in json.loads(Path(path).read_text()).get('results', []):
            if r.get('verdict') == 'CONFIRMED_LIVE':
                add(r.get('menu_url') or r['homepage'], r['name'],
                    r.get('items', 0), f'direct-{cc}', 'direct')
    return by_url


def retire_us_entries(text):
    """Comment out the never-producing US direct tuples.

    Commented out rather than deleted, matching the existing [verifier:DEAD]
    graveyard convention in this file -- the entry stays readable and
    reversible, but is out of the live TARGETS list.
    """
    lines = text.split('\n')
    out, retired, i = [], 0, 0
    targets_start = next(i for i, l in enumerate(lines) if l.startswith('TARGETS = ['))
    while i < len(lines):
        line = lines[i]
        matched = None
        if i > targets_start and re.match(r'\s*\("', line):
            for nm in US_RETIRE:
                if line.strip().startswith(f'("{nm}",'):
                    matched = nm
                    break
        if not matched:
            out.append(line)
            i += 1
            continue
        # Consume the whole tuple (balanced parens) and comment it out.
        depth, block = 0, []
        while i < len(lines):
            depth += lines[i].count('(') - lines[i].count(')')
            block.append(lines[i])
            i += 1
            if depth <= 0:
                break
        out.append('    # [audit:NEVER-PRODUCED 2026-08-10] no rows in `prices`, '
                   'ever — retired')
        out.extend('    # ' + b.strip() for b in block)
        retired += 1
    return '\n'.join(out), retired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    existing_urls = {t[1].split('?', 1)[0].rstrip('/').lower() for t in TARGETS}
    existing_names = {t[0].lower() for t in TARGETS}
    inherited = existing_sector_by_brand()

    confirmed = load_confirmed()
    counts_cache = {}
    proposed, dropped = [], []
    seen_dupe = {}

    for url, c in sorted(confirmed.items(), key=lambda kv: -kv[1]['items']):
        if c['platform'] == 'direct':
            cc = c['pool'].rsplit('-', 1)[-1]
            platform, currency, country = DIRECT_META[cc]
            source = None
            name = clean_name(c['name'])
        else:
            platform, currency, country, source = PLATFORM_META[c['pool']]
            name = title_name(c['name'], platform)

        if clean_name(c['name']).lower() in EXCLUDE_NAMES:
            dropped.append((name, 'excluded by decision (generic item names)',
                            c['items']))
            continue
        if c['items'] < MIN_ITEMS.get(platform, 5):
            dropped.append((name, f'only {c["items"]} item(s) — below '
                                  f'{MIN_ITEMS.get(platform, 5)} minimum', c['items']))
            continue
        if NOT_A_RESTAURANT.search(clean_name(c['name'])):
            dropped.append((name, 'not-a-restaurant (retail/forecourt)', c['items']))
            continue
        if url.rstrip('/').lower() in existing_urls or name.lower() in existing_names:
            dropped.append((name, 'already in TARGETS', c['items']))
            continue

        # Duplicate outlet: same country + same brand + identical item count.
        dkey = (country, brand_key(c['name']), c['items'])
        if dkey in seen_dupe:
            dropped.append((name, f'duplicate of {seen_dupe[dkey]}', c['items']))
            continue
        seen_dupe[dkey] = name

        bk = brand_key(c['name'])
        known = KNOWN_CHAINS.search(clean_name(c['name']))
        if known:
            sector, why = 'chain', f'known chain ({known.group(0).lower()})'
        elif bk in inherited:
            sector, why = inherited[bk], 'inherited from existing TARGETS'
        elif source is None:
            # Direct-site candidates are national chain websites by
            # construction (that is how they were selected).
            sector, why = 'chain', 'national chain website'
        else:
            counts_cache.setdefault(source, {})
            if country not in counts_cache[source]:
                counts_cache[source][country] = outlet_counts(source, country)
            outlets = counts_cache[source][country].get(bk, 1)
            if outlets >= CHAIN_MIN_OUTLETS:
                sector, why = 'chain', f'{outlets} outlets in pool'
            else:
                sector, why = 'independent', f'{outlets} outlet(s) in pool'

        proposed.append({'tuple': (name, url, sector, platform, currency, country),
                         'items': c['items'], 'why': why})
        existing_names.add(name.lower())
        existing_urls.add(url.rstrip('/').lower())

    # ---- cap + country-balanced allocation -------------------------------
    # Every candidate here is already probe-verified, so the cap decides which
    # verified ones make it. Round-robin by country (best item_count first
    # within each) rather than a global item_count sort, which would hand
    # nearly every slot to the UK pool purely because it is the largest.
    kept_base = len(TARGETS) - len(US_RETIRE)
    budget = max(0, TARGET_CAP - kept_base)
    if len(proposed) > budget:
        by_country = defaultdict(list)
        for p in proposed:
            by_country[p['tuple'][5]].append(p)
        for lst in by_country.values():
            lst.sort(key=lambda p: -p['items'])
        picked, order = [], sorted(by_country)
        while len(picked) < budget and any(by_country[c] for c in order):
            for c in order:
                if by_country[c] and len(picked) < budget:
                    picked.append(by_country[c].pop(0))
        cut = [p for p in proposed if p not in picked]
        for p in cut:
            dropped.append((p['tuple'][0], f'over {TARGET_CAP}-target cap', p['items']))
        proposed = picked

    print(f'CONFIRMED_LIVE probe rows: {len(confirmed)}')
    print(f'US entries retired:        {len(US_RETIRE)}')
    print(f'Proposed new TARGETS:      {len(proposed)} (cap budget {budget})')
    print(f'Dropped:                   {len(dropped)}\n')

    by_cc = Counter(p['tuple'][5] for p in proposed)
    by_sec = Counter(p['tuple'][2] for p in proposed)
    print('By country:', dict(by_cc))
    print('By sector :', dict(by_sec))
    print(f'\nTARGETS after promotion: {len(TARGETS)} - {len(US_RETIRE)} retired '
          f'+ {len(proposed)} new = {kept_base + len(proposed)} '
          f'(cap {TARGET_CAP})\n')

    print('--- proposed ---')
    for p in proposed:
        n, u, s, pl, cur, co = p['tuple']
        print(f'  {co[:14]:15} {s:11} items={p["items"]:<5} {n[:44]:46} [{p["why"]}]')
    if dropped:
        print('\n--- dropped ---')
        for n, why, it in dropped:
            print(f'  {n[:46]:48} items={it:<5} {why}')

    if not a.apply:
        print('\n(review only -- rerun with --apply to write live_scraper.py)')
        return 0

    src = Path('live_scraper.py')
    bak = f'live_scraper.py.bak_{datetime.now():%Y%m%d_%H%M%S}'
    shutil.copy(src, bak)
    text = src.read_text()
    text, retired = retire_us_entries(text)
    print(f'Retired {retired} US direct entries that never produced a row')

    block = ['', f'    # ── Expansion probed {datetime.now():%Y-%m-%d} '
                 f'({len(proposed)} added) ──',
             '    # Every entry below passed a live probe with the real menu parser',
             '    # (parse_deliveroo_uk / parse_grabfood) plus landing-page and',
             '    # redirect detection -- see probe_expansion_20260810.py.']
    for p in proposed:
        n, u, s, pl, cur, co = p['tuple']
        esc = n.replace('"', r'\"')
        block.append(f'    ("{esc}",\n     "{u}",\n     "{s}", "{pl}", "{cur}", "{co}"),')
    insert = '\n'.join(block) + '\n'

    lines = text.split('\n')
    end = None
    for i, line in enumerate(lines):
        if line.startswith('TARGETS = ['):
            depth = 0
            for j in range(i, len(lines)):
                depth += lines[j].count('[') - lines[j].count(']')
                if depth == 0:
                    end = j
                    break
            break
    if end is None:
        print('ERROR: could not locate the end of the TARGETS list', file=sys.stderr)
        return 1

    lines.insert(end, insert)
    src.write_text('\n'.join(lines))
    print(f'\nWrote {len(proposed)} entries into live_scraper.py (backup: {bak})')
    return 0


if __name__ == '__main__':
    sys.exit(main())

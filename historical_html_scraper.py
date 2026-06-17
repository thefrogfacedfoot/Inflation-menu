"""
Phase 1 — historical HTML scraper.

For each (country, platform) winner from the Phase 0 matrix, do a
time-distributed Wayback CDX walk, fetch each archived snapshot via
the id_ raw-bytes path, and extract menu prices using a per-platform
parser. Insert item-level rows into uifpi.db with source = wayback-<platform>.

This complements the existing TripAdvisor pipeline in historical_scraper.py;
it does NOT modify that file's targets. The two scrapers coexist:
  - historical_scraper.py    — TripAdvisor Restaurant_Review pages
                               (review-quoted prices + $-tier markers)
  - historical_html_scraper  — Real menu pages on Zomato / MenuPages /
                               Eatigo / Menulog / GrabFood / TripAdvisor MX

Resumable: any (snapshot_url) already in `prices` is skipped at fetch time.
Schema: extends `prices` (already has all columns we need).

Usage:
  python3 historical_html_scraper.py                    # all winners
  python3 historical_html_scraper.py 'India: zomato NCR'
  python3 historical_html_scraper.py --max-per-target 200
"""
import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, 'uifpi.db')
HDR  = {'User-Agent': 'UIFPI-research-pipeline (academic; contact via repo issues)'}
CDX  = 'http://web.archive.org/cdx/search/cdx'
WBM  = 'https://web.archive.org/web'

CDX_TIMEOUT       = 90
CDX_LIMIT         = 30000
CDX_DELAY         = 3.0
CDX_RETRIES       = 2
CDX_BACKOFF       = 15
FETCH_TIMEOUT     = 45
FETCH_RETRIES     = 2
FETCH_BACKOFF     = 8
FETCH_DELAY       = 1.5      # per worker
DEFAULT_PER_PERIOD = 5       # snapshots per quarter window per platform
DEFAULT_MAX_PER_TARGET = 500
PROGRESS_FILE = os.path.join(BASE, 'historical_html_progress.json')

# ── Currency regexes for DOM fallback ────────────────────────────────────────

CURRENCY_REGEXES = {
    'USD': re.compile(r'\$\s?(\d+(?:\.\d{2})?)'),
    'INR': re.compile(r'(?:₹|Rs\.?\s)\s?(\d+(?:[.,]\d{2})?)'),
    'IDR': re.compile(r'Rp\.?\s?([\d.,]+)'),
    'THB': re.compile(r'(?:฿|THB)\s?(\d+(?:\.\d{2})?)'),
    'AUD': re.compile(r'A?\$\s?(\d+(?:\.\d{2})?)'),
    'SGD': re.compile(r'S\$\s?(\d+(?:\.\d{2})?)'),
    'PHP': re.compile(r'(?:₱|PHP)\s?(\d+(?:\.\d{2})?)'),
    'MXN': re.compile(r'\$\s?(\d+(?:\.\d{2})?)'),
    # Added 2026-06-17 (Track C). BRL uses 'R$' with comma decimal; EUR
    # in DE locale also uses comma decimal and frequently writes '€' at
    # either end of the number. ZAR uses bare 'R' which collides with
    # English words — validate downstream that the regex match is on a
    # price field, not body text.
    'BRL': re.compile(r'R\$\s?(\d+(?:[.,]\d{2})?)'),
    'EUR': re.compile(r'(?:€\s?(\d+(?:[.,]\d{2})?)|(\d+(?:[.,]\d{2})?)\s?€)'),
    'ZAR': re.compile(r'\bR\s?(\d+(?:[.,]\d{2})?)'),
}

# ── Generic JSON-LD price walker ─────────────────────────────────────────────

def _walk_ld(node, items, name_ctx=None):
    """Walk a JSON-LD tree collecting (name, price, currency) where MenuItem
    or Offer or Product carries a price."""
    if isinstance(node, dict):
        nm = (node.get('name') or name_ctx)
        cur_node = node.get('priceCurrency')
        price_node = node.get('price')
        if price_node is None:
            offers = node.get('offers')
            if isinstance(offers, dict):
                price_node = offers.get('price')
                cur_node = cur_node or offers.get('priceCurrency')
            elif isinstance(offers, list) and offers:
                if isinstance(offers[0], dict):
                    price_node = offers[0].get('price')
                    cur_node = cur_node or offers[0].get('priceCurrency')
        if price_node is None:
            ps = node.get('priceSpecification')
            if isinstance(ps, dict):
                price_node = ps.get('price')
                cur_node = cur_node or ps.get('priceCurrency')
        # Skip non-menu @types (addresses, coordinates, restaurant-level
        # entities). TripAdvisor encodes FoodEstablishment with a priceRange
        # tier; restaurants have averagePrice fields that are restaurant-
        # level not item-level. Only emit prices from menu-shaped nodes.
        bad_types = {'PostalAddress', 'GeoCoordinates', 'Restaurant',
                     'FoodEstablishment', 'Place', 'LocalBusiness',
                     'BreadcrumbList', 'AggregateRating', 'Review'}
        if nm and price_node is not None and node.get('@type') not in bad_types:
            try:
                p = float(re.sub(r'[^\d.]', '', str(price_node)))
            except Exception:
                p = None
            if p and 0 < p < 100_000:
                items.append((str(nm)[:120], p, cur_node))
        for v in node.values():
            _walk_ld(v, items, nm)
    elif isinstance(node, list):
        for v in node:
            _walk_ld(v, items, name_ctx)


def extract_jsonld(html):
    """Return list of (name, price, currency_or_None) from all JSON-LD blocks."""
    if not html:
        return []
    out = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    ):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        _walk_ld(obj, out)
    # Dedup
    seen = set(); uniq = []
    for n, p, c in out:
        k = (n, round(p, 2), c)
        if k in seen:
            continue
        seen.add(k); uniq.append((n, p, c))
    return uniq


def extract_nextdata(html):
    """Pull __NEXT_DATA__ JSON blob and walk for prices the same way."""
    if not html or '__NEXT_DATA__' not in html:
        return []
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    )
    if not m:
        return []
    try:
        obj = json.loads(m.group(1))
    except Exception:
        return []
    out = []
    _walk_ld(obj, out)
    seen = set(); uniq = []
    for n, p, c in out:
        k = (n, round(p, 2), c)
        if k in seen:
            continue
        seen.add(k); uniq.append((n, p, c))
    return uniq


def extract_zomato_costfortwo(html, currency):
    """Zomato pre-2020 restaurant pages publish 'cost for two people'
    as a restaurant-level average meal price rather than item-level prices.
    Extract that single signal per page.

    Returns [('cost_for_two', price, currency)] or [].
    """
    if not html:
        return []
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    # Patterns like "₹1,600 for two people" or "Rs. 1600 for two"
    patterns = [
        r'(?:₹|Rs\.?\s)\s?([\d,]+)\s*for\s*two',
        r'Rp\.?\s?([\d.,]+)\s*for\s*two',
        r'₱\s?([\d,]+)\s*for\s*two',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            raw = m.group(1)
            # IDR uses dots as thousand separators with no decimals
            if currency == 'IDR':
                raw = raw.replace('.', '').replace(',', '')
            else:
                raw = raw.replace(',', '')
            try:
                p = float(raw)
            except ValueError:
                continue
            if p > 0:
                return [('cost_for_two', p, currency)]
    return []


# ── Per-platform parsers ─────────────────────────────────────────────────────

def parse_zomato(html, currency):
    """Zomato pre-2020 archived pages don't expose item-level prices in DOM
    or JSON-LD — they show 'cost for two people' as a restaurant-level
    average meal price. Extract that single signal per page; treat it as
    item_name='cost_for_two' so the index can roll it up per restaurant.
    """
    items = extract_jsonld(html)
    if items:
        return _coerce(items, currency)
    return _coerce(extract_zomato_costfortwo(html, currency), currency)


def parse_menupages(html, currency):
    """MenuPages: Schema.org Menu → MenuSection → MenuItem. The JSON-LD
    walker hits these cleanly (200+ items/page in validation). No DOM
    fallback — better an empty parse than junk."""
    return _coerce(extract_jsonld(html), currency)


def parse_eatigo(html, currency):
    """Eatigo BKK: validation found 0 LD prices and the sampled pages were
    mostly category/listing URLs. Returns empty; Thailand will need a
    different source or fall back to the Numbeo proxy."""
    return _coerce(extract_jsonld(html), currency)


def parse_menulog(html, currency):
    """Menulog: NEXT_DATA has the menu structure, JSON-LD as backup."""
    items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_grabfood(html, currency):
    """GrabFood SG archived: NEXT_DATA + JSON-LD."""
    items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_tripadvisor_mx(html, currency):
    """TripAdvisor MX restaurant pages: JSON-LD MenuItem when present.
    Most pages only have FoodEstablishment with priceRange (a tier
    marker) — we explicitly skip those via the _walk_ld @type guard."""
    return _coerce(extract_jsonld(html), currency)


# ── Track C parsers (BR / DE / ZA), added 2026-06-17 ─────────────────────────

def parse_ubereats(html, currency):
    """Uber Eats per-country archived pages. Sample probes show JSON-LD
    with Menu / MenuItem nodes; NEXT_DATA is sometimes present but the
    price fields live in JSON-LD. Same shape as parse_menupages.
    """
    return _coerce(extract_jsonld(html), currency)


def parse_lieferando(html, currency):
    """Lieferando.de (Just Eat Takeaway DE) archived menu pages.
    Probe shows LD + ND both present with 102 EUR hits in a single
    sample. NEXT_DATA is the higher-yield path; fall back to LD."""
    items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_tripadvisor_za(html, currency):
    """TripAdvisor ZA restaurant pages. Same parser shape as
    parse_tripadvisor_mx: JSON-LD MenuItem when present, FoodEstablishment
    priceRange tier markers explicitly skipped by the _walk_ld @type
    guard. (See the 2026-06-17 tier-marker purge for context.)"""
    return _coerce(extract_jsonld(html), currency)


def _coerce(items, default_currency):
    """Normalise (name, price, currency_or_None) → standard tuples."""
    out = []
    for n, p, c in items:
        cur = c or default_currency
        out.append((n, p, cur))
    return out


# ── Targets ───────────────────────────────────────────────────────────────────
# (country, sector, platform_label, source_key, url_pattern, currency, parser_fn)

TARGETS = [
    ('United States', 'formal', 'menupages',     'wayback-menupages',
     'menupages.com/*', 'USD', parse_menupages),
    ('India',         'formal', 'zomato-ncr',    'wayback-zomato',
     'zomato.com/ncr/*', 'INR', parse_zomato),
    ('Indonesia',     'formal', 'zomato-jakarta','wayback-zomato',
     'zomato.com/jakarta/*', 'IDR', parse_zomato),
    ('Thailand',      'formal', 'eatigo-bkk',    'wayback-eatigo',
     'eatigo.com/th/bangkok/*', 'THB', parse_eatigo),
    ('Australia',     'formal', 'menulog',       'wayback-menulog',
     'menulog.com.au/restaurants/*', 'AUD', parse_menulog),
    ('Philippines',   'formal', 'zomato-manila', 'wayback-zomato',
     'zomato.com/manila/*', 'PHP', parse_zomato),
    ('Singapore',     'formal', 'grabfood-sg',   'wayback-grabfood',
     'food.grab.com/sg/en/restaurant/*', 'SGD', parse_grabfood),
    ('Mexico',        'formal', 'tripadvisor-mx','wayback-tripadvisor',
     'tripadvisor.com.mx/Restaurant_Review*', 'MXN', parse_tripadvisor_mx),
    # Track C — added 2026-06-17 after the BR/DE/ZA Phase 0 probe.
    # See coverage_report_br_de_za.md + docs/track_b_c_findings_2026-06-17.md.
    # Smoke-test each with --per-period 2 before a full sweep; iFood pages
    # and TripAdvisor BR/DE returned HTTP 503 in probing and may need
    # different headers or a Cloudflare bypass.
    ('Brazil',        'formal', 'ubereats-br',   'wayback-ubereats',
     'ubereats.com/br/*', 'BRL', parse_ubereats),
    ('Brazil',        'formal', 'ifood-rj',      'wayback-ifood',
     'ifood.com.br/delivery/rio-de-janeiro-rj/*', 'BRL', parse_lieferando),
    ('Germany',       'formal', 'lieferando',    'wayback-lieferando',
     'lieferando.de/speisekarte/*', 'EUR', parse_lieferando),
    ('Germany',       'formal', 'wolt-de',       'wayback-wolt',
     'wolt.com/de/deu/*', 'EUR', parse_lieferando),
    ('South Africa',  'formal', 'tripadvisor-za','wayback-tripadvisor',
     'tripadvisor.co.za/Restaurant_Review*', 'ZAR', parse_tripadvisor_za),
    ('South Africa',  'formal', 'ubereats-za',   'wayback-ubereats',
     'ubereats.com/za/*', 'ZAR', parse_ubereats),
]


# ── CDX walk (time-distributed) ──────────────────────────────────────────────

def _period_windows(from_year, to_year):
    out = []
    for y in range(from_year, to_year + 1):
        for q in range(4):
            m0 = q * 3 + 1
            m1 = q * 3 + 3
            last = {3: 31, 6: 30, 9: 30, 12: 31}[m1]
            out.append((f'{y:04d}{m0:02d}01', f'{y:04d}{m1:02d}{last}'))
    return out


def get_distributed_snapshots(pattern, per_period, max_snapshots,
                              from_year=2018, to_year=2026):
    out = []
    seen = set()
    for start, end in _period_windows(from_year, to_year):
        params = {
            'url':    pattern, 'from': start, 'to': end,
            'output': 'json',  'fl':   'timestamp,original',
            'filter': ['statuscode:200', 'mimetype:text/html'],
            'collapse': 'urlkey',
            'limit':  per_period * 4,
        }
        rows = None
        for attempt in range(CDX_RETRIES + 1):
            try:
                r = requests.get(CDX, params=params, headers=HDR,
                                 timeout=CDX_TIMEOUT)
                if r.status_code == 200:
                    data = r.json()
                    rows = data[1:] if len(data) > 1 else []
                    break
                if attempt < CDX_RETRIES:
                    time.sleep(CDX_BACKOFF)
            except Exception:
                if attempt < CDX_RETRIES:
                    time.sleep(CDX_BACKOFF)
        if rows is None:
            rows = []
        taken = 0
        for row in rows:
            ts, orig = row[0], row[1]
            if orig in seen:
                continue
            seen.add(orig)
            out.append({'timestamp': ts, 'url': orig})
            taken += 1
            if taken >= per_period:
                break
        if max_snapshots and len(out) >= max_snapshots:
            break
        time.sleep(CDX_DELAY)
    return out


def fetch_snapshot(ts, url):
    raw_url = f'{WBM}/{ts}id_/{url}'
    for attempt in range(FETCH_RETRIES + 1):
        try:
            r = requests.get(raw_url, headers=HDR, timeout=FETCH_TIMEOUT)
            if r.status_code != 200:
                if attempt < FETCH_RETRIES:
                    time.sleep(FETCH_BACKOFF)
                    continue
                return None
            return r.text
        except Exception:
            if attempt < FETCH_RETRIES:
                time.sleep(FETCH_BACKOFF)
    return None


# ── DB helpers ───────────────────────────────────────────────────────────────

def already_have(conn, url):
    return conn.execute(
        "SELECT 1 FROM prices WHERE url = ? LIMIT 1", (url,)
    ).fetchone() is not None


def insert_items(conn, country, sector, source_key, url, ts, items):
    if not items:
        return 0
    try:
        collection_date = datetime.strptime(ts[:8], '%Y%m%d').strftime('%Y-%m-%d')
    except Exception:
        collection_date = ts[:10]
    n = 0
    for name, price, currency in items:
        conn.execute(
            "INSERT INTO prices "
            "(restaurant_name, item_name, price, currency, country, sector, "
            " source, collection_date, url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name[:100], name[:200], price, currency, country, sector,
             source_key, collection_date, url)
        )
        n += 1
    conn.commit()
    return n


# ── Runner ───────────────────────────────────────────────────────────────────

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as fh:
            return json.load(fh)
    return {}


def save_progress(p):
    with open(PROGRESS_FILE, 'w') as fh:
        json.dump(p, fh, indent=2)


def run_target(target, per_period, max_per_target):
    country, sector, label, src_key, pat, currency, parser = target
    key = f'{country}:{label}'
    print(f"\n{'='*70}\n  {key}  ({pat})\n{'='*70}")
    progress = load_progress()
    info = progress.get(key, {})
    snaps = info.get('snapshots')
    done  = set(info.get('done_urls', []))
    if not snaps:
        print(f"  Querying CDX (distributed, per_period={per_period}, "
              f"max={max_per_target}) …")
        snaps = get_distributed_snapshots(pat, per_period, max_per_target)
        print(f"  Found {len(snaps)} candidate snapshots")
        progress[key] = {'snapshots': snaps, 'done_urls': list(done),
                         'status': 'in_progress'}
        save_progress(progress)

    conn = sqlite3.connect(DB, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')

    parse_attempts = 0
    parse_hits     = 0
    rows_inserted  = 0

    for i, snap in enumerate(snaps):
        ts, url = snap['timestamp'], snap['url']
        if url in done:
            continue
        if already_have(conn, url):
            done.add(url); continue
        print(f"  [{i+1}/{len(snaps)}] {ts[:8]} {url[:70]} … ",
              end='', flush=True)
        time.sleep(FETCH_DELAY)
        html = fetch_snapshot(ts, url)
        if html is None:
            print("fetch fail")
            done.add(url)
            progress[key]['done_urls'] = list(done)
            save_progress(progress)
            continue
        parse_attempts += 1
        try:
            items = parser(html, currency)
        except Exception as e:
            print(f"parse err {str(e)[:30]}")
            done.add(url)
            progress[key]['done_urls'] = list(done)
            save_progress(progress)
            continue
        # Use the URL slug as a stable restaurant_name proxy when parser
        # doesn't return useful names — but here items already carry name.
        # Strip restaurant name from the URL for the row's restaurant_name col.
        rest_name = _restaurant_from_url(url, label)
        # Override item name's "restaurant_name" with the slug, keep item name
        n = 0
        if items:
            try:
                collection_date = datetime.strptime(
                    ts[:8], '%Y%m%d').strftime('%Y-%m-%d')
            except Exception:
                collection_date = ts[:10]
            for name, price, cur in items:
                conn.execute(
                    "INSERT INTO prices "
                    "(restaurant_name, item_name, price, currency, country, "
                    " sector, source, collection_date, url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (rest_name[:100], name[:200], price, cur or currency,
                     country, sector, src_key, collection_date, url)
                )
                n += 1
            conn.commit()
        rows_inserted += n
        if n > 0:
            parse_hits += 1
            print(f"{n} items")
        else:
            print("0 items")
        done.add(url)
        if (i + 1) % 10 == 0:
            progress[key]['done_urls'] = list(done)
            save_progress(progress)

    progress[key]['done_urls'] = list(done)
    progress[key]['status']    = 'complete'
    save_progress(progress)
    conn.close()
    print(f"\n  {key}: {parse_attempts} attempts, {parse_hits} with items, "
          f"{rows_inserted} rows inserted")
    return {
        'target': key, 'attempts': parse_attempts,
        'hits': parse_hits, 'rows': rows_inserted,
    }


def _restaurant_from_url(url, platform_label):
    """Extract a restaurant slug for restaurant_name col."""
    # Strip query / fragment
    u = url.split('?', 1)[0].split('#', 1)[0]
    parts = [p for p in u.rstrip('/').split('/') if p]
    # Last meaningful path component is usually the restaurant slug
    slug = parts[-1] if parts else url
    slug = slug.replace('-', ' ').replace('_', ' ')[:80]
    return f'{slug} ({platform_label})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='*',
                    help='Optional target keys (e.g., "India: zomato NCR"). '
                         'Default = all winners.')
    ap.add_argument('--per-period', type=int, default=DEFAULT_PER_PERIOD)
    ap.add_argument('--max-per-target', type=int, default=DEFAULT_MAX_PER_TARGET)
    ap.add_argument('--list', action='store_true', help='List targets and exit')
    args = ap.parse_args()

    if args.list:
        for t in TARGETS:
            print(f"  {t[0]:<14} {t[2]:<20} pattern={t[4]}")
        return

    selected = TARGETS
    if args.targets:
        keys = {a.strip().lower() for a in args.targets}
        selected = [t for t in TARGETS
                    if f'{t[0]}: {t[2]}'.lower() in keys or
                       t[2].lower() in keys]
        if not selected:
            print("No targets matched."); return

    print(f"Historical HTML scraper — {len(selected)} target(s)")
    print(f"per_period={args.per_period}, max_per_target={args.max_per_target}\n")

    summary = []
    for t in selected:
        summary.append(run_target(t, args.per_period, args.max_per_target))

    print(f"\n{'='*70}\nDone.")
    print(f"{'target':<40} {'attempts':>9} {'hits':>5} {'rows':>7}")
    for s in summary:
        print(f"  {s['target']:<38} {s['attempts']:>9} {s['hits']:>5} {s['rows']:>7}")


if __name__ == '__main__':
    main()

"""
UIFPI — Historical Price Scraper (Wayback Machine)
Finds archived TripAdvisor restaurant pages via the CDX API,
fetches them from archive.org, parses whatever price signals exist,
and stores them in uifpi.db with the actual archived date.

Run order: after migrate_db.py, independent of live_scraper.py.
Progress is saved to historical_progress.json so runs can be resumed.
"""
import json
import os
import re
import sqlite3
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH            = 'uifpi.db'
PROGRESS_FILE      = 'historical_progress.json'
CDX_BASE           = 'http://web.archive.org/cdx/search/cdx'
WBM_BASE           = 'https://web.archive.org/web'
SNAPSHOTS_PER_COUNTRY = 50          # CDX limit per country
MIN_CONTENT_BYTES  = 3_072          # skip archive shells < 3 KB
CDX_DELAY          = 3.0            # seconds between CDX API calls
FETCH_DELAY        = 4.0            # seconds between Wayback fetches
RETRY_ATTEMPTS     = 3
RETRY_BACKOFF      = 10             # seconds before retry

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
}

# CDX URL patterns per country.
# Uses TripAdvisor geo IDs (g######) to restrict results to the correct city/region.
# Domain-level patterns like tripadvisor.com.sg/* don't work — the .sg TLD is just a
# locale for Singaporean users who review restaurants worldwide; it isn't geo-restricted.
#
# Geo IDs used:
#   g294265 = Singapore city
#   g298570 = Kuala Lumpur, Malaysia
#   g294229 = Jakarta, Indonesia
#   g293916 = Bangkok, Thailand
#   g304554 = Mumbai, India
#   g60763  = New York City, USA
#   g186338 = London, UK
#   g255068 = Sydney, Australia
COUNTRY_CONFIG = {
    'Singapore': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g294265*',
        'currency': 'SGD',
        'price_re': r'S\$\s*([\d,]+(?:\.\d{1,2})?)',
    },
    'Malaysia': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g298570*',
        'currency': 'MYR',
        'price_re': r'RM\s*([\d,]+(?:\.\d{1,2})?)',
    },
    'Indonesia': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g294229*',
        'currency': 'IDR',
        'price_re': r'Rp\.?\s*([\d.,]+)',
    },
    'Thailand': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g293916*',
        'currency': 'THB',
        'price_re': r'฿\s*([\d,]+)',
    },
    'India': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g304554*',
        'currency': 'INR',
        'price_re': r'₹\s*([\d,]+)',
    },
    'United States': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g60763*',
        'currency': 'USD',
        'price_re': r'\$(\d+(?:\.\d{1,2})?)',
    },
    'United Kingdom': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g186338*',
        'currency': 'GBP',
        'price_re': r'£(\d+(?:\.\d{1,2})?)',
    },
    'Australia': {
        'pattern':  'tripadvisor.com/Restaurant_Review-g255068*',
        'currency': 'AUD',
        'price_re': r'\$(\d+(?:\.\d{1,2})?)',
    },
}


# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT,
            item_name TEXT,
            price REAL,
            currency TEXT,
            price_usd REAL,
            country TEXT DEFAULT 'Singapore',
            sector TEXT,
            source TEXT,
            collection_date TEXT,
            url TEXT
        )
    ''')
    conn.commit()
    return conn


def already_have_url(conn, url):
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM prices WHERE url = ? AND source = ?', (url, 'wayback'))
    return c.fetchone()[0] > 0


# ── Progress tracking ─────────────────────────────────────────────────────────

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


# ── CDX API ───────────────────────────────────────────────────────────────────

def get_cdx_snapshots(url_pattern, limit=SNAPSHOTS_PER_COUNTRY,
                      from_year=2018, to_year=2024):
    """Return list of {timestamp, url} dicts from Wayback CDX."""
    params = {
        'url':      url_pattern,
        'output':   'json',
        'fl':       'timestamp,original',
        'limit':    limit,
        'from':     f'{from_year}0101',
        'to':       f'{to_year}1231',
        'collapse': 'urlkey',       # one snapshot per unique page
        'filter':   'statuscode:200',
    }
    for attempt in range(RETRY_ATTEMPTS):
        try:
            r = requests.get(CDX_BASE, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data or len(data) < 2:
                return []
            return [{'timestamp': row[0], 'url': row[1]} for row in data[1:]]
        except Exception as e:
            print(f"    CDX attempt {attempt+1} failed: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF)
    return []


# ── Wayback fetcher ───────────────────────────────────────────────────────────

def fetch_snapshot(timestamp, url):
    """Fetch archived page; returns HTML string or None if too small / failed."""
    wayback_url = f'{WBM_BASE}/{timestamp}/{url}'
    for attempt in range(RETRY_ATTEMPTS):
        try:
            r = requests.get(wayback_url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                return None
            if len(r.content) < MIN_CONTENT_BYTES:
                return None     # empty archive shell
            return r.text
        except Exception as e:
            print(f"      fetch attempt {attempt+1} failed: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF)
    return None


# ── Price extraction ──────────────────────────────────────────────────────────

def extract_restaurant_name(soup):
    """Best-effort restaurant name from archived TripAdvisor HTML."""
    for sel in (
        'h1[data-test-target="top-info-header"]',
        'h1.ui_header',
        'h1',
        'title',
    ):
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            # Strip " - TripAdvisor" suffix if present
            for suffix in (' - TripAdvisor', ' - Menu', ' | TripAdvisor'):
                text = text.replace(suffix, '')
            if text and len(text) > 2:
                return text[:100]
    return 'Unknown Restaurant'


def extract_ld_menu_items(obj, depth=0):
    """Recursively extract MenuItem prices from JSON-LD."""
    if depth > 10 or not isinstance(obj, dict):
        return []
    items = []
    if obj.get('@type') == 'MenuItem':
        name = obj.get('name', '')
        offers = obj.get('offers', {})
        price = None
        if isinstance(offers, dict):
            price = offers.get('price')
        elif isinstance(offers, list) and offers:
            price = offers[0].get('price')
        if name and price is not None:
            try:
                items.append((str(name)[:200], float(price)))
            except (ValueError, TypeError):
                pass
    for key in ('hasMenuSection', 'hasMenuItem', 'itemListElement', 'menu'):
        child = obj.get(key)
        if isinstance(child, list):
            for c in child:
                items.extend(extract_ld_menu_items(c, depth + 1))
        elif isinstance(child, dict):
            items.extend(extract_ld_menu_items(child, depth + 1))
    return items


def parse_idr_price(raw):
    """Parse IDR price string: '25.000' or '25,000' → 25000.0"""
    # IDR uses dots as thousand separators
    cleaned = raw.replace('.', '').replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


PRICE_RANGE_TIERS = {
    '$':        1,  'Inexpensive':    1,
    '$$':       2,  'Moderate':       2,
    '$$$':      3,  'Fine Dining':    3,
    '$$$$':     4,  'Ultra Fine':     4,
    '$$ - $$$': 2,  '$$-$$$':         2,
    '$ - $$':   1,  '$-$$':           1,
    '$$$ - $$$$':3, '$$$-$$$$':       3,
}


def price_range_to_tier(raw):
    """
    Convert a TripAdvisor priceRange string to a numeric tier (1–4).
    Returns None if unrecognised.
    """
    raw = (raw or '').strip()
    for key, tier in PRICE_RANGE_TIERS.items():
        if key.lower() == raw.lower():
            return tier
    # Count dollar signs as a fallback
    count = raw.count('$')
    if 1 <= count <= 4:
        return count
    return None


def extract_prices(html, country, config):
    """
    Extract (item_name, price) pairs from archived TripAdvisor HTML.

    Strategy 1 — FoodEstablishment JSON-LD priceRange
        TripAdvisor embeds a FoodEstablishment schema on every restaurant page
        with a 'priceRange' field like '$', '$$', '$$-$$$' etc.
        We convert this to a numeric tier (1–4) which gives a consistent
        historical price-level signal even when item prices are unavailable.

    Strategy 2 — Explicit MenuItem JSON-LD
        A small fraction of restaurants have full menu markup. Captured when
        present (rare on TripAdvisor but worth keeping).

    Strategy 3 — Currency regex on page text
        Catches prices quoted in user reviews (e.g. "paid S$25 per dish").
        Coarser signal, kept as secondary.
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    restaurant_name_ld = None

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            obj = json.loads(script.string or '')
        except (json.JSONDecodeError, TypeError):
            continue

        objs = obj if isinstance(obj, list) else [obj]
        for o in objs:
            t = o.get('@type', '')

            # Strategy 1: FoodEstablishment priceRange
            if t == 'FoodEstablishment':
                name = o.get('name', '')
                price_range = o.get('priceRange', '')
                tier = price_range_to_tier(price_range)
                if tier and name:
                    restaurant_name_ld = name
                    items.append((
                        f'Price tier (TripAdvisor: {price_range})',
                        float(tier),
                    ))

            # Strategy 2: MenuItem
            items.extend(extract_ld_menu_items(o))

    if items:
        return soup, items[:30], restaurant_name_ld

    # Strategy 3: Currency regex on visible text
    text = soup.get_text(separator=' ')
    pattern = config['price_re']
    matches = re.findall(pattern, text)

    seen = set()
    for raw in matches:
        if country == 'Indonesia':
            price = parse_idr_price(raw)
        else:
            try:
                price = float(raw.replace(',', ''))
            except ValueError:
                continue
        if price is None or price <= 0 or price >= 500_000:
            continue
        if price in seen:
            continue
        seen.add(price)
        items.append(('Review-quoted price (historical)', price))

    return soup, items[:20], None


# ── Main collection loop ──────────────────────────────────────────────────────

def run(countries=None):
    conn = init_db()
    progress = load_progress()

    targets = countries or list(COUNTRY_CONFIG.keys())
    print(f"\nHistorical scraper — {len(targets)} countries")
    print(f"Target: {SNAPSHOTS_PER_COUNTRY} snapshots each, 2018–2024\n")

    total_inserted = 0

    for country in targets:
        cfg = COUNTRY_CONFIG[country]
        print(f"\n{'='*55}")
        print(f"  {country} — pattern: {cfg['pattern']}")
        print(f"{'='*55}")

        # Check if already completed
        country_progress = progress.get(country, {})
        if country_progress.get('status') == 'complete':
            print(f"  ↩  Already completed in a previous run — skipping")
            continue

        # Get snapshots list
        done_urls = set(country_progress.get('done_urls', []))
        snapshots = country_progress.get('snapshots')

        if not snapshots:
            print(f"  Querying CDX API …")
            time.sleep(CDX_DELAY)
            snapshots = get_cdx_snapshots(cfg['pattern'])
            print(f"  Found {len(snapshots)} snapshots")
            progress[country] = {
                'snapshots': snapshots,
                'done_urls': list(done_urls),
                'status': 'in_progress',
            }
            save_progress(progress)

        country_inserted = 0

        for i, snap in enumerate(snapshots):
            ts, orig_url = snap['timestamp'], snap['url']
            wayback_url = f'{WBM_BASE}/{ts}/{orig_url}'

            if orig_url in done_urls:
                print(f"  ↩  [{i+1}/{len(snapshots)}] already done")
                continue

            if already_have_url(conn, wayback_url):
                done_urls.add(orig_url)
                continue

            print(f"  [{i+1}/{len(snapshots)}] {orig_url[:60]} @ {ts[:8]} … ", end='', flush=True)
            time.sleep(FETCH_DELAY)

            html = fetch_snapshot(ts, orig_url)
            if not html:
                print("skipped (empty/failed)")
                done_urls.add(orig_url)
                continue

            soup, items, name_from_ld = extract_prices(html, country, cfg)
            if not items:
                print("0 prices found")
                done_urls.add(orig_url)
                continue

            # Prefer name extracted from JSON-LD (more reliable than H1)
            restaurant_name = name_from_ld or extract_restaurant_name(soup)
            # Convert timestamp YYYYMMDDHHMMSS → YYYY-MM-DD
            try:
                collection_date = datetime.strptime(ts[:8], '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                collection_date = ts[:10]

            c = conn.cursor()
            for item_name, price in items:
                c.execute(
                    '''INSERT INTO prices
                       (restaurant_name, item_name, price, currency, country,
                        sector, source, collection_date, url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (restaurant_name, item_name, price, cfg['currency'], country,
                     'informal', 'wayback', collection_date, wayback_url)
                )
            conn.commit()
            print(f"{len(items)} items → {restaurant_name[:40]}")
            country_inserted += len(items)
            total_inserted += len(items)

            done_urls.add(orig_url)

            # Save progress after each successful fetch
            progress[country]['done_urls'] = list(done_urls)
            if len(done_urls) >= len(snapshots):
                progress[country]['status'] = 'complete'
            save_progress(progress)

        print(f"\n  {country}: {country_inserted} items inserted this run")

    conn.close()
    print(f"\n{'='*55}")
    print(f"Historical scraper done. Total inserted: {total_inserted}")
    print(f"Progress saved to {PROGRESS_FILE}")
    print(f"Run again to continue from where it left off.")


if __name__ == '__main__':
    import sys
    # Optionally pass specific country names as args
    # e.g. python3 historical_scraper.py Singapore Malaysia
    countries = sys.argv[1:] or None
    run(countries)

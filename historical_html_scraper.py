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
from hashlib import md5
from urllib.parse import unquote

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
FETCH_BACKOFF     = 30
FETCH_DELAY       = 30       # seconds between snapshot fetches
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
    # Added 2026-06-19 (Track C re-resurrect). EUR in DE locale uses comma
    # decimal and frequently writes '€' at either end of the number; BRL
    # uses 'R$' with comma decimal.
    'EUR': re.compile(r'(?:€\s?(\d+(?:[.,]\d{2})?)|(\d+(?:[.,]\d{2})?)\s?€)'),
    'BRL': re.compile(r'R\$\s?(\d+(?:[.,]\d{2})?)'),
}

# ── Generic JSON-LD price walker ─────────────────────────────────────────────

def _walk_ld(node, items, name_ctx=None):
    """Walk a JSON-LD tree collecting (name, price, currency) where MenuItem
    or Offer or Product carries a price.

    Emission requires the local node to have its OWN `name` field — see
    the 2026-06-18 fix below.
    """
    if isinstance(node, dict):
        # 2026-06-18: priceInMinorUnit (GrabFood MY / SG NEXT_DATA).
        # Key-guarded; nodes without priceInMinorUnit fall through to the
        # existing price / offers / priceSpecification logic untouched.
        # Same 0 < p < 100_000 sanity guard as the existing path (line ~120):
        # GrabFood emits priceInMinorUnit=0 for hidden / out-of-stock items
        # and the first sweep wrote 8,914 zero-priced rows that distort
        # any index aggregate. Drop them at the source.
        if 'priceInMinorUnit' in node and node.get('name'):
            try:
                p = float(node['priceInMinorUnit']) / 100.0
            except (TypeError, ValueError):
                p = None
            if p and 0 < p < 100_000:
                items.append((str(node['name'])[:120], p,
                              node.get('priceCurrency')))
            return
        local_name = node.get('name')
        nm = local_name or name_ctx
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
        # Fix 2026-06-18: emit only when this node has its OWN name field.
        # Inheriting name_ctx from a Restaurant/FoodEstablishment parent
        # and pairing it with a child Offer/priceSpecification price
        # produced the 15 wayback-menulog rows that all had restaurant
        # names as item_names paired with 4.99 / 5.00 / 10.00 / 20.00
        # values — i.e. delivery fees and min-order amounts, not menu
        # items. MenuItem nodes that carry their own `name` are
        # unaffected; anonymous Offer leaves under non-menu parents are
        # correctly dropped.
        if local_name and price_node is not None and node.get('@type') not in bad_types:
            try:
                p = float(re.sub(r'[^\d.]', '', str(price_node)))
            except Exception:
                p = None
            if p and 0 < p < 100_000:
                items.append((str(local_name)[:120], p, cur_node))
        for v in node.values():
            _walk_ld(v, items, nm)
    elif isinstance(node, list):
        for v in node:
            _walk_ld(v, items, name_ctx)


def _extract_script_content(html, opening_re):
    """Find a script tag matching ``opening_re`` and return its inner JSON
    text. Tries the canonical ``(.*?)</script>`` shape first, then falls
    back to ``[^<]+`` (until the next ``<`` character).

    Wayback-archived pages frequently truncate or omit the closing
    ``</script>`` tag, especially for very large JSON payloads (Lieferando
    Restaurant pages store ~300 KB of JSON in __NEXT_DATA__). JSON-LD /
    NEXT_DATA payloads escape ``<`` as ``\\u003c`` so [^<]+ is a safe
    terminator when the closing tag is missing.
    """
    m = opening_re.search(html)
    if not m:
        return None
    after = html[m.end():]
    # Lazy match against </script> when present
    close = re.match(r'(.*?)</script>', after, re.S | re.I)
    if close:
        return close.group(1)
    # Fallback: grab until the next raw '<'
    rest = re.match(r'([^<]+)', after, re.S)
    if rest:
        return rest.group(1)
    return None


_LD_OPENING = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>',
    re.I,
)
_NEXTDATA_OPENING = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>',
    re.I,
)


def extract_jsonld(html):
    """Return list of (name, price, currency_or_None) from all JSON-LD blocks."""
    if not html:
        return []
    out = []
    # Walk every JSON-LD opening tag; for each, extract content via the
    # script-content helper (handles archived pages with no </script>).
    for m in _LD_OPENING.finditer(html):
        after = html[m.end():]
        close = re.match(r'(.*?)</script>', after, re.S | re.I)
        block = close.group(1) if close else (
            re.match(r'([^<]+)', after, re.S).group(1)
            if re.match(r'([^<]+)', after, re.S) else None
        )
        if not block:
            continue
        try:
            obj = json.loads(block)
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
    block = _extract_script_content(html, _NEXTDATA_OPENING)
    if not block:
        return []
    try:
        obj = json.loads(block)
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


_MENULOG_ITEM_CHUNK = re.compile(r'(?=data-test-id="menu-item")')
_MENULOG_NAME = re.compile(
    r'<h\d[^>]+data-test-id="menu-item-name"[^>]*>(.*?)</h\d>',
    re.S | re.I,
)
_MENULOG_PRICE = re.compile(
    r'<p[^>]+(?:data-js-test|data-test-id)="menu-item-price"[^>]*>(.*?)</p>',
    re.S | re.I,
)


def _strip_html(s: str) -> str:
    """Drop HTML comments + tags, decode common entities, collapse whitespace."""
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = (s.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
           .replace('&apos;', "'").replace('&lt;', '<').replace('&gt;', '>')
           .replace('&nbsp;', ' '))
    return re.sub(r'\s+', ' ', s).strip()


def extract_menulog_dom(html):
    """DOM-based menulog extractor. Menulog archived pages have menu items
    in static HTML inside `<button data-test-id="menu-item">` containers
    that wrap an `<h3 data-test-id="menu-item-name">` heading and a
    `<p data-js-test="menu-item-price">` price element. The JSON-LD on
    these pages is only Restaurant metadata — see commit 7a4d34f for the
    history of why this DOM fallback is necessary.

    Returns list of (name, price, currency_or_None). Currency is left as
    None so the per-target default ('AUD' for Menulog) is filled by
    `_coerce`.
    """
    if not html or 'data-test-id="menu-item"' not in html:
        return []
    out = []
    for chunk in _MENULOG_ITEM_CHUNK.split(html)[1:]:
        body = chunk[:4000]
        n = _MENULOG_NAME.search(body)
        p = _MENULOG_PRICE.search(body)
        if not (n and p):
            continue
        name = _strip_html(n.group(1))
        price_text = _strip_html(p.group(1))
        pm = re.search(r'(\d+(?:\.\d{1,2})?)', price_text.replace(',', ''))
        if not pm or not name:
            continue
        try:
            price = float(pm.group(1))
        except ValueError:
            continue
        if 0 < price < 10_000:
            out.append((name[:120], price, None))
    # Dedup
    seen = set(); uniq = []
    for n, pr, c in out:
        k = (n.lower(), round(pr, 2))
        if k in seen:
            continue
        seen.add(k); uniq.append((n, pr, c))
    return uniq


def parse_menulog(html, currency):
    """Menulog parser. Order: DOM (consistent, 100% yield on validated
    Sydney sample) → NEXT_DATA → JSON-LD. The JSON-LD path historically
    only matched restaurant-level metadata; the NEXT_DATA path was
    inconsistent. DOM-first reflects what actually carries menu prices
    on archived Menulog pages."""
    items = extract_menulog_dom(html)
    if not items:
        items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


# ── Deliveroo UK ─────────────────────────────────────────────────────────────
# 1-page diagnostic on 2020-09-29 Wirral Papa John's: prices live inside an
# embedded JSON blob in body HTML with shape
#   {"items":[{"name":"X","raw_price":10.99,"price":"£10.99",...}]}
# No JSON-LD, no __NEXT_DATA__, no data-test-id markers.
# 245 unique items extracted from a single 389 KB sample (Menulog AU peak
# was 126); the high count partly reflects pizza-house modifier explosion
# but the typed `raw_price` is reliable.

_DELIVEROO_PAIR = re.compile(
    r'"name"\s*:\s*"((?:\\.|[^"\\]){1,80})"'   # JSON string with backslash-escapes
    r'(?:[^{}]{0,800})'                         # within the same object
    r'"raw_price"\s*:\s*(\d+(?:\.\d+)?)',
    re.S,
)


def _unescape_json_string(s: str) -> str:
    """Decode a JSON-style escaped string fragment without re-parsing the
    whole document. Handles \\uXXXX, \\&, \\", \\/, \\n, etc."""
    try:
        return json.loads(f'"{s}"')
    except Exception:
        # Fallback for malformed escapes — strip the most common ones.
        return (s.replace('\\u0026', '&').replace('\\"', '"')
                  .replace('\\/', '/').replace('\\n', ' ').replace('\\t', ' '))


def extract_deliveroo_body_json(html):
    """Pull (name, raw_price, None) pairs from Deliveroo's embedded body-HTML
    JSON. Returns dedup'd list. Currency left None so `_coerce` fills it
    from the per-target default (GBP for Deliveroo UK)."""
    if not html or '"raw_price"' not in html:
        return []
    out = []
    for m in _DELIVEROO_PAIR.finditer(html):
        name = _unescape_json_string(m.group(1)).strip()
        try:
            price = float(m.group(2))
        except ValueError:
            continue
        if name and 0 < price < 10_000:
            out.append((name[:120], price, None))
    seen = set(); uniq = []
    for n, p, c in out:
        k = (n.lower(), round(p, 2))
        if k in seen:
            continue
        seen.add(k); uniq.append((n, p, c))
    return uniq


def parse_deliveroo_uk(html, currency):
    """Deliveroo UK parser. Tries the embedded-JSON body extractor first,
    then falls back to NEXT_DATA + JSON-LD for future template changes.
    Use `raw_price` (typed float) rather than the £-string `price` to
    sidestep currency-parsing edge cases."""
    items = extract_deliveroo_body_json(html)
    if not items:
        items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_grabfood(html, currency):
    """GrabFood SG archived: NEXT_DATA + JSON-LD."""
    items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_doordash(html, currency):
    """DoorDash US archived: JSON-LD MenuItem + Offer paired nodes carry
    a typed `price` field (dollars). Structural probe 2026-06-21 confirmed
    typed-priced 3/3 with 70-182 items/snapshot. Uses the existing JSON-LD
    walker (handles offers.price → emits with the parent MenuItem `name`).
    Falls back to NEXT_DATA, which carries the same `price` key on a
    duplicate node shape; the walker dedups by (name, round(p,2), cur).

    USD sanity guard 0 < p < 200: the generic walker only filters
    0 < p < 100_000, which would let a stray `unitAmount` (cents, e.g.
    1850) slip through if a future template variant emits it under a
    named node. $200 is a reasonable ceiling for a single menu item;
    catering trays above that are rare enough that excluding them is
    a better trade than admitting cents-as-dollars noise."""
    items = extract_jsonld(html) or extract_nextdata(html)
    filtered = [(n, p, c) for n, p, c in items if 0 < p < 200]
    return _coerce(filtered, currency)


def parse_tripadvisor_mx(html, currency):
    """TripAdvisor MX restaurant pages: JSON-LD MenuItem when present.
    Most pages only have FoodEstablishment with priceRange (a tier
    marker) — we explicitly skip those via the _walk_ld @type guard."""
    return _coerce(extract_jsonld(html), currency)


def parse_lieferando(html, currency):
    """Lieferando.de (Just Eat Takeaway DE) archived menu pages.
    2026-06-17 probe + 2026-06-19 3-page sanity check: LD + ND both
    present, 14-115 EUR hits/sample, 2/3 unblocked. NEXT_DATA is the
    higher-yield path; fall back to JSON-LD."""
    items = extract_nextdata(html) or extract_jsonld(html)
    return _coerce(items, currency)


def parse_ubereats(html, currency):
    """Uber Eats per-country archived pages: JSON-LD Menu / MenuItem.
    The captcha-string detection in the 2026-06-19 sanity probe was a
    false positive — all 'captcha'/'recaptcha' matches sit OUTSIDE the
    JSON-LD blocks (Google reCAPTCHA v3 badge + boilerplate footer).
    Menu data extracts cleanly. NEXT_DATA absent in BR sample, LD is
    the only signal — same shape as parse_menupages."""
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
    # Added 2026-06-22 after structural probe (phase0_structural_probe_
    # doordash_grubhub.py): 24,568 distinct URLs, 3,083 ≥2-cap, 30,000
    # snapshots, 2019-01 → 2026-06. JSON-LD MenuItem/Offer tree shape;
    # walker price-key hits 70-630 per snapshot. Same JSON-LD path as
    # MenuPages with an extra USD-bounded sanity guard inside the parser.
    # (Grubhub US probed same day — BAILED: archived pages are SPA shells
    # with no JSON-LD, NEXT_DATA, or embedded JSON on any of 3 samples.)
    ('United States', 'chain',  'doordash-us',   'wayback-doordash',
     'doordash.com/store/*', 'USD', parse_doordash),
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
    # Added 2026-06-18 after MY Phase 0 probe: 303 ≥40KB CDX URLs over
    # 2020-2026, NEXT_DATA populated, RM prices in static HTML (probe
    # samples yielded 7-188 prices/page). Same extractor as GrabFood SG.
    ('Malaysia',      'formal', 'grabfood-my',   'wayback-grabfood',
     'food.grab.com/my/en/restaurant/*', 'MYR', parse_grabfood),
    # Added 2026-06-19 after structural probe (phase0_structural_probe_grab_
    # deliveroo.py): 10,818 distinct URLs, 1,811 ≥2-cap, 13,136 snapshots,
    # 2019-08 → 2026-05. Tree shape MenuItem:35/Offer:35/MenuSection/Menu/
    # Restaurant; priceInMinorUnit carries real VND values (e.g.
    # 'Chả bò Đà Nẵng (500g)' = 150,000 VND). Same parser as SG/MY.
    # (PH GrabFood probed same day — BAILED: Offer.price="" empty-string
    # on every node, schema tree decorative only. Not adding.)
    ('Vietnam',       'formal', 'grabfood-vn',   'wayback-grabfood',
     'food.grab.com/vn/en/restaurant/*', 'VND', parse_grabfood),
    ('Mexico',        'formal', 'tripadvisor-mx','wayback-tripadvisor',
     'tripadvisor.com.mx/Restaurant_Review*', 'MXN', parse_tripadvisor_mx),
    # Added 2026-06-18 after the SG/UK Phase 0 probe: Deliveroo UK
    # carries 245 items/page in an embedded body-HTML JSON blob
    # (different shape than Menulog's DOM markers, but tractable).
    ('United Kingdom','formal', 'deliveroo-uk',  'wayback-deliveroo',
     'deliveroo.co.uk/menu/*', 'GBP', parse_deliveroo_uk),
    # Added 2026-06-19 after structural probe + body-JSON spot-check
    # (phase0_followup_ph_ae.py): 17,134 distinct URLs, 5,704 ≥2-cap,
    # CDX truncated at 30,000 snapshots, 2018-07 → 2026-04. No JSON-LD
    # and NEXT_DATA absent on early templates, but the embedded
    # body-HTML JSON shape is identical to UK — extract_deliveroo_body_
    # _json (line 406) pulled 92 (name, raw_price) pairs from the
    # Ladurée Abu Dhabi 2021-04 sample (AED 6-449, mean 76, sensible
    # for a Dubai café). Same parser as UK.
    # (HK Deliveroo probed same day — BAILED: CDX returned zero rows for
    # deliveroo.com.hk/menu/* over the full window. Wayback never
    # indexed the menu paths; Deliveroo exited HK 2025-04. Not adding.)
    ('United Arab Emirates','formal','deliveroo-ae','wayback-deliveroo',
     'deliveroo.ae/menu/*', 'AED', parse_deliveroo_uk),
    # Added 2026-06-19 (Track C re-resurrect; original tuples lived in
    # 7a4d34f^ before the country-expansion revert). BOTH BAILED — leave
    # in TARGETS so the warning is visible to anyone re-running, but do
    # NOT sweep until DOM extractors are written.
    #
    # - Lieferando: DOM extractor required — JSON-LD has no MenuItem
    #   nodes, current parser returns 0. See probe 2026-06-19. The 168/440
    #   pages fetched on 2026-06-19 all produced 0 items because Lieferando
    #   archived pages only carry @type='Restaurant' (name/address/geo/
    #   openingHours); EUR regex hits in the page text are template
    #   fragments the JSON-LD walker can't recurse into.
    # - Uber Eats BR: 17/17 sweep iterations on 2026-06-19 produced 0
    #   items. Captcha was a false alarm (reCAPTCHA v3 badge + Google
    #   ToS boilerplate, not a gate), but the underlying JSON-LD has
    #   the same Restaurant-only shape as Lieferando — no MenuItem /
    #   Offer / hasMenu nodes. Same DOM-extractor work required.
    # - iFood RJ probed on 2026-06-19 as a BR fallback (3 random
    #   ≥2-cap samples). All 3 showed Restaurant + OpeningHours +
    #   OrderAction + Review JSON-LD with ZERO MenuItem/Offer nodes;
    #   same Restaurant-only pattern. Not adding it as a TARGETS entry.
    ('Germany',       'formal', 'lieferando',    'wayback-lieferando',
     'lieferando.de/speisekarte/*', 'EUR', parse_lieferando),
    ('Brazil',        'formal', 'ubereats-br',   'wayback-ubereats',
     'ubereats.com/br/*', 'BRL', parse_ubereats),
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
    """Extract a restaurant slug for restaurant_name col.

    Many aggregator URLs end in a generic action segment like
    `/menu`, `/reviews`, or `/info`. The slug we actually want is
    one level up, e.g.

      menulog.com.au/restaurants-1-best-thai/menu
                    ↑ restaurant slug         ↑ action segment

    Falling through to the last segment gives every row the same
    name ("menu"), which then collapses every restaurant into a
    single bucket in restaurant-median index construction. Skip
    trailing action segments; also strip the `restaurants-` /
    `restaurant-` prefix Menulog and Foodpanda use.

    URL-decoding (added 2026-06-22): DoorDash Wayback URLs include
    %22-encoded quotes from restaurant names that previously leaked
    through unchanged. Apply unquote() so the slug reads cleanly.

    Pure-price slugs (e.g. `/store/$0.99`, `/store/$0.10`) come from
    DoorDash deal/filter pages that Wayback redirect-served to real
    restaurant menus — the items + prices are real but restaurant
    identity is unrecoverable. Bucket each such URL under a stable
    hash so per-URL grouping survives the index's restaurant-median
    step without polluting the namespace with $-strings.
    """
    u = url.split('?', 1)[0].split('#', 1)[0]
    parts = [p for p in u.rstrip('/').split('/') if p]
    SKIP = {'menu', 'reviews', 'info', 'about', 'gallery'}
    while parts and parts[-1].lower() in SKIP:
        parts.pop()
    slug = parts[-1] if parts else url
    slug = unquote(slug)
    if slug.startswith('$'):
        slug = f'junkbucket-{md5(url.encode()).hexdigest()[:8]}'
    if slug.startswith('restaurants-'):
        slug = slug[len('restaurants-'):]
    elif slug.startswith('restaurant-'):
        slug = slug[len('restaurant-'):]
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

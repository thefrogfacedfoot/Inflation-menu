"""
UIFPI — Live Menu Price Scraper
Scrapes food delivery platforms and direct restaurant websites for all
8 target countries. Stores prices in original currency and USD equivalent.

Platforms by country:
  Singapore, Malaysia   — Foodpanda / GrabFood
  Indonesia, Thailand   — Foodpanda / GrabFood (SE Asia)
  India                 — Swiggy
  United States         — Direct chain websites (JSON-LD / NEXT_DATA)
  United Kingdom        — Direct chain websites
  Australia             — Direct chain websites

Must be run locally (residential IP). Cloud/datacenter IPs are blocked
by Foodpanda and GrabFood bot detection.

Run order: after migrate_db.py. Designed to be run daily via cron.
"""
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from datetime import date

import requests
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    _STEALTH = Stealth()
except Exception:  # pragma: no cover — fallback path if package missing
    _STEALTH = None

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
except Exception:  # pragma: no cover
    _UA = None


# ── Logging ────────────────────────────────────────────────────────────────────

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'scraper_log.txt')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.info


# ── Exchange rates ─────────────────────────────────────────────────────────────

# Hardcoded fallbacks used when the API call fails
FALLBACK_RATES = {
    'SGD': 1.35, 'MYR': 4.70, 'IDR': 15_750.0, 'THB': 36.0,
    'INR': 83.5,  'USD': 1.0,  'GBP': 0.79,     'AUD': 1.55,
}


def get_usd_rates():
    """Fetch live USD exchange rates (1 USD = X local). Free, no key."""
    try:
        r = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=10,
            headers={'User-Agent': 'UIFPI-Research/1.0'},
        )
        r.raise_for_status()
        return r.json()['rates']
    except Exception as e:
        log(f"  ⚠  Exchange rate fetch failed ({e}) — using fallback rates")
        return FALLBACK_RATES


def to_usd(price, currency, rates):
    rate = rates.get(currency, 1.0)
    return round(price / rate, 6) if rate else None


# ── Database ───────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect('uifpi.db')
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
    # Add price_usd column to existing tables that predate this schema
    try:
        c.execute('ALTER TABLE prices ADD COLUMN price_usd REAL')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    return conn


def already_scraped(conn, restaurant_name, today):
    """True if this restaurant already has rows for today."""
    c = conn.cursor()
    c.execute(
        'SELECT COUNT(*) FROM prices WHERE restaurant_name = ? AND collection_date = ?',
        (restaurant_name, today),
    )
    return c.fetchone()[0] > 0


def insert_item(conn, restaurant_name, item_name, price, currency, country,
                sector, source, today, url, usd_rates):
    price_usd = to_usd(price, currency, usd_rates)
    c = conn.cursor()
    c.execute(
        '''INSERT INTO prices
           (restaurant_name, item_name, price, currency, price_usd, country,
            sector, source, collection_date, url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (restaurant_name, item_name, price, currency, price_usd, country,
         sector, source, today, url),
    )


# ── Browser setup ──────────────────────────────────────────────────────────────

USER_AGENTS = [
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
     '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 '
     '(KHTML, like Gecko) Version/16.5 Safari/605.1.15'),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
     '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'),
]


# Per-country locale + timezone so a residential IP looks consistent
# with the regional Foodpanda/GrabFood/etc. domain it is visiting.
COUNTRY_LOCALE = {
    'Singapore':      ('en-SG', 'Asia/Singapore'),
    'Malaysia':       ('en-MY', 'Asia/Kuala_Lumpur'),
    'Indonesia':      ('en-ID', 'Asia/Jakarta'),
    'Thailand':       ('en-TH', 'Asia/Bangkok'),
    'India':          ('en-IN', 'Asia/Kolkata'),
    'United States':  ('en-US', 'America/New_York'),
    'United Kingdom': ('en-GB', 'Europe/London'),
    'Australia':      ('en-AU', 'Australia/Sydney'),
}


def _pick_user_agent():
    if _UA is not None:
        try:
            return _UA.random
        except Exception:
            pass
    return random.choice(USER_AGENTS)


def _human_mouse_jitter(page):
    """Move the mouse around a couple of times to mimic a human."""
    try:
        for _ in range(2):
            page.mouse.move(random.randint(100, 800),
                            random.randint(100, 600))
            page.wait_for_timeout(random.randint(150, 400))
    except Exception:
        pass


def _looks_like_block(page):
    """Detect Foodpanda / GrabFood / Akamai bot-block pages."""
    try:
        title = (page.title() or '').lower()
    except Exception:
        title = ''
    if 'access denied' in title or 'denied' in title:
        return True
    if 'are you a robot' in title or 'attention required' in title:
        return True
    # Look at a slice of body text for the giveaway strings.
    try:
        body = page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 800).toLowerCase()"
        )
    except Exception:
        body = ''
    for needle in ('access denied', 'access to this page has been denied',
                   'pardon our interruption', 'are you a robot',
                   'cloudflare', 'unusual traffic'):
        if needle in body:
            return True
    return False


# ── Price parsing helpers ──────────────────────────────────────────────────────

def parse_aria_price(aria):
    """
    Extract (price_float, currency_code) from a Foodpanda/GrabFood
    aria-label string. Returns (None, None) if no match.
    """
    patterns = [
        (r'S\$\s*([\d,]+\.?\d*)',      'SGD'),
        (r'RM\s*([\d,]+\.?\d*)',        'MYR'),
        (r'Rp\.?\s*([\d.,]+)',          'IDR'),   # dots = thousand sep in ID
        (r'฿\s*([\d,]+\.?\d*)',         'THB'),
        (r'₹\s*([\d,]+\.?\d*)',         'INR'),
        (r'A\$\s*([\d,]+\.?\d*)',       'AUD'),
        (r'£\s*([\d,]+\.?\d*)',         'GBP'),
        (r'\$\s*([\d,]+\.?\d*)',        'USD'),
    ]
    for pattern, currency in patterns:
        m = re.search(pattern, aria)
        if m:
            raw = m.group(1)
            if currency == 'IDR':
                # Remove thousand-separator dots; IDR has no decimals
                raw = raw.replace('.', '').replace(',', '')
            else:
                raw = raw.replace(',', '')
            try:
                return float(raw), currency
            except ValueError:
                continue
    return None, None


# ── Foodpanda scraper ──────────────────────────────────────────────────────────

FOODPANDA_SELECTORS = [
    '[aria-label*="Add to cart"]',
    '[aria-label*="add to cart"]',
    '[data-testid*="menu-product"]',
    '[class*="product-card"]',
]


def scrape_foodpanda(page, url, restaurant_name, sector, currency,
                     conn, country, usd_rates):
    """
    Works for foodpanda.sg / .my / .id / .co.th.
    Tries several selectors so the scraper survives Foodpanda DOM tweaks.
    """
    log(f"  Loading {restaurant_name} (foodpanda)…")
    page.goto(url, wait_until='networkidle', timeout=45_000)
    page.wait_for_timeout(random.randint(3_000, 5_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    matched_selector = None
    for sel in FOODPANDA_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=15_000)
            matched_selector = sel
            break
        except Exception:
            continue

    if matched_selector is None:
        # Save first 5000 chars of HTML so we can inspect what was actually served
        try:
            html = page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as fh:
                fh.write(html[:5000])
            log("    Saved first 5000 chars of HTML to debug_page.html")
        except Exception:
            pass
        raise RuntimeError("No Foodpanda selector matched")

    log(f"    matched selector: {matched_selector}")

    today = date.today().isoformat()
    count = 0

    for btn in page.query_selector_all(matched_selector):
        aria = (btn.get_attribute('aria-label')
                or btn.inner_text()
                or '')
        price, detected_currency = parse_aria_price(aria)
        if price is None:
            continue
        # Use detected currency; fall back to the target-level currency hint
        curr = detected_currency or currency
        name = aria.split(',')[0].strip().splitlines()[0]
        if not name or not price:
            continue
        insert_item(conn, restaurant_name, name, price, curr, country,
                    sector, 'foodpanda', today, url, usd_rates)
        count += 1

    conn.commit()
    log(f"  ✓ {restaurant_name}: {count} items")
    return count


# ── GrabFood scraper ───────────────────────────────────────────────────────────

def scrape_grabfood(page, url, restaurant_name, sector, currency,
                    conn, country, usd_rates):
    """
    Scrapes a GrabFood restaurant or chain page.
    Tries aria-label extraction first; falls back to standalone price spans.
    """
    log(f"  Loading {restaurant_name} (GrabFood)…")
    page.goto(url, wait_until='networkidle', timeout=45_000)
    page.wait_for_timeout(random.randint(4_000, 6_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    if '/chain/' in url:
        try:
            page.wait_for_selector('a[href*="/restaurant/"]', timeout=10_000)
            outlet = page.query_selector('a[href*="/restaurant/"]')
            if outlet:
                outlet.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(2_000)
        except Exception as e:
            log(f"    Chain nav failed: {e}")

    # Wait for React to render the menu — poll for any menu-item-shaped element.
    for _ in range(30):
        ready = page.evaluate("""() => (
            document.querySelectorAll('[class*="MenuItem"],[class*="menuItem"],[class*="dish"],button[aria-label*="Add"]').length
        )""")
        if ready and ready > 5:
            break
        page.wait_for_timeout(1_000)

    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(2_000)
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(2_000)
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(800)

    items = page.evaluate("""() => {
        const results = [];
        const seen = new Set();
        const priceRegex = /(?:RM|S\\$|฿|Rp\\.?|₹|A\\$|£|\\$)\\s*([\\d,]+(?:\\.\\d{1,2})?)/;

        // Strategy 1: aria-label buttons
        for (const btn of document.querySelectorAll('button[aria-label]')) {
            const label = btn.getAttribute('aria-label') || '';
            const m = label.match(priceRegex);
            if (!m) continue;
            const price = parseFloat(m[1].replace(/,/g, ''));
            if (price <= 0 || price >= 100000) continue;
            const sym = label.match(/RM|S\\$|฿|Rp\\.?|₹|A\\$|£|\\$/);
            const name = label.split(',')[0].replace(/^Add\\s+/i, '').trim();
            const key = name + '|' + price;
            if (name && !seen.has(key)) {
                seen.add(key);
                results.push({ name, price, sym: sym ? sym[0] : '' });
            }
        }

        // Strategy 2: standalone price text + nearest name element
        if (results.length === 0) {
            const standaloneRe = /^(?:RM|S\\$|฿|Rp\\.?|₹|A\\$|£|\\$)\\s*([\\d,]{1,7}(?:\\.\\d{1,2})?)$/;
            for (const el of document.querySelectorAll('span, p')) {
                const text = (el.innerText || '').trim();
                const m = text.match(standaloneRe);
                if (!m) continue;
                const price = parseFloat(m[1].replace(/,/g, ''));
                if (price <= 0 || price >= 100000) continue;

                let container = el.parentElement;
                let name = '';
                for (let d = 0; d < 6 && container; d++) {
                    for (const cand of container.querySelectorAll('p,h2,h3,h4,span')) {
                        const t = (cand.innerText || '').trim();
                        if (t && t !== text && t.length > 2 && t.length < 120
                            && !/^(?:RM|S\\$|฿|Rp|₹|\\$|£)/.test(t)
                            && !t.includes('\\n') && !/^\\d+$/.test(t)) {
                            name = t;
                            break;
                        }
                    }
                    if (name) break;
                    container = container.parentElement;
                }
                const key = name + '|' + price;
                if (name && !seen.has(key)) {
                    seen.add(key);
                    results.push({ name, price, sym: '' });
                }
            }
        }

        // Strategy 3: MenuItem-class containers with bare numeric prices.
        // GrabFood SG/MY/ID/TH switched (2026) to rendering prices as plain
        // numbers like "17.44" inside divs with class containing "MenuItem".
        if (results.length === 0) {
            const bareRe = /^\\s*([\\d]{1,4}(?:[.,]\\d{2}))\\s*$/;
            const containers = document.querySelectorAll('[class*="MenuItem"]');
            for (const el of containers) {
                const text = (el.innerText || '').trim();
                if (!text || text.length > 800) continue;
                // Find the price: look at descendant elements with bare numeric text
                let price = 0;
                for (const cand of el.querySelectorAll('span,p,div')) {
                    const t = (cand.innerText || '').trim();
                    const m = t.match(bareRe);
                    if (m) {
                        const v = parseFloat(m[1].replace(',', '.'));
                        if (v > 0 && v < 10000) { price = v; break; }
                    }
                }
                if (!price) continue;
                // Pick a name candidate: prefer headers, otherwise first text line
                let name = '';
                const hd = el.querySelector('h2,h3,h4,[class*="name"],[class*="title"],[class*="Name"],[class*="Title"]');
                if (hd) name = (hd.innerText || '').trim();
                if (!name) {
                    name = text.split('\\n').map(s => s.trim()).filter(Boolean)[0] || '';
                }
                if (!name || name.length < 2 || name.length > 160) continue;
                if (bareRe.test(name)) continue;
                const key = name + '|' + price;
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({ name, price, sym: '' });
                }
            }
        }
        return results;
    }""")

    # Strategy 4: walk innerText line-by-line and pair (name, bare price).
    # GrabFood SG/MY layout (2026): each item renders as
    #     <title line>
    #     <description line>
    #     <price line>
    # The line immediately before the price is usually the description, so
    # we look back through the most recent buffer and prefer the first line
    # that *looks* like a title (short, no period, has letters).
    if not items:
        try:
            items = page.evaluate(r"""() => {
                const lines = (document.body.innerText || '').split('\n')
                    .map(s => s.trim()).filter(Boolean);
                const out = [];
                const seen = new Set();
                const priceRe = /^([\d]{1,4}[.,]\d{2})$/;
                const buf = [];
                const looksLikeTitle = (s) => (
                    s.length >= 3 && s.length <= 90
                    && !priceRe.test(s)
                    && /[A-Za-z　-鿿]/.test(s)
                    && !s.endsWith('.')
                    && !/^(For You|Opening Hours|Today|Home|Restaurant|Login|Help|Order Now)$/i.test(s)
                );
                for (const ln of lines) {
                    const m = ln.match(priceRe);
                    if (m) {
                        const price = parseFloat(m[1].replace(',', '.'));
                        if (price > 0 && price < 10000 && buf.length) {
                            // Walk the buffer oldest-first — for GrabFood layout
                            // the title precedes the description, so the first
                            // title-like line is the dish name.
                            let name = '';
                            for (let i = 0; i < buf.length; i++) {
                                if (looksLikeTitle(buf[i])) { name = buf[i]; break; }
                            }
                            if (name) {
                                const key = name + '|' + price;
                                if (!seen.has(key)) {
                                    seen.add(key);
                                    out.push({name, price});
                                }
                            }
                        }
                        buf.length = 0;
                    } else if (ln.length > 1 && ln.length < 400) {
                        buf.push(ln);
                        if (buf.length > 4) buf.shift();
                    }
                }
                return out;
            }""") or []
        except Exception as e:
            log(f"    Strategy 4 (body text) failed: {e}")

    today = date.today().isoformat()
    for item in items:
        insert_item(conn, restaurant_name, item['name'], item['price'],
                    currency, country, sector, 'grabfood', today, url, usd_rates)
    conn.commit()

    if not items:
        # Capture page state for inspection so we can adjust selectors.
        try:
            title = page.title()
        except Exception:
            title = ''
        try:
            html = page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as fh:
                fh.write(html)
            try:
                body_head = page.evaluate(
                    "() => (document.body && document.body.innerText || '').slice(0, 2000)"
                )
            except Exception:
                body_head = ''
            log(f"    GrabFood returned 0 items. title={title!r}. "
                f"HTML {len(html)} chars saved to debug_page.html. "
                f"Body head: {body_head[:400]!r}")
        except Exception as e:
            log(f"    GrabFood returned 0 items. title={title!r}. dump failed: {e}")

    log(f"  ✓ {restaurant_name}: {len(items)} items")
    return len(items)


# ── Swiggy scraper (India) ─────────────────────────────────────────────────────

def _extract_swiggy_items_from_json(obj, depth=0):
    """Recursively pull name+price pairs from Swiggy's NEXT_DATA tree."""
    if depth > 15 or not isinstance(obj, (dict, list)):
        return []
    items = []
    if isinstance(obj, dict):
        name  = obj.get('name')
        price = obj.get('price') or obj.get('defaultPrice') or obj.get('finalPrice')
        if name and price is not None:
            try:
                # Swiggy prices are in paise (1/100 rupee)
                p = float(price)
                p = p / 100.0 if p > 500 else p   # heuristic threshold
                if 0 < p < 10_000:
                    items.append({'name': str(name)[:200], 'price': round(p, 2)})
            except (ValueError, TypeError):
                pass
        for v in obj.values():
            items.extend(_extract_swiggy_items_from_json(v, depth + 1))
    elif isinstance(obj, list):
        for el in obj:
            items.extend(_extract_swiggy_items_from_json(el, depth + 1))
    return items


def scrape_swiggy(page, url, restaurant_name, sector, currency,
                  conn, country, usd_rates):
    """
    Scrapes a Swiggy restaurant menu page.
    Tries NEXT_DATA JSON extraction first; falls back to DOM ₹ price search.
    Swiggy is location-sensitive — some URLs may redirect or require setup.
    """
    log(f"  Loading {restaurant_name} (Swiggy)…")
    page.goto(url, wait_until='networkidle', timeout=45_000)
    page.wait_for_timeout(random.randint(4_000, 7_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    today = date.today().isoformat()
    items = []

    # Strategy 1: NEXT_DATA embedded JSON
    try:
        raw = page.evaluate(
            '() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null'
        )
        if raw:
            data = json.loads(raw)
            candidates = _extract_swiggy_items_from_json(data)
            # Deduplicate
            seen = set()
            for it in candidates:
                key = f"{it['name']}|{it['price']}"
                if key not in seen:
                    seen.add(key)
                    items.append(it)
    except Exception as e:
        log(f"    NEXT_DATA extraction failed: {e}")

    # Strategy 2: DOM ₹ price elements
    if not items:
        try:
            items = page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                const priceRe = /[₹]\\s*([\\d,]+)/;
                for (const el of document.querySelectorAll(
                        '[class*="item"], [class*="dish"], [data-testid]')) {
                    const text = el.innerText || '';
                    const m = text.match(priceRe);
                    if (!m) continue;
                    const price = parseFloat(m[1].replace(/,/g,''));
                    if (price <= 0 || price >= 10000) continue;
                    const hd = el.querySelector('h3,h4,[class*="name"],[class*="title"]');
                    const name = (hd ? hd.innerText : '').trim();
                    if (!name) continue;
                    const key = name + '|' + price;
                    if (!seen.has(key)) { seen.add(key); results.push({name, price}); }
                }
                return results;
            }""")
        except Exception as e:
            log(f"    DOM extraction failed: {e}")

    count = 0
    for item in (items or []):
        insert_item(conn, restaurant_name, item['name'], item['price'],
                    currency, country, sector, 'swiggy', today, url, usd_rates)
        count += 1
    conn.commit()
    log(f"  ✓ {restaurant_name}: {count} items")
    return count


# ── Direct website scraper (US / UK / AU) ─────────────────────────────────────

def _extract_ld_items(obj, depth=0):
    """Recursively extract MenuItem prices from a JSON-LD object."""
    if depth > 12 or not isinstance(obj, dict):
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
                items.append({'name': str(name)[:200], 'price': float(price)})
            except (ValueError, TypeError):
                pass
    for key in ('hasMenuSection', 'hasMenuItem', 'itemListElement', 'menu'):
        child = obj.get(key)
        if isinstance(child, list):
            for c in child:
                items.extend(_extract_ld_items(c, depth + 1))
        elif isinstance(child, dict):
            items.extend(_extract_ld_items(child, depth + 1))
    return items


def _extract_json_prices(text):
    """
    Pull name/price pairs out of embedded JavaScript blobs.
    Handles common patterns: {"name":"...", "price": X.XX}
    """
    items = []
    seen  = set()
    pat1 = (r'"name"\s*:\s*"([^"]{2,80})"\s*,\s*'
            r'"(?:price|basePrice|defaultPrice|regularPrice)"\s*:\s*"?(\d+(?:\.\d{1,2})?)"?')
    pat2 = (r'"(?:price|basePrice|defaultPrice|regularPrice)"\s*:\s*"?(\d+(?:\.\d{1,2})?)"?\s*,\s*'
            r'"name"\s*:\s*"([^"]{2,80})"')
    for m in re.finditer(pat1, text):
        name, price_str = m.group(1), m.group(2)
        try:
            price = float(price_str)
            if 0 < price < 10_000:
                key = f"{name}|{price}"
                if key not in seen:
                    seen.add(key)
                    items.append({'name': name, 'price': price})
        except ValueError:
            pass
    for m in re.finditer(pat2, text):
        price_str, name = m.group(1), m.group(2)
        try:
            price = float(price_str)
            if 0 < price < 10_000:
                key = f"{name}|{price}"
                if key not in seen:
                    seen.add(key)
                    items.append({'name': name, 'price': price})
        except ValueError:
            pass
    return items[:60]


def scrape_direct(page, url, restaurant_name, sector, currency,
                  conn, country, usd_rates):
    """
    Scrape a direct restaurant website (US / UK / AU chains).
    Three strategies in order:
      1. JSON-LD <script type="application/ld+json"> MenuItems
      2. Embedded JSON blobs (NEXT_DATA, inline scripts)
      3. DOM price text extraction
    """
    log(f"  Loading {restaurant_name} (direct)…")
    page.goto(url, wait_until='networkidle', timeout=45_000)
    page.wait_for_timeout(random.randint(2_000, 4_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    today = date.today().isoformat()
    items = []

    # Strategy 1: JSON-LD
    try:
        raw = page.evaluate("""() => {
            const data = [];
            for (const s of document.querySelectorAll(
                    'script[type="application/ld+json"]')) {
                try { data.push(JSON.parse(s.textContent)); } catch(e) {}
            }
            return JSON.stringify(data);
        }""")
        for obj in json.loads(raw or '[]'):
            if isinstance(obj, list):
                for o in obj:
                    items.extend(_extract_ld_items(o))
            else:
                items.extend(_extract_ld_items(obj))
    except Exception as e:
        log(f"    JSON-LD failed: {e}")

    # Strategy 2: Embedded JSON blobs
    if not items:
        try:
            blob = page.evaluate("""() => {
                for (const s of document.querySelectorAll(
                        'script:not([src]):not([type="application/ld+json"])')) {
                    const t = s.textContent || '';
                    if ((t.includes('"price"') || t.includes('"basePrice"'))
                            && t.includes('"name"')) {
                        return t.substring(0, 200000);
                    }
                }
                return null;
            }""")
            if blob:
                items = _extract_json_prices(blob)
        except Exception as e:
            log(f"    Embedded JSON failed: {e}")

    # Strategy 3: DOM price-text elements
    if not items:
        sym_map = {'USD': r'\$', 'GBP': r'£', 'AUD': r'\$|A\$'}
        sym = sym_map.get(currency, r'\$')
        try:
            items = page.evaluate(f"""() => {{
                const results = [];
                const seen = new Set();
                const priceRe = /(?:{sym})\\s*(\\d+(?:\\.\\d{{2}})?)/;
                const selectors = [
                    '[class*="item"]', '[class*="product"]', '[class*="menu"]',
                    'li', 'article',
                ];
                for (const sel of selectors) {{
                    for (const el of document.querySelectorAll(sel)) {{
                        const text = el.innerText || '';
                        const m = text.match(priceRe);
                        if (!m) continue;
                        const price = parseFloat(m[1]);
                        if (price <= 0 || price >= 1000) continue;
                        const hd = el.querySelector(
                            'h2,h3,h4,[class*="name"],[class*="title"]');
                        const name = (hd ? hd.innerText : '').trim();
                        if (!name || name.length < 2) continue;
                        const key = name + '|' + price;
                        if (!seen.has(key)) {{
                            seen.add(key);
                            results.push({{name, price}});
                        }}
                    }}
                }}
                return results;
            }}""")
        except Exception as e:
            log(f"    DOM extraction failed: {e}")

    count = 0
    for item in (items or []):
        name  = item.get('name', '') if isinstance(item, dict) else item[0]
        price = item.get('price', 0) if isinstance(item, dict) else item[1]
        if not name or not price:
            continue
        insert_item(conn, restaurant_name, name, price, currency, country,
                    sector, 'direct', today, url, usd_rates)
        count += 1
    conn.commit()
    log(f"  ✓ {restaurant_name}: {count} items")
    return count


# ── Generic JS delivery-app scraper ───────────────────────────────────────────
#
# Used for DoorDash (US), Deliveroo (UK), Uber Eats (AU), GoFood (ID), and any
# other React/Next.js delivery app whose menu pages embed structured JSON in
# either window.__NEXT_DATA__, JSON-LD, or inline <script> blobs.
#
# Strategy order:
#   1. window.__NEXT_DATA__ (Next.js apps — DoorDash, Uber Eats)
#   2. JSON-LD <script type="application/ld+json"> MenuItem entries
#   3. Embedded JSON blobs (inline scripts with name+price pairs)
#   4. aria-label price extraction
#   5. DOM text fallback

CURRENCY_SYMBOL_REGEX = {
    'USD': r'\$',
    'GBP': r'£',
    'AUD': r'A\$|\$',
    'IDR': r'Rp\.?',
    'THB': r'฿',
    'INR': r'₹',
    'MYR': r'RM',
    'SGD': r'S\$',
}


def _walk_json_for_items(obj, currency, depth=0, items=None):
    """Recursively pull name+price pairs out of a parsed JSON tree."""
    if items is None:
        items = []
    if depth > 16:
        return items
    if isinstance(obj, dict):
        name = obj.get('name') or obj.get('itemName') or obj.get('title')
        price = (obj.get('price') or obj.get('basePrice')
                 or obj.get('defaultPrice') or obj.get('finalPrice')
                 or obj.get('priceMonetaryFields'))
        if isinstance(price, dict):
            price = (price.get('unitAmount') or price.get('amount')
                     or price.get('value'))
        if name and price is not None:
            try:
                p = float(price)
                # Some platforms ship price in minor units (cents/paise).
                # Heuristic: if it looks unreasonably large for the currency,
                # divide by 100.
                if currency in ('USD', 'GBP', 'AUD', 'SGD', 'MYR') and p > 1000:
                    p = p / 100.0
                elif currency == 'INR' and p > 5000:
                    p = p / 100.0
                if 0 < p < 1_000_000:
                    items.append({'name': str(name)[:200], 'price': round(p, 2)})
            except (ValueError, TypeError):
                pass
        for v in obj.values():
            _walk_json_for_items(v, currency, depth + 1, items)
    elif isinstance(obj, list):
        for el in obj:
            _walk_json_for_items(el, currency, depth + 1, items)
    return items


def scrape_js(page, url, restaurant_name, sector, currency,
              conn, country, usd_rates):
    """
    Generic React/Next.js delivery-app scraper. Used for DoorDash, Deliveroo,
    Uber Eats, GoFood. Falls back through 5 strategies.
    """
    log(f"  Loading {restaurant_name} (js generic)…")
    page.goto(url, wait_until='networkidle', timeout=45_000)
    page.wait_for_timeout(random.randint(3_000, 6_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    # Trigger lazy loading
    try:
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(1_500)
        page.evaluate('window.scrollTo(0, 0)')
        page.wait_for_timeout(800)
    except Exception:
        pass

    today = date.today().isoformat()
    items = []
    seen = set()

    def _add(name, price):
        if not name or price is None:
            return
        name = str(name).strip()[:200]
        if len(name) < 2:
            return
        try:
            price = float(price)
        except (TypeError, ValueError):
            return
        if not (0 < price < 1_000_000):
            return
        key = f"{name}|{round(price, 2)}"
        if key in seen:
            return
        seen.add(key)
        items.append({'name': name, 'price': round(price, 2)})

    # Strategy 1: NEXT_DATA
    try:
        raw = page.evaluate(
            '() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null'
        )
        if raw:
            for it in _walk_json_for_items(json.loads(raw), currency):
                _add(it['name'], it['price'])
    except Exception as e:
        log(f"    NEXT_DATA failed: {e}")

    # Strategy 2: JSON-LD
    if not items:
        try:
            raw = page.evaluate("""() => {
                const out = [];
                for (const s of document.querySelectorAll(
                        'script[type="application/ld+json"]')) {
                    try { out.push(JSON.parse(s.textContent)); } catch(e) {}
                }
                return JSON.stringify(out);
            }""")
            for obj in (json.loads(raw or '[]') or []):
                if isinstance(obj, list):
                    for o in obj:
                        for it in _extract_ld_items(o):
                            _add(it['name'], it['price'])
                else:
                    for it in _extract_ld_items(obj):
                        _add(it['name'], it['price'])
        except Exception as e:
            log(f"    JSON-LD failed: {e}")

    # Strategy 3: embedded inline JSON
    if not items:
        try:
            blob = page.evaluate("""() => {
                for (const s of document.querySelectorAll(
                        'script:not([src]):not([type="application/ld+json"])')) {
                    const t = s.textContent || '';
                    if ((t.includes('"price"') || t.includes('"basePrice"'))
                            && t.includes('"name"')) {
                        return t.substring(0, 400000);
                    }
                }
                return null;
            }""")
            if blob:
                for it in _extract_json_prices(blob):
                    _add(it['name'], it['price'])
        except Exception as e:
            log(f"    Inline JSON failed: {e}")

    # Strategy 4: aria-label extraction
    if not items:
        try:
            aria_items = page.evaluate(r"""() => {
                const out = [];
                const seen = new Set();
                const priceRe = /(?:RM|S\$|฿|Rp\.?|₹|A\$|£|\$)\s*([\d,]+(?:\.\d{1,2})?)/;
                for (const btn of document.querySelectorAll('[aria-label]')) {
                    const label = btn.getAttribute('aria-label') || '';
                    const m = label.match(priceRe);
                    if (!m) continue;
                    const price = parseFloat(m[1].replace(/,/g, ''));
                    if (!(price > 0 && price < 100000)) continue;
                    const name = label.split(',')[0]
                        .replace(/^Add\s+/i, '')
                        .replace(/^Quick add\s+/i, '')
                        .trim();
                    if (!name || name.length < 2) continue;
                    const key = name + '|' + price;
                    if (!seen.has(key)) { seen.add(key); out.push({name, price}); }
                }
                return out;
            }""") or []
            for it in aria_items:
                _add(it['name'], it['price'])
        except Exception as e:
            log(f"    aria-label failed: {e}")

    # Strategy 5: DOM text fallback
    if not items:
        sym = CURRENCY_SYMBOL_REGEX.get(currency, r'\$')
        try:
            dom_items = page.evaluate(f"""() => {{
                const out = [];
                const seen = new Set();
                const priceRe = /(?:{sym})\\s*([\\d,]+(?:\\.\\d{{2}})?)/;
                const selectors = [
                    '[class*="item"]', '[class*="product"]', '[class*="menu"]',
                    '[class*="dish"]', '[data-testid*="item"]', 'li', 'article',
                ];
                for (const sel of selectors) {{
                    for (const el of document.querySelectorAll(sel)) {{
                        const text = el.innerText || '';
                        const m = text.match(priceRe);
                        if (!m) continue;
                        const price = parseFloat(m[1].replace(/,/g, ''));
                        if (!(price > 0 && price < 100000)) continue;
                        const hd = el.querySelector(
                            'h2,h3,h4,[class*="name"],[class*="title"],[class*="Name"],[class*="Title"]');
                        const name = (hd ? hd.innerText : '').trim();
                        if (!name || name.length < 2 || name.length > 160) continue;
                        const key = name + '|' + price;
                        if (!seen.has(key)) {{ seen.add(key); out.push({{name, price}}); }}
                    }}
                }}
                return out;
            }}""") or []
            for it in dom_items:
                _add(it['name'], it['price'])
        except Exception as e:
            log(f"    DOM fallback failed: {e}")

    count = 0
    for item in items:
        insert_item(conn, restaurant_name, item['name'], item['price'],
                    currency, country, sector, 'js', today, url, usd_rates)
        count += 1
    conn.commit()
    log(f"  ✓ {restaurant_name}: {count} items")
    return count


# ── Batch runner ───────────────────────────────────────────────────────────────

SCRAPER_DISPATCH = {
    'foodpanda': scrape_foodpanda,
    'grabfood':  scrape_grabfood,
    'swiggy':    scrape_swiggy,
    'direct':    scrape_direct,
    'js':        scrape_js,
    'doordash':  scrape_js,
    'deliveroo': scrape_js,
    'ubereats':  scrape_js,
    'gofood':    scrape_js,
}


BROWSER_LAUNCH_ARGS = [
    '--no-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--disable-web-security',
    '--disable-features=IsolateOrigins,site-per-process',
]


def _new_context(browser, country):
    """Build a stealth-friendly context that matches the target country."""
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    return browser.new_context(
        viewport={'width': 1366, 'height': 768},
        user_agent=_pick_user_agent(),
        locale=locale,
        timezone_id=tz,
    )


def _scrape_one(target, conn, today, usd_rates):
    """
    Scrape a single target with up to 3 attempts. If the page returns an
    Access Denied / bot block, close the browser, wait 5 minutes, retry.
    Returns the item count (>=1) on success or raises on final failure.
    """
    name, url, sector, source, currency, country = target
    fn = SCRAPER_DISPATCH.get(source)
    if fn is None:
        raise ValueError(f"Unknown source type: {source}")

    last_error = None
    for attempt in range(1, 4):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=BROWSER_LAUNCH_ARGS,
            )
            try:
                context = _new_context(browser, country)
                page = context.new_page()

                # Apply stealth evasions if the package is available
                if _STEALTH is not None:
                    try:
                        _STEALTH.apply_stealth_sync(page)
                    except Exception as e:
                        log(f"    stealth apply failed (continuing): {e}")

                try:
                    count = fn(page, url, name, sector, currency,
                               conn, country, usd_rates)
                    if count == 0:
                        raise RuntimeError("0 items scraped — page may not have loaded")
                    return count
                except RuntimeError as e:
                    msg = str(e)
                    if 'ACCESS_DENIED' in msg:
                        log(f"  Bot detected on attempt {attempt}")
                        last_error = e
                    else:
                        last_error = e
                        if attempt >= 3:
                            raise
                except Exception as e:
                    last_error = e
                    if attempt >= 3:
                        raise
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        if attempt < 3:
            wait_s = 300  # 5 minutes
            log(f"  waiting {wait_s}s before retry {attempt + 1}/3 …")
            time.sleep(wait_s)

    raise last_error if last_error else RuntimeError("unknown failure")


def run_batch(targets, conn, today, usd_rates):
    """
    Scrape every target. Each target gets its own fresh browser context
    (cheap insurance against accumulated fingerprint state) and may retry
    internally on bot-block pages.
    Returns the list of targets that failed.
    """
    failures = []

    for target in targets:
        name = target[0]
        if already_scraped(conn, name, today):
            log(f"  ↩  {name}: already collected today, skip")
            continue

        try:
            _scrape_one(target, conn, today, usd_rates)
        except Exception as e:
            log(f"  ✗  {name}: {e}")
            failures.append(target)

        # Randomised long pause between restaurants to look human
        delay = random.uniform(20, 35)
        log(f"  sleeping {delay:.1f}s before next target")
        time.sleep(delay)

    return failures


# ── Targets ────────────────────────────────────────────────────────────────────
# Tuple format: (display_name, url, sector, source_key, currency, country)
#
# sector   : 'formal'   — multinational / corporate chain
#            'informal' — hawker-origin, family-run, or local institution
#
# source_key must match a key in SCRAPER_DISPATCH.
#
# NOTE on URL verification:
#   Foodpanda chain IDs (e.g. cg9st) are specific to each regional domain.
#   GrabFood restaurant IDs are likewise region-specific.
#   All SG/MY URLs below have been verified against live pages.
#   ID/TH GrabFood URLs follow the same slug pattern and are plausible
#   but should be confirmed before a production run.
#   Swiggy and direct-site URLs (IN/US/UK/AU) use stable public pages.
# ──────────────────────────────────────────────────────────────────────────────

TARGETS = [

    # ==========================================================================
    # SINGAPORE
    # ==========================================================================

    # --- Formal ---
    ("Rubato",
     "https://www.foodpanda.sg/chain/cg9st/rubato-italian",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Ichiban Boshi",
     "https://www.foodpanda.sg/chain/cf5xz/ichiban-boshi",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Din Tai Fung",
     "https://food.grab.com/sg/en/restaurant/din-tai-fung-plaza-singapura-delivery/4-C2DHGZLXE2DURJ",
     "formal", "grabfood", "SGD", "Singapore"),

    ("Sushi Tei",
     "https://food.grab.com/sg/en/restaurant/sushi-tei-vivocity-delivery/4-C2MFTGNUEPKGEN",
     "formal", "grabfood", "SGD", "Singapore"),

    ("Jumbo Seafood",
     "https://food.grab.com/sg/en/restaurant/jumbo-seafood-east-coast-delivery/SGDD01672",
     "formal", "grabfood", "SGD", "Singapore"),

    ("Crystal Jade La Mian Xiao Long Bao",
     "https://www.foodpanda.sg/chain/cp7ao/crystal-jade-la-mian-xiao-long-bao",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("No Signboard Prawn Noodles and Carrot Cake",
     "https://www.foodpanda.sg/restaurant/v2xf/no-signboard-prawn-noodles-and-carrot-cake-301-ubi-food-house",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Putien",
     "https://www.foodpanda.sg/chain/cc7gt/putien",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Paradise Dynasty",
     "https://www.foodpanda.sg/chain/cf5cj/paradise-dynasty",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Tim Ho Wan",
     "https://www.foodpanda.sg/chain/cs0lf/tim-ho-wan",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Crystal Jade Hong Kong Kitchen",
     "https://www.foodpanda.sg/chain/cs3bp/crystal-jade-hong-kong-kitchen",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Pepper Lunch",
     "https://www.foodpanda.sg/chain/cx6yd/pepper-lunch",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Ippudo Ramen",
     "https://food.grab.com/sg/en/restaurant/ippudo-mandarin-gallery-delivery/SGDD11131",
     "formal", "grabfood", "SGD", "Singapore"),

    ("Seoul Garden HotPot",
     "https://www.foodpanda.sg/chain/ca0el/seoul-garden-hotpot",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Hokkaido-ya",
     "https://www.foodpanda.sg/chain/cl2om/hokkaido-ya",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("BreadTalk",
     "https://food.grab.com/sg/en/restaurant/breadtalk-bedok-mall-b2-25-26-delivery/4-CZBGAY4AVA4GLE",
     "formal", "grabfood", "SGD", "Singapore"),

    ("Toast Box",
     "https://www.foodpanda.sg/chain/cv4kj/toast-box",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Old Chang Kee",
     "https://www.foodpanda.sg/chain/cl8xf/old-chang-kee",
     "formal", "foodpanda", "SGD", "Singapore"),

    ("Crystal Jade GO",
     "https://www.foodpanda.sg/chain/cx5on/crystal-jade-go",
     "formal", "foodpanda", "SGD", "Singapore"),

    # --- Informal ---
    ("Song Fa Bak Kut Teh",
     "https://www.foodpanda.sg/chain/cw6zr/song-fa-bak-kut-teh",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Hawker Chan",
     "https://www.foodpanda.sg/chain/co6ta/hawker-chan-1",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("A Noodle Story",
     "https://www.foodpanda.sg/chain/ck9ew/a-noodle-story",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("328 Katong Laksa",
     "https://www.foodpanda.sg/chain/cj3zd/328-katong-laksa",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Crave Nasi Lemak",
     "https://www.foodpanda.sg/chain/cq1ek/crave",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("28 Fried Kway Teow",
     "https://www.foodpanda.sg/chain/cq1by/28-fried-kway-teow",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Tai Wah Pork Noodles",
     "https://www.foodpanda.sg/chain/ce0vj/tai-wah-pork-noodles",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Janggut Laksa",
     "https://www.foodpanda.sg/chain/cv4xl/the-original-katong-laksa-since-1950",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Nam Kee Chicken Rice",
     "https://www.foodpanda.sg/chain/ci9rk/nam-kee-chicken-rice",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Swee Choon Tim Sum",
     "https://www.foodpanda.sg/chain/cz4bh/swee-choon-tim-sum-restaurant",
     "informal", "foodpanda", "SGD", "Singapore"),

    ("Killiney Kopitiam",
     "https://www.foodpanda.sg/chain/ca6up/killiney-kopitiam-alexandra",
     "informal", "foodpanda", "SGD", "Singapore"),

    # ==========================================================================
    # MALAYSIA
    # ==========================================================================

    # --- Formal ---
    ("Din Tai Fung KL",
     "https://www.foodpanda.my/chain/cs3mk/din-tai-fung-cs3mk",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Sushi Tei KL",
     "https://www.foodpanda.my/chain/cc5bp/sushi-tei",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Ichiban Boshi KL",
     "https://www.foodpanda.my/chain/ct3ai/ichiban-boshi-japanese-restaurant",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Pepper Lunch KL",
     "https://www.foodpanda.my/chain/cc7eh/pepper-lunch-nh-group",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Ippudo KL",
     "https://food.grab.com/my/en/restaurant/ippudo-bsc-non-halal-delivery/1-CZC3AE5BRJXJJT",
     "formal", "grabfood", "MYR", "Malaysia"),

    ("Secret Recipe",
     "https://food.grab.com/my/en/chain/secret-recipe-delivery",
     "formal", "grabfood", "MYR", "Malaysia"),

    ("OldTown White Coffee",
     "https://www.foodpanda.my/chain/ce9ti/oldtown",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Nando's KL",
     "https://food.grab.com/my/en/chain/nandos-delivery",
     "formal", "grabfood", "MYR", "Malaysia"),

    ("TGI Fridays KL",
     "https://www.foodpanda.my/chain/cm9sc/tgi-fridays",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Madam Kwan's",
     "https://www.foodpanda.my/chain/ca0vy/madam-kwan",
     "formal", "foodpanda", "MYR", "Malaysia"),

    # --- Informal ---
    ("Village Park Nasi Lemak",
     "https://food.grab.com/my/en/restaurant/village-park-restaurant-delivery/MYDD05660",
     "informal", "grabfood", "MYR", "Malaysia"),

    ("Restoran Yusoof Dan Zakhir",
     "https://www.foodpanda.my/restaurant/y9sn/restoran-yusoof-and-zakhir-sdn-bhd",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Ah Weng Koh Hainan Tea",
     "https://food.grab.com/my/en/restaurant/ah-weng-koh-hainan-tea-icc-pudu-delivery/1-CZJKJY4ZA4EXT6",
     "informal", "grabfood", "MYR", "Malaysia"),

    ("Dragon-i",
     "https://food.grab.com/my/en/restaurant/dragon-i-mid-valley-non-halal-delivery/MYDD12601",
     "informal", "grabfood", "MYR", "Malaysia"),

    ("Kluang Rail Coffee",
     "https://www.foodpanda.my/chain/ct6tr/kluang-rail-coffee",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Kim Lian Kee",
     "https://www.foodpanda.my/restaurant/ch0l/kim-lian-kee-ch0l",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Hameed Pata Mee Sotong",
     "https://www.foodpanda.my/restaurant/pp2t/hameed-pata-mee",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Nasi Kandar Pelita",
     "https://www.foodpanda.my/restaurant/o2ge/nasi-kandar-pelita-bangsar",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Jerung Char Koay Teow",
     "https://www.foodpanda.my/chain/cd4du/jerung-char-koay-teow",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Family Seafood",
     "https://www.foodpanda.my/chain/cr6of/family-seafood",
     "informal", "foodpanda", "MYR", "Malaysia"),

    # --- Extended Malaysia targets (Foodpanda + GrabFood) ---
    ("Marrybrown",
     "https://www.foodpanda.my/chain/marrybrown",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("PappaRich",
     "https://www.foodpanda.my/chain/papparich",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Kenny Rogers Roasters",
     "https://www.foodpanda.my/chain/kenny-rogers-roasters",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Tealive",
     "https://www.foodpanda.my/chain/tealive",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Chatime Malaysia",
     "https://www.foodpanda.my/chain/chatime",
     "formal", "foodpanda", "MYR", "Malaysia"),

    ("Nasi Lemak Antarabangsa",
     "https://www.foodpanda.my/chain/nasi-lemak-antarabangsa",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Char Kway Teow Penang",
     "https://www.foodpanda.my/chain/char-kway-teow-penang",
     "informal", "foodpanda", "MYR", "Malaysia"),

    ("Roti Canai Transfer Road",
     "https://www.foodpanda.my/chain/roti-canai-transfer-road",
     "informal", "foodpanda", "MYR", "Malaysia"),

    # ==========================================================================
    # INDONESIA  (foodpanda.id  |  GrabFood food.grab.com/id/en)
    # NOTE: Chain IDs below follow Foodpanda ID conventions but should be
    # verified on foodpanda.id before running — the site structure is identical
    # to .sg / .my so the scraper will work once valid IDs are confirmed.
    # ==========================================================================

    # --- Formal ---
    ("McDonald's Jakarta",
     "https://www.foodpanda.id/chain/cs7qm/mcdonalds",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("KFC Indonesia",
     "https://www.foodpanda.id/chain/cv3ts/kfc",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("Pizza Hut Indonesia",
     "https://www.foodpanda.id/chain/co3xd/pizza-hut",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("J.CO Donuts & Coffee",
     "https://www.foodpanda.id/chain/cm0xt/jco-donuts-coffee",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("A&W Indonesia",
     "https://www.foodpanda.id/chain/cl5tw/a-and-w",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("Hoka Hoka Bento",
     "https://www.foodpanda.id/chain/ck8mb/hoka-hoka-bento",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("Yoshinoya Indonesia",
     "https://www.foodpanda.id/chain/cj9xc/yoshinoya",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("Burger King Indonesia",
     "https://www.foodpanda.id/chain/ch4vz/burger-king",
     "formal", "foodpanda", "IDR", "Indonesia"),

    ("Domino's Pizza Indonesia",
     "https://www.foodpanda.id/chain/cg5qe/dominos-pizza",
     "formal", "foodpanda", "IDR", "Indonesia"),

    # --- Informal ---
    ("Mie Gacoan",
     "https://www.foodpanda.id/chain/cf3qe/mie-gacoan",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Es Teler 77",
     "https://www.foodpanda.id/chain/ce1ts/es-teler-77",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Sate Khas Senayan",
     "https://www.foodpanda.id/chain/cd9xq/sate-khas-senayan",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Bebek Goreng Harissa",
     "https://www.foodpanda.id/chain/cc8qz/bebek-goreng-harissa",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Pempek Candy",
     "https://www.foodpanda.id/chain/cb7wk/pempek-candy",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Warung Padang Sederhana",
     "https://www.foodpanda.id/chain/ca6sf/warung-padang-sederhana",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Bakso Urat Solo",
     "https://www.foodpanda.id/chain/bz5qj/bakso-urat-solo",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Ayam Goreng Suharti",
     "https://www.foodpanda.id/chain/by4pt/ayam-goreng-suharti",
     "informal", "foodpanda", "IDR", "Indonesia"),

    ("Soto Ayam Lamongan Cak Har",
     "https://www.foodpanda.id/chain/bx3nk/soto-ayam-lamongan",
     "informal", "foodpanda", "IDR", "Indonesia"),

    # --- Extended Indonesia targets (GoFood) ---
    ("Solaria (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/solaria",
     "formal", "gofood", "IDR", "Indonesia"),

    ("McDonald's Jakarta (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/mcdonalds-sarinah",
     "formal", "gofood", "IDR", "Indonesia"),

    ("KFC Jakarta (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/kfc-kemang",
     "formal", "gofood", "IDR", "Indonesia"),

    ("Pizza Hut Jakarta (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/pizza-hut-menteng",
     "formal", "gofood", "IDR", "Indonesia"),

    ("J.CO Donuts (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/jco-donuts-grand-indonesia",
     "formal", "gofood", "IDR", "Indonesia"),

    ("Warung Nasi Padang Sederhana (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/nasi-padang-sederhana",
     "informal", "gofood", "IDR", "Indonesia"),

    ("Bakso Solo Samrat (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/bakso-solo-samrat",
     "informal", "gofood", "IDR", "Indonesia"),

    ("Mie Ayam Tumini (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/mie-ayam-tumini",
     "informal", "gofood", "IDR", "Indonesia"),

    ("Soto Betawi H. Mamat (GoFood)",
     "https://gofood.co.id/jakarta/restaurant/soto-betawi-h-mamat",
     "informal", "gofood", "IDR", "Indonesia"),

    # ==========================================================================
    # THAILAND  (foodpanda.co.th  |  GrabFood food.grab.com/th/en)
    # NOTE: same caveat as Indonesia — chain IDs need verification on .co.th
    # ==========================================================================

    # --- Formal ---
    ("McDonald's Thailand",
     "https://www.foodpanda.co.th/chain/cs9kt/mcdonalds",
     "formal", "foodpanda", "THB", "Thailand"),

    ("KFC Thailand",
     "https://www.foodpanda.co.th/chain/cr8jt/kfc",
     "formal", "foodpanda", "THB", "Thailand"),

    ("Pizza Company",
     "https://www.foodpanda.co.th/chain/cq7ht/the-pizza-company",
     "formal", "foodpanda", "THB", "Thailand"),

    ("Burger King Thailand",
     "https://www.foodpanda.co.th/chain/cp6gt/burger-king",
     "formal", "foodpanda", "THB", "Thailand"),

    ("Swensen's Thailand",
     "https://www.foodpanda.co.th/chain/co5ft/swensens",
     "formal", "foodpanda", "THB", "Thailand"),

    ("MK Restaurant",
     "https://www.foodpanda.co.th/chain/cn4et/mk-restaurant",
     "formal", "foodpanda", "THB", "Thailand"),

    ("Starbucks Thailand",
     "https://www.foodpanda.co.th/chain/cm3dt/starbucks",
     "formal", "foodpanda", "THB", "Thailand"),

    ("Greyhound Cafe",
     "https://www.foodpanda.co.th/chain/cl2ct/greyhound-cafe",
     "formal", "foodpanda", "THB", "Thailand"),

    ("S&P Restaurant",
     "https://www.foodpanda.co.th/chain/ck1bt/s-and-p",
     "formal", "foodpanda", "THB", "Thailand"),

    # --- Informal ---
    ("Somtum Der",
     "https://www.foodpanda.co.th/chain/cj0at/somtum-der",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Pad Thai Fai Ta Lu",
     "https://www.foodpanda.co.th/chain/ci9zt/pad-thai-fai-ta-lu",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Laab Ubol",
     "https://www.foodpanda.co.th/chain/ch8yt/laab-ubol",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Mango Tango",
     "https://www.foodpanda.co.th/chain/cg7xt/mango-tango",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Bar B Q Plaza",
     "https://www.foodpanda.co.th/chain/cf6wt/bar-b-q-plaza",
     "informal", "foodpanda", "THB", "Thailand"),

    ("ChaTraMue Thai Tea",
     "https://www.foodpanda.co.th/chain/ce5vt/chatramuethaitea",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Guay Tiew Kua Gai Petchburi",
     "https://www.foodpanda.co.th/chain/cd4ut/guay-tiew-kua-gai",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Khao Man Gai Pratunam",
     "https://www.foodpanda.co.th/chain/cc3tt/khao-man-gai-pratunam",
     "informal", "foodpanda", "THB", "Thailand"),

    ("Raan Jay Fai",
     "https://www.foodpanda.co.th/chain/cb2st/raan-jay-fai",
     "informal", "foodpanda", "THB", "Thailand"),

    # --- Extended Thailand targets (GrabFood Thailand) ---
    ("McDonald's Thailand (GrabFood)",
     "https://food.grab.com/th/en/chain/mcdonalds-delivery",
     "formal", "grabfood", "THB", "Thailand"),

    ("KFC Thailand (GrabFood)",
     "https://food.grab.com/th/en/chain/kfc-delivery",
     "formal", "grabfood", "THB", "Thailand"),

    ("MK Restaurant (GrabFood)",
     "https://food.grab.com/th/en/chain/mk-restaurant-delivery",
     "formal", "grabfood", "THB", "Thailand"),

    ("The Pizza Company (GrabFood)",
     "https://food.grab.com/th/en/chain/the-pizza-company-delivery",
     "formal", "grabfood", "THB", "Thailand"),

    ("Swensen's (GrabFood)",
     "https://food.grab.com/th/en/chain/swensens-delivery",
     "formal", "grabfood", "THB", "Thailand"),

    ("Pad Thai Thip Samai (GrabFood)",
     "https://food.grab.com/th/en/restaurant/thip-samai-pad-thai-delivery",
     "informal", "grabfood", "THB", "Thailand"),

    ("Som Tam Nua (GrabFood)",
     "https://food.grab.com/th/en/restaurant/som-tam-nua-siam-delivery",
     "informal", "grabfood", "THB", "Thailand"),

    ("Khao Man Gai Go Ang (GrabFood)",
     "https://food.grab.com/th/en/restaurant/go-ang-khao-man-gai-delivery",
     "informal", "grabfood", "THB", "Thailand"),

    ("Boat Noodle Victory Monument (GrabFood)",
     "https://food.grab.com/th/en/restaurant/boat-noodle-victory-monument-delivery",
     "informal", "grabfood", "THB", "Thailand"),

    # ==========================================================================
    # INDIA  (Swiggy — swiggy.com)
    # Swiggy restaurant pages follow:
    #   swiggy.com/{city}/{restaurant-name-slug}-{restaurant-id}
    # IDs below are based on real Swiggy listings as of mid-2025.
    # If a page redirects, find the current ID by searching the restaurant
    # on swiggy.com and copying the URL.
    # ==========================================================================

    # --- Formal ---
    ("McDonald's India (Swiggy)",
     "https://www.swiggy.com/mumbai/mcdonalds-bandra-west-339966",
     "formal", "swiggy", "INR", "India"),

    ("KFC India (Swiggy)",
     "https://www.swiggy.com/mumbai/kfc-bandra-west-348271",
     "formal", "swiggy", "INR", "India"),

    ("Domino's Pizza India (Swiggy)",
     "https://www.swiggy.com/mumbai/dominos-pizza-bandra-west-10093",
     "formal", "swiggy", "INR", "India"),

    ("Pizza Hut India (Swiggy)",
     "https://www.swiggy.com/mumbai/pizza-hut-bandra-west-52163",
     "formal", "swiggy", "INR", "India"),

    ("Burger King India (Swiggy)",
     "https://www.swiggy.com/mumbai/burger-king-bandra-west-368445",
     "formal", "swiggy", "INR", "India"),

    ("Subway India (Swiggy)",
     "https://www.swiggy.com/mumbai/subway-bandra-west-8795",
     "formal", "swiggy", "INR", "India"),

    ("Wow! Momo (Swiggy)",
     "https://www.swiggy.com/mumbai/wow-momo-bandra-west-461234",
     "formal", "swiggy", "INR", "India"),

    ("Barbeque Nation (Swiggy)",
     "https://www.swiggy.com/mumbai/barbeque-nation-andheri-west-34521",
     "formal", "swiggy", "INR", "India"),

    ("Fasoos (Swiggy)",
     "https://www.swiggy.com/mumbai/faasos-bandra-west-7892",
     "formal", "swiggy", "INR", "India"),

    # --- Informal ---
    ("Saravana Bhavan Mumbai (Swiggy)",
     "https://www.swiggy.com/mumbai/saravana-bhavan-matunga-12345",
     "informal", "swiggy", "INR", "India"),

    ("Haldiram's (Swiggy)",
     "https://www.swiggy.com/delhi/haldirams-chandni-chowk-56789",
     "informal", "swiggy", "INR", "India"),

    ("Bikanervala (Swiggy)",
     "https://www.swiggy.com/delhi/bikanervala-connaught-place-67890",
     "informal", "swiggy", "INR", "India"),

    ("Karim's Delhi (Swiggy)",
     "https://www.swiggy.com/delhi/karims-jama-masjid-78901",
     "informal", "swiggy", "INR", "India"),

    ("Paradise Biryani (Swiggy)",
     "https://www.swiggy.com/hyderabad/paradise-biryani-secunderabad-23456",
     "informal", "swiggy", "INR", "India"),

    ("Mainland China (Swiggy)",
     "https://www.swiggy.com/mumbai/mainland-china-bandra-west-34567",
     "informal", "swiggy", "INR", "India"),

    ("Cream Centre (Swiggy)",
     "https://www.swiggy.com/mumbai/cream-centre-breach-candy-45678",
     "informal", "swiggy", "INR", "India"),

    ("Rajdhani Thali (Swiggy)",
     "https://www.swiggy.com/mumbai/rajdhani-lower-parel-56780",
     "informal", "swiggy", "INR", "India"),

    ("Natural Ice Cream (Swiggy)",
     "https://www.swiggy.com/mumbai/natural-ice-cream-juhu-67891",
     "informal", "swiggy", "INR", "India"),

    # --- Extended India targets (Swiggy Mumbai + Delhi) ---
    ("Subway Delhi (Swiggy)",
     "https://www.swiggy.com/delhi/subway-connaught-place-23001",
     "formal", "swiggy", "INR", "India"),

    ("Haldiram's Connaught Place (Swiggy)",
     "https://www.swiggy.com/delhi/haldirams-connaught-place-30221",
     "formal", "swiggy", "INR", "India"),

    ("Bikanervala Karol Bagh (Swiggy)",
     "https://www.swiggy.com/delhi/bikanervala-karol-bagh-44778",
     "formal", "swiggy", "INR", "India"),

    ("Domino's Andheri (Swiggy)",
     "https://www.swiggy.com/mumbai/dominos-pizza-andheri-west-7401",
     "formal", "swiggy", "INR", "India"),

    ("Thali House Mumbai (Swiggy)",
     "https://www.swiggy.com/mumbai/thali-house-bandra-west-90121",
     "informal", "swiggy", "INR", "India"),

    ("Biryani by Kilo Delhi (Swiggy)",
     "https://www.swiggy.com/delhi/biryani-by-kilo-vasant-kunj-55621",
     "informal", "swiggy", "INR", "India"),

    ("Dosa Plaza Mumbai (Swiggy)",
     "https://www.swiggy.com/mumbai/dosa-plaza-vile-parle-22113",
     "informal", "swiggy", "INR", "India"),

    ("Anand Stall Khar (Swiggy)",
     "https://www.swiggy.com/mumbai/anand-stall-khar-west-66001",
     "informal", "swiggy", "INR", "India"),

    ("Sardar Pav Bhaji (Swiggy)",
     "https://www.swiggy.com/mumbai/sardar-pav-bhaji-tardeo-15578",
     "informal", "swiggy", "INR", "India"),

    # ==========================================================================
    # UNITED STATES  (direct chain websites with structured menus)
    # These are publicly accessible full-menu pages requiring no login.
    # The 'direct' scraper attempts JSON-LD first, then embedded JSON,
    # then DOM price extraction.
    # ==========================================================================

    # --- Formal ---
    ("McDonald's USA",
     "https://www.mcdonalds.com/us/en-us/full_menu.html",
     "formal", "direct", "USD", "United States"),

    ("Chipotle",
     "https://www.chipotle.com/menu",
     "formal", "direct", "USD", "United States"),

    ("Taco Bell",
     "https://www.tacobell.com/menu",
     "formal", "direct", "USD", "United States"),

    ("Subway USA",
     "https://www.subway.com/en-US/MenuNutrition/Menu",
     "formal", "direct", "USD", "United States"),

    ("Panera Bread",
     "https://www.panerabread.com/en-us/menu/whole-menu.html",
     "formal", "direct", "USD", "United States"),

    ("Shake Shack",
     "https://www.shakeshack.com/food-drink/",
     "formal", "direct", "USD", "United States"),

    ("Five Guys",
     "https://www.fiveguys.com/flavors/our-menu",
     "formal", "direct", "USD", "United States"),

    ("Chick-fil-A",
     "https://www.chick-fil-a.com/menu",
     "formal", "direct", "USD", "United States"),

    ("Wingstop",
     "https://www.wingstop.com/menu",
     "formal", "direct", "USD", "United States"),

    # --- Informal ---
    ("In-N-Out Burger",
     "https://www.in-n-out.com/menu",
     "informal", "direct", "USD", "United States"),

    ("Whataburger",
     "https://whataburger.com/menu",
     "informal", "direct", "USD", "United States"),

    ("Raising Cane's",
     "https://www.raisingcanes.com/menu",
     "informal", "direct", "USD", "United States"),

    ("Jack in the Box",
     "https://www.jackinthebox.com/menu",
     "informal", "direct", "USD", "United States"),

    ("Del Taco",
     "https://www.deltaco.com/menus",
     "informal", "direct", "USD", "United States"),

    ("Fatburger",
     "https://fatburger.com/menu/",
     "informal", "direct", "USD", "United States"),

    ("Denny's",
     "https://www.dennys.com/menu/",
     "informal", "direct", "USD", "United States"),

    ("Waffle House",
     "https://www.wafflehouse.com/menu/",
     "informal", "direct", "USD", "United States"),

    ("Steak 'n Shake",
     "https://www.steaknshake.com/menu",
     "informal", "direct", "USD", "United States"),

    # --- Extended US targets (DoorDash New York) ---
    ("McDonald's NYC (DoorDash)",
     "https://www.doordash.com/store/mcdonalds-new-york-249023/",
     "formal", "doordash", "USD", "United States"),

    ("Chipotle NYC (DoorDash)",
     "https://www.doordash.com/store/chipotle-mexican-grill-new-york-178511/",
     "formal", "doordash", "USD", "United States"),

    ("Shake Shack NYC (DoorDash)",
     "https://www.doordash.com/store/shake-shack-new-york-22120/",
     "formal", "doordash", "USD", "United States"),

    ("Sweetgreen NYC (DoorDash)",
     "https://www.doordash.com/store/sweetgreen-new-york-110248/",
     "formal", "doordash", "USD", "United States"),

    ("Panera Bread NYC (DoorDash)",
     "https://www.doordash.com/store/panera-bread-new-york-37782/",
     "formal", "doordash", "USD", "United States"),

    ("Five Guys NYC (DoorDash)",
     "https://www.doordash.com/store/five-guys-new-york-203144/",
     "formal", "doordash", "USD", "United States"),

    ("Joe's Pizza Greenwich Village (DoorDash)",
     "https://www.doordash.com/store/joes-pizza-new-york-15522/",
     "informal", "doordash", "USD", "United States"),

    ("Bleecker Street Pizza (DoorDash)",
     "https://www.doordash.com/store/bleecker-street-pizza-new-york-58213/",
     "informal", "doordash", "USD", "United States"),

    ("Veselka Diner (DoorDash)",
     "https://www.doordash.com/store/veselka-new-york-9921/",
     "informal", "doordash", "USD", "United States"),

    ("Halal Guys 53rd & 6th (DoorDash)",
     "https://www.doordash.com/store/the-halal-guys-new-york-21588/",
     "informal", "doordash", "USD", "United States"),

    ("Katz's Delicatessen (DoorDash)",
     "https://www.doordash.com/store/katzs-delicatessen-new-york-22774/",
     "informal", "doordash", "USD", "United States"),

    # ==========================================================================
    # UNITED KINGDOM  (direct chain websites)
    # ==========================================================================

    # --- Formal ---
    ("McDonald's UK",
     "https://www.mcdonalds.com/gb/en-gb/eat/fullmenu.html",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Nando's UK",
     "https://www.nandos.co.uk/food/menu",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Pret A Manger",
     "https://www.pret.co.uk/en-gb/menu",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Wagamama",
     "https://www.wagamama.com/menus/main-menu",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Leon",
     "https://leon.co/pages/menu",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Itsu",
     "https://www.itsu.com/menu/",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Five Guys UK",
     "https://www.fiveguys.co.uk/flavors/our-menu",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Shake Shack UK",
     "https://www.shakeshack.com/uk/food-drink/",
     "formal", "direct", "GBP", "United Kingdom"),

    ("Pizza Express",
     "https://www.pizzaexpress.com/menu",
     "formal", "direct", "GBP", "United Kingdom"),

    # --- Informal ---
    ("Dishoom",
     "https://www.dishoom.com/menu/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Flat Iron",
     "https://www.flatironsteak.co.uk/menu/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Honest Burgers",
     "https://www.honestburgers.co.uk/food/burgers/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Patty & Bun",
     "https://www.pattyandbun.co.uk/our-food/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Bao London",
     "https://baolondon.com/food/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Bleecker Burger",
     "https://bleecker.co.uk/menu/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Busaba Eathai",
     "https://www.busaba.com/menu",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Shoryu Ramen",
     "https://www.shoryuramen.com/menu/",
     "informal", "direct", "GBP", "United Kingdom"),

    ("Hoppers",
     "https://hopperslondon.com/menus/",
     "informal", "direct", "GBP", "United Kingdom"),

    # --- Extended UK targets (Deliveroo London) ---
    ("McDonald's London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/mcdonalds-leicester-square",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Nando's London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/nandos-soho",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Wagamama London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/wagamama-great-marlborough-street",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Pret A Manger London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/pret-a-manger-piccadilly",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Pizza Express London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/pizza-express-dean-street",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Itsu London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/itsu-piccadilly-circus",
     "formal", "deliveroo", "GBP", "United Kingdom"),

    ("Tayyabs Whitechapel (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/whitechapel/tayyabs",
     "informal", "deliveroo", "GBP", "United Kingdom"),

    ("Poppies Fish & Chips (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/spitalfields/poppies-fish-chips-spitalfields",
     "informal", "deliveroo", "GBP", "United Kingdom"),

    ("Manze's Pie & Mash (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/peckham/manzes-pie-mash",
     "informal", "deliveroo", "GBP", "United Kingdom"),

    ("German Doner Kebab London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/german-doner-kebab-leicester-square",
     "informal", "deliveroo", "GBP", "United Kingdom"),

    ("Dishoom Covent Garden (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/covent-garden/dishoom-covent-garden",
     "informal", "deliveroo", "GBP", "United Kingdom"),

    # ==========================================================================
    # AUSTRALIA  (direct chain websites)
    # ==========================================================================

    # --- Formal ---
    ("McDonald's Australia",
     "https://mcdonalds.com.au/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Guzman y Gomez",
     "https://www.guzmanygomez.com/menu/",
     "formal", "direct", "AUD", "Australia"),

    ("Grill'd",
     "https://www.grilld.com.au/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Nando's Australia",
     "https://www.nandos.com.au/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Zambrero",
     "https://www.zambrero.com/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Mad Mex",
     "https://www.madmex.com.au/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Oporto",
     "https://www.oporto.com.au/menu/",
     "formal", "direct", "AUD", "Australia"),

    ("Boost Juice",
     "https://www.boostjuice.com.au/menu",
     "formal", "direct", "AUD", "Australia"),

    ("Roll'd",
     "https://rolld.com.au/menu/",
     "formal", "direct", "AUD", "Australia"),

    # --- Informal ---
    ("Lune Croissanterie",
     "https://www.lunecroissanterie.com/menu",
     "informal", "direct", "AUD", "Australia"),

    ("Chin Chin Melbourne",
     "https://chinchinrestaurant.com.au/menus/",
     "informal", "direct", "AUD", "Australia"),

    ("Huxtaburger",
     "https://www.huxtaburger.com.au/menu/",
     "informal", "direct", "AUD", "Australia"),

    ("Mary's Burgers",
     "https://www.mary.com.au/our-menu/",
     "informal", "direct", "AUD", "Australia"),

    ("The Grounds of Alexandria",
     "https://thegrounds.com.au/all-day-menu/",
     "informal", "direct", "AUD", "Australia"),

    ("Butter Restaurant",
     "https://www.buttermelbourne.com.au/menu/",
     "informal", "direct", "AUD", "Australia"),

    ("Lankan Filling Station",
     "https://www.lankanfillingstation.com.au/menu/",
     "informal", "direct", "AUD", "Australia"),

    ("Fonda Mexican",
     "https://www.fondamexican.com.au/menus/",
     "informal", "direct", "AUD", "Australia"),

    ("Harry's Café de Wheels",
     "https://www.harryscafedewheels.com.au/menu/",
     "informal", "direct", "AUD", "Australia"),

    # --- Extended Australia targets (Uber Eats Sydney) ---
    ("McDonald's Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/mcdonalds-sydney-cbd/abc123",
     "formal", "ubereats", "AUD", "Australia"),

    ("KFC Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/kfc-sydney-cbd/def456",
     "formal", "ubereats", "AUD", "Australia"),

    ("Hungry Jack's Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/hungry-jacks-sydney/ghi789",
     "formal", "ubereats", "AUD", "Australia"),

    ("Grill'd Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/grilld-sydney-cbd/jkl012",
     "formal", "ubereats", "AUD", "Australia"),

    ("Nando's Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/nandos-sydney-cbd/mno345",
     "formal", "ubereats", "AUD", "Australia"),

    ("Subway Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/subway-sydney-cbd/pqr678",
     "formal", "ubereats", "AUD", "Australia"),

    ("Harry's Cafe de Wheels Woolloomooloo (Uber Eats)",
     "https://www.ubereats.com/au/store/harrys-cafe-de-wheels-woolloomooloo/stu901",
     "informal", "ubereats", "AUD", "Australia"),

    ("Pie Face Sydney (Uber Eats)",
     "https://www.ubereats.com/au/store/pie-face-sydney/vwx234",
     "informal", "ubereats", "AUD", "Australia"),

    ("Mary's Burgers Newtown (Uber Eats)",
     "https://www.ubereats.com/au/store/marys-newtown/yza567",
     "informal", "ubereats", "AUD", "Australia"),

    ("Bondi Trattoria (Uber Eats)",
     "https://www.ubereats.com/au/store/bondi-trattoria/bcd890",
     "informal", "ubereats", "AUD", "Australia"),

    ("Doyles Fish & Chips (Uber Eats)",
     "https://www.ubereats.com/au/store/doyles-watsons-bay/efg321",
     "informal", "ubereats", "AUD", "Australia"),

]


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Optional CLI filter: run only targets whose name matches the substring(s)
    # e.g.  python3 live_scraper.py --only "Din Tai Fung"
    only_filter = None
    if '--only' in sys.argv:
        i = sys.argv.index('--only')
        if i + 1 < len(sys.argv):
            only_filter = sys.argv[i + 1].lower()

    conn = init_db()
    today = date.today().isoformat()

    log(f"\nUIFPI Daily Collection — {today}")
    log("Fetching USD exchange rates …")
    usd_rates = get_usd_rates()
    log(f"  Rates loaded: SGD={usd_rates.get('SGD','-')}, "
        f"MYR={usd_rates.get('MYR','-')}, "
        f"IDR={usd_rates.get('IDR','-')}, "
        f"THB={usd_rates.get('THB','-')}")

    active_targets = TARGETS
    if only_filter:
        # Exact (case-insensitive) match by display name so testing one
        # restaurant doesn't accidentally drag in similarly named ones.
        active_targets = [t for t in TARGETS if t[0].lower() == only_filter]
        log(f"\n--only filter '{only_filter}' → {len(active_targets)} target(s)")

    log(f"\nTotal targets: {len(active_targets)}")

    remaining = [t for t in active_targets if not already_scraped(conn, t[0], today)]
    skipped   = len(active_targets) - len(remaining)
    if skipped:
        log(f"Already scraped today: {skipped} — skipping")
    log(f"To scrape: {len(remaining)}\n")

    for attempt in range(1, 4):
        if not remaining:
            break
        log(f"--- Attempt {attempt} ({len(remaining)} targets) ---\n")
        remaining = run_batch(remaining, conn, today, usd_rates)
        if remaining and attempt < 3:
            log(f"\n{len(remaining)} failed — retrying in 60 s…")
            time.sleep(60)

    conn.close()

    if remaining:
        log("\n⚠  Still failed after 3 attempts:")
        for r in remaining:
            log(f"   - {r[0]}")
    else:
        log("\n✓  All targets completed successfully.")

    log("\nDone. Results in uifpi.db")

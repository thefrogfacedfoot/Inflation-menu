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


# ── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Logging ────────────────────────────────────────────────────────────────────

LOG_PATH = os.path.join(BASE_DIR, 'scraper_log.txt')

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


EXCHANGE_RATE_CACHE_PATH = os.path.join(BASE_DIR, 'exchange_rates.json')
EXCHANGE_RATE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _load_cached_rates():
    """Return (rates, fetched_at_epoch) from disk, or (None, 0) if missing/invalid."""
    try:
        with open(EXCHANGE_RATE_CACHE_PATH, 'r') as fh:
            payload = json.load(fh)
        rates = payload.get('rates')
        fetched_at = float(payload.get('fetched_at', 0))
        if isinstance(rates, dict) and rates:
            return rates, fetched_at
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"  ⚠  Cached exchange rates unreadable ({e})")
    return None, 0


def _save_cached_rates(rates):
    payload = {
        'fetched_at': time.time(),
        'fetched_at_iso': date.today().isoformat(),
        'rates': rates,
    }
    try:
        with open(EXCHANGE_RATE_CACHE_PATH, 'w') as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
    except Exception as e:
        log(f"  ⚠  Could not cache exchange rates ({e})")


def get_usd_rates(force_refresh=False):
    """
    Return USD exchange rates (1 USD = X local).

    Caches results to exchange_rates.json for 24h to avoid hammering the
    free API on every run. Pass force_refresh=True to bypass the cache.
    """
    if not force_refresh:
        cached, fetched_at = _load_cached_rates()
        if cached and (time.time() - fetched_at) < EXCHANGE_RATE_TTL_SECONDS:
            age_h = (time.time() - fetched_at) / 3600
            log(f"  ✓ Using cached USD rates ({age_h:.1f}h old)")
            return cached

    try:
        r = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=10,
            headers={'User-Agent': 'UIFPI-Research/1.0'},
        )
        r.raise_for_status()
        rates = r.json()['rates']
        _save_cached_rates(rates)
        log("  ✓ Fetched fresh USD rates and cached them")
        return rates
    except Exception as e:
        log(f"  ⚠  Exchange rate fetch failed ({e})")
        # Prefer a stale cache over fallback constants if available
        cached, _ = _load_cached_rates()
        if cached:
            log("  ↩  Falling back to stale cached rates")
            return cached
        log("  ↩  Using hardcoded fallback rates")
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT,
            item_name TEXT,
            old_price REAL,
            new_price REAL,
            price_change_pct REAL,
            country TEXT,
            sector TEXT,
            change_detected_date TEXT
        )
    ''')
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_price_history_date '
        'ON price_history(change_detected_date)'
    )
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_price_history_country '
        'ON price_history(country)'
    )
    # Idempotency: detect_price_changes can be re-run on the same date
    # (manual reruns, partial scrape recovery, etc.) without inserting
    # duplicate change rows — see INSERT OR IGNORE in detect_price_changes.
    c.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_price_history_unique '
        'ON price_history(restaurant_name, item_name, change_detected_date)'
    )
    # Without this, detect_price_changes does a full table scan for every
    # item it inspects (N+1) — ~22.5K scans per daily run on current data.
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_prices_item_date '
        'ON prices(restaurant_name, item_name, collection_date)'
    )
    c.execute(
        'CREATE INDEX IF NOT EXISTS idx_prices_date '
        'ON prices(collection_date)'
    )
    conn.commit()
    # Add price_usd column to existing tables that predate this schema
    try:
        c.execute('ALTER TABLE prices ADD COLUMN price_usd REAL')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    return conn


def detect_price_changes(conn, today):
    """
    For every item collected today, compare to the most recent prior
    collection. Insert a row into price_history when the price differs.
    Returns a summary dict for the calling run.

    One windowed SQL query pairs each of today's items with its most
    recent prior price — avoids the previous N+1 per-item lookup.
    """
    c = conn.cursor()
    c.execute(
        '''
        WITH today_items AS (
            SELECT restaurant_name, item_name, price AS new_price,
                   country, sector
            FROM prices
            WHERE collection_date = ?
              AND price IS NOT NULL
        ),
        ranked_prev AS (
            SELECT restaurant_name, item_name, price AS old_price,
                   ROW_NUMBER() OVER (
                       PARTITION BY restaurant_name, item_name
                       ORDER BY collection_date DESC
                   ) AS rn
            FROM prices
            WHERE collection_date < ?
              AND price IS NOT NULL
        )
        SELECT t.restaurant_name, t.item_name,
               p.old_price, t.new_price, t.country, t.sector
        FROM today_items t
        JOIN ranked_prev p
          ON p.restaurant_name = t.restaurant_name
         AND p.item_name       = t.item_name
         AND p.rn = 1
        WHERE p.old_price > 0
          AND ABS(t.new_price - p.old_price) > 1e-6
        ''',
        (today, today),
    )
    rows = c.fetchall()

    changes = []
    history_inserts = []
    for restaurant_name, item_name, old_price, new_price, country, sector in rows:
        pct = round((new_price - old_price) / old_price * 100.0, 4)
        history_inserts.append(
            (restaurant_name, item_name, old_price, new_price,
             pct, country, sector, today)
        )
        changes.append({
            'restaurant_name': restaurant_name,
            'item_name': item_name,
            'old_price': old_price,
            'new_price': new_price,
            'pct': pct,
            'country': country,
            'sector': sector,
        })

    if history_inserts:
        c.executemany(
            '''INSERT OR IGNORE INTO price_history
               (restaurant_name, item_name, old_price, new_price,
                price_change_pct, country, sector, change_detected_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            history_inserts,
        )
    conn.commit()

    restaurants = {ch['restaurant_name'] for ch in changes}
    return {
        'changes': changes,
        'n_changes': len(changes),
        'n_restaurants': len(restaurants),
    }


def _load_dotenv_into_os():
    """Lightweight .env loader so we don't depend on python-dotenv being imported."""
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def maybe_send_failure_alert(today, total, failed, failed_targets,
                             threshold_pct=50.0):
    """
    Email a failure summary when >threshold_pct of restaurants failed.

    Reads GMAIL_USER + GMAIL_APP_PASSWORD from environment (or .env).
    Optional ALERT_TO overrides the recipient (defaults to GMAIL_USER).
    No-op when credentials missing — we never want the scraper to crash
    because alerting is misconfigured.
    """
    if total <= 0:
        return
    failure_rate = (failed / total) * 100.0
    if failure_rate < threshold_pct:
        log(f"  ✓ Failure rate {failure_rate:.1f}% below {threshold_pct:.0f}% — no alert")
        return

    _load_dotenv_into_os()
    user = os.environ.get('GMAIL_USER')
    password = os.environ.get('GMAIL_APP_PASSWORD')
    recipient = os.environ.get('ALERT_TO', user)
    if not user or not password:
        log(f"  ⚠  Failure rate {failure_rate:.1f}% over threshold but "
            "GMAIL_USER/GMAIL_APP_PASSWORD not configured — skipping alert")
        return

    import smtplib
    from email.mime.text import MIMEText

    body_lines = [
        f"UIFPI scraper failure alert — {today}",
        '',
        f"Total targets:   {total}",
        f"Failed:          {failed}  ({failure_rate:.1f}%)",
        f"Threshold:       {threshold_pct:.0f}%",
        '',
        'Failed restaurants:',
    ]
    for tgt in failed_targets:
        name = tgt[0] if isinstance(tgt, (tuple, list)) else str(tgt)
        country = tgt[5] if isinstance(tgt, (tuple, list)) and len(tgt) >= 6 else '?'
        body_lines.append(f"  - {name}  ({country})")
    body_lines += [
        '',
        f"See {LOG_PATH} for full error messages.",
    ]
    body = '\n'.join(body_lines)

    msg = MIMEText(body)
    msg['Subject'] = f"UIFPI Scraper Alert — {today} — {failed} failures"
    msg['From'] = user
    msg['To'] = recipient

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.sendmail(user, [recipient], msg.as_string())
        log(f"  ✉  Alert email sent to {recipient}")
    except Exception as e:
        log(f"  ⚠  Failed to send alert email: {e}")


def report_price_changes(summary):
    """Print the standard end-of-run price-change summary to the log."""
    n = summary['n_changes']
    r = summary['n_restaurants']
    log(f"\nPrice changes detected: {n} items across {r} restaurants")
    if n == 0:
        return

    def _fmt(ch, arrow):
        return (f"  {arrow} {ch['restaurant_name']:30s} "
                f"{ch['item_name'][:40]:40s} "
                f"{ch['old_price']:.2f} → {ch['new_price']:.2f}  "
                f"({ch['pct']:+.2f}%)")

    increases = sorted((ch for ch in summary['changes'] if ch['pct'] > 0),
                       key=lambda x: x['pct'], reverse=True)
    decreases = sorted((ch for ch in summary['changes'] if ch['pct'] < 0),
                       key=lambda x: x['pct'])
    if increases:
        log("\nTop 5 price increases:")
        for ch in increases[:5]:
            log(_fmt(ch, '↑'))
    if decreases:
        log("\nTop 5 price decreases:")
        for ch in decreases[:5]:
            log(_fmt(ch, '↓'))


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
    'Vietnam':        ('en-VN', 'Asia/Ho_Chi_Minh'),
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
            page.wait_for_timeout(random.randint(750, 1000))
    except Exception:
        pass


def _looks_like_block(page):
    """Detect Foodpanda / GrabFood / Akamai bot-block pages and dead pages.

    Returns True for bot-blocks AND for confirmed-dead pages (404, 500),
    so the retry loop fails fast instead of repeatedly hitting a non-existent
    URL. The caller treats this as ACCESS_DENIED.
    """
    try:
        title = (page.title() or '').lower()
    except Exception:
        title = ''
    if 'access denied' in title or 'denied' in title:
        return True
    if 'are you a robot' in title or 'attention required' in title:
        return True
    # Foodpanda's 404 page: <title>404 Ooops!</title>
    if '404' in title or 'page not found' in title or '500' in title:
        return True
    if 'ooops' in title:
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
                   'cloudflare', 'unusual traffic',
                   'page does not exist', 'looks like this restaurant'):
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
    _warmup(page, 'foodpanda', country)
    # 'domcontentloaded' is more reliable than 'networkidle' here — Foodpanda
    # opens long-poll WebSocket connections that prevent networkidle from
    # ever firing on slow connections.
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
    except Exception as e:
        # Treat hard nav failures as access blocks — same retry semantics
        raise RuntimeError(f"ACCESS_DENIED (nav: {str(e)[:100]})")
    page.wait_for_timeout(random.randint(2_000, 3_500))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    # Try each selector with a short individual timeout. The first matching
    # selector wins; the previous 15s × 4 selectors meant a full miss cost 60s.
    matched_selector = None
    for sel in FOODPANDA_SELECTORS:
        try:
            page.wait_for_selector(sel, timeout=5_000)
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
    if count:
        log(f"  ✓ {restaurant_name}: {count} items")
    else:
        log(f"  ✗ {restaurant_name}: 0 items — page did not yield menu data")
    return count


# ── GrabFood scraper ───────────────────────────────────────────────────────────

_GRABFOOD_LANDING_TITLE_FRAGMENTS = ('food delivery', 'promos & menu')


def _looks_like_grabfood_landing(page):
    """True if the page is the country landing page rather than the
    restaurant — happens when delivery location wasn't established before
    navigation. Detected via the country-landing <title>."""
    try:
        title = (page.title() or '').lower()
    except Exception:
        return False
    return all(frag in title for frag in _GRABFOOD_LANDING_TITLE_FRAGMENTS)


def scrape_grabfood(page, url, restaurant_name, sector, currency,
                    conn, country, usd_rates):
    """
    Scrapes a GrabFood restaurant or chain page.
    Tries aria-label extraction first; falls back to standalone price spans.
    """
    log(f"  Loading {restaurant_name} (GrabFood)…")
    _warmup(page, 'grabfood', country)

    # GrabFood will silently 302 a chain/restaurant URL to the country
    # landing page when no delivery location is set. Retry the navigation
    # up to 3 times with re-warmup between, so the location cookie has
    # time to propagate.
    nav_attempts = 0
    while True:
        nav_attempts += 1
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=45_000)
        except Exception as e:
            raise RuntimeError(f"ACCESS_DENIED (nav: {str(e)[:100]})")
        page.wait_for_timeout(random.randint(3_000, 5_000))
        _human_mouse_jitter(page)

        if _looks_like_block(page):
            raise RuntimeError("ACCESS_DENIED")

        if not _looks_like_grabfood_landing(page):
            break
        if nav_attempts >= 3:
            log(f"    still on landing page after {nav_attempts} nav attempts; giving up")
            break
        log(f"    landing-page redirect on nav {nav_attempts}; re-warming + retry")
        _warmup(page, 'grabfood', country)
        page.wait_for_timeout(random.randint(5_000, 7_500))

    if '/chain/' in url:
        try:
            page.wait_for_selector('a[href*="/restaurant/"]', timeout=8_000)
            outlet = page.query_selector('a[href*="/restaurant/"]')
            if outlet:
                outlet.click()
                page.wait_for_timeout(7_500)
        except Exception as e:
            log(f"    Chain nav failed: {e}")

    # Poll for menu to render — was 30 × 1s, now 12 × 500ms (6s max).
    # With resource blocking the menu typically renders in 2-3s.
    for _ in range(12):
        ready = page.evaluate("""() => (
            document.querySelectorAll('[class*="MenuItem"],[class*="menuItem"],[class*="dish"],button[aria-label*="Add"]').length
        )""")
        if ready and ready > 5:
            break
        page.wait_for_timeout(500)

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
        // GrabFood VN uses thousands-grouped VND like "178.000" (= 178000 VND).
        // The selector intentionally accepts both "MenuItem" and "menuItem"
        // (case-sensitive CSS attribute match) since the SPA mixes both.
        if (results.length === 0) {
            // Returns parsed value or null. Handles:
            //   "7.50" / "7,50"     → 7.50    (decimal, 2 dp)
            //   "178.000" / "178,000" → 178000 (thousands, 3 dp)
            //   "1.250.000"           → 1250000 (millions)
            //   "33000"               → 33000  (bare integer ≥ 4 digits)
            const parseLocalized = (raw) => {
                const t = raw.trim();
                let m;
                if ((m = t.match(/^(\\d{1,3})[.,](\\d{3})[.,](\\d{3})$/))) {
                    return parseInt(m[1] + m[2] + m[3], 10);
                }
                if ((m = t.match(/^(\\d{1,3})[.,](\\d{3})$/))) {
                    return parseInt(m[1] + m[2], 10);
                }
                if ((m = t.match(/^(\\d{1,4})[.,](\\d{2})$/))) {
                    return parseFloat(m[1] + '.' + m[2]);
                }
                if ((m = t.match(/^(\\d{4,7})$/))) {
                    return parseInt(m[1], 10);
                }
                return null;
            };
            const looksLikePrice = (raw) => parseLocalized(raw) !== null;
            const containers = document.querySelectorAll(
                '[class*="MenuItem"], [class*="menuItem"]'
            );
            for (const el of containers) {
                const text = (el.innerText || '').trim();
                if (!text || text.length > 800) continue;
                // Find the price: look at descendant elements with bare numeric text
                let price = 0;
                for (const cand of el.querySelectorAll('span,p,div')) {
                    const t = (cand.innerText || '').trim();
                    const v = parseLocalized(t);
                    // Wide range: VND can reach 5,000,000 (luxury combo);
                    // SGD/MYR/etc. stay below 1000. Filter pathological values.
                    if (v !== null && v > 0 && v < 10000000) {
                        price = v;
                        break;
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
                if (looksLikePrice(name)) continue;
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
                // Same parser as Strategy 3 — handles decimal and thousands
                // grouping (VND prices use "178.000" = 178000).
                const parseLocalized = (raw) => {
                    const t = raw.trim();
                    let m;
                    if ((m = t.match(/^(\d{1,3})[.,](\d{3})[.,](\d{3})$/))) {
                        return parseInt(m[1] + m[2] + m[3], 10);
                    }
                    if ((m = t.match(/^(\d{1,3})[.,](\d{3})$/))) {
                        return parseInt(m[1] + m[2], 10);
                    }
                    if ((m = t.match(/^(\d{1,4})[.,](\d{2})$/))) {
                        return parseFloat(m[1] + '.' + m[2]);
                    }
                    if ((m = t.match(/^(\d{4,7})$/))) {
                        return parseInt(m[1], 10);
                    }
                    return null;
                };
                const looksLikePrice = (s) => parseLocalized(s) !== null;
                const buf = [];
                const looksLikeTitle = (s) => (
                    s.length >= 3 && s.length <= 90
                    && !looksLikePrice(s)
                    && /[A-Za-z　-鿿]/.test(s)
                    && !s.endsWith('.')
                    && !/^(For You|Opening Hours|Today|Home|Restaurant|Login|Help|Order Now)$/i.test(s)
                );
                for (const ln of lines) {
                    const price = parseLocalized(ln);
                    if (price !== null && price > 0 && price < 10000000) {
                        if (buf.length) {
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

    if items:
        log(f"  ✓ {restaurant_name}: {len(items)} items")
    else:
        log(f"  ✗ {restaurant_name}: 0 items — page did not yield menu data")
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
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
    except Exception as e:
        raise RuntimeError(f"ACCESS_DENIED (nav: {str(e)[:100]})")
    page.wait_for_timeout(random.randint(3_000, 5_000))
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
    if count:
        log(f"  ✓ {restaurant_name}: {count} items")
    else:
        log(f"  ✗ {restaurant_name}: 0 items — page did not yield menu data")
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
    Strategies in order:
      0. XHR-intercept — capture JSON responses fetched after page load
         (modern US chain sites are React shells; prices come from APIs)
      1. JSON-LD <script type="application/ld+json"> MenuItems
      2. Embedded JSON blobs (NEXT_DATA, inline scripts)
      3. DOM price text extraction
    """
    log(f"  Loading {restaurant_name} (direct)…")

    # Set up XHR response capture BEFORE navigating, so we don't miss the
    # menu API call that fires during initial render.
    xhr_jsons = []

    def _on_response(resp):
        # Only sample JSON-ish responses likely to carry menu data
        try:
            ct = resp.headers.get('content-type', '').lower()
            if 'json' not in ct and not resp.url.lower().endswith('.json'):
                return
            # Cap body size to avoid pulling 10MB analytics blobs
            body = resp.body()
            if not body or len(body) > 2_000_000:
                return
            # Lightweight content sniff: must mention name+price-ish keys
            head = body[:8000].decode('utf-8', errors='ignore').lower()
            if not (('name' in head or 'item' in head or 'product' in head
                     or 'menu' in head or 'choice' in head)
                    and ('price' in head or 'amount' in head or 'value' in head
                         or 'cents' in head or 'pence' in head)):
                return
            xhr_jsons.append(body.decode('utf-8', errors='ignore'))
        except Exception:
            pass

    try:
        page.on('response', _on_response)
    except Exception:
        pass

    # networkidle never fires on pages with polling/long-poll — use
    # domcontentloaded + a fixed wait for menu XHR to settle.
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
    except Exception as e:
        raise RuntimeError(f"ACCESS_DENIED (nav: {str(e)[:100]})")
    page.wait_for_timeout(random.randint(6_000, 9_000))
    _human_mouse_jitter(page)

    if _looks_like_block(page):
        raise RuntimeError("ACCESS_DENIED")

    today = date.today().isoformat()
    items = []

    # Strategy 0: walk captured XHR JSON for name+price pairs
    if xhr_jsons:
        log(f"    captured {len(xhr_jsons)} XHR JSON responses")
        for raw in xhr_jsons:
            try:
                data = json.loads(raw)
            except Exception:
                continue
            for it in _walk_json_for_items(data, currency):
                # de-dup happens in insert; we collect first
                items.append(it)
        if items:
            # de-dup by (name, price)
            seen = set()
            dedup = []
            for it in items:
                key = f"{it['name']}|{round(it['price'], 2)}"
                if key in seen:
                    continue
                seen.add(key)
                dedup.append(it)
            items = dedup
            log(f"    XHR yielded {len(items)} candidate items")

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
    if count:
        log(f"  ✓ {restaurant_name}: {count} items")
    else:
        log(f"  ✗ {restaurant_name}: 0 items — page did not yield menu data")
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
    """Recursively pull name+price pairs out of a parsed JSON tree.

    Handles common price shapes:
      "price": 12.99
      "price": "12.99"
      "price": {"amount": 1299, "currency": "USD"}      (minor units)
      "prices": {"cents": 1299, "points": 0}            (Nando AU GraphQL)
      "basePrice"/"defaultPrice"/"finalPrice"
      "priceMonetaryFields": {...}
    """
    if items is None:
        items = []
    if depth > 16:
        return items
    if isinstance(obj, dict):
        name = obj.get('name') or obj.get('itemName') or obj.get('title')

        # Find the raw price object/value
        price = (obj.get('price') or obj.get('basePrice')
                 or obj.get('defaultPrice') or obj.get('finalPrice')
                 or obj.get('priceMonetaryFields')
                 or obj.get('prices'))

        # Normalise dict-shaped prices to a plain number
        from_minor_units = False
        if isinstance(price, dict):
            if 'cents' in price:
                price = price.get('cents')
                from_minor_units = True
            elif 'pence' in price:
                price = price.get('pence')
                from_minor_units = True
            else:
                price = (price.get('unitAmount') or price.get('amount')
                         or price.get('value'))
                # 'amount' in minor units when paired with a 'currency' key
                if price is not None and any(k in (obj.get('price') or {})
                                              for k in ('currency', 'currencyCode')):
                    from_minor_units = True

        if name and price is not None:
            try:
                p = float(price)
                if from_minor_units:
                    p = p / 100.0
                # Heuristic: prices that look too large for the currency
                # were likely shipped in minor units (cents/paise) but
                # didn't have the explicit signal above.
                elif currency in ('USD', 'GBP', 'AUD', 'SGD', 'MYR') and p > 1000:
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
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
    except Exception as e:
        raise RuntimeError(f"ACCESS_DENIED (nav: {str(e)[:100]})")
    page.wait_for_timeout(random.randint(3_000, 5_000))
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

    if count == 0:
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
            log(f"    js generic returned 0 items. title={title!r}. "
                f"HTML {len(html)} chars saved to debug_page.html. "
                f"Body head: {body_head[:400]!r}")
        except Exception as e:
            log(f"    js generic returned 0 items. title={title!r}. dump failed: {e}")

    if count:
        log(f"  ✓ {restaurant_name}: {count} items")
    else:
        log(f"  ✗ {restaurant_name}: 0 items — page did not yield menu data")
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


# Headless Chromium is reliably bot-detected by foodpanda / grabfood.
# Set UIFPI_HEADLESS=1 to force headless (e.g. on a server without a display).
HEADLESS = os.environ.get('UIFPI_HEADLESS', '0') == '1'


def _block_heavy_resources(route, request):
    """Block images, fonts, stylesheets, media and known analytics — none of
    them carry menu data and they account for the bulk of page weight."""
    r_type = request.resource_type
    if r_type in ('image', 'media', 'font', 'stylesheet'):
        return route.abort()
    url = request.url.lower()
    BLOCKED_HOSTS = (
        'google-analytics.com', 'googletagmanager.com', 'doubleclick.net',
        'facebook.net', 'facebook.com/tr', 'connect.facebook.net',
        'hotjar.com', 'mixpanel.com', 'segment.io', 'segment.com',
        'newrelic.com', 'nr-data.net', 'datadoghq.com', 'sentry.io',
        'optimizely.com', 'amplitude.com', 'fullstory.com',
        'cdn.cookielaw.org', 'onetrust.com', 'usercentrics.eu',
        'tvsquared.com', 'appboycdn.com', 'braze.com',
    )
    if any(host in url for host in BLOCKED_HOSTS):
        return route.abort()
    return route.continue_()


def _new_context(browser, country):
    """Build a stealth-friendly context that matches the target country."""
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    # Randomise viewport slightly to defeat fingerprint heuristics that bin
    # to common headless presets (1366x768 / 1920x1080).
    width = random.choice([1366, 1440, 1536, 1680])
    height = random.choice([768, 800, 864, 900])
    ctx = browser.new_context(
        viewport={'width': width, 'height': height},
        user_agent=_pick_user_agent(),
        locale=locale,
        timezone_id=tz,
        extra_http_headers={
            'Accept-Language': f'{locale.replace("_", "-")},en;q=0.8',
            'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                       'image/avif,image/webp,*/*;q=0.8'),
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        },
    )
    # Remove the webdriver navigator flag — easiest cdp tell
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        "Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});"
    )
    # Drop heavy resources we never use (images, fonts, css, analytics).
    # This typically cuts foodpanda / grabfood page load 40-60%.
    try:
        ctx.route('**/*', _block_heavy_resources)
    except Exception:
        pass
    return ctx


# Per-source home page used as a warm-up navigation. Hitting the chain page
# directly with no referrer flags as suspicious; visiting the home page
# first sets cookies and gives a real Referer header.
WARMUP_HOME = {
    ('foodpanda', 'Singapore'):  'https://www.foodpanda.sg/',
    ('foodpanda', 'Malaysia'):   'https://www.foodpanda.my/',
    ('foodpanda', 'Indonesia'):  'https://www.foodpanda.id/',
    ('foodpanda', 'Thailand'):   'https://www.foodpanda.co.th/',
    ('grabfood',  'Singapore'):  'https://food.grab.com/sg/en/',
    ('grabfood',  'Malaysia'):   'https://food.grab.com/my/en/',
    ('grabfood',  'Indonesia'):  'https://food.grab.com/id/en/',
    ('grabfood',  'Thailand'):   'https://food.grab.com/th/en/',
    ('grabfood',  'Vietnam'):    'https://food.grab.com/vn/en/',
}


# GrabFood requires a delivery `location` cookie before chain/restaurant
# URLs render the menu; without it, the URL silently 302s to the country
# landing page. The home page sets this automatically via geo-IP within a
# few seconds, but the cookie sometimes hasn't been written when we navigate
# away, so we seed a known-good default per country at context level.
GRABFOOD_LOCATION_SEED = {
    # Marina Bay area, Singapore — generic CBD coordinates, isAccurate=false
    'Singapore': (
        '{"latitude":1.287953,"longitude":103.851784,'
        '"address":"Singapore","countryCode":"SG","isAccurate":false,'
        '"addressDetail":"","noteToDriver":""}'
    ),
    # Kuala Lumpur city centre, Malaysia — KLCC area
    'Malaysia': (
        '{"latitude":3.158246,"longitude":101.711739,'
        '"address":"Kuala Lumpur","countryCode":"MY","isAccurate":false,'
        '"addressDetail":"","noteToDriver":""}'
    ),
    # Ho Chi Minh City — District 1 / Ben Thanh area (food delivery hub)
    'Vietnam': (
        '{"latitude":10.776530,"longitude":106.700981,'
        '"address":"Ho Chi Minh City","countryCode":"VN","isAccurate":false,'
        '"addressDetail":"","noteToDriver":""}'
    ),
}


def _seed_grabfood_location(page, country):
    """Write the GrabFood location cookie + landing-country localStorage
    so the very first restaurant navigation has a valid delivery location.
    Without this, chain URLs redirect to the country landing page."""
    seed = GRABFOOD_LOCATION_SEED.get(country)
    if not seed:
        return
    try:
        # URL-encode the JSON for cookie value (matches GrabFood's own format)
        from urllib.parse import quote
        cookie_value = quote(seed, safe='')
        page.context.add_cookies([{
            'name': 'location',
            'value': cookie_value,
            'domain': 'food.grab.com',
            'path': '/',
            'secure': True,
            'sameSite': 'Lax',
        }])
    except Exception:
        pass
    # Also seed landing-country-selected localStorage so the SPA doesn't
    # re-route to the country picker.
    _GF_COUNTRY_PATH = {
        'Singapore': '/sg/en/',
        'Malaysia':  '/my/en/',
        'Vietnam':   '/vn/en/',
    }
    cc_path = _GF_COUNTRY_PATH.get(country, '/sg/en/')
    try:
        page.evaluate(
            f"() => localStorage.setItem('landing-country-selected', '{cc_path}')"
        )
    except Exception:
        # localStorage may not be writable until after first navigation;
        # ignore — the cookie alone is usually enough.
        pass


def _warmup(page, source, country):
    """Quick home-page hit before the real navigation so we have cookies."""
    home = WARMUP_HOME.get((source, country))
    if not home:
        return
    try:
        if source == 'grabfood':
            # Seed location BEFORE the first navigation so the home page
            # itself loads as a location-aware session, then the chain URL
            # navigation doesn't redirect.
            _seed_grabfood_location(page, country)
        page.goto(home, wait_until='domcontentloaded', timeout=20_000)
        page.wait_for_timeout(random.randint(1_200, 2_500))
        if source == 'grabfood':
            # After home loads, re-write localStorage (now writable) and
            # let GrabFood's own session JS settle (writes `location` if missing).
            _seed_grabfood_location(page, country)
            page.wait_for_timeout(1_500)
        _human_mouse_jitter(page)
    except Exception:
        # Warm-up failures aren't fatal — proceed to the real target
        pass


# Per-target retry policy.
#   max_attempts:  total tries in this _scrape_one call
#   block_wait_s:  short pause between attempts after a bot-block
# Targets that exhaust attempts get re-queued for the end-of-run retry pass
# (see __main__), so we don't burn 15 min/target inline.
SCRAPE_MAX_ATTEMPTS = 2
SCRAPE_BLOCK_WAIT_S = 45


def _scrape_one(target, conn, today, usd_rates):
    """
    Scrape a single target with up to SCRAPE_MAX_ATTEMPTS quick tries.
    On bot-block, brief pause then retry once. Hard failures bubble up so
    the caller can put the target on the end-of-run retry queue instead of
    blocking the whole batch with multi-minute sleeps.
    """
    name, url, sector, source, currency, country = target
    fn = SCRAPER_DISPATCH.get(source)
    if fn is None:
        raise ValueError(f"Unknown source type: {source}")

    last_error = None
    for attempt in range(1, SCRAPE_MAX_ATTEMPTS + 1):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
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
                except Exception as e:
                    last_error = e
                    is_access_denied = (isinstance(e, RuntimeError)
                                        and 'ACCESS_DENIED' in str(e))
                    if is_access_denied:
                        log(f"  Bot detected on attempt {attempt}")
                        # Akamai/Cloudflare IP block: 45s wait does not help.
                        # Skip the inner retry and let the end-of-run pass
                        # catch it after the longer inter-pass cooldown.
                        raise
                    elif attempt >= SCRAPE_MAX_ATTEMPTS:
                        raise
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

        if attempt < SCRAPE_MAX_ATTEMPTS:
            log(f"  waiting {SCRAPE_BLOCK_WAIT_S}s before retry {attempt + 1}/{SCRAPE_MAX_ATTEMPTS} …")
            time.sleep(SCRAPE_BLOCK_WAIT_S)

    raise last_error if last_error else RuntimeError("unknown failure")


# Number of parallel scraping workers. Each worker holds its own Playwright
# browser and SQLite connection. Default 1 (sequential). Parallel runs at
# workers=3/4 produce ~95-99% Foodpanda block rate due to per-IP Akamai
# burnout; sequential keeps GrabFood at ~0% block and modestly improves
# Foodpanda. Override with UIFPI_CONCURRENCY for short low-risk batches.
SCRAPE_CONCURRENCY = int(os.environ.get('UIFPI_CONCURRENCY', '1'))
# Per-worker inter-target sleep range (seconds). Akamai/Cloudflare block
# by IP, not by request cadence, so long human-looking sleeps don't help.
INTER_TARGET_DELAY = (5.0, 10.0)


def _worker_run(target, today, usd_rates):
    """
    One target's worth of work in a single worker thread.
    Each call opens its own SQLite connection (sqlite3 connections are not
    thread-safe across threads, but WAL mode lets multiple connections write
    concurrently to the same file).
    Returns (target, ok_bool, error_or_None).
    """
    name = target[0]
    db_path = os.path.join(BASE_DIR, 'uifpi.db')
    local_conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    # Match the WAL/sync settings init_db uses
    try:
        local_conn.execute('PRAGMA journal_mode=WAL')
        local_conn.execute('PRAGMA synchronous=NORMAL')
    except Exception:
        pass
    try:
        if already_scraped(local_conn, name, today):
            log(f"  ↩  {name}: already collected today, skip")
            return target, True, None
        try:
            _scrape_one(target, local_conn, today, usd_rates)
            return target, True, None
        except Exception as e:
            log(f"  ✗  {name}: {e}")
            return target, False, e
    finally:
        try:
            local_conn.close()
        except Exception:
            pass


def run_batch(targets, conn, today, usd_rates):
    """
    Scrape every target. Each target gets its own fresh browser context
    (cheap insurance against accumulated fingerprint state) and may retry
    internally on bot-block pages.

    When UIFPI_CONCURRENCY > 1, targets are scraped in parallel by N worker
    threads — each with its own Playwright browser and SQLite connection.

    Returns the list of targets that failed.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if SCRAPE_CONCURRENCY <= 1:
        # Sequential path keeps the original log layout
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
            delay = random.uniform(*INTER_TARGET_DELAY)
            log(f"  sleeping {delay:.1f}s before next target")
            time.sleep(delay)
        return failures

    # Parallel path
    log(f"  Parallel mode: {SCRAPE_CONCURRENCY} workers")
    failures = []
    # Wrap each worker call with a per-target jitter sleep BEFORE the scrape
    # so the N workers don't slam the same domain in unison.
    def _wrapped(target):
        time.sleep(random.uniform(*INTER_TARGET_DELAY))
        return _worker_run(target, today, usd_rates)

    with ThreadPoolExecutor(max_workers=SCRAPE_CONCURRENCY) as pool:
        futures = {pool.submit(_wrapped, t): t for t in targets}
        for fut in as_completed(futures):
            target, ok, err = fut.result()
            if not ok:
                failures.append(target)
    return failures


# ── Targets ────────────────────────────────────────────────────────────────────
# Tuple format: (display_name, url, sector, source_key, currency, country)
#
# sector   : 'chain'       — multinational / corporate chain
#            'independent' — hawker-origin, family-run, or local institution
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
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Ichiban Boshi",
     "https://www.foodpanda.sg/chain/cf5xz/ichiban-boshi",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Din Tai Fung",
     "https://food.grab.com/sg/en/restaurant/din-tai-fung-plaza-singapura-delivery/4-C2DHGZLXE2DURJ",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Sushi Tei",
     "https://food.grab.com/sg/en/restaurant/sushi-tei-vivocity-delivery/4-C2MFTGNUEPKGEN",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Jumbo Seafood",
     "https://food.grab.com/sg/en/restaurant/jumbo-seafood-east-coast-delivery/SGDD01672",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Crystal Jade La Mian Xiao Long Bao",
     "https://www.foodpanda.sg/chain/cp7ao/crystal-jade-la-mian-xiao-long-bao",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("No Signboard Prawn Noodles and Carrot Cake",
     "https://www.foodpanda.sg/restaurant/v2xf/no-signboard-prawn-noodles-and-carrot-cake-301-ubi-food-house",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Putien",
     "https://www.foodpanda.sg/chain/cc7gt/putien",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Paradise Dynasty",
     "https://www.foodpanda.sg/chain/cf5cj/paradise-dynasty",
     "chain", "foodpanda", "SGD", "Singapore"),

    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("Tim Ho Wan",
     "https://food.grab.com/sg/en/restaurant/tim-ho-wan-plaza-singapura-delivery/SGDD11583",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Crystal Jade Hong Kong Kitchen",
     "https://www.foodpanda.sg/chain/cs3bp/crystal-jade-hong-kong-kitchen",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Pepper Lunch",
     "https://www.foodpanda.sg/chain/cx6yd/pepper-lunch",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Ippudo Ramen",
     "https://food.grab.com/sg/en/restaurant/ippudo-mandarin-gallery-delivery/SGDD11131",
     "chain", "grabfood", "SGD", "Singapore"),

    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("Seoul Garden HotPot",
     "https://food.grab.com/sg/en/restaurant/seoul-garden-hotpot-harbourfront-centre-delivery/SGDD09383",
     "chain", "grabfood", "SGD", "Singapore"),

    # Removed Hokkaido-ya: foodpanda.sg URL stuck behind Akamai IP block;
    # searched GrabFood SG for "Hokkaido-ya" and "Hokkaido Ya Ramen" — no match.
    # Restaurant doesn't appear to be on GrabFood SG.

    ("BreadTalk",
     "https://food.grab.com/sg/en/restaurant/breadtalk-bedok-mall-b2-25-26-delivery/4-CZBGAY4AVA4GLE",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Toast Box",
     "https://www.foodpanda.sg/chain/cv4kj/toast-box",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Old Chang Kee",
     "https://www.foodpanda.sg/chain/cl8xf/old-chang-kee",
     "chain", "foodpanda", "SGD", "Singapore"),

    ("Crystal Jade GO",
     "https://www.foodpanda.sg/chain/cx5on/crystal-jade-go",
     "chain", "foodpanda", "SGD", "Singapore"),

    # Round-2 GrabFood SG additions (probed 2026-06-23 with WAF priming).
    # GrabFood added an aws-waf-token gate; new URLs redirect to landing
    # unless a "WAF-priming" restaurant URL has been visited first in the
    # same browser session. McDonald's People's Park is the priming target
    # used by the live scraper for SG. Probe yielded 7/11 SG candidates
    # pass; the 4 that still failed (Crystal Jade HK Kitchen, Crystal Jade
    # Go United Square, Pizza Hut Plaza Singapura, Yoshinoya Wisteria Mall)
    # may be delisted or have URL changes — not retried.
    ("McDonald's",
     "https://food.grab.com/sg/en/restaurant/mcdonald-s-people-s-park-delivery/SGDD04919",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Han's",
     "https://food.grab.com/sg/en/restaurant/han-s-jalan-bukit-merah-delivery/4-CZDJJPJFFEVXHE",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Saizeriya",
     "https://food.grab.com/sg/en/restaurant/saizeriya-chinatown-point-delivery/4-CZEAR6D3V2JFCT",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Subway",
     "https://food.grab.com/sg/en/restaurant/subway-the-central-delivery/4-CYTDLPUTG242KA",
     "chain", "grabfood", "SGD", "Singapore"),

    ("Burger King",
     "https://food.grab.com/sg/en/restaurant/burger-king-ang-mo-kio-hub-delivery/4-CY3TEBNKN742R2",
     "chain", "grabfood", "SGD", "Singapore"),

    # Disambiguated from foodpanda "Old Chang Kee" (chain URL) above —
    # this is the IMM Building branch on GrabFood.
    ("Old Chang Kee IMM",
     "https://food.grab.com/sg/en/restaurant/old-chang-kee-imm-building-delivery/4-CYN2GYVDGNEXVN",
     "chain", "grabfood", "SGD", "Singapore"),

    # Disambiguated from foodpanda "Toast Box" (chain URL) above —
    # this is the VivoCity branch on GrabFood.
    ("Toast Box VivoCity",
     "https://food.grab.com/sg/en/restaurant/toast-box-vivocity-delivery/SGDD11187",
     "chain", "grabfood", "SGD", "Singapore"),

    # --- Informal ---
    ("Song Fa Bak Kut Teh",
     "https://www.foodpanda.sg/chain/cw6zr/song-fa-bak-kut-teh",
     "independent", "foodpanda", "SGD", "Singapore"),

    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("Hawker Chan",
     "https://food.grab.com/sg/en/restaurant/hawker-chan-76-78-smith-street-delivery/4-CYVGGU3TVCLFAT",
     "independent", "grabfood", "SGD", "Singapore"),

    ("A Noodle Story",
     "https://www.foodpanda.sg/chain/ck9ew/a-noodle-story",
     "independent", "foodpanda", "SGD", "Singapore"),

    ("328 Katong Laksa",
     "https://www.foodpanda.sg/chain/cj3zd/328-katong-laksa",
     "independent", "foodpanda", "SGD", "Singapore"),

    ("Crave Nasi Lemak",
     "https://www.foodpanda.sg/chain/cq1ek/crave",
     "independent", "foodpanda", "SGD", "Singapore"),

    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("28 Fried Kway Teow",
     "https://food.grab.com/sg/en/restaurant/28-fried-kway-teow-dunman-food-centre-stall-28-delivery/4-CYLCC4CHANVTBE",
     "independent", "grabfood", "SGD", "Singapore"),

    ("Tai Wah Pork Noodles",
     "https://www.foodpanda.sg/chain/ce0vj/tai-wah-pork-noodles",
     "independent", "foodpanda", "SGD", "Singapore"),

    ("Janggut Laksa",
     "https://www.foodpanda.sg/chain/cv4xl/the-original-katong-laksa-since-1950",
     "independent", "foodpanda", "SGD", "Singapore"),

    ("Nam Kee Chicken Rice",
     "https://www.foodpanda.sg/chain/ci9rk/nam-kee-chicken-rice",
     "independent", "foodpanda", "SGD", "Singapore"),

    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("Swee Choon Tim Sum",
     "https://food.grab.com/sg/en/restaurant/swee-choon-tim-sum-restaurant-jalan-besar-delivery/4-CY42SA2VETAKN6",
     "independent", "grabfood", "SGD", "Singapore"),

    ("Killiney Kopitiam",
     "https://www.foodpanda.sg/chain/ca6up/killiney-kopitiam-alexandra",
     "independent", "foodpanda", "SGD", "Singapore"),

    # ==========================================================================
    # MALAYSIA
    # ==========================================================================

    # --- Formal ---
    # Replaced foodpanda URL with verifiable GrabFood URL (found via search 2026-06-15)
    ("Din Tai Fung KL",
     "https://food.grab.com/my/en/restaurant/din-tai-fung-the-gardens-mall-non-halal-delivery/1-CY2UGABXFCA2RE",
     "chain", "grabfood", "MYR", "Malaysia"),

    # Removed Sushi Tei KL: foodpanda.my URL couldn't be verified (IP-blocked),
    # not findable on GrabFood Malaysia from KLCC delivery address.


    ("Ichiban Boshi KL",
     "https://www.foodpanda.my/chain/ct3ai/ichiban-boshi-japanese-restaurant",
     "chain", "foodpanda", "MYR", "Malaysia"),

    ("Pepper Lunch KL",
     "https://www.foodpanda.my/chain/cc7eh/pepper-lunch-nh-group",
     "chain", "foodpanda", "MYR", "Malaysia"),

    ("Ippudo KL",
     "https://food.grab.com/my/en/restaurant/ippudo-bsc-non-halal-delivery/1-CZC3AE5BRJXJJT",
     "chain", "grabfood", "MYR", "Malaysia"),

    # [verifier:DEAD] status=500 title='500 Internal Server Error'
    # ("Secret Recipe",
     # "https://food.grab.com/my/en/chain/secret-recipe-delivery",
     # "chain", "grabfood", "MYR", "Malaysia"),

    ("OldTown White Coffee",
     "https://www.foodpanda.my/chain/ce9ti/oldtown",
     "chain", "foodpanda", "MYR", "Malaysia"),

    ("Nando's KL",
     "https://food.grab.com/my/en/chain/nandos-delivery",
     "chain", "grabfood", "MYR", "Malaysia"),

    # Removed TGI Fridays KL: foodpanda.my URL couldn't be verified (IP-blocked),
    # not findable on GrabFood Malaysia from KLCC delivery address.


    # Removed Madam Kwan's: foodpanda.my URL couldn't be verified (IP-blocked),
    # not findable on GrabFood Malaysia from KLCC delivery address.


    # --- Informal ---
    # Removed Village Park Nasi Lemak: GrabFood listing is soft-disabled
    # (page title is "[INACTV: COCO] Village Park Restaurant"). Menu JSON
    # still ships in the HTML but the visible UI shows "Uh Oh... We Couldn't
    # Find What You're Looking For". Needs a fresh GrabFood/foodpanda URL.
    # ("Village Park Nasi Lemak",
    #  "https://food.grab.com/my/en/restaurant/village-park-restaurant-delivery/MYDD05660",
    #  "independent", "grabfood", "MYR", "Malaysia"),

    ("Restoran Yusoof Dan Zakhir",
     "https://www.foodpanda.my/restaurant/y9sn/restoran-yusoof-and-zakhir-sdn-bhd",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Ah Weng Koh Hainan Tea",
     "https://food.grab.com/my/en/restaurant/ah-weng-koh-hainan-tea-icc-pudu-delivery/1-CZJKJY4ZA4EXT6",
     "independent", "grabfood", "MYR", "Malaysia"),

    ("Dragon-i",
     "https://food.grab.com/my/en/restaurant/dragon-i-mid-valley-non-halal-delivery/MYDD12601",
     "independent", "grabfood", "MYR", "Malaysia"),

    ("Kluang Rail Coffee",
     "https://www.foodpanda.my/chain/ct6tr/kluang-rail-coffee",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Kim Lian Kee",
     "https://www.foodpanda.my/restaurant/ch0l/kim-lian-kee-ch0l",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Hameed Pata Mee Sotong",
     "https://www.foodpanda.my/restaurant/pp2t/hameed-pata-mee",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Nasi Kandar Pelita",
     "https://www.foodpanda.my/restaurant/o2ge/nasi-kandar-pelita-bangsar",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Jerung Char Koay Teow",
     "https://www.foodpanda.my/chain/cd4du/jerung-char-koay-teow",
     "independent", "foodpanda", "MYR", "Malaysia"),

    ("Family Seafood",
     "https://www.foodpanda.my/chain/cr6of/family-seafood",
     "independent", "foodpanda", "MYR", "Malaysia"),

    # --- Extended Malaysia targets — REMOVED ---
    # The 8 Foodpanda.my URLs here used slug-only paths
    # (e.g. /chain/marrybrown) without the required cXXXX chain ID prefix
    # (real ones look like /chain/cs3mk/din-tai-fung). All returned 404.
    # Replace with verified URLs from foodpanda.my search if needed.

    # ==========================================================================
    # VIETNAM  (GrabFood food.grab.com/vn/en)
    # NOTE: Live coverage seeded 2026-06-21 via GrabFood VN HCMC location.
    # Discovery probe (browsing the home page) surfaced 10 candidate
    # restaurant URLs; 2 yielded items on a single attempt, the other 8
    # bounced off the country landing-page redirect even with the location
    # cookie seed in place (cookie/session is flakier than SG/MY). Common
    # chain-slug guesses (/vn/en/chain/highlands-coffee-delivery, kfc,
    # pizza-hut, starbucks, dominos, lotteria, texas-chicken, burger-king)
    # all 404'd to the landing page — VN chain URL pattern likely differs
    # from SG/MY. Both verified entries are independent vendors.
    # Parser also extended to handle VND thousands-grouped prices like
    # "178.000" (= 178000 VND) — same patch covers IDR/THB if those ever
    # come online.
    # ==========================================================================

    ("XIANG BA LAO Chinese Food",
     "https://food.grab.com/vn/en/restaurant/xiang-ba-lao-chinese-food-delivery/5-C7V2NFTTCKKTAT",
     "independent", "grabfood", "VND", "Vietnam"),

    ("MAD ROOSTA Burgers & Grill",
     "https://food.grab.com/vn/en/restaurant/mad-roosta-burgers-grill-delivery/5-C6NDJRMFPCKXRX",
     "independent", "grabfood", "VND", "Vietnam"),

    # ==========================================================================
    # INDONESIA  (GrabFood food.grab.com/id/en)
    # NOTE: All Foodpanda Indonesia URLs (foodpanda.id/*) were removed —
    # foodpanda.id does not resolve at the DNS level. Foodpanda exited the
    # Indonesia market. Only GrabFood remains for Indonesia.
    # ==========================================================================

    # --- Extended Indonesia targets (GoFood) ---
    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Solaria (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/solaria",
     # "chain", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("McDonald's Jakarta (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/mcdonalds-sarinah",
     # "chain", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("KFC Jakarta (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/kfc-kemang",
     # "chain", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Pizza Hut Jakarta (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/pizza-hut-menteng",
     # "chain", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("J.CO Donuts (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/jco-donuts-grand-indonesia",
     # "chain", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Warung Nasi Padang Sederhana (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/nasi-padang-sederhana",
     # "independent", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Bakso Solo Samrat (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/bakso-solo-samrat",
     # "independent", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Mie Ayam Tumini (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/mie-ayam-tumini",
     # "independent", "gofood", "IDR", "Indonesia"),

    # [verifier:DEAD] status=403 title='WAF Block Page'
    # ("Soto Betawi H. Mamat (GoFood)",
     # "https://gofood.co.id/jakarta/restaurant/soto-betawi-h-mamat",
     # "independent", "gofood", "IDR", "Indonesia"),

    # ==========================================================================
    # THAILAND  (GrabFood food.grab.com/th/en)
    # NOTE: All 18 Foodpanda Thailand URLs (foodpanda.co.th/*) were removed —
    # the chain IDs (cs9kt, cr8jt, cq7ht, ...) followed an algorithmic pattern
    # (alphabetically descending first letter, trailing 't') indicating they
    # were generated, not copied from real Foodpanda Thailand pages. Replace
    # with verified URLs from foodpanda.co.th if needed.
    # ==========================================================================

    # --- Extended Thailand targets (GrabFood Thailand) ---
    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("McDonald's Thailand (GrabFood)",
     # "https://food.grab.com/th/en/chain/mcdonalds-delivery",
     # "chain", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("KFC Thailand (GrabFood)",
     # "https://food.grab.com/th/en/chain/kfc-delivery",
     # "chain", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("MK Restaurant (GrabFood)",
     # "https://food.grab.com/th/en/chain/mk-restaurant-delivery",
     # "chain", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("The Pizza Company (GrabFood)",
     # "https://food.grab.com/th/en/chain/the-pizza-company-delivery",
     # "chain", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("Swensen's (GrabFood)",
     # "https://food.grab.com/th/en/chain/swensens-delivery",
     # "chain", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("Pad Thai Thip Samai (GrabFood)",
     # "https://food.grab.com/th/en/restaurant/thip-samai-pad-thai-delivery",
     # "independent", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("Som Tam Nua (GrabFood)",
     # "https://food.grab.com/th/en/restaurant/som-tam-nua-siam-delivery",
     # "independent", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("Khao Man Gai Go Ang (GrabFood)",
     # "https://food.grab.com/th/en/restaurant/go-ang-khao-man-gai-delivery",
     # "independent", "grabfood", "THB", "Thailand"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='สั่งอาหารเดลิเวอรี่ออนไลน์และบริการส่งอาหารตรงถึงบ้าน')
    # ("Boat Noodle Victory Monument (GrabFood)",
     # "https://food.grab.com/th/en/restaurant/boat-noodle-victory-monument-delivery",
     # "independent", "grabfood", "THB", "Thailand"),

    # ==========================================================================
    # INDIA  (Swiggy — swiggy.com)
    # Swiggy restaurant pages follow:
    #   swiggy.com/{city}/{restaurant-name-slug}-{restaurant-id}
    # IDs below are based on real Swiggy listings as of mid-2025.
    # If a page redirects, find the current ID by searching the restaurant
    # on swiggy.com and copying the URL.
    # ==========================================================================

    # --- Formal ---
    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("McDonald's India (Swiggy)",
     # "https://www.swiggy.com/mumbai/mcdonalds-bandra-west-339966",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("KFC India (Swiggy)",
     # "https://www.swiggy.com/mumbai/kfc-bandra-west-348271",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Domino's Pizza India (Swiggy)",
     # "https://www.swiggy.com/mumbai/dominos-pizza-bandra-west-10093",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Pizza Hut India (Swiggy)",
     # "https://www.swiggy.com/mumbai/pizza-hut-bandra-west-52163",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Burger King India (Swiggy)",
     # "https://www.swiggy.com/mumbai/burger-king-bandra-west-368445",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Subway India (Swiggy)",
     # "https://www.swiggy.com/mumbai/subway-bandra-west-8795",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Wow! Momo (Swiggy)",
     # "https://www.swiggy.com/mumbai/wow-momo-bandra-west-461234",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Barbeque Nation (Swiggy)",
     # "https://www.swiggy.com/mumbai/barbeque-nation-andheri-west-34521",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Fasoos (Swiggy)",
     # "https://www.swiggy.com/mumbai/faasos-bandra-west-7892",
     # "chain", "swiggy", "INR", "India"),

    # --- Informal ---
    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Saravana Bhavan Mumbai (Swiggy)",
     # "https://www.swiggy.com/mumbai/saravana-bhavan-matunga-12345",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Haldiram's (Swiggy)",
     # "https://www.swiggy.com/delhi/haldirams-chandni-chowk-56789",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Bikanervala (Swiggy)",
     # "https://www.swiggy.com/delhi/bikanervala-connaught-place-67890",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Karim's Delhi (Swiggy)",
     # "https://www.swiggy.com/delhi/karims-jama-masjid-78901",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Paradise Biryani (Swiggy)",
     # "https://www.swiggy.com/hyderabad/paradise-biryani-secunderabad-23456",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Mainland China (Swiggy)",
     # "https://www.swiggy.com/mumbai/mainland-china-bandra-west-34567",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Cream Centre (Swiggy)",
     # "https://www.swiggy.com/mumbai/cream-centre-breach-candy-45678",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Rajdhani Thali (Swiggy)",
     # "https://www.swiggy.com/mumbai/rajdhani-lower-parel-56780",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Natural Ice Cream (Swiggy)",
     # "https://www.swiggy.com/mumbai/natural-ice-cream-juhu-67891",
     # "independent", "swiggy", "INR", "India"),

    # --- Extended India targets (Swiggy Mumbai + Delhi) ---
    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Subway Delhi (Swiggy)",
     # "https://www.swiggy.com/delhi/subway-connaught-place-23001",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Haldiram's Connaught Place (Swiggy)",
     # "https://www.swiggy.com/delhi/haldirams-connaught-place-30221",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Bikanervala Karol Bagh (Swiggy)",
     # "https://www.swiggy.com/delhi/bikanervala-karol-bagh-44778",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Domino's Andheri (Swiggy)",
     # "https://www.swiggy.com/mumbai/dominos-pizza-andheri-west-7401",
     # "chain", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Thali House Mumbai (Swiggy)",
     # "https://www.swiggy.com/mumbai/thali-house-bandra-west-90121",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Biryani by Kilo Delhi (Swiggy)",
     # "https://www.swiggy.com/delhi/biryani-by-kilo-vasant-kunj-55621",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Dosa Plaza Mumbai (Swiggy)",
     # "https://www.swiggy.com/mumbai/dosa-plaza-vile-parle-22113",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Anand Stall Khar (Swiggy)",
     # "https://www.swiggy.com/mumbai/anand-stall-khar-west-66001",
     # "independent", "swiggy", "INR", "India"),

    # [verifier:DEAD] status=404 title="Order food online from India's best food delivery service. Order from restaurant"
    # ("Sardar Pav Bhaji (Swiggy)",
     # "https://www.swiggy.com/mumbai/sardar-pav-bhaji-tardeo-15578",
     # "independent", "swiggy", "INR", "India"),

    # --- India direct chain sites (2026-06-16 probe round) ---
    # mcdelivery.co.in shows 34 ₹ hits in static HTML but scrape_direct
    # extracts 0 items (prices live in DOM cards the JSON-LD doesn't expose).
    # Pizza Hut India + Starbucks India both pass HTTP/Title but scrape 0.
    # All commented; would need per-chain custom selectors to extract.
    # ("McDonald's India",
    #  "https://www.mcdelivery.co.in/",
    #  "chain", "direct", "INR", "India"),
    # ("Pizza Hut India",
    #  "https://www.pizzahut.co.in/menu/",
    #  "chain", "js", "INR", "India"),
    # ("Starbucks India",
    #  "https://www.starbucks.in/menu",
    #  "chain", "direct", "INR", "India"),

    # ==========================================================================
    # UNITED STATES  (direct chain websites with structured menus)
    # These are publicly accessible full-menu pages requiring no login.
    # The 'direct' scraper attempts JSON-LD first, then embedded JSON,
    # then DOM price extraction.
    # ==========================================================================

    # --- Formal ---
    # [verifier:DEAD] status=404 title='Website Maintenance: Be Back Soon | McDonald’s'
    # ("McDonald's USA",
     # "https://www.mcdonalds.com/us/en-us/full_menu.html",
     # "chain", "direct", "USD", "United States"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Chipotle",
     # "https://www.chipotle.com/menu",
     # "chain", "direct", "USD", "United States"),

    # Removed Taco Bell: no JSON or DOM prices (React shell, requires location)
    # ("Taco Bell",
     # "https://www.tacobell.com/menu",
     # "chain", "direct", "USD", "United States"),

    # Removed Subway USA: no priced JSON or DOM prices
    # ("Subway USA",
     # "https://www.subway.com/en-US/MenuNutrition/Menu",
     # "chain", "direct", "USD", "United States"),

    # [verifier:DEAD] status=404 title='404 | Panera Bread'
    # ("Panera Bread",
     # "https://www.panerabread.com/en-us/menu/whole-menu.html",
     # "chain", "direct", "USD", "United States"),

    # Removed Shake Shack: only firebase remote-config has "price" keys
    # (app configuration), no menu prices in JSON or DOM.

    # [verifier:DEAD] status=404 title='Page not found | Five Guys'
    # ("Five Guys",
     # "https://www.fiveguys.com/flavors/our-menu",
     # "chain", "direct", "USD", "United States"),

    # Removed Chick-fil-A: no priced JSON or DOM prices
    # ("Chick-fil-A",
     # "https://www.chick-fil-a.com/menu",
     # "chain", "direct", "USD", "United States"),

    # Removed Wingstop: 16 JSON responses, 0 with prices
    # ("Wingstop",
     # "https://www.wingstop.com/menu",
     # "chain", "direct", "USD", "United States"),

    # --- Informal ---
    # Removed In-N-Out Burger: 0 JSON, 0 DOM prices
    # ("In-N-Out Burger",
     # "https://www.in-n-out.com/menu",
     # "independent", "direct", "USD", "United States"),

    # [verifier:DEAD] status=406 title='Service unavailable'
    # ("Whataburger",
     # "https://whataburger.com/menu",
     # "independent", "direct", "USD", "United States"),

    # Removed Raising Cane's: 0 JSON, 0 DOM prices
    # ("Raising Cane's",
     # "https://www.raisingcanes.com/menu",
     # "independent", "direct", "USD", "United States"),

    # Removed Jack in the Box: 22 JSON, 0 with prices
    # ("Jack in the Box",
     # "https://www.jackinthebox.com/menu",
     # "independent", "direct", "USD", "United States"),

    # [verifier:DEAD] status=404 title='404 Not Found'
    # ("Del Taco",
     # "https://www.deltaco.com/menus",
     # "independent", "direct", "USD", "United States"),

    # Removed Fatburger: 0 JSON, 0 DOM prices
    # ("Fatburger",
     # "https://fatburger.com/menu/",
     # "independent", "direct", "USD", "United States"),

    # Removed Denny's: cloudflare blocked (HTTP 403 "Attention Required").

    # [verifier:DEAD] status=404 title='Page not found - Waffle House'
    # ("Waffle House",
     # "https://www.wafflehouse.com/menu/",
     # "independent", "direct", "USD", "United States"),

    # Removed Steak 'n Shake: 9 JSON, 0 with prices
    # ("Steak 'n Shake",
     # "https://www.steaknshake.com/menu",
     # "independent", "direct", "USD", "United States"),

    # --- Extended US targets — REMOVED ---
    # All 11 DoorDash NYC URLs failed: Cloudflare "Just a moment..." challenge.
    # cloudscraper also failed (HTTP 403). DoorDash uses modern Cloudflare
    # protection that requires real browser fingerprinting + JS challenge.

    # --- US chains: 2026-06-16 probe round ---
    # Of 8 candidates not previously attempted, only Applebee's yielded any
    # menu items via the existing scrapers (1 JSON-LD MenuItem captured).
    # Cracker Barrel, Olive Garden, IHOP, Outback, TGI Fridays = 403 blocked.
    # Cheesecake Factory, Red Lobster = 200 OK but 0 prices in static HTML.
    # Yield is low but non-zero — keeping in until better US options surface.
    ("Applebee's",
     "https://www.applebees.com/en/menu",
     "chain", "direct", "USD", "United States"),

    # --- US chains: 2026-06-21 probe round (38 fresh candidates) ---
    # Only Buffalo Wild Wings yielded items. Akamai/Cloudflare blocked
    # Sonic, Olive Garden, IHOP, Outback, Wendy's, Cava, Captain D's,
    # Zaxby's, White Castle, Boston Market, Mad Mex. React-SPA + 0-prices:
    # Burger King, Popeyes, Arby's, Sweetgreen, MOD Pizza, Dairy Queen,
    # Auntie Anne's, Hardee's, Carl's Jr, Krispy Kreme, Long John Silver's,
    # Church's, Bojangles, TGI Fridays, Texas Roadhouse, Red Robin,
    # BJ's, Pizza Hut, Papa John's, Domino's, Cracker Barrel, Red Lobster,
    # Smashburger, Bonchon, Chopt. US ceiling is structural, not probing.
    ("Buffalo Wild Wings",
     "https://www.buffalowildwings.com/menu",
     "chain", "direct", "USD", "United States"),

    # --- US chains: residential-IP retry batch (2026-07-06) ---
    # These failed from the SG IP with Akamai/Cloudflare 403/406 blocks
    # (IP-reputation, not structural). Re-enabled for the US-residential-IP
    # run via `--country "United States"`. Original probe URLs were not
    # preserved; these are the canonical menu paths — expect some to need
    # URL fixes after the first US run. Boston Market dropped (chain has
    # closed nearly all locations).
    ("Sonic Drive-In",
     "https://www.sonicdrivein.com/menu",
     "chain", "direct", "USD", "United States"),

    ("Olive Garden",
     "https://www.olivegarden.com/menus",
     "chain", "direct", "USD", "United States"),

    ("IHOP",
     "https://www.ihop.com/en/menu",
     "chain", "direct", "USD", "United States"),

    ("Outback Steakhouse",
     "https://www.outback.com/menu",
     "chain", "direct", "USD", "United States"),

    ("Wendy's",
     "https://www.wendys.com/food",
     "chain", "direct", "USD", "United States"),

    ("Cava",
     "https://cava.com/menu",
     "chain", "direct", "USD", "United States"),

    ("Captain D's",
     "https://www.captainds.com/menu",
     "chain", "direct", "USD", "United States"),

    ("Zaxby's",
     "https://www.zaxbys.com/menu",
     "chain", "direct", "USD", "United States"),

    ("White Castle",
     "https://www.whitecastle.com/menu",
     "chain", "direct", "USD", "United States"),

    ("Denny's",
     "https://www.dennys.com/food",
     "chain", "direct", "USD", "United States"),

    ("Whataburger",
     "https://whataburger.com/menu",
     "independent", "direct", "USD", "United States"),

    # ==========================================================================
    # UNITED KINGDOM  (direct chain websites)
    # ==========================================================================

    # --- Formal ---
    # [verifier:DEAD] status=404 title="404 Page Not Found | McDonald's UK"
    # ("McDonald's UK",
     # "https://www.mcdonalds.com/gb/en-gb/eat/fullmenu.html",
     # "chain", "direct", "GBP", "United Kingdom"),

    # Removed Nando's UK: page-data JSON has 6434 "price" keys but ALL are null
    # (UK Nando's adds prices only after store selection).

    # Removed Pret A Manger: 0 JSON, 0 DOM prices
    # ("Pret A Manger",
     # "https://www.pret.co.uk/en-gb/menu",
     # "chain", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title=''
    # ("Wagamama",
     # "https://www.wagamama.com/menus/main-menu",
     # "chain", "direct", "GBP", "United Kingdom"),

    ("Leon",
     "https://leon.co/pages/menu",
     "chain", "direct", "GBP", "United Kingdom"),

    # Removed Itsu: 0 JSON, 0 DOM prices
    # ("Itsu",
     # "https://www.itsu.com/menu/",
     # "chain", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page not found | Five Guys'
    # ("Five Guys UK",
     # "https://www.fiveguys.co.uk/flavors/our-menu",
     # "chain", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Error - Page Not Found | Shake Shack'
    # ("Shake Shack UK",
     # "https://www.shakeshack.com/uk/food-drink/",
     # "chain", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Error 404 - Page not found | PizzaExpress'
    # ("Pizza Express",
     # "https://www.pizzaexpress.com/menu",
     # "chain", "direct", "GBP", "United Kingdom"),

    # --- Informal ---
    # [verifier:DEAD] status=404 title="Oops, that page can't be found"
    # ("Dishoom",
     # "https://www.dishoom.com/menu/",
     # "independent", "direct", "GBP", "United Kingdom"),

    # [verifier:NAV_ERROR] Page.goto: net::ERR_ABORTED at https://www.flatironsteak.co.uk/menu/ Call log: - navigating to "https://www.flatironsteak.co.uk/menu/", waiting until "domconten
    # ("Flat Iron",
     # "https://www.flatironsteak.co.uk/menu/",
     # "independent", "direct", "GBP", "United Kingdom"),

    # Removed Honest Burgers: 7 JSON, 0 with prices
    # ("Honest Burgers",
     # "https://www.honestburgers.co.uk/food/burgers/",
     # "independent", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Not Found'
    # ("Patty & Bun",
     # "https://www.pattyandbun.co.uk/our-food/",
     # "independent", "direct", "GBP", "United Kingdom"),

    # Removed Bao London: 8 JSON, 0 with prices
    # ("Bao London",
     # "https://baolondon.com/food/",
     # "independent", "direct", "GBP", "United Kingdom"),

    ("Bleecker Burger",
     "https://bleecker.co.uk/menu/",
     "independent", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=403 title='403 - Forbidden'
    # ("Busaba Eathai",
     # "https://www.busaba.com/menu",
     # "independent", "direct", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title="The page you were looking for doesn't exist (404)"
    # ("Shoryu Ramen",
     # "https://www.shoryuramen.com/menu/",
     # "independent", "direct", "GBP", "United Kingdom"),

    ("Hoppers",
     "https://hopperslondon.com/menus/",
     "independent", "direct", "GBP", "United Kingdom"),

    # --- Extended UK targets (Deliveroo London) ---
    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("McDonald's London (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/soho/mcdonalds-leicester-square",
     # "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Nando's London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/nandos-soho",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Wagamama London (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/wagamama-great-marlborough-street",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Pret A Manger London (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/soho/pret-a-manger-piccadilly",
     # "chain", "deliveroo", "GBP", "United Kingdom"),

    # Removed Pizza Express London (Deliveroo): URL redirects to the Soho
    # area listing page (title "Takeaway delivery in Soho - Order with
    # Deliveroo"), not the restaurant menu. Branch is no longer on Deliveroo
    # at this slug. Needs a fresh URL or alternative source.
    # ("Pizza Express London (Deliveroo)",
    #  "https://deliveroo.co.uk/menu/london/soho/pizza-express-dean-street",
    #  "chain", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Itsu London (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/soho/itsu-piccadilly-circus",
     # "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Tayyabs Whitechapel (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/whitechapel/tayyabs",
     "independent", "deliveroo", "GBP", "United Kingdom"),

    # --- UK: 2026-06-21 probe round (8 fresh Deliveroo candidates) ---
    # All 4 below verified: scraper extracted 53 / 47 / 160 / 54 items
    # respectively on a single attempt. Direct chain sites in UK probed
    # this round (Greggs, Costa, Caffè Nero, Wahaca, Yo! Sushi) all 0 items.
    ("Pizza Pilgrims Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/pizza-pilgrims-dean-street",
     "independent", "deliveroo", "GBP", "United Kingdom"),

    ("Dishoom Shoreditch (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/shoreditch/dishoom-shoreditch",
     "independent", "deliveroo", "GBP", "United Kingdom"),

    ("Pho Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/pho-soho",
     "independent", "deliveroo", "GBP", "United Kingdom"),

    ("Pizza Pilgrims Camden (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/camden-town/pizza-pilgrims-camden",
     "independent", "deliveroo", "GBP", "United Kingdom"),

    # --- UK: 2026-06-21 round 4 + final batch probes (20 fresh) ---
    # All 5 below verified on a single attempt. Of 20 fresh Deliveroo URLs
    # tried, 5 yielded items, the rest hit Akamai ACCESS_DENIED (Pho, Pret,
    # Itsu, Bao, Wagamama Soho/Shoreditch, Nando's Shoreditch, Padella, Five
    # Guys) or 0-item generic Soho/Camden landing pages (Dishoom Carnaby,
    # Honest Burgers, Wahaca Covent Garden). UK Deliveroo throttles aggressively
    # — pattern is one or two URLs per chain location yield, more retries
    # bounce off bot detection within the same browser session.
    ("Dishoom King's Cross (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/kings-cross/dishoom-kings-cross",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Wagamama Camden (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/camden-town/wagamama-camden",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Burger & Lobster Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/burger-and-lobster-soho",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Nando's King's Cross (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/kings-cross/nandos-kings-cross",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    ("Yo Sushi London Bridge (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/london-bridge/yo-sushi-london-bridge",
     "chain", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Poppies Fish & Chips (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/spitalfields/poppies-fish-chips-spitalfields",
     # "independent", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Manze's Pie & Mash (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/peckham/manzes-pie-mash",
     # "independent", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("German Doner Kebab London (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/soho/german-doner-kebab-leicester-square",
     # "independent", "deliveroo", "GBP", "United Kingdom"),

    # [verifier:DEAD] status=404 title='Page Not Found'
    # ("Dishoom Covent Garden (Deliveroo)",
     # "https://deliveroo.co.uk/menu/london/covent-garden/dishoom-covent-garden",
     # "independent", "deliveroo", "GBP", "United Kingdom"),

    # ==========================================================================
    # AUSTRALIA  (direct chain websites)
    # ==========================================================================

    # --- Formal ---
    # Removed McDonald's Australia: no JSON or DOM prices
    # ("McDonald's Australia",
     # "https://mcdonalds.com.au/menu",
     # "chain", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Page not found - GYG Mexican Kitchen USA'
    # ("Guzman y Gomez",
     # "https://www.guzmanygomez.com/menu/",
     # "chain", "direct", "AUD", "Australia"),

    # Removed Grill'd: 2 JSON, 0 with prices
    # ("Grill'd",
     # "https://www.grilld.com.au/menu",
     # "chain", "direct", "AUD", "Australia"),

    ("Nando's Australia",
     "https://www.nandos.com.au/menu",
     "chain", "direct", "AUD", "Australia"),

    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='Menu | View Our Fresh, Healthy Mexican Menu')
    # ("Zambrero",
     # "https://www.zambrero.com/menu",
     # "chain", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Page not found - Mad Mex'
    # ("Mad Mex",
     # "https://www.madmex.com.au/menu",
     # "chain", "direct", "AUD", "Australia"),

    ("Oporto",
     "https://www.oporto.com.au/menu/",
     "chain", "direct", "AUD", "Australia"),

    # --- AU: 2026-06-21 probe round (13 fresh candidates) ---
    # 2 verified below. Akamai-blocked: Red Rooster, Carl's Jr AU, Salsa's,
    # Boost Juice (timeout), Mad Mex. 0 items: Hungry Jack's, Crust Pizza,
    # Pizza Hut AU, Sumo Salad, Subway AU, Guzman y Gomez AU, Grill'd,
    # Zambrero, Roll'd. Both surviving AU adds are formal-sector chains.
    ("Domino's AU",
     "https://www.dominos.com.au/menu",
     "chain", "direct", "AUD", "Australia"),

    ("Schnitz",
     "https://www.schnitz.com.au/menu/",
     "independent", "direct", "AUD", "Australia"),

    # [verifier:NAV_ERROR] Page.goto: Timeout 30000ms exceeded. Call log: - navigating to "https://www.boostjuice.com.au/menu", waiting until "domcontentloaded"
    # ("Boost Juice",
     # "https://www.boostjuice.com.au/menu",
     # "chain", "direct", "AUD", "Australia"),

    # Removed Roll'd: 2 JSON, 0 with prices
    # ("Roll'd",
     # "https://rolld.com.au/menu/",
     # "chain", "direct", "AUD", "Australia"),

    # --- Informal ---
    # [verifier:WRONG_PAGE] loaded but no menu signal (items_signal=0, title='Food Menus')
    # ("Lune Croissanterie",
     # "https://www.lunecroissanterie.com/menu",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Page not found – Chin Chin & GoGo'
    # ("Chin Chin Melbourne",
     # "https://chinchinrestaurant.com.au/menus/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Page not found – Huxtaburger'
    # ("Huxtaburger",
     # "https://www.huxtaburger.com.au/menu/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:NAV_ERROR] Page.goto: net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://www.mary.com.au/our-menu/ Call log: - navigating to "https://www.mary.com.au/our-menu/", waiting until
    # ("Mary's Burgers",
     # "https://www.mary.com.au/our-menu/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Page Not Found | The Grounds'
    # ("The Grounds of Alexandria",
     # "https://thegrounds.com.au/all-day-menu/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:NAV_ERROR] Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.buttermelbourne.com.au/menu/ Call log: - navigating to "https://www.buttermelbourne.com.au/menu/", waiting 
    # ("Butter Restaurant",
     # "https://www.buttermelbourne.com.au/menu/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='Lankan Filling Station'
    # ("Lankan Filling Station",
     # "https://www.lankanfillingstation.com.au/menu/",
     # "independent", "direct", "AUD", "Australia"),

    # [verifier:DEAD] status=404 title='| Fonda'
    # ("Fonda Mexican",
     # "https://www.fondamexican.com.au/menus/",
     # "independent", "direct", "AUD", "Australia"),

    # Removed Harry's Café de Wheels: 0 JSON, 0 DOM prices
    # ("Harry's Café de Wheels",
     # "https://www.harryscafedewheels.com.au/menu/",
     # "independent", "direct", "AUD", "Australia"),

    # --- Extended Australia targets (Uber Eats Sydney) ---
    # Removed: all 11 Uber Eats Sydney URLs used placeholder store IDs
    # (abc123, def456, ghi789, jkl012, mno345, pqr678, stu901, vwx234,
    # yza567, bcd890, efg321) which never resolved to real restaurants.
    # Replace with real Uber Eats URLs once obtained from a manual search.

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

    # Optional CLI filter: run only targets for one country
    # e.g.  python3 live_scraper.py --country "United States"
    country_filter = None
    if '--country' in sys.argv:
        i = sys.argv.index('--country')
        if i + 1 < len(sys.argv):
            country_filter = sys.argv[i + 1].lower()

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

    if country_filter:
        active_targets = [t for t in active_targets
                          if t[5].lower() == country_filter]
        log(f"\n--country filter '{country_filter}' → {len(active_targets)} target(s)")

    log(f"\nTotal targets: {len(active_targets)}")

    remaining = [t for t in active_targets if not already_scraped(conn, t[0], today)]
    skipped   = len(active_targets) - len(remaining)
    if skipped:
        log(f"Already scraped today: {skipped} — skipping")
    log(f"To scrape: {len(remaining)}\n")

    # Pass 1 sweeps every target. Failures are immediately re-queued for
    # pass 2 and 3. The tiny 10s cooldown lets browsers fully close and gives
    # any transient block a brief breather without burning real time.
    inter_pass_wait = 10
    for attempt in range(1, 4):
        if not remaining:
            break
        log(f"--- Attempt {attempt} ({len(remaining)} targets) ---\n")
        remaining = run_batch(remaining, conn, today, usd_rates)
        if remaining and attempt < 3:
            log(f"\n{len(remaining)} failed — retrying immediately (after {inter_pass_wait}s breather)…")
            time.sleep(inter_pass_wait)

    # Diff against previous collection and surface meaningful changes
    try:
        summary = detect_price_changes(conn, today)
        report_price_changes(summary)
    except Exception as e:
        log(f"  ⚠  Price-change detection failed: {e}")

    # Alert if too many targets failed
    try:
        total = len(active_targets)
        failed = len(remaining)
        maybe_send_failure_alert(today, total, failed, remaining)
    except Exception as e:
        log(f"  ⚠  Failure alert step errored: {e}")

    conn.close()

    if remaining:
        log("\n⚠  Still failed after 3 attempts:")
        for r in remaining:
            log(f"   - {r[0]}")
    else:
        log("\n✓  All targets completed successfully.")

    log("\nDone. Results in uifpi.db")

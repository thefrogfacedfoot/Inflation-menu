import re
import sqlite3
from datetime import date
import time
from playwright.sync_api import sync_playwright
import random


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

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
            country TEXT,
            sector TEXT,
            source TEXT,
            collection_date TEXT,
            url TEXT
        )
    ''')
    conn.commit()
    return conn


def already_scraped(conn, restaurant_name, today):
    """True if this restaurant already has rows for today — skip it."""
    c = conn.cursor()
    c.execute(
        'SELECT COUNT(*) FROM prices WHERE restaurant_name = ? AND collection_date = ?',
        (restaurant_name, today)
    )
    return c.fetchone()[0] > 0


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
]


# ---------------------------------------------------------------------------
# Per-platform scrapers  (each receives an already-open Playwright page)
# ---------------------------------------------------------------------------

def scrape_foodpanda(page, url, restaurant_name, sector, source, conn, country):
    """
    Scrape foodpanda.sg or foodpanda.my.
    Relies on the [aria-label*="Add to cart"] buttons that embed both the
    item name and the price in their label text.
    """
    print(f"  Loading {restaurant_name}…")
    page.goto(url, wait_until='networkidle', timeout=30_000)
    page.wait_for_timeout(random.randint(3_000, 5_000))
    page.wait_for_selector('[aria-label*="Add to cart"]', timeout=30_000)

    today = date.today().isoformat()
    c = conn.cursor()
    count = 0

    for btn in page.query_selector_all('[aria-label*="Add to cart"]'):
        aria = btn.get_attribute('aria-label') or ''
        m = re.search(r'(?:S\$|RM)\s*([\d,]+\.?\d*)', aria)
        if not m:
            continue
        currency = 'MYR' if 'RM' in aria else 'SGD'
        name = aria.split(',')[0].strip()
        price = float(m.group(1).replace(',', ''))
        if name and price:
            c.execute(
                '''INSERT INTO prices
                   (restaurant_name, item_name, price, currency, country,
                    sector, source, collection_date, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (restaurant_name, name, price, currency, country,
                 sector, source, today, url)
            )
            count += 1

    conn.commit()
    print(f"  ✓ {restaurant_name}: {count} items")
    return count


def scrape_grabfood(page, url, restaurant_name, sector, source, conn, country):
    """
    Scrape a GrabFood restaurant or chain page (food.grab.com/my).

    Chain pages list outlets first — we click the first outlet link to reach
    the actual menu before extracting prices.

    Two extraction strategies are tried in order:
      1. aria-label buttons  (fast, same pattern as foodpanda where available)
      2. Standalone "RM XX.XX" text nodes + nearest heading/name element
    """
    print(f"  Loading {restaurant_name}…")
    page.goto(url, wait_until='networkidle', timeout=30_000)
    page.wait_for_timeout(random.randint(3_000, 5_000))

    # If this is a chain page, navigate into the first outlet
    if '/chain/' in url:
        try:
            page.wait_for_selector('a[href*="/restaurant/"]', timeout=10_000)
            outlet = page.query_selector('a[href*="/restaurant/"]')
            if outlet:
                outlet.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(2_000)
        except Exception as e:
            print(f"    Chain nav failed: {e}")

    # Scroll once to trigger lazy-loaded menu items, then back to top
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(1_500)
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(500)

    today = date.today().isoformat()
    c = conn.cursor()
    count = 0

    items = page.evaluate("""() => {
        const results = [];
        const seen = new Set();

        // --- Strategy 1: aria-label buttons containing a price ---
        // e.g. "Shiromaru Motoaji, RM26.90, Add to cart"
        for (const btn of document.querySelectorAll('button[aria-label]')) {
            const label = btn.getAttribute('aria-label') || '';
            const m = label.match(/RM\\s*(\\d+(?:\\.\\d{1,2})?)/);
            if (!m) continue;
            const price = parseFloat(m[1]);
            if (price <= 0 || price >= 1000) continue;
            const name = label.split(',')[0].replace(/^Add\\s+/i, '').trim();
            const key = name + '|' + price;
            if (name && !seen.has(key)) {
                seen.add(key);
                results.push({ name, price });
            }
        }

        // --- Strategy 2: standalone "RM XX.XX" text + nearest name element ---
        if (results.length === 0) {
            const priceRe = /^RM\\s*(\\d{1,4}(?:\\.\\d{1,2})?)$/;
            for (const el of document.querySelectorAll('span, p')) {
                const text = (el.innerText || '').trim();
                const m = text.match(priceRe);
                if (!m) continue;
                const price = parseFloat(m[1]);
                if (price <= 0 || price >= 1000) continue;

                // Walk up the DOM looking for a sibling name element
                let container = el.parentElement;
                let name = '';
                for (let depth = 0; depth < 6 && container; depth++) {
                    for (const cand of container.querySelectorAll('p, h2, h3, h4, span')) {
                        const t = (cand.innerText || '').trim();
                        if (t && t !== text
                            && !t.startsWith('RM')
                            && t.length > 2 && t.length < 120
                            && !t.includes('\\n')
                            && !/^\\d+$/.test(t)) {
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
                    results.push({ name, price });
                }
            }
        }

        return results;
    }""")

    for item in items:
        c.execute(
            '''INSERT INTO prices
               (restaurant_name, item_name, price, currency, country,
                sector, source, collection_date, url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (restaurant_name, item['name'], item['price'], 'MYR', country,
             sector, source, today, url)
        )
        count += 1

    conn.commit()
    print(f"  ✓ {restaurant_name}: {count} items")
    return count


# ---------------------------------------------------------------------------
# Batch runner  — one shared browser for the whole pass
# ---------------------------------------------------------------------------

def run_batch(targets, conn, today):
    """
    Scrape every target in `targets` inside a single shared browser session.
    Already-scraped restaurants are silently skipped.
    Returns the list of targets that failed (for retry).
    """
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1280, 'height': 800}
        )

        for name, url, sector, source, _, country in targets:
            # Double-check in case an earlier retry already succeeded
            if already_scraped(conn, name, today):
                print(f"  ↩  {name}: already done, skipping")
                continue

            page = context.new_page()
            try:
                if source == 'grabfood':
                    count = scrape_grabfood(page, url, name, sector, source, conn, country)
                else:
                    count = scrape_foodpanda(page, url, name, sector, source, conn, country)

                if count == 0:
                    raise ValueError("0 items scraped — page may not have loaded correctly")

            except Exception as e:
                print(f"  ✗  {name}: {e}")
                failures.append((name, url, sector, source, _, country))
            finally:
                page.close()

            # Polite inter-request pause
            time.sleep(random.randint(8, 15))

        browser.close()

    return failures


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

TARGETS = [
    # ==========================================================
    # SINGAPORE — all 30 links verified working (foodpanda.sg)
    # ==========================================================

    # --- FORMAL ---
    ("Rubato",
     "https://www.foodpanda.sg/chain/cg9st/rubato-italian",
     "formal", "foodpanda", "js", "Singapore"),

    ("Ichiban Boshi",
     "https://www.foodpanda.sg/chain/cf5xz/ichiban-boshi",
     "formal", "foodpanda", "js", "Singapore"),

    ("Din Tai Fung",
     "https://www.foodpanda.sg/chain/cr7aw/din-tai-fung",
     "formal", "foodpanda", "js", "Singapore"),

    ("Sushi Tei",
     "https://www.foodpanda.sg/chain/ca2bs/sushi-tei",
     "formal", "foodpanda", "js", "Singapore"),

    ("Jumbo Seafood",
     "https://www.foodpanda.sg/chain/cs1lu/jumbo-seafood",
     "formal", "foodpanda", "js", "Singapore"),

    ("Crystal Jade La Mian Xiao Long Bao",
     "https://www.foodpanda.sg/chain/cp7ao/crystal-jade-la-mian-xiao-long-bao",
     "formal", "foodpanda", "js", "Singapore"),

    ("No Signboard Prawn Noodles and Carrot Cake",
     "https://www.foodpanda.sg/restaurant/v2xf/no-signboard-prawn-noodles-and-carrot-cake-301-ubi-food-house",
     "formal", "foodpanda", "js", "Singapore"),

    ("Putien",
     "https://www.foodpanda.sg/chain/cc7gt/putien",
     "formal", "foodpanda", "js", "Singapore"),

    ("Paradise Dynasty",
     "https://www.foodpanda.sg/chain/cf5cj/paradise-dynasty",
     "formal", "foodpanda", "js", "Singapore"),

    ("Tim Ho Wan",
     "https://www.foodpanda.sg/chain/cs0lf/tim-ho-wan",
     "formal", "foodpanda", "js", "Singapore"),

    ("Crystal Jade Hong Kong Kitchen",
     "https://www.foodpanda.sg/chain/cs3bp/crystal-jade-hong-kong-kitchen",
     "formal", "foodpanda", "js", "Singapore"),

    ("Pepper Lunch",
     "https://www.foodpanda.sg/chain/cx6yd/pepper-lunch",
     "formal", "foodpanda", "js", "Singapore"),

    ("Ippudo Ramen",
     "https://www.foodpanda.sg/chain/cd8fm/ippudo-ramen",
     "formal", "foodpanda", "js", "Singapore"),

    ("Seoul Garden HotPot",
     "https://www.foodpanda.sg/chain/ca0el/seoul-garden-hotpot",
     "formal", "foodpanda", "js", "Singapore"),

    ("Hokkaido-ya",
     "https://www.foodpanda.sg/chain/cl2om/hokkaido-ya",
     "formal", "foodpanda", "js", "Singapore"),

    ("BreadTalk",
     "https://www.foodpanda.sg/chain/ci6eh/breadtalk",
     "formal", "foodpanda", "js", "Singapore"),

    ("Toast Box",
     "https://www.foodpanda.sg/chain/cv4kj/toast-box",
     "formal", "foodpanda", "js", "Singapore"),

    ("Old Chang Kee",
     "https://www.foodpanda.sg/chain/cl8xf/old-chang-kee",
     "formal", "foodpanda", "js", "Singapore"),

    ("Crystal Jade GO",
     "https://www.foodpanda.sg/chain/cx5on/crystal-jade-go",
     "formal", "foodpanda", "js", "Singapore"),

    # --- INFORMAL ---
    ("Song Fa Bak Kut Teh",
     "https://www.foodpanda.sg/chain/cw6zr/song-fa-bak-kut-teh",
     "informal", "foodpanda", "js", "Singapore"),

    ("Hawker Chan",
     "https://www.foodpanda.sg/chain/co6ta/hawker-chan-1",
     "informal", "foodpanda", "js", "Singapore"),

    ("A Noodle Story",
     "https://www.foodpanda.sg/chain/ck9ew/a-noodle-story",
     "informal", "foodpanda", "js", "Singapore"),

    ("328 Katong Laksa",
     "https://www.foodpanda.sg/chain/cj3zd/328-katong-laksa",
     "informal", "foodpanda", "js", "Singapore"),

    ("Crave Nasi Lemak",
     "https://www.foodpanda.sg/chain/cq1ek/crave",
     "informal", "foodpanda", "js", "Singapore"),

    ("28 Fried Kway Teow",
     "https://www.foodpanda.sg/chain/cq1by/28-fried-kway-teow",
     "informal", "foodpanda", "js", "Singapore"),

    ("Tai Wah Pork Noodles",
     "https://www.foodpanda.sg/chain/ce0vj/tai-wah-pork-noodles",
     "informal", "foodpanda", "js", "Singapore"),

    ("Janggut Laksa",
     "https://www.foodpanda.sg/chain/cv4xl/the-original-katong-laksa-since-1950",
     "informal", "foodpanda", "js", "Singapore"),

    ("Nam Kee Chicken Rice",
     "https://www.foodpanda.sg/chain/ci9rk/nam-kee-chicken-rice",
     "informal", "foodpanda", "js", "Singapore"),

    ("Swee Choon Tim Sum",
     "https://www.foodpanda.sg/chain/cz4bh/swee-choon-tim-sum-restaurant",
     "informal", "foodpanda", "js", "Singapore"),

    ("Killiney Kopitiam",
     "https://www.foodpanda.sg/chain/ca6up/killiney-kopitiam-alexandra",
     "informal", "foodpanda", "js", "Singapore"),

    # ==========================================================
    # MALAYSIA — foodpanda.my + GrabFood where needed
    # ==========================================================

    # --- FORMAL ---
    ("Din Tai Fung KL",
     "https://www.foodpanda.my/chain/cs3mk/din-tai-fung-cs3mk",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Sushi Tei KL",
     "https://www.foodpanda.my/chain/cc5bp/sushi-tei",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Ichiban Boshi KL",
     "https://www.foodpanda.my/chain/ct3ai/ichiban-boshi-japanese-restaurant",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Pepper Lunch KL",
     "https://www.foodpanda.my/chain/cc7eh/pepper-lunch-nh-group",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Ippudo KL",
     "https://food.grab.com/my/en/restaurant/ippudo-bsc-non-halal-delivery/1-CZC3AE5BRJXJJT",
     "formal", "grabfood", "js", "Malaysia"),

    ("Secret Recipe",
     "https://food.grab.com/my/en/chain/secret-recipe-delivery",
     "formal", "grabfood", "js", "Malaysia"),

    ("OldTown White Coffee",
     "https://www.foodpanda.my/chain/ce9ti/oldtown",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Nando's KL",
     "https://www.foodpanda.my/chain/ck9ti/nando-s",
     "formal", "foodpanda", "js", "Malaysia"),

    ("TGI Fridays KL",
     "https://www.foodpanda.my/chain/cm9sc/tgi-fridays",
     "formal", "foodpanda", "js", "Malaysia"),

    ("Madam Kwan's",
     "https://www.foodpanda.my/chain/ca0vy/madam-kwan",
     "formal", "foodpanda", "js", "Malaysia"),

    # --- INFORMAL ---
    ("Village Park Nasi Lemak",
     "https://food.grab.com/my/en/restaurant/village-park-restaurant-delivery/MYDD05660",
     "informal", "grabfood", "js", "Malaysia"),

    ("Restoran Yusoof Dan Zakhir",
     "https://www.foodpanda.my/restaurant/y9sn/restoran-yusoof-and-zakhir-sdn-bhd",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Ah Weng Koh Hainan Tea",
     "https://food.grab.com/my/en/restaurant/ah-weng-koh-hainan-tea-icc-pudu-delivery/1-CZJKJY4ZA4EXT6",
     "informal", "grabfood", "js", "Malaysia"),

    ("Dragon-i",
     "https://food.grab.com/my/en/restaurant/dragon-i-mid-valley-non-halal-delivery/MYDD12601",
     "informal", "grabfood", "js", "Malaysia"),

    ("Kluang Rail Coffee",
     "https://www.foodpanda.my/chain/ct6tr/kluang-rail-coffee",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Kim Lian Kee",
     "https://www.foodpanda.my/restaurant/ch0l/kim-lian-kee-ch0l",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Hameed Pata Mee Sotong",
     "https://www.foodpanda.my/restaurant/pp2t/hameed-pata-mee",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Nasi Kandar Pelita",
     "https://www.foodpanda.my/restaurant/o2ge/nasi-kandar-pelita-bangsar",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Jerung Char Koay Teow",
     "https://www.foodpanda.my/chain/cd4du/jerung-char-koay-teow",
     "informal", "foodpanda", "js", "Malaysia"),

    ("Family Seafood",
     "https://www.foodpanda.my/chain/cr6of/family-seafood",
     "informal", "foodpanda", "js", "Malaysia"),
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    conn = init_db()
    today = date.today().isoformat()

    print(f"\nUIFPI Daily Collection — {today}")
    print(f"Total targets: {len(TARGETS)}")

    # Filter out anything already in the DB before the first attempt
    remaining = [t for t in TARGETS if not already_scraped(conn, t[0], today)]
    skipped = len(TARGETS) - len(remaining)
    if skipped:
        print(f"Already scraped today: {skipped} — skipping")
    print(f"To scrape: {len(remaining)}\n")

    for attempt in range(1, 4):
        if not remaining:
            break

        print(f"--- Attempt {attempt} ({len(remaining)} targets) ---\n")
        remaining = run_batch(remaining, conn, today)

        if remaining and attempt < 3:
            print(f"\n{len(remaining)} failed — retrying in 1 min…")
            time.sleep(60)

    conn.close()

    if remaining:
        print(f"\n⚠  Still failed after 3 attempts:")
        for r in remaining:
            print(f"   - {r[0]}")
    else:
        print("\n✓  All targets completed successfully.")

    print("\nDone. Results in uifpi.db")
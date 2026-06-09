import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sqlite3
from datetime import date
import time

# --- Database setup ---
def init_db():
    conn = sqlite3.connect('uifpi.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT,
            item_name TEXT,
            price_sgd REAL,
            currency TEXT DEFAULT 'SGD',
            country TEXT DEFAULT 'Singapore',
            sector TEXT,
            source TEXT,
            collection_date TEXT,
            url TEXT
        )
    ''')
    conn.commit()
    return conn

# --- Scraper 1: Static HTML (TripAdvisor, Zomato, OpenRice) ---
def scrape_static(url, restaurant_name, sector, source, conn):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        today = date.today().isoformat()
        c = conn.cursor()

        # Adjust selectors per site — inspect HTML first
        items = soup.find_all('div', class_='menu-item')

        count = 0
        for item in items:
            name = item.find('span', class_='item-name')
            price = item.find('span', class_='item-price')
            if name and price:
                price_num = float(''.join(
                    ch for ch in price.get_text()
                    if ch.isdigit() or ch == '.'
                ))
                c.execute('''
                    INSERT INTO prices
                    (restaurant_name, item_name, price_sgd, sector,
                     source, collection_date, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (restaurant_name, name.get_text().strip(),
                      price_num, sector, source, today, url))
                count += 1

        conn.commit()
        print(f"  ✓ {restaurant_name} ({source}): {count} items")

    except Exception as e:
        print(f"  ✗ {restaurant_name}: {e}")

# --- Scraper 2: JavaScript-rendered (Foodpanda, GrabFood) ---
# Uses aria-label pattern: "Item Name,  S$ X.XX - Add to cart"
def scrape_js(url, restaurant_name, sector, source, conn):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            buttons = page.query_selector_all('[aria-label]')
            print(f"Total elements with aria-label: {len(buttons)}")
            for btn in buttons[:5]:
                print(f"  aria-label: {btn.get_attribute('aria-label')}")

            # Wait for add-to-cart buttons to load
            page.wait_for_selector(
                '[aria-label*="Add to cart"]',
                timeout=15000
            )

            today = date.today().isoformat()
            c = conn.cursor()
            count = 0

            # Every menu item has an add-to-cart button
            # Its aria-label contains both name and price
            # Format: "Item Name,  S$ X.XX - Add to cart"
            buttons = page.query_selector_all(
                '[aria-label*="Add to cart"]'
            )

            for button in buttons:
                aria = button.get_attribute('aria-label')
                if not aria:
                    continue

                # Extract price — find S$ followed by digits
                price_match = re.search(r'S\$\s*([\d.]+)', aria)
                if not price_match:
                    continue

                # Extract name — everything before the first comma
                name = aria.split(',')[0].strip()
                price_num = float(price_match.group(1))

                if name and price_num:
                    c.execute('''
                        INSERT INTO prices
                        (restaurant_name, item_name, price_sgd, sector,
                         source, collection_date, url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (restaurant_name, name, price_num,
                          sector, source, today, url))
                    count += 1

            conn.commit()
            browser.close()
            print(f"  ✓ {restaurant_name} ({source}): {count} items")

    except Exception as e:
        print(f"  ✗ {restaurant_name}: {e}")


# =============================================================
# TARGET LIST
# Format: (name, url, sector, source, scraper_type)
#
# Formal/Informal definition:
#   Formal   = chain restaurants, branded dining, 5+ outlets
#   Informal = hawker-origin, single or few outlets
# =============================================================

TARGETS = [
    # --- FORMAL (19 restaurants) ---
    ("Rubato",
     "https://www.foodpanda.sg/chain/cg9st/rubato-italian",
     "formal", "foodpanda", "js"),

    ("Ichiban Boshi",
     "https://www.foodpanda.sg/chain/cf5xz/ichiban-boshi",
     "formal", "foodpanda", "js"),

    ("Din Tai Fung",
     "https://www.foodpanda.sg/chain/cr7aw/din-tai-fung",
     "formal", "foodpanda", "js"),

    ("Sushi Tei",
     "https://www.foodpanda.sg/chain/ca2bs/sushi-tei",
     "formal", "foodpanda", "js"),

    ("Jumbo Seafood",
     "https://www.foodpanda.sg/chain/cs1lu/jumbo-seafood",
     "formal", "foodpanda", "js"),

    ("Crystal Jade La Mian Xiao Long Bao",
     "https://www.foodpanda.sg/chain/cp7ao/crystal-jade-la-mian-xiao-long-bao",
     "formal", "foodpanda", "js"),

    ("No Signboard Seafood",
     "https://www.foodpanda.sg/chain/cx5td/no-signboard-seafood",
     "formal", "foodpanda", "js"),

    ("Putien",
     "https://www.foodpanda.sg/chain/cc7gt/putien",
     "formal", "foodpanda", "js"),

    ("Paradise Dynasty",
     "https://www.foodpanda.sg/chain/cf5cj/paradise-dynasty",
     "formal", "foodpanda", "js"),

    ("Tim Ho Wan",
     "https://www.foodpanda.sg/chain/cs0lf/tim-ho-wan",
     "formal", "foodpanda", "js"),

    ("Crystal Jade Hong Kong Kitchen",
     "https://www.foodpanda.sg/chain/cs3bp/crystal-jade-hong-kong-kitchen",
     "formal", "foodpanda", "js"),

    ("Pepper Lunch",
     "https://www.foodpanda.sg/chain/cx6yd/pepper-lunch",
     "formal", "foodpanda", "js"),

    ("Ippudo Ramen",
     "https://www.foodpanda.sg/chain/cd8fm/ippudo-ramen",
     "formal", "foodpanda", "js"),

    ("Seoul Garden HotPot",
     "https://www.foodpanda.sg/chain/ca0el/seoul-garden-hotpot",
     "formal", "foodpanda", "js"),

    ("Hokkaido-ya",
     "https://www.foodpanda.sg/chain/cl2om/hokkaido-ya",
     "formal", "foodpanda", "js"),

    ("BreadTalk",
     "https://www.foodpanda.sg/chain/ci6eh/breadtalk",
     "formal", "foodpanda", "js"),

    ("Toast Box",
     "https://www.foodpanda.sg/chain/cv4kj/toast-box",
     "formal", "foodpanda", "js"),

    ("Old Chang Kee",
     "https://www.foodpanda.sg/chain/cl8xf/old-chang-kee",
     "formal", "foodpanda", "js"),

    ("Crystal Jade GO",
     "https://www.foodpanda.sg/chain/cx5on/crystal-jade-go",
     "formal", "foodpanda", "js"),

    # --- INFORMAL (11 restaurants) ---
    # Hawker-origin vendors, single or few outlets
    ("Song Fa Bak Kut Teh",
     "https://www.foodpanda.sg/chain/cw6zr/song-fa-bak-kut-teh",
     "informal", "foodpanda", "js"),

    ("Hawker Chan",
     "https://www.foodpanda.sg/chain/co6ta/hawker-chan-1",
     "informal", "foodpanda", "js"),

    ("A Noodle Story",
     "https://www.foodpanda.sg/chain/ck9ew/a-noodle-story",
     "informal", "foodpanda", "js"),

    ("328 Katong Laksa",
     "https://www.foodpanda.sg/chain/cj3zd/328-katong-laksa",
     "informal", "foodpanda", "js"),

    ("Crave Nasi Lemak",
     "https://www.foodpanda.sg/chain/cq1ek/crave",
     "informal", "foodpanda", "js"),

    ("28 Fried Kway Teow",
     "https://www.foodpanda.sg/chain/cq1by/28-fried-kway-teow",
     "informal", "foodpanda", "js"),

    ("Tai Wah Pork Noodles",
     "https://www.foodpanda.sg/chain/ce0vj/tai-wah-pork-noodles",
     "informal", "foodpanda", "js"),

    ("Janggut Laksa",
     "https://www.foodpanda.sg/chain/cv4xl/the-original-katong-laksa-since-1950",
     "informal", "foodpanda", "js"),

    ("Nam Kee Chicken Rice",
     "https://www.foodpanda.sg/chain/ci9rk/nam-kee-chicken-rice",
     "informal", "foodpanda", "js"),

    ("Swee Choon Tim Sum",
     "https://www.foodpanda.sg/chain/cz4bh/swee-choon-tim-sum-restaurant",
     "informal", "foodpanda", "js"),

    ("Killiney Kopitiam",
     "https://www.foodpanda.sg/chain/ca6up/killiney-kopitiam-alexandra",
     "informal", "foodpanda", "js"),
]

# =============================================================
# MAIN RUNNER
# Test with one restaurant first before running full list
# =============================================================

if __name__ == "__main__":
    conn = init_db()
    print(f"\nUIFPI Collection Run: {date.today().isoformat()}")
    print(f"Targets: {len(TARGETS)}\n")

    for name, url, sector, source, scraper_type in TARGETS:
        if scraper_type == "static":
            scrape_static(url, name, sector, source, conn)
            time.sleep(2)
        elif scraper_type in ("js", "delivery_app"):
            scrape_js(url, name, sector, source, conn)
            time.sleep(3)
        else:
            print(f"  ? Unknown scraper type for {name}: {scraper_type}")

    conn.close()
    print(f"\nDone. Check uifpi.db for results.")
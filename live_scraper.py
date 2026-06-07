import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sqlite3
from datetime import date
import time

# Database setup (const) 
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
def scrape_js(url, restaurant_name, sector, source, conn):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")

            # Adjust selector after inspecting actual page HTML
            page.wait_for_selector('[data-testid="menu-item"]', 
                                   timeout=10000)

            today = date.today().isoformat()
            c = conn.cursor()
            count = 0

            items = page.query_selector_all('[data-testid="menu-product-button-overlay-id"]')
            for item in items:
                name_el = item.query_selector(
                    '[data-testid="menu-item-name"]')
                price_el = item.query_selector(
                    '[aria-label="Home-baked Garlic Bread,  S$ 8.60 - Add to cart"]')

                if name_el and price_el:
                    name = name_el.inner_text().strip()
                    price_text = price_el.inner_text().strip()
                    price_num = float(''.join(
                        ch for ch in price_text 
                        if ch.isdigit() or ch == '.'
                    ))
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

# --- Target list ---
# Reminder: Format: (name, url, sector, source, scraper_type) 
TARGETS = [
    # Formal Restaurants (15) Singapore ones
("Rubato", "https://www.foodpanda.sg/chain/cg9st/rubato-italian", "Formal", "FoodPanda", "delivery_app")
("Ichiban Boshi", "https://www.foodpanda.sg/chain/cf5xz/ichiban-boshi", "Formal", "FoodPanda", "delivery_app")
("Din Tai Fung", "https://www.foodpanda.sg/chain/cr7aw/din-tai-fung", "Formal", "FoodPanda", "delivery_app")
("Sushi Tei", "https://www.foodpanda.sg/chain/ca2bs/sushi-tei", "Formal", "FoodPanda", "delivery_app")
("Jumbo Seafood", "https://www.foodpanda.sg/chain/cs1lu/jumbo-seafood", "Formal", "FoodPanda", "delivery_app")
("Crystal Jade La Mian Xiao Long Bao", "https://www.foodpanda.sg/chain/cp7ao/crystal-jade-la-mian-xiao-long-bao", "Formal", "FoodPanda", "delivery_app")
("No Signboard Seafood", "https://www.foodpanda.sg/chain/cx5td/no-signboard-seafood", "Formal", "FoodPanda", "delivery_app")
("Putien", "https://www.foodpanda.sg/chain/cc7gt/putien", "Formal", "FoodPanda", "delivery_app")
("Paradise Dynasty", "https://www.foodpanda.sg/chain/cf5cj/paradise-dynasty", "Formal", "FoodPanda", "delivery_app")
("Tim Ho Wan", "https://www.foodpanda.sg/chain/cs0lf/tim-ho-wan", "Formal", "FoodPanda", "delivery_app")
("Crystal Jade Hong Kong Kitchen", "https://www.foodpanda.sg/chain/cs3bp/crystal-jade-hong-kong-kitchen", "Formal", "FoodPanda", "delivery_app")
("Pepper Lunch", "https://www.foodpanda.sg/chain/cx6yd/pepper-lunch", "Formal", "FoodPanda", "delivery_app")
("Ippudo Ramen", "https://www.foodpanda.sg/chain/cd8fm/ippudo-ramen", "Formal", "FoodPanda", "delivery_app")
("Seoul Garden HotPot", "https://www.foodpanda.sg/chain/ca0el/seoul-garden-hotpot", "Formal", "FoodPanda", "delivery_app")
("Hokkaido-ya", "https://www.foodpanda.sg/chain/cl2om/hokkaido-ya", "Formal", "FoodPanda", "delivery_app")

# Informal Restaurants (15) Singapore ones
("Song Fa Bak Kut Teh", "https://www.foodpanda.sg/chain/cw6zr/song-fa-bak-kut-teh", "Informal", "FoodPanda", "delivery_app")
("Hawker Chan", "https://www.foodpanda.sg/chain/co6ta/hawker-chan-1", "Informal", "FoodPanda", "delivery_app")
("A Noodle Story", "https://www.foodpanda.sg/chain/ck9ew/a-noodle-story", "Informal", "FoodPanda", "delivery_app")
("328 Katong Laksa", "https://www.foodpanda.sg/chain/cj3zd/328-katong-laksa", "Informal", "FoodPanda", "delivery_app")
("Crave Nasi Lemak", "https://www.foodpanda.sg/chain/cq1ek/crave", "Informal", "FoodPanda", "delivery_app")
("28 Fried Kway Teow", "https://www.foodpanda.sg/chain/cq1by/28-fried-kway-teow", "Informal", "FoodPanda", "delivery_app")
("Tai Wah Pork Noodles", "https://www.foodpanda.sg/chain/ce0vj/tai-wah-pork-noodles", "Informal", "FoodPanda", "delivery_app")
("Janggut Laksa", "https://www.foodpanda.sg/chain/cv4xl/the-original-katong-laksa-since-1950", "Informal", "FoodPanda", "delivery_app")
("Nam Kee Chicken Rice", "https://www.foodpanda.sg/chain/ci9rk/nam-kee-chicken-rice", "Informal", "FoodPanda", "delivery_app")
("Old Chang Kee", "https://www.foodpanda.sg/chain/cl8xf/old-chang-kee", "Informal", "FoodPanda", "delivery_app")
("Toast Box", "https://www.foodpanda.sg/chain/cv4kj/toast-box", "Informal", "FoodPanda", "delivery_app")
("Swee Choon Tim Sum", "https://www.foodpanda.sg/chain/cz4bh/swee-choon-tim-sum-restaurant", "Informal", "FoodPanda", "delivery_app")
("BreadTalk", "https://www.foodpanda.sg/chain/ci6eh/breadtalk", "Informal", "FoodPanda", "delivery_app")
("Killiney Kopitiam", "https://www.foodpanda.sg/chain/ca6up/killiney-kopitiam-alexandra", "Informal", "FoodPanda", "delivery_app")
("Crystal Jade GO", "https://www.foodpanda.sg/chain/cx5on/crystal-jade-go", "Informal", "FoodPanda", "delivery_app")
]

# --- Main runner ---
if __name__ == "__main__":
    conn = init_db()
    print(f"\nCollection run: {date.today().isoformat()}")
    print(f"Targets: {len(TARGETS)}\n")

    for name, url, sector, source, scraper_type in TARGETS:
        if scraper_type == "static":
            scrape_static(url, name, sector, source, conn)
            time.sleep(2)
        elif scraper_type == "js":
            scrape_js(url, name, sector, source, conn)
            time.sleep(3)  # slightly longer delay for JS sites

    conn.close()
    print(f"\nDone.")

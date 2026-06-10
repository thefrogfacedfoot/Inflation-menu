import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import sqlite3
from datetime import date
import time
from playwright_stealth import stealth 

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
           browser = p.chromium.launch(headless=False)
           page = browser.new_page()
           stealth(page) # Apply stealth techniques to avoid detection
           page.goto(url, wait_until="networkidle")
           page.wait_for_timeout(8000)  # let JS fully render
           page.wait_for_selector(
            '[aria-label*="Add to cart"]',
            timeout=30000
           )  # wait for menu items to load

           today = date.today().isoformat()
           c = conn.cursor()
           count = 0

           buttons = page.query_selector_all(
               '[aria-label*="Add to cart"]'
           )

           for button in buttons:
               aria = button.get_attribute('aria-label')
               if not aria:
                   continue

               price_match = re.search(r'S\$\s*([\d.]+)', aria)
               if not price_match:
                   continue

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
    "https://www.rubato.com.sg/",
    "formal", "website", "js"),
   ("Ichiban Boshi",
    "https://www.ichibanboshi.com.sg/",
    "formal", "website", "js"),
   ("Din Tai Fung",
    "https://www.dintaifung.com.sg/",
    "formal", "website", "js"),
   ("Sushi Tei",
    "https://sushitei.com/",
    "formal", "website", "js"),
   ("Jumbo Seafood",
    "https://www.jumboseafood.com.sg/",
    "formal", "website", "js"),
   ("Crystal Jade La Mian Xiao Long Bao",
    "https://www.crystaljade.com/",
    "formal", "website", "js"),
   ("No Signboard Seafood",
    "https://nosignboardseafood.com/",
    "formal", "website", "js"),
   ("Putien",
    "https://www.putien.com/",
    "formal", "website", "js"),
   ("Paradise Dynasty",
    "https://www.paradisegp.com/paradise-dynasty/",
    "formal", "website", "js"),
   ("Tim Ho Wan",
    "https://www.timhowan.com/",
    "formal", "website", "js"),
   ("Crystal Jade Hong Kong Kitchen",
    "https://www.crystaljade.com/",
    "formal", "website", "js"),
   ("Pepper Lunch",
    "https://www.pepperlunch.com.sg/",
    "formal", "website", "js"),
   ("Ippudo Ramen",
    "https://www.ippudo.com.sg/",
    "formal", "website", "js"),
   ("Seoul Garden HotPot",
    "https://seoulgardenhotpot.com.sg/",
    "formal", "website", "js"),
   ("Hokkaido-ya",
    "https://hokkaido-ya.com.sg/",
    "formal", "website", "js"),
   ("BreadTalk",
    "https://www.breadtalk.com.sg/",
    "formal", "website", "js"),
   ("Toast Box",
    "https://www.toastbox.com.sg/",
    "formal", "website", "js"),
   ("Old Chang Kee",
    "https://www.oldchangkee.com/",
    "formal", "website", "js"),
   ("Crystal Jade GO",
    "https://www.crystaljade.com/",
    "formal", "website", "js"),

# --- INFORMAL (11 restaurants) ---
   ("Song Fa Bak Kut Teh",
    "https://songfa.com.sg/",
    "informal", "website", "js"),
   ("Hawker Chan",
    "https://www.liaofanhawkerchan.com/",
    "informal", "website", "js"),
   # A Noodle Story has no official website — replaced with Ya Kun Kaya Toast
   ("Ya Kun Kaya Toast",
    "https://yakun.com/",
    "informal", "website", "js"),
   ("328 Katong Laksa",
    "https://www.328katonglaksa.sg/",
    "informal", "website", "js"),
   # Crave Nasi Lemak has no standalone website — replaced with The Coconut Club
   ("The Coconut Club",
    "https://www.thecoconutclub.sg/",
    "informal", "website", "js"),
   # 28 Fried Kway Teow has no website — replaced with Boon Tong Kee
   ("Boon Tong Kee",
    "https://boontongkee.com.sg/",
    "informal", "website", "js"),
   ("Tai Wah Pork Noodles",
    "https://taiwahnoodles.com/",
    "informal", "website", "js"),
   # Janggut Laksa has no website — replaced with Bengawan Solo
   ("Bengawan Solo",
    "https://bengawansolo.sg/",
    "informal", "website", "js"),
   # Nam Kee Chicken Rice has no website — replaced with Wee Nam Kee
   ("Wee Nam Kee",
    "https://wnk.com.sg/",
    "informal", "website", "js"),
   ("Swee Choon Tim Sum",
    "https://www.sweechoon.com/",
    "informal", "website", "js"),
   ("Killiney Kopitiam",
    "https://killiney-kopitiam.com/",
    "informal", "website", "js"),
]

# =============================================================
# MAIN RUNNER
# =============================================================

if __name__ == "__main__":
   conn = init_db()
   print(f"\nUIFPI Collection Run: {date.today().isoformat()}")
   print(f"Targets: {len(TARGETS)}\n")

   failures = []

   for name, url, sector, source, scraper_type in TARGETS:
       try:
           if scraper_type == "static":
               scrape_static(url, name, sector, source, conn)
               time.sleep(2)
           elif scraper_type in ("js", "delivery_app"):
               scrape_js(url, name, sector, source, conn)
               time.sleep(3)
           else:
               print(f"  ? Unknown scraper type for {name}: {scraper_type}")
       except Exception as e:
           failures.append((name, str(e)))

   conn.close()

   if failures:
       print(f"\n⚠ Failed ({len(failures)}):")
       for fname, err in failures:
           print(f"  - {fname}: {err}")
   else:
       print(f"\nAll targets completed successfully.")

   print(f"\nDone. Check uifpi.db for results.")

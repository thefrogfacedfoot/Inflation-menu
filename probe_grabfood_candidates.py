"""
One-off probe for candidate GrabFood URLs (SG/MY/VN expansion, 2026-06-23).

Uses `_scrape_one` from live_scraper so probes get the full warmup +
location-cookie seed + landing-page redirect detection. Writes prices into
an in-memory SQLite so uifpi.db is not touched.

Outcomes:
  OK           — ≥1 menu items extracted
  BLOCKED      — ACCESS_DENIED bubbled from scrape_grabfood
  WRONG_PAGE   — page loaded but yielded 0 items (landing-redirect or layout drift)
  OTHER_FAIL   — unexpected exception
"""
import json
import random
import sqlite3
import time
from collections import defaultdict
from datetime import date

import live_scraper
from live_scraper import _scrape_one, get_usd_rates

live_scraper.SCRAPE_MAX_ATTEMPTS = 1


# (display_name, url, sector, source, currency, country)
CANDIDATES = [
    # ─── Singapore (11) ─────────────────────────────────────────────────────
    ("McDonald's SG",
     "https://food.grab.com/sg/en/restaurant/mcdonald-s-people-s-park-delivery/SGDD04919",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Crystal Jade Hong Kong Kitchen SG",
     "https://food.grab.com/sg/en/restaurant/crystal-jade-hong-kong-kitchen-tampines-mall-b1-11-delivery/SGDD12278",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Crystal Jade Go United Square",
     "https://food.grab.com/sg/en/restaurant/crystal-jade-go-united-square-01-02-03-delivery/4-CZLBCTCCEPKXC6",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Saizeriya SG",
     "https://food.grab.com/sg/en/restaurant/saizeriya-chinatown-point-delivery/4-CZEAR6D3V2JFCT",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Pizza Hut SG",
     "https://food.grab.com/sg/en/restaurant/pizza-hut-plaza-singapura-delivery/4-CY3KME5ZJF6YVA",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Subway SG",
     "https://food.grab.com/sg/en/restaurant/subway-the-central-delivery/4-CYTDLPUTG242KA",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Yoshinoya SG",
     "https://food.grab.com/sg/en/restaurant/yoshinoya-wisteria-mall-delivery/4-CYTTJJ22R3X2GA",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Old Chang Kee SG (GrabFood)",
     "https://food.grab.com/sg/en/restaurant/old-chang-kee-imm-building-delivery/4-CYN2GYVDGNEXVN",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Burger King SG",
     "https://food.grab.com/sg/en/restaurant/burger-king-ang-mo-kio-hub-delivery/4-CY3TEBNKN742R2",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Han's SG",
     "https://food.grab.com/sg/en/restaurant/han-s-jalan-bukit-merah-delivery/4-CZDJJPJFFEVXHE",
     "chain", "grabfood", "SGD", "Singapore"),
    ("Toast Box SG (GrabFood)",
     "https://food.grab.com/sg/en/restaurant/toast-box-vivocity-delivery/SGDD11187",
     "chain", "grabfood", "SGD", "Singapore"),

    # ─── Malaysia (9) ───────────────────────────────────────────────────────
    ("Marrybrown MY",
     "https://food.grab.com/my/en/restaurant/marrybrown-kwc-delivery/1-CY61KETKMCLDLJ",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("Chatime MY",
     "https://food.grab.com/my/en/restaurant/chatime-kl-sentral-delivery/MYDD05103",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("The Chicken Rice Shop MY",
     "https://food.grab.com/my/en/restaurant/the-chicken-rice-shop-nu-sentral-delivery/MYDD09861",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("Secret Recipe MY",
     "https://food.grab.com/my/en/restaurant/secret-recipe-suria-klcc-delivery/MYDD08963",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("McDonald's MY",
     "https://food.grab.com/my/en/restaurant/mcdonald-s%C2%AE-mont-kiara-139-delivery/MYDD06054",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("KFC MY",
     "https://food.grab.com/my/en/restaurant/kfc-meru-raya-dt-delivery/1-C2AEAXJALGLCCJ",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("Pizza Hut MY",
     "https://food.grab.com/my/en/restaurant/pizza-hut-kota-bharu-delivery/1-C2AALPTYKFXDUA",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("Domino's Pizza MY",
     "https://food.grab.com/my/en/restaurant/domino-s-pizza-gongbadak-delivery/1-CZDJG7NTL7MGEA",
     "chain", "grabfood", "MYR", "Malaysia"),
    ("Tealive MY",
     "https://food.grab.com/my/en/restaurant/tealive-penang-sentral-delivery/1-CY4DFGEJLUN3SA",
     "chain", "grabfood", "MYR", "Malaysia"),

    # ─── Vietnam (10) ───────────────────────────────────────────────────────
    ("Highlands Coffee VN A",
     "https://food.grab.com/vn/en/restaurant/highlands-coffee-nguy%E1%BB%85n-v%C4%83n-qu%C3%A1-delivery/5-CZCYNYKXNEJUVT",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Highlands Coffee VN B",
     "https://food.grab.com/vn/en/restaurant/highlands-coffee-flora-th%E1%BB%A7-%C4%91%E1%BB%A9c-delivery/5-C2LVTF23R36AAN",
     "chain", "grabfood", "VND", "Vietnam"),
    ("The Coffee House VN A",
     "https://food.grab.com/vn/en/restaurant/the-coffee-house-trung-h%C3%B2a-delivery/5-C3DGGU41E7KXEN",
     "chain", "grabfood", "VND", "Vietnam"),
    ("The Coffee House VN B",
     "https://food.grab.com/vn/en/restaurant/the-coffee-house-hai-b%C3%A0-tr%C6%B0ng-delivery/5-C3DGGU41FGK3TJ",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Phuc Long VN A",
     "https://food.grab.com/vn/en/restaurant/ph%C3%BAc-long-coffee-tea-house-ph%E1%BB%95-quang-delivery/5-CY5AGYMCV2XCBE",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Phuc Long VN B",
     "https://food.grab.com/vn/en/restaurant/ph%C3%BAc-long-82-h%C3%A0ng-%C4%91i%E1%BA%BFu-delivery/5-CYLTGZMUGPB1SA",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Lotteria VN A",
     "https://food.grab.com/vn/en/restaurant/lotteria-ph%C3%BA-m%E1%BB%B9-h%C6%B0ng-delivery/VNGFVN00000458",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Lotteria VN B",
     "https://food.grab.com/vn/en/restaurant/lotteria-tttm-royal-city-delivery/5-CYXGE6AAGXCXNT",
     "chain", "grabfood", "VND", "Vietnam"),
    ("Burger King VN",
     "https://food.grab.com/vn/en/restaurant/burger-king-trung-h%C3%B2a-delivery/5-CZNDJ4MDC4MDCE",
     "chain", "grabfood", "VND", "Vietnam"),
    ("KFC VN",
     "https://food.grab.com/vn/en/restaurant/kfc-tttm-go-c%E1%BB%A7-chi-delivery/5-C7WHGXT3CPAFL6",
     "chain", "grabfood", "VND", "Vietnam"),
]


def init_mem_db():
    conn = sqlite3.connect(':memory:')
    conn.execute('''
        CREATE TABLE prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT, item_name TEXT, price REAL, currency TEXT,
            price_usd REAL, country TEXT DEFAULT 'Singapore', sector TEXT,
            source TEXT, collection_date TEXT, url TEXT
        )
    ''')
    conn.commit()
    return conn


def classify_error(msg):
    if 'ACCESS_DENIED' in msg:
        return 'BLOCKED'
    if '0 items' in msg or 'may not have loaded' in msg:
        return 'WRONG_PAGE'
    return 'OTHER_FAIL'


def main():
    today = date.today().isoformat()
    print('Fetching USD rates...')
    usd_rates = get_usd_rates()
    conn = init_mem_db()

    results = []
    for i, target in enumerate(CANDIDATES, 1):
        name, url, sector, source, currency, country = target
        print(f'\n[{i:>2}/{len(CANDIDATES)}] {country:<10} {name}')
        t0 = time.time()
        try:
            count = _scrape_one(target, conn, today, usd_rates)
            status = 'OK'
            detail = f'{count} items'
        except RuntimeError as e:
            status = classify_error(str(e))
            detail = str(e)[:160]
        except Exception as e:
            status = 'OTHER_FAIL'
            detail = f'{type(e).__name__}: {str(e)[:140]}'
        dt = time.time() - t0
        print(f'   → {status:<11} ({dt:.1f}s)  {detail}')
        results.append({
            'name': name, 'url': url, 'country': country,
            'status': status, 'detail': detail, 'elapsed_s': round(dt, 1),
        })
        if i < len(CANDIDATES):
            cool = random.uniform(8, 14)
            print(f'   sleeping {cool:.1f}s')
            time.sleep(cool)

    with open('probe_grabfood_results.json', 'w') as fh:
        json.dump(results, fh, indent=2)

    print('\n══════════════ YIELD TABLE ══════════════')
    by_cs = defaultdict(lambda: defaultdict(int))
    for r in results:
        by_cs[r['country']][r['status']] += 1
        by_cs[r['country']]['_total'] += 1
    hdr = f'{"Country":<12} {"Tot":>4} {"OK":>4} {"Blocked":>8} {"WrongPg":>8} {"Other":>6}'
    print(hdr)
    print('-' * len(hdr))
    for c in ('Singapore', 'Malaysia', 'Vietnam'):
        d = by_cs[c]
        print(f'{c:<12} {d["_total"]:>4} {d["OK"]:>4} '
              f'{d["BLOCKED"]:>8} {d["WRONG_PAGE"]:>8} {d["OTHER_FAIL"]:>6}')

    print('\nFull JSON → probe_grabfood_results.json')


if __name__ == '__main__':
    main()

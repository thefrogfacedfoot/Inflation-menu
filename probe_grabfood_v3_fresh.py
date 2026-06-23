"""
Round 3 probe — MY/VN candidates only, fresh browser per target.

Calls live_scraper._scrape_one directly. This is identical to how the live
scraper itself processes each target in sequential mode:
  - Fresh sync_playwright/browser launch per attempt
  - _new_context per attempt (locale + UA per country)
  - _warmup → home page → restaurant nav (with 3 internal landing-page retries)
  - Default SCRAPE_MAX_ATTEMPTS=2 — second outer retry on non-block failure

In-TARGETS MY/VN URLs reliably yield items under this exact pattern
(today's workers=1 live run: MY 5/5, VN 2/2). This probe tests whether the
same pattern unlocks the previously-failed candidate URLs from rounds 1+2.
"""
import json
import random
import sqlite3
import time
from collections import defaultdict
from datetime import date

# NOTE: deliberately NOT monkey-patching SCRAPE_MAX_ATTEMPTS — use default (2)
# so we mimic _scrape_one EXACTLY.
from live_scraper import _scrape_one, get_usd_rates


CANDIDATES = [
    # Malaysia (9)
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

    # Vietnam (10)
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
    print('Fetching USD rates…')
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

    with open('probe_grabfood_v3_results.json', 'w') as fh:
        json.dump(results, fh, indent=2)

    print('\n══════════════ YIELD TABLE (v3 fresh-browser) ══════════════')
    by_cs = defaultdict(lambda: defaultdict(int))
    for r in results:
        by_cs[r['country']][r['status']] += 1
        by_cs[r['country']]['_total'] += 1
    hdr = f'{"Country":<12} {"Tot":>4} {"OK":>4} {"Blocked":>8} {"WrongPg":>8} {"Other":>6}'
    print(hdr)
    print('-' * len(hdr))
    for c in ('Malaysia', 'Vietnam'):
        d = by_cs[c]
        print(f'{c:<12} {d["_total"]:>4} {d["OK"]:>4} '
              f'{d["BLOCKED"]:>8} {d["WRONG_PAGE"]:>8} {d["OTHER_FAIL"]:>6}')


if __name__ == '__main__':
    main()

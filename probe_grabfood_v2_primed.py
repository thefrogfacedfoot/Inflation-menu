"""
Round 2 probe — same 28 failed candidates, but with WAF priming.

Hypothesis: aws-waf-token is set by hitting a known-good GrabFood restaurant
URL (e.g. McDonald's SG). Once present, subsequent restaurant URLs bypass
the "Login to search location" gate that redirected new URLs to landing.

Approach: launch ONE browser per country, prime by hitting a known-good URL,
then probe each candidate in the same persistent context.
"""
import json
import random
import sqlite3
import time
from collections import defaultdict
from datetime import date

from playwright.sync_api import sync_playwright

import live_scraper
from live_scraper import (
    BROWSER_LAUNCH_ARGS, USER_AGENTS, COUNTRY_LOCALE, _STEALTH,
    _new_context, _seed_grabfood_location, _warmup,
    scrape_grabfood, get_usd_rates,
)

live_scraper.SCRAPE_MAX_ATTEMPTS = 1


# Known-good "WAF-priming" URLs per country — these set aws-waf-token on first hit.
# For SG we know McDonald's works. For MY/VN we'll use one of the in-TARGETS URLs.
PRIMING_URLS = {
    'Singapore': ('McDonald\'s SG (prime)',
                  'https://food.grab.com/sg/en/restaurant/mcdonald-s-people-s-park-delivery/SGDD04919'),
    'Malaysia':  ('Din Tai Fung KL (prime)',
                  'https://food.grab.com/my/en/restaurant/din-tai-fung-the-gardens-mall-non-halal-delivery/1-CY2UGABXFCA2RE'),
    'Vietnam':   ('XIANG BA LAO (prime)',
                  'https://food.grab.com/vn/en/restaurant/xiang-ba-lao-chinese-food-delivery/5-C7V2NFTTCKKTAT'),
}

# 28 previously-failed candidates (omit the 2 that already passed)
CANDIDATES = [
    # Singapore (9 — previously failed)
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
    ("Toast Box SG (GrabFood)",
     "https://food.grab.com/sg/en/restaurant/toast-box-vivocity-delivery/SGDD11187",
     "chain", "grabfood", "SGD", "Singapore"),
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


def prime_session(page, country):
    """Visit the priming URL to obtain aws-waf-token cookie."""
    name, url = PRIMING_URLS[country]
    print(f'  Priming WAF via {name} …')
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45_000)
        page.wait_for_timeout(4_000)
    except Exception as e:
        print(f'    prime nav exception: {e}')
    try:
        cookies = {c['name'] for c in page.context.cookies()}
        print(f'    cookies after prime: {len(cookies)}  '
              f'aws-waf-token={"YES" if "aws-waf-token" in cookies else "NO"}')
    except Exception:
        pass


def main():
    today = date.today().isoformat()
    print('Fetching USD rates...')
    usd_rates = get_usd_rates()
    conn = init_mem_db()

    # Group candidates by country (one browser per country)
    by_country = defaultdict(list)
    for c in CANDIDATES:
        by_country[c[5]].append(c)

    results = []
    for country in ('Singapore', 'Malaysia', 'Vietnam'):
        cands = by_country[country]
        if not cands:
            continue
        print(f'\n══════════════ {country} — {len(cands)} candidates ══════════════')

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=live_scraper.HEADLESS, args=BROWSER_LAUNCH_ARGS,
            )
            try:
                context = _new_context(browser, country)
                page = context.new_page()
                if _STEALTH is not None:
                    try: _STEALTH.apply_stealth_sync(page)
                    except Exception: pass

                # Stage 1: seed + warmup (existing flow)
                _seed_grabfood_location(page, country)
                _warmup(page, 'grabfood', country)

                # Stage 2: WAF priming via known-good URL
                prime_session(page, country)

                # Stage 3: probe each candidate in the same context
                for i, target in enumerate(cands, 1):
                    name, url, sector, source, currency, _ = target
                    print(f'\n[{i:>2}/{len(cands)}] {name}')
                    t0 = time.time()
                    try:
                        count = scrape_grabfood(page, url, name, sector, currency,
                                               conn, country, usd_rates)
                        if count == 0:
                            status = 'WRONG_PAGE'
                            detail = '0 items'
                        else:
                            status = 'OK'
                            detail = f'{count} items'
                    except RuntimeError as e:
                        msg = str(e)
                        if 'ACCESS_DENIED' in msg:
                            status = 'BLOCKED'
                        else:
                            status = 'OTHER_FAIL'
                        detail = msg[:140]
                    except Exception as e:
                        status = 'OTHER_FAIL'
                        detail = f'{type(e).__name__}: {str(e)[:120]}'
                    dt = time.time() - t0
                    print(f'   → {status:<11} ({dt:.1f}s)  {detail}')
                    results.append({
                        'name': name, 'url': url, 'country': country,
                        'status': status, 'detail': detail,
                        'elapsed_s': round(dt, 1),
                    })
                    if i < len(cands):
                        cool = random.uniform(6, 10)
                        time.sleep(cool)
            finally:
                try: browser.close()
                except Exception: pass

    with open('probe_grabfood_v2_results.json', 'w') as fh:
        json.dump(results, fh, indent=2)

    print('\n══════════════ YIELD TABLE (PRIMED) ══════════════')
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


if __name__ == '__main__':
    main()

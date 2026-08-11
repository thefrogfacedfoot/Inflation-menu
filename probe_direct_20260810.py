"""
Live-probe driver for US / Australia 'direct' chain-website candidates
(2026-08-10 TARGETS expansion).

Runs the REAL live_scraper.scrape_direct code path (XHR-intercept -> JSON-LD
-> embedded JSON -> DOM prices) against an in-memory SQLite DB with the same
schema, so a candidate only passes if it would actually have produced priced
rows in a live run. Nothing is written to uifpi.db or live_scraper.py.

Menu URLs are NOT guessed. For each chain we load the homepage and follow the
site's own menu link (nav anchor whose text/href looks like a menu). Guessing
"/menu" paths would mark a live chain dead on a wrong path. If no menu link is
found the homepage itself is scraped and the verdict records that.

Excludes every chain already in TARGETS and every chain already logged dead in
the live_scraper.py graveyard (404 / WAF / "no priced JSON or DOM prices"),
per the standing rule against re-probing known-dead sources.

Usage:
  python3 probe_direct_20260810.py --country US
  python3 probe_direct_20260810.py --country AU
"""
import argparse
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import (
    COUNTRY_LOCALE, BROWSER_LAUNCH_ARGS, USER_AGENTS, _STEALTH,
    scrape_direct, get_usd_rates,
)

SCHEMA = '''
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_name TEXT, item_name TEXT, price REAL, currency TEXT,
    price_usd REAL, country TEXT, sector TEXT, source TEXT,
    collection_date TEXT, url TEXT
);
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_name TEXT, item_name TEXT, old_price REAL, new_price REAL,
    price_change_pct REAL, country TEXT, sector TEXT, change_detected_date TEXT
);
'''

# Candidates are (display name, homepage, sector). Homepages only -- the menu
# page is discovered from the site's own navigation.
US_CANDIDATES = [
    ("Chili's",                 "https://www.chilis.com",           "chain"),
    ("TGI Fridays",             "https://www.tgifridays.com",       "chain"),
    ("Red Robin",               "https://www.redrobin.com",         "chain"),
    ("Texas Roadhouse",         "https://www.texasroadhouse.com",   "chain"),
    ("Cracker Barrel",          "https://www.crackerbarrel.com",    "chain"),
    ("Bob Evans",               "https://www.bobevans.com",         "chain"),
    ("Red Lobster",             "https://www.redlobster.com",       "chain"),
    ("LongHorn Steakhouse",     "https://www.longhornsteakhouse.com", "chain"),
    ("Cheesecake Factory",      "https://www.thecheesecakefactory.com", "chain"),
    ("PF Chang's",              "https://www.pfchangs.com",         "chain"),
    ("BJ's Restaurant",         "https://www.bjsrestaurants.com",   "chain"),
    ("Golden Corral",           "https://www.goldencorral.com",     "chain"),
    ("Perkins",                 "https://www.perkinsrestaurants.com", "chain"),
    ("Hooters",                 "https://www.hooters.com",          "chain"),
    ("Carrabba's",              "https://www.carrabbas.com",        "chain"),
    ("Bonefish Grill",          "https://www.bonefishgrill.com",    "chain"),
    ("Maggiano's",              "https://www.maggianos.com",        "chain"),
    ("Yard House",              "https://www.yardhouse.com",        "chain"),
    ("Bahama Breeze",           "https://www.bahamabreeze.com",     "chain"),
    ("Chuy's",                  "https://www.chuys.com",            "chain"),
    ("On The Border",           "https://www.ontheborder.com",      "chain"),
    ("Famous Dave's",           "https://www.famousdaves.com",      "chain"),
    ("Miller's Ale House",      "https://millersalehouse.com",      "chain"),
    ("Panda Express",           "https://www.pandaexpress.com",     "chain"),
    ("Noodles & Company",       "https://www.noodles.com",          "chain"),
    ("Potbelly",                "https://www.potbelly.com",         "chain"),
    ("Jason's Deli",            "https://www.jasonsdeli.com",       "chain"),
    ("McAlister's Deli",        "https://www.mcalistersdeli.com",   "chain"),
    ("Firehouse Subs",          "https://www.firehousesubs.com",    "chain"),
    ("Jersey Mike's",           "https://www.jerseymikes.com",      "chain"),
    ("Boston Market",           "https://www.bostonmarket.com",     "chain"),
    ("Portillo's",              "https://www.portillos.com",        "independent"),
    ("Bojangles",               "https://www.bojangles.com",        "chain"),
    ("Culver's",                "https://www.culvers.com",          "chain"),
    ("Freddy's",                "https://www.freddys.com",          "chain"),
]

AU_CANDIDATES = [
    ("Red Rooster",             "https://www.redrooster.com.au",    "chain"),
    ("Hungry Jack's",           "https://www.hungryjacks.com.au",   "chain"),
    ("KFC Australia",           "https://www.kfc.com.au",           "chain"),
    ("Pizza Hut Australia",     "https://www.pizzahut.com.au",      "chain"),
    ("Crust Pizza",             "https://www.crust.com.au",         "chain"),
    ("Betty's Burgers",         "https://bettysburgers.com.au",     "chain"),
    ("Chicken Treat",           "https://www.chickentreat.com.au",  "chain"),
    ("Salsa's Fresh Mex",       "https://salsas.com.au",            "chain"),
    ("Zeus Street Greek",       "https://zeusstreetgreek.com.au",   "chain"),
    ("Fishbowl",                "https://www.fishbowl.com.au",      "chain"),
    ("SumoSalad",               "https://sumosalad.com",            "chain"),
    ("Gami Chicken",            "https://gamichicken.com.au",       "chain"),
    ("Nene Chicken",            "https://nenechicken.com.au",       "chain"),
    ("Chatime Australia",       "https://chatime.com.au",           "chain"),
    ("Gong Cha Australia",      "https://gongcha.com.au",           "chain"),
    ("Muffin Break",            "https://www.muffinbreak.com.au",   "chain"),
    ("Donut King",              "https://www.donutking.com.au",     "chain"),
    ("Baker's Delight",         "https://www.bakersdelight.com.au", "chain"),
    ("Krispy Kreme Australia",  "https://www.krispykreme.com.au",   "chain"),
    ("Sushi Hub",               "https://sushihub.com.au",          "chain"),
    ("Rashays",                 "https://rashays.com",              "chain"),
    ("Ribs & Burgers",          "https://ribsandburgers.com",       "chain"),
    ("Soul Origin",             "https://soulorigin.com.au",        "chain"),
    ("Din Tai Fung Australia",  "https://dintaifungaustralia.com.au", "independent"),
    ("Ippudo Australia",        "https://www.ippudo.com.au",        "independent"),
]

CONF = {
    'US': dict(candidates=US_CANDIDATES, country='United States', currency='USD'),
    'AU': dict(candidates=AU_CANDIDATES, country='Australia',     currency='AUD'),
}

MENU_LINK = re.compile(r'\bmenus?\b', re.I)


def mem_conn():
    c = sqlite3.connect(':memory:')
    c.executescript(SCHEMA)
    return c


def find_menu_url(page, home):
    """Follow the site's own menu link rather than guessing a /menu path."""
    try:
        hrefs = page.evaluate("""() =>
            Array.from(document.querySelectorAll('a[href]'))
                 .map(a => [ (a.innerText||'').trim(), a.href ])
                 .filter(([t,h]) => h && h.startsWith('http'))
        """)
    except Exception:
        return None
    best = None
    for text, href in hrefs:
        if not MENU_LINK.search(text or '') and not MENU_LINK.search(href):
            continue
        # Prefer a same-site link whose path mentions menu.
        if '/menu' in href.lower():
            return href
        if best is None:
            best = href
    return best


def probe_one(name, home, sector, country, currency, usd_rates):
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'America/New_York'))
    out = {'name': name, 'homepage': home, 'sector': sector}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_LAUNCH_ARGS)
        try:
            ctx = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent=random.choice(USER_AGENTS), locale=locale, timezone_id=tz,
            )
            page = ctx.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass
            try:
                resp = page.goto(home, wait_until='domcontentloaded', timeout=30_000)
            except Exception as e:
                out.update(verdict='NAV_ERROR', detail=str(e)[:160], items=0)
                return out
            out['home_status'] = resp.status if resp else None
            if resp and resp.status >= 400:
                out.update(verdict='DEAD_HTTP', items=0)
                return out
            page.wait_for_timeout(2_500)

            menu_url = find_menu_url(page, home)
            out['menu_url'] = menu_url or home
            out['menu_link_found'] = bool(menu_url)

            conn = mem_conn()
            try:
                n = scrape_direct(page, out['menu_url'], name, sector,
                                  currency, conn, country, usd_rates)
            except Exception as e:
                out.update(verdict='SCRAPE_ERROR', detail=str(e)[:160], items=0)
                return out
            rows = conn.execute(
                'SELECT item_name, price FROM prices ORDER BY id LIMIT 5').fetchall()
            out['items'] = n
            out['sample_items'] = [f'{pr} {currency} {nm[:40]}' for nm, pr in rows]
            out['verdict'] = 'CONFIRMED_LIVE' if n > 0 else 'DEAD_NO_ITEMS'
            return out
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--country', required=True, choices=list(CONF))
    a = ap.parse_args()
    cfg = CONF[a.country]
    out_path = Path(f'probe_direct_20260810_{a.country.lower()}.json')
    data = json.loads(out_path.read_text()) if out_path.exists() else {'results': []}
    done = {r['name'] for r in data['results']}
    usd_rates = get_usd_rates()

    todo = [c for c in cfg['candidates'] if c[0] not in done]
    print(f"[{a.country}] probing {len(todo)} direct-site candidates\n")
    for i, (name, home, sector) in enumerate(todo, 1):
        t0 = time.time()
        try:
            r = probe_one(name, home, sector, cfg['country'], cfg['currency'], usd_rates)
        except Exception as e:
            r = {'name': name, 'homepage': home, 'sector': sector,
                 'verdict': 'PROBE_ERROR', 'detail': str(e)[:160], 'items': 0}
        r['elapsed_s'] = round(time.time() - t0, 1)
        data['results'].append(r)
        data['updated_at'] = datetime.now().isoformat()
        out_path.write_text(json.dumps(data, indent=2))
        print(f"[{a.country} {i}/{len(todo)}] {r['verdict']:<15} "
              f"items={r.get('items', 0):<5} {name[:30]:<32} {r.get('menu_url', '')[:60]}")
        time.sleep(random.uniform(2, 5))

    ok = [r for r in data['results'] if r['verdict'] == 'CONFIRMED_LIVE']
    print(f"\n[{a.country}] {len(ok)}/{len(data['results'])} confirmed live")


if __name__ == '__main__':
    main()

"""
Headed Playwright search of GrabFood SG/MY for specific restaurant names.

For each (name, country) pair below, opens GrabFood with a delivery address
set, searches by name, and saves the first restaurant URL found.

Output: candidate_grabfood_urls.json
"""
import json
import os
import random
import re
import sys
import time

from playwright.sync_api import sync_playwright

from live_scraper import (
    COUNTRY_LOCALE,
    BROWSER_LAUNCH_ARGS,
    USER_AGENTS,
    _STEALTH,
)

# Restaurants to find on GrabFood, replacing Foodpanda originals
SEARCHES = [
    ('Hawker Chan',                       'Singapore', 'informal'),
    ('Seoul Garden HotPot',               'Singapore', 'formal'),
    ('28 Fried Kway Teow',                'Singapore', 'informal'),
    ('Din Tai Fung KL',                   'Malaysia',  'formal'),
    ('Sushi Tei KL',                      'Malaysia',  'formal'),
    ('TGI Fridays KL',                    'Malaysia',  'formal'),
    ("Madam Kwan's",                      'Malaysia',  'formal'),
]

# GrabFood requires a delivery address.
# These coordinates are CBD addresses chosen because they exist on the maps.
# Format: (lat, lng, address)
ADDRESS_PRESETS = {
    'Singapore': (1.3000, 103.8500, '1 Raffles Place, Singapore'),
    'Malaysia':  (3.1390, 101.6869, 'KLCC, Kuala Lumpur'),
}


def _new_context(p, country):
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    browser = p.chromium.launch(
        headless=False,
        args=BROWSER_LAUNCH_ARGS,
    )
    context = browser.new_context(
        viewport={'width': 1440, 'height': 900},
        user_agent=random.choice(USER_AGENTS),
        locale=locale,
        timezone_id=tz,
        geolocation={'latitude': ADDRESS_PRESETS[country][0],
                     'longitude': ADDRESS_PRESETS[country][1]},
        permissions=['geolocation'],
    )
    return browser, context


def search_grabfood(country, query):
    """
    Return list of (title, url) pairs found searching GrabFood for `query`.
    Returns [] if blocked or nothing found.
    """
    base = {
        'Singapore': 'https://food.grab.com/sg/en/',
        'Malaysia':  'https://food.grab.com/my/en/',
    }[country]

    with sync_playwright() as p:
        browser, context = _new_context(p, country)
        try:
            page = context.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass

            try:
                page.goto(base, wait_until='domcontentloaded', timeout=45_000)
            except Exception as e:
                print(f"    nav failed: {e}")
                return []

            page.wait_for_timeout(3_000)

            # GrabFood gates by a delivery-address modal. Try to dismiss /
            # auto-fill with the preset address. Click 'Use current location'
            # if available; otherwise type an address and pick first suggestion.
            try:
                # The address modal sometimes auto-uses geolocation
                page.wait_for_timeout(2_000)
                # Try clicking "Use current location"
                use_loc = page.query_selector("button:has-text('Use current location')")
                if use_loc:
                    use_loc.click()
                    page.wait_for_timeout(3_000)
            except Exception:
                pass

            # Now navigate to search results page directly
            search_url = f"{base}restaurants?search={query.replace(' ', '+')}"
            try:
                page.goto(search_url, wait_until='domcontentloaded', timeout=45_000)
            except Exception as e:
                print(f"    search nav failed: {e}")
                return []
            page.wait_for_timeout(5_000)

            # Try to find restaurant links
            links = page.evaluate(r"""() => {
                const out = [];
                const seen = new Set();
                for (const a of document.querySelectorAll('a[href*="/restaurant/"]')) {
                    const href = a.href;
                    if (!href || seen.has(href)) continue;
                    seen.add(href);
                    const text = (a.innerText || '').trim().split('\n')[0];
                    out.push({title: text, url: href});
                }
                return out;
            }""") or []
            return links
        finally:
            try:
                browser.close()
            except Exception:
                pass


def main():
    results = {}
    for name, country, sector in SEARCHES:
        print(f"\n→ {name} ({country}) …")
        # Pick a search query — strip 'KL' suffix or honorific punctuation
        q = re.sub(r'\bKL\b', '', name).strip()
        q = q.replace("'", '')
        try:
            matches = search_grabfood(country, q)
        except Exception as e:
            print(f"    ERROR: {e}")
            matches = []
        if matches:
            for m in matches[:5]:
                print(f"    {m['title'][:50]!r}  {m['url']}")
        else:
            print(f"    (no matches)")
        results[name] = {
            'country': country,
            'sector': sector,
            'query': q,
            'matches': matches[:10],
        }
        # Brief cool-down between searches
        time.sleep(random.uniform(8, 14))

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'candidate_grabfood_urls.json')
    with open(out_path, 'w') as fh:
        json.dump(results, fh, indent=2, sort_keys=False)
    print(f"\nWrote {out_path}")


if __name__ == '__main__':
    main()

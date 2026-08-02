"""One-off diagnostic: why do these 4 targets load fine but extract 0 items.
Never writes to uifpi.db. Dumps title/url/body-snippet/screenshot per target
plus a probe of each scraper's individual strategies for GrabFood targets."""
import random
import sys

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import (
    COUNTRY_LOCALE, BROWSER_LAUNCH_ARGS, USER_AGENTS, _STEALTH, _new_context,
    _looks_like_grabfood_landing, _looks_like_block, _human_mouse_jitter,
)

TARGETS = [
    ('Tim Ho Wan', 'https://food.grab.com/sg/en/restaurant/tim-ho-wan-plaza-singapura-delivery/SGDD11583', 'Singapore', 'grabfood'),
    ('Din Tai Fung KL', 'https://food.grab.com/my/en/restaurant/din-tai-fung-the-gardens-mall-non-halal-delivery/1-CY2UGABXFCA2RE', 'Malaysia', 'grabfood'),
    ('XIANG BA LAO Chinese Food', 'https://food.grab.com/vn/en/restaurant/xiang-ba-lao-chinese-food-delivery/5-C7V2NFTTCKKTAT', 'Vietnam', 'grabfood'),
    ("Wendy's", 'https://www.wendys.com/food', 'United States', 'direct'),
]

for name, url, country, source in TARGETS:
    print(f"\n{'='*70}\n{name} ({country}/{source})\n{'='*70}")
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=BROWSER_LAUNCH_ARGS)
        try:
            context = _new_context(browser, country)
            page = context.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass
            try:
                resp = page.goto(url, wait_until='domcontentloaded', timeout=45_000)
                print('http status:', resp.status if resp else None)
            except Exception as e:
                print('NAV ERROR:', str(e)[:200])
                browser.close()
                continue
            page.wait_for_timeout(random.randint(3_000, 5_000))
            _human_mouse_jitter(page)
            try:
                page.wait_for_load_state('networkidle', timeout=15_000)
            except Exception:
                pass
            print('final url:', page.url)
            print('title:', page.title())
            print('blocked?', _looks_like_block(page))
            if source == 'grabfood':
                print('looks_like_grabfood_landing?', _looks_like_grabfood_landing(page))
            body = page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 1200)")
            print('--- body text (first 1200 chars) ---')
            print(body)

            if source == 'grabfood':
                next_data = page.evaluate(
                    "() => window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__).length : 0")
                print('NEXT_DATA present, length:', next_data)
                menu_items_dom = page.evaluate(
                    "() => document.querySelectorAll('[class*=\"MenuItem\"],[class*=\"menuItem\"],[class*=\"dish\"]').length")
                print('DOM elements matching MenuItem/dish selectors:', menu_items_dom)
                add_buttons = page.evaluate(
                    "() => document.querySelectorAll('button[aria-label]').length")
                print('aria-label buttons found:', add_buttons)

            screenshot_path = f"diag_{name.replace(' ', '_').replace(chr(39),'')[:30]}.png"
            try:
                page.screenshot(path=screenshot_path)
                print('screenshot saved to', screenshot_path)
            except Exception as e:
                print('screenshot failed:', e)
        finally:
            browser.close()

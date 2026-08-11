"""
Stricter re-verification of candidates_my_grabfood.json.

GrabFood needs a delivery-location cookie seeded before a restaurant URL
renders its own page; without it, the URL silently serves the generic
country landing page (title "Food Delivery Malaysia - Promos & Menu |
GrabFood MY", body "Login to search location...") while returning HTTP
200 on the SAME url (no redirect visible in page.url) -- confirmed
2026-08-03 re-testing this script's first candidate both headless and
headed, both landing on the generic shell. This is the documented
GrabFood gotcha (see scrape_grabfood/_warmup/_seed_grabfood_location in
live_scraper.py) -- a bare page.goto() is NOT a valid probe for this
platform. This script replicates live_scraper.scrape_grabfood's actual
navigation: warmup (home page + location cookie seed) then goto with up
to 3 attempts, re-warming between attempts, until the page is no longer
the generic landing shell.

Authoritative: only keep a candidate if (a) after navigation the page is
NOT the generic country-landing shell and (b) parse_grabfood on the
rendered HTML returns at least one real item.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import (
    COUNTRY_LOCALE, BROWSER_LAUNCH_ARGS, USER_AGENTS, _STEALTH,
    _warmup, _looks_like_grabfood_landing, _looks_like_block, _human_mouse_jitter,
)
from historical_html_scraper import parse_grabfood

COUNTRY = 'Malaysia'


def recheck_one(name, url, timeout_ms=45_000):
    locale, tz = COUNTRY_LOCALE.get(COUNTRY, ('en-MY', 'Asia/Kuala_Lumpur'))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=BROWSER_LAUNCH_ARGS)
        try:
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent=random.choice(USER_AGENTS), locale=locale, timezone_id=tz,
            )
            page = context.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass

            _warmup(page, 'grabfood', COUNTRY)

            http_status = None
            still_landing = True
            for attempt in range(1, 4):
                try:
                    resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
                    http_status = resp.status if resp else None
                except Exception as e:
                    browser.close()
                    return {'verdict': 'NAV_ERROR', 'detail': str(e)[:200]}
                page.wait_for_timeout(random.randint(3_000, 5_000))
                _human_mouse_jitter(page)

                if _looks_like_block(page, http_status):
                    browser.close()
                    return {'verdict': 'BLOCKED', 'http_status': http_status}

                still_landing = _looks_like_grabfood_landing(page)
                if not still_landing:
                    break
                if attempt < 3:
                    _warmup(page, 'grabfood', COUNTRY)
                    page.wait_for_timeout(random.randint(5_000, 7_500))

            # Give the menu a moment to render, same as scrape_grabfood.
            page.wait_for_timeout(2_000)
            final_url = page.url
            html = page.content()
            browser.close()
        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            raise

    items = parse_grabfood(html, 'MYR')

    if still_landing:
        verdict = 'DEAD_REDIRECTED'
    elif not items:
        verdict = 'DEAD_NO_ITEMS'
    else:
        verdict = 'CONFIRMED_LIVE'

    return {
        'verdict': verdict,
        'http_status': http_status,
        'final_url': final_url,
        'real_item_count': len(items),
        'sample_items': [f'{p} {c} {n[:40]}' for n, p, c in items[:5]],
    }


def main():
    path = Path('candidates_my_grabfood.json')
    data = json.loads(path.read_text())
    for i, c in enumerate(data['candidates'], 1):
        r = recheck_one(c['name'], c['url'])
        c['recheck'] = r
        print(f"[{i}/{len(data['candidates'])}] {r['verdict']:<16} "
              f"real_items={r['real_item_count']:<4} {c['name'][:45]}")
    path.write_text(json.dumps(data, indent=2))
    confirmed = sum(1 for c in data['candidates'] if c['recheck']['verdict'] == 'CONFIRMED_LIVE')
    dead = len(data['candidates']) - confirmed
    print(f"\n{confirmed} confirmed live, {dead} dead-on-recheck (kept in file, flagged)")


if __name__ == '__main__':
    main()

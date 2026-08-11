"""
Stricter re-verification of candidates_us_doordash.json.

Same rationale as reverify_uk_deliveroo_candidates.py: verify_targets.
verify_one()'s heuristic can false-positive on a dead/closed store if
DoorDash silently redirects a gone store's URL to its homepage or a
generic search/error page, which can still carry enough price-like DOM
text (other restaurants, promo banners) to clear the items_signal>=3
threshold.

This re-check is authoritative: navigate the candidate's URL, and only
keep it if (a) the final URL's last path segment (the store slug/ID)
still matches the candidate's own -- no redirect away from the store's
own page -- and (b) parse_doordash on the rendered HTML returns at least
one real item.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import COUNTRY_LOCALE, BROWSER_LAUNCH_ARGS, USER_AGENTS, _STEALTH
from historical_html_scraper import parse_doordash


def slug_from_url(url):
    return url.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1].lower()


def recheck_one(name, url, timeout_ms=30_000):
    slug = slug_from_url(url)
    locale, tz = COUNTRY_LOCALE.get('United States', ('en-US', 'America/New_York'))
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
            try:
                resp = page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
            except Exception as e:
                return {'verdict': 'NAV_ERROR', 'detail': str(e)[:200]}
            try:
                page.wait_for_load_state('networkidle', timeout=15_000)
            except Exception:
                pass
            page.wait_for_timeout(2_000)
            final_url = page.url
            http_status = resp.status if resp else None
            html = page.content()
        finally:
            browser.close()

    redirected_away = slug_from_url(final_url) != slug
    items = parse_doordash(html, 'USD')

    if redirected_away:
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
    path = Path('candidates_us_doordash.json')
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

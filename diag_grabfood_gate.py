"""
Diagnostic: compare a passing GrabFood SG URL vs a failing one to identify
why the location gate accepts one and not the other.

Loads:
  PASS — McDonald's SG (People's Park)        → SGDD04919
  FAIL — Saizeriya SG (Chinatown Point)       → 4-CZEAR6D3V2JFCT

For each, captures:
  - All cookies before + after navigation
  - Final URL (so we see 302 redirects to landing)
  - HTTP status of the goto response
  - Set-Cookie response headers from network events
  - localStorage 'landing-country-selected'

Goal: find the variable that distinguishes accept from reject.
"""
import json
import random
import time

from playwright.sync_api import sync_playwright

from live_scraper import (
    BROWSER_LAUNCH_ARGS, USER_AGENTS, COUNTRY_LOCALE, _STEALTH,
    _seed_grabfood_location, _warmup,
)


PASS_URL = "https://food.grab.com/sg/en/restaurant/mcdonald-s-people-s-park-delivery/SGDD04919"
FAIL_URL = "https://food.grab.com/sg/en/restaurant/saizeriya-chinatown-point-delivery/4-CZEAR6D3V2JFCT"


def snapshot_state(page, label):
    """Capture cookies, localStorage, URL, title."""
    state = {'label': label, 'url': page.url}
    try:
        state['title'] = page.title()
    except Exception:
        state['title'] = '<title error>'
    try:
        cookies = page.context.cookies()
        # Just the names + first 80 chars of value for readability
        state['cookies'] = {c['name']: c['value'][:80] for c in cookies}
    except Exception as e:
        state['cookies'] = {'err': str(e)[:80]}
    try:
        ls = page.evaluate("() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))")
        state['localStorage'] = json.loads(ls)
        # Trim long values
        for k, v in state['localStorage'].items():
            if len(str(v)) > 100:
                state['localStorage'][k] = str(v)[:100] + '…'
    except Exception as e:
        state['localStorage'] = {'err': str(e)[:80]}
    return state


def load_and_capture(page, url, label, network_log):
    """Goto URL, return state snapshot + redirect chain."""
    redirect_chain = []
    set_cookies = []

    def on_response(response):
        if 'food.grab.com' not in response.url:
            return
        sc = response.headers.get('set-cookie')
        if sc:
            set_cookies.append({'url': response.url[:120], 'set_cookie_head': sc[:200]})
        # Capture redirects (3xx)
        if 300 <= response.status < 400:
            redirect_chain.append({
                'status': response.status,
                'url': response.url[:120],
                'location': response.headers.get('location', '')[:120],
            })

    page.on('response', on_response)
    print(f'\n────── Loading {label} ──────')
    print(f'URL: {url}')
    resp = page.goto(url, wait_until='domcontentloaded', timeout=45_000)
    page.wait_for_timeout(4_000)
    after = snapshot_state(page, f'after_{label}')
    after['http_status'] = resp.status if resp else None
    after['redirect_chain'] = redirect_chain
    after['response_set_cookies'] = set_cookies[:5]
    page.remove_listener('response', on_response)
    return after


def main():
    country = 'Singapore'
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    states = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=BROWSER_LAUNCH_ARGS)
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent=random.choice(USER_AGENTS),
            locale=locale,
            timezone_id=tz,
        )
        page = context.new_page()
        if _STEALTH is not None:
            try: _STEALTH.apply_stealth_sync(page)
            except Exception: pass

        # Stage 1: apply location seed (before any navigation)
        _seed_grabfood_location(page, country)
        states.append(snapshot_state(page, 'after_seed_before_warmup'))

        # Stage 2: warmup (home page hit)
        _warmup(page, 'grabfood', country)
        states.append(snapshot_state(page, 'after_warmup'))

        # Stage 3: navigate to PASS URL
        states.append(load_and_capture(page, PASS_URL, 'PASS_McDonalds', []))

        # Cooldown
        time.sleep(5)

        # Stage 4: navigate to FAIL URL (in same context — same cookies/storage)
        states.append(load_and_capture(page, FAIL_URL, 'FAIL_Saizeriya', []))

        # Cooldown then re-warmup + retry FAIL URL (mimics _scrape_one retry)
        time.sleep(3)
        _warmup(page, 'grabfood', country)
        states.append(load_and_capture(page, FAIL_URL, 'FAIL_Saizeriya_retry', []))

        try:
            browser.close()
        except Exception:
            pass

    with open('diag_grabfood_gate_result.json', 'w') as fh:
        json.dump(states, fh, indent=2, ensure_ascii=False)

    # Print a compact comparison
    print('\n══════════════ COMPARISON ══════════════\n')
    for s in states:
        print(f'── {s["label"]} ──')
        print(f'  url: {s["url"]}')
        print(f'  title: {s.get("title","")[:80]}')
        print(f'  http_status: {s.get("http_status","-")}')
        ck = s.get('cookies', {})
        print(f'  cookies ({len(ck)}): {list(ck.keys())}')
        # Highlight the location cookie state
        loc = ck.get('location', '<MISSING>')
        print(f'    location cookie: {loc[:60]}…' if loc != '<MISSING>' else '    location cookie: <MISSING>')
        ls = s.get('localStorage', {})
        lcs = ls.get('landing-country-selected', '<MISSING>')
        print(f'    landing-country-selected: {lcs}')
        rc = s.get('redirect_chain', [])
        if rc:
            print(f'  redirects: {len(rc)}')
            for r in rc[:4]:
                print(f'    {r["status"]} → {r["location"][:80]}')
        print()

    print('Full JSON → diag_grabfood_gate_result.json')


if __name__ == '__main__':
    main()

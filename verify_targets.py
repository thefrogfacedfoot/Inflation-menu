"""
Verify every URL in live_scraper.TARGETS with a full Playwright browser load.

Classifies each URL into one of:
  OK            — page loaded, looks like a menu / items detected
  BLOCKED       — anti-bot interstitial detected
  DEAD          — HTTP/JS 4xx/5xx, generic error page, or empty body
  WRONG_PAGE    — page loaded but no menu items detectable
  NAV_ERROR     — Playwright failed to navigate (DNS, TLS, redirect loop)

Writes results to verify_targets_report.json and prints a per-country summary.

Run:
    python3 verify_targets.py                # all targets
    python3 verify_targets.py --country=Singapore
    python3 verify_targets.py --country=Singapore --concurrency=3
    python3 verify_targets.py --resume       # skip targets already in report
"""
import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from playwright.sync_api import sync_playwright

# Import the live target list and a few helpers
from live_scraper import (
    TARGETS,
    COUNTRY_LOCALE,
    BROWSER_LAUNCH_ARGS,
    USER_AGENTS,
    _STEALTH,
)

# Headed mode is set via CLI — Foodpanda/GrabFood reliably bot-detect
# headless Chromium, so verification has to use the same headed mode as the
# real scraper to give meaningful pass/fail signal.
HEADLESS = True
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uifpi.db')

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'verify_targets_report.json')

PRICE_TOKENS = ('S$', 'RM', '฿', 'Rp', '₹', 'A$', '£', '$')


def _looks_blocked(title, body_head):
    t = (title or '').lower()
    b = (body_head or '').lower()
    for needle in ('access denied', 'access to this page has been denied',
                   'pardon our interruption', 'are you a robot',
                   'cloudflare', 'unusual traffic', 'attention required'):
        if needle in t or needle in b:
            return True
    return False


def _looks_dead(title, body_head, http_status):
    t = (title or '').lower()
    b = (body_head or '').lower()
    if http_status is not None and http_status >= 400:
        return True
    if any(needle in t for needle in (
            '500', '404', 'not found', 'page not found',
            'internal server error', 'something went wrong')):
        return True
    if 'oops, something went wrong' in b or 'page not found' in b:
        return True
    return False


def _looks_like_menu(body_text, items_signal):
    """Heuristic: page contains multiple distinct price tokens."""
    if items_signal >= 3:
        return True
    # Count distinct prices in body text
    matches = re.findall(r'(?:RM|S\$|฿|Rp\.?|₹|A\$|£|\$)\s*\d+(?:[.,]\d{1,2})?',
                        body_text or '')
    return len(set(matches)) >= 3


def _looks_like_restaurant_page(title, url, target_name):
    """
    GrabFood/Foodpanda often render the restaurant title in <title> even when
    headless prevents the menu items from rendering. If the title contains
    distinctive words from the restaurant name, treat the URL as live.
    """
    if not title:
        return False
    t = title.lower()
    # Generic site titles → not the restaurant page
    generic = ('food delivery', 'grabfood', 'foodpanda',
               'oops', 'something went wrong', 'page not found',
               '404', '500', 'access denied')
    if any(g in t for g in generic):
        return False
    # Take 2 distinctive words (3+ chars) from target name; if any appears in
    # the page title, assume it loaded the right restaurant.
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", target_name)
             if w.lower() not in {'restaurant', 'cafe', 'bar', 'and', 'the'}]
    for w in words[:5]:
        if w in t:
            return True
    return False


def verify_one(target, timeout_ms=30_000):
    name, url, sector, source, currency, country = target
    locale, tz = COUNTRY_LOCALE.get(country, ('en-US', 'UTC'))
    record = {
        'name': name,
        'url': url,
        'source': source,
        'country': country,
        'final_url': '',
        'status': '',
        'http_status': None,
        'title': '',
        'body_head': '',
        'items_signal': 0,
        'reason': '',
    }
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=BROWSER_LAUNCH_ARGS,
            )
            try:
                context = browser.new_context(
                    viewport={'width': 1366, 'height': 768},
                    user_agent=random.choice(USER_AGENTS),
                    locale=locale,
                    timezone_id=tz,
                )
                page = context.new_page()
                if _STEALTH is not None:
                    try:
                        _STEALTH.apply_stealth_sync(page)
                    except Exception:
                        pass
                try:
                    resp = page.goto(url, wait_until='domcontentloaded',
                                     timeout=timeout_ms)
                    record['http_status'] = resp.status if resp else None
                except Exception as e:
                    record['status'] = 'NAV_ERROR'
                    record['reason'] = str(e)[:300]
                    return record

                try:
                    page.wait_for_load_state('networkidle', timeout=15_000)
                except Exception:
                    pass
                page.wait_for_timeout(2_000)

                try:
                    record['final_url'] = page.url
                except Exception:
                    pass
                try:
                    record['title'] = (page.title() or '')[:200]
                except Exception:
                    pass

                # Sample first chunk of body text for heuristics
                try:
                    body_head = page.evaluate(
                        "() => (document.body && document.body.innerText || '').slice(0, 4000)"
                    ) or ''
                except Exception:
                    body_head = ''
                record['body_head'] = body_head[:1200]

                # Crude items signal: count price-ish tokens in DOM
                try:
                    items_signal = page.evaluate("""() => {
                        const re = /(?:RM|S\\$|฿|Rp\\.?|₹|A\\$|£|\\$)\\s*\\d+(?:[.,]\\d{1,2})?/g;
                        const text = (document.body && document.body.innerText || '');
                        const matches = text.match(re) || [];
                        return matches.length;
                    }""")
                    record['items_signal'] = int(items_signal or 0)
                except Exception:
                    record['items_signal'] = 0

                if _looks_blocked(record['title'], body_head):
                    record['status'] = 'BLOCKED'
                    record['reason'] = 'anti-bot interstitial'
                    return record
                if _looks_dead(record['title'], body_head, record['http_status']):
                    record['status'] = 'DEAD'
                    record['reason'] = (
                        f"status={record['http_status']} title={record['title'][:80]!r}"
                    )
                    return record
                if _looks_like_menu(body_head, record['items_signal']):
                    record['status'] = 'OK'
                    record['reason'] = f"items_signal={record['items_signal']}"
                    return record
                if _looks_like_restaurant_page(record['title'], record['final_url'], name):
                    # Title looks right but menu didn't render — treat as live
                    record['status'] = 'OK_TITLE_ONLY'
                    record['reason'] = (
                        f"title matches restaurant name "
                        f"(items didn't render headless)"
                    )
                    return record
                record['status'] = 'WRONG_PAGE'
                record['reason'] = (
                    f"loaded but no menu signal "
                    f"(items_signal={record['items_signal']}, "
                    f"title={record['title'][:80]!r})"
                )
                return record
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        record['status'] = 'NAV_ERROR'
        record['reason'] = f"outer: {e}"[:300]
        return record


def _load_prior():
    try:
        with open(REPORT_PATH) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _ever_scraped_names():
    """Set of restaurant names with at least one row in prices."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT restaurant_name FROM prices")
        out = {r[0] for r in c.fetchall()}
        conn.close()
        return out
    except Exception:
        return set()


def main():
    global HEADLESS
    ap = argparse.ArgumentParser()
    ap.add_argument('--country', help='Only verify targets in this country')
    ap.add_argument('--source', help='Only this source key (foodpanda/grabfood/...)')
    ap.add_argument('--concurrency', type=int, default=3)
    ap.add_argument('--resume', action='store_true',
                    help='Skip targets already present in prior report')
    ap.add_argument('--headed', action='store_true',
                    help='Use headed Chromium (matches live_scraper)')
    ap.add_argument('--skip-known-good', action='store_true',
                    help='Skip targets that already have rows in uifpi.db')
    args = ap.parse_args()

    HEADLESS = not args.headed

    targets = list(TARGETS)
    if args.country:
        targets = [t for t in targets if t[5].lower() == args.country.lower()]
    if args.source:
        targets = [t for t in targets if t[3].lower() == args.source.lower()]
    if args.skip_known_good:
        known = _ever_scraped_names()
        before = len(targets)
        targets = [t for t in targets if t[0] not in known]
        print(f"[skip-known-good] skipped {before - len(targets)} previously-scraped targets")

    prior = _load_prior() if args.resume else None
    prior_map = {}
    if prior and isinstance(prior.get('results'), list):
        for rec in prior['results']:
            prior_map[(rec.get('name'), rec.get('url'))] = rec
    if args.resume and prior_map:
        before = len(targets)
        targets = [t for t in targets if (t[0], t[1]) not in prior_map]
        print(f"[resume] skipping {before - len(targets)} already-verified")

    print(f"Verifying {len(targets)} targets with concurrency={args.concurrency}")
    print(f"Report → {REPORT_PATH}")

    results = list(prior_map.values()) if args.resume else []
    started = time.time()

    def _run(t):
        try:
            return verify_one(t)
        except Exception as e:
            return {
                'name': t[0], 'url': t[1], 'source': t[3], 'country': t[5],
                'status': 'NAV_ERROR', 'reason': f'top-level: {e}'[:300],
                'final_url': '', 'http_status': None,
                'title': '', 'body_head': '', 'items_signal': 0,
            }

    completed = 0
    total = len(targets)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(_run, t): t for t in targets}
        for fut in as_completed(futures):
            rec = fut.result()
            results.append(rec)
            completed += 1
            elapsed = time.time() - started
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            print(f"  [{completed:>3}/{total}] {rec['status']:<11} "
                  f"{rec['name'][:50]:<50}  ({rec['country']})  — "
                  f"ETA {eta/60:.1f}m")

            # Checkpoint every 10 results
            if completed % 10 == 0:
                _save(results)

    _save(results)
    _print_summary(results)


def _save(results):
    payload = {
        'generated_at': datetime.now().isoformat(),
        'count': len(results),
        'results': results,
    }
    with open(REPORT_PATH, 'w') as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)


def _print_summary(results):
    by_country = {}
    by_status = {}
    for r in results:
        c = r['country']
        s = r['status']
        by_country.setdefault(c, {}).setdefault(s, 0)
        by_country[c][s] += 1
        by_status[s] = by_status.get(s, 0) + 1
    print('\n── Summary ──────────────────────────────────────────')
    for s in sorted(by_status):
        print(f"  {s:<11}  {by_status[s]}")
    print('\n── Per country ──────────────────────────────────────')
    for c in sorted(by_country):
        row = ' '.join(f"{k}={v}" for k, v in sorted(by_country[c].items()))
        print(f"  {c:<18}  {row}")


if __name__ == '__main__':
    main()

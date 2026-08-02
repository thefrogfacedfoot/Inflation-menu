"""
Stricter live audit of every entry in live_scraper.TARGETS — checks the
same blind spot found in verify_targets.py (2026-08-02, UK Deliveroo
candidate review): a dead/decommissioned store can silently redirect to a
generic listing/home page that still has enough incidental price-looking
text to pass verify_targets.py's crude items_signal>=3 regex threshold.

This audit is stricter in two ways verify_targets.py is not:
  1. Redirect check: does the final URL still point at the same
     restaurant-specific path, or did navigation drift to a bare
     city/area/home listing page?
  2. Real extraction: instead of a regex over page text, this runs the
     ACTUAL PRODUCTION scraper function for that target's source
     (SCRAPER_DISPATCH — scrape_foodpanda/scrape_grabfood/scrape_direct/
     scrape_js, the same functions live_scraper.py's nightly cron calls)
     against a throwaway in-memory SQLite connection. Never touches
     uifpi.db — insert_item() writes land in the scratch DB only, which
     is discarded when the process exits.

Headed mode (matches live_scraper.py's own default) — foodpanda/grabfood
reliably bot-detect headless Chromium, so headless would produce false
DEAD verdicts for those sources, not real signal.

Writes results incrementally to targets_audit_report.json (checkpointed
every target, so a kill mid-run still leaves a readable partial report).

Usage:
  python3 audit_targets_dead_redirect.py                # all 84 targets
  python3 audit_targets_dead_redirect.py --country "United Kingdom"
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright
from live_scraper import (
    TARGETS, SCRAPER_DISPATCH, HEADLESS, BROWSER_LAUNCH_ARGS,
    _new_context, _STEALTH, get_usd_rates,
)

REPORT_PATH = 'targets_audit_report.json'


def make_scratch_conn():
    conn = sqlite3.connect(':memory:')
    conn.execute('''CREATE TABLE prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_name TEXT, item_name TEXT, price REAL, currency TEXT,
        price_usd REAL, country TEXT, sector TEXT, source TEXT,
        collection_date TEXT, url TEXT
    )''')
    return conn


def slug_path(url):
    p = urlparse(url)
    return p.path.rstrip('/').lower()


def looks_like_bare_listing(original_url, final_url):
    """Heuristic redirect check: final path is a strict PREFIX-truncation
    of the original (fewer path segments) -- e.g.
    /menu/london/soho/nandos-soho -> /restaurants/london/soho, or the
    whole path collapsed to just the domain/country root."""
    orig_path = slug_path(original_url)
    final_path = slug_path(final_url)
    if orig_path == final_path:
        return False
    orig_segs = [s for s in orig_path.split('/') if s]
    final_segs = [s for s in final_path.split('/') if s]
    if not final_segs:
        return True
    # Dropped the last (most specific) segment(s) -- the restaurant slug
    # itself is gone from the path.
    if len(final_segs) < len(orig_segs) and orig_segs[:len(final_segs)] == final_segs:
        return True
    return False


def audit_one(target, usd_rates):
    name, url, sector, source, currency, country = target
    fn = SCRAPER_DISPATCH.get(source)
    record = {
        'name': name, 'url': url, 'source': source, 'country': country,
        'final_url': '', 'redirected_to_listing': False,
        'real_item_count': 0, 'verdict': '', 'detail': '',
    }
    if fn is None:
        record['verdict'] = 'UNKNOWN_SOURCE'
        return record

    conn = make_scratch_conn()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=BROWSER_LAUNCH_ARGS)
        try:
            context = _new_context(browser, country)
            page = context.new_page()
            if _STEALTH is not None:
                try:
                    _STEALTH.apply_stealth_sync(page)
                except Exception:
                    pass
            try:
                count = fn(page, url, name, sector, currency, conn, country, usd_rates)
            except Exception as e:
                count = 0
                record['detail'] = str(e)[:200]
                is_blocked = 'ACCESS_DENIED' in str(e)
            else:
                is_blocked = False
            try:
                record['final_url'] = page.url
            except Exception:
                record['final_url'] = ''
        finally:
            try:
                browser.close()
            except Exception:
                pass

    record['real_item_count'] = count
    record['redirected_to_listing'] = looks_like_bare_listing(url, record['final_url'])

    if is_blocked and count == 0:
        record['verdict'] = 'BLOCKED'
    elif record['redirected_to_listing']:
        record['verdict'] = 'DEAD_REDIRECTED'
    elif count == 0:
        record['verdict'] = 'DEAD_NO_ITEMS'
    else:
        record['verdict'] = 'CONFIRMED_LIVE'
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--country')
    ap.add_argument('--source')
    args = ap.parse_args()

    targets = list(TARGETS)
    if args.country:
        targets = [t for t in targets if t[5].lower() == args.country.lower()]
    if args.source:
        targets = [t for t in targets if t[3].lower() == args.source.lower()]

    print(f"Auditing {len(targets)} targets (headless={HEADLESS})")
    usd_rates = get_usd_rates()

    results = []
    for i, t in enumerate(targets, 1):
        r = audit_one(t, usd_rates)
        results.append(r)
        print(f"  [{i}/{len(targets)}] {r['verdict']:<16} real_items={r['real_item_count']:<4} "
              f"{r['name'][:40]:<40} ({r['country']}/{r['source']})")
        with open(REPORT_PATH, 'w') as fh:
            json.dump({'generated_at': datetime.now().isoformat(),
                       'count': len(results), 'results': results}, fh, indent=2)

    by_verdict = {}
    for r in results:
        by_verdict.setdefault(r['verdict'], []).append(r)
    print("\n=== Summary ===")
    for v in sorted(by_verdict):
        print(f"  {v:<16} {len(by_verdict[v])}")


if __name__ == '__main__':
    main()

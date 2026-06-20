"""
Phase 0 — Wayback CDX coverage probe across (country, platform) pairs.

For each pair, queries Wayback CDX with a URL pattern that matches the
platform's actual URL convention, then samples one archived page to check
whether prices are present in the static HTML. Output: coverage_report.csv
and coverage_report.md.

This is the decision gate. We do NOT bulk-scrape pages here — only enough
sampling to confirm prices are extractable. Stop and report after Phase 0.

Run:  python3 phase0_coverage_probe.py
"""
import csv
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CDX  = 'http://web.archive.org/cdx/search/cdx'
WBM  = 'https://web.archive.org/web'
HDR  = {
    'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'
}
WINDOW_FROM = '20180101'
WINDOW_TO   = '20260601'

# Per-probe knobs. Wayback rate-limits aggressive callers; be polite.
CDX_TIMEOUT       = 90
CDX_LIMIT         = 30000
CDX_DELAY         = 4.0
CDX_RETRIES       = 2
CDX_RETRY_BACKOFF = 15
FETCH_TIMEOUT     = 45
FETCH_DELAY       = 2.5

# (country, sector_hint, platform_label, cdx_url_pattern, currency_re_label)
# Patterns use the trailing-wildcard convention (no matchType param);
# this matches the working style from historical_scraper.py.
PROBES = [
    # US — formal-sector listings & menu indexes
    ('United States', 'formal', 'allmenus.com',     'allmenus.com/*',          'USD'),
    ('United States', 'formal', 'menupages.com',    'menupages.com/*',         'USD'),
    ('United States', 'formal', 'yelp.com/biz NYC', 'yelp.com/biz/*new-york*', 'USD'),
    ('United States', 'formal', 'yelp.com/menu',    'yelp.com/menu/*',         'USD'),
    # India
    ('India',         'formal', 'zomato Mumbai',    'zomato.com/mumbai/*',     'INR'),
    ('India',         'formal', 'zomato NCR',       'zomato.com/ncr/*',        'INR'),
    ('India',         'formal', 'swiggy Mumbai',    'swiggy.com/mumbai/*',     'INR'),
    ('India',         'formal', 'swiggy Bangalore', 'swiggy.com/bangalore/*',  'INR'),
    ('India',         'formal', 'burrp Mumbai',     'burrp.com/mumbai/*',      'INR'),
    ('India',         'formal', 'dineout.co.in',    'dineout.co.in/*',         'INR'),
    # Indonesia
    ('Indonesia',     'formal', 'zomato Jakarta',   'zomato.com/jakarta/*',    'IDR'),
    ('Indonesia',     'formal', 'qraved Jakarta',   'qraved.com/jakarta/*',    'IDR'),
    ('Indonesia',     'formal', 'pergikuliner',     'pergikuliner.com/restaurants/*', 'IDR'),
    # Thailand
    ('Thailand',      'formal', 'wongnai BKK',      'wongnai.com/bangkok/*',   'THB'),
    ('Thailand',      'formal', 'wongnai restaurants','wongnai.com/restaurants/*', 'THB'),
    ('Thailand',      'formal', 'eatigo BKK',       'eatigo.com/th/bangkok/*', 'THB'),
    # Australia
    ('Australia',     'formal', 'zomato Sydney',    'zomato.com/sydney/*',     'AUD'),
    ('Australia',     'formal', 'zomato Melbourne', 'zomato.com/melbourne/*',  'AUD'),
    ('Australia',     'formal', 'urbanspoon',       'urbanspoon.com/n/*',      'AUD'),
    ('Australia',     'formal', 'menulog',          'menulog.com.au/restaurants/*', 'AUD'),
    # Vietnam
    ('Vietnam',       'formal', 'foody HCMC',       'foody.vn/ho-chi-minh/*',  'VND'),
    # Philippines
    ('Philippines',   'formal', 'zomato Manila',    'zomato.com/manila/*',     'PHP'),
    # Malaysia
    ('Malaysia',      'formal', 'zomato KL',        'zomato.com/kuala-lumpur/*', 'MYR'),
    # Singapore
    ('Singapore',     'formal', 'hungrygowhere',    'hungrygowhere.com/dining-guide/restaurants/*', 'SGD'),
    ('Singapore',     'formal', 'foodpanda SG',     'foodpanda.sg/restaurant/*', 'SGD'),
    ('Singapore',     'formal', 'food.grab SG',     'food.grab.com/sg/en/restaurant/*', 'SGD'),
    # Mexico
    ('Mexico',        'formal', 'tripadvisor MX',   'tripadvisor.com.mx/Restaurant_Review*', 'MXN'),
]

# Currency-detection regex (used on sampled archived HTML)
CURRENCY_REGEXES = {
    'USD': re.compile(r'\$\s?\d+(?:\.\d{2})?'),
    'GBP': re.compile(r'£\s?\d+(?:\.\d{2})?'),
    'INR': re.compile(r'(?:₹|Rs\.?)\s?\d+(?:[.,]\d{2})?'),
    'IDR': re.compile(r'Rp\.?\s?\d+(?:[.,]\d{3})*'),
    'THB': re.compile(r'(?:฿|THB)\s?\d+(?:\.\d{2})?'),
    'AUD': re.compile(r'A?\$\s?\d+(?:\.\d{2})?'),
    'SGD': re.compile(r'S\$\s?\d+(?:\.\d{2})?'),
    'MYR': re.compile(r'RM\s?\d+(?:\.\d{2})?'),
    'PHP': re.compile(r'(?:₱|PHP)\s?\d+(?:\.\d{2})?'),
    'VND': re.compile(r'\d+(?:\.\d{3})*\s?₫|\d+(?:\.\d{3})*\s?VND'),
    'MXN': re.compile(r'\$\s?\d+(?:\.\d{2})?'),
}


def query_cdx(pattern):
    """One CDX query with retries. Returns (rows, error_or_None)."""
    params = {
        'url':    pattern,
        'from':   WINDOW_FROM,
        'to':     WINDOW_TO,
        'output': 'json',
        'fl':     'timestamp,original',
        'filter': ['statuscode:200', 'mimetype:text/html'],
        'limit':  CDX_LIMIT,
    }
    last_err = None
    for attempt in range(CDX_RETRIES + 1):
        try:
            r = requests.get(CDX, params=params, headers=HDR, timeout=CDX_TIMEOUT)
            if r.status_code != 200:
                last_err = f'HTTP {r.status_code}'
                if r.status_code in (429, 503, 504) and attempt < CDX_RETRIES:
                    time.sleep(CDX_RETRY_BACKOFF)
                    continue
                return None, last_err
            data = r.json()
            if not data or len(data) < 2:
                return [], None
            return [(row[0], row[1]) for row in data[1:]], None
        except Exception as e:
            last_err = str(e)[:80]
            if attempt < CDX_RETRIES:
                time.sleep(CDX_RETRY_BACKOFF)
    return None, last_err


def sample_page_for_prices(timestamp, orig_url, currency_re):
    """Fetch one archived page with id_ suffix and count price matches."""
    url = f"{WBM}/{timestamp}id_/{orig_url}"
    try:
        r = requests.get(url, headers=HDR, timeout=FETCH_TIMEOUT)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}'
        text = r.text
        n_price = len(currency_re.findall(text))
        has_ld  = 'application/ld+json' in text
        has_nd  = '__NEXT_DATA__' in text
        bytes_kb = len(r.content) // 1024
        return {
            'kb': bytes_kb, 'price_hits': n_price,
            'json_ld': has_ld, 'next_data': has_nd,
        }, None
    except Exception as e:
        return None, str(e)[:60]


def main():
    print(f"Phase 0 coverage probe — {len(PROBES)} (country, platform) pairs")
    print(f"Window: {WINDOW_FROM} → {WINDOW_TO}")
    print(f"CDX limit {CDX_LIMIT}, timeout {CDX_TIMEOUT}s, delay {CDX_DELAY}s, "
          f"retries {CDX_RETRIES}\n")

    results = []
    rnd = random.Random(20260616)

    for i, (country, sector, platform, pat, cur) in enumerate(PROBES, 1):
        print(f"[{i:>2}/{len(PROBES)}] {country:<14} {platform:<22} {pat}")
        rows, err = query_cdx(pat)

        rec = {
            'country': country, 'sector': sector, 'platform': platform,
            'pattern': pat, 'currency': cur,
            'n_restaurants_ge2': 0, 'n_snapshots': 0,
            'distinct_urls': 0, 'earliest': '', 'latest': '',
            'cdx_status': '',
            'sample_url': '', 'sample_ts': '',
            'sample_kb': '', 'sample_price_hits': '',
            'sample_json_ld': '', 'sample_next_data': '',
            'sample_status': '',
        }

        if err:
            print(f"          CDX ERROR: {err}")
            rec['cdx_status'] = f'error:{err}'
            results.append(rec)
            time.sleep(CDX_DELAY)
            continue

        if not rows:
            print(f"          0 rows")
            rec['cdx_status'] = 'empty'
            results.append(rec)
            time.sleep(CDX_DELAY)
            continue

        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        ge2 = [u for u, ts_list in per_url.items() if len(ts_list) >= 2]
        all_ts = sorted(ts for ts_list in per_url.values() for ts in ts_list)
        rec.update({
            'n_restaurants_ge2': len(ge2),
            'n_snapshots': len(rows),
            'distinct_urls': len(per_url),
            'earliest': all_ts[0][:8] if all_ts else '',
            'latest':   all_ts[-1][:8] if all_ts else '',
            'cdx_status': 'truncated' if len(rows) >= CDX_LIMIT else 'ok',
        })
        trunc = ' (TRUNCATED)' if len(rows) >= CDX_LIMIT else ''
        print(f"          {len(per_url):>6} distinct URLs, {len(ge2):>5} ≥2-cap, "
              f"{len(rows):>6} snapshots, {rec['earliest']}-{rec['latest']}{trunc}")

        # Sample ONE archived page from a ≥2-capture URL (or any URL if none)
        # to confirm prices are present in the static HTML.
        candidates = ge2 if ge2 else list(per_url.keys())
        sample_url = rnd.choice(candidates)
        sample_ts  = per_url[sample_url][len(per_url[sample_url]) // 2]
        cre = CURRENCY_REGEXES.get(cur, CURRENCY_REGEXES['USD'])
        time.sleep(FETCH_DELAY)
        print(f"          sampling {sample_ts} {sample_url[:70]}")
        s, ferr = sample_page_for_prices(sample_ts, sample_url, cre)
        rec['sample_url'] = sample_url
        rec['sample_ts']  = sample_ts
        if ferr:
            rec['sample_status'] = f'error:{ferr}'
            print(f"          sample fetch failed: {ferr}")
        else:
            rec.update({
                'sample_kb': s['kb'],
                'sample_price_hits': s['price_hits'],
                'sample_json_ld': 'Y' if s['json_ld'] else 'N',
                'sample_next_data': 'Y' if s['next_data'] else 'N',
                'sample_status': 'ok',
            })
            print(f"          sample: {s['kb']} KB, {s['price_hits']} {cur} hits, "
                  f"LD={s['json_ld']} ND={s['next_data']}")

        results.append(rec)
        time.sleep(CDX_DELAY)

    # CSV
    csv_path = os.path.join(BASE, 'coverage_report.csv')
    fieldnames = ['country', 'sector', 'platform', 'pattern', 'currency',
                  'n_restaurants_ge2', 'n_snapshots', 'distinct_urls',
                  'earliest', 'latest', 'cdx_status',
                  'sample_url', 'sample_ts', 'sample_kb',
                  'sample_price_hits', 'sample_json_ld', 'sample_next_data',
                  'sample_status']
    with open(csv_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"\nCSV → {csv_path}")

    # Markdown
    md_path = os.path.join(BASE, 'coverage_report.md')
    with open(md_path, 'w') as fh:
        fh.write(f"# Phase 0 — Wayback CDX coverage matrix\n\n")
        fh.write(f"Generated: {datetime.now().isoformat()}\n  \n")
        fh.write(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n  \n")
        fh.write(f"CDX limit per query: {CDX_LIMIT:,} (rows ≥ limit = truncated).\n\n")
        fh.write("Each row probes one (country, platform) pair: counts distinct\n"
                 "archived URLs and snapshots in-window, then fetches one sample\n"
                 "archived page (id_ raw, no Wayback toolbar) and counts currency-\n"
                 "shaped price tokens in the static HTML — i.e., the data we'd\n"
                 "actually be able to extract without re-running JavaScript.\n\n")
        fh.write("## Matrix\n\n")
        fh.write("| Country | Platform | URL pattern | ≥2-cap restaurants | "
                 "Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Notes |\n")
        fh.write("|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|\n")
        for r in results:
            rng = f"{r['earliest']}–{r['latest']}" if r['earliest'] else '—'
            notes = r['cdx_status']
            if r['sample_status'] and r['sample_status'] != 'ok':
                notes += '; sample ' + r['sample_status']
            fh.write(
                f"| {r['country']} | {r['platform']} | `{r['pattern']}` | "
                f"{r['n_restaurants_ge2']:,} | {r['n_snapshots']:,} | {rng} | "
                f"{r['sample_kb']} | {r['sample_price_hits']} | "
                f"{r['sample_json_ld']} | {r['sample_next_data']} | {notes} |\n"
            )

        fh.write("\n## Country roll-up (best platform per country)\n\n")
        roll = {}
        for r in results:
            c = r['country']
            best = roll.get(c)
            if (best is None or
                (r['n_restaurants_ge2'], r['sample_price_hits'] or 0) >
                (best['n_restaurants_ge2'], best['sample_price_hits'] or 0)):
                roll[c] = r
        fh.write("| Country | Best platform | ≥2-cap restaurants | "
                 "Sample $-hits | Clears formal threshold (≥15 + prices visible)? |\n")
        fh.write("|---|---|---:|---:|---|\n")
        for c in sorted(roll):
            r = roll[c]
            ok = ('✓' if r['n_restaurants_ge2'] >= 15 and
                  (r['sample_price_hits'] or 0) >= 5 else '✗')
            fh.write(f"| {c} | {r['platform']} | {r['n_restaurants_ge2']:,} | "
                     f"{r['sample_price_hits']} | {ok} |\n")

        fh.write("\n## Reading the matrix\n\n")
        fh.write("- `≥2-cap restaurants` = distinct archived URLs with two or "
                 "more captures inside the window. This is the gating metric "
                 "for the formal-sector roster (≥15 required).\n")
        fh.write("- `Sample $-hits` = currency-token count in ONE randomly-chosen "
                 "archived page. Low or zero hits mean even though Wayback has "
                 "captures, the captured HTML doesn't contain prices — usually "
                 "because the site is/was a JS shell that loaded prices via API.\n")
        fh.write("- `LD` / `ND` = whether the sample HTML has JSON-LD or "
                 "`__NEXT_DATA__`; presence of either gives a clean structured "
                 "data path that's usually more reliable than DOM regex.\n")
        fh.write("- A country clears the formal threshold only when BOTH "
                 "≥2-cap ≥ 15 **and** sample $-hits ≥ 5.\n")
        fh.write("- Common Crawl was not probed in this pass. It is a secondary "
                 "archive available for Phase 1 if Wayback gaps are narrow.\n")
    print(f"MD  → {md_path}")
    print(f"\nDone. Inspect coverage_report.md before any collection.")


if __name__ == '__main__':
    main()

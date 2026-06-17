"""
Phase 0 — Track B candidate-source probe.

Targets:
  ID — GoFood / Gojek archived pages
  TH — GrabFood TH archived pages
  AU — Menulog revisit (sanity check; existing 12% yield)

Same matrix format as coverage_report.md. Each row probes one
(country, platform) pair: CDX yields + one sampled archived page.

Output: coverage_report_track_b.{csv,md}
"""
import csv
import os
import random
import re
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

CDX_TIMEOUT       = 90
CDX_LIMIT         = 30000
CDX_DELAY         = 4.0
CDX_RETRIES       = 2
CDX_RETRY_BACKOFF = 15
FETCH_TIMEOUT     = 45
FETCH_DELAY       = 2.5

PROBES = [
    # Indonesia GoFood — Gojek's food-delivery vertical.
    ('Indonesia',  'formal', 'gofood',            'gofood.co.id/*',                'IDR'),
    ('Indonesia',  'formal', 'gojek food',        'gojek.com/*/food/*',            'IDR'),
    ('Indonesia',  'formal', 'gofood jakarta',    'gofood.co.id/jakarta/*',        'IDR'),
    # Thailand GrabFood — Grab's TH vertical (same brand as SG, different TLD).
    ('Thailand',   'formal', 'grabfood TH',       'food.grab.com/th/en/*',         'THB'),
    ('Thailand',   'formal', 'grabfood TH (TH)',  'food.grab.com/th/th/*',         'THB'),
    ('Thailand',   'formal', 'lineman TH',        'lineman.co.th/*',               'THB'),
    # AU Menulog revisit — sanity check the existing pipeline's source.
    ('Australia',  'formal', 'menulog (revisit)', 'menulog.com.au/restaurants/*',  'AUD'),
]

CURRENCY_REGEXES = {
    'IDR': re.compile(r'Rp\.?\s?\d+(?:[.,]\d{3})*'),
    'THB': re.compile(r'(?:฿|THB)\s?\d+(?:\.\d{2})?'),
    'AUD': re.compile(r'A?\$\s?\d+(?:\.\d{2})?'),
    'USD': re.compile(r'\$\s?\d+(?:\.\d{2})?'),
}


def query_cdx(pattern):
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
    url = f"{WBM}/{timestamp}id_/{orig_url}"
    try:
        r = requests.get(url, headers=HDR, timeout=FETCH_TIMEOUT)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}'
        text = r.text
        n_price = len(currency_re.findall(text))
        has_ld  = 'application/ld+json' in text
        has_nd  = '__NEXT_DATA__' in text
        # Bot-block heuristics: tiny pages or pages containing common block
        # markers indicate the source rejected the archive request.
        block = ''
        bl = text.lower()
        if r.status_code == 200 and len(text) < 400:
            block = 'tiny-page'
        elif 'cloudflare' in bl and 'attention required' in bl:
            block = 'cloudflare-challenge'
        elif 'captcha' in bl:
            block = 'captcha'
        bytes_kb = len(r.content) // 1024
        return {
            'kb': bytes_kb, 'price_hits': n_price,
            'json_ld': has_ld, 'next_data': has_nd,
            'block': block,
        }, None
    except Exception as e:
        return None, str(e)[:60]


def main():
    print(f"Phase 0 probe (Track B) — {len(PROBES)} pairs", flush=True)
    print(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n", flush=True)

    results = []
    rnd = random.Random(20260617)

    for i, (country, sector, platform, pat, cur) in enumerate(PROBES, 1):
        print(f"[{i:>2}/{len(PROBES)}] {country:<14} {platform:<22} {pat}",
              flush=True)
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
            'sample_block': '',
            'sample_status': '',
        }

        if err:
            print(f"          CDX ERROR: {err}", flush=True)
            rec['cdx_status'] = f'error:{err}'
            results.append(rec)
            time.sleep(CDX_DELAY)
            continue

        if not rows:
            print(f"          0 rows", flush=True)
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
              f"{len(rows):>6} snapshots, {rec['earliest']}-{rec['latest']}{trunc}",
              flush=True)

        candidates = ge2 if ge2 else list(per_url.keys())
        sample_url = rnd.choice(candidates)
        sample_ts  = per_url[sample_url][len(per_url[sample_url]) // 2]
        cre = CURRENCY_REGEXES.get(cur, CURRENCY_REGEXES['USD'])
        time.sleep(FETCH_DELAY)
        print(f"          sampling {sample_ts} {sample_url[:70]}", flush=True)
        s, ferr = sample_page_for_prices(sample_ts, sample_url, cre)
        rec['sample_url'] = sample_url
        rec['sample_ts']  = sample_ts
        if ferr:
            rec['sample_status'] = f'error:{ferr}'
            print(f"          sample fetch failed: {ferr}", flush=True)
        else:
            rec.update({
                'sample_kb': s['kb'],
                'sample_price_hits': s['price_hits'],
                'sample_json_ld': 'Y' if s['json_ld'] else 'N',
                'sample_next_data': 'Y' if s['next_data'] else 'N',
                'sample_block': s['block'],
                'sample_status': 'ok' if not s['block'] else f'block:{s["block"]}',
            })
            block_str = f' BLOCK={s["block"]}' if s['block'] else ''
            print(f"          sample: {s['kb']} KB, {s['price_hits']} {cur} hits, "
                  f"LD={s['json_ld']} ND={s['next_data']}{block_str}",
                  flush=True)

        results.append(rec)
        time.sleep(CDX_DELAY)

    csv_path = os.path.join(BASE, 'coverage_report_track_b.csv')
    fieldnames = ['country', 'sector', 'platform', 'pattern', 'currency',
                  'n_restaurants_ge2', 'n_snapshots', 'distinct_urls',
                  'earliest', 'latest', 'cdx_status',
                  'sample_url', 'sample_ts', 'sample_kb',
                  'sample_price_hits', 'sample_json_ld', 'sample_next_data',
                  'sample_block', 'sample_status']
    with open(csv_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"\nCSV → {csv_path}", flush=True)

    md_path = os.path.join(BASE, 'coverage_report_track_b.md')
    with open(md_path, 'w') as fh:
        fh.write(f"# Phase 0 — Track B candidate-source probe\n\n")
        fh.write(f"Generated: {datetime.now().isoformat()}\n  \n")
        fh.write(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n  \n")
        fh.write(f"CDX limit per query: {CDX_LIMIT:,}.\n\n")
        fh.write("Same yields-table format as `coverage_report.md`. Adds a "
                 "`Block` column flagging Cloudflare/captcha/tiny-page "
                 "responses so we can bail on bot-blocked sources fast.\n\n")
        fh.write("## Matrix\n\n")
        fh.write("| Country | Platform | URL pattern | ≥2-cap restaurants | "
                 "Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Block | Notes |\n")
        fh.write("|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|---|\n")
        for r in results:
            rng = f"{r['earliest']}–{r['latest']}" if r['earliest'] else '—'
            notes = r['cdx_status']
            if r['sample_status'] and r['sample_status'] not in ('ok', ''):
                notes += '; sample ' + r['sample_status']
            block = r.get('sample_block') or '—'
            fh.write(
                f"| {r['country']} | {r['platform']} | `{r['pattern']}` | "
                f"{r['n_restaurants_ge2']:,} | {r['n_snapshots']:,} | {rng} | "
                f"{r['sample_kb']} | {r['sample_price_hits']} | "
                f"{r['sample_json_ld']} | {r['sample_next_data']} | "
                f"{block} | {notes} |\n"
            )

        fh.write("\n## Decision: which targets to add to "
                 "`historical_html_scraper.py`?\n\n")
        fh.write("| Country | Best platform | ≥2-cap | $-hits | Block | Verdict |\n")
        fh.write("|---|---|---:|---:|---|---|\n")
        roll = {}
        for r in results:
            c = r['country']
            best = roll.get(c)
            if (best is None or
                (r['n_restaurants_ge2'], r['sample_price_hits'] or 0) >
                (best['n_restaurants_ge2'], best['sample_price_hits'] or 0)):
                roll[c] = r
        for c in sorted(roll):
            r = roll[c]
            blocked = (r.get('sample_block') or '') != ''
            ok = (r['n_restaurants_ge2'] >= 15 and
                  (r['sample_price_hits'] or 0) >= 5 and not blocked)
            verdict = ('✓ queue' if ok else
                       'bail (bot-blocked)' if blocked else
                       'bail (no prices visible)')
            fh.write(f"| {c} | {r['platform']} | {r['n_restaurants_ge2']:,} | "
                     f"{r['sample_price_hits']} | "
                     f"{r.get('sample_block') or '—'} | {verdict} |\n")
    print(f"MD  → {md_path}", flush=True)
    print(f"\nDone.", flush=True)


if __name__ == '__main__':
    main()

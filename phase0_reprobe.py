"""
Phase 0 re-probes:
  (1) Try alternative URL patterns for Vietnam (foody.vn).
  (2) For high-volume / zero-regex-hit platforms (allmenus, wongnai,
      qraved, dineout), fetch 5 random sample pages and parse JSON-LD
      properly to see whether structured Offer / MenuItem prices are
      present even though raw-text regex missed them.

Outputs a short markdown digest appended to coverage_report.md so the
matrix in the repo stays the single source of truth.
"""
import json
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
HDR  = {'User-Agent': 'UIFPI-research-probe (academic)'}

CDX_TIMEOUT   = 90
CDX_LIMIT     = 30000
CDX_RETRIES   = 2
CDX_BACKOFF   = 15
FETCH_TIMEOUT = 45
FETCH_DELAY   = 3.0
SAMPLES_PER_PLATFORM = 5

# (1) Vietnam alternatives
VN_PATTERNS = [
    ('foody.vn slug',         'foody.vn/*-restaurant*'),
    ('foody.vn bare',         'foody.vn/*/'),
    ('foody.vn restaurant',   'foody.vn/restaurant/*'),
    ('foody.vn rest path',    'foody.vn/ho-chi-minh/*/restaurant'),
    ('vn tripadvisor HCMC',   'tripadvisor.com/Restaurant_Review-g293925*'),
    ('vn tripadvisor Hanoi',  'tripadvisor.com/Restaurant_Review-g293924*'),
]

# (2) JSON-LD deep-parse re-probes
LD_REPROBE = [
    ('allmenus restaurant page',  'allmenus.com/*/restaurant*', 'USD'),
    ('allmenus city slug',        'allmenus.com/il/chicago/*',  'USD'),
    ('wongnai restaurants',       'wongnai.com/restaurants/*',  'THB'),
    ('dineout restaurants',       'dineout.co.in/*-restaurants', 'INR'),
    ('qraved jakarta restaurants','qraved.com/jakarta/*-restaurant*', 'IDR'),
]


def cdx_query(pattern, frm='20180101', to='20260601'):
    params = {
        'url': pattern, 'from': frm, 'to': to,
        'output': 'json', 'fl': 'timestamp,original',
        'filter': ['statuscode:200', 'mimetype:text/html'],
        'limit': CDX_LIMIT,
    }
    last_err = None
    for attempt in range(CDX_RETRIES + 1):
        try:
            r = requests.get(CDX, params=params, headers=HDR, timeout=CDX_TIMEOUT)
            if r.status_code != 200:
                last_err = f'HTTP {r.status_code}'
                if r.status_code in (429, 503, 504) and attempt < CDX_RETRIES:
                    time.sleep(CDX_BACKOFF); continue
                return None, last_err
            data = r.json()
            return ([(row[0], row[1]) for row in data[1:]] if len(data) > 1 else []), None
        except Exception as e:
            last_err = str(e)[:80]
            if attempt < CDX_RETRIES:
                time.sleep(CDX_BACKOFF)
    return None, last_err


def fetch_archived(ts, url):
    try:
        r = requests.get(f'{WBM}/{ts}id_/{url}', headers=HDR, timeout=FETCH_TIMEOUT)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def parse_jsonld_prices(html):
    """Walk JSON-LD and extract any (name, price, currency) tuples found in
    nested Offer, MenuItem, or PriceSpecification structures."""
    if not html:
        return []
    out = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I,
    ):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        def walk(node, name_ctx=None):
            if isinstance(node, dict):
                nm = node.get('name') or name_ctx
                # MenuItem / Offer / Product with price + name
                p = (node.get('price') or
                     (node.get('offers', {}) if isinstance(node.get('offers'), dict) else {}).get('price') or
                     (node.get('priceSpecification', {}) if isinstance(node.get('priceSpecification'), dict) else {}).get('price'))
                if nm and p is not None:
                    try:
                        pf = float(re.sub(r'[^\d.]', '', str(p))) if str(p) else None
                    except Exception:
                        pf = None
                    if pf and pf > 0:
                        out.append((str(nm)[:80], pf))
                for v in node.values():
                    walk(v, nm)
            elif isinstance(node, list):
                for v in node:
                    walk(v, name_ctx)
        walk(obj)
    # Dedup
    seen = set(); uniq = []
    for n, p in out:
        k = (n, round(p, 2))
        if k in seen: continue
        seen.add(k); uniq.append((n, p))
    return uniq


def main():
    rnd = random.Random(20260616)
    digest_lines = []
    digest_lines.append('\n## Phase 0 re-probe — '
                        f'{datetime.now().strftime("%Y-%m-%d %H:%M")}\n')

    print('=== (1) Vietnam alternative patterns ===\n')
    digest_lines.append('### (1) Vietnam alternative URL patterns\n')
    digest_lines.append('| Pattern | ≥2-cap restaurants | Snapshots | '
                        'Sample $-hits | Sample bytes | Notes |\n')
    digest_lines.append('|---|---:|---:|---:|---:|---|\n')
    vnd_re = re.compile(r'\d+(?:\.\d{3})*\s?₫|\d+(?:\.\d{3})*\s?VND')
    for label, pat in VN_PATTERNS:
        print(f'[{label}] {pat}')
        rows, err = cdx_query(pat)
        if err or rows is None:
            print(f'  CDX error: {err}')
            digest_lines.append(f'| `{pat}` | — | — | — | — | error:{err} |\n')
            time.sleep(2); continue
        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        ge2 = [u for u, ts_list in per_url.items() if len(ts_list) >= 2]
        print(f'  {len(per_url)} distinct URLs, {len(ge2)} ≥2-cap, {len(rows)} snapshots')
        # Sample one page if any
        sample_kb, sample_hits, notes = '', '', ''
        if per_url:
            u = rnd.choice(list(per_url))
            ts = per_url[u][len(per_url[u]) // 2]
            time.sleep(FETCH_DELAY)
            html = fetch_archived(ts, u)
            if html is not None:
                sample_kb = len(html.encode('utf-8')) // 1024
                sample_hits = len(vnd_re.findall(html))
                if sample_kb < 5:
                    notes = 'tiny sample (redirect/stub)'
                print(f'  sample {sample_kb} KB, {sample_hits} VND hits')
            else:
                notes = 'sample fetch failed'
                print(f'  sample fetch failed')
        digest_lines.append(
            f'| `{pat}` | {len(ge2):,} | {len(rows):,} | {sample_hits} | '
            f'{sample_kb} | {notes} |\n'
        )
        time.sleep(3)

    print('\n=== (2) JSON-LD deep-parse re-probes ===\n')
    digest_lines.append('\n### (2) JSON-LD deep-parse re-probes (5 samples each)\n')
    digest_lines.append('| Platform | Pattern | ≥2-cap restaurants | '
                        'Samples with LD prices | Mean LD prices/sample | '
                        'Example item, price |\n')
    digest_lines.append('|---|---|---:|---:|---:|---|\n')
    for label, pat, currency in LD_REPROBE:
        print(f'[{label}] {pat}')
        rows, err = cdx_query(pat)
        if err or rows is None:
            print(f'  CDX error: {err}')
            digest_lines.append(f'| {label} | `{pat}` | — | — | — | error:{err} |\n')
            time.sleep(2); continue
        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        ge2 = [u for u, ts_list in per_url.items() if len(ts_list) >= 2]
        if not per_url:
            print(f'  0 URLs')
            digest_lines.append(f'| {label} | `{pat}` | 0 | — | — | empty |\n')
            time.sleep(2); continue
        # Sample SAMPLES_PER_PLATFORM
        urls = list(per_url)
        sample = rnd.sample(urls, min(SAMPLES_PER_PLATFORM, len(urls)))
        total_prices = 0
        n_with = 0
        example = ''
        for u in sample:
            ts = per_url[u][len(per_url[u]) // 2]
            time.sleep(FETCH_DELAY)
            html = fetch_archived(ts, u)
            ld = parse_jsonld_prices(html) if html else []
            if ld:
                n_with += 1
                total_prices += len(ld)
                if not example:
                    nm, pr = ld[0]
                    example = f'`{nm[:40]}` @ {pr}'
            print(f'  sample {ts[:8]} {u[:60]} → {len(ld)} LD prices')
        mean_prices = total_prices / len(sample) if sample else 0
        digest_lines.append(
            f'| {label} | `{pat}` | {len(ge2):,} | '
            f'{n_with}/{len(sample)} | {mean_prices:.1f} | {example} |\n'
        )
        time.sleep(3)

    # Append digest to coverage_report.md
    md_path = os.path.join(BASE, 'coverage_report.md')
    with open(md_path, 'a') as fh:
        fh.write(''.join(digest_lines))
    print(f'\nDigest appended to {md_path}')


if __name__ == '__main__':
    main()

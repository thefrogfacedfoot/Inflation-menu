"""
Phase 0 — SG + UK month-depth backfill probe.

These are the two countries with the strongest item counts but the
thinnest month coverage (SG: 9 months / 8,674 items; UK: 6 months /
1,150 items). We probe additional Wayback URL patterns that, if
yielding, could extend the historical series without touching the
country roster.

  SG : Deliveroo SG (deliveroo.com.sg)
       Foodpanda SG per-restaurant routes
       HungryGoWhere dining-guide
  UK : Deliveroo UK
       JustEat UK
       Foodhub UK

Same yields-table format as coverage_report.md. NO scraping triggered.
Output: coverage_report_sg_uk_backfill.{csv,md}
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
HDR  = {'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'}
WINDOW_FROM = '20180101'
WINDOW_TO   = '20260601'

CDX_TIMEOUT, CDX_LIMIT, CDX_DELAY = 90, 30000, 4.0
CDX_RETRIES, CDX_RETRY_BACKOFF = 2, 15
FETCH_TIMEOUT, FETCH_DELAY = 45, 2.5

PROBES = [
    # SG — Deliveroo + Foodpanda restaurant detail + HungryGoWhere
    ('Singapore', 'formal', 'deliveroo SG',         'deliveroo.com.sg/menu/*',                'SGD'),
    ('Singapore', 'formal', 'deliveroo SG (slug)',  'deliveroo.com.sg/menu/singapore/*',      'SGD'),
    ('Singapore', 'formal', 'foodpanda SG menu',    'foodpanda.sg/menu/*',                    'SGD'),
    ('Singapore', 'formal', 'foodpanda SG rest',    'foodpanda.sg/restaurant/*',              'SGD'),
    ('Singapore', 'formal', 'hungrygowhere',        'hungrygowhere.com/*-restaurant-*',       'SGD'),
    # UK — Deliveroo + JustEat + Foodhub
    ('United Kingdom', 'formal', 'deliveroo UK',         'deliveroo.co.uk/menu/*',           'GBP'),
    ('United Kingdom', 'formal', 'deliveroo UK london',  'deliveroo.co.uk/menu/london/*',    'GBP'),
    ('United Kingdom', 'formal', 'just-eat UK',          'just-eat.co.uk/restaurants-*/menu', 'GBP'),
    ('United Kingdom', 'formal', 'just-eat UK alt',      'just-eat.co.uk/restaurants/*',     'GBP'),
    ('United Kingdom', 'formal', 'foodhub UK',           'foodhub.co.uk/*-menu',             'GBP'),
]

CURRENCY_REGEXES = {
    'SGD': re.compile(r'(?:S\$|SGD\s?)\s?\d+(?:\.\d{2})?'),
    'GBP': re.compile(r'£\s?\d+(?:\.\d{2})?'),
}


def query_cdx(pattern):
    params = {
        'url': pattern, 'from': WINDOW_FROM, 'to': WINDOW_TO,
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
                    time.sleep(CDX_RETRY_BACKOFF); continue
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


def sample_page(ts, url, cre):
    raw = f"{WBM}/{ts}id_/{url}"
    try:
        r = requests.get(raw, headers=HDR, timeout=FETCH_TIMEOUT)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}'
        text = r.text
        hits = len(cre.findall(text))
        ld = 'application/ld+json' in text
        nd = '__NEXT_DATA__' in text
        bl = text.lower(); block = ''
        if len(text) < 400:
            block = 'tiny-page'
        elif 'cloudflare' in bl and ('attention required' in bl or 'verify' in bl):
            block = 'cloudflare-challenge'
        elif 'captcha' in bl or 'recaptcha' in bl:
            block = 'captcha'
        return {'kb': len(r.content)//1024, 'price_hits': hits,
                'json_ld': ld, 'next_data': nd, 'block': block}, None
    except Exception as e:
        return None, str(e)[:60]


def main():
    print(f"Phase 0 SG/UK backfill probe — {len(PROBES)} pairs", flush=True)
    results = []
    rnd = random.Random(20260618)
    for i, (country, sector, platform, pat, cur) in enumerate(PROBES, 1):
        print(f"[{i:>2}/{len(PROBES)}] {country:<14} {platform:<25} {pat}", flush=True)
        rows, err = query_cdx(pat)
        rec = {'country': country, 'sector': sector, 'platform': platform,
               'pattern': pat, 'currency': cur,
               'n_restaurants_ge2': 0, 'n_snapshots': 0,
               'distinct_urls': 0, 'earliest': '', 'latest': '',
               'cdx_status': '', 'sample_url': '', 'sample_ts': '',
               'sample_kb': '', 'sample_price_hits': '',
               'sample_json_ld': '', 'sample_next_data': '',
               'sample_block': '', 'sample_status': ''}
        if err:
            print(f"          CDX ERROR: {err}", flush=True)
            rec['cdx_status'] = f'error:{err}'
            results.append(rec); time.sleep(CDX_DELAY); continue
        if not rows:
            print(f"          0 rows", flush=True)
            rec['cdx_status'] = 'empty'
            results.append(rec); time.sleep(CDX_DELAY); continue
        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        ge2 = [u for u, t in per_url.items() if len(t) >= 2]
        all_ts = sorted(t for ts_list in per_url.values() for t in ts_list)
        rec.update({
            'n_restaurants_ge2': len(ge2), 'n_snapshots': len(rows),
            'distinct_urls': len(per_url),
            'earliest': all_ts[0][:8] if all_ts else '',
            'latest':   all_ts[-1][:8] if all_ts else '',
            'cdx_status': 'truncated' if len(rows) >= CDX_LIMIT else 'ok',
        })
        trunc = ' (TRUNC)' if len(rows) >= CDX_LIMIT else ''
        print(f"          {len(per_url):>6} URLs, {len(ge2):>5} ≥2-cap, "
              f"{len(rows):>6} snaps, {rec['earliest']}-{rec['latest']}{trunc}",
              flush=True)
        cands = ge2 if ge2 else list(per_url.keys())
        s_url = rnd.choice(cands)
        s_ts = per_url[s_url][len(per_url[s_url]) // 2]
        cre = CURRENCY_REGEXES.get(cur)
        time.sleep(FETCH_DELAY)
        print(f"          sampling {s_ts} {s_url[:60]}", flush=True)
        s, ferr = sample_page(s_ts, s_url, cre)
        rec['sample_url'] = s_url; rec['sample_ts'] = s_ts
        if ferr:
            rec['sample_status'] = f'error:{ferr}'
            print(f"          sample fetch failed: {ferr}", flush=True)
        else:
            rec.update({
                'sample_kb': s['kb'], 'sample_price_hits': s['price_hits'],
                'sample_json_ld': 'Y' if s['json_ld'] else 'N',
                'sample_next_data': 'Y' if s['next_data'] else 'N',
                'sample_block': s['block'],
                'sample_status': 'ok' if not s['block'] else f'block:{s["block"]}',
            })
            bs = f' BLOCK={s["block"]}' if s['block'] else ''
            print(f"          {s['kb']}KB, {s['price_hits']} {cur} hits, "
                  f"LD={s['json_ld']} ND={s['next_data']}{bs}", flush=True)
        results.append(rec); time.sleep(CDX_DELAY)

    csv_path = os.path.join(BASE, 'coverage_report_sg_uk_backfill.csv')
    fns = ['country','sector','platform','pattern','currency',
           'n_restaurants_ge2','n_snapshots','distinct_urls',
           'earliest','latest','cdx_status',
           'sample_url','sample_ts','sample_kb',
           'sample_price_hits','sample_json_ld','sample_next_data',
           'sample_block','sample_status']
    with open(csv_path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fns)
        w.writeheader(); w.writerows(results)
    print(f"\nCSV → {csv_path}", flush=True)

    md_path = os.path.join(BASE, 'coverage_report_sg_uk_backfill.md')
    with open(md_path, 'w') as fh:
        fh.write("# Phase 0 — SG + UK month-depth backfill probe\n\n")
        fh.write(f"Generated: {datetime.now().isoformat()}\n  \n")
        fh.write(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n  \n")
        fh.write("Probes new Wayback URL patterns aimed at extending the\n"
                 "month-coverage of SG (9 mo / 8,674 items today) and UK\n"
                 "(6 mo / 1,150 items). Same yields-table format as\n"
                 "`coverage_report.md`. NO scraping triggered by this run.\n\n")
        fh.write("## Matrix\n\n")
        fh.write("| Country | Platform | URL pattern | ≥2-cap restaurants | "
                 "Snapshots | Range | Sample KB | Sample $-hits | LD | ND | "
                 "Block | Notes |\n")
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

        fh.write("\n## Decision\n\n")
        fh.write("A (source, country) pair is **queue-worthy** only when\n"
                 "BOTH ≥2-cap ≥ 15 **and** sample $-hits ≥ 5 **and** Block is\n"
                 "empty.\n\n")
        roll = {}
        for r in results:
            if (r.get('sample_status') or '').startswith('error:'):
                continue
            c = r['country']
            best = roll.get(c)
            if (best is None or
                (r['n_restaurants_ge2'], r['sample_price_hits'] or 0) >
                (best['n_restaurants_ge2'], best['sample_price_hits'] or 0)):
                roll[c] = r
        fh.write("| Country | Best platform | ≥2-cap | $-hits | Block | Verdict |\n")
        fh.write("|---|---|---:|---:|---|---|\n")
        for c in sorted(roll):
            r = roll[c]
            blocked = (r.get('sample_block') or '') != ''
            ok = (r['n_restaurants_ge2'] >= 15 and
                  (r['sample_price_hits'] or 0) >= 5 and not blocked)
            verdict = ('✓ queue (await user OK)' if ok else
                       'bail (bot-blocked)' if blocked else
                       'bail (no prices visible)')
            fh.write(f"| {c} | {r['platform']} | {r['n_restaurants_ge2']:,} | "
                     f"{r['sample_price_hits']} | "
                     f"{r.get('sample_block') or '—'} | {verdict} |\n")
    print(f"MD  → {md_path}", flush=True)


if __name__ == '__main__':
    main()

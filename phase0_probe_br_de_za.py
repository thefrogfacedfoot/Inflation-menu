"""
Phase 0 — Wayback CDX coverage probe for new candidate countries
(Brazil, Germany, South Africa). Same matrix format as
coverage_report.md so results slot directly alongside the original
8-country panel.

Output: coverage_report_br_de_za.{csv,md}
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
    # Brazil (BRL) — iFood is the dominant aggregator; Rappi entered later.
    ('Brazil',       'formal', 'tripadvisor BR',   'tripadvisor.com.br/Restaurant_Review*', 'BRL'),
    ('Brazil',       'formal', 'ifood SP',         'ifood.com.br/delivery/sao-paulo-sp/*',  'BRL'),
    ('Brazil',       'formal', 'ifood RJ',         'ifood.com.br/delivery/rio-de-janeiro-rj/*', 'BRL'),
    ('Brazil',       'formal', 'rappi BR',         'rappi.com.br/restaurantes/*',           'BRL'),
    ('Brazil',       'formal', 'ubereats BR',      'ubereats.com/br/*',                     'BRL'),
    # Germany (EUR) — Lieferando = JET DE; Wolt entered ~2020.
    ('Germany',      'formal', 'tripadvisor DE',   'tripadvisor.de/Restaurant_Review*',     'EUR'),
    ('Germany',      'formal', 'lieferando',       'lieferando.de/speisekarte/*',           'EUR'),
    ('Germany',      'formal', 'wolt DE',          'wolt.com/de/deu/*',                     'EUR'),
    ('Germany',      'formal', 'ubereats DE',      'ubereats.com/de/*',                     'EUR'),
    ('Germany',      'formal', 'yelp DE',          'yelp.de/biz/*',                         'EUR'),
    # South Africa (ZAR) — Mr D Food (Takealot), Uber Eats.
    ('South Africa', 'formal', 'tripadvisor ZA',   'tripadvisor.co.za/Restaurant_Review*',  'ZAR'),
    ('South Africa', 'formal', 'mrdfood',          'mrdfood.com/*',                         'ZAR'),
    ('South Africa', 'formal', 'ubereats ZA',      'ubereats.com/za/*',                     'ZAR'),
    ('South Africa', 'formal', 'eatout ZA',        'eatout.co.za/listings/*',               'ZAR'),
]

CURRENCY_REGEXES = {
    'BRL': re.compile(r'R\$\s?\d+(?:[.,]\d{2})?'),
    'EUR': re.compile(r'(?:€|EUR)\s?\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s?€'),
    'ZAR': re.compile(r'\bR\s?\d+(?:[.,]\d{2})?'),
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
        bytes_kb = len(r.content) // 1024
        return {'kb': bytes_kb, 'price_hits': n_price,
                'json_ld': has_ld, 'next_data': has_nd}, None
    except Exception as e:
        return None, str(e)[:60]


def main():
    print(f"Phase 0 probe (BR/DE/ZA) — {len(PROBES)} pairs")
    print(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n")

    results = []
    rnd = random.Random(20260617)

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

    csv_path = os.path.join(BASE, 'coverage_report_br_de_za.csv')
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

    md_path = os.path.join(BASE, 'coverage_report_br_de_za.md')
    with open(md_path, 'w') as fh:
        fh.write(f"# Phase 0 — BR / DE / ZA candidate-country probe\n\n")
        fh.write(f"Generated: {datetime.now().isoformat()}\n  \n")
        fh.write(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n  \n")
        fh.write(f"CDX limit per query: {CDX_LIMIT:,} "
                 f"(rows ≥ limit = truncated).\n\n")
        fh.write("Same yields-table format as `coverage_report.md`. Each row "
                 "probes one (country, platform) pair: counts distinct archived "
                 "URLs and snapshots in-window, then fetches one sample archived "
                 "page (id_ raw, no Wayback toolbar) and counts currency-shaped "
                 "price tokens in the static HTML.\n\n")
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
                 "more captures inside the window. Gating metric for the formal-sector "
                 "roster (≥15 required).\n")
        fh.write("- `Sample $-hits` = currency-token count in ONE randomly-chosen "
                 "archived page. Low or zero hits ⇒ HTML doesn't contain prices "
                 "(JS shell that loaded prices via API after render).\n")
        fh.write("- `LD` / `ND` = JSON-LD or `__NEXT_DATA__` present; either gives "
                 "a clean structured-data path.\n")
        fh.write("- A country clears the formal threshold only when BOTH "
                 "≥2-cap ≥ 15 **and** sample $-hits ≥ 5.\n")
    print(f"MD  → {md_path}")
    print(f"\nDone.")


if __name__ == '__main__':
    main()

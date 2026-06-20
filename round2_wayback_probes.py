"""
Round-2 Wayback CDX probes for Sources 2, 4, 5.

Source 2: food blogger archives for SG/MY/ID/TH/IN
Source 4: menupages.com + allmenus.com re-probe per-country
Source 5: yelp.com/biz/* with 2012-2016 timestamp filter

Each query is single-shot (no per-window distribution) to avoid the
broad-pattern throttle. Saves yields to a JSON for downstream compile.
"""
import requests, time, json, re
from collections import defaultdict

CDX = 'http://web.archive.org/cdx/search/cdx'
HDR = {'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'}

# (label, pattern, from, to, currency_re, country)
PROBES = [
    # Source 2 — Food bloggers
    ('blogspot-hawker-sg',         '*.blogspot.com/*hawker*',     '20120101', '20240101',
     r'(?:S\$|SGD\s?)\s?\d+(?:\.\d{2})?',  'Singapore'),
    ('blogspot-nasi-lemak-my',     '*.blogspot.com/*nasi-lemak*', '20120101', '20240101',
     r'RM\s?\d+(?:\.\d{2})?',              'Malaysia'),
    ('wordpress-street-food-sea',  '*.wordpress.com/*street-food*','20120101', '20240101',
     r'(?:S\$|SGD|RM|Rp|฿|THB|₹|Rs\.?\s)\s?\d+(?:[.,]\d{2,3})?', 'mixed'),
    ('blogspot-makan-sg',          '*.blogspot.com/*makan*',      '20120101', '20240101',
     r'S\$\s?\d+(?:\.\d{2})?',             'Singapore'),
    ('blogspot-warung-id',         '*.blogspot.com/*warung*',     '20120101', '20240101',
     r'Rp\.?\s?\d+(?:[.,]\d{3})*',         'Indonesia'),
    ('blogspot-bangkok-th',        '*.blogspot.com/*bangkok*',    '20120101', '20240101',
     r'(?:฿|THB|baht)\s?\d+',              'Thailand'),
    # Source 4 — menupages / allmenus per-country recheck
    ('menupages-uk',               'menupages.co.uk/*',           '20100101', '20180101',
     r'£\s?\d+\.\d{2}',                    'United Kingdom'),
    ('menupages-au',               'menupages.com.au/*',          '20100101', '20180101',
     r'A?\$\s?\d+\.\d{2}',                 'Australia'),
    ('allmenus-uk',                'allmenus.co.uk/*',            '20100101', '20180101',
     r'£\s?\d+\.\d{2}',                    'United Kingdom'),
    # Source 5 — Yelp 2012-2016 (server-rendered pre-SPA era)
    ('yelp-biz-2012-2016',         'yelp.com/biz/*',              '20120101', '20161231',
     r'\$\s?\d+(?:\.\d{2})?',              'United States'),
    ('yelp-menu-2012-2016',        'yelp.com/menu/*',             '20120101', '20161231',
     r'\$\s?\d+(?:\.\d{2})?',              'United States'),
]


def probe(label, pattern, t_from, t_to, currency_re, country):
    rec = {'label': label, 'pattern': pattern, 'from': t_from, 'to': t_to,
           'country': country, 'distinct_urls': 0, 'snapshots': 0,
           'sample_url': '', 'sample_ts': '', 'sample_kb': 0,
           'sample_currency_hits': 0, 'sample_has_ld': False,
           'sample_has_nd': False, 'sample_blocked': '',
           'cdx_status': '', 'sample_status': ''}
    params = {
        'url': pattern, 'from': t_from, 'to': t_to,
        'output': 'json', 'fl': 'timestamp,original,length',
        'filter': ['statuscode:200', 'mimetype:text/html'],
        'collapse': 'urlkey',
        'limit': 500,
    }
    try:
        r = requests.get(CDX, params=params, headers=HDR, timeout=60)
        if r.status_code != 200:
            rec['cdx_status'] = f'HTTP {r.status_code}'
            return rec
        data = r.json()
        rows = data[1:] if len(data) > 1 else []
        rec['distinct_urls'] = len(rows)
        rec['snapshots'] = len(rows)
        rec['cdx_status'] = 'ok' if rows else 'empty'
        if not rows:
            return rec
        # Sample the biggest by size
        rows_sorted = sorted(rows, key=lambda r: -(int(r[2]) if str(r[2]).isdigit() else 0))
        ts, url, sz = rows_sorted[0][0], rows_sorted[0][1], rows_sorted[0][2]
        rec['sample_url'] = url; rec['sample_ts'] = ts
        try:
            rr = requests.get(f'https://web.archive.org/web/{ts}id_/{url}',
                              headers=HDR, timeout=45)
            rec['sample_kb'] = len(rr.content) // 1024
            if rr.status_code != 200:
                rec['sample_status'] = f'HTTP {rr.status_code}'
                return rec
            text = rr.text
            cre = re.compile(currency_re)
            rec['sample_currency_hits'] = len(cre.findall(text))
            rec['sample_has_ld'] = 'application/ld+json' in text
            rec['sample_has_nd'] = '__NEXT_DATA__' in text
            bl = text.lower()
            if len(text) < 400: rec['sample_blocked'] = 'tiny-page'
            elif 'cloudflare' in bl and ('attention required' in bl or 'verify' in bl):
                rec['sample_blocked'] = 'cloudflare'
            elif 'captcha' in bl or 'recaptcha' in bl: rec['sample_blocked'] = 'captcha'
            rec['sample_status'] = 'ok' if not rec['sample_blocked'] else f'block:{rec["sample_blocked"]}'
        except Exception as e:
            rec['sample_status'] = f'err:{str(e)[:50]}'
    except Exception as e:
        rec['cdx_status'] = f'err:{str(e)[:60]}'
    return rec


results = []
for p in PROBES:
    label = p[0]
    print(f"[probe] {label}", flush=True)
    r = probe(*p)
    if r['cdx_status'] == 'ok':
        print(f"  {r['distinct_urls']:>5} URLs, sample {r['sample_kb']}KB "
              f"hits={r['sample_currency_hits']} LD={r['sample_has_ld']} "
              f"ND={r['sample_has_nd']} block={r['sample_blocked']}",
              flush=True)
    else:
        print(f"  cdx={r['cdx_status']}", flush=True)
    results.append(r)
    time.sleep(3.0)

with open('/tmp/round2_probes.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved /tmp/round2_probes.json: {len(results)} probes")

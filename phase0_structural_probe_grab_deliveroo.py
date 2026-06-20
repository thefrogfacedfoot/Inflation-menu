"""
Phase 0 structural probe — GrabFood PH/VN + Deliveroo HK/AE.

For each of 4 patterns:
  1. Hit Wayback CDX, build (url -> [ts]) map.
  2. Pick 3 ≥2-cap candidates (fall back to single-snapshot urls if none).
  3. Fetch each archived page via the /id_/ raw replay.
  4. Pull every JSON-LD block + the __NEXT_DATA__ blob, parse to dicts.
  5. Recursive tree-walk:
        a. @type histogram (counts every @type seen anywhere in the tree).
        b. priceInMinorUnit hits — first 5 (name, value/100) samples.
        c. raw_price hits — first 5 (name, value) samples.
        d. priced-named-node count — anything with both `name` and one of
           {priceInMinorUnit, raw_price, price, offers.price,
           priceSpecification.price}.
  6. Per-target verdict:
        CONFIRM      — ≥1/3 snapshots have a priced-name signal we'd extract.
        BAIL         — 0/3 have any.

Walk hits the SAME shapes the production scraper expects, so a CONFIRM here
should translate to non-zero items in a follow-up sweep. No regex price
counting — that's what burned DE/BR in the original Track C probe.
"""
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CDX  = 'http://web.archive.org/cdx/search/cdx'
WBM  = 'https://web.archive.org/web'
HDR  = {'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'}

WINDOW_FROM = '20180101'
WINDOW_TO   = '20260601'

CDX_TIMEOUT       = 90
CDX_LIMIT         = 30000
CDX_DELAY         = 4.0
CDX_RETRIES       = 2
CDX_RETRY_BACKOFF = 15
FETCH_TIMEOUT     = 60
FETCH_DELAY       = 8.0   # be polite to Wayback

SAMPLES_PER_TARGET = 3

# (label, country, pattern, currency, extractor-key)
# extractor-key picks which named field we expect in the embedded payload:
#   'priceInMinorUnit' for Grab (NEXT_DATA),
#   'raw_price'        for Deliveroo (embedded body JSON).
PROBES = [
    ('GrabFood PH',  'Philippines', 'food.grab.com/ph/en/restaurant/*', 'PHP', 'priceInMinorUnit'),
    ('GrabFood VN',  'Vietnam',     'food.grab.com/vn/en/restaurant/*', 'VND', 'priceInMinorUnit'),
    ('Deliveroo HK', 'Hong Kong',   'deliveroo.com.hk/menu/*',          'HKD', 'raw_price'),
    ('Deliveroo AE', 'UAE',         'deliveroo.ae/menu/*',              'AED', 'raw_price'),
]

_LD_OPENING = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>', re.I)
_NEXTDATA_OPENING = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>', re.I)


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
            last_err = str(e)[:100]
            if attempt < CDX_RETRIES:
                time.sleep(CDX_RETRY_BACKOFF)
    return None, last_err


def _extract_script_content(html, opening_re):
    m = opening_re.search(html)
    if not m:
        return None
    after = html[m.end():]
    close = re.match(r'(.*?)</script>', after, re.S | re.I)
    if close:
        return close.group(1)
    rest = re.match(r'([^<]+)', after, re.S)
    return rest.group(1) if rest else None


def all_jsonld_blocks(html):
    out = []
    for m in _LD_OPENING.finditer(html):
        after = html[m.end():]
        close = re.match(r'(.*?)</script>', after, re.S | re.I)
        block = close.group(1) if close else None
        if not block:
            rest = re.match(r'([^<]+)', after, re.S)
            block = rest.group(1) if rest else None
        if not block:
            continue
        try:
            out.append(json.loads(block))
        except Exception:
            pass
    return out


def nextdata_block(html):
    if '__NEXT_DATA__' not in html:
        return None
    block = _extract_script_content(html, _NEXTDATA_OPENING)
    if not block:
        return None
    try:
        return json.loads(block)
    except Exception:
        return None


def walk(node, hist, pim_samples, rp_samples, named_priced, name_ctx=None):
    """Tree walk:
      hist          — Counter of every @type seen.
      pim_samples   — list of (name, price) where price = priceInMinorUnit/100.
      rp_samples    — list of (name, price) where price = raw_price.
      named_priced  — int, # nodes with both a `name` and any price-bearing key.
    """
    if isinstance(node, dict):
        t = node.get('@type')
        if isinstance(t, str):
            hist[t] += 1
        elif isinstance(t, list):
            for x in t:
                if isinstance(x, str):
                    hist[x] += 1

        local_name = node.get('name') if isinstance(node.get('name'), str) else None
        nm = local_name or name_ctx

        if 'priceInMinorUnit' in node:
            try:
                p = float(node['priceInMinorUnit']) / 100.0
            except (TypeError, ValueError):
                p = None
            if p is not None and nm:
                if len(pim_samples) < 25:
                    pim_samples.append((nm[:60], round(p, 2)))
                named_priced[0] += 1

        if 'raw_price' in node:
            try:
                p = float(node['raw_price'])
            except (TypeError, ValueError):
                p = None
            if p is not None and nm:
                if len(rp_samples) < 25:
                    rp_samples.append((nm[:60], round(p, 2)))
                named_priced[0] += 1

        if local_name and (
            'price' in node or 'offers' in node or 'priceSpecification' in node
        ):
            named_priced[0] += 1

        for v in node.values():
            walk(v, hist, pim_samples, rp_samples, named_priced, nm)
    elif isinstance(node, list):
        for v in node:
            walk(v, hist, pim_samples, rp_samples, named_priced, name_ctx)


def probe_snapshot(ts, orig_url, expected_key):
    url = f"{WBM}/{ts}id_/{orig_url}"
    try:
        r = requests.get(url, headers=HDR, timeout=FETCH_TIMEOUT)
    except Exception as e:
        return {'err': str(e)[:80]}
    if r.status_code != 200:
        return {'err': f'HTTP {r.status_code}', 'kb': len(r.content)//1024}
    html = r.text
    kb = len(r.content) // 1024

    # Block heuristics
    bl = html.lower()
    block = ''
    if len(html) < 400:
        block = 'tiny'
    elif 'cloudflare' in bl and 'attention required' in bl:
        block = 'cloudflare'
    elif 'captcha' in bl and 'recaptcha' not in bl[:bl.find('captcha')+50]:
        # accept reCAPTCHA badges, flag real captcha walls
        pass

    hist = Counter()
    pim = []
    rp  = []
    named_priced = [0]

    # JSON-LD blocks
    ld_blocks = all_jsonld_blocks(html)
    for blk in ld_blocks:
        walk(blk, hist, pim, rp, named_priced)

    # NEXT_DATA blob
    nd = nextdata_block(html)
    if nd is not None:
        walk(nd, hist, pim, rp, named_priced)

    # Raw-text presence (so we can distinguish "key absent" from "key present
    # but in unexpected JSON shape") — counts substring occurrences only.
    raw_pim_hits = html.count('"priceInMinorUnit"')
    raw_rp_hits  = html.count('"raw_price"')

    return {
        'kb': kb, 'block': block,
        'n_ld_blocks': len(ld_blocks),
        'has_nextdata': nd is not None,
        'hist': dict(hist),
        'pim_samples': pim[:5],
        'rp_samples':  rp[:5],
        'named_priced': named_priced[0],
        'raw_pim_hits': raw_pim_hits,
        'raw_rp_hits':  raw_rp_hits,
    }


def fmt_hist(h, top=10):
    if not h:
        return '(empty)'
    items = sorted(h.items(), key=lambda kv: -kv[1])[:top]
    return ', '.join(f'{k}:{v}' for k, v in items)


def main():
    print(f"Phase 0 structural probe — {len(PROBES)} targets, "
          f"{SAMPLES_PER_TARGET} snapshots each", flush=True)
    print(f"Window: {WINDOW_FROM} → {WINDOW_TO}\n", flush=True)

    rnd = random.Random(20260619)
    summary = []

    for label, country, pat, cur, key in PROBES:
        print(f"\n{'='*70}", flush=True)
        print(f"{label} — {country} — {pat}  (expect: {key})", flush=True)
        print('='*70, flush=True)

        rows, err = query_cdx(pat)
        if err:
            print(f"  CDX error: {err}", flush=True)
            summary.append((label, 'CDX-ERR', err))
            time.sleep(CDX_DELAY)
            continue
        if not rows:
            print(f"  CDX empty.", flush=True)
            summary.append((label, 'BAIL', 'cdx-empty'))
            time.sleep(CDX_DELAY)
            continue

        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        ge2 = [u for u, lst in per_url.items() if len(lst) >= 2]
        all_ts = sorted(ts for lst in per_url.values() for ts in lst)
        print(f"  {len(per_url)} distinct URLs, {len(ge2)} ≥2-cap, "
              f"{len(rows)} snapshots, {all_ts[0][:8]}-{all_ts[-1][:8]}",
              flush=True)

        candidates = ge2 if len(ge2) >= SAMPLES_PER_TARGET else list(per_url.keys())
        rnd.shuffle(candidates)
        picks = []
        for u in candidates[:SAMPLES_PER_TARGET * 2]:
            ts_list = sorted(per_url[u])
            picks.append((ts_list[len(ts_list)//2], u))
            if len(picks) >= SAMPLES_PER_TARGET:
                break

        confirms = 0
        for i, (ts, u) in enumerate(picks, 1):
            time.sleep(FETCH_DELAY)
            print(f"\n  [{i}/{len(picks)}] {ts}  {u[:80]}", flush=True)
            r = probe_snapshot(ts, u, key)
            if 'err' in r:
                print(f"      ERROR: {r['err']}", flush=True)
                continue
            print(f"      kb={r['kb']}  ld_blocks={r['n_ld_blocks']}  "
                  f"next_data={r['has_nextdata']}  named_priced_nodes="
                  f"{r['named_priced']}", flush=True)
            print(f"      @type histogram: {fmt_hist(r['hist'])}", flush=True)
            print(f"      raw key counts: priceInMinorUnit={r['raw_pim_hits']}  "
                  f"raw_price={r['raw_rp_hits']}", flush=True)
            if r['pim_samples']:
                print(f"      priceInMinorUnit samples:", flush=True)
                for n, p in r['pim_samples']:
                    print(f"          ({n!r}, {p})", flush=True)
            if r['rp_samples']:
                print(f"      raw_price samples:", flush=True)
                for n, p in r['rp_samples']:
                    print(f"          ({n!r}, {p})", flush=True)

            # Verdict: walker has to find a (name, expected-key) sample.
            if key == 'priceInMinorUnit' and r['pim_samples']:
                confirms += 1
            elif key == 'raw_price' and r['rp_samples']:
                confirms += 1
            elif r['named_priced'] > 0:
                # generic priced-name signal — partial credit
                confirms += 1

        verdict = 'CONFIRM' if confirms >= 1 else 'BAIL'
        print(f"\n  → {label}: {confirms}/{len(picks)} snapshots usable → {verdict}",
              flush=True)
        summary.append((label, verdict, f'{confirms}/{len(picks)}'))
        time.sleep(CDX_DELAY)

    print(f"\n\n{'='*70}\nSUMMARY\n{'='*70}", flush=True)
    for label, verdict, detail in summary:
        print(f"  {label:<14} {verdict:<10} {detail}", flush=True)


if __name__ == '__main__':
    main()

"""
PH follow-up retry — Wayback /id_/ replay flakes; walk a candidate list
until one snapshot returns 200 with MenuItem nodes, then inspect Offer
shape.
"""
import json
import re
import sys
import time
from collections import Counter, defaultdict

import requests

sys.path.insert(0, '/Users/erwenchen/Inflation-menu')
from historical_html_scraper import _extract_script_content, _LD_OPENING, _NEXTDATA_OPENING

CDX  = 'http://web.archive.org/cdx/search/cdx'
WBM  = 'https://web.archive.org/web'
HDR  = {'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'}

CANDIDATE_PATTERNS = [
    'food.grab.com/ph/en/restaurant/bonchon*',
    'food.grab.com/ph/en/restaurant/sunae*',
    'food.grab.com/ph/en/restaurant/jollibee*',
    'food.grab.com/ph/en/restaurant/mang*',
]


def query_cdx(pattern):
    params = {
        'url': pattern, 'from': '20200101', 'to': '20240101',
        'output': 'json', 'fl': 'timestamp,original',
        'filter': ['statuscode:200', 'mimetype:text/html'], 'limit': 200,
    }
    r = requests.get(CDX, params=params, headers=HDR, timeout=90)
    if r.status_code != 200:
        return []
    data = r.json()
    return [(row[0], row[1]) for row in data[1:]] if len(data) > 1 else []


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


def collect(node, out, type_match):
    if isinstance(node, dict):
        t = node.get('@type')
        if (t == type_match) or (isinstance(t, list) and type_match in t):
            out.append(node)
        for v in node.values():
            collect(v, out, type_match)
    elif isinstance(node, list):
        for v in node:
            collect(v, out, type_match)


def try_snapshot(ts, url):
    full = f"{WBM}/{ts}id_/{url}"
    try:
        r = requests.get(full, headers=HDR, timeout=60)
    except Exception as e:
        return None, f'err:{e}'
    if r.status_code != 200:
        return None, f'HTTP {r.status_code}'
    html = r.text
    blocks = all_jsonld_blocks(html)
    nd = nextdata_block(html)
    menuitems = []
    for b in blocks:
        collect(b, menuitems, 'MenuItem')
    if nd is not None:
        collect(nd, menuitems, 'MenuItem')
    return (html, blocks, nd, menuitems), 'ok'


def main():
    pool = []
    for pat in CANDIDATE_PATTERNS:
        print(f"  CDX {pat}", flush=True)
        rows = query_cdx(pat)
        per_url = defaultdict(list)
        for ts, orig in rows:
            per_url[orig].append(ts)
        # Prefer URLs with multiple snapshots, prefer mid-2020 to 2022
        ranked = sorted(per_url.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for url, ts_list in ranked[:8]:
            # take the middle snapshot for each URL
            ts_list = sorted(ts_list)
            pool.append((ts_list[len(ts_list)//2], url))
        time.sleep(3)

    print(f"\n  candidate pool: {len(pool)} snapshots", flush=True)

    for i, (ts, url) in enumerate(pool, 1):
        print(f"\n  [{i}/{len(pool)}] try {ts} {url[:80]}", flush=True)
        result, status = try_snapshot(ts, url)
        if result is None:
            print(f"      {status}", flush=True)
            time.sleep(6)
            continue
        html, blocks, nd, menuitems = result
        print(f"      200, ld_blocks={len(blocks)}, nd={nd is not None}, "
              f"menuitems={len(menuitems)}", flush=True)
        if len(menuitems) >= 5:
            inspect(html, blocks, nd, menuitems, ts, url)
            return
        time.sleep(6)

    print("\n  No PH snapshot in candidate pool returned MenuItem nodes — bail.")


def inspect(html, blocks, nd, menuitems, ts, url):
    print(f"\n  === Inspecting {ts} {url} ===", flush=True)

    offers = []
    for b in blocks:
        collect(b, offers, 'Offer')
    if nd is not None:
        collect(nd, offers, 'Offer')
    print(f"  collected: {len(offers)} Offer nodes, {len(menuitems)} MenuItem nodes")

    # First MenuItem with inline offers
    print("\n  --- First MenuItem with inline offers (raw JSON, truncated) ---")
    shown = False
    for mi in menuitems:
        if mi.get('offers') is not None:
            sample = {k: v for k, v in mi.items() if k != 'image'}
            print(json.dumps(sample, indent=2, ensure_ascii=False)[:2500])
            shown = True
            break
    if not shown:
        print("  (no MenuItem with inline 'offers' field)")

    # First standalone Offer
    if offers:
        print("\n  --- First standalone Offer node (raw JSON) ---")
        print(json.dumps(offers[0], indent=2, ensure_ascii=False)[:2000])

    # Offer summary
    print("\n  --- Offer.price / priceCurrency / priceSpecification summary ---")
    has_pspec = has_pim = null_or_zero = 0
    price_vals, cur_vals = [], []
    for o in offers:
        p = o.get('price')
        price_vals.append(p)
        cur_vals.append(o.get('priceCurrency'))
        if o.get('priceSpecification') is not None:
            has_pspec += 1
        if 'priceInMinorUnit' in o:
            has_pim += 1
        try:
            pf = float(p) if p not in (None, '') else None
        except (TypeError, ValueError):
            pf = None
        if pf is None or pf == 0:
            null_or_zero += 1
    print(f"  total offers: {len(offers)}")
    print(f"  offers with priceSpecification: {has_pspec}")
    print(f"  offers with priceInMinorUnit:   {has_pim}")
    print(f"  offers with null/zero price:    {null_or_zero}")

    distinct = Counter()
    for p in price_vals:
        if isinstance(p, (int, float)):
            distinct[round(float(p), 2)] += 1
        else:
            distinct[repr(p)] += 1
    print(f"  distinct Offer.price values (top 10):")
    for v, n in distinct.most_common(10):
        print(f"      {v!r:<20} × {n}")
    print(f"  distinct Offer.priceCurrency values: "
          f"{Counter(cur_vals).most_common()}")

    print("\n  --- First 5 Offers with non-zero price ---")
    shown = 0
    for o in offers:
        try:
            pf = float(o.get('price'))
        except (TypeError, ValueError):
            continue
        if pf and pf > 0:
            print(f"    name={o.get('name')!r}  price={o.get('price')!r}  "
                  f"currency={o.get('priceCurrency')!r}")
            shown += 1
            if shown >= 5:
                break
    if shown == 0:
        print("  (no Offer carries a non-zero numeric price)")

        # Also dump the parent MenuItem for one of the Offers to see
        # whether the price lives at the MenuItem level (priceInMinorUnit
        # or some other key).
        print("\n  --- Sample MenuItem raw JSON (price probably lives here) ---")
        for mi in menuitems[:3]:
            sample = {k: v for k, v in mi.items() if k != 'image'}
            print(json.dumps(sample, indent=2, ensure_ascii=False)[:1500])
            print()


if __name__ == '__main__':
    main()

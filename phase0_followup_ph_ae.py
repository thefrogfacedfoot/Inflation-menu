"""
Phase 0 follow-up — PH offer-shape inspection + AE Deliveroo body-JSON test.

(1) PH: fetch the 20210619104040 Bonchon Porta Vaga snapshot
       (134 MenuItem nodes in the structural probe).
    Locate the first MenuItem with an embedded Offer, print the raw Offer
    JSON, and dump every Offer node's (price, priceCurrency,
    priceSpecification) so we can see whether real PHP floats live there.

(2) AE: fetch the 20210419095753 Ladurée Abu Dhabi snapshot
       (193 raw '"raw_price"' occurrences, no NEXT_DATA, no JSON-LD).
    Run extract_deliveroo_body_json (the UK regex extractor, line 406 of
    historical_html_scraper.py). Report pair count + first 5 samples.
"""
import json
import re
import sys
import time

import requests

# Make sure we can import the production extractor
sys.path.insert(0, '/Users/erwenchen/Inflation-menu')
from historical_html_scraper import (
    extract_deliveroo_body_json,
    _extract_script_content,
    _LD_OPENING,
    _NEXTDATA_OPENING,
)

WBM = 'https://web.archive.org/web'
HDR = {'User-Agent': 'UIFPI-research-probe (academic; contact via repo issues)'}
TIMEOUT = 60

PH_TS  = '20210619104040'
PH_URL = 'https://food.grab.com/ph/en/restaurant/bonchon-porta-vaga-delivery/2-CZD1AU4XC25'

AE_TS  = '20210419095753'
AE_URL = 'https://deliveroo.ae/menu/abu-dhabi/al-zahiyah/laduree-abu-dhabi-mall'


def fetch(ts, url):
    full = f"{WBM}/{ts}id_/{url}"
    print(f"  Fetching {full[:120]}", flush=True)
    r = requests.get(full, headers=HDR, timeout=TIMEOUT)
    print(f"  HTTP {r.status_code}, {len(r.content)//1024} KB", flush=True)
    if r.status_code != 200:
        return None
    return r.text


def collect_offer_nodes(node, out):
    if isinstance(node, dict):
        t = node.get('@type')
        is_offer = (t == 'Offer') or (isinstance(t, list) and 'Offer' in t)
        if is_offer:
            out.append(node)
        for v in node.values():
            collect_offer_nodes(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_offer_nodes(v, out)


def collect_menuitem_nodes(node, out):
    if isinstance(node, dict):
        t = node.get('@type')
        if (t == 'MenuItem') or (isinstance(t, list) and 'MenuItem' in t):
            out.append(node)
        for v in node.values():
            collect_menuitem_nodes(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_menuitem_nodes(v, out)


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


def ph_probe():
    print("\n" + "="*70)
    print("(1) PH follow-up — Bonchon Porta Vaga, 2021-06-19")
    print("="*70)
    html = fetch(PH_TS, PH_URL)
    if not html:
        print("  FETCH FAILED")
        return

    blocks = all_jsonld_blocks(html)
    nd     = nextdata_block(html)
    print(f"  json-ld blocks: {len(blocks)}, next_data: {nd is not None}",
          flush=True)

    offers    = []
    menuitems = []
    for blk in blocks:
        collect_offer_nodes(blk, offers)
        collect_menuitem_nodes(blk, menuitems)
    if nd is not None:
        collect_offer_nodes(nd, offers)
        collect_menuitem_nodes(nd, menuitems)
    print(f"  collected: {len(offers)} Offer nodes, {len(menuitems)} MenuItem nodes",
          flush=True)

    # Show a MenuItem with an Offer inline
    print("\n  --- First MenuItem with inline offers (raw JSON, truncated) ---")
    found = False
    for mi in menuitems:
        if mi.get('offers') is not None:
            sample = {k: v for k, v in mi.items() if k != 'image'}
            print(json.dumps(sample, indent=2, ensure_ascii=False)[:2000])
            found = True
            break
    if not found:
        print("  (no MenuItem with an inline 'offers' field)")

    # Show the first Offer node in isolation
    if offers:
        print("\n  --- First standalone Offer node (raw JSON) ---")
        print(json.dumps(offers[0], indent=2, ensure_ascii=False)[:2000])

    # Histogram of (price, priceCurrency) tuples across all Offers
    print("\n  --- Offer.price / priceCurrency / priceSpecification summary ---")
    price_vals = []
    cur_vals = []
    has_pspec = 0
    has_pim   = 0
    null_or_zero = 0
    for o in offers:
        p = o.get('price')
        c = o.get('priceCurrency')
        price_vals.append(p)
        cur_vals.append(c)
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

    # distinct prices
    from collections import Counter
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

    # Non-zero Offer.price sample
    print("\n  --- First 5 Offers with a non-zero price ---")
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
        print("  (no Offer carries a non-zero numeric price — PH is dead)")


def ae_probe():
    print("\n" + "="*70)
    print("(2) AE follow-up — Ladurée Abu Dhabi, 2021-04-19")
    print("="*70)
    html = fetch(AE_TS, AE_URL)
    if not html:
        print("  FETCH FAILED")
        return

    raw_hits = html.count('"raw_price"')
    print(f"  raw '\"raw_price\"' substring hits: {raw_hits}", flush=True)

    pairs = extract_deliveroo_body_json(html)
    print(f"  extract_deliveroo_body_json → {len(pairs)} pairs", flush=True)

    print("\n  --- First 10 (name, raw_price) pairs ---")
    for n, p, c in pairs[:10]:
        print(f"    name={n!r:<60}  raw_price={p}  currency={c}")

    # Sanity: are values in plausible AED range?
    if pairs:
        prices = [p for _, p, _ in pairs]
        print(f"\n  price stats: n={len(prices)}, "
              f"min={min(prices):.2f}, max={max(prices):.2f}, "
              f"mean={sum(prices)/len(prices):.2f}")


def main():
    ph_probe()
    time.sleep(8)
    ae_probe()


if __name__ == '__main__':
    main()

"""
Phase 0 structural probe — DoorDash + Grubhub, US.

Same template as phase0_structural_probe_grab_deliveroo.py:
  1. Hit Wayback CDX for the storefront URL pattern.
  2. Pick 3 ≥2-cap candidates (fall back to single-cap if needed).
  3. Fetch each archived page via Wayback /id_/ raw replay.
  4. Pull JSON-LD blocks + __NEXT_DATA__ + any other obvious embedded JSON
     (DoorDash and Grubhub historically used several conventions).
  5. Recursive tree-walk: @type histogram, real-typed price counts by node
     shape (MenuItem / Offer / Product / generic-named-priced).
  6. Per-platform verdict:
        CONFIRM — ≥1/3 snapshots have a typed numeric price on a named
                  MenuItem/Offer/Product node (the shapes the production
                  scraper would extract).
        BAIL    — 0/3 have any such node, OR every snapshot is a saved
                  CAPTCHA/Cloudflare challenge page (the menu was gated
                  even at archive time).

The DE/BR/PH lesson: HTML regex hits like `$\d+\.\d+` and "price" string
matches are NOT a confirm signal. The walker reports them separately as
substring counts so we can distinguish "key absent" from "key present in
unexpected shape", but the verdict requires a parsed typed value on a
named node.
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
HDR  = {'User-Agent': 'UICPI-research-probe (academic; contact via repo issues)'}

WINDOW_FROM = '20180101'
WINDOW_TO   = '20260601'

CDX_TIMEOUT       = 90
CDX_LIMIT         = 30000
CDX_DELAY         = 4.0
CDX_RETRIES       = 2
CDX_RETRY_BACKOFF = 15
FETCH_TIMEOUT     = 60
FETCH_DELAY       = 8.0

SAMPLES_PER_TARGET = 3

# (label, country, CDX pattern, currency, expected primary price key)
# The walker also detects a broader fallback set per platform.
PROBES = [
    ('DoorDash US', 'United States',
     'doordash.com/store/*', 'USD',
     # DoorDash historically uses both `displayPrice` (string, e.g. "$8.99")
     # and `priceMonetaryFields.unitAmount`/`price`/`unitPrice` (number cents).
     # The walker collects any numeric price on a node that also has a name.
     {'displayPrice', 'unitAmount', 'price', 'unitPrice', 'priceInCents'}),
    ('Grubhub US',  'United States',
     'grubhub.com/restaurant/*', 'USD',
     # Grubhub historically uses `price.amount` (cents) and `price` (number)
     # plus JSON-LD `offers.price`.
     {'amount', 'price'}),
]

# Price-key set the walker also tries beyond the expected — every numeric
# field on a named node gets the chance to count. Keep the master set in
# sync if new platforms get added.
GENERIC_PRICE_KEYS = {
    'price', 'priceInCents', 'priceInMinorUnit', 'priceInMinor', 'raw_price',
    'amount', 'unitAmount', 'unitPrice', 'displayPrice', 'minOrderPrice',
    'salePrice', 'basePrice', 'listPrice',
}

# Names of node classes we care about for the verdict — only typed numeric
# prices on these shapes count toward CONFIRM.
TYPED_PRICE_NODE_TYPES = {
    'MenuItem', 'Offer', 'AggregateOffer', 'Product', 'FoodEstablishment',
}

_LD_OPENING = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>', re.I)
_NEXTDATA_OPENING = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>', re.I)
# Grubhub historically used `window.INITIAL_STATE = {...}` and `__APOLLO_STATE__`
_INITSTATE_OPENING = re.compile(
    r'window\.(?:INITIAL_STATE|__APOLLO_STATE__|__INITIAL_STATE__)\s*=\s*',
    re.I)


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


def initstate_block(html):
    """Grubhub/Apollo-style window.INITIAL_STATE = {...}; best-effort.
    Returns parsed dict or None. Brace-balance to find the end."""
    m = _INITSTATE_OPENING.search(html)
    if not m:
        return None
    start = m.end()
    # Skip leading whitespace, find first {
    while start < len(html) and html[start].isspace():
        start += 1
    if start >= len(html) or html[start] != '{':
        return None
    depth = 0
    in_str = False
    esc = False
    end = start
    for i in range(start, min(len(html), start + 4_000_000)):
        ch = html[i]
        if esc:
            esc = False
            continue
        if ch == '\\' and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == start:
        return None
    try:
        return json.loads(html[start:end])
    except Exception:
        return None


def _coerce_price(val):
    """Return float or None. Accepts numbers, numeric strings, and price
    strings like '$8.99' / '£9.50' / '8.99 USD'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        return v if v != 0 else None
    if isinstance(val, str):
        m = re.search(r'(\d+(?:\.\d{1,4})?)', val.replace(',', ''))
        if not m:
            return None
        try:
            v = float(m.group(1))
        except ValueError:
            return None
        # Heuristic — if the field name was a cents-style key, caller
        # decides scaling. Here we just return the parsed magnitude.
        return v if v != 0 else None
    return None


def walk(node, hist, named_priced_typed, named_priced_generic,
         typed_samples, generic_samples, raw_key_hits, name_ctx=None,
         type_ctx=None):
    """Tree walk:
      hist                  Counter of every @type seen anywhere.
      named_priced_typed    int, # nodes that have a name AND a numeric
                            price AND @type ∈ TYPED_PRICE_NODE_TYPES (or
                            inherit one from an ancestor).
      named_priced_generic  int, # nodes with name + any numeric price,
                            regardless of @type.
      typed_samples         list of (type, name, price) for first 25
                            qualifying nodes.
      generic_samples       list of (key, name, price) for first 25 nodes
                            that had a price under a different key but
                            still a real name.
      raw_key_hits          Counter of every numeric-price key seen.
    """
    if isinstance(node, dict):
        # @type may be a string or a list
        local_types = []
        t = node.get('@type')
        if isinstance(t, str):
            hist[t] += 1
            local_types = [t]
        elif isinstance(t, list):
            for x in t:
                if isinstance(x, str):
                    hist[x] += 1
                    local_types.append(x)

        local_name = None
        for k in ('name', 'itemName', 'productName', 'title', 'displayName'):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                local_name = v.strip()
                break
        nm = local_name or name_ctx
        # The "effective type" for this node — own @type, or inherited from
        # an ancestor (so deeply-nested Offers under MenuItem still count).
        type_for_node = local_types[0] if local_types else type_ctx

        # Scan price-bearing fields
        for pk in node.keys():
            if pk not in GENERIC_PRICE_KEYS:
                continue
            raw_key_hits[pk] += 1
            p = _coerce_price(node[pk])
            if p is None or not nm:
                continue
            # Cents heuristic: if the key is *InCents / *Minor*, divide by 100
            # iff the value is implausibly large for a meal price (>$100).
            scaled = p
            if pk in ('priceInCents', 'priceInMinor', 'priceInMinorUnit',
                      'unitAmount', 'amount') and p > 100:
                scaled = p / 100.0
            if scaled <= 0:
                continue
            named_priced_generic += 1
            if type_for_node in TYPED_PRICE_NODE_TYPES or any(
                    lt in TYPED_PRICE_NODE_TYPES for lt in local_types):
                named_priced_typed += 1
                if len(typed_samples) < 25:
                    typed_samples.append(
                        (type_for_node or 'inherited', nm[:60], round(scaled, 2))
                    )
            elif len(generic_samples) < 25:
                generic_samples.append((pk, nm[:60], round(scaled, 2)))

        for v in node.values():
            named_priced_typed, named_priced_generic = walk(
                v, hist, named_priced_typed, named_priced_generic,
                typed_samples, generic_samples, raw_key_hits, nm,
                type_for_node,
            )
    elif isinstance(node, list):
        for v in node:
            named_priced_typed, named_priced_generic = walk(
                v, hist, named_priced_typed, named_priced_generic,
                typed_samples, generic_samples, raw_key_hits, name_ctx,
                type_ctx,
            )
    return named_priced_typed, named_priced_generic


def detect_gating(html):
    """Return ('', '') if page looks like real content, else a tag."""
    if len(html) < 800:
        return 'tiny', f'{len(html)} bytes'
    bl = html.lower()
    if 'attention required' in bl and 'cloudflare' in bl:
        return 'cloudflare', 'attention required'
    if 'sorry, you have been blocked' in bl:
        return 'cf-block', 'sorry blocked'
    if 'just a moment' in bl and 'cloudflare' in bl:
        return 'cf-challenge', 'just a moment'
    # PerimeterX / HUMAN
    if 'px-captcha' in bl or 'perimeterx' in bl:
        return 'perimeterx', ''
    # Generic CAPTCHA wall (exclude reCAPTCHA badge widgets which are common
    # on real pages)
    if 'g-recaptcha' in bl and ('verify you are human' in bl
                                 or 'verify you\'re human' in bl):
        return 'recaptcha-wall', ''
    return '', ''


def probe_snapshot(ts, orig_url, primary_keys):
    url = f"{WBM}/{ts}id_/{orig_url}"
    try:
        r = requests.get(url, headers=HDR, timeout=FETCH_TIMEOUT)
    except Exception as e:
        return {'err': str(e)[:80]}
    if r.status_code != 200:
        return {'err': f'HTTP {r.status_code}', 'kb': len(r.content)//1024}
    html = r.text
    kb = len(r.content) // 1024

    gate_tag, gate_detail = detect_gating(html)

    hist = Counter()
    typed_samples = []
    generic_samples = []
    raw_key_hits = Counter()

    ld_blocks = all_jsonld_blocks(html)
    npt = npg = 0
    for blk in ld_blocks:
        npt, npg = walk(blk, hist, npt, npg, typed_samples,
                        generic_samples, raw_key_hits)

    nd = nextdata_block(html)
    if nd is not None:
        npt, npg = walk(nd, hist, npt, npg, typed_samples,
                        generic_samples, raw_key_hits)

    isd = initstate_block(html)
    if isd is not None:
        npt, npg = walk(isd, hist, npt, npg, typed_samples,
                        generic_samples, raw_key_hits)

    # Raw-substring counts so we can tell "key absent" from "key present
    # in a shape the walker didn't reach".
    raw_substr = {
        k: html.count(f'"{k}"') for k in primary_keys
    }
    # Also the bare USD-regex count, the DE/BR false-positive signal
    bare_usd_regex_hits = len(re.findall(r'\$\d+\.\d{2}\b', html))

    return {
        'kb': kb,
        'gate': gate_tag,
        'gate_detail': gate_detail,
        'n_ld_blocks': len(ld_blocks),
        'has_nextdata': nd is not None,
        'has_initstate': isd is not None,
        'hist': dict(hist),
        'typed_samples': typed_samples[:5],
        'generic_samples': generic_samples[:5],
        'named_priced_typed': npt,
        'named_priced_generic': npg,
        'raw_key_substr_hits': raw_substr,
        'bare_usd_regex_hits': bare_usd_regex_hits,
        'raw_price_key_hits': dict(raw_key_hits),
    }


def fmt_hist(h, top=10):
    if not h:
        return '(empty)'
    items = sorted(h.items(), key=lambda kv: -kv[1])[:top]
    return ', '.join(f'{k}:{v}' for k, v in items)


def main():
    print(f"Phase 0 structural probe — DoorDash + Grubhub (US)", flush=True)
    print(f"Window: {WINDOW_FROM} → {WINDOW_TO}", flush=True)
    print(f"{SAMPLES_PER_TARGET} snapshots per platform\n", flush=True)

    rnd = random.Random(20260621)
    summary = []

    for label, country, pat, cur, primary_keys in PROBES:
        print(f"\n{'='*72}", flush=True)
        print(f"{label} — {country} — {pat}", flush=True)
        print(f"primary price keys: {sorted(primary_keys)}", flush=True)
        print('='*72, flush=True)

        rows, err = query_cdx(pat)
        if err:
            print(f"  CDX error: {err}", flush=True)
            summary.append((label, 'CDX-ERR', err, 0, 0))
            time.sleep(CDX_DELAY)
            continue
        if not rows:
            print(f"  CDX empty.", flush=True)
            summary.append((label, 'BAIL', 'cdx-empty', 0, 0))
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
        for u in candidates[:SAMPLES_PER_TARGET * 4]:
            ts_list = sorted(per_url[u])
            # Pick a mid-snapshot if the URL has more than one
            picks.append((ts_list[len(ts_list)//2], u))
            if len(picks) >= SAMPLES_PER_TARGET:
                break

        confirms = 0
        gated = 0
        for i, (ts, u) in enumerate(picks, 1):
            time.sleep(FETCH_DELAY)
            print(f"\n  [{i}/{len(picks)}] {ts}  {u[:80]}", flush=True)
            r = probe_snapshot(ts, u, primary_keys)
            if 'err' in r:
                print(f"      ERROR: {r['err']}", flush=True)
                continue
            print(f"      kb={r['kb']}  gating={r['gate'] or 'none'}"
                  f"{(' (' + r['gate_detail'] + ')') if r['gate_detail'] else ''}  "
                  f"ld_blocks={r['n_ld_blocks']}  next_data={r['has_nextdata']}  "
                  f"init_state={r['has_initstate']}", flush=True)
            print(f"      @type histogram: {fmt_hist(r['hist'])}", flush=True)
            print(f"      named_priced_typed={r['named_priced_typed']}  "
                  f"named_priced_generic={r['named_priced_generic']}",
                  flush=True)
            print(f"      raw substr counts: "
                  f"{r['raw_key_substr_hits']}  bare-USD-regex={r['bare_usd_regex_hits']}",
                  flush=True)
            if r['raw_price_key_hits']:
                print(f"      walker price-key hits: {r['raw_price_key_hits']}",
                      flush=True)
            if r['typed_samples']:
                print(f"      typed-node samples:", flush=True)
                for tn, nm, p in r['typed_samples']:
                    print(f"          ({tn!r}, {nm!r}, {p})", flush=True)
            if r['generic_samples']:
                print(f"      generic-node samples (not MenuItem/Offer):",
                      flush=True)
                for k, nm, p in r['generic_samples']:
                    print(f"          ({k!r}, {nm!r}, {p})", flush=True)

            # Verdict ingredient: typed node with real price = strong confirm
            if r['named_priced_typed'] > 0:
                confirms += 1
            if r['gate']:
                gated += 1

        verdict = 'CONFIRM' if confirms >= 1 else 'BAIL'
        # If every snapshot was gated, flag separately
        if gated >= len(picks):
            verdict_note = f'all-gated ({gated}/{len(picks)})'
        else:
            verdict_note = f'typed-priced {confirms}/{len(picks)}'
        print(f"\n  → {label}: {verdict_note} → {verdict}", flush=True)
        summary.append((label, verdict, verdict_note, len(per_url), len(ge2)))
        time.sleep(CDX_DELAY)

    # ── Yields table ───────────────────────────────────────────────────────
    print(f"\n\n{'='*72}\nYIELDS TABLE\n{'='*72}", flush=True)
    print(f"  {'platform':<14} {'verdict':<10} {'detail':<22} "
          f"{'CDX urls':>10} {'≥2-cap':>8}", flush=True)
    for label, verdict, detail, cdx, ge2 in summary:
        print(f"  {label:<14} {verdict:<10} {detail:<22} "
              f"{cdx:>10} {ge2:>8}", flush=True)


if __name__ == '__main__':
    main()

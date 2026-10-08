#!/usr/bin/env python3
"""Wayback feasibility audit (read-only). Registered spec: docs/preregistration.md at bd859403.

Does NOT write uifpi.db, change the scraper, or touch the cron. Computes and
stores NO prices and NO index values: the parse test records only whether >= 1
item price was extractable (boolean), never the price.

Countries: US, GB, SG, MY (TH and ID are excluded: not verified before the audit).

Stages (all resumable; checkpoint under diagnostics/wayback_audit/):
  crawl      CDX counts per candidate pattern per calendar month, 2010-2026.
             filter=statuscode:200 (+ mimetype), one capture per URL per month
             (collapse=urlkey inside a one-month window == one capture per
             URL-month; collapse=timestamp:6 on a wildcard query would also merge
             ADJACENT DIFFERENT URLs, so the month window is used instead).
             <= 1 request/second, exponential backoff on 429/5xx, User-Agent with
             contact email.
  parse      fixed-seed sample of 20 captures per (country, source type); fetch the
             id_ snapshot; success = >= 1 item price extractable (platform parser
             where one exists, else a generic JSON-LD / visible-currency test).
  analyse    estimated coverage under (a) the registered chained rule and (b) a
             time-product-dummy (TPD) rule, official-series monthly check, tables.

Usage: python3 diagnostics/wayback_feasibility_audit.py crawl|parse|analyse [--country US]
"""
import argparse
import datetime
import gzip
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent / "wayback_audit"
OUT.mkdir(exist_ok=True)
CACHE = OUT / "cache"                    # URL lists per pattern-month (not committed)
CKPT = OUT / "checkpoint.json"
SEED = 20261008
UA = "UICPI-research-audit (erwenchen56@gmail.com; academic feasibility audit)"
CDX = "https://web.archive.org/cdx/search/cdx"
FIRST_YEAR, LAST_YEAR = 2010, 2026
SAMPLE_PER_CELL = 6                      # captures remembered per pattern-month for the parse test
PARSE_N = 20

# ── Candidate inventory ─────────────────────────────────────────────────────
# (country, source_type, label, pattern, mimetype, currency, in_TARGETS)
# source_type: delivery-platform | aggregator | chain-menu | chain-pdf
# unit: "url" = each captured URL is a restaurant; "brand" = the pattern is ONE restaurant (a chain)
H, P = "text/html", "application/pdf"
INVENTORY = [
    # United States
    ("US", "delivery-platform", "doordash", "doordash.com/store/*", H, "USD", True),
    ("US", "delivery-platform", "grubhub", "grubhub.com/restaurant/*", H, "USD", False),
    ("US", "delivery-platform", "seamless", "seamless.com/menu/*", H, "USD", False),
    ("US", "delivery-platform", "ubereats", "ubereats.com/store/*", H, "USD", False),
    ("US", "delivery-platform", "postmates", "postmates.com/merchant/*", H, "USD", False),
    ("US", "aggregator", "menupages", "menupages.com/*", H, "USD", True),
    ("US", "aggregator", "allmenus", "allmenus.com/*", H, "USD", False),
    ("US", "aggregator", "yelp-menu", "yelp.com/menu/*", H, "USD", False),
    ("US", "aggregator", "menuism", "menuism.com/*", H, "USD", False),
    ("US", "chain-menu", "mcdonalds-us", "mcdonalds.com/us/en-us/full-menu*", H, "USD", False),
    ("US", "chain-menu", "burgerking-us", "burgerking.com/menu*", H, "USD", False),
    ("US", "chain-menu", "kfc-us", "kfc.com/menu*", H, "USD", False),
    ("US", "chain-menu", "subway-us", "subway.com/en-us/menunutrition*", H, "USD", False),
    ("US", "chain-menu", "tacobell-us", "tacobell.com/food*", H, "USD", False),
    ("US", "chain-menu", "wendys-us", "wendys.com/menu*", H, "USD", False),
    ("US", "chain-menu", "chipotle-us", "chipotle.com/menu*", H, "USD", False),
    ("US", "chain-menu", "starbucks-us", "starbucks.com/menu/*", H, "USD", False),
    ("US", "chain-menu", "dominos-us", "dominos.com/menu*", H, "USD", False),
    ("US", "chain-menu", "pizzahut-us", "pizzahut.com/menu*", H, "USD", False),
    ("US", "chain-menu", "applebees-us", "applebees.com/en/menu*", H, "USD", False),
    ("US", "chain-menu", "ihop-us", "ihop.com/en/menu*", H, "USD", False),
    ("US", "chain-pdf", "mcdonalds-us-pdf", "mcdonalds.com/*", P, "USD", False),
    # United Kingdom
    ("GB", "delivery-platform", "deliveroo-uk", "deliveroo.co.uk/menu/*", H, "GBP", True),
    ("GB", "delivery-platform", "justeat-uk", "just-eat.co.uk/restaurants-*", H, "GBP", False),
    ("GB", "delivery-platform", "ubereats-gb", "ubereats.com/gb/store/*", H, "GBP", False),
    ("GB", "delivery-platform", "hungryhouse", "hungryhouse.co.uk/*", H, "GBP", False),
    ("GB", "aggregator", "tripadvisor-uk", "tripadvisor.co.uk/Restaurant_Review*", H, "GBP", False),
    ("GB", "aggregator", "menus-uk", "menus.co.uk/*", H, "GBP", False),
    ("GB", "chain-menu", "mcdonalds-gb", "mcdonalds.com/gb/en-gb/*", H, "GBP", False),
    ("GB", "chain-menu", "kfc-gb", "kfc.co.uk/our-menu*", H, "GBP", False),
    ("GB", "chain-menu", "burgerking-gb", "burgerking.co.uk/menu*", H, "GBP", False),
    ("GB", "chain-menu", "nandos-gb", "nandos.co.uk/menu*", H, "GBP", False),
    ("GB", "chain-menu", "wagamama-gb", "wagamama.com/menu*", H, "GBP", False),
    ("GB", "chain-menu", "greggs-gb", "greggs.co.uk/menu*", H, "GBP", False),
    ("GB", "chain-menu", "pizzahut-gb", "pizzahut.co.uk/menu*", H, "GBP", False),
    ("GB", "chain-menu", "dominos-gb", "dominos.co.uk/menu*", H, "GBP", False),
    ("GB", "chain-menu", "subway-gb", "subway.com/en-gb/*", H, "GBP", False),
    ("GB", "chain-menu", "pret-gb", "pret.co.uk/en-GB/menu*", H, "GBP", False),
    ("GB", "chain-menu", "pizzaexpress-gb", "pizzaexpress.com/menu*", H, "GBP", False),
    ("GB", "chain-menu", "wetherspoon-gb", "jdwetherspoon.com/food*", H, "GBP", False),
    ("GB", "chain-pdf", "mcdonalds-gb-pdf", "mcdonalds.com/gb/*", P, "GBP", False),
    # Singapore
    ("SG", "delivery-platform", "grabfood-sg", "food.grab.com/sg/en/restaurant/*", H, "SGD", True),
    ("SG", "delivery-platform", "foodpanda-sg", "foodpanda.sg/restaurant/*", H, "SGD", False),
    ("SG", "delivery-platform", "deliveroo-sg", "deliveroo.com.sg/menu/*", H, "SGD", False),
    ("SG", "aggregator", "burpple", "burpple.com/*", H, "SGD", False),
    ("SG", "aggregator", "hungrygowhere", "hungrygowhere.com/singapore/*", H, "SGD", False),
    ("SG", "aggregator", "tripadvisor-sg", "tripadvisor.com.sg/Restaurant_Review*", H, "SGD", False),
    ("SG", "chain-menu", "mcdonalds-sg", "mcdonalds.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "kfc-sg", "kfc.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "burgerking-sg", "burgerking.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "subway-sg", "subway.com.sg/*", H, "SGD", False),
    ("SG", "chain-menu", "pizzahut-sg", "pizzahut.com.sg/*", H, "SGD", False),
    ("SG", "chain-menu", "dominos-sg", "dominos.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "starbucks-sg", "starbucks.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "toastbox-sg", "toastbox.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "yakun-sg", "yakun.com/menu*", H, "SGD", False),
    ("SG", "chain-menu", "jollibee-sg", "jollibee.com.sg/menu*", H, "SGD", False),
    ("SG", "chain-menu", "popeyes-sg", "popeyes.com.sg/menu*", H, "SGD", False),
    # Malaysia
    ("MY", "delivery-platform", "grabfood-my", "food.grab.com/my/en/restaurant/*", H, "MYR", True),
    ("MY", "delivery-platform", "foodpanda-my", "foodpanda.my/restaurant/*", H, "MYR", False),
    ("MY", "aggregator", "tripadvisor-my", "tripadvisor.com.my/Restaurant_Review*", H, "MYR", False),
    ("MY", "aggregator", "openrice-my", "openrice.com/*", H, "MYR", False),
    ("MY", "chain-menu", "mcdonalds-my", "mcdonalds.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "kfc-my", "kfc.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "dominos-my", "dominos.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "pizzahut-my", "pizzahut.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "burgerking-my", "burgerking.com.my/*", H, "MYR", False),
    ("MY", "chain-menu", "starbucks-my", "starbucks.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "secretrecipe-my", "secretrecipe.com.my/menu*", H, "MYR", False),
    ("MY", "chain-menu", "marrybrown-my", "marrybrown.com/menu*", H, "MYR", False),
    ("MY", "chain-menu", "subway-my", "subway.com.my/*", H, "MYR", False),
]
# Own-site menus of independent restaurants cannot be enumerated as one CDX pattern; they are
# reported in the audit as an inventory item (candidate list needed), not counted here.


def unit_of(source_type):
    return "brand" if source_type in ("chain-menu", "chain-pdf") else "url"


def pid(label):
    return re.sub(r"[^a-z0-9_-]", "_", label.lower())


# ── polite CDX ──────────────────────────────────────────────────────────────
import threading
_slot_lock = threading.Lock()
_next_slot = [0.0]


DEADLINE = datetime.datetime(2026, 10, 9, 20, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))  # 20:00 SGT
TIMEOUT = (10, 60)                     # connect 10 s, read 60 s; a timeout is a failure and goes through backoff
HEARTBEAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wayback_audit", "heartbeat.txt")
STATS = {"ok": 0, "fail": 0, "backoff": "none", "t0": time.time(), "last_report": time.time()}


def _beat(ok, note=""):
    """Heartbeat after EVERY request (success or failure) + a progress line every 30 min."""
    STATS["ok" if ok else "fail"] += 1
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    with open(HEARTBEAT, "a") as fh:
        fh.write(f"{now} {'ok' if ok else 'FAIL'} {note}\n")
    if time.time() - STATS["last_report"] >= 1800:
        STATS["last_report"] = time.time()
        try:
            ck = json.load(open(CKPT))
            done = sum(1 for c in ck.values() if c.get("status") in ("done", "empty"))
            n = len(ck)
        except Exception:
            done, n = "?", "?"
        print(f"PROGRESS {now} patterns done {done}/{n} requests ok={STATS['ok']} failed={STATS['fail']} backoff={STATS['backoff']}", flush=True)


class DeadlineReached(RuntimeError):
    pass


def polite_get(url, params=None, timeout=TIMEOUT, tries=5):
    """Single global slot: request STARTS spaced 3-5 s apart (random); exponential backoff on 5xx and network
    errors; on 429 wait >= 5 min before retrying. Raises DeadlineReached after the hard deadline."""
    err = None
    for i in range(tries):
        if datetime.datetime.now(datetime.timezone.utc) >= DEADLINE:
            raise DeadlineReached("deadline 2026-10-09 20:00 SGT reached")
        with _slot_lock:
            slot = max(time.time(), _next_slot[0] + random.uniform(3.0, 5.0))
            _next_slot[0] = slot
        time.sleep(max(0.0, slot - time.time()))
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code == 429:
                err = "HTTP 429"
                STATS["backoff"] = f"429 sleep {300 + 60 * i}s"
                _beat(False, err)
                time.sleep(300 + 60 * i)
                STATS["backoff"] = "none"
                continue
            if r.status_code in (500, 502, 503, 504):
                err = f"HTTP {r.status_code}"
                STATS["backoff"] = f"{err} sleep {min(120, 5 * 2 ** i)}s"
                _beat(False, err)
                time.sleep(min(120, 5 * 2 ** i))
                STATS["backoff"] = "none"
                continue
            _beat(True, f"HTTP {r.status_code}")
            return r
        except requests.RequestException as e:
            err = type(e).__name__
            STATS["backoff"] = f"{err} sleep {min(120, 5 * 2 ** i)}s"
            _beat(False, err)
            time.sleep(min(120, 5 * 2 ** i))
            STATS["backoff"] = "none"
    raise RuntimeError(f"gave up after {tries} tries: {err}")


PAGE = 10000


def cdx_rows(pattern, mimetype, frm, to, collapse="timestamp:6", limit=100000, fl="urlkey,timestamp,original"):
    """Paged with showResumeKey; trailing-* patterns are sent as matchType=prefix."""
    params = {"url": pattern, "from": frm, "to": to, "output": "json", "fl": fl,
              "filter": ["statuscode:200", f"mimetype:{mimetype}"]}
    if pattern.endswith("*") and not pattern.startswith("*"):
        params["url"] = pattern.rstrip("*")
        params["matchType"] = "prefix"
    if collapse:
        params["collapse"] = collapse
    out, key = [], None
    while True:
        q = dict(params, limit=min(PAGE, limit - len(out)), showResumeKey="true")
        if key:
            q["resumeKey"] = key
        r = polite_get(CDX, q)
        if r.status_code != 200:
            raise RuntimeError(f"CDX HTTP {r.status_code}")
        if not r.text.strip():
            break
        data = r.json()
        key = None
        if len(data) >= 2 and data[-2] == [] and len(data[-1]) == 1:
            key = data[-1][0]
            data = data[:-2]
        out.extend(data[1:] if data and data[0][:1] == [fl.split(",")[0]] else data)
        if not key or len(out) >= limit:
            break
    return out


def load_ckpt():
    return json.loads(CKPT.read_text()) if CKPT.exists() else {}


def save_ckpt(c):
    tmp = CKPT.with_suffix(".tmp")
    tmp.write_text(json.dumps(c, indent=0, sort_keys=True))
    tmp.replace(CKPT)


def month_end(y, m):
    return {1: 31, 2: 29 if y % 4 == 0 else 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}[m]


# ── stage 1: crawl ───────────────────────────────────────────────────────────
WORKERS = 1
YEAR_LIMIT = 100000


def _record(cell, key, rows, rng, lock):
    """Fold CDX rows (urlkey, timestamp, original) into per-month distinct-URL cells."""
    by_month = defaultdict(dict)
    for urlkey, ts, orig in rows:
        by_month[ts[:6]].setdefault(urlkey, (ts, orig))
    with lock:
        d = CACHE / key
        d.mkdir(parents=True, exist_ok=True)
        for ym, urls in by_month.items():
            items = sorted(urls.items())
            with gzip.open(d / f"{ym}.txt.gz", "wt") as fh:
                fh.write("\n".join(k for k, _ in items))
            pick = rng.sample(items, min(SAMPLE_PER_CELL, len(items)))
            cell["months"][ym] = {"n": len(items), "trunc": False, "sample": [[v[0], v[1]] for _, v in pick]}


# Crawl order from the existing-data feasibility (wayback_existing_feasibility.py): the longest runs come from
# platform listings (deliveroo-uk UK, doordash US, grabfood MY), where the binding constraint is the number of
# restaurants matched in consecutive months. Platform patterns that can add restaurants per month go first, then
# directory aggregators, then single-brand pages. Years are crawled newest first, extending the existing
# windows (UK 2024-12..2025-10, US 2025-03..2025-07, MY 2025-07..2025-10) before older history.
_PRIORITY_ORDER = ["deliveroo-uk", "doordash", "grabfood-my", "ubereats-gb", "ubereats", "justeat-uk", "grubhub",
                   "seamless", "foodpanda-my", "deliveroo-sg", "grabfood-sg", "foodpanda-sg",
                   "allmenus", "menupages", "menus-uk", "hungryhouse", "postmates", "menuism", "yelp-menu",
                   "hungrygowhere", "burpple", "openrice-my", "tripadvisor-uk", "tripadvisor-my", "tripadvisor-sg"]
PRIORITY = {pid(l): i for i, l in enumerate(_PRIORITY_ORDER)}


def crawl(countries):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    ck = load_ckpt()
    lock = threading.Lock()
    rng = random.Random(SEED)
    cells = {}
    for (cc, stype, label, pattern, mime, cur, intargets) in INVENTORY:
        if cc in countries:
            cells[pid(label)] = ck.setdefault(pid(label), {
                "country": cc, "type": stype, "label": label, "pattern": pattern, "mime": mime,
                "in_targets": intargets, "status": "new", "years": {}, "months": {}})
    # A: existence over the full window
    def exists(key):
        c = cells[key]
        if c["status"] in ("empty", "done") or c.get("exists"):
            return key
        try:
            has = bool(cdx_rows(c["pattern"], c["mime"], f"{FIRST_YEAR}0101", f"{LAST_YEAR}1231", collapse=None, limit=1, fl="timestamp"))
            with lock:
                c["exists"] = has
                if not has:
                    c["status"] = "empty"
                save_ckpt(ck)
            print(f"[{c['country']}] {c['label']:<20} {'has captures' if has else 'EMPTY'}", flush=True)
        except RuntimeError as e:
            print(f"[{c['country']}] {c['label']:<20} existence check failed ({e}); retry on next run", flush=True)
        return key
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(exists, list(cells)))
    # B: month cells. A pattern-year is one query; if it fails (504/timeouts on dense patterns) it is
    # split into four quarter queries (smaller windows), tracked in c["split"].
    def windows(c):
        if unit_of(c["type"]) == "brand":
            return [("all", f"{FIRST_YEAR}0101", f"{LAST_YEAR}0930")]
        out = []
        for y in range(LAST_YEAR, FIRST_YEAR - 1, -1):
            if c.setdefault("split", {}).get(str(y)):
                for q in range(4):
                    m0, m1 = 3 * q + 1, 3 * q + 3
                    out.append((f"{y}Q{q + 1}", f"{y}{m0:02d}01", f"{y}{m1:02d}{month_end(y, m1):02d}"))
            else:
                out.append((str(y), f"{y}0101", f"{y}1231"))
        return out

    jobs = []
    for key, c in sorted(cells.items(), key=lambda kv: PRIORITY.get(pid(kv[1]["label"]), len(PRIORITY))):
        if c["status"] in ("empty", "done") or not c.get("exists"):
            continue
        jobs.append(key)

    def run_window(c, key, wid, frm, to):
        try:
            rows = cdx_rows(c["pattern"], c["mime"], frm, to)
        except RuntimeError as e:
            print(f"[{c['country']}] {c['label']:<20} {wid} FAILED ({e})", flush=True)
            return False
        with lock:
            _record(c, key, rows, rng, lock)
            if len(rows) >= YEAR_LIMIT:
                for ym in {r[1][:6] for r in rows}:
                    c["months"][ym]["trunc"] = True
            c["years"][wid] = len(rows)
            save_ckpt(ck)
        print(f"[{c['country']}] {c['label']:<20} {wid}: rows={len(rows)}", flush=True)
        return True

    def do(key):
        c = cells[key]
        for wid, frm, to in windows(c):
            if wid in c["years"]:
                continue
            if run_window(c, key, wid, frm, to):
                continue
            if wid.isdigit():                       # a whole year failed: split into quarters and try those
                with lock:
                    c.setdefault("split", {})[wid] = True
                    save_ckpt(ck)
                y = int(wid)
                for q in range(4):
                    m0, m1 = 3 * q + 1, 3 * q + 3
                    qid = f"{y}Q{q + 1}"
                    if qid not in c["years"]:
                        run_window(c, key, qid, f"{y}{m0:02d}01", f"{y}{m1:02d}{month_end(y, m1):02d}")

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(do, jobs))
    for key, c in cells.items():
        if c.get("exists") and c["status"] != "empty":
            if all(wid in c["years"] for wid, _, _ in windows(c)):
                c["status"] = "done"
    save_ckpt(ck)
    pending = [c["label"] for c in cells.values() if c.get("exists") and c["status"] not in ("empty", "done")]
    if datetime.datetime.now(datetime.timezone.utc) >= DEADLINE and pending:
        print(f"BLOCKED on archive availability: deadline reached with {len(pending)} patterns incomplete: {pending}", flush=True)
        return
    print("crawl pass complete; re-run to retry any failed cells", flush=True)


# ── stage 2: parse test ──────────────────────────────────────────────────────
CUR_RE = {"USD": r"\$\s?\d{1,3}(?:\.\d{2})?", "GBP": r"£\s?\d{1,3}(?:\.\d{2})?",
          "SGD": r"(?:S?\$)\s?\d{1,3}(?:\.\d{2})?", "MYR": r"RM\s?\d{1,3}(?:\.\d{2})?"}


def parser_for(label):
    import historical_html_scraper as h
    return {"doordash": h.parse_doordash, "menupages": h.parse_menupages, "deliveroo-uk": h.parse_deliveroo_uk,
            "grabfood-sg": h.parse_grabfood, "grabfood-my": h.parse_grabfood}.get(label)


def generic_has_price(html, currency):
    """Not a JS shell: JSON-LD with a priced Menu/Offer node, or >= 3 currency amounts in visible text."""
    for blk in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, flags=re.S | re.I):
        if re.search(r'"(?:price|lowPrice)"\s*:\s*"?\d', blk) and re.search(r'MenuItem|Offer', blk):
            return True, "jsonld"
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(re.findall(CUR_RE[currency], text)) >= 3, "visible-currency"


def parse_stage(countries):
    ck = load_ckpt()
    done_f = OUT / "parse_sample.json"
    res = json.loads(done_f.read_text()) if done_f.exists() else {}
    rng = random.Random(SEED)
    lab2cur = {e[2]: e[5] for e in INVENTORY}
    for cc in sorted(countries):
        for stype in ("delivery-platform", "aggregator", "chain-menu", "chain-pdf"):
            pool = []
            for key, cell in sorted(ck.items()):
                if cell["country"] == cc and cell["type"] == stype:
                    for ym, v in cell["months"].items():
                        for ts, orig in v["sample"]:
                            pool.append((cell["label"], ts, orig))
            if not pool:
                continue
            k = f"{cc}|{stype}"
            if k in res and len(res[k]["rows"]) >= min(PARSE_N, len(pool)):
                continue
            pick = rng.sample(pool, min(PARSE_N, len(pool)))
            rows = []
            for label, ts, orig in pick:
                html = None
                try:
                    r = polite_get(f"https://web.archive.org/web/{ts}id_/{orig}", tries=3)
                    if r.status_code == 200:
                        r.encoding = "utf-8"
                        html = r.text
                except RuntimeError:
                    html = None
                ok, how = False, "fetch-failed"
                if html is not None:
                    fn = parser_for(label)
                    if stype == "chain-pdf":
                        ok, how = False, "pdf-not-parsed-as-html"
                    elif fn is not None:
                        try:
                            ok, how = (len(fn(html, lab2cur[label])) >= 1), "platform-parser"
                        except Exception:
                            ok, how = False, "parser-error"
                    else:
                        ok, how = generic_has_price(html, lab2cur[label])
                rows.append({"label": label, "ts": ts, "url": orig, "parsed": bool(ok), "method": how})
            res[k] = {"n": len(rows), "ok": sum(r["parsed"] for r in rows), "rows": rows}
            done_f.write_text(json.dumps(res, indent=0))
            print(f"{k:<28} parse {res[k]['ok']}/{res[k]['n']}", flush=True)


# ── stage 3: analyse ─────────────────────────────────────────────────────────
def months_range(a, b):
    y, m = int(a[:4]), int(a[4:])
    out = []
    while f"{y}{m:02d}" <= b:
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def prev_month(ym):
    y, m = int(ym[:4]), int(ym[4:])
    return f"{y - 1}12" if m == 1 else f"{y}{m - 1:02d}"


def longest_run(flags):
    best, cur, best_end = 0, 0, None
    for ym in sorted(flags):
        if flags[ym]:
            cur += 1
            if cur > best:
                best, best_end = cur, ym
        else:
            cur = 0
    if not best:
        return 0, None, None
    start = best_end
    for _ in range(best - 1):
        start = prev_month(start)
    return best, start, best_end


def load_urls(key, ym):
    f = CACHE / key / f"{ym}.txt.gz"
    if not f.exists():
        return set()
    with gzip.open(f, "rt") as fh:
        t = fh.read()
    return set(t.split("\n")) if t else set()


def analyse(countries):
    ck = load_ckpt()
    ps = json.loads((OUT / "parse_sample.json").read_text()) if (OUT / "parse_sample.json").exists() else {}
    allm = months_range(f"{FIRST_YEAR}01", f"{LAST_YEAR}09")
    rows_out, counts_rows, summary = [], [], {}
    for cc in sorted(countries):
        # parse rate per source type (pooled over the country's patterns of that type)
        rate = {}
        for stype in ("delivery-platform", "aggregator", "chain-menu", "chain-pdf"):
            r = ps.get(f"{cc}|{stype}")
            rate[stype] = (r["ok"] / r["n"]) if r and r["n"] else None
        est_n = defaultdict(float)       # month -> expected parseable distinct restaurants
        est_m = defaultdict(float)       # month -> expected parseable MATCHED restaurants (t and t-1)
        raw_n = defaultdict(float)
        multi = {}                       # type -> (urls seen, urls in >= 2 months)
        contrib = defaultdict(lambda: defaultdict(float))   # label -> month -> expected matched contribution
        for key, cell in sorted(ck.items()):
            if cell["country"] != cc or not cell["months"]:
                continue
            st, lab = cell["type"], cell["label"]
            rt = rate[st] if rate[st] is not None else 0.0
            sets = {ym: load_urls(key, ym) for ym in cell["months"]}
            seen_months = defaultdict(int)
            for ym, s in sets.items():
                for u in s:
                    seen_months[u] += 1
            if unit_of(st) == "url":
                tot, ge2 = len(seen_months), sum(1 for c in seen_months.values() if c >= 2)
            else:
                tot, ge2 = 1, 1 if len(sets) >= 2 else 0
            a, b = multi.get(st, (0, 0))
            multi[st] = (a + tot, b + ge2)
            for ym in cell["months"]:
                n_raw = len(sets[ym]) if unit_of(st) == "url" else (1 if len(sets[ym]) else 0)
                pm = prev_month(ym)
                if unit_of(st) == "url":
                    matched = len(sets[ym] & sets.get(pm, set()))
                else:
                    matched = 1 if (len(sets[ym]) and len(sets.get(pm, set()))) else 0
                raw_n[ym] += n_raw
                est_n[ym] += n_raw * rt
                est_m[ym] += matched * rt * rt
                contrib[lab][ym] += matched * rt * rt
                counts_rows.append((cc, st, lab, ym, len(sets[ym]), int(cell["months"][ym]["trunc"]), matched))
        chained = {ym: est_m[ym] >= 15 for ym in allm}
        tpd = {ym: est_n[ym] >= 15 for ym in allm}
        n_ch, s_ch, e_ch = longest_run(chained)
        n_tp, s_tp, e_tp = longest_run(tpd)
        summary[cc] = dict(rate=rate, n_chain=(n_ch, s_ch, e_ch), n_tpd=(n_tp, s_tp, e_tp), multi=multi,
                           contrib={l: sum(1 for v in d.values() if v >= 15) for l, d in contrib.items()},
                           peak_est_n=max(est_n.values()) if est_n else 0,
                           peak_est_m=max(est_m.values()) if est_m else 0,
                           months_est_n_ge15=sum(tpd.values()), months_est_m_ge15=sum(chained.values()))
    # official series monthly check over the candidate windows
    import official_cpi_prereg as o
    official = {}
    for spec in o.SERIES:
        if spec["role"] == "primary" and spec["country"] in countries:
            obs = o.parse(spec, o.fetch(spec["url"]))
            official[spec["country"]] = (spec["series_id"], set(k.replace("-", "") for k in obs))
    for cc, sm in summary.items():
        sid, have = official[cc]
        for name in ("n_chain", "n_tpd"):
            n, s, e = sm[name]
            miss = [m for m in months_range(s, e) if m not in have] if n else []
            sm[name + "_official"] = (sid, "y" if not miss else "n (missing: " + ",".join(miss[:6]) + ")")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=lambda x: list(x) if isinstance(x, set) else x))
    with open(OUT / "counts_by_month.csv", "w") as fh:
        fh.write("country,source_type,pattern_label,year_month,distinct_urls,truncated,url_matched_with_prev_month\n")
        for r in counts_rows:
            fh.write(",".join(map(str, r)) + "\n")
    print(json.dumps(summary, indent=1, default=lambda x: list(x) if isinstance(x, set) else x))


def question(countries):
    """Single question: does any source have >= 15 restaurants captured in each of >= 36 consecutive months, for any
    country? Counts of distinct captured URLs per pattern-month from the CDX crawl (an UPPER bound: no parse or
    matching yet, so 'yes' is necessary, not sufficient). Candidates per country: each URL-unit pattern; the sum over
    each source type's URL-unit patterns (platform / aggregator); and the number of single-brand chain patterns with a
    capture that month (>= 15 brands). Prints BLOCKED with no counts if any existing pattern is still incomplete."""
    ck = load_ckpt()
    cells = [c for c in ck.values() if c["country"] in countries]
    pending = [c["label"] for c in cells if c.get("exists") is not False and c["status"] not in ("empty", "done")]
    if pending:
        print(f"BLOCKED on archive availability: {len(pending)} patterns incomplete: {pending}; no counts reported", flush=True)
        return
    allm = months_range(f"{FIRST_YEAR}01", f"{LAST_YEAR}09")
    out = {}
    for cc in sorted(countries):
        cand = defaultdict(lambda: defaultdict(int))
        for c in cells:
            if c["country"] != cc or c["status"] == "empty":
                continue
            for ym, v in c["months"].items():
                if unit_of(c["type"]) == "url":
                    cand[c["label"]][ym] += v["n"]
                    cand[f"SUM[{c['type']}]"][ym] += v["n"]
                else:
                    cand["SUM[brands with a capture]"][ym] += 1 if v["n"] else 0
        res = {}
        for name, d in cand.items():
            flags = {ym: d.get(ym, 0) >= 15 for ym in allm}
            n, s_, e_ = longest_run(flags)
            res[name] = dict(longest_run_months_ge15=n, window=(s_, e_), peak=max(d.values()), months_ge15=sum(flags.values()))
        best = max(res.items(), key=lambda kv: (kv[1]["longest_run_months_ge15"], kv[1]["months_ge15"]), default=(None, None))
        out[cc] = dict(best=best[0], **(best[1] or {}), candidates=res)
    yes = any(v.get("longest_run_months_ge15", 0) >= 36 for v in out.values())
    (OUT / "question.json").write_text(json.dumps(out, indent=1))
    print("ANSWER:", "YES" if yes else "NO", "- any source with >= 15 restaurants captured in each of >= 36 consecutive months", flush=True)
    for cc, v in out.items():
        print(f"{cc}: best={v['best']} longest_run={v.get('longest_run_months_ge15')} window={v.get('window')} peak={v.get('peak')}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("crawl", "parse", "analyse", "question"))
    ap.add_argument("--country", default="US,GB,SG,MY")
    a = ap.parse_args()
    cs = set(a.country.split(","))
    {"crawl": crawl, "parse": parse_stage, "analyse": analyse, "question": question}[a.stage](cs)


if __name__ == "__main__":
    main()

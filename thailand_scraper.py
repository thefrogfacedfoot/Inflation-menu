"""Thailand data collection — Wayback Machine TripAdvisor Bangkok approach."""
from __future__ import annotations
import re
import json
import sqlite3
import time
from datetime import datetime
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup

DB = "uifpi.db"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

THB_PATTERNS = [
    re.compile(r"(\d{2,4}(?:[\.,]\d{1,2})?)\s*(?:THB|baht|Baht|BAHT|฿)", re.IGNORECASE),
    re.compile(r"฿\s*(\d{2,4}(?:[\.,]\d{1,2})?)"),
    re.compile(r"(?:THB|Baht)\s*(\d{2,4}(?:[\.,]\d{1,2})?)", re.IGNORECASE),
]

ITEM_KEYWORDS = [
    "pad thai", "tom yum", "tom yam", "green curry", "red curry", "massaman",
    "som tam", "papaya salad", "khao soi", "khao pad", "fried rice", "rice",
    "noodle", "noodles", "soup", "satay", "spring roll", "mango sticky",
    "sticky rice", "thai tea", "thai iced", "coffee", "beer", "chang", "singha",
    "leo", "water", "coke", "pepsi", "chicken", "pork", "beef", "shrimp",
    "prawn", "fish", "duck", "salad", "curry", "rice ", "noodle ", "soup ",
    "dim sum", "bao", "dumpling", "pho", "ramen", "burger", "pizza", "sandwich",
    "set menu", "set lunch", "starter", "dessert", "appetizer", "main",
    "khao man gai", "khao kha moo", "boat noodle", "kuay teow", "moo ping",
    "gai yang", "larb", "yam", "phad", "phat", "panaeng", "panang",
    "yam pla", "tom kha", "kway teow", "kway teow",
]


def cdx_search(url_pattern: str, frm: str = "20220101", to: str = "20231231",
               limit: int = 80) -> list[dict]:
    """Query Wayback CDX API."""
    cdx = "http://web.archive.org/cdx/search/cdx"
    params = {
        "url": url_pattern,
        "from": frm,
        "to": to,
        "limit": str(limit),
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "urlkey",
    }
    try:
        r = requests.get(cdx, params=params, timeout=30, headers=HEADERS)
        if r.status_code != 200:
            return []
        rows = r.json()
        if not rows or len(rows) < 2:
            return []
        cols = rows[0]
        return [dict(zip(cols, row)) for row in rows[1:]]
    except Exception as e:
        print(f"CDX error: {e}")
        return []


def fetch_wayback(timestamp: str, original: str) -> str | None:
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.text
    except Exception:
        pass
    return None


def restaurant_name_from_url(url: str) -> str:
    m = re.search(r"Reviews-([^/]+)-Bangkok", url)
    if m:
        return m.group(1).replace("_", " ").strip()
    return "Unknown Bangkok Restaurant"


def extract_thb_prices(html: str, restaurant: str) -> list[dict]:
    """Find THB prices near food keywords in the page text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text_low = text.lower()
    out: list[dict] = []
    seen: set[tuple[str, float]] = set()

    for pat in THB_PATTERNS:
        for m in pat.finditer(text):
            try:
                price = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if not (10 <= price <= 5000):
                continue
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 40)
            ctx = text[start:end]
            ctx_low = ctx.lower()
            item = None
            for kw in ITEM_KEYWORDS:
                if kw in ctx_low:
                    idx = ctx_low.find(kw)
                    s = max(0, idx - 8)
                    e = min(len(ctx), idx + len(kw) + 12)
                    item = ctx[s:e].strip(" .,;:-—")
                    break
            if not item:
                continue
            # collapse whitespace
            item = re.sub(r"\s+", " ", item)
            if len(item) > 60:
                item = item[:60]
            key = (item.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "restaurant_name": restaurant,
                "item_name": item,
                "price": price,
                "currency": "THB",
            })
            if len(out) >= 6:
                break
        if len(out) >= 6:
            break
    return out


def insert_prices(rows: list[dict], source: str, url: str) -> int:
    if not rows:
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n = 0
    for r in rows:
        try:
            cur.execute(
                """INSERT INTO prices
                (restaurant_name, item_name, price, country, sector, source,
                 collection_date, url, currency)
                VALUES (?, ?, ?, 'Thailand', 'formal', ?, ?, ?, 'THB')""",
                (r["restaurant_name"], r["item_name"], r["price"],
                 source, TODAY, url),
            )
            n += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return n


def approach_b_wayback_tripadvisor() -> int:
    print("\n=== APPROACH B: Wayback TripAdvisor Bangkok ===")
    # Bangkok g293916, Chiang Mai g293917, Phuket g293920, Pattaya g293919
    snaps: list = []
    for geo in ("g293916", "g293917", "g293920", "g293919"):
        s = cdx_search(f"tripadvisor.com/Restaurant_Review-{geo}*",
                       "20220101", "20240601", 80)
        snaps.extend(s)
    print(f"CDX returned {len(snaps)} candidate snapshots across 4 Thai cities")
    total = 0
    attempted = 0
    for snap in snaps:
        if attempted >= 120:
            break
        original = snap["original"]
        ts = snap["timestamp"]
        attempted += 1
        html = fetch_wayback(ts, original)
        if not html:
            continue
        rest = restaurant_name_from_url(original)
        prices = extract_thb_prices(html, rest)
        if prices:
            n = insert_prices(prices, "Wayback/TripAdvisor", original)
            total += n
            print(f"  + {n:>2} prices from {rest[:50]}")
        time.sleep(0.4)
    print(f"Approach B total inserted: {total}")
    return total


def approach_c_direct_sites() -> int:
    """Try direct Thai chain websites and Wongnai static pages."""
    print("\n=== APPROACH C: Direct Thai restaurant sites + Wongnai ===")
    targets = [
        ("https://www.wongnai.com/restaurants?regions=9", "Wongnai", "Bangkok Wongnai"),
        ("https://food.grab.com/th/en/", "GrabFood TH", "GrabFood Thailand"),
        ("https://www.mkrestaurant.com/th/menu.html", "mkrestaurant.com", "MK Restaurant"),
    ]
    total = 0
    for url, source, rest in targets:
        try:
            r = requests.get(url, timeout=15, headers=HEADERS)
            if r.status_code != 200:
                print(f"  - {source}: HTTP {r.status_code}")
                continue
            prices = extract_thb_prices(r.text, rest)
            if prices:
                n = insert_prices(prices, source, url)
                total += n
                print(f"  + {n} prices from {source}")
            else:
                print(f"  - {source}: no extractable prices")
        except Exception as e:
            print(f"  - {source}: {str(e)[:60]}")
    print(f"Approach C total inserted: {total}")
    return total


def approach_d_wayback_chains() -> int:
    """Wayback snapshots of Thai chain menu pages."""
    print("\n=== APPROACH D: Wayback Thai chain menus ===")
    patterns = [
        "mkrestaurant.com/*menu*",
        "swensens.co.th/*menu*",
        "thepizzacompany.com/*menu*",
        "kfcth.com/*menu*",
        "mcdonalds.co.th/*menu*",
        "blackcanyoncoffee.com/*menu*",
        "afteryoudessertcafe.com/*menu*",
        "oishigroup.com/*menu*",
        "wongnai.com/restaurants/*",
    ]
    total = 0
    for pat in patterns:
        snaps = cdx_search(pat, "20210101", "20241231", 6)
        if not snaps:
            print(f"  - {pat}: no snapshots")
            continue
        for snap in snaps[:4]:
            html = fetch_wayback(snap["timestamp"], snap["original"])
            if not html:
                continue
            rest = pat.split("/")[0].split(".")[0]
            prices = extract_thb_prices(html, rest)
            if prices:
                n = insert_prices(prices, f"Wayback/{rest}", snap["original"])
                total += n
                print(f"  + {n} prices from {rest}")
            time.sleep(0.3)
    print(f"Approach D total inserted: {total}")
    return total


def main():
    print("Thailand data collection run:", TODAY)
    counts = {}
    counts["B_wayback_tripadvisor"] = approach_b_wayback_tripadvisor()
    counts["D_wayback_chains"] = approach_d_wayback_chains()
    counts["C_direct"] = approach_c_direct_sites()
    print("\n=== TOTALS ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    conn = sqlite3.connect(DB)
    final = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE country='Thailand'"
    ).fetchone()[0]
    conn.close()
    print(f"\nThailand rows in DB: {final}")
    with open("thailand_run.json", "w") as f:
        json.dump({"date": TODAY, "counts": counts, "final_rows": final}, f, indent=2)


if __name__ == "__main__":
    main()

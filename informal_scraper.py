"""
UIFPI — Informal Sector Image Scraper
Collects price board images from public Facebook pages, Google Images,
and a researcher-managed manual upload folder.

Sources (in priority order):
  1. Public Facebook pages of Singapore hawker centres
  2. Google Images searches per country
  3. images/manual/ — researcher-dropped JPG/PNG

Images are saved to: images/[country_code]/[source]/[date]/[filename]
All downloads logged to:  images/image_log.csv

Usage:
    python informal_scraper.py [--country sg] [--source all|facebook|google|manual]
"""

import argparse
import csv
import hashlib
import os
import re
import sys
import time
import urllib.parse
import warnings
from datetime import date
from pathlib import Path
from typing import Optional, Set

import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

IMAGES_DIR  = Path("images")
LOG_FILE    = IMAGES_DIR / "image_log.csv"
LOG_FIELDS  = ["filename", "country", "country_code", "source",
               "date_collected", "url", "processed", "item_count"]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

COUNTRY_CODES = {
    "Singapore": "sg", "Malaysia": "my", "Indonesia": "id",
    "Thailand": "th", "India": "in", "United States": "us",
    "United Kingdom": "gb", "Australia": "au",
}

# Facebook public pages for Singapore hawker centres.
# These are real, publicly listed business pages — no login required.
FACEBOOK_TARGETS = {
    "sg": [
        # Maxwell Food Centre area vendors
        {"page": "TianTianChickenRice",      "query": "chicken rice price menu"},
        {"page": "ZhenZhenCongee",           "query": "congee price menu"},
        # Old Airport Road Food Centre
        {"page": "OldAirportRoadFoodCentre", "query": "price menu"},
        # Lau Pa Sat
        {"page": "LauPaSatFestivalMarket",   "query": "satay price menu"},
        # Generic hawker search terms
        {"page": None, "query": "singapore hawker stall price board 2024"},
    ],
    "my": [
        {"page": None, "query": "warung makan malaysia harga menu papan"},
    ],
    "id": [
        {"page": None, "query": "warung makan indonesia harga makanan papan menu"},
    ],
    "th": [
        {"page": None, "query": "ร้านอาหาร ราคา เมนู อาหารข้างทาง"},
    ],
    "in": [
        {"page": None, "query": "dhaba menu price board india street food"},
    ],
}

# Google Images search queries per country code
GOOGLE_IMAGE_QUERIES = {
    "sg": [
        "hawker stall price board singapore",
        "hawker centre menu signboard singapore",
        "char kway teow price board singapore",
        "chicken rice price board maxwell singapore",
    ],
    "my": [
        "warung menu price malaysia",
        "mamak stall price board malaysia",
        "nasi lemak price signboard malaysia",
    ],
    "id": [
        "warung makan harga menu Indonesia",
        "nasi goreng harga papan menu",
        "warteg harga makanan",
    ],
    "th": [
        "ราคาอาหาร menu street food thailand",
        "ร้านอาหาร ราคา ป้าย",
        "pad thai price board street food",
    ],
    "in": [
        "dhaba menu price board india",
        "street food price board mumbai",
        "biryani price board india",
    ],
    "us": [
        "food truck menu price board USA",
        "street vendor price sign new york",
    ],
    "gb": [
        "market stall food price board UK",
        "street food menu price sign london",
    ],
    "au": [
        "food market stall price board australia",
        "street food price sign melbourne",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Logging helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_log():
    """Create image_log.csv with headers if it doesn't exist."""
    if not LOG_FILE.exists():
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS).writeheader()


def load_logged_urls() -> Set[str]:
    """Return the set of URLs already in the log."""
    if not LOG_FILE.exists():
        return set()
    with open(LOG_FILE) as f:
        return {row["url"] for row in csv.DictReader(f) if row.get("url")}


def append_log(row: dict):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="ignore")
        writer.writerow(row)


# ─────────────────────────────────────────────────────────────────────────────
# Image downloading
# ─────────────────────────────────────────────────────────────────────────────

def image_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:12]


def download_image(url: str, dest_dir: Path, country_code: str,
                   source: str, logged_urls: Set[str]) -> Optional[dict]:
    """Download one image, return log row dict or None on skip/failure."""
    if url in logged_urls:
        return None
    # Only accept image URLs
    clean = url.split("?")[0].lower()
    if not any(clean.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return None
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15, stream=True)
        if resp.status_code != 200:
            return None
        ctype = resp.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            return None
        data = resp.content
        if len(data) < 5_000:   # skip tiny/placeholder images
            return None
        ext      = ".jpg" if "jpeg" in ctype else (".png" if "png" in ctype else ".jpg")
        fname    = f"{image_hash(data)}{ext}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_path = dest_dir / fname
        out_path.write_bytes(data)
        return {
            "filename":       str(out_path.relative_to(IMAGES_DIR)),
            "country":        {v: k for k, v in COUNTRY_CODES.items()}.get(country_code, country_code),
            "country_code":   country_code,
            "source":         source,
            "date_collected": str(date.today()),
            "url":            url,
            "processed":      "0",
            "item_count":     "",
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Source A — Facebook public page search
# ─────────────────────────────────────────────────────────────────────────────

def scrape_facebook(country_code: str, max_per_query: int = 5) -> int:
    """
    Fetch images from Facebook public page photo posts.
    Uses the public Facebook search endpoint (no login).
    Returns count of new images downloaded.
    """
    targets   = FACEBOOK_TARGETS.get(country_code, [])
    logged    = load_logged_urls()
    dest_base = IMAGES_DIR / country_code / "facebook" / str(date.today())
    count     = 0
    session   = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    for target in targets:
        query = target.get("query", "")
        page  = target.get("page")

        # Build search URL for the Facebook page if specified, else general search
        if page:
            search_url = f"https://www.facebook.com/{page}/photos"
        else:
            enc_query  = urllib.parse.quote(query)
            search_url = f"https://www.facebook.com/search/photos/?q={enc_query}"

        try:
            resp = session.get(search_url, timeout=15)
            if resp.status_code != 200:
                print(f"  FB {search_url[:60]}... → HTTP {resp.status_code}")
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # Look for image tags and og:image meta
            img_urls: list[str] = []
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if "fbcdn" in src or "scontent" in src:
                    img_urls.append(src)
            # og:image
            for meta in soup.find_all("meta", property="og:image"):
                c = meta.get("content", "")
                if c:
                    img_urls.append(c)
            for url in img_urls[:max_per_query]:
                row = download_image(url, dest_base, country_code, "facebook", logged)
                if row:
                    append_log(row)
                    logged.add(url)
                    count += 1
                    print(f"  [FB] {country_code} ← {row['filename']}")
            time.sleep(1.5)
        except Exception as e:
            print(f"  [FB] Error scraping {search_url[:60]}: {e}")

    return count


# ─────────────────────────────────────────────────────────────────────────────
# Source B — Google Images
# ─────────────────────────────────────────────────────────────────────────────

def _extract_google_image_urls(html: str) -> list:
    """
    Extract full-resolution image URLs from a Google Images HTML response.
    Google encodes them as JSON inside <script> tags.
    """
    urls: list[str] = []
    # Pattern 1: full-res URLs in JS payload
    for match in re.finditer(r'"(https://[^"]+\.(?:jpg|jpeg|png|webp))"', html):
        url = match.group(1)
        if "gstatic" not in url and "google" not in url:
            urls.append(url)
    # Pattern 2: data-src / src attributes
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img", attrs={"data-src": True}):
        src = img["data-src"]
        if src.startswith("http"):
            urls.append(src)
    return list(dict.fromkeys(urls))   # dedupe, preserve order


def scrape_google_images(country_code: str, max_per_query: int = 6) -> int:
    """
    Fetch images from Google Images search results.
    Returns count of new images downloaded.
    """
    queries   = GOOGLE_IMAGE_QUERIES.get(country_code, [])
    logged    = load_logged_urls()
    dest_base = IMAGES_DIR / country_code / "google" / str(date.today())
    count     = 0
    session   = requests.Session()
    session.headers.update({
        **REQUEST_HEADERS,
        "Accept": "text/html,application/xhtml+xml",
    })

    for query in queries:
        enc    = urllib.parse.quote(query)
        url    = f"https://www.google.com/search?q={enc}&tbm=isch&hl=en&safe=off"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"  Google search HTTP {resp.status_code} for '{query[:40]}'")
                time.sleep(2)
                continue
            img_urls = _extract_google_image_urls(resp.text)
            saved = 0
            for img_url in img_urls:
                if saved >= max_per_query:
                    break
                row = download_image(img_url, dest_base, country_code,
                                     "google", logged)
                if row:
                    append_log(row)
                    logged.add(img_url)
                    count += 1
                    saved += 1
                    print(f"  [Google] {country_code} ← {row['filename']}")
            time.sleep(2)
        except Exception as e:
            print(f"  [Google] Error on '{query[:40]}': {e}")

    return count


# ─────────────────────────────────────────────────────────────────────────────
# Source C — Manual upload folder
# ─────────────────────────────────────────────────────────────────────────────

def process_manual_uploads() -> int:
    """
    Register any new JPG/PNG in images/manual/ that aren't already logged.
    Researcher drops images here; country is inferred from filename prefix
    or defaults to 'sg'.
    """
    manual_dir = IMAGES_DIR / "manual"
    manual_dir.mkdir(parents=True, exist_ok=True)
    logged = load_logged_urls()
    count  = 0

    for img_path in sorted(manual_dir.glob("*")):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        file_url = f"file://{img_path.resolve()}"
        if file_url in logged:
            continue
        # Infer country code from filename prefix: sg_xxx.jpg → sg
        name_lower = img_path.stem.lower()
        country_code = "sg"
        for code in COUNTRY_CODES.values():
            if name_lower.startswith(code + "_") or name_lower.startswith(code + "-"):
                country_code = code
                break

        # Register without moving — just log the path
        row = {
            "filename":       str(img_path.relative_to(IMAGES_DIR)),
            "country":        {v: k for k, v in COUNTRY_CODES.items()}.get(country_code, country_code),
            "country_code":   country_code,
            "source":         "manual",
            "date_collected": str(date.today()),
            "url":            file_url,
            "processed":      "0",
            "item_count":     "",
        }
        append_log(row)
        logged.add(file_url)
        count += 1
        print(f"  [Manual] Registered {img_path.name} (country={country_code})")

    return count


# ─────────────────────────────────────────────────────────────────────────────
# Summary helper
# ─────────────────────────────────────────────────────────────────────────────

def print_summary():
    if not LOG_FILE.exists():
        print("No images logged yet.")
        return
    with open(LOG_FILE) as f:
        rows = list(csv.DictReader(f))
    by_country = {}
    by_source  = {}
    for r in rows:
        cc = r.get("country_code", "?")
        s  = r.get("source", "?")
        by_country[cc] = by_country.get(cc, 0) + 1
        by_source[s]   = by_source.get(s, 0) + 1
    print(f"\n{'─'*50}")
    print(f"Total images logged : {len(rows)}")
    print(f"By country          : {dict(sorted(by_country.items()))}")
    print(f"By source           : {dict(sorted(by_source.items()))}")
    unprocessed = sum(1 for r in rows if r.get("processed") == "0")
    print(f"Awaiting extraction : {unprocessed}")
    print(f"{'─'*50}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UIFPI informal sector image scraper")
    parser.add_argument("--country", default="all",
                        help="Country code(s): sg,my,id,th,in,us,gb,au or 'all'")
    parser.add_argument("--source", default="all",
                        choices=["all", "facebook", "google", "manual"],
                        help="Which source to scrape")
    parser.add_argument("--max", type=int, default=6,
                        help="Max images per query (default 6)")
    args = parser.parse_args()

    ensure_log()

    target_codes = (
        list(COUNTRY_CODES.values())
        if args.country == "all"
        else [c.strip() for c in args.country.split(",")]
    )

    total = 0
    for code in target_codes:
        print(f"\n{'='*50}")
        print(f"Country: {code.upper()}")

        if args.source in ("all", "facebook"):
            n = scrape_facebook(code, max_per_query=args.max)
            print(f"  Facebook: {n} new images")
            total += n

        if args.source in ("all", "google"):
            n = scrape_google_images(code, max_per_query=args.max)
            print(f"  Google Images: {n} new images")
            total += n

    if args.source in ("all", "manual"):
        n = process_manual_uploads()
        print(f"\nManual uploads: {n} new images registered")
        total += n

    print(f"\nTotal new images this run: {total}")
    print_summary()


if __name__ == "__main__":
    main()

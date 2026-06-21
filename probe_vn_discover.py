"""Discover GrabFood VN restaurant URLs by browsing the location-seeded
home page and extracting chain/restaurant hrefs. Outputs candidate URLs
for the next probe round.
"""
import json
import re
import sys
from playwright.sync_api import sync_playwright

import live_scraper as L

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Vietnam chain names likely to appear on GrabFood VN — try discovering
# their restaurant pages by searching the GrabFood UI.
TARGET_CHAIN_NAMES = [
    "Highlands Coffee", "The Coffee House", "Phuc Long", "Trung Nguyen",
    "Starbucks", "Cong Caphe",
    "Pho 24", "Pho 2000", "Wrap & Roll",
    "Pizza Hut", "Domino's Pizza", "Pizza 4P's",
    "KFC", "Lotteria", "McDonald's", "Burger King", "Texas Chicken",
    "Bún Bò Huế", "Cơm Tấm",
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=USER_AGENT,
                locale="en-VN",
                timezone_id="Asia/Ho_Chi_Minh",
            )
            page = ctx.new_page()
            # Seed location cookie via our patched live_scraper helper
            L._seed_grabfood_location(page, "Vietnam")
            page.goto("https://food.grab.com/vn/en/", wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(3_000)
            L._seed_grabfood_location(page, "Vietnam")
            page.wait_for_timeout(2_000)

            print("=== Home page state ===", flush=True)
            print(f"   URL: {page.url}", flush=True)
            print(f"   Title: {page.title()!r}", flush=True)

            # Collect all chain/restaurant anchor hrefs across home + search pages
            collected = {}

            def collect_from_page():
                hrefs = page.evaluate("""() => {
                    const out = [];
                    for (const a of document.querySelectorAll('a[href*="/vn/en/restaurant/"], a[href*="/vn/en/chain/"]')) {
                        const href = a.getAttribute('href') || '';
                        let text = (a.innerText || '').trim().slice(0, 80);
                        if (!text) text = (a.getAttribute('aria-label') || '').slice(0, 80);
                        out.push({href, text});
                    }
                    return out;
                }""") or []
                for h in hrefs:
                    full = h["href"]
                    if full.startswith("/"):
                        full = "https://food.grab.com" + full
                    if "?" in full:
                        full = full.split("?")[0]
                    collected[full] = h.get("text") or ""

            collect_from_page()
            print(f"   Home anchors collected: {len(collected)}", flush=True)

            # Now do a few text searches via the search box if present
            for query in TARGET_CHAIN_NAMES[:8]:  # limit to top 8 to keep runtime reasonable
                try:
                    # Find any search input on the home page
                    search = page.query_selector(
                        'input[type="search"], input[placeholder*="earch"], input[placeholder*="ood"]'
                    )
                    if not search:
                        print(f"   No search box for {query!r}", flush=True)
                        continue
                    search.click()
                    page.wait_for_timeout(400)
                    search.fill("")
                    search.type(query, delay=40)
                    page.wait_for_timeout(2_500)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(4_000)
                    collect_from_page()
                    print(f"   After search {query!r}: {len(collected)} total URLs", flush=True)
                    # Go home for next search
                    page.goto("https://food.grab.com/vn/en/", wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(2_000)
                except Exception as e:
                    print(f"   Search for {query!r} failed: {e}", flush=True)

            print(f"\n=== Total unique URLs collected: {len(collected)} ===", flush=True)
            with open("vn_candidate_urls.json", "w", encoding="utf-8") as fh:
                json.dump(
                    [{"url": k, "anchor_text": v} for k, v in collected.items()],
                    fh, ensure_ascii=False, indent=2,
                )
            print("Saved to vn_candidate_urls.json", flush=True)
            for url, text in list(collected.items())[:40]:
                print(f"  {url}    [{text}]", flush=True)
        finally:
            browser.close()


if __name__ == "__main__":
    main()

"""Inspect VN GrabFood page price format so we can extend the parser."""
import re
from playwright.sync_api import sync_playwright
import live_scraper as L

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
URL = "https://food.grab.com/vn/en/restaurant/jollibee-pasteur-delivery/AWjmnWhPfYWaYaQC46R_"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                      user_agent=UA, locale="en-VN",
                                      timezone_id="Asia/Ho_Chi_Minh")
            page = ctx.new_page()
            L._seed_grabfood_location(page, "Vietnam")
            page.goto("https://food.grab.com/vn/en/", wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(3_000)
            L._seed_grabfood_location(page, "Vietnam")
            page.wait_for_timeout(2_000)
            page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(6_000)

            print(f"Title: {page.title()!r}")

            info = page.evaluate(r"""() => {
                const text = (document.body && document.body.innerText) || '';
                // Look for VND-ish numbers
                const dongMatches = text.match(/\d[\d,.]*\s*(?:₫|đ|VND|\bd\b)/gi) || [];
                const bigNums = text.match(/\b\d{1,3}[,.]?\d{3}\b/g) || [];
                // Sample MenuItem element class names / structure
                const sample = [];
                const items = document.querySelectorAll('[class*="MenuItem"], [class*="menuItem"]');
                for (let i = 0; i < Math.min(5, items.length); i++) {
                    sample.push({
                        idx: i,
                        cls: items[i].className.slice(0, 100),
                        text: (items[i].innerText || '').slice(0, 250)
                    });
                }
                return {
                    dong_matches: dongMatches.slice(0, 15),
                    big_nums:     bigNums.slice(0, 20),
                    item_count:   items.length,
                    samples:      sample,
                };
            }""")
            print(f"Dong matches: {info['dong_matches']}")
            print(f"Big numerics: {info['big_nums']}")
            print(f"MenuItem element count: {info['item_count']}")
            for s in info["samples"]:
                print(f"\n--- sample {s['idx']} ---")
                print(f"  class: {s['cls']!r}")
                print(f"  text: {s['text']!r}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()

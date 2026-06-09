from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    stealth_sync(page)  # masks Playwright fingerprints
    
    page.goto(
        "https://www.foodpanda.sg/chain/cr7aw/din-tai-fung",
        wait_until="networkidle"
    )
    page.wait_for_timeout(5000)
    print(f"Page title: {page.title()}")
    
    buttons = page.query_selector_all('[aria-label]')
    print(f"Total aria-label elements: {len(buttons)}")
    for btn in buttons[:10]:
        label = btn.get_attribute('aria-label')
        if label:
            print(f"  {label}")
    
    browser.close()

# test.py — run this separately to check each layer
import sys
print("Python working")

try:
    from playwright.sync_api import sync_playwright
    print("Playwright imported OK")
except ImportError:
    print("Playwright NOT installed — run: playwright install chromium")
    sys.exit()

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        print("Browser launched OK")
        page = browser.new_page()
        print("Page created OK")
        page.goto("https://www.foodpanda.sg/chain/cr7aw/din-tai-fung", 
                  wait_until="networkidle")
        print("Page loaded OK")
        
        # Print page title so we know content arrived
        print(f"Page title: {page.title()}")
        
        # Check what aria-labels actually exist
        buttons = page.query_selector_all('[aria-label*="cart"]')
        print(f"Buttons with 'cart' in aria-label: {len(buttons)}")
        
        # Print first 3 aria-labels so we can see the actual format
        for i, btn in enumerate(buttons[:3]):
            print(f"  Button {i+1}: {btn.get_attribute('aria-label')}")
        
        browser.close()
except Exception as e:
    print(f"Error: {e}")

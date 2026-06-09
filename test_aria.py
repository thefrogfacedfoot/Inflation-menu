from playwright.sync_api import sync_playwright

url = "https://www.foodpanda.sg/chain/cg9st/rubato-italian"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # visible window
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    
    # Give it extra time to fully render
    page.wait_for_timeout(5000)
    
    # Dump ALL aria-labels on the page
    elements = page.query_selector_all('[aria-label]')
    print(f"Total aria-label elements: {len(elements)}\n")
    
    for el in elements:
        label = el.get_attribute('aria-label')
        if label:
            print(label)
    
    input("Press Enter to close...")  # keeps browser open so you can inspect
    browser.close()

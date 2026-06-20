import requests
from time import sleep

def check_coverage(url_pattern, label, timeout=60):
    endpoint = "http://web.archive.org/cdx/search/cdx"
    params = {
        "url": url_pattern,
        "output": "json",
        "limit": 200,
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,length",
        "collapse": "urlkey"
    }
    for attempt in range(3):
        try:
            r = requests.get(endpoint, params=params, timeout=timeout)
            data = r.json()
            break
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            sleep(10)
    else:
        print(f"\n{label}: FAILED")
        return

    if len(data) <= 1:
        print(f"\n{label}: NO COVERAGE")
        return

    rows = data[1:]
    lengths = [int(r[2]) for r in rows if r[2].isdigit()]
    years = sorted(set(r[0][:4] for r in rows))
    real_pages = sum(1 for l in lengths if l > 3000)

    print(f"\n{label}")
    print(f"  Pages: {len(rows)} | Years: {years[0]}–{years[-1]} | Content pages: {real_pages}")
    if real_pages >= 50 and len(years) >= 3:
        print(f"  VERDICT: ✓ USABLE")
    elif real_pages >= 20 and len(years) >= 2:
        print(f"  VERDICT: ~ MARGINAL")
    else:
        print(f"  VERDICT: ✗ DROP")

targets = [
    ("tripadvisor.com.my/Restaurant_Review*",    "Malaysia — TripAdvisor"),
    ("tripadvisor.com/Restaurants-g294245*",     "Philippines (Manila) — TripAdvisor"),
    ("tripadvisor.com/Restaurants-g293916*",     "Thailand (Bangkok) — TripAdvisor"),
    ("tripadvisor.com/Restaurants-g304554*",     "India (Mumbai) — TripAdvisor"),
]

for url, label in targets:
    check_coverage(url, label)
    sleep(15)

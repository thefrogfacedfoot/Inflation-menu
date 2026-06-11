import requests
from time import sleep

def check_coverage(url_pattern, label, limit=200, timeout=60):
    endpoint = "http://web.archive.org/cdx/search/cdx"
    params = {
        "url": url_pattern,
        "output": "json",
        "limit": limit,
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,length",
        "collapse": "urlkey"
    }

    for attempt in range(3):  # retry up to 3 times
        try:
            r = requests.get(endpoint, params=params, timeout=timeout)
            data = r.json()
            break
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            sleep(10)
            continue
    else:
        print(f"\n{label}")
        print(f"  Result: FAILED AFTER 3 ATTEMPTS")
        return

    if len(data) <= 1:
        print(f"\n{label}")
        print(f"  Result: NO COVERAGE")
        return

    rows = data[1:]
    timestamps = [row[0] for row in rows]
    lengths = [int(row[2]) for row in rows if row[2].isdigit()]
    years = sorted(set(t[:4] for t in timestamps))
    avg_size = sum(lengths) / len(lengths) if lengths else 0
    real_pages = sum(1 for l in lengths if l > 3000)

    print(f"\n{label}")
    print(f"  Unique pages found : {len(rows)}")
    print(f"  Years covered      : {years[0]} – {years[-1]}")
    print(f"  Avg page size      : {avg_size:.0f} bytes")
    print(f"  Pages with content : {real_pages}  (>3KB)")

    if real_pages >= 50 and len(years) >= 3:
        print(f"  VERDICT            : ✓ USABLE")
    elif real_pages >= 20 and len(years) >= 2:
        print(f"  VERDICT            : ~ MARGINAL")
    else:
        print(f"  VERDICT            : ✗ DROP")

# Only retry the ones that failed — with longer gaps between
targets = [
    ("tripadvisor.com.sg/Restaurant_Review*",     "Singapore — TripAdvisor"),
    ("tripadvisor.co.uk/Restaurant_Review*",      "UK — TripAdvisor"),
    ("tripadvisor.com/Restaurants-g305226*",      "Nigeria (Lagos) — TripAdvisor"),
    ("tripadvisor.com.br/Restaurant_Review*",     "Brazil — TripAdvisor"),
    ("tripadvisor.com.au/Restaurant_Review*",     "Australia — TripAdvisor"),
]

for url_pattern, label in targets:
    check_coverage(url_pattern, label)
    sleep(15)  # longer gap to avoid rate limiting

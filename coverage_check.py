import requests
from time import sleep

def check_coverage(url_pattern, label, limit=500):
    endpoint = "http://web.archive.org/cdx/search/cdx"
    params = {
        "url": url_pattern,
        "output": "json",
        "limit": limit,
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,length",
        "collapse": "urlkey"  # one row per unique URL
    }

    try:
        r = requests.get(endpoint, params=params, timeout=30)
        data = r.json()
    except Exception as e:
        print(f"  ERROR for {label}: {e}")
        return

    if len(data) <= 1:
        print(f"\n{label}")
        print(f"  Result: NO COVERAGE")
        return

    rows = data[1:]  # strip header row

    timestamps = [row[0] for row in rows]
    lengths    = [int(row[2]) for row in rows if row[2].isdigit()]

    years = sorted(set(t[:4] for t in timestamps))
    avg_size = sum(lengths) / len(lengths) if lengths else 0

    # Pages under 3KB are almost certainly empty JS shells
    real_pages = sum(1 for l in lengths if l > 3000)

    print(f"\n{label}")
    print(f"  Unique pages found : {len(rows)}")
    print(f"  Years covered      : {years[0]} – {years[-1]}")
    print(f"  Year list          : {years}")
    print(f"  Avg page size      : {avg_size:.0f} bytes")
    print(f"  Pages with content : {real_pages}  (>3KB)")

    if real_pages >= 50 and len(years) >= 3:
        verdict = "✓ USABLE"
    elif real_pages >= 20 and len(years) >= 2:
        verdict = "~ MARGINAL"
    else:
        verdict = "✗ DROP THIS SOURCE"

    print(f"  VERDICT            : {verdict}")


# -------------------------------------------------------
# Target URLs to test
# TripAdvisor and Zomato are best bets — more static HTML
# Delivery apps (Grab, Foodpanda) will likely show poor coverage
# -------------------------------------------------------
targets = [
    # Singapore
    ("tripadvisor.com.sg/Restaurant_Review*",       "Singapore — TripAdvisor"),
    ("zomato.com/singapore/*/menu*",                "Singapore — Zomato"),
    ("openrice.com/en/singapore*",                  "Singapore — OpenRice"),

    # United States
    ("tripadvisor.com/Restaurant_Review-g60763*",   "US (NYC) — TripAdvisor"),
    ("yelp.com/biz/*",                              "US — Yelp"),

    # United Kingdom
    ("tripadvisor.co.uk/Restaurant_Review*",        "UK — TripAdvisor"),

    # India
    ("zomato.com/mumbai/*/menu*",                   "India (Mumbai) — Zomato"),
    ("zomato.com/delhi/*/menu*",                    "India (Delhi) — Zomato"),

    # Nigeria
    ("tripadvisor.com/Restaurants-g305226*",        "Nigeria (Lagos) — TripAdvisor"),

    # Brazil
    ("tripadvisor.com.br/Restaurant_Review*",       "Brazil — TripAdvisor"),

    # Indonesia
    ("zomato.com/jakarta/*/menu*",                  "Indonesia — Zomato"),
    ("tripadvisor.com/Restaurants-g294229*",        "Indonesia (Jakarta) — TripAdvisor"),

    # Australia
    ("tripadvisor.com.au/Restaurant_Review*",       "Australia — TripAdvisor"),
    ("zomato.com/sydney/*/menu*",                   "Australia (Sydney) — Zomato"),
]

print("=" * 55)
print("UIFPI — Wayback Machine Coverage Check")
print("=" * 55)
print("Testing archival coverage for each country/source.")
print("This takes ~10–15 minutes. Don't interrupt it.\n")

for url_pattern, label in targets:
    check_coverage(url_pattern, label)
    sleep(2)  # be polite to the API

print("\n" + "=" * 55)
print("SUMMARY")
print("=" * 55)
print("USABLE   = include in country sample")
print("MARGINAL = include with caveats, note in methodology")
print("DROP     = exclude from sample, document why")
print("\nUpdate your country sample based on these results.")
print("Any country with no USABLE source gets dropped.")

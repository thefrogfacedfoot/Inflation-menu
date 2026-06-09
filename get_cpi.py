import requests
import json
import os
from time import sleep

# -------------------------------------------------------
# Downloads official CPI data for all 8 target countries
# Source: World Bank Open Data API (free, no key needed)
# Indicator: FP.CPI.TOTL — Consumer Price Index (2010=100)
# -------------------------------------------------------

COUNTRIES = {
    "Singapore":     "SG",
    "United States": "US",
    "United Kingdom":"GB",
    "India":         "IN",
    "Nigeria":       "NG",
    "Brazil":        "BR",
    "Indonesia":     "ID",
    "Australia":     "AU"
}

# Date range — go back to 2015 to give enough history
DATE_RANGE = "2015:2025"

os.makedirs("cpi_data", exist_ok=True)

def get_cpi(country_name, country_code):
    url = (
        f"https://api.worldbank.org/v2/country/{country_code}"
        f"/indicator/FP.CPI.TOTL"
        f"?format=json&date={DATE_RANGE}&per_page=100"
    )

    try:
        r = requests.get(url, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"  ✗ {country_name}: request failed — {e}")
        return

    if len(data) < 2 or not data[1]:
        print(f"  ✗ {country_name}: no data returned")
        return

    records = data[1]

    # Filter to only rows with actual values
    clean = [
        {"year": rec["date"], "cpi": rec["value"]}
        for rec in records
        if rec["value"] is not None
    ]

    if not clean:
        print(f"  ✗ {country_name}: all values null")
        return

    # Sort by year ascending
    clean.sort(key=lambda x: x["year"])

    # Print summary
    print(f"\n  {country_name} ({country_code})")
    print(f"  Years with data: {clean[0]['year']} – {clean[-1]['year']}")
    print(f"  Data points: {len(clean)}")
    print(f"  Latest CPI: {clean[-1]['cpi']:.2f} ({clean[-1]['year']})")

    # Save to file
    filepath = f"cpi_data/cpi_{country_code.lower()}.json"
    with open(filepath, "w") as f:
        json.dump({
            "country": country_name,
            "country_code": country_code,
            "indicator": "FP.CPI.TOTL",
            "source": "World Bank",
            "data": clean
        }, f, indent=2)

    print(f"  Saved → {filepath}")


print("=" * 50)
print("UIFPI — Official CPI Data Download")
print("Source: World Bank Open Data API")
print("=" * 50)

for name, code in COUNTRIES.items():
    get_cpi(name, code)
    sleep(1)  # polite delay between requests

print("\n" + "=" * 50)
print("Done. Check the cpi_data/ folder.")
print("These files are your benchmark — what UIFPI")
print("will be validated against.")
print("=" * 50)

"""Canonical hardcoded fallback FX rates for the UIFPI pipeline.

Convention: 1 USD = FALLBACK_RATES[code] units of local currency
(divide a local price by its rate to get USD).

Single source of truth — previously duplicated (and drifted) across
live_scraper.py / index_builder.py / dashboard_data.py / image_processor.py.
Update rates here only.
"""

FALLBACK_RATES = {
    "SGD": 1.35, "MYR": 4.70, "IDR": 15_750.0, "THB": 36.0,
    "INR": 83.5, "USD": 1.0, "GBP": 0.79, "AUD": 1.55,
    "VND": 25_400.0, "AED": 3.67, "EUR": 0.93,
}

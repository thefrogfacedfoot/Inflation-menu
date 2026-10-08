#!/usr/bin/env python3
"""Check the confirmatory provenance whitelist on label strings (no DB, no data).

Run: python3 diagnostics/test_confirmatory_whitelist.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from index_builder import is_confirmatory_source  # noqa: E402

ADMITTED = ["wayback", "wayback-deliveroo", "wayback-doordash", "wayback-grabfood",
            "wayback-menupages", "wayback-menulog", "wayback-zomato",
            "Wayback/TripAdvisor", "Wayback/wongnai"]
QUARANTINED = ["js", "direct", "grabfood", "foodpanda", "swiggy",
               "official_price_series_bls_apu", "", None, "live-wayback-x"]

for s in ADMITTED:
    assert is_confirmatory_source(s), f"should admit {s!r}"
for s in QUARANTINED:
    assert not is_confirmatory_source(s), f"should quarantine {s!r}"
print(f"ok: {len(ADMITTED)} admitted, {len(QUARANTINED)} quarantined")

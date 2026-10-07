#!/usr/bin/env python3
"""Tests for the >=15 matched-restaurants rule and confirmatory cap handling (synthetic data only).

Run: python3 diagnostics/test_matched_rule.py   (needs pandas)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import index_builder as ib  # noqa: E402

def rows(country, month, names):
    return [{"country": country, "year_month": month, "restaurant_name": n} for n in names]

R = lambda lo, hi: [f"R{i}" for i in range(lo, hi)]
df = pd.DataFrame(
    rows("X", "2020-01", R(0, 20)) +      # base month: no previous month -> matched 0
    rows("X", "2020-02", R(0, 20)) +      # 20 matched with Jan  -> kept
    rows("X", "2020-03", R(0, 10)) +      # 10 matched with Feb  -> missing
    rows("X", "2020-04", R(0, 20)) +      # only 10 in Mar -> 10 matched -> missing
    rows("X", "2020-06", R(0, 20)) +      # May has no data: a gap is never bridged -> 0 -> missing
    rows("X", "2020-07", R(0, 15)) +      # exactly 15 matched with Jun -> kept
    rows("Y", "2020-02", R(100, 130)) +
    rows("Y", "2020-03", R(100, 114)))    # 14 matched -> missing
c = ib.matched_restaurant_counts(df)
assert c[("X", "2020-01")] == 0
assert c[("X", "2020-02")] == 20 and c[("X", "2020-03")] == 10 and c[("X", "2020-04")] == 10
assert c[("X", "2020-06")] == 0 and c[("X", "2020-07")] == 15
assert c[("Y", "2020-03")] == 14

index_rows = [{"country": "X", "year_month": m, "uifpi_combined": 100.0}
              for m in ("2020-01", "2020-02", "2020-03", "2020-04", "2020-06", "2020-07")] + \
             [{"country": "Y", "year_month": "2020-03", "uifpi_combined": 101.0}]
kept, dropped = ib.apply_matched_rule(index_rows, c)
assert [(r["country"], r["year_month"], r["matched_restaurants"]) for r in kept] == \
    [("X", "2020-02", 20), ("X", "2020-07", 15)]
assert {(a, b) for a, b, _ in dropped} == {("X", "2020-01"), ("X", "2020-03"), ("X", "2020-04"),
                                            ("X", "2020-06"), ("Y", "2020-03")}
assert ib.MIN_MATCHED_RESTAURANTS == 15
assert not hasattr(ib, "CONFIRMATORY_FIELDWORK_SOURCES"), "fieldwork is not an index input"
print("ok: matched-restaurant rule tests passed")

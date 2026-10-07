#!/usr/bin/env python3
"""Tests for the confirmatory matched-model index (synthetic data only).

Run: python3 diagnostics/test_confirmatory_index.py   (needs pandas, numpy)
"""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import index_builder as ib  # noqa: E402


def recs(country, ym, restaurants, items=("a",), price=10.0, cur="USD"):
    """restaurants: iterable of names; price: float or dict name->{item: price}"""
    out = []
    for r in restaurants:
        for it in items:
            p = price[r][it] if isinstance(price, dict) else price
            out.append({"country": country, "year_month": ym, "restaurant_name": r,
                        "item_name": it, "currency": cur, "price": p})
    return out


def build(rows, **kw):
    return ib.build_confirmatory_index(pd.DataFrame(rows), **kw)


R = lambda n, tag="R": [f"{tag}{i}" for i in range(n)]

# ── matched counts: calendar-adjacent months only ──
df = pd.DataFrame(recs("X", "2020-01", R(20)) + recs("X", "2020-02", R(20)) + recs("X", "2020-03", R(10)) +
                  recs("X", "2020-05", R(20)) + recs("X", "2020-06", R(15)))
c = ib.matched_restaurant_counts(df)
assert c[("X", "2020-01")] == 0 and c[("X", "2020-02")] == 20 and c[("X", "2020-03")] == 10
assert c[("X", "2020-05")] == 0, "May's previous calendar month (Apr) is absent: a gap is never bridged"
assert c[("X", "2020-06")] == 15

# ── chain maths: +10% each month for 3 months; first month has no link ──
rows, dropped = build(recs("X", "2020-01", R(15), price=10.0) + recs("X", "2020-02", R(15), price=11.0) +
                      recs("X", "2020-03", R(15), price=12.1))
assert [r["year_month"] for r in rows] == ["2020-02", "2020-03"]
assert abs(rows[0]["uifpi_combined"] - 110.0) < 1e-4 and abs(rows[1]["uifpi_combined"] - 121.0) < 1e-4
assert dropped == [("X", "2020-01", 0, 0)]
assert rows[0]["matched_restaurants"] == 15 and rows[0]["contributing_restaurants"] == 15

# ── calendar-consecutive only: Apr absent, so May has NO row; June restarts the chain at 100 * relative ──
rows, dropped = build(recs("X", "2020-02", R(15), price=10.0) + recs("X", "2020-03", R(15), price=11.0) +
                      recs("X", "2020-05", R(15), price=20.0) + recs("X", "2020-06", R(15), price=22.0))
assert [r["year_month"] for r in rows] == ["2020-03", "2020-06"], rows
assert abs(rows[1]["uifpi_combined"] - 110.0) < 1e-4, "restarted chain: 100 * 1.1, never bridging 03 -> 05"
assert ("X", "2020-05", 0, 0) in dropped

# ── >= 15 matched restaurants (14 -> missing, exactly 15 -> kept) ──
rows, dropped = build(recs("X", "2020-01", R(20)) + recs("X", "2020-02", R(14), price=11.0))
assert rows == [] and dropped[-1] == ("X", "2020-02", 14, 14)
rows, _ = build(recs("X", "2020-01", R(20)) + recs("X", "2020-02", R(15), price=11.0))
assert len(rows) == 1

# ── weights: geometric mean WITHIN restaurant, then EQUAL restaurant weights ──
# restaurant R0: item relatives 2 and 8 (GM 4); 14 other restaurants: one item, relative 1.
p0 = {"R0": {"a": 10.0, "b": 10.0}}
p1 = {"R0": {"a": 20.0, "b": 80.0}}
for r in R(15)[1:]:
    p0[r] = {"a": 10.0, "b": 10.0}
    p1[r] = {"a": 10.0}
m0 = recs("X", "2020-01", R(15), items=("a", "b"), price=p0)
m1 = [x for x in recs("X", "2020-02", R(15), items=("a", "b"), price={r: {"a": p1[r].get("a", 0), "b": p1[r].get("b", 0)} for r in R(15)})
      if not (x["restaurant_name"] != "R0" and x["item_name"] == "b")]
rows, _ = build(m0 + m1)
assert len(rows) == 1
want = 100.0 * math.exp((math.log(4.0) + 14 * 0.0) / 15)          # equal restaurant weights
item_weighted = 100.0 * math.exp((math.log(2) + math.log(8)) / 16)  # what item weighting would give
assert abs(rows[0]["uifpi_combined"] - want) < 1e-4 and abs(want - item_weighted) > 1.0, (rows[0], want)

# ── median of repeated captures within a month ──
rows, _ = build(recs("X", "2020-01", R(15), price=10.0) +
                recs("X", "2020-02", R(15), price=11.0) + recs("X", "2020-02", R(15), price=13.0) +
                recs("X", "2020-02", R(15), price=999.0))
assert abs(rows[0]["uifpi_combined"] - 130.0) < 1e-4, "median of (11, 13, 999) = 13"

# ── items must match within the same restaurant and currency; unmatched restaurants do not contribute ──
rows, dropped = build(recs("X", "2020-01", R(15), items=("a",), price=10.0) +
                      recs("X", "2020-02", R(15), items=("b",), price=11.0))
assert rows == [] and dropped[-1] == ("X", "2020-02", 15, 0), "restaurants observed in both but no matched ITEM: no valid link"
rows, _ = build(recs("X", "2020-01", R(15), cur="USD") + recs("X", "2020-02", R(15), price=11.0, cur="EUR"))
assert rows == [], "a different currency is a different item"
mixed = recs("X", "2020-01", R(16), price=10.0) + recs("X", "2020-02", R(15), price=11.0) + \
    recs("X", "2020-02", ["Z"], items=("other",), price=5.0)
rows, _ = build(mixed + recs("X", "2020-02", ["R15"], items=("other",), price=7.0))
assert rows[0]["matched_restaurants"] == 16 and rows[0]["contributing_restaurants"] == 15, \
    "R15 is observed in both months but has no matched item: it is not a contributing restaurant"
# ── the >= 15 rule applies to CONTRIBUTING restaurants: 20 observed in both months, only 14 with a matched item ──
m1 = recs("X", "2020-01", R(20), price=10.0)
m2 = recs("X", "2020-02", R(14), price=11.0) + recs("X", "2020-02", R(20)[14:], items=("other",), price=3.0)
rows, dropped = build(m1 + m2)
assert rows == [] and dropped[-1] == ("X", "2020-02", 20, 14), dropped
rows, dropped = build(m1 + recs("X", "2020-02", R(15), price=11.0) + recs("X", "2020-02", R(20)[15:], items=("other",), price=3.0))
assert len(rows) == 1 and rows[0]["matched_restaurants"] == 20 and rows[0]["contributing_restaurants"] == 15

# ── no leakage across countries ──
rows, _ = build(recs("X", "2020-01", R(15)) + recs("X", "2020-02", R(15), price=11.0) +
                recs("Y", "2020-01", R(15)) + recs("Y", "2020-02", R(15), price=9.0))
byc = {r["country"]: r["uifpi_combined"] for r in rows}
assert abs(byc["X"] - 110.0) < 1e-4 and abs(byc["Y"] - 90.0) < 1e-4
assert not hasattr(ib, "CONFIRMATORY_FIELDWORK_SOURCES") and not hasattr(ib, "apply_matched_rule")
print("ok: confirmatory matched-model index tests passed")

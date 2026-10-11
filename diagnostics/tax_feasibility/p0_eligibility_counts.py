"""Label-only count of eligible placebo anchors (prereg v2 section 5). Uses series availability (period labels) and the
event list only; no outcome value is read. Rules: h-month statistic from anchor m needs m and m+h present; no event month in
[m, m+h]; August 2020 is never an endpoint or anchor (UK); an anchor is eligible if >= 3 of its same-calendar-month
neighbours within +-36 months (m +- 12, 24, 36) are themselves base-eligible. The UK 500-matched-relatives rule is NOT applied
here (it needs quote counts), so UK N is an upper bound."""
import csv, sys

def idx(y, m): return y * 12 + (m - 1)

def months(a, b):
    return set(range(idx(*a), idx(*b) + 1))

def count(present, events, h, eoho=False):
    def base(m):
        if m not in present or (m + h) not in present: return False
        if any(m <= e <= m + h for e in events): return False
        if eoho and idx(2020, 8) in (m, m + h): return False
        return True
    B = {m for m in present if base(m)}
    E = {m for m in B if sum((m + k * 12) in B for k in (-3, -2, -1, 1, 2, 3)) >= 3}
    return len(B), len(E)

sg_events = [idx(2007, 7), idx(2023, 1), idx(2024, 1)]
uk_events = [idx(2011, 1), idx(2020, 7), idx(2021, 10), idx(2022, 4)]
series = {
    "SG restaurants/cafes/pubs, fast food (2005-01..2026-08)": months((2005, 1), (2026, 8)),
    "SG Hawker Centres only (2019-01..2026-08)": months((2019, 1), (2026, 8)),
    "SG M213761 full-span dishes (2015-01..2026-08)": months((2015, 1), (2026, 8)),
}
print("series | h | base-eligible | eligible (neighbour rule)")
for name, p in series.items():
    for h in (1, 2, 3):
        print(name, "|", h, "|", *count(p, sg_events, h), sep=" ")
with open("diagnostics/tax_feasibility/ons_catering_monthly_counts.csv") as f:
    r = csv.reader(f); hdr = next(r)
    col = hdr.index("month") if "month" in hdr else 0
    uk = set()
    for row in r:
        s = row[col].replace("-", "")[:6]
        uk.add(idx(int(s[:4]), int(s[4:6])))
print("UK months present:", len(uk), "(upper bound; before the 500-relative rule)")
for h in (1, 2, 3):
    print("UK catering quotes | h", h, "|", *count(uk, uk_events, h, eoho=True), sep=" ")

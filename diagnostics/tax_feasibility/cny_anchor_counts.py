"""Chinese New Year (CNY) exposure of placebo anchors, calendar only (prereg v2 section 5.1). No outcome value is read.
CNY dates 2005-2026 (Gregorian, first day of the lunar year); cross-checked against the `lunardate` package on 2026-10-10.
c(m,h) = 1 if the month containing CNY lies in [m+1, m+h] (the months over which the h-month change is measured)."""
CNY = {2005:(2,9),2006:(1,29),2007:(2,18),2008:(2,7),2009:(1,26),2010:(2,14),2011:(2,3),2012:(1,23),2013:(2,10),2014:(1,31),
       2015:(2,19),2016:(2,8),2017:(1,28),2018:(2,16),2019:(2,5),2020:(1,25),2021:(2,12),2022:(2,1),2023:(1,22),2024:(2,10),
       2025:(1,29),2026:(2,17)}
JAN = {y for y, (m, d) in CNY.items() if m == 1}
def idx(y, m): return y * 12 + m - 1
def months(a, b): return set(range(idx(*a), idx(*b) + 1))
cny_month = {y: idx(y, m) for y, (m, d) in CNY.items()}
def year_of(i): return i // 12
EV = [idx(2007, 7), idx(2023, 1), idx(2024, 1)]
arms = {"restaurants/fast food (2005-01..2026-08)": months((2005,1),(2026,8)),
        "hawker centres CPI class (2019-01..2026-08)": months((2019,1),(2026,8)),
        "M213761 10 full-span dishes (2015-01..2026-08)": months((2015,1),(2026,8))}
def base(P, h):
    return {m for m in P if (m + h) in P and not any(m <= e <= m + h for e in EV)}
def expo(m, h):  # CNY year whose CNY month lies in [m+1, m+h], else None
    for y, cm in cny_month.items():
        if m + 1 <= cm <= m + h: return y
    return None
def elig(B, S):  # neighbour rule inside the restricted set S
    return {m for m in S if sum((m + 12 * k) in S for k in (-3,-2,-1,1,2,3)) >= 3}
print("CNY year classes (Jan-CNY = CNY date in January):")
print(" Jan-CNY:", sorted(JAN)); print(" Feb-CNY:", sorted(set(CNY) - JAN))
for y in sorted(CNY): print(f"  {y}: {CNY[y][0]:02d}-{CNY[y][1]:02d} {'Jan' if y in JAN else 'Feb'}")
print("\narm | h | all eligible (rule of s.4) | A: exposure-matched, Jan-CNY windows (base / with >=3-neighbour rule) | B: anchors in Jan-CNY years (base / rule) | any-CNY exposed (base) | CNY-free windows (base)")
for name, P in arms.items():
    for h in (1, 2):
        B = base(P, h); E = elig(B, B)
        A = {m for m in B if expo(m, h) in JAN}
        Bj = {m for m in B if year_of(m + 1) in JAN}
        anyc = {m for m in B if expo(m, h) is not None}
        free = B - anyc
        print(f"{name} | {h} | {len(E)} | {len(A)} / {len(elig(A, A))} | {len(Bj)} / {len(elig(Bj, Bj))} | {len(anyc)} | {len(free)}")
print("\nSG-E0 (event 2007-07, anchor 2007-06, CNY 2007-02-18, a Feb-CNY year):")
for h in (1, 2, 3):
    print(f"  h={h}: c(anchor)={'1' if expo(idx(2007,6),h) else '0'}  (window months {h} after 2007-06; CNY month index {cny_month[2007]-idx(2007,6)} months after anchor)")

print("\nInformative anchors for the CNY-timing adjustment (R3): eligible anchors (s.4 rule) whose own c or j differs from the mean over their same-month neighbours")
def cj(m, h):
    y = expo(m, h); return (1 if y is not None else 0, 1 if (y in JAN) else 0)
for name, P in arms.items():
    for h in (1, 2):
        B = base(P, h); E = elig(B, B)
        n = 0
        for m in E:
            nb = [m + 12 * k for k in (-3,-2,-1,1,2,3) if (m + 12 * k) in B]
            c0, j0 = cj(m, h)
            cb = sum(cj(x, h)[0] for x in nb) / len(nb); jb = sum(cj(x, h)[1] for x in nb) / len(nb)
            if abs(c0 - cb) > 1e-9 or abs(j0 - jb) > 1e-9: n += 1
        print(f"{name} | h={h} | eligible {len(E)} | informative for R3: {n}")

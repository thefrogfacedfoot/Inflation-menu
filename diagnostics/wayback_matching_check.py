"""Read-only, counts only. (1) Matching-artifact check: rerun the existing-data feasibility with restaurants keyed by a
stable ID from the URL (Deliveroo slug, DoorDash store ID, GrabFood merchant ID; generic last path segment otherwise)
and item names normalised (lowercase, non-alphanumerics stripped), vs the old (restaurant_name, raw item) matching.
(2) Event-study coverage for wayback-doordash (US) and wayback-deliveroo (UK). V1/V2/V3 as in
wayback_existing_feasibility.py. Prices and relatives are never printed or written."""
import collections
import csv
import re
import sqlite3
import statistics
from pathlib import Path
from urllib.parse import urlparse

DB = Path("/Users/erwenchen/Inflation-menu/uifpi.db")
HERE = Path(__file__).resolve().parent
MIN_R = 15


def label(ym):
    return f"{ym // 12}-{ym % 12 + 1:02d}"


def to_ym(d):
    return int(d[:4]) * 12 + int(d[5:7]) - 1


def ymof(s):  # "YYYY-MM" -> ym
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def norm_item(s):
    return re.sub(r"[\W_]+", "", (s or "").lower())


def store_id(url, source):
    if not url:
        return None
    path = urlparse(url).path
    if source == "wayback-doordash":
        m = re.search(r"/store/(?:[^/?#]*-)?(\d+)", path)
        return f"dd{m.group(1)}" if m else None
    if source == "wayback-deliveroo":
        m = re.search(r"/menu/[^/]+/[^/]+/([^/?#]+)", path)
        return m.group(1).lower() if m else None
    if source == "wayback-grabfood":
        segs = [x for x in path.split("/") if x]
        if "restaurant" in segs and len(segs) > segs.index("restaurant") + 2:
            return segs[-1].upper()
        return segs[-1].lower() if segs else None
    segs = [x for x in path.split("/") if x and x != "menu"]
    return segs[-1].lower() if segs else None


def longest(months, ok):
    best, cur, prev = (0, None, None), 0, None
    for m in sorted(months):
        if ok(m):
            cur = cur + 1 if cur and m == prev + 1 else 1
            start = m if cur == 1 else start
            prev = m
            if cur > best[0]:
                best = (cur, start, m)
        else:
            cur = 0
    return best


def load():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur_of = {}
    for cn, cu, n in c.execute("select country,currency,count(*) from prices where lower(source) not like 'wayback%' and currency is not null group by 1,2 order by 3"):
        cur_of[cn] = cu
    for cn, cu, n in c.execute("select country,currency,count(*) from prices where currency is not null group by 1,2 order by 3"):
        cur_of.setdefault(cn, cu)
    rows = [r for r in c.execute("select country,restaurant_name,item_name,price,currency,source,collection_date,url from prices where lower(source) like 'wayback%'") if r[3] is not None and r[3] > 0 and r[4] == cur_of.get(r[0])]
    return rows


def build(rows, keyfn, itemfn):
    """Returns obs[(cn,ym)] -> set(rest), contrib, src_of, item_month, stats."""
    raw = collections.defaultdict(list)
    dropped_noid = collections.Counter()
    for cn, r, i, p, cu, s, d, u in rows:
        k = keyfn(r, s, u)
        if k is None:
            dropped_noid[s] += 1
            continue
        raw[(cn, k, itemfn(i), cu, d[:10])].append((p, s))
    month_prices = collections.defaultdict(list)
    src_of = collections.defaultdict(set)
    v2 = 0
    for (cn, k, i, cu, d), v in raw.items():
        if len({p for p, _ in v}) > 1:
            v2 += 1
            continue
        month_prices[(cn, k, i, cu, to_ym(d))].append(v[0][0])
        src_of[(cn, k)].add(v[0][1])
    obs = collections.defaultdict(set)
    byrest = collections.defaultdict(dict)
    for (cn, k, i, cu, ym), ps in month_prices.items():
        obs[(cn, ym)].add(k)
        byrest[(cn, k, i, cu)][ym] = statistics.median(ps)
    contrib = collections.defaultdict(set)
    v3 = pairs = 0
    for (cn, k, i, cu), d in byrest.items():
        for ym, p in d.items():
            q = d.get(ym - 1)
            if q is None:
                continue
            pairs += 1
            if not 0.5 <= p / q <= 2.0:
                v3 += 1
                continue
            contrib[(cn, ym)].add(k)
    return obs, contrib, src_of, byrest, dict(v2=v2, pairs=pairs, v3=v3, noid=dict(dropped_noid))


def summarise(obs, contrib, src_of):
    out = {}
    for cn in sorted({c for c, _ in obs}):
        months = sorted(m for (k, m) in obs if k == cn)
        reg = longest(months, lambda m: len(contrib.get((cn, m), ())) >= MIN_R)
        tpd = longest(months, lambda m: len(obs.get((cn, m), ())) >= MIN_R)
        drv = collections.Counter()
        if reg[0]:
            for m in range(reg[1], reg[2] + 1):
                for k in contrib[(cn, m)]:
                    for s in src_of[(cn, k)]:
                        drv[s] += 1 / len(src_of[(cn, k)])
        t = sum(drv.values()) or 1
        out[cn] = dict(reg=reg, tpd=tpd, peak_obs=max(len(obs[(cn, m)]) for m in months),
                       peak_contrib=max([len(contrib.get((cn, m), ())) for m in months] + [0]),
                       contrib15=sum(len(contrib.get((cn, m), ())) >= MIN_R for m in months),
                       obs15=sum(len(obs[(cn, m)]) >= MIN_R for m in months),
                       drivers={s: round(100 * v / t) for s, v in drv.most_common()},
                       sources=sorted({s for (k, r), ss in src_of.items() if k == cn for s in ss}))
    return out


QSR = re.compile(r"mcdonald|burger king|wendy|taco bell|\bkfc\b|kentucky fried|subway|chick-?fil|popeye|domino|pizza hut|papa john|little caesar|starbucks|dunkin|chipotle|panda express|sonic drive|jack in the box|arby|carl'?s jr|hardee|five guys|panera|jersey mike|jimmy john|wingstop|in-?n-?out|shake shack|whataburger|del taco|culver|raising cane|zaxby|bojangles|white castle|qdoba|moe'?s southwest|church'?s chicken|a&w|dairy queen|krispy kreme|baskin|jamba|tim hortons|firehouse subs|el pollo loco|checkers|rally'?s|wienerschnitzel|freddy|smashburger|habit burger|nathan'?s|papa murphy|marco'?s pizza|cici|round table", re.I)


def main():
    rows = load()
    print("wayback rows with price>0 and registered currency:", len(rows))
    old = build(rows, lambda r, s, u: r, lambda i: i)
    # hybrid key: stable ID from the URL; where the URL carries no store identity (DoorDash $-filter URLs, 35% of
    # DoorDash rows) the restaurant_name (backfilled from the page's JSON-LD) is used as the key
    new = build(rows, lambda r, s, u: store_id(u, s) or f"name:{r}", norm_item)
    so, sn = summarise(*old[:3]), summarise(*new[:3])
    print("old:", {k: v for k, v in old[4].items()}, "\nnew:", {k: v for k, v in new[4].items()})
    print(f"\n{'country':20s} {'n_reg':>5s} {'window_reg':>17s} {'n_tpd':>5s} {'window_tpd':>17s} {'peak_obs':>8s} {'peak_contr old->new':>20s} {'months contr>=15 old->new':>26s}  drivers(new)")
    for cn in sn:
        s, o = sn[cn], so.get(cn, dict(peak_contrib=0, contrib15=0))
        wr = f"{label(s['reg'][1])}..{label(s['reg'][2])}" if s["reg"][0] else "-"
        wt = f"{label(s['tpd'][1])}..{label(s['tpd'][2])}" if s["tpd"][0] else "-"
        print(f"{cn:20s} {s['reg'][0]:5d} {wr:>17s} {s['tpd'][0]:5d} {wt:>17s} {s['peak_obs']:8d} {o['peak_contrib']:>9d} -> {s['peak_contrib']:<6d} {o['contrib15']:>12d} -> {s['contrib15']:<8d}  {s['drivers'] or s['sources']}")
    for thr in (36, 100):
        print(f"countries n_reg>={thr} (new):", [c for c, s in sn.items() if s["reg"][0] >= thr], "| n_tpd:", [c for c, s in sn.items() if s["tpd"][0] >= thr])
    obs, contrib, src_of, byrest, st = new
    with open(HERE / "wayback_matching_check_counts.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["country", "month", "restaurants_observed_id", "restaurants_contributing_id"])
        for (cn, ym) in sorted(obs):
            w.writerow([cn, label(ym), len(obs[(cn, ym)]), len(contrib.get((cn, ym), ()))])

    # ---- 2a DoorDash US ------------------------------------------------------
    print("\n== 2a wayback-doordash (US), ID = store ID from URL. State/address are NOT stored in the DB (URL carries only the store ID) -> California split not derivable.")
    names = {}
    for cn, r, i, p, cu, s, d, u in rows:
        if s == "wayback-doordash" and cn == "United States":
            k = store_id(u, s)
            if k:
                names.setdefault(k, r)
    nodd = sum(1 for cn, r, i, p, cu, s, d, u in rows if s == "wayback-doordash" and store_id(u, s) is None)
    print(f"doordash rows without a store ID (junk $-filter URLs, keyed by name instead): {nodd}")
    for cn, r, i, p, cu, s, d, u in rows:
        if s == "wayback-doordash" and cn == "United States" and store_id(u, s) is None:
            names.setdefault(f"name:{r}", r)
    dd = {ym: {k for k in obs[("United States", ym)] if "wayback-doordash" in src_of[("United States", k)]} for (cn, ym) in list(obs) if cn == "United States"}
    stores_by_month = {ym: {k for k in v} for ym, v in dd.items()}
    with open(HERE / "wayback_event_study_counts.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["panel", "key", "value"])
        print("month   distinct DoorDash stores observed (all states) | of which name matches a QSR chain")
        for ym in range(ymof("2023-01"), ymof("2025-06") + 1):
            s = stores_by_month.get(ym, set())
            q = sum(bool(QSR.search(names.get(k, ""))) for k in s)
            print(f"{label(ym)}  {len(s):4d} | {q:3d}")
            w.writerow(["dd_month", label(ym), len(s)]); w.writerow(["dd_month_qsr", label(ym), q])
        def win(a, b):
            out = set()
            for ym in range(ymof(a), ymof(b) + 1):
                out |= stores_by_month.get(ym, set())
            return out
        A, B = win("2023-10", "2024-03"), win("2024-04", "2024-09")
        both = A & B
        # matched-item version: a store observed in both windows with >=1 common normalised item
        def items(win_a, win_b):
            n = 0
            for k in both:
                ia = {key[2] for key in byrest if key[0] == "United States" and key[1] == k for ym in byrest[key] if win_a[0] <= ym <= win_a[1]}
                ib = {key[2] for key in byrest if key[0] == "United States" and key[1] == k for ym in byrest[key] if win_b[0] <= ym <= win_b[1]}
                n += bool(ia & ib)
            return n
        common = items((ymof("2023-10"), ymof("2024-03")), (ymof("2024-04"), ymof("2024-09")))
        qb = sum(bool(QSR.search(names.get(k, ""))) for k in both)
        print(f"windows 2023-10..2024-03: {len(A)} stores; 2024-04..2024-09: {len(B)} stores; in BOTH: {len(both)} (QSR-name chains {qb}; with >=1 common normalised item: {common})")
        print("California vs non-California: NOT DERIVABLE from the DB (no state/address field). Needs a store-page fetch (JSON-LD addressRegion) per store ID.")
        for k, v in (("A_stores", len(A)), ("B_stores", len(B)), ("both", len(both)), ("both_qsr", qb), ("both_common_item", common)):
            w.writerow(["dd_windows", k, v])

        # ---- 2b Deliveroo UK ----------------------------------------------------
        print("\n== 2b wayback-deliveroo (UK), ID = Deliveroo slug")
        uk = {ym: {k for k in obs[("United Kingdom", ym)] if "wayback-deliveroo" in src_of[("United Kingdom", k)]} for (cn, ym) in list(obs) if cn == "United Kingdom"}
        print("month   distinct restaurants (2019-06..2022-12)")
        line = []
        for ym in range(ymof("2019-06"), ymof("2022-12") + 1):
            n = len(uk.get(ym, ()))
            line.append(f"{label(ym)}:{n}")
            w.writerow(["uk_month", label(ym), n])
        print("  ".join(line))
        for ev in ("2020-07-15", "2021-10-01", "2022-04-01"):
            e = to_ym(ev)
            day = int(ev[8:])
            # before: the 3 calendar months before the event month, after: the 3 calendar months starting the month after;
            # the event month itself is excluded for mid-month events (2020-07-15), included in 'after' for first-of-month events
            if day == 1:
                bef, aft = range(e - 3, e), range(e, e + 3)
            else:
                bef, aft = range(e - 3, e), range(e + 1, e + 4)
            Bs = set().union(*[uk.get(m, set()) for m in bef]); As = set().union(*[uk.get(m, set()) for m in aft])
            common_items = 0
            for k in Bs & As:
                ib = {key[2] for key in byrest if key[0] == "United Kingdom" and key[1] == k for m in bef if m in byrest[key]}
                ia = {key[2] for key in byrest if key[0] == "United Kingdom" and key[1] == k for m in aft if m in byrest[key]}
                common_items += bool(ib & ia)
            print(f"{ev}: before({label(bef[0])}..{label(bef[-1])}) {len(Bs)} restaurants; after({label(aft[0])}..{label(aft[-1])}) {len(As)}; both sides {len(Bs & As)}; both with >=1 common normalised item {common_items}")
            for k, v in (("before", len(Bs)), ("after", len(As)), ("both", len(Bs & As)), ("both_common_item", common_items)):
                w.writerow(["uk_event_" + ev, k, v])


if __name__ == "__main__":
    main()

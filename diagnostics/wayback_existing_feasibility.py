"""Feasibility from EXISTING wayback-* rows in uifpi.db (read-only; counts only).

Applies the proposed §6 validation logic of docs/prereg_implementation_notes.md to wayback-* rows:
  V1 price > 0 and currency == country's registered (modal live) currency; price_usd is not used.
  V2 any (restaurant, item, currency, date) with > 1 distinct price is excluded for that date;
     the monthly price is the median over the remaining dates.
  V3 item relatives vs the previous CALENDAR month outside [0.5, 2.0] are excluded.
Per country-month: restaurants observed (>= 1 valid item-month) and contributing restaurants
(>= 1 matched item with a valid relative, consecutive months only). Longest runs under
  - registered rule: contributing >= 15, consecutive months
  - TPD-style rule : observed >= 15, no t-1 requirement (comparison only)
n = number of months in the run. Prices and relatives are never written out: only counts.
"""
import collections
import csv
import sqlite3
import statistics
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "uifpi.db"
if not DB.exists():
    DB = Path("/Users/erwenchen/Inflation-menu/uifpi.db")
OUT = Path(__file__).resolve().parent / "wayback_existing_feasibility_counts.csv"
MIN_R = 15


def ym_prev(ym):
    y, m = divmod(ym, 12)       # ym = year*12 + (month-1)
    return ym - 1


def label(ym):
    return f"{ym // 12}-{ym % 12 + 1:02d}"


def longest(months, ok):
    best, cur, start = (0, None, None), 0, None
    for m in sorted(months):
        if ok(m):
            if cur and m == prev + 1:
                cur += 1
            else:
                cur, start = 1, m
            prev = m
            if cur > best[0]:
                best = (cur, start, m)
        else:
            cur = 0
    return best


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur_of = {}
    for cn, cu, n in c.execute("select country,currency,count(*) from prices where source not like 'wayback%' and source not like 'Wayback%' and currency is not null group by 1,2 order by 3"):
        cur_of[cn] = cu                      # last (largest) wins
    for cn, cu, n in c.execute("select country,currency,count(*) from prices where currency is not null group by 1,2 order by 3"):
        cur_of.setdefault(cn, cu)
    raw = collections.defaultdict(list)       # (country, restaurant, item, currency, date) -> [(price, source)]
    n_all = n_v1 = 0
    for cn, r, i, p, cu, s, d in c.execute("select country,restaurant_name,item_name,price,currency,source,collection_date from prices where lower(source) like 'wayback%'"):
        n_all += 1
        if p is None or not p > 0 or cu != cur_of.get(cn):
            continue
        n_v1 += 1
        raw[(cn, r, i, cu, d[:10])].append((p, s))
    # V2
    month_prices = collections.defaultdict(list)   # (country, restaurant, item, currency, ym) -> [price per remaining date]
    src_of = {}
    n_v2_cells = 0
    for (cn, r, i, cu, d), v in raw.items():
        if len({p for p, _ in v}) > 1:
            n_v2_cells += 1
            continue
        ym = int(d[:4]) * 12 + int(d[5:7]) - 1
        month_prices[(cn, r, i, cu, ym)].append(v[0][0])
        src_of[(cn, r)] = src_of.get((cn, r)) or set()
        src_of[(cn, r)].add(v[0][1])
    item_month = {k: statistics.median(v) for k, v in month_prices.items()}
    obs = collections.defaultdict(set)        # (country, ym) -> restaurants
    byrest = collections.defaultdict(dict)    # (country, restaurant, item, currency) -> {ym: price}
    for (cn, r, i, cu, ym), p in item_month.items():
        obs[(cn, ym)].add(r)
        byrest[(cn, r, i, cu)][ym] = p
    contrib = collections.defaultdict(set)
    n_pairs = n_v3 = 0
    for (cn, r, i, cu), d in byrest.items():
        for ym, p in d.items():
            q = d.get(ym - 1)
            if q is None:
                continue
            n_pairs += 1
            rel = p / q
            if not 0.5 <= rel <= 2.0:
                n_v3 += 1
                continue
            contrib[(cn, ym)].add(r)
    print(f"wayback rows {n_all}; after V1 {n_v1}; V2 removed item-date cells {n_v2_cells}; relatives {n_pairs}, V3 excluded {n_v3}")
    countries = sorted({cn for cn, _ in obs})
    rows, summary = [], {}
    for cn in countries:
        months = sorted(ym for (k, ym) in obs if k == cn)
        for ym in range(months[0], months[-1] + 1):
            rows.append((cn, label(ym), len(obs.get((cn, ym), ())), len(contrib.get((cn, ym), ()))))
        reg = longest(months, lambda m: len(contrib.get((cn, m), ())) >= MIN_R)
        tpd = longest(months, lambda m: len(obs.get((cn, m), ())) >= MIN_R)
        drv = collections.Counter()
        if reg[0]:
            for m in range(reg[1], reg[2] + 1):
                for r in contrib[(cn, m)]:
                    for s in src_of[(cn, r)]:
                        drv[s] += 1.0 / len(src_of[(cn, r)])
        tot = sum(drv.values()) or 1
        allsrc = collections.Counter(s for (k, r), ss in src_of.items() if k == cn for s in ss)
        summary[cn] = dict(reg=reg, tpd=tpd, drivers={s: round(100 * v / tot) for s, v in drv.most_common()},
                           sources=dict(allsrc), months_obs=len(months),
                           obs15=sum(len(obs[(cn, m)]) >= MIN_R for m in months),
                           consec=sum((cn, m - 1) in obs for m in months),
                           contrib15=sum(len(contrib.get((cn, m), ())) >= MIN_R for m in months),
                           first=label(months[0]), last=label(months[-1]),
                           max_obs=max(len(obs[(cn, m)]) for m in months), max_contrib=max([len(contrib.get((cn, m), ())) for m in months] + [0]))
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["country", "month", "restaurants_observed", "restaurants_contributing"])
        w.writerows(rows)
    print(f"\n{'country':20s} {'n_reg':>5s} {'window_reg':>17s} {'n_tpd':>5s} {'window_tpd':>17s} {'max_obs':>7s} {'max_contr':>9s}  drivers(% of contributing restaurant-months)")
    for cn, s in summary.items():
        wr = f"{label(s['reg'][1])}..{label(s['reg'][2])}" if s["reg"][0] else "-"
        wt = f"{label(s['tpd'][1])}..{label(s['tpd'][2])}" if s["tpd"][0] else "-"
        print(f"{cn:20s} {s['reg'][0]:5d} {wr:>17s} {s['tpd'][0]:5d} {wt:>17s} {s['max_obs']:7d} {s['max_contrib']:9d}  {s['drivers'] or s['sources']}")
    print(f"\n{'country':20s} {'first':>8s} {'last':>8s} {'months_with_data':>16s} {'obs>=15':>8s} {'consec_pairs':>12s} {'contrib>=15':>11s}")
    for cn, s in summary.items():
        print(f"{cn:20s} {s['first']:>8s} {s['last']:>8s} {s['months_obs']:16d} {s['obs15']:8d} {s['consec']:12d} {s['contrib15']:11d}")
    for thr in (36, 100):
        print(f"countries with n_reg >= {thr}:", [cn for cn, s in summary.items() if s["reg"][0] >= thr],
              "| n_tpd >=", thr, [cn for cn, s in summary.items() if s["tpd"][0] >= thr])


if __name__ == "__main__":
    main()

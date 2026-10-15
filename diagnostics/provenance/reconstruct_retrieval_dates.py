#!/usr/bin/env python3
"""Reconstruct WHEN archival (Wayback) rows were retrieved, from row ids.

For archival rows prices.collection_date is the Wayback SNAPSHOT date, not the
date the project fetched the page. The retrieval date is not stored, but
prices.id is AUTOINCREMENT, so ids are in insertion order, and live-scrape rows
(sources direct, grabfood, js, foodpanda) carry their true scrape date in
collection_date. So for an archival row with id i:
    retrieved on or after  = scrape date of the largest live id below i
    retrieved on or before = scrape date of the smallest live id above i
(rows before the first live row have no lower anchor; rows after the last have
no upper anchor). The script checks the assumption: live ids must be
non-decreasing in date, and every DB backup whose filename carries a timestamp
must contain no row whose lower bound is later than the backup date.

Read-only by default. Prints a per-source/country/bracket summary and writes it
to docs/data_provenance_retrieval_brackets.csv.

--write   back up uifpi.db (repo convention), then add and populate
          prices.retrieved_at (= upper bound date, "on or before") and
          prices.retrieved_at_basis ('reconstructed_id_bracket') for archival
          rows only. Live rows are left NULL: their collection_date already is
          the retrieval date. Refuses to run while live_scraper.py is running.

Usage: python3 diagnostics/provenance/reconstruct_retrieval_dates.py [--db uifpi.db] [--write]
"""
import argparse
import bisect
import csv
import glob
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LIVE = ("direct", "grabfood", "js", "foodpanda")
ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = ROOT / "docs" / "data_provenance_retrieval_brackets.csv"


def archival_where():
    return "(lower(source) LIKE 'wayback%')"


def anchors(con):
    q = f"SELECT id, collection_date FROM prices WHERE source IN ({','.join('?' * len(LIVE))}) ORDER BY id"
    rows = con.execute(q, LIVE).fetchall()
    bad = sum(1 for a, b in zip(rows, rows[1:]) if b[1] < a[1])
    return [r[0] for r in rows], [r[1] for r in rows], bad


def bracket(ids, dates, i):
    k = bisect.bisect_left(ids, i)
    lo = dates[k - 1] if k > 0 else None
    hi = dates[k] if k < len(ids) else None
    return lo, hi


def check_backups(arch_ids, ids, dates):
    """For every backup with a date in its name: its largest archival id must
    have a lower bound on or before the backup date, and the next archival id in
    the current DB (inserted after the backup) an upper bound on or after it. Rows deleted since the backup are not in the current
    DB, so this checks the id-date mapping, not row counts."""
    out = []
    for f in sorted(glob.glob(str(ROOT / "uifpi.db.backup_*"))):
        if f.endswith(("-shm", "-wal")):
            continue
        m = re.search(r"(20\d{6})(?:_(\d{6}))?$", f)
        if not m:
            continue
        bdate = datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        try:
            b = sqlite3.connect(f"file:{f}?immutable=1", uri=True)
            mx = b.execute(f"SELECT max(id) FROM prices WHERE {archival_where()}").fetchone()[0]
            b.close()
        except sqlite3.Error as e:
            out.append((Path(f).name, bdate, None, None, f"unreadable: {e}"))
            continue
        if mx is None:
            out.append((Path(f).name, bdate, None, None, "no archival rows"))
            continue
        lo, _ = bracket(ids, dates, mx)
        k = bisect.bisect_right(arch_ids, mx)
        hi = bracket(ids, dates, arch_ids[k])[1] if k < len(arch_ids) else None
        ok = (lo is None or lo <= bdate) and (hi is None or hi >= bdate)
        out.append((Path(f).name, bdate, mx, f"{lo}/{hi}", "OK" if ok else "VIOLATION"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "uifpi.db"))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--skip-backup-check", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    ids, dates, bad = anchors(con)
    print(f"live anchor rows: {len(ids)}; date decreases with id: {bad}")
    if bad:
        sys.exit("id order does not match live scrape dates; reconstruction invalid")

    agg = defaultdict(lambda: [0, None, None, None, None])
    per_row = []
    for rid, src, ctry, snap in con.execute(
            f"SELECT id, source, country, collection_date FROM prices WHERE {archival_where()} ORDER BY id"):
        lo, hi = bracket(ids, dates, rid)
        per_row.append((rid, hi))
        g = agg[(src, ctry, lo, hi)]
        g[0] += 1
        g[1] = rid if g[1] is None else min(g[1], rid)
        g[2] = rid if g[2] is None else max(g[2], rid)
        g[3] = snap if g[3] is None else min(g[3], snap)
        g[4] = snap if g[4] is None else max(g[4], snap)
    con.close()

    rows = [{"source": s, "country": c, "retrieved_on_or_after": lo or "", "retrieved_on_or_before": hi or "",
             "rows_in_current_db": v[0], "min_id": v[1], "max_id": v[2],
             "snapshot_date_min": v[3], "snapshot_date_max": v[4]}
            for (s, c, lo, hi), v in sorted(agg.items(), key=lambda kv: kv[1][1])]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['source']:20s} {r['country']:22s} {r['retrieved_on_or_after'] or '-':>10s} .. "
              f"{r['retrieved_on_or_before'] or '-':10s} n={r['rows_in_current_db']:>7} "
              f"snap {r['snapshot_date_min']}..{r['snapshot_date_max']}")
    print(f"wrote {OUT_CSV}")

    if not a.skip_backup_check:
        print("\nbackup consistency (max archival id in each backup vs its filename date):")
        for name, bdate, mx, lo, status in check_backups([r[0] for r in per_row], ids, dates):
            print(f"  {name:62s} {bdate} max_id={mx} lower/next_upper={lo} {status}")

    if a.write:
        running = subprocess.run(["pgrep", "-f", "live_scraper.py"], capture_output=True, text=True).stdout.strip()
        if running:
            sys.exit("live_scraper.py is running; not writing")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = f"{a.db}.backup_pre_retrieved_at_{stamp}"
        src = sqlite3.connect(a.db)
        dst = sqlite3.connect(bak)
        src.backup(dst)
        dst.close()
        print(f"backup: {bak}")
        cols = {r[1] for r in src.execute("PRAGMA table_info(prices)")}
        if "retrieved_at" not in cols:
            src.execute("ALTER TABLE prices ADD COLUMN retrieved_at TEXT")
        if "retrieved_at_basis" not in cols:
            src.execute("ALTER TABLE prices ADD COLUMN retrieved_at_basis TEXT")
        src.executemany("UPDATE prices SET retrieved_at = ?, retrieved_at_basis = 'reconstructed_id_bracket' WHERE id = ?",
                        [(hi, rid) for rid, hi in per_row])
        src.commit()
        n = src.execute("SELECT count(*) FROM prices WHERE retrieved_at_basis = 'reconstructed_id_bracket'").fetchone()[0]
        src.close()
        print(f"populated retrieved_at for {n} archival rows")


if __name__ == "__main__":
    main()

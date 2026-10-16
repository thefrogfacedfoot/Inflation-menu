#!/usr/bin/env python3
"""Data freeze for the analysis: one frozen, hashed copy of uifpi.db.

Rule: the analysis uses exactly the prices rows written on or before FREEZE_AT
(docs/data_freeze_config.json, SGT). Rows carry prices.inserted_at (SGT, set
by live_scraper.insert_item); older rows have NULL. Because prices.id is
AUTOINCREMENT, the cut is "id <= max id whose inserted_at <= FREEZE_AT", which
also covers the NULL rows written before inserted_at existed. Archival rows'
retrieval dates are documented separately (docs/data_provenance.md).

The nightly scraper and the dashboard keep using uifpi.db; nothing here writes
to it.

  python3 data_freeze.py snapshot   # at/after FREEZE_AT: copy, cut, hash, write docs/data_freeze.json
  python3 data_freeze.py verify     # check the frozen file against the manifest
  python3 data_freeze.py workcopy   # (re)create the working copy and print its path

Analysis on the frozen data runs on the working copy, never on the pristine
frozen file (index_builder writes tables back into its DB):
  python3 index_builder.py --db "$(python3 data_freeze.py workcopy)"
  UICPI_DB="$(python3 data_freeze.py workcopy)" python3 granger_analysis.py --min-obs 24

Env overrides (testing): UICPI_DB_LIVE, UICPI_FREEZE_CONFIG, UICPI_FREEZE_DIR, UICPI_FREEZE_MANIFEST.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SGT = timezone(timedelta(hours=8))
LIVE_DB = Path(os.environ.get("UICPI_DB_LIVE", ROOT / "uifpi.db"))
CONFIG = Path(os.environ.get("UICPI_FREEZE_CONFIG", ROOT / "docs" / "data_freeze_config.json"))
FREEZE_DIR = Path(os.environ.get("UICPI_FREEZE_DIR", ROOT))
MANIFEST = Path(os.environ.get("UICPI_FREEZE_MANIFEST", ROOT / "docs" / "data_freeze.json"))


def freeze_at():
    cfg = json.loads(CONFIG.read_text())
    if not cfg.get("freeze_at"):
        sys.exit(f"freeze_at is not set in {CONFIG}; nothing to do")
    t = datetime.fromisoformat(cfg["freeze_at"])
    if t.tzinfo is None:
        sys.exit("freeze_at must carry an offset, e.g. 2026-12-31T23:59:59+08:00")
    return t


def frozen_path(t):
    return FREEZE_DIR / f"uifpi_freeze_{t.astimezone(SGT):%Y%m%d_%H%M}.db"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snapshot():
    t = freeze_at()
    now = datetime.now(SGT)
    if now < t:
        print(f"not yet: now {now.isoformat(timespec='seconds')} < freeze_at {t.isoformat()}")
        return 0
    if MANIFEST.exists():
        print(f"already frozen: {MANIFEST}")
        return 0
    out = frozen_path(t)
    tmp = out.with_suffix(".db.partial")
    src = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    src.backup(dst)  # consistent copy even while the scraper is writing
    src.close()
    cols = {r[1] for r in dst.execute("PRAGMA table_info(prices)")}
    if "inserted_at" not in cols:
        dst.close(); tmp.unlink()
        sys.exit("prices.inserted_at does not exist; the cut cannot be made exactly")
    cutoff = t.astimezone(SGT).isoformat(timespec="seconds")
    max_id = dst.execute("SELECT max(id) FROM prices WHERE inserted_at IS NOT NULL AND inserted_at <= ?",
                         (cutoff,)).fetchone()[0]
    if max_id is None:
        dst.close(); tmp.unlink()
        sys.exit("no row has inserted_at <= freeze_at; refusing to guess the cut")
    after = dst.execute("SELECT count(*), min(inserted_at), max(inserted_at) FROM prices WHERE id > ?",
                        (max_id,)).fetchone()
    # ids are insertion-ordered; a row above the cut stamped before the cutoff would break the rule
    bad = dst.execute("SELECT count(*) FROM prices WHERE id > ? AND inserted_at <= ?", (max_id, cutoff)).fetchone()[0]
    if bad:
        dst.close(); tmp.unlink()
        sys.exit(f"{bad} rows above the cut have inserted_at <= freeze_at; id order broken, stopping")
    dst.execute("DELETE FROM prices WHERE id > ?", (max_id,))
    dst.commit()
    dst.execute("VACUUM")
    counts = dst.execute("SELECT source, count(*), max(collection_date) FROM prices GROUP BY source ORDER BY source").fetchall()
    tables = {n: dst.execute(f'SELECT count(*) FROM "{n}"').fetchone()[0]
              for (n,) in dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    dst.close()
    tmp.rename(out)
    os.chmod(out, 0o444)
    try:
        git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        git = ""
    m = {
        "freeze_at": t.isoformat(),
        "snapshot_taken_at": now.isoformat(timespec="seconds"),
        "minutes_after_freeze_at": round((now - t).total_seconds() / 60, 1),
        "frozen_file": out.name,
        "sha256": sha256(out),
        "prices_max_id": max_id,
        "rows_dropped_after_cut": {"count": after[0], "inserted_at_min": after[1], "inserted_at_max": after[2]},
        "prices_by_source": [{"source": s, "rows": n, "max_collection_date": d} for s, n, d in counts],
        "table_row_counts": tables,
        "note": "Tables other than prices are copied as they stood at snapshot_taken_at (not cut by time).",
        "git_head": git,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
    print(f"frozen: {out} max_id={max_id} sha256={m['sha256'][:12]}… manifest {MANIFEST}")
    return 0


def _manifest():
    if not MANIFEST.exists():
        sys.exit(f"no manifest at {MANIFEST}; run `data_freeze.py snapshot` first")
    return json.loads(MANIFEST.read_text())


def verify():
    m = _manifest()
    f = FREEZE_DIR / m["frozen_file"]
    if sha256(f) != m["sha256"]:
        sys.exit(f"HASH MISMATCH for {f}")
    con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
    mx = con.execute("SELECT max(id) FROM prices").fetchone()[0]
    con.close()
    if mx != m["prices_max_id"]:
        sys.exit(f"max(id) {mx} != manifest {m['prices_max_id']}")
    return f, m


def workcopy():
    f, m = verify()
    w = FREEZE_DIR / f"uifpi_freeze_work_{m['sha256'][:12]}.db"
    if not w.exists():
        shutil.copyfile(f, w)
        os.chmod(w, 0o644)
    con = sqlite3.connect(w)
    mx = con.execute("SELECT max(id) FROM prices").fetchone()[0]
    con.close()
    if mx is None or mx > m["prices_max_id"]:
        sys.exit(f"working copy {w} has rows beyond the freeze (max id {mx}); delete it and rerun")
    return w


def connect_frozen():
    """sqlite3 connection to the verified working copy of the frozen DB."""
    return sqlite3.connect(workcopy())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        sys.exit(snapshot())
    if cmd == "verify":
        f, m = verify()
        print(f"OK {f} sha256 {m['sha256']} max_id {m['prices_max_id']}")
    elif cmd == "workcopy":
        print(workcopy())
    else:
        sys.exit("usage: data_freeze.py snapshot|verify|workcopy")

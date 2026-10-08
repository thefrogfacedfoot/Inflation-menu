#!/usr/bin/env python3
"""Monthly official CPI ingestion for the pre-registered series.

Implements docs/preregistration.md §2 (registered at bd859403) and §9 item 3.
Registered series (all NSA, monthly):

  US  primary CUUR0000SEFV  (BLS food away from home, via FRED)
      headline CPIAUCNS     (FRED, CPI-U all items NSA)
  GB  primary D7EW          (ONS MM23, CPI index 11.1.1 restaurants & cafes)
      headline D7BT         (ONS MM23, CPI index 00 all items)
  SG  primary M213751 row 1.11  (SingStat, F&B serving services, 2024=100)
      headline M213751 row 1    (All items)
  MY  primary cpi_3d group 111  (OpenDOSM, F&B preparation services, 2010=100)
      headline cpi_headline division "overall"
  TH / ID: NOT ingested. They enter the family only if verified before the
      feasibility audit (§2 TH and ID entry rule); no fetcher exists here.

Every stored row carries series ID, source URL, retrieval date and the SHA-256
of the raw response, so any value traces to a fetch. Rows are never
interpolated or carried forward: a month the publisher does not report has no
row.

Rebasing / splicing rule (§2): two vintages of a series are joined only by
chain-linking at an overlap month: scale the older vintage by
(new level / old level at the overlap month) and use the older vintage's
month-on-month changes before it. With no overlap month the join is a series
BREAK (flagged on the first month of the new vintage; no splice, no
interpolation); the analysis then applies D5 (longest contiguous run).
The registered rule does not say WHICH overlap month; this implementation
uses the EARLIEST (documented in chain_link and flagged in the PR).

Usage:
  python3 official_cpi_prereg.py --db uifpi_backfill_test.db [--countries US,GB,SG,MY] [--dry-run]
"""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
import time
from datetime import date

CONTACT_UA = "UICPI-research (erwenchen56@gmail.com)"
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
REF_TOL = 1e-4          # relative tolerance for "pure re-reference" detection

# ── Registry ────────────────────────────────────────────────────────────────
SERIES = [
    dict(country="US", role="primary", series_id="CUUR0000SEFV", kind="fred",
         url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=CUUR0000SEFV"),
    dict(country="US", role="headline", series_id="CPIAUCNS", kind="fred",
         url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"),
    dict(country="GB", role="primary", series_id="D7EW", kind="ons",
         url="https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7ew/mm23/data"),
    dict(country="GB", role="headline", series_id="D7BT", kind="ons",
         url="https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7bt/mm23/data"),
    dict(country="SG", role="primary", series_id="M213751:1.11", kind="singstat",
         row="1.11",
         url="https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751?search=serving"),
    dict(country="SG", role="headline", series_id="M213751:1", kind="singstat",
         row="1",
         url="https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751"),
    dict(country="MY", role="primary", series_id="cpi_3d:111", kind="dosm_csv",
         key_col="group", key="111",
         url="https://storage.dosm.gov.my/cpi/cpi_3d.csv"),
    dict(country="MY", role="headline", series_id="cpi_headline:overall", kind="dosm_api",
         key="overall",
         url="https://api.data.gov.my/data-catalogue/?id=cpi_headline&limit=100000"),
]


# ── Parsers: raw response text -> {"YYYY-MM": float} ───────────────────────
def parse_fred_csv(text):
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        vals = [v for k, v in r.items() if k != "observation_date"]
        if vals and vals[0] not in ("", "."):
            out[r["observation_date"][:7]] = float(vals[0])
    return out


def parse_ons_json(text):
    out = {}
    for m in json.loads(text).get("months", []):
        parts = m["date"].split()               # e.g. "1988 JAN"
        if len(parts) == 2 and m.get("value", "") != "":
            out[f"{parts[0]}-{MONTHS[parts[1].upper()]:02d}"] = float(m["value"])
    return out


def parse_singstat_json(text, row):
    out = {}
    for r in json.loads(text)["Data"]["row"]:
        if r["seriesNo"] == row:
            for c in r["columns"]:
                y, mon = c["key"].split()        # e.g. "2026 Aug"
                if c["value"] not in ("", None, "na"):
                    out[f"{y}-{MONTHS[mon.upper()]:02d}"] = float(c["value"])
    return out


def parse_dosm_csv(text, key_col, key):
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r[key_col] == key and r["index"] != "":
            out[r["date"][:7]] = float(r["index"])
    return out


def parse_dosm_api(text, key):
    out = {}
    for r in json.loads(text):
        if r.get("division") == key and r.get("index") is not None:
            out[r["date"][:7]] = float(r["index"])
    return out


def parse(spec, text):
    k = spec["kind"]
    if k == "fred":
        return parse_fred_csv(text)
    if k == "ons":
        return parse_ons_json(text)
    if k == "singstat":
        return parse_singstat_json(text, spec["row"])
    if k == "dosm_csv":
        return parse_dosm_csv(text, spec["key_col"], spec["key"])
    if k == "dosm_api":
        return parse_dosm_api(text, spec["key"])
    raise ValueError(k)


def fetch(url, retries=4, session=None):
    """Polite GET: contact User-Agent, exponential backoff on 429/5xx."""
    import requests
    s = session or requests
    for i in range(retries):
        r = s.get(url, headers={"User-Agent": CONTACT_UA}, timeout=90)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** (i + 1))
            continue
        r.raise_for_status()
        time.sleep(1.0)                          # <= 1 request/second
        return r.text
    raise RuntimeError(f"GET failed after {retries} tries: {url}")


# ── Rebasing / splicing ─────────────────────────────────────────────────────
def chain_link(old, new):
    """Join an older vintage to a newer one per the registered rule.

    Returns (series, info): series = {ym: value} (months in both inputs use the
    NEW vintage's value); info = {"method", "overlap_month", "factor",
    "break_before"}.
      * overlap exists: link at the EARLIEST overlap month m; months before m
        are old * (new[m] / old[m]); months from m on are the new vintage.
      * no overlap: BREAK. Both vintages are returned unscaled and
        info["break_before"] is the first month of the new vintage. The
        analysis must cut the series there (D5), never splice or interpolate.
    """
    overlap = sorted(set(old) & set(new))
    if not overlap:
        series = dict(old)
        series.update(new)
        return series, {"method": "break", "overlap_month": None, "factor": None,
                        "break_before": min(new)}
    m = overlap[0]
    factor = new[m] / old[m]
    series = {ym: v * factor for ym, v in old.items() if ym < m}
    series.update(new)
    return series, {"method": "chain_link", "overlap_month": m, "factor": factor,
                    "break_before": None}


def classify_vintage_change(old, new):
    """How a freshly fetched vintage relates to the stored one.

    "refresh"        - same levels on every overlapping month (new months added).
    "re_reference"   - new = old * constant on the overlap (pure rebase); the
                       new vintage covers the old span, so just replace.
    "rebase_or_revision" - anything else on the overlap, or the new vintage
                       does not reach back to the old start: apply chain_link.
    "no_overlap"     - no common month: chain_link reports a break.
    """
    overlap = sorted(set(old) & set(new))
    if not overlap:
        return "no_overlap"
    ratios = [new[m] / old[m] for m in overlap]
    r0 = ratios[0]
    if max(abs(r / r0 - 1) for r in ratios) > REF_TOL:
        return "rebase_or_revision"
    if abs(r0 - 1) <= REF_TOL:
        return "refresh"
    return "re_reference" if min(old) >= min(new) else "rebase_or_revision"


# ── Storage ─────────────────────────────────────────────────────────────────
def init_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS official_cpi_prereg (
            country_code  TEXT NOT NULL,
            role          TEXT NOT NULL,      -- primary | headline
            series_id     TEXT NOT NULL,
            year_month    TEXT NOT NULL,
            value         REAL NOT NULL,
            source_url    TEXT NOT NULL,
            retrieved_date TEXT NOT NULL,
            raw_sha256    TEXT NOT NULL,
            splice_method TEXT,               -- NULL | chain_link | break
            break_before  INTEGER DEFAULT 0,  -- 1 on the first month after a break
            PRIMARY KEY (series_id, year_month, retrieved_date)
        )""")
    conn.commit()


def latest_stored(conn, series_id):
    d = conn.execute("SELECT MAX(retrieved_date) FROM official_cpi_prereg WHERE series_id=?",
                     (series_id,)).fetchone()[0]
    if d is None:
        return {}
    return dict(conn.execute("SELECT year_month, value FROM official_cpi_prereg "
                             "WHERE series_id=? AND retrieved_date=?", (series_id, d)))


def store(conn, spec, obs, raw_sha, retrieved):
    """Store one fetched vintage (applying the splicing rule if needed)."""
    old = latest_stored(conn, spec["series_id"])
    kind = classify_vintage_change(old, obs) if old else "first"
    splice, brk = None, None
    series = obs
    if kind in ("rebase_or_revision", "no_overlap"):
        series, info = chain_link(old, obs)
        splice, brk = info["method"], info["break_before"]
    rows = [(spec["country"], spec["role"], spec["series_id"], ym, v, spec["url"],
             retrieved, raw_sha, splice, 1 if ym == brk else 0)
            for ym, v in sorted(series.items())]
    conn.executemany("INSERT OR REPLACE INTO official_cpi_prereg VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return kind, len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True, help="SQLite DB to write (never defaults to uifpi.db)")
    ap.add_argument("--countries", default="US,GB,SG,MY")
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse, write nothing")
    a = ap.parse_args()
    want = set(a.countries.split(","))
    if want - {"US", "GB", "SG", "MY"}:
        sys.exit("TH/ID are not ingested: they are not verified (prereg §2).")
    today = date.today().isoformat()
    conn = None if a.dry_run else sqlite3.connect(a.db)
    if conn:
        init_table(conn)
    for spec in SERIES:
        if spec["country"] not in want:
            continue
        text = fetch(spec["url"])
        obs = parse(spec, text)
        if not obs:
            sys.exit(f"{spec['series_id']}: parsed 0 observations; refusing to store")
        sha = hashlib.sha256(text.encode()).hexdigest()
        msg = f"{spec['country']} {spec['role']:8s} {spec['series_id']:22s} n={len(obs)} {min(obs)}..{max(obs)}"
        if conn:
            kind, n = store(conn, spec, obs, sha, today)
            msg += f"  [{kind}] stored {n} rows"
        print(msg)


if __name__ == "__main__":
    main()

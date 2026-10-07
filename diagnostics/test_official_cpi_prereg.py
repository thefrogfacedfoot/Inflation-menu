#!/usr/bin/env python3
"""Tests for official_cpi_prereg.py on SYNTHETIC fixtures only (no network, no real data).

Run: python3 diagnostics/test_official_cpi_prereg.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import official_cpi_prereg as o  # noqa: E402

# ── parsers: formats mirror the publishers' responses, values are synthetic ──
fred = "observation_date,CUUR0000SEFV\n2020-01-01,100.0\n2020-02-01,101.0\n2020-03-01,.\n"
assert o.parse_fred_csv(fred) == {"2020-01": 100.0, "2020-02": 101.0}, "FRED: '.' must be skipped"

ons = json.dumps({"months": [{"date": "2020 JAN", "value": "100.5"},
                             {"date": "2020 FEB", "value": ""},
                             {"date": "2020 MAR", "value": "102"}]})
assert o.parse_ons_json(ons) == {"2020-01": 100.5, "2020-03": 102.0}, "ONS: empty value skipped"

sg = json.dumps({"Data": {"row": [
    {"seriesNo": "1", "rowText": "All Items", "columns": [{"key": "2020 Jan", "value": "50"}]},
    {"seriesNo": "1.11", "rowText": "F&B", "columns": [
        {"key": "2020 Jan", "value": "60"}, {"key": "2020 Feb", "value": "na"},
        {"key": "2020 Mar", "value": "62"}]}]}})
assert o.parse_singstat_json(sg, "1.11") == {"2020-01": 60.0, "2020-03": 62.0}
assert o.parse_singstat_json(sg, "1") == {"2020-01": 50.0}

dcsv = "date,group,index\n2020-01-01,111,70\n2020-01-01,112,80\n2020-02-01,111,71\n"
assert o.parse_dosm_csv(dcsv, "group", "111") == {"2020-01": 70.0, "2020-02": 71.0}
dapi = json.dumps([{"date": "2020-01-01", "division": "overall", "index": 90},
                   {"date": "2020-01-01", "division": "11", "index": 5}])
assert o.parse_dosm_api(dapi, "overall") == {"2020-01": 90.0}

# ── rebasing / splicing rule ──
old = {"2020-01": 100.0, "2020-02": 110.0, "2020-03": 121.0}
new_overlap = {"2020-03": 50.0, "2020-04": 55.0}          # rebased, overlap at 2020-03
s, info = o.chain_link(old, new_overlap)
assert info["method"] == "chain_link" and info["overlap_month"] == "2020-03"
assert abs(s["2020-02"] - 110.0 * 50.0 / 121.0) < 1e-12 and s["2020-03"] == 50.0
# month-on-month changes before the overlap are preserved exactly
assert abs(s["2020-02"] / s["2020-01"] - 1.1) < 1e-12
# earliest overlap month is used when several exist
s2, info2 = o.chain_link(old, {"2020-02": 11.0, "2020-03": 12.1, "2020-04": 13.0})
assert info2["overlap_month"] == "2020-02" and abs(info2["factor"] - 0.1) < 1e-12
# no overlap -> BREAK: nothing scaled, nothing interpolated, flagged
gap = {"2020-06": 7.0, "2020-07": 7.7}
s3, info3 = o.chain_link(old, gap)
assert info3["method"] == "break" and info3["break_before"] == "2020-06"
assert s3["2020-03"] == 121.0 and "2020-04" not in s3 and "2020-05" not in s3, "no gap filling"

# ── vintage classification ──
assert o.classify_vintage_change(old, dict(old, **{"2020-04": 130.0})) == "refresh"
assert o.classify_vintage_change(old, {k: v * 0.5 for k, v in old.items()}) == "re_reference"
assert o.classify_vintage_change(old, new_overlap) == "rebase_or_revision"
assert o.classify_vintage_change(old, gap) == "no_overlap"

# ── storage: provenance fields, no carry-forward, breaks flagged ──
conn = sqlite3.connect(":memory:")
o.init_table(conn)
spec = dict(country="US", role="primary", series_id="TESTSER", url="https://example.invalid/x")
assert o.store(conn, spec, {"2020-01": 1.0, "2020-03": 3.0}, "abc", "2026-10-01") == ("first", 2)
months = [r[0] for r in conn.execute("SELECT year_month FROM official_cpi_prereg ORDER BY 1")]
assert months == ["2020-01", "2020-03"], "a missing month must have no row"
row = conn.execute("SELECT series_id, source_url, retrieved_date, raw_sha256 FROM official_cpi_prereg").fetchone()
assert row == ("TESTSER", "https://example.invalid/x", "2026-10-01", "abc")
kind, n = o.store(conn, spec, {"2020-07": 9.0}, "def", "2026-10-02")   # disjoint -> break
assert kind == "no_overlap"
b = conn.execute("SELECT year_month, break_before, splice_method FROM official_cpi_prereg "
                 "WHERE retrieved_date='2026-10-02' ORDER BY 1").fetchall()
assert b == [("2020-01", 0, "break"), ("2020-03", 0, "break"), ("2020-07", 1, "break")], b
print("ok: all official_cpi_prereg tests passed")

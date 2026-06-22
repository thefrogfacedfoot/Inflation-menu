"""Diagnostic: compare US Granger WITH vs WITHOUT wayback-doordash data.
Pure read-only — does not write to DB or any persistent artifact.

Run from repo root:  python diagnostics/diag_us_no_doordash.py
Or from diagnostics/: python diag_us_no_doordash.py

This is the reproducer cited in index_builder.EXCLUDED_SOURCES — the
production decision to drop DoorDash from index construction rests on
the F-stat / p-value contrast this script prints.
"""
import os
import sqlite3
import sys

import pandas as pd

# Allow running from diagnostics/ subdir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import index_builder
# Disable the production exclusion for this diagnostic; we want to *measure*
# DoorDash's effect, not silently honor the exclusion.
index_builder.EXCLUDED_SOURCES = ()

from index_builder import load_price_data, build_restaurant_median_index
from granger_analysis import load_cpi, align_series, run_granger, \
    DEFAULT_MIN_OBS, DEFAULT_MAX_LAGS

COUNTRY = "United States"
DOORDASH_SOURCE = "wayback-doordash"


def build_and_test(df: pd.DataFrame, label: str) -> dict:
    rows = build_restaurant_median_index(df, COUNTRY)
    udf = pd.DataFrame(rows).dropna(subset=["uifpi_combined"])
    udf["period"]  = pd.PeriodIndex(udf["year_month"], freq="M")
    udf["country"] = COUNTRY

    cpi_s = load_cpi(COUNTRY)
    uifpi_s, cpi_aligned = align_series(udf, COUNTRY, cpi_s)
    res = run_granger(COUNTRY, uifpi_s, cpi_aligned,
                      min_obs=DEFAULT_MIN_OBS, max_lags=DEFAULT_MAX_LAGS)
    res["_months"]  = len(udf)
    res["_overlap"] = len(uifpi_s)
    res["_label"]   = label
    return res


conn = sqlite3.connect("uifpi.db")
df_all = load_price_data(conn)
conn.close()
df_all = df_all[df_all["country"] == COUNTRY].copy()

df_no_dd = df_all[df_all["source"] != DOORDASH_SOURCE].copy()
print(f"US rows: total {len(df_all):,}  |  no-DoorDash {len(df_no_dd):,}")

res_with = build_and_test(df_all,   "WITH DoorDash")
res_wout = build_and_test(df_no_dd, "WITHOUT DoorDash (production)")

print()
print("=" * 72)
print(f"{'':32s} {'months':>7s} {'overlap':>8s} {'F':>9s} {'p':>9s} sig")
print("-" * 72)
for r in (res_with, res_wout):
    gf = r.get("granger_f_statistic")
    gp = r.get("granger_p_value")
    print(f"  {r['_label']:<30s} {r['_months']:>7d} "
          f"{r['_overlap']:>8d} "
          f"{gf:>9.4f} {gp:>9.4f}  "
          f"{'✓' if r.get('granger_significant') else '✗'}")
print("=" * 72)

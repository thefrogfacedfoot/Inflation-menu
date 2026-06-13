"""
UIFPI — Monthly CPI Pipeline (all 8 countries)
Fetches monthly CPI (all items + food component where available) from
official statistical sources and stores in the monthly_cpi table of
uifpi.db.

Confirmed-working sources (tested 2026-06):
  AU  — OECD PRICES_CPI quarterly (key 41:2:0:0:3:0:0:3) → ~135 monthly
  US  — OECD PRICES_CPI HICP monthly index (key 18:0:1:0:3:0:0:3) → 120 monthly
  IN  — OECD PRICES_CPI national monthly (key 47:0:0:0:3:0:0:3) → 135 monthly
  SG  — World Bank FP.CPI.TOTL annual (10 annual observations)
  MY  — World Bank FP.CPI.TOTL annual
  GB  — World Bank FP.CPI.TOTL annual
  TH  — World Bank FP.CPI.TOTL annual
  ID  — World Bank FP.CPI.TOTL annual

Fallback for all: World Bank annual if primary fails.

Usage:
    python get_monthly_cpi_all.py [--country SG] [--no-fallback] [--reset]
"""

import argparse
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

import requests

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH    = "uifpi.db"
ERROR_FILE = "monthly_cpi_errors.txt"
START_YEAR = 2015

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

CODE_TO_COUNTRY = {
    "SG": "Singapore",    "MY": "Malaysia",       "ID": "Indonesia",
    "TH": "Thailand",     "IN": "India",          "US": "United States",
    "GB": "United Kingdom", "AU": "Australia",
}

# ─────────────────────────────────────────────────────────────────────────────
# OECD PRICES_CPI dataset
# Downloaded once per run and cached in _OECD_CACHE.
# Series key layout: REF_AREA:FREQ:METHODOLOGY:MEASURE:UNIT_MEASURE:EXPENDITURE:ADJUSTMENT:TRANSFORMATION
# Confirmed positions (as at 2026-06):
#   FREQ      M=0, A=1, Q=2
#   METHODOLOGY N=0, HICP=1
#   UNIT_MEASURE PC=0, PA=1, PD=2, IX=3
#   EXPENDITURE  _T=0, CP01=1 (food)
#   ADJUSTMENT  N=0, S=1
#   TRANSFORMATION G1=0, GY=1, GOY=2, _Z=3
# Country positions: AU=41, GBR=36, USA=18, IDN=23, IND=47
# ─────────────────────────────────────────────────────────────────────────────

OECD_URL = ("https://stats.oecd.org/SDMX-JSON/data/PRICES_CPI"
            "/AUS.M.N.CPI.IX._T.N._Z/all"
            "?startTime=2015-01&endTime=2026-12")

# OECD series keys: {country_code: (all_items_key, food_key, frequency)}
# frequency: 'M' = already monthly, 'Q' = quarterly (needs interpolation)
OECD_SERIES: Dict[str, Tuple[str, str, str]] = {
    "AU": ("41:2:0:0:3:0:0:3", "41:2:0:0:3:1:0:3", "Q"),   # ABS quarterly
    "US": ("18:0:1:0:3:0:0:3", "18:0:1:0:3:1:0:3", "M"),   # HICP monthly
    "IN": ("47:0:0:0:3:0:0:3", "47:0:0:0:3:1:0:3", "M"),   # national monthly
}

_OECD_CACHE: Optional[Dict[str, Any]] = None


def _get_oecd_dataset() -> Dict[str, Any]:
    """Download the OECD PRICES_CPI dataset once and cache it in memory."""
    global _OECD_CACHE
    if _OECD_CACHE is not None:
        return _OECD_CACHE
    print("  Downloading OECD PRICES_CPI dataset (one-time, ~77MB) …")
    data = get_json(OECD_URL, timeout=60)
    structs   = data["data"]["structures"][0]
    ds        = data["data"]["dataSets"][0]
    obs_times = [v["id"] for v in
                 structs["dimensions"]["observation"][0]["values"]]
    _OECD_CACHE = {
        "series":    ds["series"],
        "obs_times": obs_times,
    }
    return _OECD_CACHE


def _oecd_series_to_records(series_key: str,
                             frequency: str) -> List[Tuple[str, float]]:
    """
    Extract (period_str, value) pairs from a cached OECD series.
    Quarterly periods returned as "YYYY-Qn"; monthly as "YYYY-MM".
    """
    cache    = _get_oecd_dataset()
    obs      = cache["series"].get(series_key, {}).get("observations", {})
    times    = cache["obs_times"]
    result   = []
    for k, v in obs.items():
        period = times[int(k)]
        val    = v[0] if v else None
        if val is None or period < str(START_YEAR):
            continue
        result.append((period, float(val)))
    result.sort(key=lambda x: x[0])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS monthly_cpi (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code    TEXT NOT NULL,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    year_month      TEXT NOT NULL,
    cpi_value       REAL,
    cpi_food        REAL,
    source          TEXT,
    date_downloaded TEXT,
    UNIQUE(country_code, year_month)
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_SQL)
    conn.commit()
    return conn


def upsert_records(conn: sqlite3.Connection, records: List[Dict[str, Any]],
                   country_code: str, source: str) -> int:
    today    = str(date.today())
    inserted = 0
    for r in records:
        ym = r.get("year_month", "")
        if not ym or len(ym) < 7:
            continue
        year  = int(ym[:4])
        month = int(ym[5:7])
        if year < START_YEAR:
            continue
        try:
            conn.execute("""
                INSERT INTO monthly_cpi
                  (country_code, year, month, year_month,
                   cpi_value, cpi_food, source, date_downloaded)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(country_code, year_month)
                DO UPDATE SET
                  cpi_value=excluded.cpi_value,
                  cpi_food=excluded.cpi_food,
                  source=excluded.source,
                  date_downloaded=excluded.date_downloaded
            """, (
                country_code, year, month, ym,
                r.get("cpi_value"), r.get("cpi_food"),
                source, today,
            ))
            inserted += 1
        except Exception as e:
            log_error(country_code, f"DB insert {ym}: {e}")
    conn.commit()
    return inserted


def query_range(conn: sqlite3.Connection,
                country_code: str) -> Tuple[int, str, str]:
    cur = conn.execute(
        "SELECT COUNT(*), MIN(year_month), MAX(year_month) "
        "FROM monthly_cpi WHERE country_code=?",
        (country_code,),
    )
    row = cur.fetchone()
    return (row[0] or 0, row[1] or "", row[2] or "") if row else (0, "", "")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_json(url: str, params: Optional[Dict] = None,
             timeout: int = 20, max_retries: int = 3) -> Any:
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, headers=HEADERS,
                             timeout=timeout)
            if r.status_code == 429:
                wait = 3 * attempt
                print(f"    Rate limited, waiting {wait}s …")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep(2)
            else:
                raise


def log_error(country_code: str, msg: str):
    with open(ERROR_FILE, "a") as f:
        f.write(f"{date.today()} [{country_code}] {msg}\n")


def ym(year: Any, month: Any) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def parse_float(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Quarterly → monthly interpolation (for AU)
# ─────────────────────────────────────────────────────────────────────────────

def _interpolate_quarterly(quarterly: List[Tuple[str, float]]) -> List[Dict]:
    """
    Linear interpolation from quarterly to monthly.
    Each quarter (value Q_i) → 3 months, linearly interpolated toward Q_{i+1}.
    """
    q_to_months = {"Q1": (1, 2, 3), "Q2": (4, 5, 6),
                   "Q3": (7, 8, 9), "Q4": (10, 11, 12)}
    records = []
    for i, (qperiod, q_val) in enumerate(quarterly):
        # Parse "2015-Q1" or "2015Q1"
        qp = qperiod.strip().replace(" ", "")
        if "-Q" in qp:
            yr_str, q_str = qp.split("-")
        elif "Q" in qp:
            idx = qp.index("Q")
            yr_str, q_str = qp[:idx], qp[idx:]
        else:
            continue
        try:
            yr = int(yr_str)
        except ValueError:
            continue
        months = q_to_months.get(q_str.upper())
        if not months:
            continue
        next_val = quarterly[i + 1][1] if i + 1 < len(quarterly) else q_val
        step     = (next_val - q_val) / 3.0
        for j, m in enumerate(months):
            records.append({
                "year_month": ym(yr, m),
                "cpi_value":  round(q_val + step * j, 4),
                "cpi_food":   None,
            })
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Country fetch functions
# ─────────────────────────────────────────────────────────────────────────────

def fetch_australia() -> Tuple[List[Dict], str]:
    """ABS CPI via OECD PRICES_CPI quarterly (key 41:2:0:0:3:0:0:3)."""
    print("  Primary: OECD PRICES_CPI quarterly (ABS source) …")
    all_key, food_key, freq = OECD_SERIES["AU"]
    quarterly = _oecd_series_to_records(all_key, freq)
    if not quarterly:
        raise ValueError("No AU quarterly data in OECD dataset")
    records = _interpolate_quarterly(quarterly)

    # Food quarterly (interpolated too)
    food_q = _oecd_series_to_records(food_key, freq)
    if food_q:
        food_monthly = {r["year_month"]: r["cpi_value"]
                        for r in _interpolate_quarterly(food_q)}
        for r in records:
            r["cpi_food"] = food_monthly.get(r["year_month"])

    return records, "OECD PRICES_CPI/ABS CPI quarterly (interpolated)"


def fetch_united_states() -> Tuple[List[Dict], str]:
    """US HICP monthly index via OECD PRICES_CPI (key 18:0:1:0:3:0:0:3)."""
    print("  Primary: OECD PRICES_CPI HICP monthly (US) …")
    all_key, food_key, freq = OECD_SERIES["US"]
    all_data  = _oecd_series_to_records(all_key, freq)
    if not all_data:
        raise ValueError("No US monthly data in OECD dataset")
    food_data = dict(_oecd_series_to_records(food_key, freq))
    records   = [{"year_month": p, "cpi_value": v,
                  "cpi_food": food_data.get(p)} for p, v in all_data]
    return records, "OECD PRICES_CPI HICP monthly index"


def fetch_united_kingdom() -> Tuple[List[Dict], str]:
    """UK: no monthly source reachable from this network; raise to trigger fallback."""
    print("  Primary: ONS CPIH01 — not reachable from this network.")
    raise ValueError("ONS API not reachable (network timeout); using fallback")


def fetch_india() -> Tuple[List[Dict], str]:
    """India national monthly CPI via OECD PRICES_CPI (key 47:0:0:0:3:0:0:3)."""
    print("  Primary: OECD PRICES_CPI national monthly (India) …")
    all_key, food_key, freq = OECD_SERIES["IN"]
    all_data  = _oecd_series_to_records(all_key, freq)
    if not all_data:
        raise ValueError("No IN monthly data in OECD dataset")
    food_data = dict(_oecd_series_to_records(food_key, freq))
    records   = [{"year_month": p, "cpi_value": v,
                  "cpi_food": food_data.get(p)} for p, v in all_data]
    return records, "OECD PRICES_CPI national monthly index"


def fetch_singapore() -> Tuple[List[Dict], str]:
    """SingStat API (table ID lookup in progress). Raise to use fallback."""
    print("  Primary: SingStat — table IDs returning 404 (API restructured).")
    raise ValueError("SingStat API 404 on known table IDs; using fallback")


def fetch_malaysia() -> Tuple[List[Dict], str]:
    print("  Primary: DOSM open.dosm.gov.my — API endpoint returns 404.")
    raise ValueError("DOSM API 404; using fallback")


def fetch_indonesia() -> Tuple[List[Dict], str]:
    print("  Primary: BPS requires API key; skipping to fallback.")
    raise ValueError("BPS requires registration key; using fallback")


def fetch_thailand() -> Tuple[List[Dict], str]:
    print("  Primary: BOT IAPI — DNS not reachable from this network.")
    raise ValueError("BOT IAPI DNS failure; using fallback")


# ─────────────────────────────────────────────────────────────────────────────
# Fallbacks
# ─────────────────────────────────────────────────────────────────────────────

def fetch_worldbank_annual(country_code: str) -> Tuple[List[Dict], str]:
    """World Bank FP.CPI.TOTL annual — confirmed working."""
    print(f"  Fallback: World Bank FP.CPI.TOTL (annual) …")
    url = (
        f"https://api.worldbank.org/v2/country/{country_code}"
        f"/indicator/FP.CPI.TOTL"
        f"?format=json&date={START_YEAR}:2025&per_page=100"
    )
    data = get_json(url, timeout=20)
    if len(data) < 2 or not data[1]:
        raise ValueError(f"No World Bank data for {country_code}")
    records = []
    for rec in data[1]:
        if rec.get("value") is None:
            continue
        year = rec.get("date", "")
        v    = parse_float(rec["value"])
        if year and v:
            records.append({
                "year_month": ym(year, 1),
                "cpi_value":  v,
                "cpi_food":   None,
            })
    if not records:
        raise ValueError(f"All null from World Bank for {country_code}")
    return records, f"World Bank FP.CPI.TOTL (annual)"


# ─────────────────────────────────────────────────────────────────────────────
# Country dispatch
# ─────────────────────────────────────────────────────────────────────────────

COUNTRY_PRIMARY = {
    "SG": fetch_singapore,
    "MY": fetch_malaysia,
    "ID": fetch_indonesia,
    "TH": fetch_thailand,
    "IN": fetch_india,
    "US": fetch_united_states,
    "GB": fetch_united_kingdom,
    "AU": fetch_australia,
}


def collect_country(code: str, conn: sqlite3.Connection,
                    no_fallback: bool = False) -> Tuple[int, str]:
    """Try primary → World Bank annual. Returns (n_stored, source_used)."""
    primary_fn = COUNTRY_PRIMARY[code]
    records: List[Dict] = []
    source:  str        = "none"

    try:
        records, source = primary_fn()
        print(f"  Got {len(records)} records from primary.")
    except Exception as e:
        msg = f"Primary failed: {e}"
        print(f"  {msg}")
        log_error(code, msg)
        if no_fallback:
            return 0, "no_fallback"
        try:
            time.sleep(1)
            records, source = fetch_worldbank_annual(code)
            print(f"  Got {len(records)} records from World Bank.")
        except Exception as e2:
            msg2 = f"World Bank also failed: {e2}"
            print(f"  {msg2}")
            log_error(code, msg2)
            return 0, "all_sources_failed"

    n = upsert_records(conn, records, code, source)
    return n, source


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(conn: sqlite3.Connection, results: List[Dict[str, Any]]):
    print(f"\n{'='*72}")
    print(f"{'MONTHLY CPI PIPELINE SUMMARY':^72}")
    print(f"{'='*72}")
    print(f"{'Country':<22} {'CC':4} {'Obs':>6} {'From':>9} {'To':>9}  Freq  Source")
    print(f"{'─'*72}")
    for r in results:
        code = r["code"]
        country = CODE_TO_COUNTRY.get(code, code)
        n, mn, mx = query_range(conn, code)
        src = r["source"][:25] if r["source"] else "—"
        # Detect frequency from date range
        if n >= 12 and mn and mx:
            years = int(mx[:4]) - int(mn[:4]) + 1
            freq  = "monthly" if n >= years * 10 else "annual"
        else:
            freq = "annual" if n <= 11 else "monthly"
        status = f"✓ {n:>5}" if n > 0 else "✗     0"
        print(f"{country:<22} {code:4} {status:>6}  {mn or '—':>9} {mx or '—':>9}  {freq:<7}  {src}")
    print(f"{'─'*72}")
    total = sum(r["n"] for r in results)
    print(f"{'Total':26} {total:>6}")
    print(f"{'='*72}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="UIFPI monthly CPI collector")
    parser.add_argument("--country", default="all",
                        help="Comma-separated codes: SG,US,GB,AU,MY,TH,IN,ID or 'all'")
    parser.add_argument("--no-fallback", action="store_true",
                        help="Only use primary source, no fallbacks")
    parser.add_argument("--reset", action="store_true",
                        help="DELETE existing monthly_cpi rows before running")
    args = parser.parse_args()

    if args.country == "all":
        # OECD countries first (they share one 77MB download), then WB countries
        target_codes = ["AU", "US", "IN", "GB", "SG", "MY", "TH", "ID"]
    else:
        target_codes = [c.strip().upper() for c in args.country.split(",")]

    conn = get_db()

    if args.reset:
        phs = ",".join("?" * len(target_codes))
        conn.execute(f"DELETE FROM monthly_cpi WHERE country_code IN ({phs})",
                     target_codes)
        conn.commit()
        print(f"Reset monthly_cpi for: {target_codes}")

    results = []
    for code in target_codes:
        if code not in COUNTRY_PRIMARY:
            print(f"\nUnknown code: {code}")
            continue
        country = CODE_TO_COUNTRY.get(code, code)
        print(f"\n{'='*60}")
        print(f"{country} ({code})")
        print(f"{'='*60}")
        n, source = collect_country(code, conn, no_fallback=args.no_fallback)
        results.append({"code": code, "n": n, "source": source})
        cnt, mn, mx = query_range(conn, code)
        if cnt > 0:
            print(f"  {country}: {cnt} observations ({mn} to {mx}) from {source}")
        else:
            print(f"  {country}: 0 observations (all sources failed)")
        time.sleep(1)

    conn.close()
    conn2 = get_db()
    print_summary(conn2, results)
    conn2.close()

    if Path(ERROR_FILE).exists():
        with open(ERROR_FILE) as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        if lines:
            print(f"\n⚠  {len(lines)} errors logged to {ERROR_FILE}")


if __name__ == "__main__":
    main()

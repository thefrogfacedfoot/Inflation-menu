"""
UIFPI — Monthly CPI Downloader
Fetches monthly (or best-available) CPI data for all 8 target countries
from official statistical sources. Falls back to IMF/World Bank annual
data where monthly isn't freely available.

Run order: this script is independent; run any time.
Output: cpi_data/monthly_cpi_[code].json
"""
import os
import json
import time
import requests

os.makedirs('cpi_data', exist_ok=True)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
}

DELAY = 2  # seconds between requests


# ── Helpers ──────────────────────────────────────────────────────────────────

def save(code, country, source, unit, records):
    """Write records to cpi_data/monthly_cpi_[code].json."""
    records.sort(key=lambda r: (r['year'], r.get('month', '01')))
    path = f'cpi_data/monthly_cpi_{code.lower()}.json'
    with open(path, 'w') as f:
        json.dump({
            'country': country,
            'country_code': code,
            'source': source,
            'unit': unit,
            'data': records,
        }, f, indent=2)
    print(f"  Saved {len(records)} records → {path}")


def get(url, params=None, timeout=20):
    """GET with standard headers and basic error propagation."""
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


# ── Singapore — SingStat Table Builder API ───────────────────────────────────
# Table M212882: Consumer Price Index (CPI), All Items, 2019=100

def fetch_singapore():
    print("\n[Singapore] SingStat API …")
    url = 'https://tablebuilder.singstat.gov.sg/api/table/tabledata/M212882'
    try:
        data = get(url).json()
        rows = data.get('Data', {}).get('row', [])
        if not rows:
            raise ValueError('Empty response')
        records = []
        for col in rows[0].get('columns', []):
            key = col.get('key', '')          # e.g. "2020 Jan"
            value = col.get('value', '')
            if not value or value.strip() == 'na':
                continue
            parts = key.strip().split()
            if len(parts) != 2:
                continue
            year, mon_abbr = parts
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12',
            }
            month = month_map.get(mon_abbr)
            if not month:
                continue
            try:
                records.append({'year': year, 'month': month,
                                 'period': f'{year}-{month}', 'cpi': float(value)})
            except ValueError:
                pass
        if not records:
            raise ValueError('No usable data parsed')
        save('SG', 'Singapore', 'SingStat', 'CPI All Items (2019=100)', records)
    except Exception as e:
        print(f"  ✗ SingStat failed: {e}")
        fetch_imf_annual('SGP', 'SG', 'Singapore')


# ── United States — FRED (no key needed for CSV endpoint) ───────────────────
# Series CPIAUCSL: CPI for All Urban Consumers: All Items, 1982–84=100

def fetch_united_states():
    print("\n[United States] FRED CSV …")
    url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL'
    try:
        r = get(url)
        records = []
        for line in r.text.splitlines():
            if line.startswith('DATE'):
                continue
            parts = line.split(',')
            if len(parts) != 2:
                continue
            date_str, val = parts
            if val.strip() == '.':
                continue
            try:
                year, month, _ = date_str.split('-')
                records.append({
                    'year': year, 'month': month,
                    'period': f'{year}-{month}', 'cpi': float(val),
                })
            except (ValueError, AttributeError):
                pass
        if not records:
            raise ValueError('No records parsed')
        save('US', 'United States', 'FRED CPIAUCSL', 'CPI All Items (1982-84=100)', records)
    except Exception as e:
        print(f"  ✗ FRED failed: {e}")
        fetch_imf_annual('USA', 'US', 'United States')


# ── United Kingdom — ONS Time Series API ─────────────────────────────────────
# Dataset CPIH01, Series L55O: CPIH All Items, index 2015=100

def fetch_united_kingdom():
    print("\n[United Kingdom] ONS API …")
    url = 'https://api.ons.gov.uk/v1/datasets/cpih01/timeseries/l55o/data'
    try:
        data = get(url).json()
        records = []
        for entry in data.get('months', []):
            # date format: "2020 JAN"
            raw = entry.get('date', '')
            value = entry.get('value', '')
            if not value:
                continue
            parts = raw.strip().split()
            if len(parts) != 2:
                continue
            year, mon_abbr = parts
            month_map = {
                'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12',
            }
            month = month_map.get(mon_abbr.upper())
            if not month:
                continue
            try:
                records.append({'year': year, 'month': month,
                                 'period': f'{year}-{month}', 'cpi': float(value)})
            except ValueError:
                pass
        if not records:
            raise ValueError('No usable months data')
        save('GB', 'United Kingdom', 'ONS CPIH01/L55O', 'CPIH All Items (2015=100)', records)
    except Exception as e:
        print(f"  ✗ ONS failed: {e}")
        fetch_imf_annual('GBR', 'GB', 'United Kingdom')


# ── IMF DataMapper — annual % change (fallback for remaining countries) ──────
# Indicator PCPIPCH: Inflation, Consumer Prices (annual %)
# IMF country codes differ from ISO-2

IMF_CODES = {
    'MY':  'MYS',
    'ID':  'IDN',
    'TH':  'THA',
    'IN':  'IND',
    'AU':  'AUS',
    'US':  'USA',
    'GB':  'GBR',
    'SG':  'SGP',
}

COUNTRY_NAMES = {
    'MY': 'Malaysia', 'ID': 'Indonesia', 'TH': 'Thailand',
    'IN': 'India', 'AU': 'Australia', 'US': 'United States',
    'GB': 'United Kingdom', 'SG': 'Singapore',
}


def fetch_imf_annual(imf_code, iso2, country_name):
    """
    Fallback: fetch annual CPI % change from IMF DataMapper.
    Stores as year-only records (month='01' placeholder).
    """
    print(f"  ↳ Falling back to IMF DataMapper ({imf_code}) …")
    url = f'https://www.imf.org/external/datamapper/api/v1/PCPIPCH/{imf_code}'
    try:
        data = get(url).json()
        values = data.get('values', {}).get('PCPIPCH', {}).get(imf_code, {})
        if not values:
            raise ValueError('No values returned')
        records = []
        for year, val in values.items():
            if val is None:
                continue
            records.append({
                'year': year, 'month': '01',
                'period': f'{year}-01', 'cpi': round(float(val), 4),
            })
        if not records:
            raise ValueError('All values null')
        save(iso2, country_name, 'IMF PCPIPCH (annual %)',
             'Annual CPI % change', records)
    except Exception as e:
        print(f"  ✗ IMF also failed: {e}")
        fetch_worldbank_annual(iso2, country_name)


def fetch_worldbank_annual(iso2, country_name):
    """Last resort: World Bank annual CPI (2010=100)."""
    print(f"  ↳ Falling back to World Bank ({iso2}) …")
    url = (
        f'https://api.worldbank.org/v2/country/{iso2}'
        f'/indicator/FP.CPI.TOTL?format=json&date=2015:2025&per_page=100'
    )
    try:
        data = get(url).json()
        if len(data) < 2 or not data[1]:
            raise ValueError('No data')
        records = []
        for rec in data[1]:
            if rec['value'] is None:
                continue
            records.append({
                'year': rec['date'], 'month': '01',
                'period': f"{rec['date']}-01", 'cpi': rec['value'],
            })
        if not records:
            raise ValueError('All values null')
        save(iso2, country_name, 'World Bank FP.CPI.TOTL',
             'CPI Index (2010=100)', records)
    except Exception as e:
        print(f"  ✗ World Bank also failed for {iso2}: {e}")


# ── Per-country fetchers that try primary → IMF fallback ─────────────────────

def fetch_malaysia():
    print("\n[Malaysia] IMF DataMapper + World Bank fallback …")
    # DOSM Malaysia API requires registration; use IMF as primary here
    fetch_imf_annual('MYS', 'MY', 'Malaysia')


def fetch_indonesia():
    print("\n[Indonesia] IMF DataMapper …")
    fetch_imf_annual('IDN', 'ID', 'Indonesia')


def fetch_thailand():
    print("\n[Thailand] IMF DataMapper …")
    fetch_imf_annual('THA', 'TH', 'Thailand')


def fetch_india():
    print("\n[India] IMF DataMapper …")
    fetch_imf_annual('IND', 'IN', 'India')


def fetch_australia():
    print("\n[Australia] IMF DataMapper …")
    # ABS API requires registration; use IMF as primary
    fetch_imf_annual('AUS', 'AU', 'Australia')


# ── Main ─────────────────────────────────────────────────────────────────────

FETCHERS = [
    fetch_singapore,
    fetch_malaysia,
    fetch_indonesia,
    fetch_thailand,
    fetch_india,
    fetch_united_states,
    fetch_united_kingdom,
    fetch_australia,
]


if __name__ == '__main__':
    print("=" * 60)
    print("UIFPI — Monthly CPI Downloader")
    print("=" * 60)

    for fn in FETCHERS:
        fn()
        time.sleep(DELAY)

    print("\n" + "=" * 60)
    print("Done. Check cpi_data/ for monthly_cpi_*.json files.")
    print("These complement the annual cpi_*.json from get_cpi.py.")
    print("=" * 60)

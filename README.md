# UIFPI — Unified Informal-Formal Price Index

A food-price index built from restaurant menu data across 8 countries,
designed as a leading indicator of official CPI. Research project for
ISEF/SSEF competition, extending the MIT Billion Prices Project to the
restaurant and informal food sector.

**Countries covered:** Singapore · Malaysia · Indonesia · Thailand ·
India · United States · United Kingdom · Australia

---

## Architecture

```
uifpi/
├── migrate_db.py          one-time: adds price_usd column
├── live_scraper.py        daily: scrapes delivery apps + direct sites
├── historical_scraper.py  one-time: Wayback Machine TripAdvisor archive
├── get_monthly_cpi.py     one-time (refresh monthly): official CPI data
├── get_cpi.py             one-time: World Bank annual CPI (legacy)
├── check_db.py            anytime: database status report
├── uifpi.db               SQLite database
├── cpi_data/
│   ├── cpi_*.json         annual CPI from World Bank
│   └── monthly_cpi_*.json monthly CPI from official sources
└── historical_progress.json  resume state for historical_scraper
```

---

## Setup

```bash
# Install Python dependencies
pip install playwright requests beautifulsoup4

# Install Playwright browser (Chromium)
playwright install chromium

# Create / migrate the database
python3 migrate_db.py
```

---

## Scripts — run in this order

### 1. `migrate_db.py` — one-time setup

Adds the `price_usd` column to an existing database.
Safe to re-run; no-ops if the column already exists.

```bash
python3 migrate_db.py
```

---

### 2. `live_scraper.py` — daily collection

Scrapes menus from food delivery platforms and direct restaurant
websites across all 8 countries. Stores prices in original currency
and USD equivalent (fetched live from exchangerate-api.com).

**Platform coverage:**

| Country       | Platform          | Currency |
|---------------|-------------------|----------|
| Singapore     | Foodpanda, GrabFood | SGD    |
| Malaysia      | Foodpanda, GrabFood | MYR    |
| Indonesia     | Foodpanda         | IDR      |
| Thailand      | Foodpanda         | THB      |
| India         | Swiggy            | INR      |
| United States | Direct websites   | USD      |
| United Kingdom| Direct websites   | GBP      |
| Australia     | Direct websites   | AUD      |

**Must be run on a residential IP.** Foodpanda and GrabFood block
cloud/datacenter IPs at the network edge. GitHub Codespace IPs will
not work. Run from a home or university network.

```bash
python3 live_scraper.py
```

The script is resumable: already-scraped restaurants are skipped.
It retries failed targets up to 3 times before giving up.

**URL verification for Indonesia / Thailand:**
The Foodpanda chain IDs for ID and TH are estimates following
Foodpanda's slug pattern. Before a production run, visit
`foodpanda.id` or `foodpanda.co.th`, find each chain, and update
the URL in the `TARGETS` list with the correct chain ID.

**Swiggy (India):**
Swiggy restaurant IDs are embedded in the URL
(`swiggy.com/{city}/{name}-{id}`). The provided IDs are from
mid-2025 Mumbai/Delhi listings. If a page redirects, search the
restaurant on swiggy.com and replace the URL.

---

### 3. `historical_scraper.py` — historical baseline

Uses the Wayback Machine CDX API to find archived TripAdvisor
restaurant pages (2018–present), fetches them, extracts whatever
price signals exist, and inserts them with the actual archived date
as `collection_date`. This gives the price index a historical tail
to compare against official CPI.

```bash
# All 8 countries (slow — expect several hours with polite rate limiting)
python3 historical_scraper.py

# Single country for testing
python3 historical_scraper.py Singapore

# Multiple specific countries
python3 historical_scraper.py "United States" "United Kingdom"
```

Progress is saved to `historical_progress.json` after every page
fetch. Interrupt and restart freely — the script skips already-done
URLs. Set `SNAPSHOTS_PER_COUNTRY` at the top of the file to collect
more data (default 50 per country).

---

### 4. `get_monthly_cpi.py` — official monthly CPI

Downloads monthly CPI from each country's official statistical
source. Re-run monthly to keep the benchmark data current.

| Country | Primary source | Falls back to |
|---------|---------------|---------------|
| Singapore | SingStat Table M212882 | IMF DataMapper |
| United States | FRED CPIAUCSL (CSV) | IMF DataMapper |
| United Kingdom | ONS CPIH01/L55O | IMF DataMapper |
| Malaysia | IMF DataMapper | World Bank |
| Indonesia | IMF DataMapper | World Bank |
| Thailand | IMF DataMapper | World Bank |
| India | IMF DataMapper | World Bank |
| Australia | IMF DataMapper | World Bank |

```bash
python3 get_monthly_cpi.py
# Output: cpi_data/monthly_cpi_sg.json, monthly_cpi_us.json, etc.
```

---

### 5. `check_db.py` — database diagnostics

Shows collection status, data quality flags, and sample rows.
Run any time to verify coverage.

```bash
python3 check_db.py
```

Output includes:
- Total rows and breakdown by country / sector / source
- Date range of collection
- Countries below the 10-item minimum (flagged with ⚠)
- Null-price items
- 5 random sample rows per country

---

## Database schema

```sql
CREATE TABLE prices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_name  TEXT,
    item_name        TEXT,
    price            REAL,       -- original currency
    currency         TEXT,       -- ISO 4217: SGD, MYR, IDR, THB, INR, USD, GBP, AUD
    price_usd        REAL,       -- converted at collection-day rate
    country          TEXT,
    sector           TEXT,       -- 'formal' | 'informal'
    source           TEXT,       -- 'foodpanda' | 'grabfood' | 'swiggy' | 'direct' | 'wayback'
    collection_date  TEXT,       -- ISO 8601: YYYY-MM-DD
    url              TEXT
);
```

`price_usd` is null for rows collected before `migrate_db.py` was run.
Backfill with the exchange rate on the original `collection_date` if
needed for time-series analysis.

---

## Sector classification

| Label | Meaning |
|-------|---------|
| `formal` | Multinational or large regional chain (McDonald's, Din Tai Fung, etc.) |
| `informal` | Hawker-origin, family-run, or local institution (Song Fa, Hawker Chan, Jay Fai, etc.) |

The formal/informal split is a key research variable — the hypothesis
is that informal sector prices lead formal sector price adjustments,
which in turn leads official CPI.

---

## Recommended run schedule

```
Daily  :  python3 live_scraper.py
Monthly:  python3 get_monthly_cpi.py
One-off:  python3 historical_scraper.py   (run once; resume with same command)
Anytime:  python3 check_db.py
```

---

## Known limitations

- **Bot detection:** Foodpanda and GrabFood block non-residential IPs.
- **Swiggy:** Location-sensitive; some restaurant pages may require
  a delivery address to be set. If items are not loading, try with
  `headless=False` in the Playwright launch call to debug visually.
- **Direct sites (US/UK/AU):** Success depends on whether the chain
  uses JSON-LD structured data. McDonald's and Chipotle work well;
  others may return 0 items if the menu is behind a React SPA that
  doesn't embed structured data.
- **Historical scraper:** TripAdvisor did not embed detailed menu
  prices in most archived pages — most data comes from price-range
  regex, which is coarser than live scraping. Treat historical data
  as directional, not item-level.
- **IDR prices:** Indonesian Rupiah uses dots as thousand separators
  (25.000 = 25,000 IDR). The parser handles this but verify a few
  rows in `check_db.py` after the first Indonesia run.

---

## Citation

If you use this dataset or code in published research, please cite:

> UIFPI: Unified Informal-Formal Price Index.
> Erwen Chen, 2025. https://github.com/thefrogfacedfoot/Inflation-menu

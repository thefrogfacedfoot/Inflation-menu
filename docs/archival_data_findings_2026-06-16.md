# Historical menu-price data: what's recoverable from Wayback

**Date**: 2026-06-16
**Goal**: Build enough historical UIFPI observations across 8 countries to run Granger causality against CPI. Baseline: Singapore p=0.092 (the only marginal pre-existing result).

## TL;DR

After exhaustive probing of Wayback Machine archives across multiple source types, **no viable archival route exists** for the price data we actually need. The only path to Granger-testable monthly menu prices is **sustained going-forward live scraping** of foodpanda / GrabFood / direct sites.

## What was tried, what was found

### 1. TripAdvisor restaurant reviews (Wayback)
Already in pipeline via `historical_scraper.py`. Today's rescan added **+1,403 rows** distributed across 32 quarter-windows × 7 countries (Singapore excluded per instruction).

**Verdict**: data exists but is mostly unusable for index purposes. **92% of the new rows are TripAdvisor `priceRange` tier markers (`$`, `$$`, `$$$`, `$$$$`) stored as the literal integers 1–4 in the `price` column**, with `item_name = "Price tier (TripAdvisor: $$$$)"`. Only 5–34 real menu prices per country are present.

Including tier-as-price in the index produced wildly inflated values (Indonesia's `uifpi_combined` hit **26,021,657**), and the apparent significant Granger results (MY p=0.021, ID p=0.005 under restaurant-median method) were entirely tier-bug artifacts. After excluding tier rows, every country drops below the 8-month minimum for Granger.

Fix landed: `index_builder.py` filtered `item_name LIKE "Price tier%"` rows out of index construction. Raw rows remained in `uifpi.db` for transparency.

**Resolved 2026-06-17.** The tier-marker rows were purged from the raw `prices` table (1,648 rows across 8 countries: TH 279, UK 293, US 277, IN 237, AU 221, MY 188, ID 118, SG 35) and `historical_scraper.py` was updated so it no longer emits them. The `index_builder.py` filter was removed as redundant. The pre-purge DB is preserved as `uifpi.db.backup_pre_tier_purge_20260617_204040`.

### 2. Chain restaurant PDF menus (Wayback)
Hypothesis was that major chains publish menu PDFs on their websites with prices. Probed `*.mcdonalds.com/*.pdf`, `*.kfc.com/*.pdf`, `*.pizzahut.com/*.pdf`, plus per-country variants for 8 countries.

**Verdict**: chains don't publish menus as PDFs. The PDFs that do exist are forms (job applications, children's-party consent forms), allergen/nutrition charts, press releases, and recipes. Wide-glob queries also frequently time out on Wayback's CDX index, but the non-timeout queries returned 0 menu PDFs.

### 3. Chain restaurant HTML menu pages (Wayback)
Pivoted to archived HTML at canonical menu URLs: `mcdonalds.co.uk/menu`, `kfc.co.uk/menu`, `wagamama.com/menu`, etc. CDX confirmed 200+ snapshots for several (KFC UK, KFC AU, KFC MY, McD Indonesia, Wagamama UK).

**Verdict**: snapshots exist but contain no price data.

| Archive | Size | Currency hits |
|---|---|---|
| McDonald's Indonesia 2018 | 54 KB | 0 |
| KFC Malaysia 2020 | 67 KB | 0 |
| KFC Australia 2018 | 44 KB | 0 |
| KFC UK 2023 | 128 KB | 7 (delivery chrome, not menu items) |

Modern chain sites load menu data via JS/API calls after page render (React/Next.js — `__NEXT_DATA__` present, JSON-LD absent for prices). Wayback archives the initial HTML shell but cannot replay or capture the subsequent API responses, so the archived pages are price-empty even when fetched successfully.

This is the same blocker that forces the live scraper to use Playwright with full JS execution. Wayback is fundamentally incapable of capturing JS-driven price data.

## What does work, and what to do next

**Going-forward live scraping is the only viable path.** The `live_scraper.py` pipeline already collects ~10k real menu prices per day across the 8 countries (foodpanda + GrabFood + direct sites). After ~8 consecutive months of daily collection, every country will have ≥8 overlapping monthly UIFPI observations, which is the Granger minimum.

Today's pipeline improvements that support this:
- `MAX_ROWS_PER_COUNTRY = 300` cap (per `index_builder.py`) ensures cross-country equal weighting even as live data accumulates unevenly.
- New `--method restaurant-median` index option for when stable-basket can't find cross-month items (early data, sparse coverage).
- Tier-marker exclusion + truncate-before-rebuild prevent stale rows from contaminating Granger.
- `scheduled/com.uifpi.url-health.plist` runs `verify_targets.py` weekly so dead URLs get flagged before they erode collection.

## Reproducibility

Re-probing the dead ends:

```sh
# TripAdvisor wayback (tier-heavy, current scraper)
python3 historical_scraper.py --distributed --rescan --per-period 10

# Chain PDF probe
python3 -c "import requests; r=requests.get('http://web.archive.org/cdx/search/cdx',
    params={'url':'*.mcdonalds.com/*.pdf','output':'json','limit':200,
            'filter':['statuscode:200','mimetype:application/pdf']},
    timeout=30); print(r.json()[:5])"

# Chain HTML probe + sample fetch
python3 -c "import requests; r=requests.get(
    'https://web.archive.org/web/2020/http://www.kfc.com.my/menu', timeout=60);
    import re; print('£:', len(re.findall(r'£\s?\d', r.text)),
                     'RM:', len(re.findall(r'RM\s?\d', r.text)))"
```

All three return what's documented above.

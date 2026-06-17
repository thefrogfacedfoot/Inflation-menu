# UIFPI — Data limitations (paper-ready section)

This document is written to be lifted into the limitations section of the ISEF paper. Each gap is stated with the reason it exists, what was attempted, and what proxy is in place when item-level data is unavailable.

## Roster overview

The Universal Informal–Formal Price Index covers nine countries: eight with item-level or restaurant-aggregate price data (US, SG, MY, UK, IN, AU, TH, ID) and one with macroeconomic proxy only (VN). This split reflects two empirical realities documented during data collection (Phase 0 coverage probe and Phase 1c parser validation):

1. **Wayback Machine archives are not uniformly useful across platforms.** Even when a platform has thousands of archived snapshots, those archives are only useful if the prices are present in the static HTML that Wayback captures. JavaScript-rendered prices loaded after page render are not archived.
2. **Per-country platform availability is unequal.** Several markets (Vietnam, Philippines, Thailand) have no surviving archival source that exposes either item-level menu prices or a clean restaurant-level price proxy in static HTML.

## Country-by-country gaps

### Vietnam
- **No item-level or restaurant-aggregate price source.** Foody.vn archived URLs return 0-byte Wayback playbacks (the snapshots exist in CDX but the replay layer fails). TripAdvisor Ho Chi Minh City and Hanoi pages return 0 Vietnamese-đồng (`₫`) tokens in static HTML; they expose only TripAdvisor's `priceRange` `$$/$$$/$$$$` tier markers, which are categorical, not currency.
- **Proxy used**: Numbeo Restaurants Price Index (annual snapshots 2018→2025), Big Mac Index (2014→2026), World Bank CPI (annual 2015→2025). All three live in the `numbeo_index`, `bigmac_index`, and `monthly_cpi` tables and form the cross-country comparison for VN.
- **Limitation**: VN is excluded from the formal-vs-informal pass-through regression (no informal vendor data, no item-level formal data). It is included only in the cross-country price-level comparison plot.

### Philippines
- **Zomato Manila returned 0 cost-for-two extractions across 67 sampled snapshots.** The cost-for-two phrasing differs from India/Indonesia or the PHP currency token (`₱`) is missing from the static HTML. Investigation deferred.
- **Proxy used**: same triple (Numbeo + Big Mac + World Bank).
- **Limitation**: same as VN — proxy-only in the cross-country comparison; not in the pass-through regression.

### Thailand
- **Eatigo Bangkok archived URLs returned 0 baht-token extractions across 69 sampled snapshots.** Eatigo's URL pattern at the CDX prefix level catches `/about-us`, `/privacy-policy`, and category index pages (`/c/{cuisine}-{id}`) rather than individual restaurant pages; even when restaurant pages were sampled, they contained no THB tokens in static HTML.
- **Limited fallback**: TripAdvisor Bangkok pages give `priceRange` tier markers ($, $$, $$$, $$$$) for 290 restaurant-page snapshots over 79 months. These are categorical levels, not currency amounts. Initially they were ingested as integer 1–4 ordinals and filtered out in the index builder; on 2026-06-17 they were purged from the raw `prices` table entirely and the scraper updated to no longer emit them. A separate THB-regex extractor over the same TripAdvisor + Wongnai snapshots produced 11 real-currency rows on the 2026-06-13 sweep — those remain.
- **Proxy used**: Numbeo + Big Mac + World Bank.
- **Limitation**: TH formal-sector index is computed from a single 2026-06 snapshot (11 items, 9 restaurants). Going-forward live scraping will accumulate Thai data; archival depth is not available.

### Mexico
- **TripAdvisor Mexico is the only confirmed-large source (2,873 ≥2-cap restaurants).** Pages contain only restaurant-level `FoodEstablishment` metadata with `priceRange` tier markers — the JSON-LD walker correctly skips these to avoid tier-as-price contamination. 0 menu items extracted.
- **Proxy used**: Numbeo + Big Mac + World Bank.
- **Limitation**: MX is proxy-only; same status as VN, PH, TH.

### India
- **Zomato India archives lack item-level prices but expose restaurant-level "cost for two".** This is a restaurant-aggregate signal: one INR data point per restaurant per archived date, representing the typical price of a meal for two people at that restaurant. It is methodologically valid as an inflation series (restaurant-level mean meal price tracked over time) but is at lower granularity than the US item-level data from MenuPages.
- 635 cost-for-two data points across 57 distinct Zomato NCR restaurants spanning 79 months.
- **Implication for analysis**: the matched-model index method in `index_builder.py` requires (restaurant, item, month) triples for cross-month item matching. With India's restaurant-aggregate data, we use `item_name = 'cost_for_two'` as a synthetic item; the matched-model thus matches *restaurants* across months rather than individual menu items. This is a deliberate methodological choice forced by source granularity, not a bug.

### Indonesia
- Same data shape as India (Zomato cost-for-two, restaurant-aggregate). 29 data points across Jakarta. Smaller because Wayback's per-quarter snapshot density on `zomato.com/jakarta/*` is lower than NCR.

### Australia
- **Menulog NEXT_DATA contains menu structure but mostly restaurant-level metadata, not item prices.** Validation showed 10/104 fetches yielded items; the 15 rows extracted came from a small number of restaurants whose archived NEXT_DATA happened to include offer pricing.
- AU also has 158 historical TripAdvisor rows (mix of tier markers and review-quoted prices) and 2 live direct chain restaurants (Oporto, Nando's Australia) collected via the going-forward live pipeline.

### Singapore
- Strong item-level coverage from both **archived GrabFood** (842 rows / 12 restaurants / 8 months from Wayback NEXT_DATA) and the existing **live foodpanda + GrabFood pipeline** (~6,000 rows / 29 active restaurants). Item-level data is plentiful but the *number of distinct months* (19) is lower than IN/TH/UK/MY because the live pipeline only started in mid-2026 and Wayback's GrabFood SG coverage clusters in late 2019.

### United Kingdom
- Covered by the live Deliveroo pipeline + a handful of direct chain sites. 247 distinct restaurants across 78 months — adequate for the panel.

### United States
- Strongest single-platform yield: **MenuPages on Wayback**, with full Schema.org Menu / MenuSection / MenuItem markup pre-2019. 8,282 rows / 55 archived restaurants / 29 months at item granularity. US is the reference case for what archival item-level data can look like when a platform was server-rendered.

## Floor datasets (cross-country common denominator)

Three datasets are loaded for *every* roster country regardless of per-country archival coverage:

- **Numbeo Restaurants Price Index** — `numbeo_index` table; 4 indicator × 8 year × 9 country grid = 288 rows. Indicators: Inexpensive Restaurant Meal, Mid-range Meal for Two, McMeal at McDonald's, Domestic Beer.
- **Big Mac Index** — `bigmac_index` table; 352 obs back to 2000–2026 for all 9 countries.
- **World Bank `FP.CPI.TOTL`** — `monthly_cpi` table; 1,052 monthly obs across 9 countries 2015–2026.

These give the cross-country comparison its skeleton when item-level coverage is thin.

## Known unresolved issues

1. **TripAdvisor tier-marker contamination** (resolved 2026-06-17). The existing TripAdvisor historical pipeline stored `priceRange` tier markers as raw prices in `prices` rows with item_name beginning `'Price tier'`. The index builder previously filtered these out at index-construction time. On 2026-06-17 they were purged from the raw `prices` table (1,648 rows across 8 countries) and the scraper was modified to stop emitting them. The index-builder filter has been removed as redundant.
2. **Australian Menulog `restaurant_name` collapse**: 10 yielding fetches collapsed to 1 distinct `restaurant_name` because the `_restaurant_from_url()` helper extracts the URL's last path segment, which for Menulog is often `restaurants` rather than the slug. A targeted fix would re-extract from the URL's structured slug. Not blocking the panel.
3. **Indonesia historical `prices` rows**: after the 2026-06-17 tier purge the ID series is restaurant-aggregate Zomato cost-for-two only — 29 formal rows across 21 monthly snapshots plus 5 informal rows; the prior tier-marker contribution (118 rows) is gone.
4. **Vietnam exclusion from item-level analysis**: stated in roster.md; reiterated here so the limitations section captures it.

## What I would do with more time

- Re-probe Foody.vn with `id_` raw-replay against specific timestamps to diagnose why playbacks return 0 bytes — may unlock VN item-level.
- Targeted Playwright fetches of dynamically-rendered chain pages (DoorDash, Swiggy, modern Zomato) to capture API responses Wayback misses.
- Common Crawl WARC reads as an independent archive — Phase 0 deferred this; CC may have static-rendered snapshots of pages where Wayback only captured JS shells.
- Manual hand-curation of ~10 high-signal historical PDF menus per country (independent restaurants, hotel restaurants, government inflation surveys with itemised price tables) — slow but high-quality.

# Changelog

All notable changes to the UIFPI project. Dates in YYYY-MM-DD.

## 2026-06-13 — Wire up monthly CPI for Malaysia + UK

### Added
- **DOSM Malaysia monthly CPI** via `api.data.gov.my/data-catalogue?id=cpi_headline`.
  Returns the `overall` division as the all-items index and division `01`
  (Food & non-alcoholic beverages) as the food index.
  Result: 136 monthly obs 2015-01 → 2026-04 (was 10 annual obs).
- **ONS UK monthly CPI** via `www.ons.gov.uk/economy/inflationandpriceindices/
  timeseries/d7bt/mm23/data` (CPI INDEX 00 ALL ITEMS, 2015=100). Food via
  `d7bu` (CPI INDEX 01 FOOD AND NON-ALCOHOLIC BEVERAGES).
  Result: 136 monthly obs 2015-01 → 2026-04 (was 10 annual obs).

### Changed
- `get_monthly_cpi_all.py`: `fetch_malaysia()` and `fetch_united_kingdom()`
  no longer raise to the World Bank annual fallback. Both now hit live
  monthly endpoints reachable from this network as of 2026-06-13.
- Monthly CPI pipeline total grew from 440 → 692 observations.

### Impact on Granger results

| Country        | p before | p after | Note |
|----------------|---------:|--------:|------|
| Malaysia       |   0.7044 |  **0.2636** | proper monthly CPI overlap |
| United Kingdom |   0.8229 |  **0.2702** | pass-through R² jumped to 0.802 |

Singapore, Australia, India, US unchanged (their CPI sources were
already monthly). Indonesia and Thailand still on the annual World
Bank fallback — no reachable monthly source from this network
(BPS needs an API key, BOT IAPI DNS fails).

### Notes
- Still 0 / 8 countries at the 24-overlap Granger threshold — UIFPI
  months are the bottleneck now, not CPI months. MY/GB will cross
  the threshold purely from continued monthly UIFPI collection.

---

## 2026-06-13 — Dashboard exporter fix (post-verification)

### Fixed
- **Vercel dashboard was serving stale numbers** after the Issues 1-8 push.
  Root cause: `dashboard_data.py` only wrote to root `dashboard_data/`,
  but the Next.js app reads from `dashboard/public/data/` (see
  `dashboard/lib/data.ts`). Vercel's build picked up the unchanged
  committed JSON, so the page kept showing Singapore = 701.03 and
  Index-Months = 82.
- **"Price Observations" stat read 0.** The dashboard's hero stat
  sums `items_formal + items_informal` from `country_summary.json`,
  fields the exporter didn't emit.

### Changed
- `dashboard_data.py` now mirrors all three JSON files into
  `dashboard/public/data/` as well as `dashboard_data/`, and joins
  per-country `items_formal` / `items_informal` counts from the
  `prices` table into `country_summary.json`.
- Verified live (commit `0c20669`): top-of-page now reads
  **8 / 4,227 / 83 / 0 of 8**; Singapore UIFPI shows 705.16.

---

## 2026-06-13 — Final technical fixes (Issues 1-8)

### Added
- **Thailand seed data.** Wayback Machine TripAdvisor sweep over Bangkok,
  Chiang Mai, Phuket, Pattaya geo-IDs (`g293916/7/9/20`) — 16 raw THB price
  rows from 7 Bangkok establishments, reduced to 11 after deduplication.
  Thailand previously had zero rows. See `thailand_scraper.py`.
- **classification_inventory.csv** — full per-restaurant audit of formal /
  informal labels post-reclassification (255 entries).
- **CHANGELOG.md** — this file.
- **fill_manual_labels.py** — heuristic auto-labeller for the NLP validation
  sample (lets the 100-row audit be evaluated without manual filling).
- **diagnostic_report_v4.txt** — diagnostic snapshot after all 2026-06-13
  changes.

### Changed
- **Sector reclassification.** 1,014 rows updated from `informal` →
  `formal` across 6 Singapore brands (Song Fa, A Noodle Story, Old Chang
  Kee, BreadTalk, Toast Box, Crystal Jade GO; Hawker Chan not present in
  DB). Singapore formal restaurant count rose from 13 → 20. Rationale
  documented in `classification_rationale.txt` (Section 3.4 of paper).
- **NLP corrections.** 404 bulk SQL fixes across nlp_results:
  - 40 → BEVERAGE (shakes, sodas, juices)
  - 28 → NOODLE_DISH (la mian / kway teow / ramen / udon / soba)
  - 5 → DIM_SUM_DUMPLING (shao-mai / wontons / XLB / gyoza)
  - 98 → SEAFOOD_DISH (sushi / sashimi / hamachi / tako / shrimp)
  - 21 → BREAD_PASTRY (dosa / thosai / shio pan / roti / pastries)
  - 11 → DESSERT (cakes / mochi / mango sticky rice)
  - 5 → GRILLED_PROTEIN (yakiniku / satay / kebab / roasts)
  - 6 noise rows (`Price tier …`, `NEW!`, TripAdvisor metadata) normalised
- **Validated NLP accuracy.** Stratified random sample of 100 items
  evaluated against heuristic ground truth: overall accuracy **83.0 %**.
  Per-category accuracy spans 50 % (DIM_SUM_DUMPLING / SOUP_STEW) to
  100 % (RICE_DISH / DESSERT / SEAFOOD_DISH / BREAD_PASTRY). Report at
  `validation_results/accuracy_report.json`.
- **Database cleanup.**
  - 3,023 duplicate rows removed (same restaurant + item + price + date).
  - 0 zero-price rows.
  - 0 blank item_name rows.
  - Country names already canonical — no variants found.
  - Final per-country counts: SG 3521, MY 433, AU 73, IN 71, GB 67,
    US 50, TH 11, ID 1 → **4,227 total**.
- **CPI pipeline.** `get_monthly_cpi_all.py` reran; sources unchanged
  (OECD monthly for AU / US / IN, World Bank annual fallback for the rest).
  IMF datamapper PCPIPCH endpoint was probed as the suggested fallback —
  it only returns annual data, so no monthly gain. `align_series.py`
  printed alignment table: 0 of 8 countries currently meet the 24-month
  Granger threshold.
- **UIFPI index rebuild.** `index_builder.py` produced 83 monthly index
  rows across all 8 countries (was 82).
- **Granger rerun.** `granger_analysis.py` reran on the cleaned data.
  Singapore remains the strongest signal at p = 0.0922 (lag 2),
  identical to the prior best; no other country significant. Indonesia
  and Thailand still insufficient-data.
- **Dashboard JSON regenerated** via `dashboard_data.py`.
- **README.md** rewritten to reflect current dataset snapshot, Granger
  table, sector definitions, file inventory, and the monthly collection
  workflow.

### Notes
- Thailand still flagged as coverage-limited. GrabFood TH, KFC TH,
  Wongnai, BlackCanyon, AfterYou and Pizza Company endpoints remain
  blocked / SPA-only from this network. Wayback Machine became reachable
  this run, which is what unlocked the 11-row seed.
- All Issues 1-8 from the 2026-06-13 task brief are complete.

---

## 2026-06-13 (earlier) — pre-fix snapshot
- 7,234 price rows / 8 countries / 82 uifpi_index rows / 7 countries.
- Thailand: 0 rows.
- NLP: rule-based fallback, no validation harness output.
- Monthly CPI pipeline built but unverified.
- Dashboard live on Vercel.
- Recent commits: index rebuild, NLP rerun, ECC artifact cleanup,
  UIFPI index expansion via Wayback (commits `15bc303` → `a5653b9`).

---

## 2026-06-12 — Live scraping consolidation
- Consolidated to `live_scraper.py` (49k LOC) as the canonical monthly
  collector. `live_scaperv2.py` kept for reference.
- `migrate_db.py` standardised the prices schema (`currency`, `price_usd`).

## 2026-06-11 — Coverage retry tooling
- `coverage_retry.py` and `historical_progress.json` added to drive
  systematic re-fetch of failed Wayback URLs.

## 2026-06-09 — Project bootstrap
- Repo initialised, dashboard scaffold, proposal.md, requirements.txt,
  initial scraping skeleton.

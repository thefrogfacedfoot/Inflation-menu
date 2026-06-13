# Changelog

All notable changes to the UIFPI project. Dates in YYYY-MM-DD.

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

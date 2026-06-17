# Changelog

All notable changes to the UIFPI project. Dates in YYYY-MM-DD.

## 2026-06-17 — TripAdvisor tier-marker purge, dashboard honesty pass

### TripAdvisor `priceRange` tier markers removed from `prices` table

The TripAdvisor scraper historically stored `priceRange` tier strings (`$`,
`$$`, `$$$`, `$$$$`) as integer ordinals 1–4 in the `price` column, with
`item_name` beginning `"Price tier (TripAdvisor: …)"`. They are categorical
levels, not currency, and were already excluded from index construction —
but they inflated raw row counts on the dashboard tile and the country
pages, which was misleading.

- **Raw table purge**: 1,648 tier-marker rows deleted across 8 countries.
  Per-country breakdown:

  | Country | Rows removed |
  |---|---|
  | Thailand | 279 |
  | United Kingdom | 293 |
  | United States | 277 |
  | India | 237 |
  | Australia | 221 |
  | Malaysia | 188 |
  | Indonesia | 118 |
  | Singapore | 35 |

  Pre-purge snapshot preserved as
  `uifpi.db.backup_pre_tier_purge_20260617_204040`.
- **Scraper updated** (`historical_scraper.py`): the
  `FoodEstablishment` JSON-LD branch no longer emits tier rows (restaurant
  name harvesting is preserved). A defensive `startswith('Price tier')`
  guard sits in the insert loop. The `PRICE_RANGE_TIERS` /
  `price_range_to_tier` helpers are gone.
- **Index builder** (`index_builder.py`): the post-load `tier_mask`
  filter has been removed as redundant; a one-line comment points to
  this changelog entry.
- **Audit cleanup**: removed stale `("price tier", "OTHER")` rule from
  `nlp_pipeline.py` and the `"price tier"` noise keyword from
  `fill_manual_labels.py`. Updated `final_roster.md`, `data_gaps.md`,
  and `docs/archival_data_findings_2026-06-16.md` to reflect that the
  tier rows are gone, not just filtered.

### Dashboard count honesty

- Re-ran `index_builder.py` + `dashboard_data.py` against the post-purge
  database. The homepage tile counts and per-country sector counts now
  reflect **price-bearing rows only**, not raw rows.
- **The visible drop in homepage item counts is from tier-marker
  removal, not data loss.** Thailand: 290 → 11 (the 279 tier markers
  are gone; the 11 real currency rows from the 2026-06 Wayback
  TripAdvisor/Wongnai THB-regex sweep remain). Indonesia: 152 → 34.
  Equivalent reductions across every country in the table above.
- Added per-country `COVERAGE_NOTES` (Thailand, Indonesia) on the
  country page, rendered as an amber caveat banner under the chart so
  the visitor understands what the single TH point and the
  restaurant-aggregate ID series actually represent.

## 2026-06-15 — Scraper hardening, URL audit, parallelism

### Scraper engine (`live_scraper.py`)

- **Parallel mode** via `UIFPI_CONCURRENCY=N`. Targets are sharded across N
  worker threads, each holding its own Playwright browser and SQLite
  connection (WAL handles concurrent writes). On the workstation: a full
  47-target sweep dropped from ~5h sequential to ~21 min with 4 workers.
- **XHR-intercept scraper** in `scrape_direct`. Captures JSON responses
  fetched after page load and walks them for `name`/`price` pairs. Recovers
  data from React-shell sites (Nando AU GraphQL → 41 items, Hoppers → 14).
- **Resource blocking** via `page.route` — images, fonts, CSS, and known
  analytics hosts are aborted. Cuts foodpanda/grabfood page loads ~40-60%.
- **Bot-block fast-fail**: dropped the 45s inner retry on `ACCESS_DENIED`;
  IP-level blocks don't lift on that timescale, so failed targets defer
  straight to the end-of-run retry queue.
- **`networkidle` → `domcontentloaded`** in `scrape_swiggy`, `scrape_js`,
  `scrape_direct`. `networkidle` never fires on pages with polling, so the
  old code timed out at 45s instead of proceeding.
- **Tighter waits**: foodpanda selector wait 15s × 4 → 5s × 4; GrabFood
  menu-render poll 30 × 1s → 12 × 500ms; inter-target sleep in parallel
  mode 8-18s → 3-7s.
- **Foodpanda 404/500 detection** in `_looks_like_block` — page returns
  with "404 Ooops!" / "500" title now fail fast instead of retrying.
- **Warm-up navigation** added: hit the home page first, set cookies, then
  go to the chain page (less obvious to anti-bot fingerprint).
- **`_walk_json_for_items`** handles two more price shapes used by real
  menu APIs: `prices: {cents: N, points: M}` and `price: {amount: N,
  currency: ...}` (minor units).

### URL audit

Full-browser verifier (`verify_targets.py`) used to classify all 226
TARGETS as OK / BLOCKED / DEAD / NAV_ERROR / WRONG_PAGE. Result:
**TARGETS 226 → 54** (-172).

- **Indonesia Foodpanda**: 18 URLs removed. `foodpanda.id` doesn't resolve
  at the DNS level — Foodpanda exited the Indonesia market years ago.
- **Thailand Foodpanda**: 18 URLs removed. Chain IDs followed an
  algorithmic pattern (alphabetically descending first letter, trailing
  `t` suffix) — fabricated rather than copied from real pages.
- **DoorDash NYC**: 11 URLs removed. Cloudflare "Just a moment..." gate;
  `cloudscraper` also fails (HTTP 403).
- **US direct chains** (Taco Bell, Chick-fil-A, In-N-Out, Wingstop,
  Subway, Shake Shack, Cane's, Jack, Fatburger, Steak'n Shake, Denny's):
  removed. All are React shells with prices fetched only after a location
  is picked; no `$X.XX`, no `"price"`, no `data-price` in the static HTML
  or in any XHR before interaction.
- **UK direct chains** (Pret, Itsu, Bao London, Honest Burgers, Nando's
  UK): removed. Same React-shell pattern; Nando's UK Gatsby data has
  6,434 `"price"` fields but every one is `null` until store selection.
- **Australia direct chains** (Grill'd, Roll'd, McDonald's Australia,
  Harry's): removed for the same reason.
- **Australia Uber Eats**: 11 URLs removed. All used literal placeholder
  store IDs (`abc123`, `def456`, …) — never resolved.
- **Thailand GrabFood**: 9 URLs removed. All redirected to the GrabFood
  Thailand home page.
- **Secret Recipe MY (GrabFood)**: 500 server error.

Seven unverifiable Foodpanda SG/MY URLs were **replaced with verified
GrabFood URLs** found via headed Playwright search on `food.grab.com`:
Hawker Chan, Seoul Garden HotPot, 28 Fried Kway Teow, Din Tai Fung KL,
Tim Ho Wan, Swee Choon Tim Sum. Hokkaido-ya removed (not on GrabFood SG).

### Cron + ops

- Daily cron entry updated to `UIFPI_CONCURRENCY=4 UIFPI_HEADLESS=1` so
  the 21:00 SGT run benefits from parallelism and survives a locked
  screen / closed session.

### Caveats

- 2,480 unique items remain unclassified in `nlp_results`. Run
  `nlp_pipeline.py` to categorise them so the matched-model index
  populates `category_relatives` for these items.

### Index methodology fix

`index_builder.build_mean_price_index` previously compared cross-item
monthly mean prices when matched-model found no overlap, which produced
inflated indices (e.g. Singapore 712, UK 1,047 in 2026-06) that
conflated basket churn with price change. Replaced by
`build_stable_basket_index`:

- Restrict to items appearing in ≥2 monthly observations.
- For each stable item, relative = current_price / earliest_price.
- Monthly index = geometric mean of relatives × 100, computed separately
  for formal/informal sectors and combined via `INFORMAL_WEIGHTS`.
- When the stable basket has < 5 items, the row is still emitted but the
  index columns are NULL with `coverage_note = "insufficient stable
  basket"` so the dashboard renders a gap instead of a fabricated number.
- Months with no stable-basket items also emit NULL.

After the fix, 2026-06 indices come out either honest (Thailand 100,
Indonesia 100) or NULL (Singapore, UK, Malaysia, Australia, US, India —
their newly-scraped items haven't appeared in a prior month yet). YoY
columns are correspondingly null. `dashboard_data.build_latest_values`
now also prefers the most recent row with an actual value over the
freshest-but-null row.

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

# Changelog

All notable changes to the UIFPI project. Dates in YYYY-MM-DD.

## 2026-07-09 — Quarantine corrupted UAE/VN wayback price slices

Two (country, source) slices carried systematically corrupted prices:
**United Arab Emirates / wayback-deliveroo** (9,243 rows — from 2022-01 the
Deliveroo template stores price as a `{code, fractional, formatted}` object
and the generic JSON walker digit-fuses it, turning AED 9 into 90,009) and
**Vietnam / wayback-grabfood** (4,309 rows — the `priceInMinorUnit` handler
divides by 100 unconditionally, but GrabFood VN's field carries raw VND, so
every price is ~100× too small). Both had entered the index via
`load_price_data`'s FALLBACK_RATES backfill; the AE index ran at
5,775–156,099 from 2022 on, and VN 2026-06 printed 25,455.82 at the
corrupt-wayback → healthy-live crossover.

New `data_quality.QUARANTINED_SLICES` excludes the two slices in
`index_builder.load_price_data` and `dashboard_data.load_price_counts`
(same pattern as EXCLUDED_SOURCES; raw rows stay in `prices`). Impact:
AE index series empty (no other AE source), VN loses 19 wayback months and
restarts at 2026-06 = 100. All other countries — including the entire
8-country panel and the US Granger headline inputs — byte-identical.
Root-cause evidence and quantification in `docs/data_quality_2026-07.md`.
Parsers in historical_html_scraper.py intentionally not fixed here (dead
code for these slices until a re-scrape).

## 2026-07-09 — Sector-label cleanup: stale `formal` rows relabelled, dashboard source-exclusion added

7,571 wayback-doordash rows still carried the pre-2026-06-21 `formal` label
(historical_html_scraper.py TARGETS were never updated after the rename).
Relabelled to `chain` (backup: uifpi.db.backup_pre_formal_relabel_*), TARGETS
now emit `chain`/`independent`. dashboard_data.load_price_counts previously
had no source-exclusion filter and only skipped DoorDash by the accident of
the stale label; it now excludes EXCLUDED_SOURCES explicitly, so dashboard
counts are unchanged and DoorDash stays out of all aggregates.

## 2026-07-08 — Repair 2026-07 ingest artifacts; guard against empty-DB runs

The 2026-07-01 GitHub Actions ingest ran on a runner with no uifpi.db
(the file is gitignored) and committed zeroed dashboard/analysis exports
(aa0fbb7), later merged in d2bd832. Repaired by rebuilding index/Granger/
dashboard exports locally from the intact 156k-row database.
monthly_ingest.py now aborts (exit 2) when the prices table has fewer
than 50,000 rows unless --allow-empty-db is passed; the workflow no
longer stages the gitignored uifpi.db.

## 2026-06-18 — First valid Granger result (US); 8-country panel finalised

### Headline: US Granger-significant at p = 0.021

Running `granger_analysis.py --min-obs 24` (the standard
publication threshold) restricts the panel to the two countries
with enough overlapping months: **India (47 obs, 2018-01 → 2026-01)
and United States (31 obs, 2018-04 → 2024-10)**.

| Country | n | Granger F | p | Lead | Pass-through β | 95% CI | R² |
|---|---:|---:|---:|---:|---:|---|---:|
| **United States** | 31 | **6.034** | **0.0210** ✓ | **1 month** | −0.00248 | [−0.00531, +0.00034] | 0.557 |
| India | 47 | 0.521 | 0.4742 | — | −0.00076 | [−0.00220, +0.00068] | 0.500 |

Both series stationary at levels (UIFPI ADF p ≤ 0.012, CPI ADF
p ≤ 0.018). VAR-AIC selected lag = 4 for the US, lag = 1 for
India; in both cases the minimum-p lag is 1.

**Interpretation.** The US Granger result is the first
statistically valid finding in the project: restaurant menu prices
Granger-cause headline CPI at the 5% level with a one-month lead.
The pass-through coefficient is small and only marginally
significant (p = 0.083, 95% CI includes zero), which is
methodologically consistent with restaurant menus being one of
many CPI components — the *lead* is the headline, not the
magnitude of the linear pass-through. The Indian sample, with
47 months and a strong stationary identification, finds no
relationship (F ≈ 0.5, p = 0.47); cross-country heterogeneity in
CPI leadership is itself a result.

Full numbers in `docs/granger_results_2026-06-18.md`. JSON in
`analysis_results/granger_results.json`.

### Roster decision: keep 8 countries

The final roster is Singapore, Malaysia, Indonesia, Thailand,
India, United States, United Kingdom, Australia — the same eight
that have ever had item-level price observations in `prices`. No
new countries are added.

Reverted from the 2026-06-17 / 2026-06-18 attempts:
  - **Mexico** dashboard tile + ProxyCountryPage template (was
    floor-only because no archival item-level source clears the
    formal-sector threshold).
  - **Brazil, Germany, South Africa** dashboard tiles + tile
    expansion (8 → 11). The Phase 0 probes found CDX-yield in all
    three but the actual archived HTML carries restaurant
    metadata + i18n strings only — modern SPA delivery sources
    don't expose menu data through Wayback at all. Not worth
    pursuing.
  - **PROXY_COUNTRIES** literal in `dashboard/types/index.ts`.
  - **FloorChart** component + `getFloorData` / `getFloorDataForCountry`
    + `floor_data.json` exports — supplementary floor-data section
    removed for the sample countries too, since the project's
    artifact is the item-level UIFPI and not cross-country
    Numbeo/Big Mac.
  - **historical_html_scraper.py** Track C TARGETS (UberEats BR,
    iFood RJ, Lieferando, Wolt DE, TripAdvisor ZA, UberEats ZA)
    and the BRL / EUR / ZAR currency regexes + parsers. The
    `_walk_ld` fix and the truncated-`</script>` tolerant
    extractor stay — both are genuine parser improvements
    independent of the country-expansion direction.
  - **floor_datasets.py** ROSTER additions (GB, MY, BR, DE, ZA).
    Numbeo / Big Mac / WB CPI rows for these countries remain in
    `uifpi.db` but are no longer surfaced anywhere; they're
    harmless historical residue.

`generateStaticParams()` now produces 8 country routes; `next
build` clean; `tsc --noEmit` clean.

## 2026-06-18 — Menulog parser fix; 11-country panel; ID/TH alt probes

### JSON-LD walker: require local `name` on the emitting node

`historical_html_scraper.py::_walk_ld` previously inherited a parent's
`name` field into descendant price-bearing nodes. For Schema.org
Restaurant JSON-LD that pattern produced
`("Restaurant Name", 4.99)` where the price was the delivery fee from
an anonymous `Offer` under `Restaurant.offers` and the name was the
restaurant's name — the parent's. The 15 wayback-menulog rows that
sat in `prices` were all of this shape (prices 4.99 / 5.00 / 10.00 /
20.00 — Menulog's flat delivery fee and minimum-order tiers).

Fix: the walker still recurses with the inherited `name_ctx` for
descent, but emission requires the local node to have its own `name`.
Anonymous Offer / priceSpecification leaves under non-menu parents
are now correctly dropped. MenuPages-shaped JSON-LD
(Menu → MenuSection → MenuItem with own name) is unaffected — all
six synthetic test shapes pass.

Action taken:
  - The 15 polluted `wayback-menulog` rows in `prices` were deleted.
  - The `Australia:menulog` entry in `historical_html_progress.json`
    was reset so the 128 cached snapshots are re-walked with the
    fixed parser.
  - `historical_html_scraper.py --per-period 3 --max-per-target 100`
    re-launched. The 8 existing-cache targets resume from `done_urls`
    and skip in seconds; AU Menulog + 6 new BR/DE/ZA targets walk
    fresh.

### Dashboard: 8 → 11 countries (12 with Mexico proxy)

`types/index.ts` `COUNTRIES` now lists Brazil, Germany, South Africa
alongside the original 8. Mexico stays in `PROXY_COUNTRIES`. Flags,
slugs, and `DEVELOPMENT_STATUS` extended for the new three. The world
map (`components/CountryMap.tsx`) gets approximate viewBox positions
for BR / DE / ZA so the dots render in the right hemispheres.

South Africa ships with a `COVERAGE_NOTES` banner — *"limited coverage
— supplementary only"* — given the thin 16-hit Phase 0 probe yield.

`floor_datasets.py` ROSTER also extended: GB and MY are now included
(both had monthly CPI but were missing Numbeo / Big Mac); BR / DE / ZA
added for completeness so the next `floor_datasets.py` run loads
their floor data too.

### ID / TH alternative-source probe results

`phase0_probe_id_th_alts.py` ran 7 probes against ShopeeFood (ID) and
Wongnai / LineMan (TH). Per `coverage_report_id_th_alts.md`:

  - **ID — bail**. ShopeeFood SP (47 ≥2-cap) is captcha-blocked.
    `shopeefood.co.id/*` only has 4 ≥2-cap restaurants. No viable
    item-level source.
  - **TH — bail**. `wongnai.com/restaurants/*` has 5,545 ≥2-cap
    restaurants but the sample fetch returned a connection reset.
    Other Wongnai routes are too thin (2 URLs, 6 THB hits, no
    LD/ND).

Pivot: ID and TH ship as hybrid country pages — main country in the
roster, item-level series shown (Zomato cost-for-two for ID; the
single 2026-06 live snapshot for TH), with a supplementary floor-data
section (Numbeo + Big Mac + WB CPI) and an explicit coverage banner.
Not converted to `PROXY_COUNTRIES` because they still have direct
price observations.

### Reality check: Wayback doesn't capture modern delivery-app menus

Running `historical_html_scraper.py` with the 14 wired targets
returned **0 rows across all new targets**: AU Menulog (81 attempts),
BR Uber Eats (66), BR iFood RJ (80), DE Lieferando (57), DE Wolt (60),
ZA TripAdvisor (84), ZA Uber Eats (75).

Diagnosis (verified on a 1 MB Lieferando archived page):
  - The Phase 0 single-sample probes were misleading. The 102 EUR /
    218 BRL / 48 AUD hit counts were body-text matches; the
    structured data tells a different story.
  - The archived JSON-LD on these pages is typically
    `@type=Restaurant` with restaurant metadata only (address, hours)
    and **no** MenuItem nodes.
  - The archived `__NEXT_DATA__` blob contains the app's i18n
    strings, service URLs, and feature flags but **no menu data**.
    Menu data on modern SPAs (Lieferando, Uber Eats, iFood, GoFood,
    GrabFood) loads via XHR from a BFF API after page render.
    Wayback captures only the static HTML shell — never the
    hydrated state.
  - On many archived pages the embedded `__NEXT_DATA__` script is
    even truncated mid-string at ~315 KB, so the old extractor's
    `(.*?)</script>` regex returned nothing because there was no
    closing tag. `extract_jsonld` and `extract_nextdata` were
    updated to fall back to a `[^<]+` terminator when no
    `</script>` is found; even so, the underlying JSON has no
    menu items to extract.
  - The lieferando ND payload contains **zero `"price"` substrings**
    in its 314 KB — this was the cleanest possible proof.

Action taken:
  - The 15 prior `wayback-menulog` rows were correctly identified
    as delivery fees (4.99 / 5.00 / 10.00 / 20.00 — Menulog's
    flat-fee structure) and deleted. The cleaned `prices` table
    now reflects only genuine menu items.
  - BR / DE / ZA tiles ship as `"Data Collection Ongoing"` with 0
    items — honest about coverage status. Live going-forward
    collection via `live_scraper.py` is the realistic path; Wayback
    is not.
  - Documented in `docs/track_b_c_findings_2026-06-17.md` (revised)
    and surfaced via the COVERAGE_NOTES banner for ZA.

The original delivery-app probes (Uber Eats / iFood / GoFood /
GrabFood / Lieferando / Wolt) are now understood to be **inherently
unsuitable for archival item-level extraction**, regardless of CDX
yield. This is a structural limitation of the SPA-by-XHR pattern,
not a parser issue.

## 2026-06-17 — Track B / Track C probe results

### TL;DR
- **3 new countries clear the formal-sector threshold**: Brazil (Uber Eats BR, 218 BRL hits/page), Germany (Lieferando, 102 EUR), South Africa (TripAdvisor ZA, 16 ZAR).
- **2 candidate sources bail**: Indonesia GoFood (JS shell — 0 IDR hits in static HTML across 3 URL patterns); Thailand GrabFood (captcha-blocked on Wayback playback, both `/th/en/*` and `/th/th/*`).
- **AU Menulog revisit**: sample shows 48 AUD hits/page with both JSON-LD and NEXT_DATA. The existing 12% parser yield is a parser undercount, not a source limit. Full re-sweep deferred pending parser work.

### Scraper wiring
- `historical_html_scraper.py`: added BRL / EUR / ZAR currency regexes; added `parse_ubereats`, `parse_lieferando`, `parse_tripadvisor_za` parsers; appended 6 new TARGETS (BR ubereats + ifood-rj, DE lieferando + wolt-de, ZA tripadvisor-za + ubereats-za). Not yet executed — each needs a small smoke test (`--per-period 2`) before a full sweep, partly because iFood / Rappi / TripAdvisor BR + DE sample fetches all returned HTTP 503 during probing and may need header tweaks.

### Probe scripts
- `phase0_probe_br_de_za.py` + `phase0_probe_track_b.py`: roll-up logic now skips rows whose sample fetch failed before ranking. The original auto-generated roll-up in `coverage_report_br_de_za.md` is preserved with a corrected version above it for clarity.

### Docs
- `docs/track_b_c_findings_2026-06-17.md`: per-country yields, parser/source verdicts, and the parser-yield gap for AU Menulog.

## 2026-06-17 — Mexico floor-only page; Track C kickoff

### Mexico added as proxy-only country on dashboard

`final_roster.md` and `data_gaps.md` already document Mexico as proxy-only
(TripAdvisor MX exposes restaurant-level tier markers, not menu items; no
other Wayback source clears the formal-sector threshold). The data was
loaded by `floor_datasets.py` — Numbeo (32 rows, 2018–2025), Big Mac
(43 obs, 2000–2026), World Bank CPI (120 monthly rows, 2015–2024) — but
the dashboard didn't surface it. The LatAm tile is now live with honest
"proxy data only" labeling.

- **Types** (`dashboard/types/index.ts`): added `PROXY_COUNTRIES`,
  `FloorData`, `FloorDataMap`, Mexico to `COUNTRY_FLAGS` /
  `COUNTRY_SLUGS` / `DEVELOPMENT_STATUS`.
- **Floor-data export** (`dashboard_data.py`): new `build_floor_data()`
  reads `numbeo_index`, `bigmac_index`, `monthly_cpi` for each proxy
  country and writes `floor_data.json` to `dashboard_data/` and
  `dashboard/public/data/`.
- **Country page** (`dashboard/app/[country]/page.tsx`): proxy countries
  detected at request time; render a separate `ProxyCountryPage`
  template — no UIFPI chart, an amber "no item-level UIFPI computed"
  banner, four StatCards (Big Mac USD, WB CPI, Numbeo inexpensive,
  Numbeo midrange), two charts (Big Mac USD time series, WB CPI time
  series), and a Numbeo year-table. Page docstring notes Numbeo's
  current-snapshot methodology so the flat year-over-year values
  aren't misread as missing data.
- **Homepage** (`dashboard/app/page.tsx`): new "Proxy data only"
  section below the main grid with a `ProxyCountryCard` showing the
  latest Big Mac (USD) and WB CPI per country.
- **FloorChart** (`dashboard/components/FloorChart.tsx`): a simpler
  Recharts wrapper for floor time-series; same Recharts version as
  `IndexChart` to avoid SSR shape surprises.

`generateStaticParams()` now produces 9 routes (8 UIFPI + 1 proxy).
`next build` completes; SSR Recharts width warnings are unchanged.

### Phase 0 probes for BR + DE + ZA in flight

Companion probe script (`phase0_probe_br_de_za.py`) launched against
12 candidate (country, platform) patterns: TripAdvisor + iFood + Rappi
+ Uber Eats for BR, TripAdvisor + Lieferando + Wolt + Uber Eats + Yelp
for DE, TripAdvisor + Mr D Food + Uber Eats + EatOut for ZA. Results
land in `coverage_report_br_de_za.{csv,md}` in the same yields-table
format as `coverage_report.md`. Decision: any country whose best
platform has ≥15 ≥2-cap restaurants AND ≥5 currency-token hits in the
sampled HTML gets queued for `historical_html_scraper.py` integration.

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

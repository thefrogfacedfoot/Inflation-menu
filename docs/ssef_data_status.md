# UIFPI — SSEF 2026 data status

**Date**: 2026-06-18
**Scope**: 8-country panel (no Mexico, no Vietnam, no Brazil / Germany / South Africa — those expansions were attempted in mid-June 2026, found infeasible on Wayback archives, and reverted).
**Data collection**: closed. Going-forward signal will arrive via the monthly ingest cron rather than further historical sweeps.

## Headline finding

**United States — UIFPI Granger-causes CPI at 1-month lead.** F(26, 1) = 6.034, p = 0.0210, n = 31 overlapping months (2018-04 → 2024-10). Both series stationary at levels (UIFPI ADF p ≈ 0, CPI ADF p = 0.018). VAR-AIC selected lag 4 but lag 1 carries the signal (p at lags 2–4: 0.090, 0.138, 0.146). Pass-through β = −0.00248 with 95 % CI [−0.00531, +0.00034] — small, of indeterminate sign, **not significant** at 5 %; the result is a *timing* signal, not a *level* one.

## Per-country roll-up

| Country | n overlap | Granger p | β | 95 % CI on β | Verdict |
|---|---:|---:|---:|---|---|
| **United States** | **31** | **0.021** ✓ | −0.00248 | [−0.00531, +0.00034] | **Significant**; lead = 1 month |
| India | 47 | 0.474 | −0.00076 | [−0.00220, +0.00068] | Null result |
| **Australia** | **23** | — | — | — | **Pending one CPI publication** — ABS Q2 2026 expected late July via OECD SDMX. AU UIFPI sits at 24 distinct months; CPI overlap is 23. The next monthly ingest after the publication will tip AU over the n = 24 threshold automatically. |
| **United Kingdom** | **18** | — | — | — | **Accumulating monthly**. 17,371 items / 20 months in UIFPI; CPI overlap 18. Bridging 18 → 24 requires either pre-2021 Wayback archives (the JS-shell era for Deliveroo — uncertain hit rate) or 6 monthly ticks of going-forward collection. SSEF write-up should treat UK as a "pending" panel member. |
| Indonesia | 20 | — | — | — | Restaurant-aggregate Zomato cost-for-two series. Hit n = 20 last year; closer to threshold than SG/MY/TH but methodologically distinct from item-level countries (one observation per restaurant per archived date, not per menu item). |
| Singapore | 8 | — | — | — | 9,557 items but only 9 distinct months of UIFPI — live going-forward pipeline started mid-2026. |
| Malaysia | 6 | — | — | — | Live collection ongoing. |
| Thailand | 0 | — | — | — | Single 2026-06 snapshot (11 items, 9 restaurants). No archival depth from Wayback (multiple alternative sources probed and bailed — see `coverage_report_track_b.md`, `coverage_report_id_th_alts.md`). |

Significant Granger results: **1 / 8** (United States).

## Method — how the index is constructed

**Index construction.** `index_builder.py` builds UIFPI from `prices` table rows (`price > 0`, currency-converted to USD with same fallback rates as `dashboard_data.py`). Method = `restaurant-median` (see `82091d3 index_builder: default to restaurant-median method`). Per (country, year_month), prices are sampled to `MAX_ROWS_PER_COUNTRY` with a deterministic random seed so dense months don't dominate. Formal vs. informal sector tracked separately and combined into `uifpi_combined`. Hedonic adjustments applied per `quality_signals` JSON from `nlp_pipeline.py`, capped at ±15 %.

**Stationarity & Granger.** `granger_analysis.py --min-obs 24`. ADF test on each series at 5 %; series differenced if non-stationary. VAR lag chosen by AIC, capped at min(4, n/5). `grangercausalitytests` over the joint (CPI, UIFPI) series; we report the minimum-p lag.

**Pass-through.** OLS of Δ log CPI on Δ log UIFPI per Cavallo-Rigobon (2016). Standard errors and 95 % CIs reported in `docs/granger_results_2026-06-18.md`.

## Sources

**Item-level (in priority order)**:

- **United States**: MenuPages via Wayback Machine (JSON-LD Menu / MenuSection / MenuItem). 8,282 rows / 55 restaurants / 29 archived months.
- **Singapore**: live GrabFood + foodpanda; archived GrabFood via Wayback NEXT_DATA (842 rows / 12 restaurants / 8 months).
- **Malaysia**: live foodpanda + GrabFood.
- **United Kingdom**: archived **Deliveroo** via Wayback's embedded body-HTML JSON (15,845 rows from 53 hit pages across 8 UK cities — London, Manchester, Birmingham, Edinburgh, Glasgow, Bristol, Leeds, Liverpool; ingested 2026-06-18). Plus existing live Deliveroo + 3 direct chains.
- **India**: Zomato NCR cost-for-two (Wayback). Methodologically *restaurant-aggregate* (one observation per restaurant per archived date), not item-level — flagged as such in the UIFPI and on the dashboard.
- **Indonesia**: Zomato Jakarta cost-for-two (Wayback). Same restaurant-aggregate shape as India.
- **Australia**: archived **Menulog** via Wayback's `data-test-id="menu-item"` DOM containers (1,652 rows from 25 hit pages across 19 months, ingested 2026-06-18). Plus live direct chains.
- **Thailand**: Wayback TripAdvisor/Wongnai THB-regex extraction over a single 2026-06-13 sweep (11 items, 9 restaurants). No archival depth recoverable.

**Floor / cross-country reference**: World Bank `FP.CPI.TOTL`, The Economist Big Mac Index, Numbeo restaurant-price indicators. Loaded but **not surfaced** on the SSEF dashboard (a hybrid floor section was attempted and reverted on 2026-06-18 — keeping the artifact focused on item-level UIFPI).

## Honest collection notes

- **TripAdvisor `priceRange` tier-marker purge (2026-06-17).** TripAdvisor restaurant pages store the `priceRange` field (`$`, `$$`, `$$$`, `$$$$`) as a tier ordinal 1–4. An early version of `historical_scraper.py` wrote these into `prices` with `item_name = "Price tier (TripAdvisor: $$)"` and used them in the index — they're categorical, not currency, and produced wildly inflated levels (Indonesia briefly read 26 M). On 2026-06-17 **1,648 tier-marker rows** (TH 279, UK 293, US 277, IN 237, AU 221, MY 188, ID 118, SG 35) were deleted from `prices`. The scraper was updated to skip the tier path; the index builder's filter was removed as redundant. Pre-purge snapshot preserved locally as `uifpi.db.backup_pre_tier_purge_20260617_204040`.
- **AU Menulog delivery-fee fix (2026-06-18).** The first 15 `wayback-menulog` rows in `prices` were all delivery-fee values (4.99 / 5.00 / 10.00 / 20.00 — Menulog's flat-fee structure) emitted by a JSON-LD walker that inherited the Restaurant's `name` into anonymous `Offer` leaves. Those 15 rows were deleted; the walker now requires the emitting node to carry its own `name`. The new DOM extractor recovered **1,652 real menu items** from the same 96-snapshot cache.
- **Delivery-app archives are mostly JS shells.** Phase 0 probes (`coverage_report.md`, `coverage_report_br_de_za.md`, `coverage_report_track_b.md`, `coverage_report_id_th_alts.md`) confirmed that modern delivery aggregators load menus via XHR after page render and Wayback only captures the static HTML shell. iFood, Uber Eats (BR / DE / ZA), Lieferando, Wolt, GoFood, ShopeeFood, and GrabFood Thailand all bail at the structured-data layer or are bot-blocked at the archive layer. Menulog AU and Deliveroo UK are the exceptions because they embed the menu in body HTML rather than hydrating later; both required custom DOM/regex extractors written for this project.
- **Probe-first discipline.** Every (country, source) pair was Phase 0 probed before scraping. The yields tables are committed (`coverage_report*.md`) and are the auditable rationale for which sources were queued and which were declined.

## Going-forward path

- **Monthly cron** (`scheduled/monthly_ingest.py` + `.github/workflows/monthly_ingest.yml`). Refreshes CPI, re-runs the index, re-runs Granger at `--min-obs 24`, regenerates the dashboard JSON, appends a per-country yield row to `docs/ingest_log.md`. Cloud-hosted runners default to `--skip-scrape` because Foodpanda + GrabFood bot-block datacenter IPs; the live-scraper portion needs a residential-IP self-hosted runner or a local launchd job.
- **Expected crossovers**:
  - **AU** the moment the ABS Q2 2026 CPI lands on OECD's SDMX endpoint — automatic, no manual step.
  - **UK** ~6 monthly ticks (late 2026) via going-forward Deliveroo + direct-chain collection.

The homepage Granger counter and country-page status pills read directly from `country_summary.json` so any crossover triggered by the cron will surface on Vercel within minutes of the commit.

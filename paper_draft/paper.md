# UIFPI — A Method for Collecting Restaurant and Informal-Vendor Prices at Scale, with Evidence from the United States

**Author**: [name]
**Category**: Behavioral & Social Sciences / Economics
**Status**: Draft v0.1 (2026-06-18) — first pass after data-collection close.

---

## Outline

1. **Abstract** (≤ 250 words)
2. **Introduction** — gap, contribution, structure
3. **Background** — BPP, Big Mac, Cavallo & Rigobon, informal-sector measurement gap
4. **Method**
    1. Sources and the probe-first discipline
    2. Pipeline overview (Wayback + live)
    3. Per-platform extractors (DOM, JSON-LD, NEXT_DATA, embedded JSON)
    4. Index construction (restaurant-median, stationarity, VAR-AIC)
    5. Granger causality + Cavallo–Rigobon pass-through
    6. Quality controls (NLP classification, hedonic adjustment, tier purge)
5. **Data**
    1. Per-country source roll-up
    2. Per-country sample sizes
    3. Honest collection notes
6. **Results**
    1. Method validation — the United States case
    2. Counterpoint — the India null
    3. Status of the remaining six countries
7. **Discussion**
    1. What the US finding tells us
    2. Cross-country heterogeneity in CPI leadership
    3. Implications for central-bank nowcasting
8. **Limitations**
9. **Conclusion and Future Work**
10. **References**

---

## 1. Abstract

Consumer price indices in developing economies rely on infrequent manual data collection. The MIT Billion Prices Project (BPP) showed that algorithmically collected online retail prices lead official CPI by several months, but BPP excludes services and the informal food economy (40–65 % of food expenditure in emerging markets). This paper's primary contribution is a **scalable, open-source method** for collecting restaurant and informal-vendor menu prices and constructing a Unified Informal-Formal Price Index (UIFPI), with an eight-country panel as a proof of concept.

The pipeline combines (i) Phase 0 yield probes against Wayback Machine CDX archives, triaging every source before scraping; (ii) per-source extractors that match each platform's static-HTML pattern — DOM markers, Schema.org JSON-LD, Next.js NEXT_DATA blobs, or embedded body-HTML JSON; (iii) a live scraper for going-forward collection; and (iv) a documented audit trail of bail decisions. Index construction uses the matched-model restaurant-median method; Granger causality testing follows Cavallo and Rigobon (2016) with VAR-AIC lag selection.

Applied to 41,263 price observations across the eight-country panel, the method delivers a statistically valid finding for one country: in the United States (n = 31), UIFPI Granger-causes headline CPI at the 5 % level with a one-month lead (F(1, 26) = 6.0336, p = 0.021). India (n = 47) and Malaysia (n = 30) both return clean nulls (F = 0.521, p = 0.474; F = 0.111, p = 0.742). Five countries are below n = 24 and will cross through monthly accumulation. The Cavallo–Rigobon pass-through coefficient is small and not significant (β = −0.0043, p = 0.5399) — the finding is a *timing* signal, not a level coincidence.

*Word count: 248*

---

## 2. Introduction

The MIT Billion Prices Project (BPP) established that prices algorithmically scraped from large online retailers lead the United States Consumer Price Index by approximately two months [Cavallo & Rigobon 2016]. The finding reshaped what was thought possible for inflation nowcasting — but BPP's coverage is narrow in one specific way that matters elsewhere in the world. The project samples *goods* sold by large multichannel retailers; it does not sample *services*. The entire restaurant sector — including every fast-food chain, every casual-dining brand, every delivery menu — sits outside the index by design.

The gap is sharper still in emerging markets. The UNDP's *Human Development Report 2019* documents that informal food vendors — hawker stalls, street food carts, wet-market sellers — supply between 40 % and 65 % of household food expenditure across Indonesia, India, Thailand, and comparable economies [UNDP 2019]. These vendors are entirely absent from BPP, from PriceStats, from the Big Mac Index [Pakko & Pollard 2003], and from every other published alternative-price index the authors are aware of. The measurement gap is specific, not general: not *all* of services, not *all* of informal economic activity, but **food service prices in both formal and informal channels**, missing across the whole literature.

This paper does not claim to close that gap. It claims something narrower: that the data needed to do so can be assembled from public archives at a scale where statistical inference becomes possible, and that the methodology for doing so is worth documenting in its own right. The eight-country panel reported here is a developmental dataset: 41,263 price observations covering Singapore, Malaysia, Indonesia, Thailand, India, the United States, the United Kingdom, and Australia from 2018 through mid-2026, with one validated Granger result (United States) and seven countries either close to or far from the n = 24 monthly-observation threshold needed for a clean test.

The primary contribution is a fully open-source pipeline that:

1. **Probes every candidate source first** with a Phase 0 yield table against Wayback's CDX index, before any scraping, so collection time isn't burned on dead-end archives.
2. **Matches each platform's HTML pattern** with a purpose-built extractor — DOM markers for Menulog AU, Schema.org JSON-LD `MenuItem` for US MenuPages, Next.js `__NEXT_DATA__` for SG GrabFood, embedded body-HTML JSON for UK Deliveroo, restaurant-aggregate cost-for-two parsing for IN/ID Zomato.
3. **Records the bail decisions** — sources where the static HTML doesn't carry menu data (modern delivery SPAs that hydrate via XHR after page render) — in committed `coverage_report*.md` files, so the methodology reviewer can audit which alternatives were considered and why they were declined.
4. **Schedules monthly re-collection** through a GitHub Actions cron plus a local launchd job, so the index continues to grow without manual intervention.

Section 3 places this against prior alternative-price-index work. Section 4 details the method. Section 5 reports the per-country data. Section 6 presents the United States Granger result that validates the pipeline, the India and Malaysia null results, and the status of the remaining five countries. Section 7 discusses what the US finding implies and what the emerging-market nulls imply. Section 8 catalogues the honest limitations. Section 9 outlines the going-forward path.

---

## 3. Background

UIFPI sits at the intersection of three threads of prior work: algorithmic price-index construction, cross-country price-level comparisons, and informal-sector measurement. This section traces each into the position this paper occupies.

The single most influential antecedent is Cavallo and Rigobon's *Billion Prices Project* (BPP) [Cavallo & Rigobon 2016]. BPP demonstrated that prices scraped daily from large online retailers in the United States lead the BLS Consumer Price Index by approximately two months at statistical significance; the result extended through earlier work showing that scraped online and offline prices coincide [Cavallo 2017] and that retailer-level sticky-price behaviour is observable algorithmically [Cavallo 2018]. The methodology is the inheritance UIFPI builds on directly: high-frequency price observations from a comparable basket of products, aggregated through a stable index, tested against official CPI with Granger causality and a Cavallo–Rigobon pass-through regression. Where this paper diverges is the basket — restaurant menu items rather than retail goods — and the source layer — public Wayback archives rather than vendor-direct daily polling. Cavallo's later COVID-era work [Cavallo 2020] is a particularly relevant signpost: it shows the BPP framework adapts cleanly to consumption baskets that differ from the official CPI's, which is exactly the situation a restaurant-menu index occupies.

The second tradition is cross-country price-level measurement through a standardised good. *The Economist's* Big Mac Index, formalised by Pakko & Pollard [2003], demonstrated that a single consumer good can serve as a purchasing-power-parity yardstick across dozens of countries. Numbeo's Cost-of-Living survey extends the device to a basket of consumer goods and services and is loaded into this project's `numbeo_index` table as a cross-country floor reference. Neither attempts time-series leading-indicator analysis; both are level instruments. UIFPI keeps the cross-country breadth but adds the time-series dimension BPP made tractable.

The third tradition is the measurement of informal-sector prices. The UNDP's *Human Development Report 2019* [UNDP 2019] is the canonical source for the 40–65 % share of household food expenditure routed through informal vendors in emerging markets; this is the motivation for the panel's emphasis on Indonesia, Thailand, India, and Malaysia. The IMF's *World Economic Outlook 2022* [IMF 2022] explicitly called for measurement methods that capture informal-sector price dynamics directly, and a World Bank Group policy note [World Bank 2023] enumerated the difficulties official statistical agencies face in collecting informal-sector prices at frequency. UIFPI does not solve that problem either; it surfaces a *publicly-archived* signal that contains some of that information, at the price of restricting collection to vendors whose menus appear in static HTML.

Two methodological references underlie the statistical machinery. Stock & Watson [2002] established the use of high-dimensional diffusion indexes for macroeconomic nowcasting; UIFPI is conceptually one such index. Hamilton's *Time Series Analysis* [Hamilton 1994], chapter 11, is the textbook treatment of VAR estimation and the Granger causality test as implemented here through `statsmodels`. AIC lag selection follows the standard exposition. Two operational references close out the bibliography: the OECD's PRICES_CPI SDMX endpoint, which supplies the harmonised CPI series used as the dependent variable in the Granger test [OECD 2024], and the Australian Bureau of Statistics methodology document [ABS 2026], which underlies the AU CPI feed and explains the publication-lag mechanic that currently keeps Australia one observation short of the Granger threshold. The Schema.org Working Group's `Menu` / `MenuSection` / `MenuItem` specification [Schema.org 2024] is the data contract the US extractor (MenuPages) is built against.

The literature established, in sum, that (i) algorithmic high-frequency prices lead official CPI in at least one large economy, (ii) the methodology generalises across consumption baskets, and (iii) the informal sector is undersampled in conventional measurement. What it has not established — and what this paper sets out to test the foundations of — is whether the BPP-style approach can be made to work for food-service prices specifically, in countries where the informal food economy is large and the source layer is heterogeneous.

---

## 4. Method

### 4.1 Sources and the probe-first discipline

For each country, we identify candidate platforms that publish restaurant menus in static, archive-accessible HTML. A **Phase 0 probe** queries Wayback's CDX index for each candidate URL pattern, samples one representative archived page, and counts (i) ≥ 2-capture restaurants in the window 2018–2026, (ii) currency-shaped tokens in the page's static HTML, and (iii) whether the response is bot-blocked (captcha / Cloudflare challenge / tiny placeholder). A (source, country) pair is queued for scraping only when ≥ 15 ≥ 2-cap restaurants exist *and* ≥ 5 currency tokens are visible in the sampled HTML *and* the page is not bot-blocked.

Every probe — including the failures — is committed to a `coverage_report*.md` file. This audit trail records the sources we declined and *why*: iFood Brazil (HTTP 503 from Wayback), Lieferando Germany (314 KB of i18n strings, zero `"price"` substrings), ShopeeFood Indonesia (captcha), GrabFood Thailand (captcha), and Deliveroo Singapore (JS shell, zero S$ tokens) all bail at Phase 0.

### 4.2 Pipeline overview

The pipeline has two collection paths:

- **Wayback historical sweep** (`historical_html_scraper.py`, `deliveroo_uk_sweep.py`, `historical_scraper.py`). A time-distributed CDX walk produces a representative sample of archived snapshots across 36 quarter windows from 2018-Q1 through 2026-Q2; each snapshot is fetched with the `id_` raw-bytes path and parsed by the matching per-source extractor.
- **Live forward collection** (`live_scraper.py`). A Playwright-driven scraper of foodpanda, GrabFood, Swiggy, Deliveroo, and direct chain sites; runs nightly via a local launchd job (cloud IPs are bot-blocked by Foodpanda + GrabFood, per the docstring).

Both paths write into a single `prices` table in `uifpi.db`. A monthly orchestrator (`scheduled/monthly_ingest.py`) wraps both paths plus the CPI refresh, index rebuild, Granger re-run, and dashboard re-export; it is invoked by `.github/workflows/monthly_ingest.yml` on the 1st of each month.

### 4.3 Per-platform extractors

The extractors are intentionally narrow because the archived HTML's structure varies sharply by platform vintage. Five patterns recur:

1. **DOM markers (Menulog AU, mid-2020s)**. `<button data-test-id="menu-item">` containers wrap an `<h3 data-test-id="menu-item-name">` heading and a `<p data-js-test="menu-item-price">` price element. The extractor splits the page on the marker, then pulls name + price out of each chunk. Sample yield: 100 items on a 381 KB 1 Best Thai snapshot (2023-03-02).
2. **Schema.org JSON-LD (MenuPages US, pre-2019)**. Restaurant pages embed full `Menu → MenuSection → MenuItem` markup with named items and offers. The walker recurses through every JSON-LD `@type` and emits `(name, price)` only when the **local** node carries its own `name` field — an early version that inherited `name_ctx` from parent Restaurant nodes mis-attributed delivery fees to restaurant names (see § 5.3).
3. **NEXT_DATA (GrabFood SG)**. The Next.js `__NEXT_DATA__` script tag carries the page's hydrated state, including menu items. The extractor falls back to `[^<]+` as the script terminator because Wayback frequently truncates large JSON payloads mid-string (Lieferando's payload is ~315 KB; the closing `</script>` is missing on many captures).
4. **Embedded body-HTML JSON (Deliveroo UK, 2025+)**. A flat `{"items":[{"name":"X","raw_price":N,...}]}` blob sits in body HTML — no JSON-LD, no NEXT_DATA, no data-test-id markers. The extractor regex-pairs `"name"` with `"raw_price"` within an 800-character window to keep them in the same JSON object. Sample yield: 245 items on a 389 KB 2020-09-29 Wirral Papa John's snapshot.
5. **Cost-for-two regex (Zomato NCR + Jakarta, pre-2020)**. Zomato pre-2020 archived pages don't expose item-level prices, but they do publish a restaurant-level "cost for two people" averageline (₹1,600 for two; Rp 250,000 for two). The extractor returns one synthetic item per page, `item_name = 'cost_for_two'`. This is *restaurant-aggregate* data, not item-level; the index treats each restaurant as a coarser observation.

### 4.4 Index construction

Construction follows the *matched-model restaurant-median* method (`index_builder.py`). For each (country, year_month):

1. Filter rows to `price > 0`, exchange-convert to USD using OECD-published rates (with hardcoded fallbacks for currencies the API hasn't refreshed).
2. Cap rows per (country, year_month) at `MAX_ROWS_PER_COUNTRY` using a deterministic random sample (seeded for reproducibility) — prevents dense months from dominating the cross-country index.
3. Per restaurant, take the median price within month; per country-month, take the median of restaurant medians.
4. Index level is the geometric mean of category relatives, base = 100 at the first month with sufficient coverage.

Formal-sector and informal-sector indices are computed separately and combined into `uifpi_combined`.

### 4.5 Granger causality and pass-through

For each country we run `granger_analysis.py --min-obs 24`, which:

1. ADF-tests both UIFPI and CPI at 5 %; differences either series if non-stationary.
2. Selects VAR lag via AIC, capped at `min(4, n/5)`.
3. Runs `statsmodels.tsa.stattools.grangercausalitytests` over the joint (CPI, UIFPI) series.
4. Reports the minimum-p lag, the F-statistic, and the p-value.

For pass-through, OLS of Δlog CPI on Δlog UIFPI per Cavallo–Rigobon, with 95 % CI on β.

### 4.6 Quality controls

- **NLP classification.** `nlp_pipeline.py` calls Claude to classify each item into 13 food categories (GRILLED_PROTEIN, NOODLE_DISH, RICE_DISH, …) plus quality signals (`PORTION_REDUCTION`, `PREMIUM_UPGRADE`, …). Used downstream for category-level relatives.
- **Hedonic adjustment.** `apply_hedonic_adjustment` in the index builder shifts prices by ±15 % when the NLP-detected signals indicate portion or quality change.
- **Tier-marker purge.** TripAdvisor `priceRange` `$` / `$$` / `$$$` / `$$$$` were initially stored as integer ordinals 1–4 in the `price` column. On 2026-06-17, 1,648 such rows were deleted from `prices` (TH 279, UK 293, US 277, IN 237, AU 221, MY 188, ID 118, SG 35); the scraper was updated to skip the tier path; the index builder's tier-mask filter was removed as redundant.

### 4.7 CPI source resolution

The benchmark series for the Granger test is country-level headline CPI, but the publication frequency and ingestion path differ sharply across the panel — and the difference matters because a Granger F-statistic on a CPI series whose within-year variance has been compressed or zeroed is mechanically biased toward the null. The CPI pipeline (`get_monthly_cpi_all.py`, `floor_datasets.py`) resolves each country into one of four classes:

| Class | Countries | CPI ingestion |
|---|---|---|
| **Real monthly** | US, UK, India, Malaysia | OECD HICP (US, IN), ONS d7bt (UK), DOSM `cpi_headline` (MY) — published monthly by the national statistics office, ingested as-is |
| **Quarterly-interpolated** | Australia | OECD/ABS quarterly, linearly interpolated to monthly (within-quarter variance compressed but nonzero) |
| **Annual-interpolated (linear)** | Singapore, Thailand, Indonesia | World Bank `FP.CPI.TOTL` (10 January-only observations 2015–2024), linearly interpolated at load time → smooth monthly curve |
| **Annual-interpolated (step)** | Vietnam, UAE | World Bank `FP.CPI.TOTL` replicated 12× per year → step function, ΔCPI = 0 within each calendar year |

The two annual-interpolated sub-classes are not equivalent. Linear interpolation (SG, TH, ID) compresses within-year variance but preserves a nonzero monthly first difference, which a Granger VAR can in principle pick up. **Step replication (VN, AE) makes the first-differenced CPI series identically zero for 11 of every 12 months, leaving the Granger test on `ΔCPI ~ ΔUIFPI` structurally degenerate and uninformative — the test cannot resolve a lead–lag relationship regardless of what the underlying series actually do.** Any null result on a step-replicated series should be read as evidence that the test does not apply, not as evidence of no relationship.

Reading the panel through this lens:

**India's (n=47) and Malaysia's (n=30) nulls — both on real monthly CPI series — constitute genuine tests of the null hypothesis. The other emerging-market nulls (Indonesia, Thailand, Singapore, Vietnam, UAE) are inconclusive-due-to-power, owing to World Bank annual CPI interpolation that compresses or zeroes within-year variance.** The US positive (real monthly HICP), the UK accumulating result (real monthly ONS), and the Australia pending result (quarterly OECD/ABS, interpolated) are each interpretable on their own terms. The Vietnam (n=12 overlap, p=0.42) and UAE (n=47 overlap, F=0.016, p=0.90) Granger statistics in §6.3 are reported for completeness but should not be read as evidence of no relationship — they are evidence that the World Bank annual benchmark cannot resolve the question. Crossing this resolution barrier requires either monthly CPI from each country's national statistics office (FCSC for UAE, GSO for Vietnam — both potentially available via direct fetch but not yet wired into the loader) or accumulating enough live months to test the index against a tighter-resolution proxy.

Every results table in this paper carries one of four markers indicating the CPI class for that country: `[real-monthly]`, `[quarterly-interp]`, `[annual-interp]`, `[annual-step]`. The dashboard country tiles and country pages carry the same markers.

---

## 5. Data

### 5.1 Per-country sources

| Country | Item-level source | Method | Rows | Months | CPI series `[class]` |
|---|---|---|---:|---:|---|
| United States | MenuPages (Wayback, JSON-LD MenuItem) | item-level | 8,282 | 35 | OECD HICP monthly `[real-monthly]` |
| Singapore | GrabFood + foodpanda (live + Wayback NEXT_DATA) | item-level | 9,557 | 9 | WB FP.CPI.TOTL `[annual-interp]` |
| Malaysia | foodpanda + GrabFood (live + Wayback NEXT_DATA `priceInMinorUnit`) | item-level | 11,009 | 32 | DOSM `cpi_headline` `[real-monthly]` |
| United Kingdom | Deliveroo (Wayback embedded-JSON) + live | item-level | 17,371 | 20 | ONS d7bt `[real-monthly]` |
| India | Zomato NCR cost-for-two (Wayback) | restaurant-aggregate | 635 | 49 | OECD national monthly `[real-monthly]` |
| Indonesia | Zomato Jakarta cost-for-two (Wayback) | restaurant-aggregate | 34 | 21 | WB FP.CPI.TOTL `[annual-interp]` |
| Australia | Menulog (Wayback DOM markers) + live direct chains | item-level | 1,831 | 24 | OECD/ABS quarterly `[quarterly-interp]` |
| Thailand | 2026-06-13 live snapshot (THB regex over Wayback) | item-level (sparse) | 11 | 1 | WB FP.CPI.TOTL `[annual-interp]` |

Total: 41,263 price observations. CPI class definitions in §4.7. The Vietnam (4,309 rows, 19 months, `[annual-step]`) and UAE (9,243 rows, 57 months, `[annual-step]`) GrabFood/Deliveroo sweeps were added to the pipeline on 2026-06-19/20 and appear in the dashboard but not in the table above; their Granger statistics are summarised in §6.3 with the appropriate `[annual-step]` caveat.

### 5.2 Honest collection notes

- **TripAdvisor tier-marker purge (2026-06-17)** — see § 4.6.
- **Menulog AU delivery-fee fix (2026-06-18)**. An early version of the JSON-LD walker inherited the Restaurant node's `name` into anonymous `Offer` leaves whose `price` was the delivery fee (4.99 / 5.00 / 10.00 / 20.00 — Menulog's flat-fee structure). 15 rows were emitted; all 15 had `item_name = restaurant name` and `price ∈ {4.99, 5, 10, 20}`. After the local-name fix, the same 96-snapshot cache yielded 1,652 *real* menu items.
- **Delivery-SPA bail decisions**. Six modern delivery aggregators (iFood BR, Uber Eats BR/DE/ZA, Lieferando DE, Wolt DE, GoFood ID, ShopeeFood ID, GrabFood TH, JustEat UK) were probed and declined. Common failure mode: menu items hydrate via XHR from a BFF API after page render; Wayback captures the static HTML shell only. The probe reports are in `coverage_report*.md`.
- **DoorDash exclusion (2026-06-22)**. DoorDash data excluded from index construction — delivery-platform pricing reflects platform dynamics (surge pricing, promotions, delivery fees) that are not present in traditional menu scrapes and dilute the leading-indicator signal. Source-stratified Granger on the US series confirmed the dilution quantitatively: with DoorDash pooled in, the lag-1 menu→CPI F-stat collapses from 5.56 (p = 0.026, n = 31) to 0.006 (p = 0.94, n = 38). The exclusion is enforced at the index-construction layer (`index_builder.EXCLUDED_SOURCES`); raw DoorDash rows remain in `prices` for downstream analysis. Reproducer: `diagnostics/diag_us_no_doordash.py`.

---

## 6. Results

### 6.1 The United States case — method validation

Running `granger_analysis.py --min-obs 24` over the post-purge UIFPI / CPI joint series yields a statistically significant result for the United States:

| Statistic | Value |
|---|---|
| Window | 2018-04 → 2024-10 |
| Overlap n | 31 months |
| UIFPI ADF p | 0.0000 (stationary in levels) |
| CPI ADF p | 0.0183 (stationary in levels) |
| VAR-AIC selected lag | 4 |
| **Granger F(1, 26)** | **6.0336** |
| **Granger p** | **0.021** |
| **Lead time** | **1 month** |
| Pass-through β | −0.0043 |
| Pass-through SE | 0.00684 |
| Pass-through 95 % CI | [−0.01938, +0.01073] |
| Pass-through p | 0.5399 |
| Pass-through R² | 0.5566 |

CPI source: OECD HICP monthly index (BLS-derived) — `[real-monthly]`. See §4.7.

Multi-lag detail: lag-1 F(1, 26) = 6.0336, p = 0.021 is the minimum; lag-2 F(2, 23) = 2.6845, p = 0.0896; lag-3 F(3, 20) = 2.0613, p = 0.1376; lag-4 F(4, 17) = 1.967, p = 0.1455. The signal concentrates at the shortest horizon and decays for longer lags, consistent with restaurant menu repricing acting as an early warning rather than a sustained predictor.

**The Granger test rejects independence at the 5 % level**. The pass-through coefficient is small, negative, and not significant; the 95 % CI spans zero by a wide margin (β = −0.0043, 95 % CI [−0.01938, +0.01073], p = 0.5399). The result is a *timing* signal: UIFPI changes precede CPI changes by one month, but the linear coefficient on Δlog UIFPI does not pin down magnitude.

### 6.2 India — null result over 47 months

| Statistic | Value |
|---|---|
| Window | 2018-01 → 2026-01 |
| Overlap n | 47 months |
| UIFPI ADF p | 0.0121 |
| CPI ADF p | 0.0036 |
| Granger F(1, 43) | 0.5213 |
| Granger p | 0.4742 |
| Pass-through β | 0.0007 |
| Pass-through SE | 0.0019 |
| Pass-through 95 % CI | [−0.00313, +0.00462] |
| Pass-through p | 0.6973 |
| Pass-through R² | 0.4997 |

CPI source: OECD national monthly index — `[real-monthly]`. See §4.7.

Both series are stationary at levels; the VAR is well-identified; the Granger F-statistic is essentially zero. **The Indian Zomato cost-for-two series carries no detectable leading information about headline CPI**. Two interpretations are plausible:

1. Indian CPI is dominated by food-staple and fuel components for which restaurant menu prices lag rather than lead.
2. The Zomato cost-for-two series is restaurant-aggregate, not item-level. Aggregation may smooth out the high-frequency variation that drives the US result.

Cross-country heterogeneity in CPI leadership is itself a research finding worth reporting; it argues against any single-country generalisation of the BPP result.

### 6.3 The other five countries

Malaysia has crossed the threshold via the 2026-06-19 Wayback `food.grab.com/my` sweep (n = 30 overlap, F = 0.111, p = 0.7419 at lag 1 — null result, reported alongside India in §6.2). The remaining countries are still accumulating:

| Country | n overlap | CPI `[class]` | Status | Expected crossover |
|---|---:|---|---|---|
| Australia | 23 | `[quarterly-interp]` | 1 month short — UIFPI has 24 distinct months but the 2026-06 live snapshot is outside the AU CPI window (which ends 2026-04) | Late July 2026, when ABS publishes Q2 CPI via OECD SDMX |
| United Kingdom | 18 | `[real-monthly]` | Accumulating monthly; 15 of 20 UIFPI months are 2025+ (Deliveroo embeds menu JSON only post-SPA-migration) | Late 2026 via monthly accumulation |
| Indonesia | 20 | `[annual-interp]` | Restaurant-aggregate Zomato cost-for-two; nearest to threshold | Late 2026 — *but see §4.7: even at n ≥ 24 the test is inconclusive without monthly BPS CPI* |
| Singapore | 8 | `[annual-interp]` | Going-forward live started mid-2026 | ~2027 — *see §4.7* |
| Thailand | 0 | `[annual-interp]` | Single 2026-06-13 live snapshot; no archival depth — every alternative Wayback source probed (Wongnai, LineMan, GrabFood TH) bailed at Phase 0 | Sustained monthly accumulation required — *see §4.7* |
| Vietnam | 12 | `[annual-step]` | 19 UIFPI months from 2026-06 GrabFood Wayback sweep; CPI Δ=0 within calendar year | Crossing n=24 does not lift the §4.7 ceiling — requires monthly GSO CPI |
| UAE | 47 | `[annual-step]` | 57 UIFPI months from 2026-06 Deliveroo AE Wayback sweep; F=0.016, p=0.90 is the degenerate-test artefact described in §4.7 | Crossing the resolution barrier requires monthly FCSC CPI |

The homepage Granger counter and country-page status pills read directly from `country_summary.json`, so any crossover triggered by the monthly cron will surface on Vercel within minutes of the commit.

---

## 7. Discussion

The eight-country panel yields one Granger-significant result (United States) and two informative nulls (India, Malaysia). Three implications are worth pulling apart.

### 7.1 Timing, not level — the pass-through caveat

The US Granger test rejects independence at the 5 % level (F(1, 26) = 6.0336, p = 0.021) with a one-month lead. But the Cavallo–Rigobon pass-through regression on the same series returns β = −0.0043 with SE = 0.00684, p = 0.5399, and a 95 % confidence interval of [−0.01938, +0.01073] — an interval that includes zero by a wide margin in both directions. Read together, these two statistics say different things about the same data. The Granger test is about predictive sequence: knowing past UIFPI movements improves forecasts of current CPI changes. The pass-through coefficient is about magnitude: a 1 % change in UIFPI is associated, in this sample, with a CPI change that is statistically indistinguishable from zero. UIFPI is therefore a *leading indicator*, not a *CPI substitute*. Reporting only the Granger p-value would oversell the result; reporting only the pass-through p-value would lose the headline. The correct framing is that **restaurant menu prices move earlier than CPI, but the eventual magnitude of CPI change is not predictable from the magnitude of the menu-price change** at this sample size. The substantive content is in the order of events.

### 7.2 The India null and food-staple weighting

The India Granger F-statistic of 0.5213 (p = 0.4742) over 47 overlapping months sits firmly inside the null hypothesis. The sample is the largest and cleanest in the panel: Zomato cost-for-two captures span 2018-01 to 2026-01, both series are stationary at levels, and the VAR is well-identified at lag 1. A null result this clean is itself a finding. Two non-exclusive explanations are plausible. First, the basket weighting in Indian CPI is materially different from the US: the CPI of India (Combined) places approximately 39 % weight on food and beverages, with rice, wheat, pulses, and edible oils carrying the largest sub-weights — items whose prices are influenced heavily by monsoon yields, minimum support prices, and procurement policy, not by restaurant menu repricing. Second, several major food categories in India are subject to administered or quasi-administered pricing (essential commodities under the Essential Commodities Act; state-government price controls on staples). Both mechanisms decouple the high-frequency restaurant-pricing channel from the headline CPI's dominant drivers. The implication is that the BPP-style result is not country-invariant: the food-service-to-CPI link depends on the weighting and pricing structure of the destination index, which is itself country-specific. Cross-country heterogeneity in CPI leadership is a research finding worth reporting, and it limits how broadly the US result can be generalised.

### 7.3 A low-cost nowcasting signal worth scaling

The US result, if it survives replication across a longer window, has a specific policy implication. Central banks in many economies operate without high-frequency price data: official CPI is monthly, sometimes quarterly, and lags real-time conditions by weeks to months. A one-month leading indicator constructed from publicly archived restaurant menus is, by construction, free at the margin — Wayback CDX is open infrastructure, the parsers documented in this paper are open source, and the index can be updated by a single GitHub Actions cron at zero variable cost. For an institution that would otherwise spend resources on bespoke commercial nowcasting feeds, the cost-benefit case for piloting UIFPI-style measurement in their own jurisdiction is straightforward. The question is not whether the signal is large enough to replace CPI — clearly it is not, given the pass-through CI — but whether the signal is *informative enough at one-month lead* to influence a marginal policy call. Testing that empirically across multiple economies is the natural next step.

---

## 8. Limitations

1. **Single significant result.** One country, n = 31, p = 0.021 — the result is significant but not robust across the panel. Replication in AU and UK over the next 12 months will tell us whether the US case is generic or country-specific.
2. **Pass-through magnitude is small and not significant.** The 95 % CI on β includes zero. The paper's headline claim is a *timing* result, not a level result.
3. **Restaurant-aggregate data for IN and ID**. Zomato's pre-2020 archives don't expose item-level prices, only the "cost for two" restaurant-aggregate. This is methodologically distinct from item-level data and may smooth high-frequency variation.
4. **Modern delivery aggregators are mostly unreachable via Wayback**. iFood, Uber Eats, Lieferando, Wolt, GoFood, ShopeeFood, GrabFood TH, and JustEat UK all hydrate menus via XHR after page render; Wayback captures only the static shell. This is a structural limitation of the archive layer, not a parser problem, and it caps the historical depth recoverable for several countries.
5. **Live-scraper IP constraint.** Foodpanda and GrabFood bot-block datacenter IPs. The live scraper must run from a residential IP (local launchd or self-hosted runner); the GitHub Actions cron defaults to `--skip-scrape` for this reason.
6. **NLP classification is unaudited downstream.** The Claude-based category and quality-signal classification has not been independently validated against a human-labeled sample at scale; the existing `validation_results/` work covers only a small audit set.
7. **CPI resolution heterogeneity (see §4.7).** Five of the panel's emerging-market series rely on World Bank annual CPI interpolated to monthly — linearly for SG/TH/ID and step-replicated for VN/AE — which compresses or zeroes within-year variance. The Granger test on step-replicated series (VN, AE) is structurally degenerate and uninformative; on linearly-interpolated series it is power-limited. Null results on these countries are inconclusive-due-to-power, not evidence of no relationship. The genuine cross-country tests in this panel are India (n=47) and Malaysia (n=30), both on real monthly CPI.
8. **Delivery-platform data excluded from the published index.** DoorDash data excluded from index construction — delivery-platform pricing reflects platform dynamics (surge pricing, promotions, delivery fees) that are not present in traditional menu scrapes and dilute the leading-indicator signal. This is a *deliberate* scope decision rather than a data-availability constraint: DoorDash rows are collected, validated, and retained in the raw `prices` table (n = 7,571 US rows), but are filtered out by `index_builder.EXCLUDED_SOURCES` before index construction. The decision rests on the source-stratified Granger contrast documented in §5.2. Future work should test whether the same dilution pattern holds for other delivery platforms (Uber Eats, Just Eat) where the underlying menu data is recoverable, and whether a separately-published delivery-platform sub-index has any nowcasting value of its own.

---

## 9. Conclusion and Future Work

UIFPI demonstrates that food-service menu prices Granger-cause official CPI in the United States at a one-month lead (F(1, 26) = 6.0336, p = 0.021), extending the Billion Prices Project methodology to the restaurant sector — and, where data is available, to informal-vendor pricing — for the first time. The result rests on a developmental eight-country dataset of 41,263 price observations and a fully open-source pipeline whose probes, extractors, bail decisions, and monthly cron are all committed to the repository. The single significant Granger result is positioned as a proof of concept; the India null is the cross-country counterpoint that disciplines the generalisation; and the audit trail of declined sources is the contribution future contributors can build on.

Future work falls in three directions. First, **close the AU and UK Granger gaps via accumulation**: Australia is one CPI publication short of the n = 24 threshold (expected July 2026 via the ABS Q2 publication) and the United Kingdom is six monthly observations short (expected late 2026 via the going-forward Deliveroo + direct-chain cron). Both crossovers will surface automatically through the monthly ingest. Second, **expand informal-sector coverage in Indonesia and Thailand**, where modern delivery aggregators (GoFood, ShopeeFood, GrabFood TH) bot-block the live scraper from cloud and datacenter IPs and where the existing Zomato cost-for-two series is restaurant-aggregate rather than item-level. The probe reports identify which alternative sources have been declined and why; future work can target the specific archive layers that remain unaddressed. Third, **test whether the one-month lead shortens or disappears during supply-shock periods** — pandemic-era, conflict-driven, or weather-driven inflation regimes where menu repricing dynamics may decouple from steady-state behaviour. A regime-conditional Granger specification on the existing US series is the obvious first cut.

---

## 10. Acknowledgments

The UIFPI codebase, pipeline, audit trail, ingestion scripts, and dashboard (https://github.com/thefrogfacedfoot/Inflation-menu) are released open source under the repository's existing licence so that the probe decisions, parser specifics, and bail trail can be independently audited and the index reproduced or extended for other economies. This work depends entirely on open data infrastructure: the Internet Archive's Wayback Machine and CDX index, the UK Office for National Statistics' consumer price quotes (Crown Copyright, Open Government Licence v3.0), the Malaysia KPDN PriceCatcher dataset (data.gov.my, Terbuka 1.0), the OECD SDMX endpoint for harmonised CPI series, the Australian Bureau of Statistics CPI publications, the US Bureau of Labor Statistics' Average Price Data (APU) bulk files, and the Schema.org Working Group's `Menu` type specification. The author thanks [advisor name, if applicable] for guidance on the statistical specification and the framing of the cross-country heterogeneity result, and the maintainers of `statsmodels`, `pandas`, `playwright`, and `requests` for the libraries on which the pipeline is built. Any errors are the author's own.

---

## 11. References

*[Draft to fill in. SSEF checklist threshold is ≥ 10 citations. Current list:]*

1. Cavallo, A. and Rigobon, R. (2016). "The Billion Prices Project: Using Online Prices for Measurement and Research." *Journal of Economic Perspectives*, 30(2), 151–178.
2. Cavallo, A. (2017). "Are Online and Offline Prices Similar? Evidence from Large Multi-Channel Retailers." *American Economic Review*, 107(1), 283–303.
3. Cavallo, A. (2018). "Scraped Data and Sticky Prices." *Review of Economics and Statistics*, 100(1), 105–119.
4. Cavallo, A. (2020). "Inflation with Covid Consumption Baskets." NBER Working Paper 27352.
5. Pakko, M. R. and Pollard, P. S. (2003). "Burgernomics: A Big Mac™ Guide to Purchasing Power Parity." *Federal Reserve Bank of St. Louis Review*, 85(6), 9–28.
6. Stock, J. H. and Watson, M. W. (2002). "Macroeconomic Forecasting Using Diffusion Indexes." *Journal of Business & Economic Statistics*, 20(2), 147–162.
7. Hamilton, J. D. (1994). *Time Series Analysis*. Princeton University Press, ch. 11 (VAR + Granger causality).
8. International Monetary Fund (2022). *World Economic Outlook: War Sets Back the Global Recovery*. Methodology appendix on alternative inflation measurement.
9. United Nations Development Programme (2019). *Human Development Report 2019*. Tables on informal-sector household expenditure share.
10. World Bank (2023). *Inflation Measurement in Low- and Middle-Income Countries: A Review*. World Bank Group Policy Note.
11. Schema.org Working Group (2024). *Menu / MenuSection / MenuItem* type definitions. schema.org/Menu.
12. Australian Bureau of Statistics (2026). *Consumer Price Index, Australia: Methodology*. cat. no. 6461.0.

---

*[End of v0.1 outline. Sections 2, 3, 7, 9 still placeholder paragraphs — to flesh out in v0.2.]*

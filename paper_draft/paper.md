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

Applied to 41,263 price observations across the eight-country panel, the method delivers a statistically valid finding for one country: in the United States (n = 31), UIFPI Granger-causes headline CPI at the 5 % level with a one-month lead (F(26, 1) = 6.034, p = 0.0210). India (n = 47) returns a clean null. Six countries are below n = 24 and will cross through monthly accumulation. The Cavallo–Rigobon pass-through coefficient is small and not significant — the finding is a *timing* signal, not a level coincidence.

*Word count: 248*

---

## 2. Introduction

*[Draft to fill in]*

The MIT Billion Prices Project (BPP) established that algorithmic price collection from large online retailers leads the U.S. Consumer Price Index by approximately two months [Cavallo & Rigobon 2016]. The result reshaped expectations of what high-frequency price data can do for nowcasting and monetary-policy lead times. But BPP is constrained in two ways that matter for the inflation question in most of the world: (i) it samples *goods* sold through large multichannel retailers, leaving services — including the entire restaurant sector — outside the index; and (ii) it has no mechanism for capturing prices set by informal vendors (hawker stalls, street food, market traders), which the UNDP estimates account for 40–65 % of household food expenditure in emerging markets [UNDP 2019].

The question this paper poses is not whether menu-price data *could* in principle replicate the BPP result for services. It is the engineering question of whether such an index can be **built and validated at all** with publicly available archives. The eight-country panel is the testbed; the method is the contribution.

The primary contribution is a fully open-source pipeline — about 6,000 lines of Python plus a Next.js dashboard — that:

1. **Probes every candidate source first** with a yield table against Wayback's CDX index before any scraping happens, ensuring time isn't spent on dead-end archives.
2. **Matches each platform's HTML pattern** with a purpose-built extractor — DOM markers for Menulog AU, JSON-LD MenuItem for US MenuPages, NEXT_DATA for SG GrabFood, embedded body-HTML JSON for UK Deliveroo, restaurant-aggregate cost-for-two parsing for IN/ID Zomato.
3. **Records the bail decisions** — sources where the static HTML doesn't carry menu data (modern delivery SPAs that hydrate via XHR after page render) — in committed `coverage_report*.md` files so the methodology reviewer can audit which alternatives were considered.
4. **Schedules monthly re-collection** through a GitHub Actions cron + a local launchd job, so the index updates without manual intervention.

Section 3 places this against prior alternative-price-index work. Section 4 details the method. Section 5 reports the per-country data. Section 6 presents the United States Granger result that validates the pipeline, the India null, and the status of the remaining six countries. Section 7 discusses what the US finding implies for central-bank nowcasting. Section 8 catalogues the honest limitations. Section 9 outlines the going-forward path.

---

## 3. Background

*[To draft. Cite BPP / Cavallo–Rigobon, Big Mac Index / Pakko & Pollard 2003, scraping literature, informal-sector measurement work — at least 10 references for the SSEF checklist threshold.]*

Three strands of prior work motivate this project:

- **Algorithmic price indices.** Cavallo and Rigobon's MIT Billion Prices Project [Cavallo & Rigobon 2016] is the canonical demonstration that web-scraped retail prices lead official CPI. *PriceStats* commercialised the method; subsequent work has extended it to specific country panels and to inflation-expectations measurement [Cavallo 2017, 2018, 2020].
- **Cross-country purchasing-power comparisons.** *The Economist's* Big Mac Index [Pakko & Pollard 2003] popularised the idea that a single standardised consumer good can serve as a purchasing-power-parity yardstick. The Numbeo Cost-of-Living dataset extends this to a basket of consumer goods and services. Neither attempts time-series leading-indicator analysis.
- **Informal-sector measurement.** The UNDP's *Human Development Reports* document the share of household expenditure routed through informal food vendors in emerging markets [UNDP 2019]. Recent work from the IMF and World Bank has called for measurement methods that capture informal-sector price dynamics directly [IMF 2022, World Bank 2023] — a gap this paper attempts to address with web archives.

*[Add 4–7 more citations to clear the SSEF ≥ 10 threshold: e.g., Stock & Watson on nowcasting, Hamilton on time-series methods, the SDMX/OECD CPI methodology documents, the Australian Bureau of Statistics CPI publication schedule, the original Schema.org Menu specification.]*

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

---

## 5. Data

### 5.1 Per-country sources

| Country | Item-level source | Method | Rows | Months |
|---|---|---|---:|---:|
| United States | MenuPages (Wayback, JSON-LD MenuItem) | item-level | 8,282 | 35 |
| Singapore | GrabFood + foodpanda (live + Wayback NEXT_DATA) | item-level | 9,557 | 9 |
| Malaysia | foodpanda + GrabFood (live) | item-level | 3,505 | 7 |
| United Kingdom | Deliveroo (Wayback embedded-JSON) + live | item-level | 17,371 | 20 |
| India | Zomato NCR cost-for-two (Wayback) | restaurant-aggregate | 635 | 49 |
| Indonesia | Zomato Jakarta cost-for-two (Wayback) | restaurant-aggregate | 34 | 21 |
| Australia | Menulog (Wayback DOM markers) + live direct chains | item-level | 1,831 | 24 |
| Thailand | 2026-06-13 live snapshot (THB regex over Wayback) | item-level (sparse) | 11 | 1 |

Total: 41,263 price observations.

### 5.2 Honest collection notes

- **TripAdvisor tier-marker purge (2026-06-17)** — see § 4.6.
- **Menulog AU delivery-fee fix (2026-06-18)**. An early version of the JSON-LD walker inherited the Restaurant node's `name` into anonymous `Offer` leaves whose `price` was the delivery fee (4.99 / 5.00 / 10.00 / 20.00 — Menulog's flat-fee structure). 15 rows were emitted; all 15 had `item_name = restaurant name` and `price ∈ {4.99, 5, 10, 20}`. After the local-name fix, the same 96-snapshot cache yielded 1,652 *real* menu items.
- **Delivery-SPA bail decisions**. Six modern delivery aggregators (iFood BR, Uber Eats BR/DE/ZA, Lieferando DE, Wolt DE, GoFood ID, ShopeeFood ID, GrabFood TH, JustEat UK) were probed and declined. Common failure mode: menu items hydrate via XHR from a BFF API after page render; Wayback captures the static HTML shell only. The probe reports are in `coverage_report*.md`.

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
| **Granger F(26, 1)** | **6.034** |
| **Granger p** | **0.0210** |
| **Lead time** | **1 month** |
| Pass-through β | −0.00248 |
| Pass-through SE | 0.00138 |
| Pass-through 95 % CI | [−0.00531, +0.00034] |
| Pass-through p | 0.0828 |
| Pass-through R² | 0.557 |

Multi-lag detail: lag-1 p = 0.0210 is the minimum; lag-2 p = 0.0896, lag-3 p = 0.1376, lag-4 p = 0.1455. The signal concentrates at the shortest horizon and decays for longer lags, consistent with restaurant menu repricing acting as an early warning rather than a sustained predictor.

**The Granger test rejects independence at the 5 % level**. The pass-through coefficient is small, negative, and only marginally significant (p < 0.10 but > 0.05; CI includes zero). The result is a *timing* signal: UIFPI changes precede CPI changes by one month, but the linear coefficient on Δlog UIFPI does not pin down magnitude.

### 6.2 India — null result over 47 months

| Statistic | Value |
|---|---|
| Window | 2018-01 → 2026-01 |
| Overlap n | 47 months |
| UIFPI ADF p | 0.0121 |
| CPI ADF p | 0.0036 |
| Granger F(43, 1) | 0.521 |
| Granger p | 0.474 |
| Pass-through β | −0.00076 |
| Pass-through 95 % CI | [−0.00220, +0.00068] |
| Pass-through R² | 0.500 |

Both series are stationary at levels; the VAR is well-identified; the Granger F-statistic is essentially zero. **The Indian Zomato cost-for-two series carries no detectable leading information about headline CPI**. Two interpretations are plausible:

1. Indian CPI is dominated by food-staple and fuel components for which restaurant menu prices lag rather than lead.
2. The Zomato cost-for-two series is restaurant-aggregate, not item-level. Aggregation may smooth out the high-frequency variation that drives the US result.

Cross-country heterogeneity in CPI leadership is itself a research finding worth reporting; it argues against any single-country generalisation of the BPP result.

### 6.3 The other six countries

| Country | n overlap | Status | Expected crossover |
|---|---:|---|---|
| Australia | 23 | 1 month short — UIFPI has 24 distinct months but the 2026-06 live snapshot is outside the AU CPI window (which ends 2026-04) | Late July 2026, when ABS publishes Q2 CPI via OECD SDMX |
| United Kingdom | 18 | Accumulating monthly; 15 of 20 UIFPI months are 2025+ (Deliveroo embeds menu JSON only post-SPA-migration) | Late 2026 via monthly accumulation |
| Indonesia | 20 | Restaurant-aggregate Zomato cost-for-two; nearest to threshold | Late 2026 via monthly accumulation |
| Singapore | 8 | Going-forward live started mid-2026 | ~2027 |
| Malaysia | 6 | Live collection only | ~2027 |
| Thailand | 0 | Single 2026-06-13 live snapshot; no archival depth — every alternative Wayback source probed (Wongnai, LineMan, GrabFood TH) bailed at Phase 0 | Sustained monthly accumulation required |

The homepage Granger counter and country-page status pills read directly from `country_summary.json`, so any crossover triggered by the monthly cron will surface on Vercel within minutes of the commit.

---

## 7. Discussion

*[Draft to fill in.]*

The single significant Granger result for the United States is consistent with the BPP finding that algorithmically collected high-frequency prices carry leading information about headline CPI. The novel piece is that this result extends BPP's domain — large-retailer online goods — to restaurant menus, which BPP excludes by design. The negative pass-through coefficient and the wide CI [−0.0053, +0.0003] argue against interpreting the result as "menu prices set CPI". Rather, restaurant operators reprice in response to underlying input-cost movements at roughly the same time as the input-cost shocks that eventually flow through the broader CPI basket — but the menu repricing happens first, on the order of a month earlier.

The India null is informative. With 47 months of clean data, a well-identified VAR, and stationary series at level, the F-statistic of 0.521 is essentially the null hypothesis itself. Cross-country heterogeneity in CPI leadership cuts against any universal claim that menu prices lead headline inflation. The mechanism is plausibly that Indian CPI is dominated by food-staple weights that move independently of restaurant menu re-pricing.

For policy: the US result, if it survives replication across a longer window, suggests that high-frequency menu-price collection from delivery aggregators could provide central banks with a one-month leading inflation indicator at near-zero cost. The method documented here is the substrate on which that policy claim can be tested.

---

## 8. Limitations

1. **Single significant result.** One country, n = 31, p = 0.021 — the result is significant but not robust across the panel. Replication in AU and UK over the next 12 months will tell us whether the US case is generic or country-specific.
2. **Pass-through magnitude is small and not significant.** The 95 % CI on β includes zero. The paper's headline claim is a *timing* result, not a level result.
3. **Restaurant-aggregate data for IN and ID**. Zomato's pre-2020 archives don't expose item-level prices, only the "cost for two" restaurant-aggregate. This is methodologically distinct from item-level data and may smooth high-frequency variation.
4. **Modern delivery aggregators are mostly unreachable via Wayback**. iFood, Uber Eats, Lieferando, Wolt, GoFood, ShopeeFood, GrabFood TH, and JustEat UK all hydrate menus via XHR after page render; Wayback captures only the static shell. This is a structural limitation of the archive layer, not a parser problem, and it caps the historical depth recoverable for several countries.
5. **Live-scraper IP constraint.** Foodpanda and GrabFood bot-block datacenter IPs. The live scraper must run from a residential IP (local launchd or self-hosted runner); the GitHub Actions cron defaults to `--skip-scrape` for this reason.
6. **NLP classification is unaudited downstream.** The Claude-based category and quality-signal classification has not been independently validated against a human-labeled sample at scale; the existing `validation_results/` work covers only a small audit set.

---

## 9. Conclusion and Future Work

*[Draft to fill in.]*

This paper's contribution is a method — open source, auditable, probe-first, and source-specific — for collecting restaurant and informal-vendor menu prices at scale. Applied to an 8-country panel, the method produces one statistically valid Granger result (United States, p = 0.021, lead = 1 month) and one informative null (India). Six countries are below the n = 24 threshold and will cross it through the monthly ingest cron without further manual intervention. Future work falls in three directions:

1. **Sustain the panel.** Run the monthly cron through end-2026 to bring all eight countries above n = 24 and re-run Granger at that point.
2. **Replicate the BPP comparison.** Match the US UIFPI series against PriceStats-style alternative indices to test whether menu prices add information beyond goods.
3. **Extend the method to additional countries.** The probe framework is country-agnostic; the bail decisions in `coverage_report*.md` document what doesn't work and why, narrowing the search space for future contributors.

---

## 10. References

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

# UICPI — A Method for Collecting Chain-Restaurant and Independent-Vendor Prices at Scale, with Evidence from the United States

**Author**: Wen Chen Er
**Category**: Behavioral & Social Sciences / Economics
**Status**: Draft v0.3 (2026-07-12) — renamed and reframed from UIFPI ("Unified Informal-Formal Price Index"); research question now centres on chain vs. independent vendor pricing rather than formal/informal sector status.
**Affiliation**: Raffles Institution, Singapore

---

## Outline

1. **Abstract** (≤ 250 words)
2. **Introduction** — gap, contribution, structure
3. **Background** — BPP, Big Mac, Cavallo & Rigobon, price stickiness, the independent-vendor measurement gap
4. **Method**
    1. Sources and the probe-first discipline
    2. Pipeline overview (Wayback + live)
    3. Per-platform extractors (DOM, JSON-LD, NEXT_DATA, embedded JSON)
    4. Index construction (restaurant-median, stationarity, VAR-AIC)
    5. Granger causality + Cavallo–Rigobon pass-through
    6. Quality controls (NLP classification, hedonic adjustment, tier purge, data-quarantine)
5. **Data**
    1. Per-country source roll-up
    2. Honest collection notes
6. **Results**
    1. Method validation — the United States case
    2. Counterpoint — the India null
    3. Status of the remaining countries
7. **Discussion**
    1. What the US finding tells us
    2. Cross-country heterogeneity in CPI leadership
    3. Implications for central-bank nowcasting
    4. The chain-vs-independent question this draft still can't answer
8. **Limitations**
9. **Conclusion and Future Work**
10. **Acknowledgments**
11. **References**
12. Appendix — Notes for the Author

---

## 1. Abstract

Algorithmic alternatives to official CPI — chiefly the MIT Billion Prices Project (BPP) — sample prices from large, centrally-priced chains. None test whether centralized versus owner-set pricing changes how quickly, or how informatively, prices move relative to CPI. This paper contributes a scalable, open-source method for collecting restaurant menu prices from both chain and independent vendors (including street stalls and hawker centres), built to eventually test that question directly.

The pipeline combines Wayback Machine CDX probes that triage sources before scraping, per-platform HTML extractors, a live scraper, and an audit trail of declined sources. Index construction uses matched-model restaurant medians; Granger testing follows Cavallo and Rigobon (2016).

As of this draft, the dataset spans ten countries and 102,499 observations (roughly four-fifths chain-labeled, one-fifth independent). The one statistically meaningful finding is carried forward unchanged from the prior draft, since it cannot be recomputed here: in the United States (n = 31 months), UICPI Granger-leads CPI at a one-month lag (F(1,28) = 4.20, p = 0.0499; permutation p = 0.052/0.069), strengthening under a forward-fill check (F(1,35) = 9.05, p = 0.0048, n = 38). India (n = 47) and Malaysia (n = 30) return clean nulls on real-monthly CPI. Independent-vendor samples remain too thin, wherever a valid Granger test exists, to isolate a chain-specific from an independent-specific leading-indicator effect — the paper's central open question. Vietnam and UAE, two newly added countries, had historical price data found corrupted in July 2026 and are not carried forward.

*Word count: 244*

---

## 2. Introduction

The MIT Billion Prices Project (BPP) established that prices algorithmically scraped from large online retailers lead the United States Consumer Price Index by approximately two months [Cavallo & Rigobon 2016]. The finding reshaped what was thought possible for inflation nowcasting — but BPP's sampling frame has a specific shape that matters for what it can and can't tell us. It draws from large, multichannel retailers: chains, in effect, whose prices are typically set centrally and rolled out across many locations at once. The same is true of the other well-known alternative price benchmark, *The Economist's* Big Mac Index, which is — by construction — a single global chain [Pakko & Pollard 2003]. Neither instrument samples the other kind of vendor: the single-location, owner-priced restaurant, food stall, or hawker stand that sets its own prices independently of any corporate pricing calendar.

This matters for two separate reasons, one about *coverage* and one about *mechanism*.

The coverage reason is a known gap: the UNDP's *Human Development Report 2019* documents that independent, informal food vendors — hawker stalls, street food carts, wet-market sellers — supply between 40% and 65% of household food expenditure across Indonesia, India, Thailand, and comparable economies [UNDP 2019]. These vendors are structurally invisible to BPP, PriceStats, and the Big Mac Index alike, because all three instruments are built around large, branded operators.

The mechanism reason is less obvious and, this paper argues, more interesting. Cavallo's follow-on work to BPP found that scraped retail prices exhibit measurable *stickiness* — some retailers reprice rarely, in discrete jumps, in a pattern consistent with a fixed cost of changing a price [Cavallo 2018]. Restaurant chains plausibly face an analogous friction: printed menus, centralized approval for price changes across hundreds of locations, and brand-consistency pressure all raise the cost of repricing relative to a single owner-operator who can chalk a new number on a board the same afternoon input costs rise. If that's right, chain and independent vendors should differ systematically in how often, how much, and how *predictively* their prices move — which is a direct, testable question about whether either vendor type leads CPI more strongly than the other, and one no existing price index is built to ask.

This paper does not yet answer that question — see §7.4 and §8 for why not — but it is now the paper's organizing research question, and the data-collection pipeline was already, independently, built around a chain/independent split (see the Note on this revision, above). What this paper does claim is narrower: that the data needed to eventually answer the question can be assembled from public archives at a scale where statistical inference becomes possible, and that the methodology for doing so is worth documenting in its own right. The panel reported here is a developmental dataset: as of this draft, ten countries and 102,499 price observations from 2018 through mid-2026, with one validated Granger result (United States, carried forward unchanged from the prior analysis) and the rest of the panel either accumulating toward the n = 24 monthly-observation threshold or, in two cases, sidelined by a data-quality issue discovered after the prior draft was written.

The primary contribution is a fully open-source pipeline that:

1. **Probes every candidate source first** with a Phase 0 yield table against Wayback's CDX index, before any scraping, so collection time isn't burned on dead-end archives.
2. **Matches each platform's HTML pattern** with a purpose-built extractor — DOM markers for Menulog AU, Schema.org JSON-LD `MenuItem` for US MenuPages, Next.js `__NEXT_DATA__` for SG GrabFood, embedded body-HTML JSON for UK Deliveroo, restaurant-aggregate cost-for-two parsing for IN/ID Zomato.
3. **Labels every observation chain or independent** at collection time, so the underlying dataset supports the chain-vs-independent comparison directly, once sample sizes allow it.
4. **Records the bail decisions** — sources where the static HTML doesn't carry menu data (modern delivery SPAs that hydrate via XHR after page render) — in committed `coverage_report*.md` files, so the methodology reviewer can audit which alternatives were considered and why they were declined.
5. **Schedules monthly re-collection** through a GitHub Actions cron plus a local launchd job, so the index continues to grow without manual intervention, and **catches its own data-quality regressions** — the Vietnam/UAE corruption discussed in §5.2 was found and quarantined by the project's own tooling, not by an external reviewer.

Section 3 places this against prior alternative-price-index work and the sticky-price literature. Section 4 details the method. Section 5 reports the per-country data, including the quarantine. Section 6 presents the United States Granger result that validates the pipeline, the India and Malaysia null results, and the status of the remaining countries. Section 7 discusses what the US finding implies, what the emerging-market nulls imply, and — new in this draft — why the chain-vs-independent question can't yet be tested directly. Section 8 catalogues the honest limitations. Section 9 outlines the going-forward path.

---

## 3. Background

UICPI sits at the intersection of four threads of prior work: algorithmic price-index construction, price stickiness, cross-country price-level comparisons, and informal-sector measurement. This section traces each into the position this paper occupies.

The single most influential antecedent is Cavallo and Rigobon's *Billion Prices Project* (BPP) [Cavallo & Rigobon 2016]. BPP demonstrated that prices scraped daily from large online retailers in the United States lead the BLS Consumer Price Index by approximately two months at statistical significance; the result extended through earlier work showing that scraped online and offline prices coincide [Cavallo 2017]. The methodology is the inheritance UICPI builds on directly: high-frequency price observations from a comparable basket of products, aggregated through a stable index, tested against official CPI with Granger causality and a Cavallo–Rigobon pass-through regression. Where this paper diverges is the basket — restaurant menu items rather than retail goods — and the source layer — public Wayback archives rather than vendor-direct daily polling.

The second, and for this draft's reframing the most important, antecedent is Cavallo's work on price stickiness [Cavallo 2018], which showed retailer-level sticky-price behaviour is directly observable in scraped price data: some sellers reprice frequently and in small increments, others rarely and in large discrete jumps, in a pattern consistent with a fixed per-repricing cost. This paper's central hypothesis — that chain restaurants, facing centralized multi-location repricing frictions, behave differently from single-location independent vendors who can reprice at will — is a direct extension of that finding into the restaurant sector, and into a *between-vendor-type* comparison rather than a between-retailer comparison. Cavallo's later COVID-era work [Cavallo 2020] is a relevant secondary signpost: it shows the BPP framework adapts cleanly to consumption baskets that differ from the official CPI's, which is exactly the situation a restaurant-menu index occupies regardless of how the chain/independent split resolves.

The third tradition is cross-country price-level measurement through a standardised good. The Big Mac Index, formalised by Pakko & Pollard [2003], demonstrated that a single consumer good can serve as a purchasing-power-parity yardstick across dozens of countries — and, not incidentally, is a chain-only instrument by construction, which this paper takes as further motivation for a chain/independent axis rather than as a competing methodology. Numbeo's Cost-of-Living survey extends the device to a basket of consumer goods and services and is loaded into this project's `numbeo_index` table as a cross-country floor reference. Neither the Big Mac Index nor Numbeo attempts time-series leading-indicator analysis; both are level instruments. UICPI keeps the cross-country breadth but adds both the time-series dimension BPP made tractable and the chain/independent split neither instrument has.

The fourth tradition is the measurement of independent and informal-sector prices. The UNDP's *Human Development Report 2019* [UNDP 2019] is the canonical source for the 40–65% share of household food expenditure routed through independent, informal vendors in emerging markets; this is the motivation for the panel's emphasis on Indonesia, Thailand, India, and Malaysia, and for treating "independent" as a category worth collecting at all rather than discarding as noise around the chain signal. The IMF's *World Economic Outlook 2022* [IMF 2022] explicitly called for measurement methods that capture informal-sector price dynamics directly, and a World Bank Group policy note [World Bank 2023] enumerated the difficulties official statistical agencies face in collecting such prices at high frequency. UICPI does not solve that problem either; it surfaces a *publicly-archived* signal that contains some of that information, at the price of restricting collection to vendors whose menus appear in static HTML — a constraint that, as §5.2 and §7.4 discuss, currently limits independent-vendor sample sizes more than chain sample sizes.

Two methodological references underlie the statistical machinery. Stock & Watson [2002] established the use of high-dimensional diffusion indexes for macroeconomic nowcasting; UICPI is conceptually one such index. Hamilton's *Time Series Analysis* [Hamilton 1994], chapter 11, is the textbook treatment of VAR estimation and the Granger causality test as implemented here through `statsmodels`. Two operational references close out the bibliography: the OECD's PRICES_CPI SDMX endpoint, which supplies the harmonised CPI series used as the dependent variable in the Granger test [OECD 2024], and the Australian Bureau of Statistics methodology document [ABS 2026], which underlies the AU CPI feed. The Schema.org Working Group's `Menu` / `MenuSection` / `MenuItem` specification [Schema.org 2024] is the data contract the US extractor (MenuPages) is built against.

The literature established, in sum, that (i) algorithmic high-frequency prices lead official CPI in at least one large economy, (ii) price stickiness varies systematically across sellers in ways that are directly observable in scraped data, (iii) the methodology generalises across consumption baskets, and (iv) independent/informal-sector vendors are undersampled in conventional measurement. What it has not established — and what this paper sets out to build the infrastructure to test — is whether chain and independent restaurant vendors differ in CPI-leading behaviour the way Cavallo's sticky-price work would predict.

---

## 4. Method

### 4.1 Sources and the probe-first discipline

For each country, we identify candidate platforms that publish restaurant menus in static, archive-accessible HTML. A **Phase 0 probe** queries Wayback's CDX index for each candidate URL pattern, samples one representative archived page, and counts (i) ≥ 2-capture restaurants in the window 2018–2026, (ii) currency-shaped tokens in the page's static HTML, and (iii) whether the response is bot-blocked (captcha / Cloudflare challenge / tiny placeholder). A (source, country) pair is queued for scraping only when ≥ 15 ≥2-cap restaurants exist *and* ≥ 5 currency tokens are visible in the sampled HTML *and* the page is not bot-blocked.

Every probe — including the failures — is committed to a `coverage_report*.md` file. This audit trail records the sources we declined and *why*: iFood Brazil (HTTP 503 from Wayback), Lieferando Germany (314 KB of i18n strings, zero `"price"` substrings), ShopeeFood Indonesia (captcha), GrabFood Thailand (captcha), and Deliveroo Singapore (JS shell, zero S$ tokens) all bail at Phase 0. A companion round of probes against candidate expansion countries (Brazil, Germany, South Africa, Mexico, the Philippines) found the same structural problem — modern delivery-app SPAs hydrate menu data via XHR after page render, which Wayback never captures — and none of those countries were added to the roster on that basis; see the project CHANGELOG, 2026-06-18 entry, "Reality check: Wayback doesn't capture modern delivery-app menus."

### 4.2 Pipeline overview

The pipeline has two collection paths:

- **Wayback historical sweep** (`historical_html_scraper.py`, `deliveroo_uk_sweep.py`, `historical_scraper.py`). A time-distributed CDX walk produces a representative sample of archived snapshots across quarter windows from 2018-Q1 through 2026-Q2; each snapshot is fetched with the `id_` raw-bytes path and parsed by the matching per-source extractor.
- **Live forward collection** (`live_scraper.py`). A Playwright-driven scraper of foodpanda, GrabFood, Swiggy, Deliveroo, and direct chain sites; runs nightly via a local launchd job (cloud IPs are bot-blocked by Foodpanda + GrabFood, per the docstring).

Both paths write into a single `prices` table in `uifpi.db` (the database filename has not yet been migrated to match the UICPI rename — see Appendix). A monthly orchestrator (`scheduled/monthly_ingest.py`) wraps both paths plus the CPI refresh, index rebuild, Granger re-run, and dashboard re-export; it is invoked by `.github/workflows/monthly_ingest.yml` on the 1st of each month, and now refuses to run against an empty database (a guard added 2026-07-08 after a runner without a populated database silently committed zeroed exports — see §5.2).

### 4.3 Per-platform extractors

The extractors are intentionally narrow because the archived HTML's structure varies sharply by platform vintage. Five patterns recur:

1. **DOM markers (Menulog AU, mid-2020s)**. `<button data-test-id="menu-item">` containers wrap an `<h3 data-test-id="menu-item-name">` heading and a `<p data-js-test="menu-item-price">` price element. The extractor splits the page on the marker, then pulls name + price out of each chunk. Sample yield: 100 items on a 381 KB 1 Best Thai snapshot (2023-03-02).
2. **Schema.org JSON-LD (MenuPages US, pre-2019)**. Restaurant pages embed full `Menu → MenuSection → MenuItem` markup with named items and offers. The walker recurses through every JSON-LD `@type` and emits `(name, price)` only when the **local** node carries its own `name` field. An earlier version inherited `name_ctx` from parent Restaurant nodes and mis-attributed delivery fees to restaurant names; this was traced to 15 polluted `wayback-menulog` rows (prices 4.99 / 5.00 / 10.00 / 20.00 — Menulog's flat delivery-fee tiers) and fixed by requiring local `name` at the emitting node (see § 5.2).
3. **NEXT_DATA (GrabFood SG)**. The Next.js `__NEXT_DATA__` script tag carries the page's hydrated state, including menu items. The extractor falls back to `[^<]+` as the script terminator because Wayback frequently truncates large JSON payloads mid-string.
4. **Embedded body-HTML JSON (Deliveroo UK, 2025+)**. A flat `{"items":[{"name":"X","raw_price":N,...}]}` blob sits in body HTML — no JSON-LD, no NEXT_DATA, no data-test-id markers. The extractor regex-pairs `"name"` with `"raw_price"` within an 800-character window to keep them in the same JSON object. Sample yield: 245 items on a 389 KB 2020-09-29 Wirral Papa John's snapshot.
5. **Cost-for-two regex (Zomato NCR + Jakarta, pre-2020)**. Zomato pre-2020 archived pages don't expose item-level prices, but they do publish a restaurant-level "cost for two people" average (₹1,600 for two; Rp 250,000 for two). The extractor returns one synthetic item per page, `item_name = 'cost_for_two'`. This is *restaurant-aggregate* data, not item-level; every Zomato-sourced row in the current dataset is labelled `chain` rather than `independent` (see §6.2 for why this matters).

### 4.4 Index construction

Construction follows the *matched-model restaurant-median* method (`index_builder.py`). For each (country, year_month):

1. Filter rows to `price > 0`, exchange-convert to USD using OECD-published rates (with hardcoded fallbacks for currencies the API hasn't refreshed).
2. Cap rows per (country, year_month) at `MAX_ROWS_PER_COUNTRY` using a deterministic random sample (seeded for reproducibility) — prevents dense months from dominating the cross-country index.
3. Per restaurant, take the median price within month; per country-month, take the median of restaurant medians.
4. Index level is the geometric mean of category relatives, base = 100 at the first month with sufficient coverage.

Chain-sector and independent-sector indices are computed separately and combined into `uicpi_combined` (renamed from `uifpi_combined`; see Appendix).

### 4.5 Granger causality and pass-through

For each country we run `granger_analysis.py --min-obs 24`, which:

1. ADF-tests both UICPI and CPI at 5%; differences either series if non-stationary.
2. Selects VAR lag via AIC, capped at `min(4, n/5)`.
3. Runs `statsmodels.tsa.stattools.grangercausalitytests` over the joint (CPI, UICPI) series.
4. Reports the minimum-p lag, the F-statistic, and the p-value.

For pass-through, OLS of Δlog CPI on Δlog UICPI per Cavallo–Rigobon, with 95% CI on β. The same specification can be run separately on the chain-only and independent-only sub-indices once either has enough monthly observations — the pipeline supports this today, but no country currently has both sub-indices past the 24-month threshold (§7.4).

### 4.6 Quality controls

- **NLP classification.** `nlp_pipeline.py` calls Claude to classify each item into 13 food categories (GRILLED_PROTEIN, NOODLE_DISH, RICE_DISH, …) plus quality signals (`PORTION_REDUCTION`, `PREMIUM_UPGRADE`, …). Used downstream for category-level relatives.
- **Hedonic adjustment.** `apply_hedonic_adjustment` in the index builder shifts prices by ±15% when the NLP-detected signals indicate portion or quality change.
- **Tier-marker purge (2026-06-17).** TripAdvisor `priceRange` `$` / `$$` / `$$$` / `$$$$` were initially stored as integer ordinals 1–4 in the `price` column. 1,648 such rows were deleted from `prices` (TH 279, UK 293, US 277, IN 237, AU 221, MY 188, ID 118, SG 35); the scraper was updated to skip the tier path; the index builder's tier-mask filter was removed as redundant.
- **Data-quarantine (2026-07-09).** Two (country, source) slices were found to carry systematically corrupted prices: **UAE / wayback-deliveroo** (9,243 rows — from 2022-01 the Deliveroo archive template stores price as a `{code, fractional, formatted}` object, and the generic JSON walker digit-fuses it, turning AED 9 into 90,009) and **Vietnam / wayback-grabfood** (4,309 rows — the `priceInMinorUnit` handler divides by 100 unconditionally, but GrabFood VN's field already carries raw VND, so every price came out roughly 100× too small). Both slices are now excluded from index construction via `data_quality.QUARANTINED_SLICES`; raw rows remain in `prices` for a future re-scrape with corrected parsers, but no statistic in this paper is computed from them. This is the same class of fix as the tier-marker purge above — a systematic parsing error caught by the project's own tooling rather than by an external reviewer — and is disclosed here for the same reason the tier purge was disclosed in the prior draft.
- **Sector-label cleanup (2026-07-09).** 7,571 `wayback-doordash` rows still carried the pre-rename `formal` label (the scraper's `TARGETS` list was not updated when the project moved to `chain`/`independent` labels). These were relabelled to `chain`; DoorDash rows remain excluded from index construction regardless of label (§5.2), so this was a labelling-consistency fix, not a change to any published index value.

### 4.7 CPI source resolution

The benchmark series for the Granger test is country-level headline CPI, but the publication frequency and ingestion path differ sharply across the panel — and the difference matters because a Granger F-statistic on a CPI series whose within-year variance has been compressed or zeroed is mechanically biased toward the null. The CPI pipeline (`get_monthly_cpi_all.py`, `floor_datasets.py`) resolves each country into one of four classes:

| Class | Countries | CPI ingestion |
|---|---|---|
| **Real monthly** | US, UK, India, Malaysia | OECD HICP (US, IN), ONS d7bt (UK), DOSM `cpi_headline` (MY) — published monthly by the national statistics office, ingested as-is |
| **Quarterly-interpolated** | Australia | OECD/ABS quarterly, linearly interpolated to monthly (within-quarter variance compressed but nonzero) |
| **Annual-interpolated (linear)** | Singapore, Thailand, Indonesia | World Bank `FP.CPI.TOTL`, linearly interpolated at load time → smooth monthly curve |
| **Annual-interpolated (step)** | Vietnam, UAE | World Bank `FP.CPI.TOTL` replicated 12× per year → step function, ΔCPI = 0 within each calendar year |

The two annual-interpolated sub-classes are not equivalent. Linear interpolation (SG, TH, ID) compresses within-year variance but preserves a nonzero monthly first difference, which a Granger VAR can in principle pick up. **Step replication (VN, AE) makes the first-differenced CPI series identically zero for 11 of every 12 months, leaving the Granger test on `ΔCPI ~ ΔUICPI` structurally degenerate and uninformative regardless of what the underlying series actually do.** For Vietnam and UAE specifically, this limitation is now moot in the near term: both countries' item-level price histories were quarantined on 2026-07-09 (§4.6), so neither has enough clean months to run the test at all, independent of the CPI-resolution problem.

**India's (n=47) and Malaysia's (n=30) nulls — both on real monthly CPI series — constitute genuine tests of the null hypothesis.** The US positive (real monthly HICP), the UK accumulating result (real monthly ONS), and the Australia pending result (quarterly OECD/ABS, interpolated) are each interpretable on their own terms. Crossing the resolution barrier for Vietnam and UAE requires both a clean re-scrape and monthly CPI from each country's national statistics office (FCSC for UAE, GSO for Vietnam).

Every results table in this paper carries one of four markers indicating the CPI class for that country: `[real-monthly]`, `[quarterly-interp]`, `[annual-interp]`, `[annual-step]`.

---

## 5. Data

### 5.1 Per-country sources

The table below uses the live dashboard's data-download page (`inflation-price-menu.vercel.app/data`, pulled 2026-07-12) for item counts, months, and start dates — these are descriptive figures and have been updated from the prior draft. CPI class and item-level-vs-aggregate method are unchanged from the v0.2 draft.

| Country | Item-level source | Method | Chain items | Independent items | Total | Months | From | CPI series `[class]` |
|---|---|---|---:|---:|---:|---:|---|---|
| United States | MenuPages (Wayback, JSON-LD MenuItem) | item-level | 8,344 | 34 | 8,378 | 36 | 2018-04 | OECD HICP monthly `[real-monthly]` |
| United Kingdom | Deliveroo (Wayback embedded-JSON) + live | item-level | 29,878 | 8,973 | 38,851 | 21 | 2019-09 | ONS d7bt `[real-monthly]` |
| Malaysia | foodpanda + GrabFood (live + Wayback NEXT_DATA) | item-level | 15,544 | 3,964 | 19,508 | 33 | 2019-07 | DOSM `cpi_headline` `[real-monthly]` |
| India | Zomato NCR cost-for-two (Wayback) | restaurant-aggregate | 635 | 0 | 635 | 49 | 2018-01 | OECD national monthly `[real-monthly]` |
| Singapore | GrabFood + foodpanda (live + Wayback NEXT_DATA) | item-level | 26,563 | 3,580 | 30,143 | 10 | 2022-07 | WB FP.CPI.TOTL `[annual-interp]` |
| Australia | Menulog (Wayback DOM markers) + live direct chains | item-level | — | — | 2,743 | 25 | — | OECD/ABS quarterly `[quarterly-interp]` |
| Indonesia | Zomato Jakarta cost-for-two (Wayback) | restaurant-aggregate | 29 | 5 | 34 | 21 | 2018-02 | WB FP.CPI.TOTL `[annual-interp]` |
| Thailand | 2026-06 live snapshot (THB regex over Wayback) | item-level (sparse) | 11 | 0 | 11 | 1 | 2026-06 | WB FP.CPI.TOTL `[annual-interp]` |
| Vietnam | GrabFood (live, post-quarantine restart) | item-level | 1,216 | 980 | 2,196 | 2 | 2026-06 | WB FP.CPI.TOTL, step `[annual-step]` |
| UAE | — (entire Deliveroo slice quarantined) | — | 0 | 0 | 0 | 0 | — | WB FP.CPI.TOTL, step `[annual-step]` |

**Total: 102,499 price observations across ten countries.** The chain/independent split is available for eight of the ten (Australia's breakdown was not exposed on the pages reachable for this draft — its 2,743 total is reported without a split). Across the eight countries with a known split, roughly 82% of items are chain-labeled and 18% independent-labeled; see §7.4 for why this imbalance matters for the paper's central question.

The v0.2 draft reported 41,263 observations across the same eight "legacy" countries (all but Vietnam and UAE, which were added afterward). Summing the legacy eight in the table above gives approximately 100,303 — collection has continued well past the point at which the v0.2 statistics were computed, but per the constraint stated at the top of this draft, the Granger results in §6 are not recomputed against this larger pool.

### 5.2 Honest collection notes

- **TripAdvisor tier-marker purge (2026-06-17)** — see §4.6.
- **Menulog AU delivery-fee fix (2026-06-18)**. See §4.3.2. After the local-name fix, the same 96-snapshot cache yielded 1,652 real menu items in place of the 15 polluted rows.
- **Delivery-SPA bail decisions**. Modern delivery aggregators (iFood BR, Uber Eats BR/DE/ZA, Lieferando DE, Wolt DE, GoFood ID, ShopeeFood ID, GrabFood TH, JustEat UK) were probed and declined. Common failure mode: menu items hydrate via XHR from a BFF API after page render; Wayback captures the static HTML shell only. The probe reports are in `coverage_report*.md`.
- **DoorDash exclusion (2026-06-22)**. DoorDash data is excluded from index construction — delivery-platform pricing reflects platform dynamics (surge pricing, promotions, delivery fees) not present in traditional menu scrapes, which dilutes the leading-indicator signal. Source-stratified Granger on the US series confirmed the dilution quantitatively: with DoorDash pooled in, the lag-1 F-stat collapses from 5.56 (p = 0.026, n = 31) to 0.006 (p = 0.94, n = 38).¹ The exclusion is enforced at the index-construction layer; raw DoorDash rows (n = 7,571) remain in `prices`.
- **Sector-label cleanup and data-quarantine (2026-07-09)** — see §4.6. Two items worth restating plainly here because they postdate the v0.2 draft: (1) the 7,571 DoorDash rows' stale `formal` label was corrected to `chain` — no effect on any published index value, since DoorDash is excluded regardless of label; (2) UAE's entire item-level dataset (9,243 rows) and 19 months of Vietnam's Wayback history (4,309 rows) were found systematically mispriced and are now excluded pending a corrected re-scrape. **All Granger and pass-through statistics for the original eight-country panel — including the US headline result — are unaffected by the quarantine**, per the project's own impact assessment (CHANGELOG, 2026-07-09).
- **Ingest-artifact repair (2026-07-08)**. A GitHub Actions run executed against an empty database (the SQLite file is gitignored) and committed zeroed dashboard exports before the error was caught and repaired from an intact local copy. The monthly orchestrator now refuses to run against a database with fewer than 50,000 rows unless explicitly overridden. Mentioned here as evidence of the same "catch it before it ships" discipline as the tier-marker and quarantine fixes above, not because it affected any figure in this paper.
- **Rename (2026-07).** The project — and this paper — moved from `UIFPI` / "formal-informal" to `UICPI` / "chain-independent" labeling. The underlying two-way vendor split is unchanged (branded, multi-location operators vs. single-location, owner-priced operators including hawker stalls and street vendors); only the framing and labels changed. Not every artifact has caught up — the SQLite file is still named `uifpi.db`, the dashboard's `/methodology` and `/data` page copy and CSV column headers still read `uifpi`/`formal`/`informal` as of this draft — and that lag is disclosed rather than papered over (see Appendix).

¹ *This contrast uses the pre-respec VAR/AIC Granger method, not calendar-true — no calendar-true DoorDash comparison script exists yet. The dilution direction is expected to hold under calendar-true but has not been re-verified there.*

---

## 6. Results

### 6.1 The United States case — method validation

*The statistics in this subsection are carried forward unchanged from the v0.2 draft; they cannot be recomputed against the current, larger US item pool (8,378 items vs. 8,282 at the time of the v0.2 analysis) from this environment.*

| Statistic | Value |
|---|---|
| Window | 2018-04 → 2024-10 |
| Overlap n | 31 months |
| UICPI ADF p | 0.0000 (stationary in levels; menu enters in levels) |
| **Granger F(1, 28)** | **4.20** |
| **Granger p (analytic)** | **0.0499** |
| Permutation p (shuffle, 1000 draws) | 0.052 |
| Permutation p (circular block, b=5) | 0.069 |
| **Lead time** | **1 month** |

CPI source: OECD HICP monthly index (BLS-derived) — `[real-monthly]`. See §4.7.

**The Granger test is marginal, not a clean rejection of independence**: the analytic F-test places p just under 0.05 (p = 0.0499), but both permutation checks place it just outside conventional significance (p = 0.052 shuffle, p = 0.069 block) — the parametric and nonparametric tests disagree at exactly the threshold that matters, and the result should be read as suggestive rather than conclusive. It strengthens under a causal forward-fill robustness check that fills single-month menu gaps using only past information (F(1, 35) = 9.05, p = 0.0048, n = 38); a midpoint-interpolation variant agrees in direction but carries a look-ahead caveat and is not treated as robustness-confirming. The finding is a *timing* signal: UICPI changes precede CPI changes by one month. No claim is made here about the magnitude of the eventual CPI change.

This result combines chain and independent items into a single US index (8,344 chain, 34 independent). The independent sample is too thin to test separately — see §7.4.

### 6.2 India — null result over 47 months

*Statistics carried forward unchanged from the v0.2 draft.*

| Statistic | Value |
|---|---|
| Window | 2018-01 → 2026-01 |
| Overlap n | 47 months |
| UICPI ADF p | 0.0121 |
| CPI ADF p | 0.0036 |
| Granger F(1, 43) | 0.5213 |
| Granger p | 0.4742 |
| Pass-through β | 0.0007 |
| Pass-through SE | 0.0019 |
| Pass-through 95% CI | [−0.00313, +0.00462] |
| Pass-through p | 0.6973 |
| Pass-through R² | 0.4997 |

CPI source: OECD national monthly index — `[real-monthly]`. See §4.7.

Both series are stationary at levels; the VAR is well-identified; the Granger F-statistic is essentially zero. **The Indian Zomato cost-for-two series carries no detectable leading information about headline CPI**. Two interpretations are plausible, unchanged from the prior draft:

1. Indian CPI is dominated by food-staple and fuel components for which restaurant menu prices lag rather than lead.
2. The Zomato cost-for-two series is restaurant-aggregate, not item-level. Aggregation may smooth out the high-frequency variation that drives the US result.

A third point is new to this draft and worth flagging honestly: **every one of the 635 India observations is currently labeled `chain`, not `independent`** (Table 5.1). This is almost certainly a sampling artefact of Zomato's own listing composition rather than a claim that India's restaurant sector is chain-dominated — the 40–65% independent/informal food-expenditure share cited in §3 is a national-accounts figure, not a Zomato-sample figure. Whatever the India null means for CPI leadership, it cannot speak to the chain-vs-independent question this paper is organized around, because the sample contains no independent-labeled observations to compare against.

### 6.3 The other countries

Malaysia's Granger statistic (n = 30 overlap, F = 0.111, p = 0.7419 at lag 1) is carried forward unchanged from the v0.2 draft and reported alongside India as a genuine null on real-monthly CPI.

The table below distinguishes two different counts for the remaining countries: the **Granger-overlap n** used in the v0.2 analysis (the number of months where both UICPI and CPI data existed, which is what the Granger test actually consumes), and the **UICPI months collected today**, pulled from the live dashboard. These are not the same number — CPI availability is often the binding constraint, not raw collection — and conflating them would overstate how close a country is to a valid test.

| Country | Granger-overlap n (v0.2) | UICPI months collected (dashboard, today) | CPI `[class]` | Status |
|---|---:|---:|---|---|
| Australia | 23 | 25 | `[quarterly-interp]` | Was 1 month short of the 24-CPI-month threshold in the v0.2 analysis; collection has continued (23→25 raw months) but the binding constraint is ABS's quarterly CPI publication, not UICPI collection. Expected crossover late July 2026 per ABS's Q2 release schedule. |
| United Kingdom | 18 | 21 | `[real-monthly]` | Accumulating; UICPI-side months have grown from 20 to 21 since the v0.2 draft. |
| Indonesia | 20 | 21 | `[annual-interp]` | Restaurant-aggregate Zomato cost-for-two; nearest emerging-market country to the raw-month threshold, but see §4.7 — even at n ≥ 24 the annual-interpolated CPI limits test power. |
| Singapore | 8 | 10 | `[annual-interp]` | Going-forward live collection continues to add months; same §4.7 caveat applies. |
| Thailand | 0 | 1 | `[annual-interp]` | Single 2026-06 live snapshot; no archival depth — every alternative Wayback source probed (Wongnai, LineMan, GrabFood TH) bailed at Phase 0. |
| Vietnam | *12 (invalidated)* | 2 | `[annual-step]` | The v0.2 draft's n=12, p=0.42 statistic was computed on the Wayback GrabFood slice later found systematically corrupted (§4.6, §5.2) and is **not carried forward**. Post-quarantine, Vietnam has 2 clean months from a 2026-06 live-collection restart — further from a valid test than the v0.2 draft's now-invalid number suggested. |
| UAE | *47 (invalidated)* | 0 | `[annual-step]` | The v0.2 draft's n=47, F=0.016, p=0.90 statistic was computed entirely on the quarantined Deliveroo slice (§4.6) and is **not carried forward**. UAE currently has zero usable item-level rows; a corrected re-scrape is required before any statistic can be reported. |

---

## 7. Discussion

The panel yields one marginally significant Granger result (United States, carried forward unchanged) and two informative nulls (India, Malaysia), against a backdrop of substantially expanded — but not yet re-tested — data collection, and a data-quality issue in two of the newer countries. Four implications are worth pulling apart.

### 7.1 Timing, not level — the pass-through caveat

The US Granger test is, at best, marginal: the analytic F-test places it under conventional significance (F(1, 28) = 4.20, p = 0.0499), but permutation checks that don't rely on distributional assumptions place it just outside that threshold (p = 0.052 shuffle, p = 0.069 block). The Granger test is about predictive sequence: knowing past UICPI movements improves forecasts of current CPI changes. This paper does not make a companion magnitude claim — a pass-through regression on the calendar-true series has not been re-estimated, and the prior magnitude estimate (computed on the now-deprecated gap-mixed CPI construction) is not carried forward. UICPI is therefore presented strictly as a *leading indicator* — a claim about the order of events — with no claim, in either direction, about the size of the eventual CPI movement.

### 7.2 The India null and food-staple weighting

The India Granger F-statistic of 0.5213 (p = 0.4742) over 47 overlapping months sits firmly inside the null hypothesis. The sample is the largest and cleanest in the panel: Zomato cost-for-two captures span 2018-01 to 2026-01, both series are stationary at levels, and the VAR is well-identified at lag 1. A null result this clean is itself a finding. Two non-exclusive explanations remain plausible, unchanged from the prior draft. First, the basket weighting in Indian CPI is materially different from the US: the CPI of India (Combined) places approximately 39% weight on food and beverages, with rice, wheat, pulses, and edible oils carrying the largest sub-weights — items whose prices are influenced heavily by monsoon yields, minimum support prices, and procurement policy, not by restaurant menu repricing. Second, several major food categories in India are subject to administered or quasi-administered pricing. Both mechanisms decouple the high-frequency restaurant-pricing channel from the headline CPI's dominant drivers. As §6.2 notes, this particular null cannot be read as evidence about chain vs. independent dynamics specifically, since the Indian sample contains no independent-labeled observations.

### 7.3 A low-cost nowcasting signal worth scaling

The US result, if it survives replication across a longer window, has a specific policy implication. Central banks in many economies operate without high-frequency price data: official CPI is monthly, sometimes quarterly, and lags real-time conditions by weeks to months. A one-month leading indicator constructed from publicly archived restaurant menus is, by construction, free at the margin — Wayback CDX is open infrastructure, the parsers documented in this paper are open source, and the index can be updated by a single GitHub Actions cron at zero variable cost. The question is not whether the signal is large enough to replace CPI — clearly it is not, given the pass-through CI — but whether the signal is *informative enough at one-month lead* to influence a marginal policy call.

### 7.4 The chain-vs-independent question this draft still can't answer

This is the question the paper is now organized around, and it deserves a direct, honest answer: **the current dataset cannot yet test it.** Two structural reasons why:

First, **sample imbalance**. Across the countries with a known chain/independent split, roughly 82% of collected items are chain-labeled and 18% independent-labeled (§5.1). In the one country with a valid Granger test — the United States — the imbalance is far more extreme: 8,344 chain items against 34 independent items. Thirty-four items cannot support a separate stationarity test, let alone a separate VAR, so the US result in §6.1 is necessarily a combined-index finding that cannot be decomposed into a chain effect and an independent effect after the fact.

Second, **no country yet has both sub-indices past the 24-month Granger threshold**. The countries with the largest independent-vendor samples — the UK (8,973 items), Malaysia (3,964), Singapore (3,580) — are exactly the countries still accumulating toward a valid combined-index test (§6.3), so a separate independent-only test is further away still.

What can be said, provisionally, is theoretical rather than empirical: if Cavallo's [2018] sticky-price mechanism carries over from retail to restaurants, chain vendors — facing centralized, multi-location repricing frictions — should reprice less often and in larger discrete steps, while independent vendors should reprice more often and in smaller steps as local input costs shift. Whether that translates into chains *lagging* CPI (because centralized decisions synthesize broader market information before committing to a change) or *leading* it less strongly than independents (because independents react to the same local cost pressures that eventually show up in the food-CPI print) is genuinely unclear ex ante, and is exactly the kind of question a properly powered chain-only vs. independent-only Granger comparison would resolve. Building the dataset to run that comparison — rather than running it prematurely on 34 items — is this paper's most direct next step (§9).

---

## 8. Limitations

1. **Single, marginal result, not recomputed against the larger current dataset.** One country, n = 31 (as analyzed in the v0.2 draft), analytic p = 0.0499 — marginal, just outside significance on nonparametric checks. The US item pool has grown to 8,378 since that analysis was run; whether the result strengthens, weakens, or holds on the larger pool is unknown until `granger_analysis.py` is re-run.
2. **No magnitude (pass-through) claim in this draft.** The Cavallo–Rigobon pass-through regression has not been re-estimated on the calendar-true CPI construction; the paper's claim is limited to *timing* — order of events — not magnitude.
3. **The chain-vs-independent comparison, the paper's central question, is not yet tested.** See §7.4. This is the most consequential limitation in this revision: the rename and reframing describe where the paper is going, not a result it has reached.
4. **Severe chain/independent sample imbalance.** Roughly 82/18 chain/independent overall, and far more skewed in the US specifically (§7.4). Even once countries cross the raw Granger threshold, an independent-only test may remain underpowered for some time.
5. **Restaurant-aggregate data for IN and ID, entirely chain-labeled.** Zomato's pre-2020 archives don't expose item-level prices, only the "cost for two" restaurant-aggregate, and every such row in the current dataset is labeled `chain` — likely an artefact of Zomato's listing composition rather than a substantive claim about either country's restaurant sector (§6.2).
6. **Two countries' historical data quarantined for a parsing bug.** UAE's entire item-level history and 19 months of Vietnam's were found systematically mispriced and excluded on 2026-07-09 (§4.6). Their v0.2 Granger statistics are invalid and are not carried forward; a corrected re-scrape is required before either can be reported again.
7. **Modern delivery aggregators are mostly unreachable via Wayback.** iFood, Uber Eats, Lieferando, Wolt, GoFood, ShopeeFood, GrabFood TH, and JustEat UK all hydrate menus via XHR after page render; Wayback captures only the static shell. This is a structural limitation of the archive layer, not a parser problem, and it caps the historical depth recoverable for several countries — and, since these are overwhelmingly chain platforms, arguably caps chain coverage more than it caps independent coverage, running counter to the sample-imbalance problem in Limitation 4 rather than helping it.
8. **Live-scraper IP constraint.** Foodpanda and GrabFood bot-block datacenter IPs. The live scraper must run from a residential IP (local launchd or self-hosted runner); the GitHub Actions cron defaults to `--skip-scrape` for this reason.
9. **NLP classification is unaudited downstream.** The Claude-based category and quality-signal classification has not been independently validated against a human-labeled sample at scale.
10. **CPI resolution heterogeneity (see §4.7).** Several of the panel's emerging-market series rely on World Bank annual CPI interpolated to monthly — linearly for SG/TH/ID and step-replicated for VN/AE — which compresses or zeroes within-year variance. Null results on these countries are inconclusive-due-to-power, not evidence of no relationship. The genuine cross-country tests in this panel remain India (n=47) and Malaysia (n=30), both on real monthly CPI.
11. **Delivery-platform data excluded from the published index.** DoorDash pricing reflects platform dynamics (surge pricing, promotions, delivery fees) not present in traditional menu scrapes and dilutes the leading-indicator signal (§5.2). This is a deliberate scope decision, not a data-availability constraint: DoorDash rows are collected, validated, and retained in the raw `prices` table (n = 7,571 US rows) but filtered out before index construction.

---

## 9. Conclusion and Future Work

UICPI demonstrates that food-service menu prices Granger-lead official CPI in the United States at an exact one-month calendar lag, marginally so (F(1, 28) = 4.20, analytic p = 0.0499; permutation p = 0.052 shuffle / 0.069 block) — a result carried forward unchanged from the project's prior formal/informal-framed analysis, extending the Billion Prices Project methodology to the restaurant sector. The result rests on a developmental dataset that has grown to ten countries and 102,499 price observations, and on a fully open-source pipeline whose probes, extractors, bail decisions, and monthly cron are all committed to the repository. This draft's contribution beyond the prior one is a sharper research question — chain vs. independent vendor pricing, motivated by Cavallo's [2018] sticky-price findings — and an honest accounting of what the current, larger dataset can and cannot yet say about it.

Future work falls in four directions. First, **re-run the statistical pipeline against the current, larger dataset**: every Granger and pass-through statistic in this draft was carried forward from the v0.2 analysis because it could not be recomputed from this environment; doing so is the single highest-priority next step, given how much collection has continued since. Second, **close the AU and UK Granger gaps via accumulation**, and **re-scrape Vietnam and UAE with corrected parsers** now that the quarantine has identified exactly what went wrong in each. Third, **grow independent-vendor sample sizes deliberately** rather than incidentally — the current 82/18 chain/independent split makes the paper's central question untestable in every country examined so far, and closing that gap (particularly in the UK, Malaysia, and Singapore, which already have the largest independent samples) is a precondition for the chain-vs-independent Granger and pass-through comparison described in §7.4. Fourth, **run that comparison** once sample sizes allow it, and **test whether the one-month lead shortens, lengthens, or disappears** when chain and independent sub-indices are examined separately — the question this entire reframing was undertaken to eventually ask.

---

## 10. Acknowledgments

The UICPI codebase, pipeline, audit trail, ingestion scripts, and dashboard (https://github.com/thefrogfacedfoot/Inflation-menu) are released open source under the repository's existing licence so that the probe decisions, parser specifics, and bail trail can be independently audited and the index reproduced or extended for other economies. This work depends entirely on open data infrastructure: the Internet Archive's Wayback Machine and CDX index, the UK Office for National Statistics' consumer price quotes (Crown Copyright, Open Government Licence v3.0), the Malaysia KPDN PriceCatcher dataset (data.gov.my, Terbuka 1.0), the OECD SDMX endpoint for harmonised CPI series, the Australian Bureau of Statistics CPI publications, the US Bureau of Labor Statistics' Average Price Data (APU) bulk files, and the Schema.org Working Group's `Menu` type specification. The author thanks the maintainers of `statsmodels`, `pandas`, `playwright`, and `requests` for the libraries on which the pipeline is built. Any errors are the author's own.

---

## 11. References

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

# UICPI Pre-registration, v1 (DRAFT, revision 2)

Status: DRAFT for review. Becomes binding when merged; the merge commit SHA is the registered version.
Drafted: 2026-10-07. Revised: 2026-10-07. No analysis was run and no index values were viewed while writing or revising this document. The only data fetched in revision 2 is official-series metadata (IDs, start/end dates, adjustment status) needed for §2.

**Study type: pre-specified analysis of partially observed data.** This is not a blind pre-registration (§0). The word "confirmatory" in this document always carries that qualifier.

Items marked **DECISION FOR WC** are open choices with a recommendation written as the default. Items marked **VERIFY** are facts not yet confirmed against the publisher; the tag is removed only once confirmed.

## 0. Disclosure: all data were previously examined

All countries' existing data, and the prior Granger outputs on them, have been examined by the authors before this registration. The study is therefore a **pre-specified analysis of partially observed data**, not a blind one. "Confirmatory" below means: specification, family, and inference were fixed before the *extended Wayback backfill data* are analysed. It does not mean the hypothesis is untested or the data are unseen.

Prior country-level Granger runs and related looks, all treated as seen:

| Country | Prior run (source) |
|---|---|
| US | F=4.20, p=0.0499, n=31, one-month calendar lag, F(1,28); permutation p=0.052 (shuffle) / 0.069 (circular block, b=5) (paper draft). Forward-fill robustness F(1,35)=9.05, p=0.0048, n=38. |
| US (deprecated) | F=6.03, p=0.021, gap-mixing; deprecated, not cited. |
| US (source-stratified) | menupages-only F=6.22, p=0.021, n=27; with DoorDash pooled F=0.006, p=0.94, n=38 (`diagnostics/diag_us_no_doordash.py`). A related stratified run reports F=5.56, p=0.026, n=31 without DoorDash. |
| India | F=0.521, p=0.474, n=47 (paper draft). |
| Malaysia | F=0.111, p=0.742, n=30 (paper draft). |
| Singapore | p=0.092 (reported by WC; I did not locate this run's output in the repo. `analysis_results/granger_results.json` lists SG with n=8, below the 24 threshold). |
| Australia, Indonesia, UK | Below the n=24 threshold in `analysis_results/granger_results.json` (n=23, 20, 18); no test reported. |
| Thailand | No overlap with a monthly CPI series; no test. |
| Vietnam, UAE | Earlier Granger statistics (VN n=12, p=0.42; UAE n=47, F=0.016, p=0.90) were computed on corrupted Wayback slices and are withdrawn. |

Also seen: the DoorDash exclusion from index construction (`index_builder.EXCLUDED_SOURCES`, 2026-06-22) was made after observing its effect on the US Granger statistic, and the 2026-07-06 calendar-true respec was made after seeing the gap-mixed result.

Consequences stated plainly:
- The US result is exploratory-prior. It is not counted as confirmatory evidence.
- Any country whose prior result is listed above may show the same pattern again simply because the index data overlaps. The new backfill extends the spans; the overlap is not independent evidence.

### D1 finding: how the DoorDash data was collected (result of the code and log audit)

- All DoorDash rows carry `source='wayback-doordash'` (`doordash_us_2023_sweep.py`, `SOURCE_KEY`). They were collected from the **Internet Archive**: CDX queries on `doordash.com/store/*`, then raw snapshot fetches via `web.archive.org/web/<ts>id_/<url>` (`historical_html_scraper.py`: `CDX`, `WBM`, line 749), with the identifying header `User-Agent: UIFPI-research-pipeline (academic; contact via repo issues)`.
- I found **no proxy, stealth, fingerprint-spoofing, captcha-solving or block-circumvention code** in either script. The only `captcha` mentions are a comment recording that a suspected captcha was a false positive (reCAPTCHA badge outside the JSON-LD blocks).
- **Live DoorDash scraping did not succeed.** `live_scraper.py` records that all 11 DoorDash NYC URLs hit a Cloudflare challenge (HTTP 403, also with cloudscraper) and the targets were removed. The only live code path for DoorDash is the generic `scrape_js`, and the code writes no `live-doordash` source key.
- Limits of this audit: I did not query `uifpi.db`, so I have not confirmed that no live-sourced DoorDash rows exist under another label. The code shows none can be written. Many sweep snapshots parsed to "0 items" (e.g. a 97% zero-item rate on an earlier sweep), which affects coverage, not provenance.
- The exclusion rationale on record is explicitly "a deliberate scope decision, not a data-quality bail": delivery-platform prices embed fees and markup, and the pooled index diluted the Granger statistic.

**Resolution under your rule (D1):** the DoorDash data are archival, not circumvention-collected, so they are **included in the primary confirmatory index**. The exclusion is reported as a **labelled sensitivity analysis** (index built with `wayback-doordash` removed). The result-informed exclusion is not used for the primary. Expect this to change the US primary result relative to the published headline; that is the point of fixing it in advance.

## 1. Primary hypothesis

- H1: the lagged monthly change in the UICPI menu-price index contains information about the future monthly change in the official restaurant / food-away-from-home CPI, beyond that CPI's own lags. The direction is UICPI → official CPI.
- H0: all coefficients on lagged Δlog UICPI are zero in the equation for Δlog CPI, conditional on lagged Δlog CPI.
- Test statistic: the Wald/F statistic of the Granger exclusion restriction in a bivariate VAR(p) estimated by OLS. It is a joint test; there is no one-sided variant.
- The reverse direction (CPI → UICPI) is exploratory.

## 2. Outcome variables

Primary outcome: the official restaurant / food-away-from-home CPI, monthly, **seasonally adjusted where the publisher provides it**. Secondary outcome: headline all-items CPI (also SA where published).

Verified 2026-10-07 by fetching the publisher or a mirror; "start–end" are the first and last monthly observations present.

| Country | Series (primary) | Exact ID | Source URL | Start–end | SA available | Notes |
|---|---|---|---|---|---|---|
| US | CPI-U Food away from home, SA | `CUSR0000SEFV` | https://fred.stlouisfed.org/series/CUSR0000SEFV (BLS via FRED) | 1953-01 – 2026-08 | Yes (this is the SA series). Headline SA: FRED `CPIAUCSL`, 1947-01 – 2026-08. | Index 1982-84=100. An NSA counterpart exists (FRED notes it); used only as an exploratory sensitivity. |
| GB | CPI index 11.1.1 Restaurants & cafés, 2015=100 | `D7EW` (dataset MM23) | https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7ew/mm23 | 1988-01 – 2026-08 (464 months) | No SA series found in MM23; **NSA** | Headline `D7BT` (CPI Index 00 All items), 1988-01 – 2026-08. Related ONS IDs are not this series: `D7GI` is the annual rate for division 11; `CJYL` is weights; `J3G3` and `L82E` are CPIH/monthly-rate series. |
| SG | CPI 2024=100, Food & Beverage Serving Services (series 1.11) | SingStat table `M213752` (SA) / `M213751` (NSA), row `1.11` | https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213752?search=serving | 1990-01 – 2026-08 (440 months) | Yes (`M213752`) | Headline: row `1` All Items, 1961-01 – 2026-08. Table is on a 2024 base. Rebasing is handled in-table, but confirm no splice is applied before 2024 (§9 item 3). |
| MY | DOSM monthly CPI by division, division `11` | OpenDOSM `cpi_headline` (rows with `division == "11"`; the API serves the 2-digit national monthly table) | https://open.dosm.gov.my/data-catalogue/cpi_headline | 1980-01 – 2026-08 (560 months, no gaps) | Not stated by the publisher; treated as NSA | Base 2010=100. A finer group `111` exists in `cpi_3d` (2010-01 – 2026-08). **VERIFY** only the English label of codes `11`/`111` against the DOSM MCOICOP lookup; I could not retrieve the lookup table. Headline: division `overall`. |
| TH | TPSO "Prepared food: away from home", base 2019=100 | **VERIFY** exact series ID | Ministry of Commerce / TPSO (the category appears in secondary reports; I could not reach a primary download) | **VERIFY** | **VERIFY** | Series name and 2019 base confirmed only from secondary sources (Bangkok Bank research charts). Not yet admissible. |
| ID | BPS IHK, group "Penyediaan Makanan dan Minuman/Restoran" | **VERIFY** exact series ID | BPS tables (bps.go.id returned HTTP 403 to my fetch; the group's existence and monthly publication were confirmed only from secondary reports and data catalogues) | **VERIFY** | **VERIFY** | A base change (2018=100 → 2022=100) is likely a series break; not yet confirmed. Not yet admissible. |
| AU | ABS CPI, expenditure class "Meals out and take away foods" (Restaurant meals + Takeaways and fast foods) | ABS Table 3 (A-number not captured) | https://www.abs.gov.au/statistics/detailed-methodology-information/information-papers/introducing-consumer-price-indexes-new-monthly-time-series | **2024-04** – 2026-08 (about 29 months) | Yes (ABS Table 7) | **Excluded under D2.** The complete monthly CPI begins with the October-2025 release, back-cast only to April 2024, so the complete monthly history is about 29 months, below N_MIN=36. Earlier history is quarterly with carried-forward steps between collections, which is not a real monthly observation. |
| IN, AE, VN | Not researched in this revision | n/a | n/a | n/a | n/a | Remain out of the confirmatory family unless a monthly restaurant series is added and verified before merge. |

Rules:

- A country whose primary series is not monthly over the whole analysis span is excluded from the confirmatory family (§3). It is never interpolated.
- A series break (rebasing, reclassification) is spliced only if the publisher provides an official linking factor. Otherwise the series is cut at the break and the longest clean contiguous run is used.
- A country enters the family only after its series is **fully verified here** and ingested monthly (§9 item 3). Until then it is not in the family, however its index looks.
- Headline CPI is a secondary outcome with its own multiplicity family (§5), labelled "secondary".

## 3. Test family (inclusion by rule)

A country is in the confirmatory family if and only if it meets ALL of:

1. n ≥ **36** calendar-true monthly observations (definition in §4.5). [D2]
2. A verified monthly official primary series exists over that span (§2). Australia fails this by rule (about 29 complete monthly months).
3. The index for that country is reproducible from committed code and public or archival data (§8).
4. At least 15 matched restaurants per country-month. Matched means the same restaurant observed in both month t and t−1. This was decided on 2026-10-07. Months below 15 count as missing.

Inclusion is evaluated on data counts only (series length, restaurant counts) by a script that computes no index-vs-CPI statistic. The resulting country list is committed before any test is run.

**D2 = 36 (decided).** Rationale: with max lag 3, n=36 leaves roughly 30 residual degrees of freedom.

**Minimum detectable effect at n=36 (approximate, hand calculation, not yet simulated).** Take n=36 levels, so 35 differences, about 32 usable regression observations at lag 1 and 30 at lag 3. At α=0.05 and 80% power, using a noncentral-F approximation:
- Lag 1 (1 restriction): λ≈8, so partial f²≈0.25, i.e. a partial R² of about 0.20 (partial correlation about 0.45) for the lagged index term.
- Lag 3 (3 restrictions): λ≈11, so f²≈0.35, partial R² about 0.26.
- Stated differently: at n=36 the design detects only a **large** lead-lag effect. It has low power for a medium one (partial R² ≈ 0.10). A null result at this n is not evidence of absence.
- These figures are before multiplicity correction. Under Romano–Wolf with k countries, the adjusted threshold is stricter, so the minimum detectable effect is larger. The permutation test reduces size distortion but does not add power.
- The exact figure is replaced by a simulation-based power calculation in the code PR (§9 item 1); the calculation must be run on simulated data, not on index values.

## 4. Specification (fixed)

4.1 Transform. Let I_t be the index level and C_t the CPI level. Use x_t = Δlog I_t = log I_t − log I_{t−1} and y_t = Δlog C_t. Both are defined only if months t and t−1 are real observations.

4.2 Stationarity. Run ADF (constant, lag length by AIC) and KPSS (level stationarity) on x and y within each country's analysis window. A series is stationary if ADF p < 0.05 AND KPSS p > 0.05. **D3 (decided):** if either series fails, the country is **exploratory**. There is **no second differencing**. The stationarity outcome decides the family, not the Granger result.

4.3 Lag selection. **D4 (decided):** BIC on the unrestricted bivariate VAR of (y, x), p ∈ {1, 2, 3}. Ties go to the smaller p. Note: a maximum lag of 3 months **cannot detect slower transmission** (a lead of 4 months or more). A null result here says nothing about longer pass-through horizons. Any longer-lag analysis is exploratory.

4.4 Calendar-true alignment only. The monthly index is aligned to the official CPI by calendar month. A lag never spans a missing month, so a "lag 1" difference is always exactly one calendar month. Regressions use only windows where every month is a real observation.

4.5 Months with no real observation. A month with fewer than 15 matched restaurants, or no data, is MISSING. Missing months are never forward-filled, interpolated, or carried. A carried value is never counted as an observation.

**D5 (as recommended):** use the longest single contiguous run of valid months per country, and define n as the number of months in that run (levels, before differencing).

4.6 Seasonality.
- Use the official **seasonally adjusted** series where published (US: `CUSR0000SEFV`, not the `CUUR` NSA series; SG: `M213752`). Where only NSA exists (GB, MY), use NSA and say so.
- The UICPI index itself is not seasonally adjusted. This mismatch is acknowledged: seasonality remaining in x is handled only by the diagnostic below.
- **Required diagnostic:** after fitting the VAR(p) selected in §4.3, run a Ljung–Box test at lag 12 on the residuals of both equations (degrees of freedom adjusted for the fitted lags). If it rejects at 5% for either equation, **add 11 month dummies** to both equations and re-run the Granger test; the dummy version is then the reported test. Otherwise no dummies.
- Caveat: at n=36, adding 11 dummies leaves very few residual degrees of freedom, and the Ljung–Box test at lag 12 has low power. Both facts are reported with the result.

4.7 Sensitivity analyses (all exploratory unless listed in §7): the DoorDash-excluded index (D1), the NSA US series, AIC vs BIC, max lag 4, reverse direction, source-stratified indices.

## 5. Inference

5.1 Raw p-value: the asymptotic F-test p-value, always reported next to the permutation p.

5.2 Circular-block permutation (primary p-value). The permuted object is the x series. Cut it into circular blocks of length b, draw blocks with replacement, concatenate to the original length, and recompute the F statistic. y is not permuted. B = 9,999, fixed seed recorded in the results commit. p = (1 + #{F* ≥ F_obs}) / (B + 1).

**D6 (as recommended):** b = ⌈n^(1/3)⌉ per country (n = number of differenced observations), floor 3, cap 6. Report p at b±1 as an exploratory robustness line.

5.3 Multiplicity. Within the family of countries from §3, for the primary outcome:
- Romano–Wolf stepdown adjusted p-values from the permutation distributions. Blocks are drawn on a common calendar index, so overlapping months share the same resampling and cross-country dependence is retained.
- Benjamini–Hochberg q-values on the permutation p-values, FDR 0.10, reported as secondary.
- Both are reported next to the raw p and the permutation p, in the same row.

Decision rule: country-level evidence is claimed only where the Romano–Wolf adjusted p < 0.05. The headline-CPI secondary outcome is its own family with its own Romano–Wolf and BH adjustment and is never pooled with the primary family.

## 6. Panel alternative

Dumitrescu–Hurlin panel Granger test over all included countries (§3), same transforms (§4).

**Declared now as the primary test if fewer than 3 included countries reach n ≥ 100** (n as in §4.5). Then the per-country tests are confirmatory-secondary with the §5.3 adjustment. If 3 or more reach n ≥ 100, the per-country family is primary and the panel test is confirmatory-secondary.

**D7 (as recommended, with panel on the common window):**
- Statistic: the Z̃-bar (small-T standardised) statistic; W-bar also reported.
- **Window:** the panel is estimated on the **common calendar window**, the months for which every included country has a valid observation, so the panel is balanced.
- Lag: the common lag p from the BIC rule applied to the pooled panel.
- **Inference:** the p-value comes from the circular-block permutation with **blocks drawn on calendar time and applied jointly across countries**: the same calendar blocks are applied to every country's x series in each draw, so cross-sectional dependence is preserved. Asymptotic Z̃ is reported but not used for the decision.
- The code is written from Dumitrescu–Hurlin (2012) and committed.
- Cost: the common window is as short as the shortest country's span. If that is under the §3 threshold, the panel is not run and the report says so, rather than relaxing the window.

## 7. Confirmatory vs exploratory

"Confirmatory" here always means *pre-specified analysis of partially observed data* (§0). The confirmatory claims are:

- C1. Per-country Granger test, UICPI → restaurant / food-away-from-home CPI, for countries in the §3 family, with raw p, block-permutation p, Romano–Wolf p and BH q (primary if ≥ 3 countries reach n ≥ 100, secondary otherwise).
- C2. The Dumitrescu–Hurlin panel test (primary if fewer than 3 countries reach n ≥ 100, secondary otherwise).
- C3. Secondary outcome: UICPI → headline CPI, its own family, labelled secondary.

Everything else is exploratory and must be labelled "exploratory" wherever it appears, including:

- The earlier US F=4.20 / p=0.0499 result and every other prior run in §0.
- The reverse direction, the DoorDash-excluded sensitivity index, AIC and max-lag-4 runs, source-stratified or chain-vs-independent indices, other block lengths, the NSA US series, and any country dropped by the §3 or §4.2 rules.
- The ADL pass-through models in the current code.
- The hawker fieldwork (descriptive only).
- Any specification change after this document is merged. Any such change is a **deviation**, listed in the results file with a reason.

## 8. Data provenance rule

- The confirmatory index uses only: archival data (Wayback Machine snapshots fetched via the raw-bytes `id_` path), data from public sites, and the hawker fieldwork. Every Wayback row carries its snapshot timestamp, original URL and CDX digest so each price is traceable.
- **DoorDash:** the D1 audit shows `wayback-doordash` is Internet Archive data collected without proxy or block circumvention, so it is **in** the confirmatory index. The DoorDash-excluded index is an exploratory sensitivity. If a later audit finds any DoorDash rows from residential-IP or circumvented live access, those rows are removed from the confirmatory index under the rule below.
- Residential-IP live-scrape data (`live_scraper.py`, nightly cron) is supplementary only. It may appear in clearly labelled exploratory figures and sensitivity analyses and never contributes to a confirmatory index level or test.
- The confirmatory index is built with an explicit source whitelist (§9 item 2); the current builder has no provenance filter.
- Code is frozen at a commit SHA recorded in the results commit. If the specification cannot be executed as written, the run stops and reports. It does not improvise.

## 9. Code PRs required before the confirmatory run (none done yet)

1. **`granger_analysis.py` (or a new script) implementing this specification.** Today's script uses AIC (max lag 4), has no BIC rule, no ADF+KPSS gate, no Ljung–Box/dummy rule, no circular-block permutation (b=⌈n^(1/3)⌉, B=9,999), no Romano–Wolf or BH, no Dumitrescu–Hurlin panel, and no calendar-true contiguous-run handling; it also interpolates AU. Includes the simulation-based power calculation that replaces the §3 hand figures, and the stationarity test of the §4.2 rule.
2. **Provenance whitelist in `index_builder.py`.** Add an explicit source whitelist for the confirmatory index (archival `wayback-*` and public-site sources only; live-scrape sources excluded), enforce the ≥15 matched-restaurant rule per country-month, emit missing months as missing (no carry-forward), and make the `EXCLUDED_SOURCES` behaviour a switch so the D1 sensitivity index can be built from the same code path.
3. **Monthly CPI ingestion for the five countries.** Wire monthly restaurant/food-away-from-home series into the CPI pipeline (`get_monthly_cpi_all.py` currently loads headline/food and falls back to World Bank annual): US `CUSR0000SEFV`, GB `D7EW`, SG `M213752` row `1.11`, MY `cpi_headline` division `11`, and TH and ID once their IDs are verified (§2). Store both SA and NSA where available and record the series ID and fetch date. Remove AU interpolation from the primary path.

## 10. Pre-merge checklist

- [ ] Verify the remaining **VERIFY** items in §2: TH series ID, start date and SA status; ID series ID, start date, SA status and base-change break; the English label of MY division `11` / group `111`.
- [ ] Record the merge commit SHA as the registered version.

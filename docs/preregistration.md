# UICPI Pre-registration, v1 (DRAFT, revision 3)

Status: DRAFT for review. Becomes binding when merged; the merge commit SHA is the registered version.
Drafted: 2026-10-07. Revised: 2026-10-07 (revisions 2 and 3). No analysis was run and no index values were viewed while writing or revising this document. Data touched in revisions 2 and 3: official-series metadata (IDs, start/end dates, adjustment status, code-label lookups) for §2, and one read-only count of `prices` rows per `source` (§0, D1).

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
| Singapore | **Withdrawn pending reproduction.** The figure p=0.092 (lag 2, n=12) appears in `diagnostic_report_v3.txt`, `diagnostic_report_v4.txt`, `README.md`, `CHANGELOG.md` and `docs/archival_data_findings_2026-06-16.md`, but its provenance could not be traced: no committed script, command, or data snapshot that reproduces it was found, and the current `analysis_results/granger_results.json` lists SG with n=8, below the n=24 threshold. It is not cited as a result and is not counted as a prior run until reproduced. |
| Australia, Indonesia, UK | Below the n=24 threshold in `analysis_results/granger_results.json` (n=23, 20, 18); no test reported. |
| Thailand | No overlap with a monthly CPI series; no test. |
| Vietnam, UAE | Earlier Granger statistics (VN n=12, p=0.42; UAE n=47, F=0.016, p=0.90) were computed on corrupted Wayback slices and are withdrawn. |

Also seen: the DoorDash exclusion from index construction (`index_builder.EXCLUDED_SOURCES`, 2026-06-22) was made after observing its effect on the US Granger statistic, and the 2026-07-06 calendar-true respec was made after seeing the gap-mixed result.

Consequences stated plainly:
- The US result is exploratory-prior. It is not counted as confirmatory evidence.
- Any country whose prior result is listed above may show the same pattern again simply because the index data overlaps. The new backfill extends the spans; the overlap is not independent evidence.

### D1 finding: how the DoorDash data was collected (result of the code, log and database audit)

- All DoorDash rows carry `source='wayback-doordash'` (`doordash_us_2023_sweep.py`, `SOURCE_KEY`). They were collected from the **Internet Archive**: CDX queries on `doordash.com/store/*`, then raw snapshot fetches via `web.archive.org/web/<ts>id_/<url>` (`historical_html_scraper.py`: `CDX`, `WBM`, line 749), with the identifying header `User-Agent: UIFPI-research-pipeline (academic; contact via repo issues)`.
- I found **no proxy, stealth, fingerprint-spoofing, captcha-solving or block-circumvention code** in either script. The only `captcha` mentions are a comment recording that a suspected captcha was a false positive (reCAPTCHA badge outside the JSON-LD blocks).
- **Live DoorDash scraping did not succeed.** `live_scraper.py` records that all 11 DoorDash NYC URLs hit a Cloudflare challenge (HTTP 403, also with cloudscraper) and the targets were removed. The code writes no `live-doordash` source key.
- **Database provenance check** (read-only, `SELECT source, COUNT(*) FROM prices GROUP BY source`, 2026-10-07; no other query was run):

| source | rows |
|---|---|
| wayback-deliveroo | 306,103 |
| js | 265,889 |
| grabfood | 137,814 |
| wayback-doordash | 64,922 |
| wayback-grabfood | 45,178 |
| official_price_series_bls_apu | 38,216 |
| direct | 10,413 |
| wayback-menupages | 8,282 |
| foodpanda | 6,544 |
| wayback-menulog | 1,652 |
| wayback-zomato | 664 |
| wayback | 70 |
| Wayback/TripAdvisor | 10 |
| Wayback/wongnai | 1 |

  No DoorDash-labelled live source exists. Caveats: the `js` label (generic JS scraper, 265,889 rows) is not broken down by platform, and I ran no other query, so labels alone cannot show that none of it came from DoorDash; the code history says live DoorDash returned nothing. The bare `wayback`, `Wayback/TripAdvisor` and `Wayback/wongnai` labels, and the non-restaurant `official_price_series_bls_apu`, show the source taxonomy has several label generations, which a whitelist must handle (§9 item 2).
- Many sweep snapshots parsed to "0 items" (e.g. a 97% zero-item rate on an earlier sweep). That affects coverage, not provenance.
- The exclusion rationale on record is explicitly "a deliberate scope decision, not a data-quality bail": delivery-platform prices embed fees and markup, and the pooled index diluted the Granger statistic.

**Resolution under your rule (D1):** the DoorDash data are archival, not circumvention-collected, so they are **included in the primary confirmatory index**. The exclusion is reported as a **labelled sensitivity analysis** (index built with `wayback-doordash` removed). The result-informed exclusion is not used for the primary. Expect this to change the US primary result relative to the published headline.

## 1. Primary hypothesis

- H1: the lagged monthly change in the UICPI menu-price index contains information about the future monthly change in the official restaurant / food-away-from-home CPI, beyond that CPI's own lags. The direction is UICPI → official CPI.
- H0: all coefficients on lagged Δlog UICPI are zero in the equation for Δlog CPI, conditional on lagged Δlog CPI. For the panel test (§6) H0 is that this holds in every country (homogeneous non-causality).
- Test statistic: the Wald/F statistic of the Granger exclusion restriction in a bivariate VAR(p) estimated by OLS. It is a joint test; there is no one-sided variant.
- The reverse direction (CPI → UICPI) is exploratory.

## 2. Outcome variables

Primary outcome: the official restaurant / food-away-from-home CPI, monthly, **not seasonally adjusted (NSA)**. Secondary outcome: headline all-items CPI, also NSA. The UICPI index is also NSA (§4.6).

Verified 2026-10-07 by fetching the publisher or a mirror; "start–end" are the first and last monthly observations present.

| Country | Primary series (NSA) | Exact ID | Source URL | Start–end | Headline (NSA, secondary) | Notes |
|---|---|---|---|---|---|---|
| US | CPI-U Food away from home, NSA | `CUUR0000SEFV` | https://fred.stlouisfed.org/series/CUUR0000SEFV (BLS via FRED) | 1953-01 – 2026-08 | FRED `CPIAUCNS`, 1913-01 – 2026-08 | Index 1982-84=100. The SA counterpart `CUSR0000SEFV` exists and is **not used**. |
| GB | CPI index 11.1.1 Restaurants & cafés, 2015=100 | `D7EW` (dataset MM23) | https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7ew/mm23 | 1988-01 – 2026-08 (464 months) | `D7BT` (CPI Index 00 All items), 1988-01 – 2026-08 | ONS publishes these indices NSA. Related ONS IDs that are not this series: `D7GI` (annual rate, division 11), `CJYL` (weights), `J3G3`/`L82E` (CPIH / monthly-rate series). |
| SG | CPI 2024=100, Food & Beverage Serving Services (row 1.11) | SingStat table `M213751`, row `1.11` | https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751?search=serving | 1990-01 – 2026-08 (440 months) | Row `1` All Items, 1961-01 – 2026-08 | The SA table `M213752` exists and is **not used**. The table is on a 2024 base; the §2 rebasing rule applies if any splice is found (§9 item 3). |
| MY | DOSM monthly CPI by group (3-digit), group `111` | OpenDOSM `cpi_3d`, `group == "111"` | https://open.dosm.gov.my/data-catalogue/cpi_3d | 2010-01 – 2026-08 (200 months) | `cpi_headline`, division `overall` (1980-01 – 2026-08) | Base 2010=100. DOSM documents no seasonal adjustment, so treated as NSA (to be confirmed with the raw file). **Label confirmed** from the DOSM MCOICOP lookup (OpenDOSM API `id=mcoicop`): group `111` is "Food & beverage preparation services" (Malay: Perkhidmatan penyediaan minuman), division `11` "Restaurant & Accommodation Services"; its only class is `1111` "Restaurants, cafés & the like". Note this is "preparation", not the "serving" wording used for SG; the content is equivalent (restaurants and cafés). Division `11` (1980-01 –) also includes accommodation and is **not** used. |
| TH | TPSO "Prepared food: away from home", base 2019=100 | **VERIFY** exact series ID | Ministry of Commerce / TPSO (primary source not reached) | **VERIFY** | **VERIFY** | Name and 2019 base known only from secondary reports. WC will supply raw files. Not admissible until verified. |
| ID | BPS IHK, group "Penyediaan Makanan dan Minuman/Restoran" | **VERIFY** exact series ID | BPS (bps.go.id returned HTTP 403 to my fetch) | **VERIFY** | **VERIFY** | A base change (2018=100 → 2022=100) is likely a series break (§2 rebasing rule). WC will supply raw files. Not admissible until verified. |
| AU | ABS CPI, expenditure class "Meals out and take away foods" | ABS Table 3 (A-number not captured) | https://www.abs.gov.au/statistics/detailed-methodology-information/information-papers/introducing-consumer-price-indexes-new-monthly-time-series | **2024-04** – 2026-08 (about 29 months) | n/a | **Excluded under D2.** The complete monthly CPI begins with the October-2025 release, back-cast only to April 2024, so the complete monthly history is about 29 months, below N_MIN=36. Earlier history is quarterly with carried-forward steps, which is not a real monthly observation. |
| IN, AE, VN | Not researched | n/a | n/a | n/a | n/a | Out of the confirmatory family unless a monthly restaurant series is added and verified before merge. |

Rules:

- A country whose primary series is not monthly over the whole analysis span is excluded from the confirmatory family (§3). It is never interpolated.
- **Rebasing and splicing rule.** When a publisher rebases or reclassifies, two vintages of a series may be joined only by chain-linking at an **overlap month** present in both vintages: scale the older vintage by (new level at the overlap month) / (old level at the overlap month), then use the older vintage's month-on-month changes before the overlap. The overlap month, both vintages' IDs and the scaling factor are recorded in the results file. If the vintages have **no overlap month**, the rebasing is treated as a **series break**: the series is cut there and **D5 (longest contiguous run)** is applied, with no splice and no interpolation across the break. The same rule applies to the UICPI index if its basket definition changes.
- A country enters the family only after its series is fully verified here and ingested monthly (§9 item 3).
- Headline CPI is a secondary outcome, labelled "secondary" (§5).

## 3. Test family (inclusion by rule)

A country is in the confirmatory family if and only if it meets ALL of:

1. n ≥ **36** calendar-true monthly observations (definition in §4.5). [D2]
2. A verified monthly official primary series exists over that span (§2). Australia fails this by rule (about 29 complete monthly months).
3. The index for that country is reproducible from committed code and public or archival data (§8).
4. At least 15 matched restaurants per country-month. Matched means the same restaurant observed in both month t and t−1. This was decided on 2026-10-07. Months below 15 count as missing.

Inclusion is evaluated on data counts only (series length, restaurant counts) by a script that computes no index-vs-CPI statistic. The resulting country list is committed before any test is run.

**D2 = 36 (decided).**

**Minimum detectable effect at n=36, with the 11 month dummies (approximate, hand calculation, not yet simulated).** n=36 monthly levels gives 35 differences. Each equation has a constant, p lags of each variable (2p coefficients), and 11 month dummies:

| Lag p | Regression obs (35 − p) | Parameters (1 + 2p + 11) | **Residual df** |
|---|---|---|---|
| 1 | 34 | 14 | **20** |
| 2 | 33 | 16 | **17** |
| 3 | 32 | 18 | **14** |

At α=0.05 and 80% power, using a noncentral-F approximation for one country's Granger test:
- Lag 1 (1 restriction, residual df 20): λ≈8.7, so partial f²≈0.26, i.e. a partial R² for the lagged index term of about 0.20 (partial correlation about 0.45).
- Lag 3 (3 restrictions, residual df 14): λ≈13, so partial f²≈0.4, i.e. partial R² about 0.3.
- At n=36 a single-country test therefore detects only a **large** lead-lag effect. Power for a medium effect (partial R² ≈ 0.10) is low, and a null at this n is not evidence of absence. This is before any multiplicity correction, which only raises the minimum detectable effect.
- The panel test (primary, §6) pools countries and has more power than any one country, but its power depends on how many countries enter and on the common window length, neither of which is known yet. It is not quantified here.
- These figures are hand approximations. The code PR (§9 item 1) replaces them with a simulation-based power calculation run on simulated data, not on index values.

## 4. Specification (fixed)

4.1 Transform. Let I_t be the index level and C_t the CPI level. Use x_t = Δlog I_t = log I_t − log I_{t−1} and y_t = Δlog C_t. Both are defined only if months t and t−1 are real observations.

4.2 Stationarity. Run ADF (constant, lag length by AIC) and KPSS (level stationarity) on x and y within each country's analysis window. A series is stationary if ADF p < 0.05 AND KPSS p > 0.05. **D3 (decided):** if either series fails, the country is **exploratory**. There is **no second differencing**. The stationarity outcome decides the family, not the Granger result.

4.3 Lag selection. **D4 (decided):** BIC on the unrestricted bivariate VAR of (y, x) **including the 11 month dummies** (§4.6), p ∈ {1, 2, 3}. Ties go to the smaller p. A maximum lag of 3 months **cannot detect slower transmission** (a lead of 4 months or more); a null here says nothing about longer horizons. Any longer-lag analysis is exploratory.

4.4 Calendar-true alignment only. The monthly index is aligned to the official CPI by calendar month. A lag never spans a missing month, so a "lag 1" difference is always exactly one calendar month. Regressions use only windows where every month is a real observation.

4.5 Months with no real observation. A month with fewer than 15 matched restaurants, or no data, is MISSING. Missing months are never forward-filled, interpolated, or carried. A carried value is never counted as an observation.

**D5 (as recommended):** use the longest single contiguous run of valid months per country, and define n as the number of months in that run (levels, before differencing).

4.6 Seasonality. **Both sides are NSA, in every country.** The official CPI series are the NSA series in §2, and the UICPI index is NSA. **11 month dummies are always included** in both VAR equations, in the lag selection (§4.3), the Granger tests (country and panel), and the permutation (§5.2). There is no conditional rule.
- **Why NSA rather than SA:** seasonal-adjustment filters (X-11/X-13, STL and similar) are two-sided: the adjusted value at month t is computed using observations after t. That leaks future information into the series and smears its timing, which distorts exactly the thing a Granger test measures: which series moves first. SA series are also revised as the filter is re-run. Adjusting only one side would be inconsistent, and the UICPI index has no official adjustment. Month dummies handle seasonality inside the regression using only the sample's own months.
- **Diagnostic only:** a Ljung–Box test at lag 12 on the residuals of both equations is **reported for every country** as a diagnostic. It changes nothing: it triggers no re-specification and removes no country.
- Cost, reported with the result: the dummies use degrees of freedom (§3 table). Residual df at n=36 is 14–20.

4.7 Sensitivity analyses (all exploratory unless listed in §7): the DoorDash-excluded index (D1), the SA official series, AIC vs BIC, max lag 4, no-dummy specification, reverse direction, source-stratified indices.

## 5. Inference

5.1 Raw p-value: the asymptotic F-test p-value, always reported next to the permutation p.

5.2 Circular-block permutation (primary p-value for country-level tests). The permuted object is the x series (month dummies are not permuted). Cut it into circular blocks of length b, draw blocks with replacement, concatenate to the original length, and recompute the F statistic. y is not permuted. B = 9,999, fixed seed recorded in the results commit. p = (1 + #{F* ≥ F_obs}) / (B + 1).

**D6 (as recommended):** b = ⌈n^(1/3)⌉ per country (n = number of differenced observations), floor 3, cap 6. Report p at b±1 as an exploratory robustness line.

5.3 Multiplicity for the **secondary** country-level family. Within the family of countries from §3, for the primary outcome:
- Romano–Wolf stepdown adjusted p-values from the permutation distributions. Blocks are drawn on a common calendar index, so overlapping months share the same resampling and cross-country dependence is retained.
- Benjamini–Hochberg q-values on the permutation p-values, FDR 0.10.
- Both are reported next to the raw p and the permutation p, in the same row.

Country-level evidence is claimed only where the Romano–Wolf adjusted p < 0.05, and is labelled secondary. The headline-CPI outcome is its own family with its own adjustment and is never pooled.

## 6. Panel test (primary confirmatory test, unconditional)

The **Dumitrescu–Hurlin panel Granger test is the primary confirmatory test, unconditionally.** It is not conditional on how many countries reach any n threshold. The country-level tests (§5) are secondary.

- Panel: all countries meeting the §3 inclusion rule; same transforms (§4), month dummies, and NSA series.
- Statistic: the Z̃-bar (small-T standardised) statistic; W-bar also reported.
- **Window:** the **common calendar window**, the months for which every included country has a valid observation, so the panel is balanced.
- Lag: the common lag p from the BIC rule (§4.3) applied to the pooled panel.
- **Inference:** the p-value comes from the circular-block permutation with **blocks drawn on calendar time and applied jointly across countries** (the same calendar blocks to every country's x series in each draw), so cross-sectional dependence is preserved. Asymptotic Z̃ is reported but not used for the decision.
- The code is written from Dumitrescu–Hurlin (2012) and committed.
- **Failure mode, stated now:** if the common window is shorter than N_MIN=36 months, or fewer than 2 countries are included, the primary test cannot be run as registered. The run **stops and reports**; it does not shorten the threshold, drop countries post hoc, or substitute another test.

**D7 (decided):** panel on the common calendar window, calendar-time blocks applied jointly.

## 7. Confirmatory vs exploratory

"Confirmatory" here always means *pre-specified analysis of partially observed data* (§0).

- **Primary confirmatory (C1):** the Dumitrescu–Hurlin panel test, UICPI → restaurant / food-away-from-home CPI, with permutation p (§6).
- **Secondary confirmatory (C2):** per-country Granger tests for countries in the §3 family, with raw p, block-permutation p, Romano–Wolf p and BH q.
- **Secondary confirmatory (C3):** UICPI → headline CPI (panel and per-country), its own family, labelled secondary.

Everything else is exploratory and must be labelled "exploratory" wherever it appears, including:

- The earlier US F=4.20 / p=0.0499 result and every other prior run in §0.
- The reverse direction, the DoorDash-excluded sensitivity index, SA-series runs, AIC and max-lag-4 runs, no-dummy runs, source-stratified or chain-vs-independent indices, other block lengths, and any country dropped by the §3 or §4.2 rules.
- The ADL pass-through models in the current code.
- The hawker fieldwork (descriptive only).
- Any specification change after this document is merged. Any such change is a **deviation**, listed in the results file with a reason.

## 8. Data provenance rule

- The confirmatory index uses only: archival data (Wayback Machine snapshots fetched via the raw-bytes `id_` path), data from public sites, and the hawker fieldwork. Every Wayback row carries its snapshot timestamp, original URL and CDX digest so each price is traceable.
- **DoorDash:** the D1 audit shows `wayback-doordash` is Internet Archive data collected without proxy or block circumvention, so it is **in** the confirmatory index. The DoorDash-excluded index is an exploratory sensitivity. If a later audit finds DoorDash rows from residential-IP or circumvented live access, those rows are removed from the confirmatory index.
- Residential-IP live-scrape data (`live_scraper.py`, nightly cron) is supplementary only. It may appear in clearly labelled exploratory figures and sensitivity analyses and never contributes to a confirmatory index level or test.
- The confirmatory index is built with an explicit source whitelist (§9 item 2); the current builder has no provenance filter.
- Code is frozen at a commit SHA recorded in the results commit. If the specification cannot be executed as written, the run stops and reports. It does not improvise.

## 9. Code PRs required before the confirmatory run (none done yet)

1. **`granger_analysis.py` (or a new script) implementing this specification.** Today's script uses AIC (max lag 4), has no BIC rule, no month dummies, no ADF+KPSS gate, no Ljung–Box diagnostic, no circular-block permutation (b=⌈n^(1/3)⌉, B=9,999), no Romano–Wolf or BH, no Dumitrescu–Hurlin panel, and no calendar-true contiguous-run handling; it also interpolates AU. Includes the simulation-based power calculation that replaces the §3 hand figures.
2. **Provenance whitelist in `index_builder.py`.** Add an explicit source whitelist for the confirmatory index (archival `wayback-*` and public-site sources only; live-scrape sources excluded), handling every label generation present in `prices` (including `wayback`, `Wayback/TripAdvisor`, `Wayback/wongnai`, and excluding non-restaurant `official_price_series_bls_apu`). Enforce the ≥15 matched-restaurant rule per country-month, emit missing months as missing (no carry-forward), and make `EXCLUDED_SOURCES` a switch so the D1 sensitivity index comes from the same code path.
3. **Monthly CPI ingestion for the five countries.** Wire the monthly NSA restaurant/food-away-from-home series into the CPI pipeline (`get_monthly_cpi_all.py` currently loads headline/food and falls back to World Bank annual): US `CUUR0000SEFV`, GB `D7EW`, SG `M213751` row `1.11`, MY `cpi_3d` group `111`, and TH and ID once verified (§2). Record the series ID, vintage, and fetch date; implement the §2 rebasing/splicing rule. Remove AU interpolation from the primary path.

## 10. Pre-merge checklist

- [ ] TH and ID: WC to supply raw files; verify series ID, start date, NSA status, and any rebasing break (§2), then remove the VERIFY tags.
- [ ] Record the merge commit SHA as the registered version.

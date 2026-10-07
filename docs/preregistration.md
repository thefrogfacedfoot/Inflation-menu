# UICPI Pre-registration, v1 (DRAFT, revision 4)

Status: DRAFT for review. Becomes binding when merged; the merge commit SHA is the registered version.
Drafted: 2026-10-07. Revised: 2026-10-07 (revisions 2 to 4). No analysis was run and no index values were viewed while writing or revising this document. Data touched in revisions 2 to 4: official-series metadata (IDs, start/end dates, adjustment status, code-label lookups) for §2; one read-only count of `prices` rows per `source` (§0, D1); and a Monte Carlo on simulated data (no project data) to check the §3 power figures.

**Study type: pre-specified analysis of partially observed data.** This is not a blind pre-registration (§0). The word "confirmatory" in this document always carries that qualifier.

Items marked **DECISION FOR WC** are open choices with a recommendation written as the default. Items marked **VERIFY** are facts not yet confirmed against the publisher; the tag is removed only once confirmed.

## 0. Disclosure: all data were previously examined

All countries' existing data, and the prior Granger outputs on them, have been examined by the authors before this registration. The study is therefore a **pre-specified analysis of partially observed data**, not a blind one. "Confirmatory" below means: specification, family, and inference were fixed before the *extended Wayback backfill data* are analysed. It does not mean the hypothesis is untested or the data are unseen.

Prior country-level Granger runs and related looks, all treated as seen:

| Country | Prior run (source) |
|---|---|
| US | **Superseded; the published specification is not relied on.** F=4.20, p=0.0499, n=31, one-month calendar lag, F(1,28); permutation p=0.052 (shuffle) / 0.069 (circular block, b=5) (paper draft). Forward-fill robustness F(1,35)=9.05, p=0.0048, n=38. See "Published US specification" below. |
| US (deprecated) | F=6.03, p=0.021, gap-mixing; deprecated, not cited. |
| US (source-stratified) | menupages-only F=6.22, p=0.021, n=27; with DoorDash pooled F=0.006, p=0.94, n=38 (`diagnostics/diag_us_no_doordash.py`). A related stratified run reports F=5.56, p=0.026, n=31 without DoorDash. |
| India | F=0.521, p=0.474, n=47 (paper draft). |
| Malaysia | F=0.111, p=0.742, n=30 (paper draft). |
| Singapore | **Withdrawn; not evidence of anything even if reproduced.** The figure p=0.092 (lag 2, n=12) appears in `diagnostic_report_v3.txt`, `diagnostic_report_v4.txt`, `README.md`, `CHANGELOG.md` and `docs/archival_data_findings_2026-06-16.md`. Its provenance could not be traced: no committed script, command, or data snapshot that reproduces it was found, and the current `analysis_results/granger_results.json` lists SG with n=8, below the n=24 threshold. It also cannot have come from this registration's specification: n=12 levels gives 11 differences, 9 usable observations at lag 2, against 16 parameters (constant, 11 dummies, 4 lag terms), i.e. negative residual df. It must therefore have come from a different, much smaller specification (details unrecorded) with at most a handful of residual df. It is not cited as a result and is not counted as a prior run. A reproduction, if ever done, would be reported as exploratory. |
| Australia, Indonesia, UK | Below the n=24 threshold in `analysis_results/granger_results.json` (n=23, 20, 18); no test reported. |
| Thailand | No overlap with a monthly CPI series; no test. |
| Vietnam, UAE | Earlier Granger statistics (VN n=12, p=0.42; UAE n=47, F=0.016, p=0.90) were computed on corrupted Wayback slices and are withdrawn. |

**Published US specification, and why it is superseded.** The published US result comes from `gap_robustness.py`: CPI_chg(t) ~ 1 + CPI_chg(t−1) + UICPI(t−1), with ΔCPI the full-calendar month-over-month change and **UICPI entered in levels**. The choice of levels rests on a single ADF test on 31 to 38 observations (paper table: ADF p = 0.0000, "stationary in levels"), which is a pretest decision.
- If the UICPI level series is I(1), regressing the stationary ΔCPI on it makes the Granger F statistic **non-standard** (Sims, Stock and Watson 1990), so the reported p = 0.0499 does not have its nominal meaning under that specification. The project's own ADF classed the series as stationary, and this registration has not re-run it (no index values were viewed); so whether the published p-value is invalid depends on a pretest that a 31-observation ADF on a chain-linked index cannot settle.
- Either way the published specification cannot be relied on: its levels-versus-differences choice is data-dependent, it has no lag selection, no month dummies, no stationarity gate on UICPI, and its p-value sits at the 0.05 boundary with both permutation p-values above it (0.052, 0.069).
- This registration removes the question: both sides are log-differenced and passed through the ADF + KPSS gate (§4.2), and the lagged index never enters in levels.
- The published result's CPI series is OECD PRICES_CPI key `USA.M.HICP.CPI.IX._T.N._Z` (METHODOLOGY = `HICP`, "Eurostat harmonised index of consumer prices", 2015=100). Checked 2026-10-07 against the OECD SDMX API: the values stored in `monthly_cpi` (source label "OECD PRICES_CPI HICP monthly index", 120 rows, 2015-01 to 2024-12) equal that series for 2024-09 to 2024-12 (129.21, 129.43, 129.46, 129.47). So the "HICP" label is correct. It is **not** the BLS CPI-U: OECD's national series for the same months (`USA.M.N.CPI.IX._T.N._Z`) reads 133.03 to 133.18. The paper's "(BLS-derived)" description is not something I could confirm. The registered US outcome (BLS `CUUR0000SEFV`, headline `CPIAUCNS`) is a different series, so the published and registered US results are not comparable.

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

  No DoorDash-labelled live source exists. The largest open provenance gap is the `js` label (265,889 rows, about 4× the `wayback-doordash` count). `live_scraper.py` writes the literal `'js'` for every target routed through `scrape_js`, and that function is the handler for the `js`, `doordash`, `deliveroo`, `ubereats` and `gofood` target types (lines 1668, 1707-1711). So the label hides the platform, and nothing in the labels rules out DoorDash (or any other platform) inside `js`. The code history says live DoorDash returned nothing, but that is not a row-level check. `js` rows are also live-scraper output (residential-IP), which §8 already makes supplementary-only. **Rule adopted: `js` is quarantined from the confirmatory index entirely** (§8, §9 item 2) until its rows are broken down by platform from the scraper's logged URL or domain. The bare `wayback`, `Wayback/TripAdvisor` and `Wayback/wongnai` labels, and the non-restaurant `official_price_series_bls_apu`, show the source taxonomy has several label generations, which a whitelist must handle (§9 item 2).
- Many sweep snapshots parsed to "0 items" (e.g. a 97% zero-item rate on an earlier sweep). That affects coverage, not provenance.
- The exclusion rationale on record is explicitly "a deliberate scope decision, not a data-quality bail": delivery-platform prices embed fees and markup, and the pooled index diluted the Granger statistic.

**Resolution under the D1 rule:** the DoorDash data are archival, not circumvention-collected, so they are **included in the primary confirmatory index**. The exclusion is reported as a **labelled sensitivity analysis** (index built with `wayback-doordash` removed). The result-informed exclusion is not used for the primary. Expect this to change the US primary result relative to the published headline.

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

**Minimum detectable effect at n=36, with the 11 month dummies.**

*Degrees of freedom, and what n counts.* n is the number of monthly **levels** in the contiguous run (§4.5). n=36 levels gives 35 first differences. A VAR(p) loses p differences to lags, so each equation has T = 35 − p regression observations. There is **no trend term**. Each equation has a constant, 11 month dummies, and p lags of each variable (2p coefficients). Residual df of the unrestricted equation:

| Lag p | T = 35 − p | Parameters (1 + 11 + 2p) | **Residual df** |
|---|---|---|---|
| 1 | 34 | 14 | **20** |
| 2 | 33 | 16 | **17** |
| 3 | 32 | 18 | **14** |

(A calculation that counts all 35 differences at every lag, without losing p to lags, gives 21, 18, 15. That is a different convention; this registration uses T = 35 − p.)

*Minimum detectable effect (simulated).* Monte Carlo, `diagnostics/mde_simulation.py` (simulated data only, no project data; standard library; seed 20261007; 2,000 replications per grid point). Design: the residual df above, iid N(0,1) regressors and errors, the tested block's effect spread equally over its p lags, joint F test at α = 0.05. Effect size is the population partial R² of the lagged-index block. Interpolated **MDE at 80% power**:

| Lag p | Residual df | **Simulated MDE (partial R²)** | Power at partial R² = 0.30 |
|---|---|---|---|
| 1 | 20 | **0.31** | 0.78 |
| 2 | 17 | **0.40** | 0.64 |
| 3 | 14 | **0.49** | 0.50 |

The simulation's Monte Carlo error on each MDE is about ±0.01. These supersede the earlier hand approximations (about 0.20 at lag 1 and 0.30 at lag 3) and an analytic noncentral-F approximation (0.28, 0.37, 0.45), both of which understate the MDE relative to the simulation.

Reading: at n=36 a single country's Granger test can only detect a **very large** lead-lag effect (the lagged index explaining roughly 31% to 49% of the CPI variance left after the other regressors). A null at this n is not evidence of absence. This is before multiplicity correction, which only raises the MDE. The panel test (§6) pools countries and has more power, but how much depends on how many countries enter and on the common window; that is not quantified here. The code PR (§9 item 1) replaces the §3 table with the script's output and adds a size check, on simulated data only.

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

5.2 Permutation scheme (primary p-value for country-level tests): **Freedman–Lane with circular blocks of restricted-model residuals.** Permuting the raw index series would destroy its autocorrelation and misalign its seasonal pattern with the month dummies, so the null distribution would be wrong. Instead, for each country:
1. Fit the restricted model for the CPI equation: y on a constant, the 11 month dummies and p lags of y (no index lags). Keep its fitted values ŷ and residuals e.
2. Cut e (in calendar order) into circular blocks of length b, draw blocks with replacement and concatenate to the original length to get e*.
3. Form y* = ŷ + e*. Recompute the Granger F statistic from the unrestricted model with y* as the dependent variable and the **original, unpermuted** regressors (x lags, y lags, dummies). Regressors are held fixed, so x keeps its own autocorrelation and seasonality.
4. B = 9,999 draws, fixed seed recorded in the results commit. p = (1 + #{F* ≥ F_obs}) / (B + 1).

Holding the lagged-y regressors at their observed values is an approximation to a fully recursive scheme. The code PR (§9 item 1) must show by simulation on data generated under the null (an AR process for y, an independent autocorrelated x, with seasonality) that the rejection rate at α=0.05 is close to 5% for n=36 and n=100; if not, the scheme is revised before any real data are run. **Fallback, fixed now.** The size check is run on data simulated under the null at n=36 and at n=100. If the null rejection rate at α=0.05 falls **outside [0.03, 0.07] at either n**, the primary scheme is replaced by a **recursive restricted-model block bootstrap**: fit the restricted model, draw circular blocks of its residuals as above, and regenerate y* **recursively** (y*_t = restricted-model prediction using the already-generated y*_{t−1}, …, y*_{t−p}, the dummies, and e*_t, started from the observed first p values), then recompute F from the unrestricted model on the regenerated series (including its lagged y*). The switch is decided by the size check alone, on simulated data, before any real data are analysed, and is recorded in the results commit. The same switch applies to the panel bootstrap (§6). Permuting blocks of the raw x series is an exploratory robustness check only.

**D6 (as recommended):** b = ⌈n^(1/3)⌉ per country applied to the residual blocks above (n = number of regression observations), floor 3, cap 6. Report p at b±1 as an exploratory robustness line.

5.3 Multiplicity for the **secondary** country-level family. Within the family of countries from §3, for the primary outcome:
- Romano–Wolf stepdown adjusted p-values from the permutation distributions. Blocks are drawn on a common calendar index, so overlapping months share the same resampling and cross-country dependence is retained.
- Benjamini–Hochberg q-values on the permutation p-values, FDR 0.10.
- Both are reported next to the raw p and the permutation p, in the same row.

Country-level evidence is claimed only where the Romano–Wolf adjusted p < 0.05, and is labelled secondary. The headline-CPI outcome is its own family with its own adjustment and is never pooled.

## 6. Panel test (primary confirmatory test when the panel is large enough)

The **Dumitrescu–Hurlin (DH) panel Granger test is the primary confirmatory test, provided the panel has at least N_PANEL countries (D8).** It does not depend on any country reaching n ≥ 100. The country-level tests (§5) are secondary, except under the small-panel rule below.

- Panel: all countries meeting the §3 inclusion rule; same transforms (§4), month dummies, and NSA series.
- Statistic: the Z̃-bar statistic; W-bar also reported.
- **Window:** the **common calendar window**, the months for which every included country has a valid observation, so the panel is balanced.
- Lag: the common lag p from the BIC rule (§4.3) applied to the pooled panel.
- **Inference: bootstrap, never asymptotic.** DH's Z̃-bar relies on N → ∞ and assumes cross-sectional independence. At small N the normal approximation is not trustworthy, and food prices in neighbouring countries (SG, MY, TH, ID in particular) share common shocks. So the p-value used for the decision is a **bootstrap p-value that preserves cross-sectional dependence**: each draw applies the §5.2 Freedman–Lane scheme in every country, with the **same calendar-time blocks drawn once per draw and applied jointly to all countries' restricted residuals**, and recomputes Z̃-bar (and W-bar). B = 9,999. The asymptotic Z̃ p-value is reported but never used for a decision, at any N. (The code PR should compare this scheme against an existing implementation, such as the `xtgcause` bootstrap, on simulated panels with common shocks.)
- The code is written from Dumitrescu–Hurlin (2012) and committed.

**D8 (decided): N_PANEL = 4, with the small-panel rule.**
- If N ≥ 4: DH is the primary confirmatory test, as above.
- If N < 4 (including the likely case N = 2 if TH and ID stay unverified): DH is **still computed and reported, but as exploratory**, with bootstrap p only. The **primary confirmatory test becomes the country-level family** (§5): Romano–Wolf adjusted permutation p for N = 2 or 3, and a single unadjusted permutation p for N = 1. This is declared now and depends only on the data-count rule in §3, not on any result.
- If N = 0, or the common calendar window is shorter than 36 months, the panel cannot be run as registered. The run **stops and reports**; it does not shorten the threshold, drop countries post hoc, or substitute another test. The country-level tests are then still run on each country's own window and labelled secondary.

**D7 (decided):** panel on the common calendar window, calendar-time blocks applied jointly.

## 7. Confirmatory vs exploratory

"Confirmatory" here always means *pre-specified analysis of partially observed data* (§0).

- **Primary confirmatory (C1):** if N ≥ N_PANEL (D8), the Dumitrescu–Hurlin panel test, UICPI → restaurant / food-away-from-home CPI, with bootstrap p (§6). If N < N_PANEL, C1 is instead the country-level family below, with Romano–Wolf adjusted p (N = 2 or 3) or the single permutation p (N = 1), and DH is exploratory.
- **Secondary confirmatory (C2):** per-country Granger tests for countries in the §3 family, with raw p, Freedman–Lane block-permutation p, Romano–Wolf p and BH q (secondary when C1 is the panel).
- **Secondary confirmatory (C3):** UICPI → headline CPI (panel and per-country), its own family, labelled secondary.

Everything else is exploratory and must be labelled "exploratory" wherever it appears, including:

- The earlier US F=4.20 / p=0.0499 result (superseded specification, §0) and every other prior run in §0.
- The reverse direction, the DoorDash-excluded sensitivity index, SA-series runs, AIC and max-lag-4 runs, no-dummy runs, source-stratified or chain-vs-independent indices, other block lengths, and any country dropped by the §3 or §4.2 rules.
- The ADL pass-through models in the current code.
- The hawker fieldwork (descriptive only).
- Any specification change after this document is merged. Any such change is a **deviation**, listed in the results file with a reason.

## 8. Data provenance rule

- The confirmatory index uses only: archival data (Wayback Machine snapshots fetched via the raw-bytes `id_` path), data from public sites, and the hawker fieldwork. Every Wayback row carries its snapshot timestamp, original URL and CDX digest so each price is traceable.
- **DoorDash:** the D1 audit shows `wayback-doordash` is Internet Archive data collected without proxy or block circumvention, so it is **in** the confirmatory index. The DoorDash-excluded index is an exploratory sensitivity. If a later audit finds DoorDash rows from residential-IP or circumvented live access, those rows are removed from the confirmatory index.
- Residential-IP live-scrape data (`live_scraper.py`, nightly cron) is supplementary only. It may appear in clearly labelled exploratory figures and sensitivity analyses and never contributes to a confirmatory index level or test.
- The confirmatory index is built with an explicit source whitelist (§9 item 2); the current builder has no provenance filter. **The `js` source is quarantined entirely** (265,889 rows whose platform is hidden by the label; also live-scraper output). It may re-enter only after its rows are broken down by platform from the logged URL or domain, a rule is committed, and it is shown to contain no DoorDash or other circumvention-collected data; that change would be a deviation (§7) unless made before merge.
- Code is frozen at a commit SHA recorded in the results commit. If the specification cannot be executed as written, the run stops and reports. It does not improvise.

## 9. Code PRs required before the confirmatory run (none done yet)

1. **`granger_analysis.py` (or a new script) implementing this specification.** Today's script uses AIC (max lag 4), has no BIC rule, no month dummies, no Freedman–Lane residual-block permutation, no bootstrap panel scheme, no ADF+KPSS gate, no Ljung–Box diagnostic, no circular-block permutation (b=⌈n^(1/3)⌉, B=9,999), no Romano–Wolf or BH, no Dumitrescu–Hurlin panel, and no calendar-true contiguous-run handling; it also interpolates AU. Includes a scripted power calculation (replacing the §3 table's hand-entered values) and null-simulation size checks of the §5.2 scheme and the §6 bootstrap (n=36, n=100; panels with common shocks), with the [0.03, 0.07] rule that triggers the §5.2 recursive-bootstrap fallback, all on simulated data.
2. **Provenance whitelist in `index_builder.py`.** Add an explicit source whitelist for the confirmatory index (archival `wayback-*` and public-site sources only; live-scrape sources excluded, **`js` quarantined entirely**, §8), handling every label generation present in `prices` (including `wayback`, `Wayback/TripAdvisor`, `Wayback/wongnai`, and excluding non-restaurant `official_price_series_bls_apu`). Enforce the ≥15 matched-restaurant rule per country-month, emit missing months as missing (no carry-forward), and make `EXCLUDED_SOURCES` a switch so the D1 sensitivity index comes from the same code path.
3. **Monthly CPI ingestion for the five countries.** Wire the monthly NSA restaurant/food-away-from-home series into the CPI pipeline (`get_monthly_cpi_all.py` currently loads headline/food and falls back to World Bank annual): US `CUUR0000SEFV`, GB `D7EW`, SG `M213751` row `1.11`, MY `cpi_3d` group `111`, and TH and ID once verified (§2). Record the series ID, vintage, and fetch date; implement the §2 rebasing/splicing rule. Remove AU interpolation from the primary path.

## 10. Pre-merge checklist

- [ ] TH and ID: WC to supply raw files; verify series ID, start date, NSA status, and any rebasing break (§2), then remove the VERIFY tags.
- [ ] Record the merge commit SHA as the registered version.

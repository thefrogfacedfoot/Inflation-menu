# UICPI Pre-registration, v1 (DRAFT)

Status: DRAFT for review. Becomes binding when merged; the merge commit SHA is the registered version.
Drafted: 2026-10-07. No analysis was run, no new data was queried, and no index values were viewed while writing this document.

Items marked **DECISION FOR WC** are open choices. Each has a recommendation, written as the default. They must be resolved (the text edited to the final value) before merge.
Items marked **VERIFY** are factual details about official series that must be confirmed against the publisher before merge. They were not looked up while drafting.

## 0. Disclosure of prior looks

The authors have already seen results from earlier versions of this pipeline. These are not blinded.

- A US Granger result was seen, then respecified. The calendar-true respec gave F=4.20, p=0.0499. The earlier F=6.03, p=0.021 was deprecated for gap-mixing.
- DoorDash (`wayback-doordash`, `index_builder.EXCLUDED_SOURCES`) was excluded from index construction after it was observed to dilute the US Granger signal. This exclusion was result-informed.
- Earlier per-country Granger outputs are archived in `docs/granger_results_2026-06-18.md` and are treated as seen.

Consequence: the confirmatory value of this registration comes from fixing the specification, family, and inference *before* the extended Wayback backfill data are analysed. It does not come from the earlier US result being unseen. The US result is exploratory-prior and is not counted as confirmatory evidence.

**DECISION FOR WC (D1): DoorDash.**
Recommendation: the primary index excludes DoorDash only if you can state a data-quality reason that does not mention the Granger outcome, and that reason is written here before merge. Otherwise the primary index includes it. Either way, report the other variant as a labelled sensitivity analysis.
Reason: an exclusion chosen because it improved F is a researcher degree of freedom, and a reviewer will find it in the git history.

## 1. Primary hypothesis

- H1: the lagged monthly change in the UICPI menu-price index contains information about the future monthly change in the official restaurant / food-away-from-home CPI, beyond that CPI's own lags. The direction is UICPI → official CPI.
- H0: all coefficients on lagged Δlog UICPI are zero in the equation for Δlog CPI, conditional on lagged Δlog CPI.
- Test statistic: the Wald/F statistic of the Granger exclusion restriction, in a bivariate VAR(p) estimated by OLS.
- Granger tests are two-sided in the coefficients (a joint F test). There is no one-sided variant.
- The reverse direction (CPI → UICPI) is exploratory.

## 2. Outcome variables

Primary outcome: the official restaurant / food-away-from-home CPI, monthly. Secondary outcome: headline all-items CPI.

| Country | Primary series (source) | Series ID | Frequency / known issues |
|---|---|---|---|
| US | CPI-U Food away from home, NSA (BLS) | `CUUR0000SEFV` | Monthly. Headline: `CUUR0000SA0`. |
| GB | CPI 11.1 Restaurants & cafés index (ONS, dataset MM23) | **VERIFY** | Monthly. Headline: `d7bt` (already used in the code). Check for a COICOP-2018 reclassification break. |
| AU | ABS CPI: "Meals out and take away foods" | **VERIFY** | **Flag:** historically quarterly. ABS complete monthly CPI is believed to exist only from a 2024 back-cast. Before that, only quarterly or partial indicator data exist. The current pipeline linearly interpolates quarterly values. That is not a monthly observation and is **not permitted** here. |
| SG | SingStat CPI, "Food serving services" | **VERIFY** (table ID) | Monthly. **Flag:** base-year rebasing break. |
| MY | DOSM CPI, division 11 Restaurants & accommodation services (OpenDOSM / data.gov.my) | **VERIFY** (dataset ID; the code uses `cpi_headline` for headline) | Monthly. Check for a COICOP-2018 reclassification break. |
| IN | MoSPI CPI (Combined), "Prepared meals, snacks, sweets" | **VERIFY** | Monthly. **Flag:** base change (2012 → 2024) is a series break. The OECD key currently used has no restaurant component. |
| ID | BPS IHK, prepared food, beverages and tobacco subgroup | **VERIFY** | Monthly, but the subgroup is broader than restaurants. Likely "limited". |
| TH | MoC / TPSO CPI, prepared food or restaurant component | **VERIFY** | Monthly if located. Currently only World Bank annual CPI is used. Likely "limited". |
| AE | FCSC CPI, restaurants & hotels | **VERIFY** | Not in the current CPI pipeline. |
| VN | GSO CPI, "eating out" component | **VERIFY** | Not in the current CPI pipeline. |

Rules:

- Any country whose primary series is not monthly over the whole analysis span is excluded from the confirmatory family (§3). It is not interpolated.
- A series break (rebasing, reclassification) is handled by splicing only if the publisher provides an official linking factor. Otherwise the series is cut at the break and the longest clean contiguous run is used.
- Countries currently covered only by World Bank annual CPI (SG, MY, GB, TH, ID in the current code) cannot enter the family until a monthly official series is wired into the pipeline.
- Headline CPI is a secondary outcome. It has its own multiplicity family (§5) and is labelled "secondary".

## 3. Test family (inclusion by rule)

A country is in the confirmatory family if and only if it meets ALL of:

1. n ≥ **N_MIN** calendar-true monthly observations (definition in §4.5).
2. A monthly official primary series exists over that span (§2).
3. The index for that country is reproducible from committed code and public or archival data (§8).
4. At least 15 matched restaurants per country-month. Matched means the same restaurant observed in both month t and t−1. This was decided on 2026-10-07. Months below 15 count as missing, not as low-quality observations.

Inclusion is evaluated on data counts only (series length, restaurant counts), by a script that does not compute any index-vs-CPI statistic. The resulting country list is committed before any test is run.

**DECISION FOR WC (D2): N_MIN.**
Recommendation: **36** (months of valid index levels).
Reason: with max lag 3 and one exclusion block of the same length, 36 leaves roughly 30 residual degrees of freedom. That is enough for the F-distribution to be roughly sensible and for permutation inference to have a meaningful grid. The existing code's default of 8 is not credible. 24 is the minimum I would defend. 60 would likely leave only one or two countries.
Note: the n≥100 threshold in §6 is a separate, higher bar that decides which headline test is primary.

## 4. Specification (fixed)

4.1 Transform. Let I_t be the index level and C_t the CPI level. Use x_t = Δlog I_t = log I_t − log I_{t−1} and y_t = Δlog C_t. Both are defined only if both months t and t−1 are real observations.

4.2 Stationarity. Run the ADF test (constant, lag length by AIC) and the KPSS test (level stationarity) on x and y within each country's analysis window. Each series is classed stationary if ADF p < 0.05 AND KPSS p > 0.05.
- If both x and y are stationary: proceed.
- If either fails: difference that series once more, within the contiguous run, and re-test. If it still fails, the country is dropped from the confirmatory family and reported as exploratory with a note. The test outcome decides the family, not the Granger result.
- The stationarity decision uses the full-window series, not rolling windows.

**DECISION FOR WC (D3): stationarity rule.**
Recommendation: require both ADF and KPSS agreement, as above.
Reason: ADF alone has low power at n≈36–100. Requiring both guards against "borderline" series passing silently. The cost is some countries dropped to exploratory.

4.3 Lag selection. One rule, applied identically to every country.

**DECISION FOR WC (D4): lag rule and maximum lag.**
Recommendation: select p by **BIC** on the unrestricted bivariate VAR of (y, x), p ∈ {1,…,**3**}. Ties go to the smaller p. Use this p for the Granger test.
Reason: BIC is more parsimonious than the AIC the current code uses, which matters at n≈36–60. A max of 3 months fits the plausible pass-through horizon and keeps degrees of freedom. The alternative is AIC with max lag 4, which is the current code's default and is likelier to over-fit.

4.4 Calendar-true alignment only.
- The monthly index is aligned to the official CPI by calendar month. No gap-mixing: a lag never spans a missing month, so a "lag 1" difference is always exactly one calendar month apart.
- Regressions use only (y_t, x_t, lags) windows where every month in the window is a real observation.

4.5 Months with no real observation. A month with fewer than 15 matched restaurants, or with no data, is MISSING. Missing months are never forward-filled, interpolated, or carried. A carried value is never counted as an observation.

**DECISION FOR WC (D5): how to use a series that has gaps.**
Recommendation: use the **longest single contiguous run** of valid months per country, and define n as the number of months in that run (levels, before differencing).
Reason: simple, unambiguous, and cannot mix gaps. The alternative is to stack all contiguous segments and use every window that fits inside one. That keeps more data, but segment-boundary handling adds complexity and an extra place to make choices after the fact.

4.6 Seasonality. No seasonal adjustment and no month dummies. Both series are Δlog of non-seasonally-adjusted data (use NSA official series where published). Residual seasonality is checked exploratorily only.

4.7 Sensitivity analyses (all exploratory unless listed in §7): the DoorDash variant (D1), AIC vs BIC, max lag 4, reverse direction, source-stratified indices.

## 5. Inference

5.1 Raw p-value: the asymptotic F-test p-value, always reported next to the permutation p.

5.2 Circular-block permutation (primary p-value). The permuted object is the x series. Cut it into circular blocks of length b, draw blocks with replacement and concatenate them to the original length, then recompute the F statistic. y is not permuted. This preserves the within-series autocorrelation of x and breaks its relation to y. Use B = 9,999 draws and a fixed seed written in the results commit. The p-value is (1 + #{F* ≥ F_obs}) / (B + 1).

**DECISION FOR WC (D6): block length b.**
Recommendation: **b = ⌈n^(1/3)⌉** per country (n = number of differenced observations, so b≈4 at n≈60 and 5 at n≈100), with a floor of 3 and a cap of 6. Report p at b±1 as a robustness line, labelled exploratory.
Reason: n^(1/3) is the standard rate for dependent-data block lengths. A fixed b=6 over-blocks short series.

5.3 Multiplicity across the declared family. Within the family of countries from §3, for the primary outcome:
- Romano–Wolf stepdown adjusted p-values, built from the permutation distributions. Blocks are drawn on a common calendar index, so overlapping months share the same resampling and the cross-country dependence is retained.
- Benjamini–Hochberg q-values on the permutation p-values. FDR level 0.10, reported as secondary.
- Both are reported next to the raw p and the permutation p, in the same row.

Confirmatory decision rule: country-level evidence is claimed only where the Romano–Wolf adjusted p < 0.05. The headline CPI secondary outcome is its own family with its own Romano–Wolf and BH adjustment, and never pooled with the primary family.

## 6. Panel alternative

Dumitrescu–Hurlin panel Granger test over all included countries (§3), with the same transforms (§4) and the same lag rule (§4.3).

**Declared now as the primary test if fewer than 3 included countries reach n ≥ 100** (n as in §4.5). In that case the per-country tests are reported as confirmatory-secondary, with the multiplicity adjustment in §5.3. If 3 or more countries reach n ≥ 100, the per-country family (§5.3) is primary and the panel test is confirmatory-secondary.

- Statistic: the Z̃-bar (small-T standardised) statistic. Report W-bar as well.
- Lag: the common lag p from the BIC rule applied to the pooled panel, rather than a per-country lag.
- Because countries have unequal spans, the p-value comes from the same calendar-block permutation as §5.2. This handles cross-sectional dependence and unbalanced panels, instead of relying on the asymptotic Z̃ distribution.
- The code is written from the Dumitrescu–Hurlin (2012) paper and committed. There is no standard Python implementation to import.

**DECISION FOR WC (D7): panel lag and p-value.**
Recommendation: common lag from the pooled BIC and permutation p-values, as above.
Reason: it keeps one lag rule and avoids the known size distortion of asymptotic Z̃ under cross-sectional dependence.

## 7. Confirmatory vs exploratory

Confirmatory (the only claims the registration supports):

- C1. Per-country Granger test, UICPI → restaurant / food-away-from-home CPI, for countries in the §3 family, with raw p, block-permutation p, Romano–Wolf p and BH q (primary if ≥ 3 countries reach n ≥ 100, secondary otherwise).
- C2. The Dumitrescu–Hurlin panel test (primary if fewer than 3 countries reach n ≥ 100, secondary otherwise).
- C3. Secondary outcome: UICPI → headline CPI, its own family, labelled secondary.

Everything else is exploratory and must be labelled "exploratory" wherever it appears. This includes:

- The earlier US F=4.20 / p=0.0499 result.
- The reverse direction, DoorDash and AIC sensitivity runs, source-stratified or chain-vs-independent indices, other lags or block lengths, and any country dropped by the §3 or §4.2 rules.
- The ADL pass-through models in the current code.
- The hawker fieldwork (descriptive only).
- Any specification change made after this document is merged. Any such change is a **deviation**, listed in the results file with a reason.

## 8. Data provenance rule

- The confirmatory index uses only: archival data (Wayback Machine snapshots fetched via the raw-bytes `id_` path), data from public sites, and the hawker fieldwork. Every Wayback row must carry its snapshot timestamp, original URL and CDX digest so each price is traceable.
- Residential-IP live-scrape data (`live_scraper.py`, nightly cron) is supplementary only. It may appear in clearly labelled exploratory figures and sensitivity analyses. It may never contribute to a confirmatory index level or a confirmatory test.
- The index builder must be run with an explicit source whitelist for the confirmatory index. This is a code change to be reviewed before the confirmatory run. The current builder does not have a provenance filter.
- The confirmatory index code and the Granger/permutation code are frozen at a commit SHA recorded in the results commit. Today's `granger_analysis.py` does not implement this specification (it uses AIC, no permutation, and interpolated AU data), so a new script is required. If the specification cannot be executed as written, the run stops and reports. It does not improvise.

## 9. Pre-merge checklist

- [ ] Resolve D1–D7 and edit the chosen values into the text.
- [ ] Verify and fill every **VERIFY** series ID and frequency note in §2.
- [ ] Record the merge commit SHA as the registered version.

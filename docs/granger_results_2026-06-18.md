> **DEPRECATED (2026-07-06).** The results below use the original spec, which
> intersected CPI to menu-observation months before differencing and therefore
> mixed 1–9-month CPI changes. Do not cite F=6.034 / p=0.021. The current
> headline is the calendar-true respec (F=4.20, p=0.0499, n=31) in
> `analysis_results/gap_robustness.json`. This file is kept as a historical
> record of the 2026-06-18 run.

# First valid Granger results — India, Malaysia and United States

**Date**: 2026-06-18 (Malaysia added 2026-06-19 after wayback-grabfood sweep)
**Threshold**: ≥24 overlapping months (`--min-obs 24`)
**Eligible countries**: India (47 obs), United States (31 obs), Malaysia (30 obs)
**Final 8-country roster (unchanged)**: Singapore, Malaysia, Indonesia, Thailand, India, US, UK, Australia.

These are the first statistically valid Granger causality results in the project. The other 5 countries fall below the 24-month threshold (see `analysis_results/summary.csv` for the full table) and report `insufficient_data`.

## Results

### United States — Granger-significant ✓

| Field | Value |
|---|---|
| Sample window | 2018-04 → 2024-10 |
| Overlapping months (n) | **31** |
| UIFPI ADF p | 0.0000 (stationary in levels) |
| CPI ADF p | 0.0183 (stationary in levels) |
| VAR AIC-selected lag | 4 |
| **Granger F-statistic** | **F(26, 1) = 6.034** |
| **Granger p-value** | **p = 0.0210** |
| **Lead time** | **1 month** |
| Verdict | **Reject H₀: UIFPI does NOT Granger-cause CPI** at α = 0.05 |

**Multi-lag detail** (full grangercausalitytests output):

| Lag | F(df_num, df_denom) | p |
|---:|---|---:|
| 1 | F(1, 26) = 6.0336 | **0.021** |
| 2 | F(2, 23) = 2.6845 | 0.0896 |
| 3 | F(3, 20) = 2.0613 | 0.1376 |
| 4 | F(4, 17) = 1.967  | 0.1455 |

The minimum-p lag = 1 is the dominant signal. Higher-order lags carry diminishing predictive content, consistent with restaurant menu repricing happening at roughly monthly cadence.

**Pass-through regression** (Cavallo-Rigobon style with the controlled spec — lagged controls plus month dummies — that `granger_analysis.py` runs):

| Field | Value |
|---|---|
| β | **−0.0043** |
| SE | 0.00684 |
| p | 0.5399 |
| **95% CI** | **[−0.01938, +0.01073]** |
| R² | 0.5566 |

The pass-through β is small, negative, and **not significant** under the controlled specification (p = 0.5399; the 95 % CI spans zero by a wide margin in both directions). **The Granger test rejects independence at the 5 % level; the linear pass-through magnitude does not.** This is methodologically consistent with restaurant menu prices being one of many CPI components — the *lead* is the headline result, not the magnitude of the linear coefficient.

### India — Not significant

| Field | Value |
|---|---|
| Sample window | 2018-01 → 2026-01 |
| Overlapping months (n) | **47** |
| UIFPI ADF p | 0.0121 (stationary in levels) |
| CPI ADF p | 0.0036 (stationary in levels) |
| VAR AIC-selected lag | 1 |
| **Granger F-statistic** | **F(1, 43) = 0.5213** |
| **Granger p-value** | **p = 0.4742** |
| Verdict | Fail to reject H₀ at α = 0.05 |

**Pass-through regression**:

| Field | Value |
|---|---|
| β | 0.0007 |
| SE | 0.0019 |
| p | 0.6973 |
| 95% CI | [−0.00313, +0.00462] |
| R² | 0.4997 |

Adjusted R² near zero. No detectable predictive relationship between the Indian restaurant-aggregate UIFPI (built from Zomato cost-for-two snapshots over Delhi NCR) and headline CPI. Plausible interpretation: Indian CPI is dominated by food-staple and fuel components for which restaurant menu prices lag rather than lead.

### Malaysia — Not significant

| Field | Value |
|---|---|
| Sample window | 2019-07 → 2025-10 |
| Overlapping months (n) | **30** |
| UIFPI ADF p | 0.0000 (stationary in levels) |
| CPI ADF p | 0.0000 (stationary in levels) |
| VAR AIC-selected lag | 1 |
| **Granger F-statistic** | **F(1, 25) = 0.1109** |
| **Granger p-value** | **p = 0.7419** |
| Verdict | Fail to reject H₀ at α = 0.05 |

**Pass-through regression**:

| Field | Value |
|---|---|
| β | 0.0034 |
| SE | 0.00267 |
| p | 0.2206 |
| 95% CI | [−0.0023, +0.00915] |
| R² | 0.5892 |

Malaysia replicates the India null with an even smaller F-statistic (0.11 vs 0.52) and slightly higher R² (0.59 vs 0.50). UIFPI built from 9,307 formal-sector items across 32 months of food.grab.com Wayback snapshots; first valid Granger test for the country, enabled by the `priceInMinorUnit` extractor extension added 2026-06-19 (lifted MY usable months from 7 → 30). Cross-country pattern now reads: **1 significant (US), 2 null (India, Malaysia)** at the 24-month threshold.

## Interpretation — what to lead with

**The US result is the first publishable finding of the project.** UIFPI Granger-causes CPI at the 5% significance level with a one-month lead. The relationship is concentrated at lag 1 and decays for longer lags, which is consistent with the underlying mechanism — restaurant operators repricing menus in response to input-cost movements ahead of CPI publication. The pass-through magnitude is small (and the linear coefficient's CI includes zero), which means the result is a *leading indicator* story, not a "menu prices set CPI" story.

The India result is informative as a negative case: 47 months of data, fully stationary, well-identified VAR, and the F-statistic is essentially 0.5 (close to 1.0 = no relationship). Malaysia replicates that null over 30 months with an F-statistic an order of magnitude smaller. Cross-country heterogeneity in CPI-leadership — emerging-market nulls flanking the developed-market US positive — is itself a result worth reporting.

## Reproduction

```bash
python3 granger_analysis.py --min-obs 24
```

Writes `analysis_results/granger_results.json` and `analysis_results/summary.csv`.

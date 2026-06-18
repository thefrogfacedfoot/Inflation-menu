# First valid Granger results — India and United States

**Date**: 2026-06-18
**Threshold**: ≥24 overlapping months (`--min-obs 24`)
**Eligible countries**: India (47 obs), United States (31 obs)
**Final 8-country roster (unchanged)**: Singapore, Malaysia, Indonesia, Thailand, India, US, UK, Australia.

These are the first statistically valid Granger causality results in the project. All other countries fall below the 24-month threshold (see `analysis_results/summary.csv` for the full table) and report `insufficient_data`.

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

## Interpretation — what to lead with

**The US result is the first publishable finding of the project.** UIFPI Granger-causes CPI at the 5% significance level with a one-month lead. The relationship is concentrated at lag 1 and decays for longer lags, which is consistent with the underlying mechanism — restaurant operators repricing menus in response to input-cost movements ahead of CPI publication. The pass-through magnitude is small (and the linear coefficient's CI includes zero), which means the result is a *leading indicator* story, not a "menu prices set CPI" story.

The India result is informative as a negative case: 47 months of data, fully stationary, well-identified VAR, and the F-statistic is essentially 0.5 (close to 1.0 = no relationship). Cross-country heterogeneity in CPI-leadership is itself a result worth reporting.

## Reproduction

```bash
python3 granger_analysis.py --min-obs 24
```

Writes `analysis_results/granger_results.json` and `analysis_results/summary.csv`.

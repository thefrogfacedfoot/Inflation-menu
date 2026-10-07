# Pre-registration implementation notes

Companion to `docs/preregistration.md` (registered version: merge commit `bd859403`).
These notes record implementation choices the registration leaves open, and how the registered size-check contingency resolved. They add no hypothesis, outcome, family or threshold. They are filed before the Wayback backfill is built or any confirmatory test is run.

Code: analysis module PR #45 (`prereg_analysis.py`), provenance whitelist PR #43 (`index_builder.py`), official CPI ingestion PR #44 (`official_cpi_prereg.py`). Where these notes and the merged code differ, the registered text governs and the difference is a deviation.

## 1. Choices left open by the registration

1. **D5 ties (longest contiguous run).** If two runs of valid months have equal length, the **earliest** run is used. "Valid month" means both the index and the official series have a positive level in that calendar month. n is the number of monthly levels in the run.

2. **BIC lag selection (D4).** The criterion is the Gaussian system criterion for the unrestricted bivariate VAR(p) of (Δlog CPI, Δlog index), both equations with the same regressors (constant, 11 month dummies, p lags of each variable):
   `BIC(p) = ln|Σ̂_p| + k_p ln(T) / T`, where Σ̂_p is the residual covariance matrix (divided by T) and k_p is the total number of coefficients in the system.
   To compare p on equal footing, every p in {1, 2, 3} is evaluated on a **common sample**: the first 3 differences are dropped for all p. Ties go to the smaller p. The Granger test at the selected p then uses all rows available at that p (T = 35 − p for n = 36). For the panel, the common lag minimises the sum of the per-country BIC values.

3. **Romano-Wolf statistic.** The registration says Romano-Wolf is "built from the permutation distributions". Implemented as the **minP stepdown on permutation p-values**, not on raw F statistics, because F statistics with different degrees of freedom are not comparable across countries. Each draw's null p-value for country k is its rank within that country's own null distribution. Adjusted p-values are monotone (running maximum) and floored by the unadjusted permutation p-value.

4. **Shared block starts across countries (§5.3, §6).** For the country-level family, one set of random circular-block start positions on the union calendar is drawn per bootstrap draw and shared by all countries. Block length is per country (`b = clip(ceil(T^(1/3)), 3, 6)`, T = the country's regression observations). Each country maps the draw's calendar source positions into its own regression window by modulo, so months inside a country's window are resampled identically wherever countries overlap. For the panel, all countries share the common calendar window, one block length (from the common window's T), and identical resampled indices in every draw.

5. **Earliest overlap month for splicing (§2).** When two vintages of an official series overlap in more than one month, they are chain-linked at the **earliest** overlap month: the older vintage is scaled by (new level / old level) at that month and used for earlier months; the new vintage is used from that month on. With no overlap month, the join is a series break, flagged on the first month of the new vintage, and D5 applies.

## 2. Size-check outcome: registered contingency invoked

§5.2 registers a size check on simulated null data at n = 36 and n = 100 and a fallback if the rejection rate at 5% falls outside [0.03, 0.07]. The check is `diagnostics/prereg_size_check.py` (seed 20261008, 2,000 replications; results files `diagnostics/prereg_size_check_*.txt` in PR #45). The primary Freedman-Lane scheme's country-level rate was **0.074 at n = 36**, outside the interval, so **the registered contingency was invoked** (this is the registered procedure operating, not a deviation). The recursive restricted-model block bootstrap is therefore the primary scheme for country-level and panel tests, and **no further switching will occur**, whatever later size results show.

Size results as limitations (rejection rate at nominal 5%, 2,000 replications; ± is the 95% Monte Carlo half-width):

| scheme / DGP | country n=36 | country n=100 | panel n=36 (N=4) | panel n=100 (N=4) |
|---|---|---|---|---|
| Freedman-Lane, base DGP (B=9999 country, 1999 panel) | **0.0740** | 0.0530 | 0.0655 | 0.0425 |
| **Recursive (primary)**, base DGP (B=999) | 0.0675 | 0.0510 | 0.0540 | 0.0395 |
| Recursive, persistent CPI, AR(y)=0.9 (B=999) | 0.0680 | 0.0520 | 0.0550 | 0.0460 |
| Recursive, stochastic seasonality, lag-12 term 0.5 (B=999) | **0.0975** | **0.1740** | **0.0775** | **0.2985** |

Panel DGPs share an i.i.d. common shock across countries (cross-sectional dependence with the null true). Under the base and persistent DGPs every recursive rate is inside [0.03, 0.07]. **Under stochastic seasonality the recursive test is badly over-sized, increasingly so at n = 100.** Month dummies absorb deterministic seasonality exactly but not a lag-12 dependence, and the registered maximum lag of 3 cannot model it, so lagged index terms pick up omitted dynamics; the recursive bootstrap resamples residuals of the same misspecified model and does not repair this. A rejecting Ljung-Box(12) diagnostic (reported only) is the warning sign; results must then be read with this limitation in mind. This is a limitation, not a specification change. (An earlier version of the simulation used a serially correlated common factor in the panel levels, which makes the null false; those panel numbers were discarded. The country-level Freedman-Lane figure that triggered the contingency did not depend on it.)

These come from one family of simulated data-generating processes; actual size on the real series is not known. At n = 36 a single country's test has 14 to 18 parameters on 32 to 34 observations, and even the asymptotic F test is over-sized there (0.075).

## 3. Other implementation facts

- **Diagnostics.** Ljung-Box at lag 12 is computed on both equations' residuals (degrees of freedom adjusted for the fitted lags) and reported only; it never changes the specification.
- **Differences and missing months.** A first difference exists only if both calendar months have a value. No month is filled, interpolated or carried forward, at any stage (index, official series, regression rows).
- **Stationarity.** ADF (constant, lag length by AIC) and KPSS (level, automatic bandwidth) on Δlog of each series within the run; both must pass for the country to be in the confirmatory family (ADF p < 0.05 and KPSS p > 0.05).
- **Fieldwork.** The hawker fieldwork is descriptive-only and is **not an index input**. §8 of the registration lists fieldwork among the confirmatory inputs; this note narrows that: no fieldwork row enters any confirmatory index.
- **Provenance whitelist.** Confirmatory mode admits only source labels beginning with `wayback` (case-insensitive). Everything else, including `js`, is quarantined with its row counts logged. The `MAX_ROWS_PER_COUNTRY` cap is not applied in confirmatory mode; what it would have dropped is logged per country-month.
- **Matched-restaurant rule.** A country-month's matched count is the number of restaurants observed in both that month and the calendar-adjacent previous month; a month whose predecessor has no data has count 0. Country-months below 15 have no index row.
- **Dumitrescu-Hurlin cross-check.** The module's W-bar, Z-bar and Z-tilde were checked against R `plm::pgrangertest` (plm 2.6.3, R 4.2.3) on a simulated balanced panel (N = 6, T = 60, lag 2, no dummies): W-bar 4.389292, Z-bar 2.926273, Z-tilde 2.618628 in both. Z-tilde uses T equal to the observations after lags (58 here), as in plm.

## 4. Not yet decided (needs registration or amendment before the backfill build)

- Which index aggregation method is the confirmatory index. The builder's default (`restaurant-median`) is not a matched design, and its matched-model path pairs each month with the previous *observed* month, which can span a calendar gap. The ≥15 matched-restaurant filter removes the first month after any gap but does not settle the method.

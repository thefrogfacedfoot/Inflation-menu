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
- **US official series, October 2025.** The restaurant series (`CUUR0000SEFV`) and headline (`CPIAUCNS`) have no value for 2025-10 (checked on the FRED mirror of BLS data on 2026-10-07); GB, SG and MY have no missing months. Cause: BLS's own notice, "2025 Federal Government Shutdown Impact on CPI" (https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi.htm), states "BLS did not collect CPI data from October 1, 2025, through November 12, 2025" and that "Missing CPI data affected October and November 2025 indexes". (BLS regional releases are reported to say the November 2025 indexes were computed against carried-forward October prices; that sentence was not on the notice page fetched here and is not independently confirmed.) **Pre-data clarification: US 2025-11 is treated as missing, as 2025-10 is.** BLS describes both the October and November 2025 indexes as affected, so neither is used. **No US window spans 2025-10 or 2025-11**: the US run is cut at 2025-09 (levels through 2025-09), and any later US run would start no earlier than 2025-12, with the first usable Δlog at 2026-01 (the 2025-12 level is a usable level, but its change from the missing 2025-11 is undefined). Calendar-true: no month is filled, interpolated or carried. D5 then applies as usual.
- **Provenance whitelist.** Confirmatory mode admits only source labels beginning with `wayback` (case-insensitive). Everything else, including `js`, is quarantined with its row counts logged. The `MAX_ROWS_PER_COUNTRY` cap is not applied in confirmatory mode; what it would have dropped is logged per country-month.
- **Matched-restaurant rule.** A country-month's matched count is the number of restaurants observed in both that month and the calendar-adjacent previous month; a month whose predecessor has no data has count 0. Country-months below 15 have no index row.
- **Dumitrescu-Hurlin cross-check.** The module's W-bar, Z-bar and Z-tilde were checked against R `plm::pgrangertest` (plm 2.6.3, R 4.2.3) on a simulated balanced panel (N = 6, T = 60, lag 2, no dummies): W-bar 4.389292, Z-bar 2.926273, Z-tilde 2.618628 in both. Z-tilde uses T equal to the observations after lags (58 here), as in plm.

## 3b. Commitment: every p-value is reported with the test's simulated size

Every reported p-value (country-level raw, permutation, Romano-Wolf, BH; panel bootstrap) is shown **in the same table row** as the simulated size of that test at that country's n (the panel's common-window n for panel results), under the **base** and **seasonal_ar12** DGPs, taken from the primary (recursive) scheme's size check at the nearest simulated n (n = 36 or n = 100; for other n the size check is re-run at that n with the same DGPs, seed rule and B = 999, 2,000 replications, before the result is reported). Currently:

| n | base, country | seasonal_ar12, country | base, panel | seasonal_ar12, panel |
|---|---|---|---|---|
| 36 | 0.0675 | 0.0975 | 0.0540 | 0.0775 |
| 100 | 0.0510 | 0.1740 | 0.0395 | 0.2985 |

(rejection rate at nominal 0.05; the full tables with Monte Carlo half-widths are in §2.) This is a reporting commitment only: it changes no test and no decision rule.

## 4. Decided: the confirmatory index method

The confirmatory index is a **matched-model index on calendar-consecutive months only** (never the previous *observed* month). Implemented as the only confirmatory path in `index_builder.py` (PR #43, `build_confirmatory_index`):
1. Item relative: the median price of a (restaurant, item, currency) in month t divided by its median in month t-1, for items present in both months. Prices are local currency. Repeated captures of an item within a month are reduced by the median. Item names are matched after trimming and case-folding.
2. Restaurant relative: the geometric mean of that restaurant's item relatives.
3. Month relative: the geometric mean of restaurant relatives across restaurants, with **equal restaurant weights** (no sector weights, no item weights).
4. Chained: level_t = level_{t-1} x relative_t. A country-month has a row only if at least 15 restaurants were observed in both t and t-1 (§3 rule 4) and at least one restaurant has a matched item; otherwise it is missing (no row, no carry-forward). A gap restarts the chain at 100, so no relative ever bridges a missing month, and the analysis uses within-run differences only.

The builder's default `restaurant-median` method and its previous-observed-month matched model are **not** confirmatory paths.

### Pre-data clarification: "matched restaurants" means contributing restaurants
§3 rule 4 requires at least 15 matched restaurants per country-month and defines "matched" as observed in both month t and month t-1. This note clarifies the definition: a **matched restaurant is a restaurant with at least one item priced in both months** (a *contributing* restaurant: one that enters the index). A restaurant seen in both months but sharing no item with the previous month does not count. The weaker count (observed in both months) is still logged as `matched_restaurants` next to `contributing_restaurants`; the threshold of 15 is applied to `contributing_restaurants`. This is stricter than the literal registered wording, so it can only remove country-months, never add them. Implemented in PR #43 (`build_confirmatory_index`) with synthetic tests (20 restaurants observed in both months, 14 contributing => missing; 15 contributing => kept).

## 5. Proposed pre-data amendment: seasonal-misspecification flag

**Status: proposed, not yet registered. No menu data have been used for any evidence below.**

### Motivation
The registered specification handles seasonality with 11 month dummies and a maximum lag of 3. That absorbs deterministic seasonality but not seasonal *dependence* at lag 12. In simulation (§2 table) the recursive test is badly over-sized under lag-12 stochastic seasonality (country level 0.0975 at n = 36 and 0.174 at n = 100; panel 0.0775 and 0.2985, against a nominal 0.05). A flag is therefore proposed so that results obtained under visible seasonal misspecification are not read as confirmatory.

### Proposed rule
If the Ljung-Box(12) diagnostic on a country's unrestricted y-equation residuals rejects at 5%, that country's country-level result is reported as **"not interpretable — seasonal misspecification"**. If it rejects for **any** country in the panel, the panel result is **exploratory**. The diagnostic never changes the specification.

### Evidence 1: the official series (official data only)
`diagnostics/official_seasonality_check.py` (PR #44). Δlog of the registered NSA restaurant-CPI series on the longest contiguous run, fitted with constant + 11 month dummies + AR(3); Ljung-Box(12) with 3 model df; residual autocorrelation at lag 12.

| series | fit | months | LB(12) p | residual ACF(12) | ±2/√T |
|---|---|---|---|---|---|
| US CUUR0000SEFV | full 1953-01..2025-09 | 873 | <0.0001 | +0.170 | 0.068 |
| US | last 60 | 60 | 0.937 | −0.129 | 0.267 |
| GB D7EW | full 1988-01..2026-08 | 464 | <0.0001 | +0.189 | 0.093 |
| GB | last 60 | 60 | 0.243 | −0.193 | 0.267 |
| SG M213751 row 1.11 | full 1990-01..2026-08 | 440 | 0.0120 | +0.132 | 0.096 |
| SG | last 60 | 60 | 0.878 | +0.037 | 0.267 |
| MY cpi_3d 111 | full 2010-01..2026-08 | 200 | 0.1675 | −0.002 | 0.143 |
| MY | last 60 | 60 | 0.243 | −0.057 | 0.267 |

Over their full histories, US, GB and SG retain positive residual autocorrelation at lag 12 (+0.13 to +0.19, outside the ±2/√T band), i.e. seasonal dependence that dummies and three lags do not remove; MY does not. In the last 60 months no series rejects, but power there is low and the dummy-induced bias (below) pushes the lag-12 autocorrelation negative. (The "last 60" rows are supplementary to the full-history fits.) The US series has **no October 2025 observation** (both the restaurant series and the headline), so no US window can span 2025-10 and no value is filled.

### Evidence 2: the raw Ljung-Box(12) is miscalibrated under this specification
`diagnostics/lb_rejection_share.py` (PR #45), simulated null series, 2,000 replications, share rejecting at 5% (standard chi-square, 2p model df):

| DGP | n | y equation | x equation | either |
|---|---|---|---|---|
| base | 36 | 0.516 | 0.518 | 0.761 |
| base | 100 | 0.184 | 0.189 | 0.339 |
| persistent | 36 | 0.549 | 0.535 | 0.785 |
| persistent | 100 | 0.193 | 0.188 | 0.348 |
| seasonal_ar12 | 36 | 0.394 | 0.382 | 0.614 |
| seasonal_ar12 | 100 | 0.525 | 0.584 | 0.791 |

The test rejects about half the time at n = 36 and 18% at n = 100 even when the model is correctly specified. Cause: with 11 month dummies the residuals within each calendar-month class sum to zero, which forces **negative** lag-12 residual autocorrelation (checked on pure iid noise: mean lag-12 correlation −0.52 at T = 34 and −0.15 at T = 97; chi-square LB(12) rejects 45% and 14%). It also rejects *less* often at n = 36 under the seasonal DGP (0.394) than under the correct model (0.516), so it carries no signal at that size. **A flag defined on the raw chi-square test would label most countries not interpretable for no reason.**

### Evidence 3: a bootstrap-calibrated Ljung-Box(12)
`diagnostics/lb_calibrated_check.py` (PR #45), 500 replications, B = 199. The observed LB statistic (y-equation residuals of the unrestricted fit) is compared with its distribution under the restricted model regenerated by the registered recursive block bootstrap, which carries the same dummy-induced bias.

| DGP | n | raw chi-square | calibrated |
|---|---|---|---|
| base | 36 | 0.508 | 0.020 |
| base | 100 | 0.176 | 0.022 |
| persistent | 36 | 0.534 | 0.024 |
| persistent | 100 | 0.182 | 0.018 |
| seasonal_ar12 | 36 | 0.394 | 0.022 |
| seasonal_ar12 | 100 | 0.504 | 0.184 |

The calibrated version has correct (slightly conservative, about 2%) size, but **little power**: it flags the lag-12 seasonal DGP in 2% of series at n = 36 and 18% at n = 100, while the Granger test's own over-size there is large. The flag is a weak protection, not a guarantee.

### Option C considered and not adopted
Option C adds the own seasonal lag y(t-12) of the official CPI to both the restricted and unrestricted CPI equations. y(t-12) for the first rows is taken from official history before the window, so no observation is lost; residual df fall by one (19/16/13 at n = 36), and the recursive bootstrap regenerates y*(t-12). The pre-set rule was: adopt Option C as the proposed amendment (with the calibrated LB(12) as diagnostic only) if every size rate is inside [0.03, 0.07]. Size, recursive scheme, B = 999, 2,000 replications (`diagnostics/prereg_size_check_optionC_B999_*.txt`, PR #45):

| DGP | country n=36 | country n=100 | panel n=36 | panel n=100 |
|---|---|---|---|---|
| base | **0.0780** | 0.0515 | 0.0545 | 0.0480 |
| persistent | **0.0780** | 0.0550 | 0.0695 | 0.0460 |
| seasonal_ar12 | **0.0980** | 0.0675 | **0.0770** | 0.0555 |

Four of the 12 rates exceed 0.07, so **Option C is not adopted** and the registered specification (dummies plus lags 1 to 3) is unchanged. Option C removes the large n = 100 over-size under lag-12 seasonality (country 0.174 to 0.0675; panel 0.2985 to 0.0555) but is over-sized at n = 36 under every DGP, including base (0.0675 to 0.0780), because the extra parameter uses one of about 20 residual df. The residual over-size of the registered test under lag-12 stochastic seasonality (§2 table) therefore remains a stated limitation.

### Proposed amendment: Option A
**Option A is the proposed amendment** (not yet registered):
- The flag uses the **bootstrap-calibrated** Ljung-Box(12) on the y-equation residuals (Evidence 3), with the same B and seed rules as the primary test. A flagged country-level result is reported as "not interpretable — seasonal misspecification"; a flagged panel is exploratory. The diagnostic never changes the specification.
- The raw chi-square Ljung-Box(12) is **not** proposed as the flag (Evidence 2: it rejects about half of correctly specified series at n = 36).
- Unflagged results are reported with the §2 size limitation: the calibrated flag has low power (2% at n = 36, 18% at n = 100 against lag-12 seasonality), so an unflagged result is not evidence that seasonal misspecification is absent.

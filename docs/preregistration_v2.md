# UICPI Pre-registration, v2: tax pass-through to restaurant prices (DRAFT, revision 1)

Status: DRAFT for review. Becomes binding when merged; the merge commit SHA is the registered version. **No analysis has been run.**
Drafted: 2026-10-10.

This document is independent of `docs/preregistration.md` (v1, Granger lead-lag). It has its own hypotheses, families and error budget. Nothing here changes v1, and v1's results do not enter any v2 test.

Items marked **DECISION FOR WC** are open choices, with the recommendation written as the default. Items marked **VERIFY** are facts not yet confirmed against the publisher; the tag is removed only when confirmed, and a confirmed fact that contradicts the text is handled as a listed correction, not silently.

## 0. Disclosure: what has been seen

This is **not** a blind pre-registration. "Confirmatory" in this document means: specification, windows, exclusions and inference were fixed before the outcome series were evaluated around the event dates.

**Seen by WC**
- Singapore month-on-month CPI figures for **January 2024**. The series and values are not recorded here. The January 2024 SG event (§2) is therefore treated as **seen**, and its result carries that label wherever it appears.

**Seen in this project (counts and coverage only)**
- ONS price-quote **row counts** by month, item and region, and the list of 44 catering item IDs with first and last month (`diagnostics/tax_feasibility/`). The PRICE column was not read.
- SingStat M213751 and M213761: the **first and last period with a value** for each series, and the list of series. No index or price value was read or stored.
- Malaysian PriceCatcher cooked-food row counts (not used here).

**Seen in published sources and abstracts (not data)**
- The ONS October 2020 article states that the combined effect of Eat Out to Help Out (EOHO) and the VAT cut lowered the August 2020 CPIH annual rate from about 0.9% to 0.5%, and that the fall was largely due to EOHO. Press reports quote a −0.44 percentage-point contribution of restaurants and cafés to the August 2020 CPI change. So the **aggregate direction and rough size of the 2020 UK restaurant response are known**, and the UK 2020 event is **seen**.
- Abstract-level literature: UK hotel pass-through of the 2020 cut of 20-50% (Onnis et al., Cardiff WP E2025/4); German restaurant pass-through of the 2024 VAT rise of about 31% in month one and about 58% by month six (Firgo, arXiv:2409.01180); the Irish Fiscal Advisory Council (2025) on asymmetry. These are background. They are **not** used to set any threshold, window or expected effect size below.
- Common knowledge of the tax changes and of rapid food-service price rises in Singapore in 2023-24.

**Consequence.** For the UK 2020 event and the SG January 2024 event the direction of the aggregate result is partly known. Results for those events are labelled "seen" and cannot, on their own, carry a claim of confirmation. The 2011 UK, 2021 UK, 2022 UK, 2023 SG and 2007 SG events are not known to have been seen at the series level by anyone on the project, but WC's general familiarity is acknowledged.

## 1. Hypotheses

Notation. For a tax change at an event, τ is the tax rate on the relevant supply and Δ = log((1+τ_after)/(1+τ_before)). **Pass-through** is ρ = (Δ log consumer price) / Δ. ρ = 1 means the consumer price moves by exactly the tax-inclusive amount; ρ = 0 means no movement.

- **H1 (UK, by event).** For each UK event in §2, consumer prices of catering items move in the direction of the tax change: ρ_e > 0 (one-sided in the direction of the change). Tested separately for each evaluable event. The estimand is ρ_e, with a placebo-calibrated band (§5).
- **H2 (UK, asymmetry).** Pass-through of tax rises exceeds pass-through of the tax cut: mean ρ over informative rise events minus ρ of the 2020 cut is > 0. **Weak by construction:** there is one cut event, it coincides with COVID and EOHO, and the 2008 cut is not in the open data.
- **H3 (SG, GST).** The GST rate rises of 2023-01-01 (7% to 8%) and 2024-01-01 (8% to 9%) pass through more to restaurant and fast-food prices than to hawker-centre prices: mean of (ρ_restaurant/fast-food − ρ_hawker-centre) over the two events is > 0. The registered-versus-unregistered interpretation is conditional on H4 (§6).
- **H4 (SG, descriptive).** The share of GST-registered stalls among stalls in sampled hawker centres. A descriptive estimate with an interval; no hypothesis test.

Direction is specified in advance for H1 to H3. A result in the opposite direction is reported as such and does not confirm the hypothesis.

## 2. Events

### UK, VAT on catering (eat-in food and non-alcoholic drinks, hot takeaway)

| ID | Effective date | Change | Δ = log((1+τ₁)/(1+τ₀)) | Source | Status |
|---|---|---|---|---|---|
| UK-E1 | 2011-01-04 | standard rate 17.5% to 20% | **+0.0211** | HMRC / GOV.UK | **VERIFY** (date from memory) |
| UK-E2 | 2020-07-15 | temporary reduced rate 20% to 5% | **−0.1335** | GOV.UK, "VAT: reduced rate for hospitality, holiday accommodation and attractions" (accounting rates 5% 2020-07-15 to 2021-09-30) | confirmed in search extract, page not opened |
| UK-E3 | 2021-10-01 | 5% to 12.5% | **+0.0690** | same GOV.UK page (12.5% 2021-10-01 to 2022-03-31) | as above |
| UK-E4 | 2022-04-01 | 12.5% to 20% | **+0.0645** | same GOV.UK page (standard rate resumes 2022-04-01) | as above |

Not events: the extensions of the 5% rate (to 2021-03-31, then 2021-09-30), which changed no rate. Excluded because they are outside the open data: the 1 December 2008 cut and the 1 January 2010 rise (ONS quotes before 2010-01 are not openly published; see `diagnostics/tax_feasibility/addendum_2026-10-10_readonly_checks.md` §a). **Conditional extension:** if secure-access microdata for 1996-2009 are obtained **before any outcome data are evaluated**, these two events and a 2008-2010 placebo base may be added, using the same rules, and the addition is recorded as a deviation (§8).

**Data-quality overlays on UK-E2, declared now.** Restaurants were closed for most of March-early July 2020 and quote collection was disrupted; the EOHO scheme ran 2020-08-03 to 2020-08-31; hospitality closures and tier restrictions followed in late 2020 and the first half of 2021. These affect E2's anchor, endpoints and matched-quote counts and cannot be removed by design. They are the reason E2 may fail the §5 evaluability or informativeness gates, in which case E2 and H2 are reported as **not testable** rather than weakened.

### Singapore, GST

| ID | Effective date | Change | Δ | Source | Status |
|---|---|---|---|---|---|
| SG-E0 | 2007-07-01 | 5% to 7% | **+0.0189** | IRAS rate table | confirmed (IRAS page, earlier session) |
| SG-E1 | 2023-01-01 | 7% to 8% | **+0.0093** | IRAS rate table | confirmed |
| SG-E2 | 2024-01-01 | 8% to 9% | **+0.0092** | IRAS (via search extract of IRAS pages); Wikipedia | extract only; page not opened. **Seen** (§0) |

Earlier rate changes (1994, 2003, 2004) precede the start of the SingStat restaurant / fast-food / hawker series (2005-01) and are out of scope. SG-E0 is **secondary** (§7) because the only available hawker control class in 2007 is the combined "Hawker Centres, And Food Courts, Coffee Shops & Kiosks" class, which contains food-court operators that are likelier to be registered.

## 3. Outcomes and data

### 3.1 UK

- Source: ONS "Consumer price inflation item indices and price quotes" monthly files, 2010-01 to 2026-08 (191 of 200 months published; missing 2017-01, 2017-02 and 2019-01 to 2019-07, so those months are MISSING and never interpolated).
- Items: catering item IDs `220xxx` (44 IDs). ID column is `ITEM_ID` until the 2025/26 files and `CS_ID` after; both are mapped to one `ITEM_ID`.
- A **quote key** is (`SHOP_CODE`, `ITEM_ID`). If a key has several rows in a month, the median PRICE for that key-month is used. Rows enter only with the VALIDITY codes ONS documents as valid prices. **VERIFY:** the valid code list is fixed by a pre-analysis commit that reads the ONS field documentation only, before PRICE is read.
- **Item VAT classification.** Every catering ID is classified before any price is read, in a committed file `docs/prereg_v2_uk_item_vat_status.csv`, with the HMRC citation per ID (VAT Notice 709/1 and the HMRC briefs on the 2020-22 reduced rate): `treated` (standard-rated before and reduced-rated in 2020-22: eat-in food and soft drinks, hot takeaway), `control` (rate unchanged in 2020-22), or `ambiguous` (excluded). The classification is by HMRC rule, not by observed price behaviour. Items whose tax treatment depends on the outlet or the context not recorded in ITEM_DESC are `ambiguous`.
- **Primary outcome per event:** the log of the Jevons (geometric-mean) price relative between an **anchor month** and an **endpoint month** over matched quote keys present in both, equal-weighted within item, then geometric mean across `treated` items with equal item weights. SHOP_WEIGHT weighting is a sensitivity.
- A month is a valid anchor or endpoint only if there are at least **500 matched relatives** across treated items between the two months. **DECISION FOR WC:** 500 (default). Months below are MISSING.
- **Secondary (event-level difference-in-differences):** treated minus control-item relative, only for events where at least 3 `control` IDs have at least 100 matched relatives in both months. This is a robustness estimate, never the primary.

### 3.2 Singapore

- Source: SingStat Table Builder M213751 (CPI, 2024 as base year, monthly, non-seasonally adjusted; **not** the seasonally adjusted M213752), data.gov.sg mirror `d_bdaff844e3ef89d39fceb962ff8f0791` as fallback. Vintage and fetch date are recorded in the results file.
- Series: **Restaurants, Cafes & Pubs** and **Fast Food Restaurants** (both from 2005-01) as treated; **Hawker Centres** (separate series from 2019-01) as the primary control; **Hawker Centres, And Food Courts, Coffee Shops & Kiosks** (from 2005-01) as the secondary control. "Restaurants and Cafes" (from 2024-01 only) is **not** used.
- The treated outcome is the log-index of Restaurants, Cafes & Pubs and Fast Food Restaurants combined, with the CPI weights from the same table if published, otherwise the equal-weight mean of the two log-indices (**VERIFY** availability of weights).
- The price-based table M213761 (20 cooked food and drink series; 10 from 2015-01 and 10 from 2024-01) is **exploratory only**. It is indicative average transaction prices on a changing basket, and has no restaurant series and no establishment-type breakdown.
- **VERIFY before analysis:** (i) whether SingStat records prices **including** GST and service charge. If yes, restaurants that price "++" (tax and service charge added at the till) show **mechanical** pass-through of 1 with no repricing, and H3 measures the legal incidence plus repricing, not repricing alone. (ii) how the 2024-base series is linked to earlier vintages at the 2024 boundary (information paper "Rebasing of the CPI (2024 as Base Year)"). If the Dec 2023 to Feb 2024 interval spans a basket vintage boundary, **SG-E2 is flagged vintage-confounded** and is reported but moved to secondary. **Rule fixed now.**

### 3.3 H4 data (IRAS)

Described in §6. The IRAS GST-registered business search is public, takes one business name (at least the first five characters) or up to four UEN / GST numbers per search, and requires a CAPTCHA each time. It is used **manually only**.

## 4. Statistic

For an event with effective date d and horizon h (months), define:

- **Anchor month a** = the last month whose price observation date precedes d. UK observations fall on the ONS index day (the second or third Tuesday of the month; ONS publishes the date in the bulletin; **VERIFY** for July 2020). SG CPI is monthly, so for 1 January events a = December.
- **Endpoint month a + h.** Primary **h = 2** (the event month and the next). Secondary h = 1 and h = 3. This is fixed now and was chosen before any outcome was evaluated.
- **Raw statistic** T_m = L_{m+h} − L_m, where L is the log outcome level (SG) or the log matched price relative (UK, §3.1), for any anchor month m.
- **Local baseline.** T*_m = T_m − mean of T_{m'} over eligible non-event anchors m' with the same calendar month, |m' − m| ≤ 36 months, m' ≠ m. An anchor is eligible only with **at least 4** such neighbours. This removes seasonality (January repricing) and slowly varying inflation without using any post-event information, and the same operator is applied to the event anchor and to every placebo anchor.
- **Signed statistic** U_m = sign(Δ) · T*_m, and **pass-through** ρ̂ = T*_a / Δ.
- **UK-E2 endpoint exception.** The endpoint is **2020-09** (the first non-EOHO month after the cut), and a is the last month with index day before 2020-07-15 (July 2020 if its index day precedes 15 July, otherwise June 2020). If a has fewer than 500 matched relatives to 2020-09, E2 is not evaluable.

## 5. Inference: placebo in time

Each test compares the event statistic with the same statistic at **placebo anchors**, which are all eligible months with no event nearby. No parametric distribution is assumed.

**Placebo anchors.** All months m for which: (i) L is observed at m and m + h; (ii) m + h is not 2020-08 (EOHO), and no month in [m − 36, m + h] used by the local baseline is 2020-08 as an endpoint; (iii) no **event month** (the month containing an effective date in §2) lies in [m, m + h]; (iv) the neighbour rule of §4 is met; (v) for UK, the 500-relative rule holds. The placebo pool is therefore 2010-2026 for UK and, for SG, **2005-2026 for the restaurant / fast-food series** and **2019-2026 for the hawker-centre-only control**. Months inside the COVID period are **kept** (they widen the null, which is conservative) and removed in a labelled sensitivity.

**Test.** One-sided placebo rank p-value: p = (1 + #{placebo m : U_m ≥ U_a}) / (N + 1).

**Calibrated band.** Report ρ̂ together with the 5th and 95th percentiles of T*_m / |Δ| over placebo anchors, so that the reader sees what noise alone produces at that tax step size.

**Resolution rule.** A test with N + 1 < 1/α_adj cannot reject and is reported as resolution-limited.

**P0, the informativeness gate (run before any event window is evaluated).** A script that cannot read event-anchor windows (they are masked by the §2 event list) computes, from the placebo pool only, for each event and series: N, q₉₅ and q₂₀ of T*_m, and **MDE_ρ = (q₉₅ − q₂₀) / |Δ|** (the pass-through that a location shift of the null distribution would need to be detected with 80% power at one-sided α = 0.05). An event is **informative** iff MDE_ρ ≤ 1.0 (full pass-through would be detectable). The P0 output is committed before the event statistics are computed. Events that are not evaluable (§4) or not informative are **reported descriptively and excluded from the confirmatory family**, never dropped silently. The threshold 1.0 was fixed before any outcome was evaluated. **DECISION FOR WC.**

**Pooled test for H3.** For SG-E1 and SG-E2 jointly: D_m = T*_{restaurant/fast-food, m} − T*_{hawker-centre, m}. Statistic R_a = ½ (D_{a1} / Δ₁ + D_{a2} / Δ₂), where a₁ = 2022-12 and a₂ = 2023-12. The placebo distribution is R_m = ½ (D_m / Δ₁ + D_{m+12} / Δ₂) over all anchors m such that m and m + 12 are both eligible placebo anchors (with the same Δ₁, Δ₂ constants). The pooled statistic has lower variance than either event alone, which is why it is the registered H3 test. If SG-E2 is flagged vintage-confounded (§3.2), H3 is run on SG-E1 alone and labelled secondary.

**H2 test.** A = mean over informative rise events of (T*_e / Δ_e) minus T*_{E2} / Δ_{E2}. Placebo: B = 9,999 draws of distinct eligible anchors assigned to the same event slots, with the same Δ constants. One-sided p for A > 0. P0 applies to A itself: MDE_A = q₉₅ − q₂₀ of the placebo A distribution must be ≤ 1.0, otherwise H2 is reported as not testable.

**Multiplicity.** Three confirmatory hypotheses, H1, H2 and H3. The error budget is α = 0.05 split equally: α = 0.0167 each. Inside H1, Holm over the informative UK events. H1 is claimed if at least one informative UK event rejects after Holm. H4 is descriptive. Everything else is exploratory (§7).

## 6. H4: GST registration among hawker stalls (descriptive)

- **Estimand.** The share of stalls, among sampled stalls in sampled hawker centres, that appear in the IRAS GST-registered business search as "currently registered" at the query date, among stalls for which the search outcome is determinate.
- **Outcome categories, recorded for every sampled stall:** `registered`, `not found` (a registered-name search returned none), `ambiguous` (several matches), `unmatchable` (no registered business name or UEN could be obtained for the stall). `not found` and `unmatchable` are **never** read as "not registered".
- **Reported:** the share among determinate stalls, with a cluster-robust 95% interval (clusters are hawker centres; Wilson interval as the headline), and the two bounds obtained by assigning all `not found`, `ambiguous` and `unmatchable` stalls to registered (upper) or not registered (lower).
- **Sampling frame and size. DECISION FOR WC.** Default: a random sample of at least 15 hawker centres, stratified by region, from the NEA hawker-centre list (**VERIFY** that a stall-level frame exists; if none, stalls are enumerated on site during WC's visit from displayed licence names). Target at least 150 stalls (worst-case Wilson half-width about ±8 percentage points before clustering).
- **Process.** Manual, one query per stall, a person reads the CAPTCHA; no automation; **no NRIC search**; each query's date, time and result category are logged. Registered business names are public records, and names are stored; nothing else about individuals is stored.
- **Link to H3.** H4 does not change H3's registered specification. If the point estimate of the registered share is **≥ 0.5**, the H3 contrast is described as "restaurant and fast-food versus hawker-centre", **without** the registered-versus-unregistered interpretation. If it is lower, the interpretation is allowed but is reported with the bounds.

## 7. Confirmatory versus exploratory

**Confirmatory (this registration):** H1 (informative UK events, Holm), H2 (if testable), H3 (pooled SG-E1 and SG-E2 against the hawker-centre-only control, if testable). "Confirmatory" carries the §0 qualifier throughout; the "seen" labels for UK-E2 and SG-E2 stay attached.

**Secondary (labelled):** SG-E0 (2007, combined control); h = 1 and h = 3; the control-item difference-in-differences for UK; the COVID-excluded placebo pool; the SG-E1 only version of H3 if SG-E2 is vintage-confounded.

**Exploratory (labelled "exploratory" wherever it appears):** M213761 dish prices; the SG "Restaurants and Cafes" series; any event not in §2; any other control definition; reverse or lead-lag analyses; regressions on chain versus independent status from the UICPI live data; any analysis suggested by looking at the results.

## 8. Exclusions, deviations and stopping rules

- **EOHO.** August 2020 is never an endpoint or an anchor, and is never used in a baseline average. A month-level exclusion, not an adjustment. If, before any outcome is evaluated, the ONS quote file for 2020-08 is found to carry a documented flag that separates discounted quotes, the flagged quotes may be removed and August 2020 re-admitted. That is a recorded deviation. The sensitivity that includes August 2020 with raw PRICE is exploratory.
- **Missing months** are never filled. **No second differencing, no interpolation, no seasonal adjustment** (the SA table M213752 is not used).
- **No result-dependent choices.** The horizon, the thresholds (500 relatives, MDE_ρ ≤ 1.0, 4 neighbours, ±36 months), the series list and the control definitions are fixed. A change made after the P0 output is committed is a deviation and is listed with a reason in the results file.
- **If the specification cannot be executed as written, the run stops and reports.** It does not improvise.
- **Code** is frozen at a commit SHA recorded in the results commit. Before any real data are used, the placebo procedure is run on **simulated** series with a known injected pass-through (size and power check, simulated data only) and the P0 script is verified to be unable to read masked event windows.
- **Data provenance.** Only public sources: ONS, SingStat, IRAS public search. No residential-IP live-scrape data and no UICPI index values enter any confirmatory test.

## 9. What must be done before the confirmatory run (none done yet)

1. `docs/prereg_v2_uk_item_vat_status.csv` with HMRC citations for all 44 IDs, committed before PRICE is read.
2. The §3.1 VALIDITY and field-documentation commit (valid codes; ONS index day for July 2020 and every other event month).
3. The SG verifications in §3.2 (GST and service-charge inclusion; the vintage boundary; weights).
4. The simulation, P0 script and masking test in §8.
5. Confirm UK-E1's effective date and the SG-E2 IRAS page text (§2).
6. H4: sampling frame and sample size decided; a protocol for naming, logging and storage.

## 10. Pre-merge checklist

- [ ] WC decisions: 500 matched relatives; MDE_ρ ≤ 1.0; h = 2; α split 0.0167 each; H4 frame and size.
- [ ] §2 VERIFY tags resolved or carried as stated.
- [ ] Record the merge commit SHA as the registered version.

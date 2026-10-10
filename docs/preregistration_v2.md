# UICPI Pre-registration, v2: tax pass-through to restaurant prices (DRAFT, revision 2)

Status: DRAFT for review. Becomes binding when merged and registered (§10). **No outcome value has been read and no analysis has been run.**
Drafted: 2026-10-10. Revision 2: 2026-10-10 (changes listed in §11).

This document is independent of `docs/preregistration.md` (v1, Granger lead-lag). It has its own hypotheses, families and error budget; v1's results do not enter any v2 test.

Items marked **DECISION FOR WC** are open choices, with the recommendation written as the default. Items marked **VERIFY** are facts not yet confirmed against the publisher. Evidence labels in §11: **page read** (I opened and read the page or PDF) and **search extract** (text returned by a search, page not opened).

## 0. Disclosure: what has been seen

This is **not** a blind pre-registration. "Confirmatory" means: specification, windows, exclusions and inference were fixed before the outcome series were evaluated around the event dates.

**Seen by WC:** Singapore month-on-month CPI figures for **January 2024** (series and values not recorded). SG-E2 (§2) is therefore treated as seen.

**Seen in this project (counts, labels and coverage only):**
- ONS price-quote row counts by month, item and region; the 44 catering item IDs with first and last month. The PRICE column was not read.
- SingStat M213751 and M213761: series labels, and the first and last period with a non-empty cell, plus the number of non-empty months in 2006-01 to 2008-12 for the food-service classes. No index or price value was printed or stored.
- The ONS field glossary, the ONS July 2020 bulletin text on collection, the SingStat rebasing information paper text, and IRAS and GOV.UK pages (methodology and rules only).

**Seen in published sources and abstracts (not data):**
- The ONS October 2020 article states that EOHO plus the VAT cut lowered the August 2020 CPIH annual rate from about 0.9% to 0.5%, mostly through EOHO; press reports quote a −0.44 percentage-point contribution of restaurants and cafés to the August 2020 CPI change. So the aggregate direction and rough size of the 2020 UK restaurant response are known: **UK-E2 is seen**.
- Abstract-level literature (UK hotels 2020, Onnis et al.; German restaurants 2024, Firgo; Irish Fiscal Advisory Council 2025). Background only; **not** used to set any threshold, window or expected effect.
- Common knowledge of the tax changes and of food-service price rises in Singapore in 2023-24.

**Consequence.** UK-E2 and SG-E2 are labelled "seen" and cannot alone carry a claim of confirmation. UK-E1, UK-E3, UK-E4, SG-E0 and SG-E1 are not known to have been seen at series level by anyone on the project; WC's general familiarity is acknowledged.

## 1. Hypotheses

Notation. At an event, Δ = log((1+τ₁)/(1+τ₀)) is the log change in the tax-inclusive factor. **Pass-through** is ρ = (Δ log consumer price) / Δ; ρ = 1 means the consumer price moves by exactly the tax change.

- **H1 (UK, by event).** For each UK event in §2, the consumer price of treated catering items moves in the direction of the tax change: ρ_e > 0 (one-sided). Tested per evaluable, informative event in a pre-set order (§5).
- **H2 (UK, asymmetry).** Mean ρ over informative UK rise events minus ρ of the 2020 cut is > 0. **Weak by construction:** one cut event, coinciding with COVID and EOHO, and the 2008 cut is outside the open data.
- **H3 (SG, GST, one event).** The 1 January 2023 GST rise (7% to 8%) passes through more to restaurant and fast-food prices than to hawker-centre prices: ρ_restaurant/fast-food − ρ_hawker-centre > 0. **This is the sole confirmatory Singapore test.** Whether the contrast reflects registration status is conditional on H4 (§6), and whether it reflects repricing or only the tax-inclusive price mechanism is limited by §3.2.
- **H4 (SG, descriptive).** The share of GST-registered stalls in sampled hawker centres, reported as a **lower bound** with an upper bound. No hypothesis test.

Direction is fixed in advance for H1 to H3. A result in the opposite direction is reported as such and does not confirm the hypothesis.

## 2. Events

### UK, VAT on catering (eat-in food and non-alcoholic drinks; hot takeaway)

| ID | Effective date | Change | Δ | Source | Status |
|---|---|---|---|---|---|
| UK-E1 | 2011-01-04 | standard rate 17.5% to 20% | **+0.0211** | gov.uk/vat-rates: "The standard rate of VAT increased to 20% on 4 January 2011 (from 17.5%)." | **page read** |
| UK-E2 | 2020-07-15 | temporary reduced rate 20% to 5% | **−0.1335** | GOV.UK "VAT: reduced rate for hospitality, holiday accommodation and attractions": 5% from 15 July 2020 to 30 September 2021 | **page read**. **Seen** (§0) |
| UK-E3 | 2021-10-01 | 5% to 12.5% | **+0.0690** | same page: 12.5% from 1 October 2021 to 31 March 2022 | page read |
| UK-E4 | 2022-04-01 | 12.5% to 20% | **+0.0645** | same page: "From 1 April 2022 the normal VAT rules apply" | page read |

Covered supplies (page read): food and non-alcoholic drinks for consumption on the premises, hot takeaway food and hot takeaway non-alcoholic drinks. The page does not address cold takeaway or alcohol. The extensions of the 5% rate changed no rate and are not events.

**Index day.** The ONS July 2020 bulletin states "The figures in this publication use data collected on or around 14 July 2020" (**page read**). That precedes the 15 July cut. So UK-E2's anchor month is **2020-07** (a pre-cut observation), and the first post-cut index month is August 2020, which is the EOHO month and is excluded (§8). UK-E2's endpoint is therefore **2020-09**.

**Data-quality overlays on UK-E2, declared now.** Restaurants were closed for most of March to early July 2020; from April 2020 ONS collected prices centrally by phone, email and website and imputed index movements for unavailable items (July 2020 bulletin, **page read**); EOHO ran 2020-08-03 to 2020-08-31; hospitality closures and tier restrictions followed. These can make E2's matched counts fall below the §3.1 threshold. If so, E2 and H2 are reported as **not testable**.

### Singapore, GST

| ID | Effective date | Change | Δ | Status in this registration | Source |
|---|---|---|---|---|---|
| SG-E1 | 2023-01-01 | 7% to 8% | **+0.0093** | **Confirmatory (H3), the only one** | IRAS "GST Rate Change for Consumers": "7% to 8% with effect from 1 Jan 2023" (**page read**) |
| SG-E2 | 2024-01-01 | 8% to 9% | **+0.0092** | **Secondary / descriptive.** Reasons: (i) its month-on-month figures are already seen (§0); (ii) 10 of the 20 cooked-food series in M213761 begin 2024-01 and have no pre-period; (iii) the 2019- to 2024-based link boundary falls at 2023-12 | 2024-01 (§3.2) | IRAS same page: "8% to 9% with effect from 1 Jan 2024" (**page read**) |
| SG-E0 | 2007-07-01 | 5% to 7% | **+0.0189** | **Secondary / descriptive**, conditional on a pre-run check (§3.2); otherwise moves to "Dropped events" | IRAS rate table (page read, earlier session) |

### Dropped events

| Event | Why dropped |
|---|---|
| UK 2008-12-01 VAT cut (17.5% to 15%) and 2010-01-01 rise | ONS price quotes before 2010-01 are not openly published (§3.1, addendum §a); the only access found is secure-access microdata. Conditional extension: if that access is obtained **before** any outcome is evaluated, the two events may be added under the same rules, recorded as a deviation (§8) |
| SG GST changes of 1994, 2003 and 2004 | Precede the start of the SingStat restaurant / fast-food / hawker series (2005-01) |
| UK extensions of the 5% rate (2021-01, 2021-04) | No rate change |
| SG-E0 (2007) | **Not dropped now.** A source exists (§3.2). It is dropped automatically if the §3.2 pre-run class-definition check for the 2004-based vintage fails |

## 3. Outcomes and data

### 3.1 UK

- Source: ONS "Consumer price inflation item indices and price quotes" monthly files, 2010-01 to 2026-08 (191 of 200 months published; 2017-01, 2017-02 and 2019-01 to 2019-07 are MISSING and never interpolated). `CS_ID` is mapped to `ITEM_ID` for files that use it.
- Items: the 44 catering IDs `220xxx`.
- **Field handling, from the ONS glossary (page read):** `VALIDITY` is TRUE if the quote entered the month's index, FALSE if not; `INDICATOR_BOX` codes are C comparable change, M missing, N non-comparable, P price unavailable, Q message, R recovery after sale, S sale or special offer, T temporarily out of stock, W size change; `TEMPORAL` marks quotes collected the Friday before the index day (excluded from RPI); `REGION` has 13 codes (1 is catalogue collections); `SHOP_TYPE` has codes 1 to 3 (1 multiples with 10 or more outlets, 2 independents, 3 not stratified).
- **Registered filters:** keep rows with `VALIDITY` = TRUE and, where the column exists, `TEMPORAL` = FALSE. Drop a matched pair if the endpoint's `INDICATOR_BOX` is in {M, P, T, N, W} or the anchor's is in {N, W}. Sale prices (S, R) are kept in the primary and dropped in a labelled sensitivity.
- **Imputation and carry-forward in 2020-21: no flag exists.** The glossary documents no flag for imputed, carried-forward or estimated quotes. It documents that `BASE_PRICE_CPI` and `BASE_PRICE_RPI` may be "observed or imputed", which is why the primary statistic uses `PRICE` only and never the price-relative or base-price columns. The July 2020 bulletin says imputation was applied to index movements for unavailable items; whether any synthetic quote rows appear in the files is **not documented**. **Limitation, stated now:** quotes in 2020-21 cannot be screened for imputation; the `VALIDITY`/`INDICATOR_BOX` filters remove only quotes ONS itself marks as missing or unavailable. The stress-period pool (§5, R2) is the registered check on this.
- A **quote key** is (`SHOP_CODE`, `ITEM_ID`); if a key has several rows in a month, the median PRICE for that key-month is used.
- **Item VAT classification.** Before any price is read, every catering ID is classified in a committed file `docs/prereg_v2_uk_item_vat_status.csv` with the citation per ID: `treated` (eat-in food and non-alcoholic drinks, hot takeaway), `control` (rate unchanged in 2020-22), or `ambiguous` (excluded). The classification follows the GOV.UK page and HMRC VAT Notice 709/1, not observed price behaviour.
- **Primary outcome per event:** the log of the Jevons price relative between the **anchor month** and the **endpoint month** over matched quote keys, equal-weighted within item, then the geometric mean over `treated` items with equal item weights. `SHOP_WEIGHT` weighting is a sensitivity.
- A month is a valid anchor or endpoint only if there are at least **500 matched relatives** across treated items between the two months (**DECISION FOR WC**: 500). Months below are MISSING.
- **Secondary:** treated minus control-item relative, only for events where at least 3 `control` IDs have at least 100 matched relatives in both months.

### 3.2 Singapore

- Source: SingStat Table Builder **M213751** (CPI, 2024 as base year, monthly, **not** the seasonally adjusted M213752); the data.gov.sg mirror `d_bdaff844e3ef89d39fceb962ff8f0791` is the fallback. The vintage and fetch date are recorded in the results file.
- Series (labels and coverage, API read 2026-10-10): `1.11.1` **Restaurants, Cafes & Pubs** and `1.11.2` **Fast Food Restaurants**, both 2005-01 to 2026-08 (260 months); `1.11.3.1` **Hawker Centres**, 2019-01 to 2026-08 (92 months); `1.11.3` Hawker Centres, And Food Courts, Coffee Shops & Kiosks, 2005-01 to 2026-08 (260 months); `1.11.3.2` Food Courts, Coffee Shops & Kiosks and `1.11.1.1` to `1.11.1.3` (Restaurants, Cafes, Pubs) are sub-series of the 2024 base (the latter three from 2024-01 only and **not used**).
- **Treated:** the combination of 1.11.1 and 1.11.2, weighted by the CPI class weights from the SingStat information paper (2019-based weights 537 and 86; 2024-based 585 and 85; **VERIFY** which weights apply to which month; if unresolved, equal weights).
- **Primary control:** `1.11.3.1` Hawker Centres. **Secondary control:** `1.11.3`.
- **Taxes are in the price (page read).** The SingStat information paper on rebasing the CPI (2024 as base year), ¶15: "Prices collected refer to those paid by consumers, that is, inclusive of taxes levied and net of subsidies/ rebates granted on the specific individual good or service". The paper's glossary names GST as such a tax. **Service charge is not mentioned**; whether it is in the collected price is **VERIFY** (not found).
- **Consequence for H3 ("++" outlets).** Because collected prices are tax-inclusive, an outlet that quotes menu prices "++" (GST and service charge added at the till) will show a mechanical rise of about the full GST step in the CPI **without any repricing**, and an outlet with GST-inclusive menu prices shows a rise only if it reprices. The CPI does not record which convention an outlet uses, so **the CPI test cannot separate the two, and H3 is registered as a test of the tax-inclusive consumer-price differential, not of repricing.** Separating them needs outlet-level menu data. Registered handling: (i) H3's wording and conclusion are limited accordingly; (ii) **H3b (exploratory)**: from archived or live menu pages of Singapore restaurant brands, classify each as "++" or GST-inclusive, record the share, and compare menu-price (pre-tax) changes around 2023-01-01 for the two groups; this needs its own data-collection protocol and is outside this registration's confirmatory tests.
- **Splice at the 2024 boundary (page read).** Information paper ¶43: "the 2019-based CPI data series are linked to the 2024-based CPI data series by re-scaling them to the new base year of 2024 via a link factor. The link factor is the ratio of the annual 2024-based index in 2024 to the annual 2019-based index in 2024." ¶42: Jan to Dec 2024 is the overlap year. So pre-2024 months are the 2019-based series multiplied by one constant, and 2024 months come from the 2024-based series (consistent with the M213761 footnote that prices "starting from January 2024 are based on the 2024-based CPI basket"). **The change from 2023-12 to 2024-01 therefore crosses a vintage boundary** (the inference that the published table uses the 2024-based values from 2024-01 is **VERIFY**, not stated in so many words). Within the 2019-based vintage the month-on-month changes are unaltered by the rescaling. **SG-E1 (2022-12 to 2023-01, h = 1 or 2) lies entirely inside the 2019-based vintage and is not affected.** SG-E2 spans the boundary and is secondary partly for this reason.
- **SG-E0 (2007), what exists and what does not.** M213751 holds Restaurants, Cafes & Pubs, Fast Food Restaurants, and Hawker Centres, And Food Courts, Coffee Shops & Kiosks with **36 of 36 non-empty months in 2006-01 to 2008-12** (and 2005-01 onward). Which vintage these months come from: the SingStat September 2008 CPI release states "2004 = 100" (page read, archived copy), so 2007 lies in the **2004-based vintage**. How that vintage is carried into the 2024-based table is documented only for the 2019-to-2024 step (above); that the earlier steps used the same constant-link-factor method is **assumed, not verified**. The older information papers (2004 and 2009 base) returned 404 when fetched. The September 2008 release names only the group "Food". **Pre-run check (before any outcome is evaluated):** locate a SingStat document for the 2004- or 2009-based CPI that lists restaurant food, fast food and hawker food as separate classes; if none is found, SG-E0 moves to "Dropped events". Even if it stays, its control is the combined class that includes food-court operators, so it is secondary and cannot support H3.
- **M213761 (dish prices).** 85 series, 2015-01 to 2026-08. Ten cooked-food and drink series span all 140 months (coffee/tea without milk, coffee/tea with condensed milk, fishball noodles, mee rebus, chicken rice, chicken nasi briyani, economical rice, roti prata plain, fried carrot cake, ice kachang); ten begin 2024-01 (32 months) and are **not used** in any pre-2024 statistic. Footnote (page read): the prices "are not a measure of pure price movements across CPI baskets due to changes in the sample of brands/varieties and outlets priced." Used only as the **dish arm of H3 (H3-dish, secondary)**, restricted to the 10 full-span series; its gate and N are in §5.

### 3.3 H4 data

The IRAS GST-registered business search (§6) is the only data source for H4. It is used **manually**.

## 4. Statistic

For an event with effective date d and horizon h (months):

- **Anchor month a** = the last month whose price observation precedes d. UK: the ONS index day is the second or third Tuesday and the exact date is published in each bulletin (**VERIFY** per event; resolved for July 2020, above). SG: monthly CPI; for 1 January events a = December.
- **Endpoint month a + h.** **UK primary h = 2** (UK-E2 uses the fixed endpoint 2020-09). **SG primary h = 1** (**DECISION FOR WC**, recommended): the CPI is tax-inclusive (§3.2), so the mechanical effect of a 1 January GST change should appear in the December-to-January change; h = 1 also has less noise than h = 2. SG h = 2 and h = 3 are reported as secondary. This choice was fixed before any outcome was evaluated.
- **Raw statistic** T_m = L_{m+h} − L_m, with L the log outcome level (SG) or the log matched price relative (UK).
- **Local baseline.** T*_m = T_m − mean of T_{m'} over eligible non-event anchors m' with the same calendar month, |m' − m| ≤ 36 months, m' ≠ m. An anchor is eligible only with **at least 3** such neighbours (changed from 4 in revision 1; see §11). This removes seasonality (January repricing) and slow drift using only the sample's own months, and is applied identically to the event anchor and to every placebo anchor.
- **Signed statistic** U_m = sign(Δ)·T*_m. **Pass-through** ρ̂ = T*_a / Δ. For H3 the contrast is D_m = T*_{restaurant/fast-food, m} − T*_{hawker centres, m}, and ρ̂_D = D_a / Δ.

## 5. Inference

### 5.1 Placebo pool (primary, and two registered robustness pools; all three are reported)

**Primary pool: all non-event months.** Placebo anchors are all months m for which (i) L is observed at m and m + h; (ii) for UK, neither m nor m + h is 2020-08, and (iii) no event month (any of the §2 events, including secondary ones) lies in [m, m + h]; (iv) the neighbour rule of §4 holds; (v) for UK, the 500-relative rule holds. Months in the COVID period are **kept** in the primary pool (they widen the null, which is conservative).

Counts of eligible anchors from period labels only (`diagnostics/tax_feasibility/p0_eligibility_counts.py`, output `p0_eligibility_counts_output.txt`; no value read):

| Series (coverage) | h = 1 | h = 2 | h = 3 |
|---|---|---|---|
| SG Restaurants/Cafes/Pubs and Fast Food (2005-01 to 2026-08) | 247 | 240 | 233 |
| **SG Hawker Centres only (2019-01 to 2026-08)** | **81** | **74** | **67** |
| SG M213761 full-span dishes (2015-01 to 2026-08) | 131 | 126 | 121 |
| UK catering quotes (191 months), before the 500-relative rule | 178 | 171 | 165 |

**R1, volatility-matched pool.** Define V_m = mean over the 12 months before the anchor of |log month-on-month change| of the outcome (UK: chained matched Jevons index of treated items; SG: the series' own monthly log change). Placebo anchors are those whose V falls in the **same tercile** as the event anchor's V, with terciles taken over the eligible primary-pool anchors. Anchors without 12 prior months are dropped, so the SG hawker pool shrinks to roughly one third of 81 (about 25), below the resolution limit (§5.3); R1 for H3 is therefore **expected to be descriptive only** and is reported with its N.

**R2, stress-period pool.** For events inside 2020-03 to 2022-12 (UK-E2, E3, E4), the placebo pool is restricted to anchors in that window, with the same eligibility rules. This explicitly includes the 2020-22 months and is the registered check on COVID-period imputation and closures (§3.1). Its N is reported; resolution-limited results are descriptive.

### 5.2 Tests, point estimates and confidence intervals

- **Test.** One-sided placebo rank p: p = (1 + #{placebo m : U_m ≥ U_a}) / (N + 1).
- **Reporting commitment.** For **every evaluable event, whether or not it passes the gate or rejects**, I report ρ̂ with a **95% confidence interval** and the placebo p for each registered horizon. CI by placebo test inversion: with G_m = T*_m / Δ over the placebo pool, CI₉₅ = [ρ̂ − q₀.₉₇₅(G), ρ̂ − q₀.₀₂₅(G)], valid under the shift model (event statistic = placebo-like noise + ρΔ). The same is done for H3's D/Δ and H2's A. Results are reported as estimates with intervals, never as pass/fail alone, for the primary pool and for R1 and R2.
- **What the gate does and does not guarantee.** The informativeness gate (below) guarantees only that **full pass-through (ρ = 1) would be detected with 80% power**. It says nothing about partial pass-through: a non-rejection does not exclude ρ = 0.3 or ρ = 0.6, which published estimates for other settings span (§0). A null here is therefore **uninformative about partial pass-through**, and the CI, not the p-value, is the evidence.

### 5.3 P0 informativeness gate (run before any event window is evaluated)

A script that cannot read the event-anchor windows (they are masked by the §2 event list) computes, from the placebo pool only: N, q₉₅ and q₂₀ of T*, and **MDE_ρ = (q₉₅ − q₂₀) / |Δ|**. An event (or contrast) is **informative** iff MDE_ρ ≤ 1.0 and N + 1 ≥ 1/α for its test (**resolution rule**). The P0 output is committed before event statistics are computed. Events not evaluable (§4) or not informative are reported descriptively with their ρ̂ and CI and are **excluded from the confirmatory family**, never dropped silently. Threshold 1.0 (**DECISION FOR WC**) was fixed before any outcome was evaluated.

**P0 design for H3 (SG-E1, Jan 2023, Δ = 0.0093).**
- **N.** CPI-class contrast: restaurants/fast-food (247) against Hawker Centres (81 at h = 1; 74 at h = 2): the contrast is defined only where both exist, so **N = 81 (h = 1), 74 (h = 2)**. Dish arm (H3-dish, 10 full-span M213761 series against the restaurant class, both available 2015-01 onward): **N = 131 (h = 1), 126 (h = 2)**.
- **Resolution.** At α = 0.0167 the rank test needs N + 1 ≥ 60; both arms meet it.
- **The MDE condition in plain terms.** MDE_ρ ≤ 1 means q₉₅ − q₂₀ of the demeaned contrast must be at most Δ = 0.0093, i.e. 0.93 log points. If the placebo contrast were roughly normal that requires a standard deviation of about 0.37 log points for the h = 1 contrast (q₉₅ − q₂₀ ≈ 2.49 σ).
- **Whether this can plausibly be met.** I cannot say from the data without reading the placebo values, which this revision does not do. On general knowledge, month-on-month movements of these CPI food-service classes are of the order of a few tenths of a percent, and a contrast of two classes has a variance equal to the sum of both, so I expect the condition to be **marginal and more likely to fail than to pass** for the Hawker Centres contrast, and to be easier for the dish arm only if the dish averages are smooth (they are indicative averages on a changing basket, so I would not expect that). **Registered rule: if the P0 gate fails, H3 is reported as "not testable"** (same rule as H2), with ρ̂, CI and N, and no confirmatory claim. This outcome is accepted in advance; with a single event the pooled-event variance reduction available in revision 1 is no longer available.
- **UK gates, for reference.** The same MDE_ρ condition applies per UK event: thresholds q₉₅ − q₂₀ ≤ 0.0211 (E1), 0.0690 (E3), 0.0645 (E4), 0.1335 (E2).

### 5.4 Multiplicity

Three confirmatory hypotheses, H1, H2, H3. The error budget is α = 0.05 split equally, **α = 0.0167** each. Inside H1, events are tested in the **fixed order of decreasing |Δ|**: E2, E3, E4, E1; each at α = 0.0167, stopping at the first non-rejection (fixed-sequence testing; Holm is not used because its first-step threshold, 0.0042, is below the placebo resolution 1/(N+1) ≈ 0.006 for N ≈ 170). H1 is claimed if at least one tested event rejects. H4 is descriptive. Everything else is exploratory (§7).

**H2 test.** A = mean over informative rise events of (T*_e / Δ_e) minus T*_{E2} / Δ_{E2}. Placebo: B = 9,999 draws of distinct eligible anchors assigned to the same event slots with the same Δ constants. One-sided p for A > 0. P0 applies to A: q₉₅ − q₂₀ of the placebo A distribution must be ≤ 1.0, otherwise H2 is "not testable".

## 6. H4: GST registration among hawker stalls (descriptive)

- **What the search can and cannot show (page read, IRAS).** One business name (at least the first five characters) **or** up to four UEN / GST numbers per search; a CAPTCHA each search; no stated result fields. It matches registered names and UENs, not stall signboard names.
- **"Not found" is not "not registered".** A stall registered under a name or UEN that I could not obtain, or recorded under a different name, returns "not found". The registered share computed from found, currently registered stalls is therefore a **lower bound** on the true share.
- **Outcome categories for every sampled stall:** `registered` (a matching entry with current registration, and, if the result shows a registration date, registered on or before 2023-01-01), `not found`, `ambiguous` (several matches), `unmatchable` (no registered name or UEN obtainable for the stall).
- **Estimand and reporting.** Lower bound p_L = registered / n_all; upper bound p_U = (registered + not found + ambiguous + unmatchable) / n_all. Report both with cluster-robust 95% intervals (clusters are hawker centres; Wilson interval as the headline), and the counts of each category. Nothing is dropped.
- **Link to H3 (revised).** If **p_L ≥ 0.5**, H3 is worded as "restaurant and fast-food versus hawker-centre" with no registration interpretation. If **p_U < 0.5**, the registered-versus-unregistered reading is permitted, with the bounds. Otherwise the reading is **indeterminate** and is not used.
- **Frame and sample size, fixed now (DECISION FOR WC; recommended values).**
  - **Frame:** the NEA hawker-centre list on data.gov.sg (a centre-level list with cooked-food stall counts; search extract found a 2016 list of 107 centres and a newer NEA dataset; **VERIFY** the current dataset and its stall-count field before sampling). Centres with fewer than 20 cooked-food stalls are excluded from the frame.
  - **Sample:** **12 centres, 10 stalls each, 120 stalls**. Centres are drawn by a seeded random draw (seed committed before the draw), stratified by region (proportional allocation); within a centre, stalls are chosen by systematic sampling in a fixed walking order from a random start (WC's site visit). Worst-case Wilson half-width about ±9 percentage points before clustering; a larger design effect is expected.
  - **Feasibility:** names are first matched offline against the ACRA entity datasets on data.gov.sg (metadata read: "ACRA Information on Corporate Entities", split by UEN type, updated 2026-09-16; **VERIFY** that it covers sole-proprietorship business names) to obtain UENs; UEN lookups go four to a search, so 120 stalls need at most 30 IRAS searches, and any stall without a UEN needs one search of its own. At about two minutes per CAPTCHA search, 120 stalls need about 1 to 3 hours of manual lookup. A larger sample (150) is affordable but widens the fieldwork, so the recommendation is 120.
- **Process.** Manual, one person reads the CAPTCHA; no automation; **no NRIC search**; each query's date, time and result category are logged. Only public registered business names are stored.

## 7. Confirmatory versus exploratory

**Confirmatory (this registration):** H1 (informative UK events, fixed-sequence), H2 (if testable), H3 (SG-E1, Hawker Centres control, if testable). "Confirmatory" carries the §0 qualifier; the "seen" labels for UK-E2 and SG-E2 stay attached.

**Secondary (labelled):** SG-E2 (2024) and SG-E0 (2007) results, with CIs; SG h = 2, 3; H3-dish; R1 and R2 pools (reported alongside the primary for every event); the UK control-item difference-in-differences; sale-price exclusion sensitivity; the COVID-excluded pool.

**Exploratory (labelled "exploratory" wherever it appears):** H3b ("++" menu-price check); M213761 dishes other than the 10 full-span series; "Restaurants and Cafes" and other 2024-only sub-series; any event not in §2; any other control definition; any analysis suggested by looking at the results.

## 8. Exclusions, deviations and stopping rules

- **EOHO.** August 2020 is never an anchor or endpoint and never enters a baseline average. It is a month-level exclusion, not an adjustment. If the August 2020 quote file is found to carry a documented flag that identifies discounted quotes before any outcome is evaluated (none was found in the glossary), flagged quotes may be removed and the month re-admitted as a recorded deviation. The sensitivity that includes August 2020 with raw PRICE is exploratory.
- **Missing months** are never filled. No seasonal adjustment (M213752 is not used).
- **No result-dependent choices.** Horizons, thresholds (500 relatives, MDE_ρ ≤ 1.0, ≥ 3 neighbours, ±36 months), series and controls are fixed. A change after the P0 output is committed is a deviation, listed with a reason.
- **If the specification cannot be executed as written, the run stops and reports.**
- **Code** is frozen at a commit SHA recorded in the results commit. Before real data are used, the placebo procedure is run on **simulated** series with a known injected pass-through (size and power check, simulated data only), and the P0 script is verified to be unable to read masked event windows.
- **Provenance.** Only public sources: ONS, SingStat, IRAS public search, GOV.UK. No residential-IP live-scrape data and no UICPI index values enter a confirmatory test.

## 9. What must be done before the confirmatory run (none done yet)

1. `docs/prereg_v2_uk_item_vat_status.csv` with citations for all 44 IDs, committed before PRICE is read.
2. SG verifications: service-charge treatment in the CPI price; whether M213751 uses 2024-based values from 2024-01; CPI class weights by month; the SG-E0 class-definition check (§3.2).
3. The UK per-event index-day check (July 2020 done) and the quote-file handling commit (§3.1 filters).
4. The simulation, P0 script and masking test (§8).
5. H4: verify the NEA frame and ACRA coverage; commit the sampling seed and the logging protocol.
6. WC decisions listed in §10.

## 10. Registration and pre-merge checklist

**Registration (freezing).** Once WC approves, the PR is merged and the merge commit is tagged **`prereg-v2`**. **WC** then deposits `docs/preregistration_v2.md` (and `diagnostics/tax_feasibility/p0_eligibility_counts*`) on OSF as a time-stamped registration, with the tag, the merge SHA and the file hash recorded in the OSF entry. **That deposit must precede the first read of any outcome value** (the UK PRICE column, the SG index or dish values), and the P0 output is committed after it. Any change after registration is a deviation (§8), listed in the results file.

- [ ] WC decisions: 500 matched relatives; MDE_ρ ≤ 1.0; UK h = 2; **SG primary h = 1**; α split 0.0167 each; H4 frame and 12 × 10 sample.
- [ ] VERIFY tags carried or resolved as stated (§11).
- [ ] Merge, tag `prereg-v2`, WC deposits on OSF, record the SHA.

## 11. Verification log and revision history

| Item | Result | Evidence |
|---|---|---|
| UK 4 Jan 2011 VAT rise | "The standard rate of VAT increased to 20% on 4 January 2011 (from 17.5%)." | page read, gov.uk/vat-rates |
| UK 2020-22 rates and dates | 5% from 15 Jul 2020 to 30 Sep 2021; 12.5% from 1 Oct 2021 to 31 Mar 2022; normal rules from 1 Apr 2022; eat-in, hot takeaway and hot takeaway non-alcoholic drinks covered | page read, GOV.UK guidance |
| ONS July 2020 index day | "on or around 14 July 2020" | page read, ONS July 2020 bulletin |
| ONS imputation in 2020 | From April 2020 prices collected centrally; imputation of index movements for unavailable items; carried-forward not mentioned | page read, same bulletin |
| ONS quote-file flags | VALIDITY TRUE/FALSE; INDICATOR_BOX codes (§3.1); no imputed/carried-forward flag; base prices may be "observed or imputed" | page read (glossary, Feb 2025 onwards xlsx) |
| SG CPI prices tax-inclusive | "inclusive of taxes levied and net of subsidies/ rebates" (¶15) | page read, SingStat rebasing paper ip-e61 |
| SG CPI includes service charge | Not stated | not found |
| 2024-base splice | Constant link factor (annual 2024 ratio) applied to the 2019-based series; overlap year 2024; boundary at 2023-12 | page read, ip-e61 ¶42-43 |
| Whether published table switches to 2024-based values at 2024-01 | Inferred from ¶42-43 and the M213761 footnote | inference |
| IRAS 9% from 2024-01-01; 8% from 2023-01-01 | "7% to 8% with effect from 1 Jan 2023 (first rate change)"; "8% to 9% with effect from 1 Jan 2024 (second rate change)" | page read, IRAS "GST Rate Change for Consumers" |
| SG 2006-2008 cooked-food class series | 36 of 36 non-empty months for 1.11.1, 1.11.2, 1.11.3 | API read (labels and period keys only) |
| SG 2004-based class definitions | Not found; older info papers returned 404; Sep 2008 release (2004 = 100) names only "Food" | not found |
| IRAS threshold history | Not found | not found |
| NEA hawker centre list | 2016 centre list (107 rows) and a newer NEA dataset with cooked-food stall counts | search extract |
| ACRA entity datasets | Three datasets on data.gov.sg, updated 2026-09-16 | metadata read (dataset listing) |

**Revision 2 (2026-10-10) changes**, by item of WC's review: (1) SG 2007: source found, kept secondary with a conditional class-definition check, "Dropped events" section added; (2) SG 2024 demoted, SG 2023 sole confirmatory H3 event, P0 design with N and the plausibility statement, "not testable" rule; (3) UK imputation-flag check and limitation; placebo pool primary plus R1 and R2; (4) point estimates and 95% CIs for every event, and the limits of the MDE gate; (5) H4 lower-bound framing, frame and sample size; (6) VERIFY items resolved and logged; (7) Registration section. **Unrequested design changes made while doing this**, for WC to accept or revert: neighbour rule changed from at least 4 to at least 3 (the 7.7-year hawker series left only 57 anchors under the old rule, below the resolution limit for α = 0.0167); Holm replaced by fixed-sequence testing in H1 (Holm's first-step threshold is below the placebo resolution); SG primary horizon changed from h = 2 to **h = 1**; H3's "pooled 2023+2024" removed (item 2).

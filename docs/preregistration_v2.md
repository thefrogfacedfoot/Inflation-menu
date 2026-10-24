# UICPI Pre-registration, v2: tax pass-through to restaurant prices (registered revision 3, tag `prereg-v3`; **revision 4**, for WC review, to be tagged `prereg-v4` on merge)

Status: DRAFT for review. Becomes binding when merged and registered (§10). **No outcome value has been read and no analysis has been run.**
Drafted: 2026-10-10. Revisions 2 to 5: 2026-10-10 (changes listed in §11). Registered as `prereg-v2` (06b92d4, 2026-10-11). **Registered revision 3 (`prereg-v3`), 2026-10-16:** gate statistic, size-control rule, CNY simulation and the H3 intersection-union test (§1, §5.1–§5.5, §7, §9.4, §11). **No outcome value had been read when revision 3 was written**; its motivation is the synthetic simulation in `analysis/simulation/` (PR #55). **Revision 4 (2026-10-24):** the H1 test becomes a level-gap conformal test, the H3 components become uncalibrated placebo rank tests, every gate becomes a symmetric gate at q₀₅, and the §5.5 calibration is withdrawn (§1, §4, §5.2–§5.5, §7–§11). **No outcome value has been read for revision 4 either**; its evidence is synthetic (`analysis/simulation/`, PR #67). H2 is demoted to a descriptive secondary result, so the confirmatory family is H1 and H3 (§1, §5.4, §7). WC's revision-4 decisions are recorded in §10.

> **Decisions recorded (WC, 2026-10-16):** D1-b (gate with q₁₀, §5.3), D2-b (every event tested with the simulation-calibrated critical value at the bias-corrected φ̂, §5.5), and H3 decided by an intersection-union test of h = 2 and h = 1 (§5.4). **Revision 4 (WC, 2026-10-24) supersedes D1-b and D2-b** (§5.3, §5.5); the H3 intersection-union test is kept.
>
> **Revision 4 design (WC, 2026-10-24):** H1 by the level-gap conformal statistic with a symmetric gate; H3 keeps the demeaned statistic and the IUT, with a symmetric gate; secondary events follow their family's rules. **Chosen by the revision-4 simulation within that design:** H3 components are uncalibrated rank tests (the residual-bootstrap calibration failed its conditional-size check, §5.5); the symmetric gate uses the (K+2)-th largest pooled value and q₀₅ (q₁₀ failed the 80% power check, §5.3).

This document is independent of `docs/preregistration.md` (v1, Granger lead-lag). It has its own hypotheses, families and error budget; v1's results do not enter any v2 test.

The decisions WC made on revision 2 are recorded in §10 and the DECISION tags are removed. Items marked **VERIFY** are facts not yet confirmed against the publisher. Evidence labels in §11: **page read** (I opened and read the page or PDF) and **search extract** (text returned by a search, page not opened).

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

- **H1 (UK, by event).** For each of the three clean UK events (UK-E3 Oct 2021, UK-E4 Apr 2022, UK-E1 Jan 2011), the consumer price of treated catering items moves in the direction of the tax change: ρ_e > 0 (one-sided). Tested per evaluable, informative event in the fixed order E3 → E4 → E1 (§5.4), each with the level-gap conformal test (§4, revision 4). **UK-E2 (Jul 2020) is not in H1**: it is seen (§0) and COVID/EOHO-confounded, so it does not gate the clean events.
- **H2 (UK, asymmetry). Revision 4: demoted to a secondary, descriptive result; no test, no gate, no confirmatory claim.** Reported: mean ρ̂ over the evaluable UK rise events (E3, E4, E1) minus ρ̂ of the 2020 cut (E2), with a 95% CI (§5.4). **Weak by construction:** one cut event, seen, coinciding with COVID and EOHO, and the 2008 cut is outside the open data. **UK-E2 also gets its own ρ̂ with a 95% CI as a secondary result** (§5.2).
- **H3 (SG, GST, one event; decided by an intersection-union test of h = 2 and h = 1, revision 3, §5.4; each component an uncalibrated placebo rank test with the symmetric gate, revision 4).** The 1 January 2023 GST rise (7% to 8%) passes through more to restaurant and fast-food prices than to hawker-centre prices: ρ_restaurant/fast-food − ρ_hawker-centre > 0. **This is the sole confirmatory Singapore test.** Whether the contrast reflects registration status is conditional on H4 (§6), and whether it reflects repricing or only the tax-inclusive price mechanism is limited by §3.2.
- **H4 (SG, descriptive).** The share of GST-registered stalls in sampled hawker centres, reported as a **lower bound** with an upper bound. No hypothesis test.

Direction is fixed in advance for H1 to H3. A result in the opposite direction is reported as such and does not confirm the hypothesis.

## 2. Events

### UK, VAT on catering (eat-in food and non-alcoholic drinks; hot takeaway)

| ID | Effective date | Change | Δ | Source | Status |
|---|---|---|---|---|---|
| UK-E1 | 2011-01-04 | standard rate 17.5% to 20% | **+0.0211** | gov.uk/vat-rates: "The standard rate of VAT increased to 20% on 4 January 2011 (from 17.5%)." | **page read** |
| UK-E2 | 2020-07-15 | temporary reduced rate 20% to 5% | **−0.1335** | GOV.UK "VAT: reduced rate for hospitality, holiday accommodation and attractions": 5% from 15 July 2020 to 30 September 2021 | **page read**. **Seen** (§0). **In H2 and secondary; not in H1** |
| UK-E3 | 2021-10-01 | 5% to 12.5% | **+0.0690** | same page: 12.5% from 1 October 2021 to 31 March 2022 | page read |
| UK-E4 | 2022-04-01 | 12.5% to 20% | **+0.0645** | same page: "From 1 April 2022 the normal VAT rules apply" | page read |

Covered supplies (page read): food and non-alcoholic drinks for consumption on the premises, hot takeaway food and hot takeaway non-alcoholic drinks. The page does not address cold takeaway or alcohol. The extensions of the 5% rate changed no rate and are not events.

**ONS index days relative to the effective dates (resolved).** Source: ONS ad hoc 3190, "Consumer price inflation index dates, January 2000 to November 2025" (xlsx, **file read**), cross-checked against the "data collected on or around" sentence of the bulletins for Jul 2020, Sep 2021, Oct 2021, Mar 2022 and Apr 2022 (**page read**; every date is a Tuesday).

| Event | Effective | Anchor month (index day, before) | First post-change month (index day, after) | Endpoint, h = 2 |
|---|---|---|---|---|
| UK-E1 | 2011-01-04 | 2010-12 (14 Dec 2010) | 2011-01 (11 Jan 2011) | 2011-03 |
| UK-E2 | 2020-07-15 | 2020-07 (14 Jul 2020) | 2020-08 (11 Aug 2020; **EOHO month, excluded**) | **2020-09** (fixed exception) |
| UK-E3 | 2021-10-01 | 2021-09 (14 Sep 2021) | 2021-10 (12 Oct 2021) | 2021-11 |
| UK-E4 | 2022-04-01 | 2022-03 (15 Mar 2022) | 2022-04 (12 Apr 2022) | 2022-05 |

In every case the anchor's index day precedes the effective date and the next index day follows it, so no event is split across an index day.

**Data-quality overlays on UK-E2, declared now.** Restaurants were closed for most of March to early July 2020; from April 2020 ONS collected prices centrally by phone, email and website and imputed index movements for unavailable items (July 2020 bulletin, **page read**); EOHO ran 2020-08-03 to 2020-08-31; hospitality closures and tier restrictions followed. These can make E2's matched counts fall below the §3.1 threshold. If so, E2's ρ̂ is not reported and H2 is **not testable**.

### Singapore, GST

| ID | Effective date | Change | Δ | Status in this registration | Source |
|---|---|---|---|---|---|
| SG-E1 | 2023-01-01 | 7% to 8% | **+0.0093** | **Confirmatory (H3), the only one.** Chinese New Year fell on 22 Jan 2023, inside the window (§5.1) | IRAS "GST Rate Change for Consumers": "7% to 8% with effect from 1 Jan 2023" (**page read**) |
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
- **Item VAT classification (committed, `docs/prereg_v2_uk_item_vat_status.csv`, before PRICE is read).** All 44 catering IDs, with per-event roles. Rules read from: GOV.UK hospitality reduced-rate guidance, VAT Notice 709/1 (catering) and VAT Notice 701/14 (food) (**page read**, the paragraph numbers are those returned by the page-reading tool), and HMRC's education manual for school meals (**search extract**). Result:

| Class | IDs | Count | Role |
|---|---|---|---|
| Standard-rated, in scope of the 2020-22 reduced rate (eat-in food and non-alcoholic drinks, pub items, hot takeaway) | 220106, 107, 111, 116, 118, 120, 121, 122, 126, 127, 128, 301, 304, 305, 316, 318, 319, 321, 322, 323, 326, 328, 329 | 23 | **treated** for E1 to E4 |
| Standard-rated, staff restaurant (taxable catering to staff, 709/1 2.6; the reduced-rate page is silent on staff canteens) | 220205, 208, 211, 212, 213, 214 | 6 | treated for E1 only; **excluded for E2 to E4** |
| Zero-rated (cold takeaway sandwich, 709/1 4.1) | 220303; 220330 (2026-02 onward) | 2 | **control**; 220330 is outside every event window |
| Standard-rated, **outside** the reduced rate (cold takeaway soft drink) | 220320; 220331 (2026-02 onward) | 2 | treated for E1; **control** for E2 to E4 |
| **Ambiguous (excluded everywhere)** | 220117 bottled water, 119 (no description), 124 muffin/cake, 125 bottled juice, 310 crisps, 317 pasty/pie, 324 cinema popcorn, 325 vending soft drink, 327 pastry snack: treatment depends on hot or cold, eat-in or takeaway, or machine location, none of which ITEM_DESC records | 9 | excluded |
| **Ambiguous, supplier-dependent** | 220209 primary school fixed charge, 220210 secondary school cafeteria: outside scope or exempt if the school supplies at or below cost, taxable if a contract caterer supplies | 2 | excluded |

  Zero-rated items are **excluded from H1 and H2** and are available only as a control. Only **one** zero-rated ID (220303) lies inside the event windows, and the only other within-window control is 220320; the control-item difference-in-differences needs at least 3 `control` IDs (below), so it is **infeasible for every UK event** (E1: one control ID; E2 to E4: two). It is reported as infeasible, not loosened.
- **Primary outcome per event:** the log of the Jevons price relative between the **anchor month** and the **endpoint month** over matched quote keys, equal-weighted within item, then the geometric mean over `treated` items with equal item weights. `SHOP_WEIGHT` weighting is a sensitivity.
- A month is a valid anchor or endpoint only if there are at least **500 matched relatives** across treated items between the two months. Months below are MISSING.
- **Secondary:** treated minus control-item relative, only for events where at least 3 `control` IDs have at least 100 matched relatives in both months (not met; see above).

### 3.2 Singapore

- Source: SingStat Table Builder **M213751** (CPI, 2024 as base year, monthly, **not** the seasonally adjusted M213752); the data.gov.sg mirror `d_bdaff844e3ef89d39fceb962ff8f0791` is the fallback. The vintage and fetch date are recorded in the results file.
- Series (labels and coverage, API read 2026-10-10): `1.11.1` **Restaurants, Cafes & Pubs** and `1.11.2` **Fast Food Restaurants**, both 2005-01 to 2026-08 (260 months); `1.11.3.1` **Hawker Centres**, 2019-01 to 2026-08 (92 months); `1.11.3` Hawker Centres, And Food Courts, Coffee Shops & Kiosks, 2005-01 to 2026-08 (260 months); `1.11.3.2` Food Courts, Coffee Shops & Kiosks and `1.11.1.1` to `1.11.1.3` (Restaurants, Cafes, Pubs) are sub-series of the 2024 base (the latter three from 2024-01 only and **not used**).
- **Treated:** the combination of 1.11.1 and 1.11.2, as the weighted sum of the two log changes with **fixed weights 537 : 86 (0.862 : 0.138)** applied to every anchor, event and placebo alike. **Resolved (page read):** the CPI is a base-weighted Laspeyres-type index with a fixed basket (information paper ¶38), so the weights in force are constant within a vintage: the 2019-based weights (Restaurants, Cafes & Pubs 537, Fast Food Restaurants 86) apply to all months through December 2023, the 2024-based (585, 85) from January 2024. Weights for earlier vintages were not found, so the 2019-based pair is used throughout for consistency.
- **Primary control:** `1.11.3.1` Hawker Centres. **Secondary control:** `1.11.3`.
- **Taxes are in the price (page read).** The SingStat information paper on rebasing the CPI (2024 as base year), ¶15: "Prices collected refer to those paid by consumers, that is, inclusive of taxes levied and net of subsidies/ rebates granted on the specific individual good or service". The paper's glossary names GST as such a tax. The paper does not say whether service charge is in the collected price, and that is now a **stated limitation, not a VERIFY item**: IRAS (**page read**, "Hotel and Food & Beverage") states "The service charge is subject to GST as it is part of the total price for goods and services provided" and that GST is computed on the price including service charge, so the mechanical log change in the tax-inclusive price is ln(1.08/1.07) = 0.0093 for SG-E1 whether or not the collected price includes service charge. It matters only if outlets changed their service-charge rate at the GST date; that cannot be observed in the CPI and is a limitation of H3.
- **GST-exclusive display is permitted (page read, IRAS).** IRAS requires GST-inclusive prices on displays but lets hotels and F&B establishments that impose a service charge "display GST-exclusive prices" with a prominent statement that prices are subject to GST and service charge; it does not extend to establishments with no or a nominal service charge. So "++" pricing is a lawful, common practice for registered restaurants, and a registered hawker stall with no service charge must display GST-inclusive prices.
- **Consequence for H3 ("++" outlets).** Because collected prices are tax-inclusive, an outlet that quotes menu prices "++" (GST and service charge added at the till) will show a mechanical rise of about the full GST step in the CPI **without any repricing**, and an outlet with GST-inclusive menu prices shows a rise only if it reprices. The CPI does not record which convention an outlet uses, so **the CPI test cannot separate the two, and H3 is registered as a test of the tax-inclusive consumer-price differential, not of repricing.** Separating them needs outlet-level menu data. Registered handling: (i) H3's wording and conclusion are limited accordingly; (ii) **H3b (exploratory)**: from archived or live menu pages of Singapore restaurant brands, classify each as "++" or GST-inclusive, record the share, and compare menu-price (pre-tax) changes around 2023-01-01 for the two groups; this needs its own data-collection protocol and is outside this registration's confirmatory tests.
- **Splice at the 2024 boundary (page read).** Information paper ¶43: "the 2019-based CPI data series are linked to the 2024-based CPI data series by re-scaling them to the new base year of 2024 via a link factor. The link factor is the ratio of the annual 2024-based index in 2024 to the annual 2019-based index in 2024." ¶42: Jan to Dec 2024 is the overlap year. So pre-2024 months are the 2019-based series multiplied by one constant, and 2024 months come from the 2024-based series (consistent with the M213761 footnote that prices "starting from January 2024 are based on the 2024-based CPI basket"). **The change from 2023-12 to 2024-01 therefore crosses a vintage boundary** (that the published table uses the 2024-based values from 2024-01 is an **inference**, not stated in so many words and not testable without reading values; the M213751 footnote describes only the weighting pattern. It affects only the demoted SG-E2 and is carried as a **flagged limitation**). Within the 2019-based vintage the month-on-month changes are unaltered by the rescaling. **SG-E1 (2022-12 to 2023-01, h = 1 or 2) lies entirely inside the 2019-based vintage and is not affected.** SG-E2 spans the boundary and is secondary partly for this reason.
- **SG-E0 (2007), what exists and what does not.** M213751 holds Restaurants, Cafes & Pubs, Fast Food Restaurants, and Hawker Centres, And Food Courts, Coffee Shops & Kiosks with **36 of 36 non-empty months in 2006-01 to 2008-12** (and 2005-01 onward). Which vintage these months come from: the SingStat September 2008 CPI release states "2004 = 100" (page read, archived copy), so 2007 lies in the **2004-based vintage**. How that vintage is carried into the 2024-based table is documented only for the 2019-to-2024 step (above); that the earlier steps used the same constant-link-factor method is **assumed, not verified**. The older information papers (2004 and 2009 base) returned 404 when fetched. The September 2008 release names only the group "Food". **Pre-run check (before any outcome is evaluated):** locate a SingStat document for the 2004- or 2009-based CPI that lists restaurant food, fast food and hawker food as separate classes; if none is found, SG-E0 moves to "Dropped events". Even if it stays, its control is the combined class that includes food-court operators, so it is secondary and cannot support H3.
- **M213761 (dish prices).** 85 series, 2015-01 to 2026-08. Ten cooked-food and drink series span all 140 months (coffee/tea without milk, coffee/tea with condensed milk, fishball noodles, mee rebus, chicken rice, chicken nasi briyani, economical rice, roti prata plain, fried carrot cake, ice kachang); ten begin 2024-01 (32 months) and are **not used** in any pre-2024 statistic. Footnote (page read): the prices "are not a measure of pure price movements across CPI baskets due to changes in the sample of brands/varieties and outlets priced." Used only as the **dish arm of H3 (H3-dish, secondary)**, restricted to the 10 full-span series; its gate and N are in §5.

### 3.3 H4 data

The IRAS GST-registered business search (§6) is the only data source for H4. It is used **manually**.

## 4. Statistic

For an event with effective date d and horizon h (months):

- **Anchor month a** = the last month whose price observation precedes d. UK: the ONS index day is the second or third Tuesday and the exact date is published in each bulletin (resolved for all four UK events, table in §2). SG: monthly CPI; for 1 January events a = December.
- **Endpoint month a + h.** **UK primary h = 2** (UK-E2 uses the fixed endpoint 2020-09). **SG: January events (SG-E1, SG-E2) use h = 2 primary and h = 1 secondary; the non-January event SG-E0 uses h = 1 primary and h = 2 secondary** (single rule, §10; reasoning in §5.1: at h = 2 every December same-month neighbour window contains the CNY month, so the local demeaning removes the CNY effect by construction). The CPI is tax-inclusive (§3.2), so the mechanical effect of a 1 January GST change is in the December-to-January change; the h = 2 window contains it plus the following month. h = 3 is exploratory. These choices were fixed before any outcome was evaluated.
- **Raw statistic** T_m = L_{m+h} − L_m, with L the log outcome level (SG) or the log matched price relative (UK).
- **Local baseline.** T*_m = T_m − mean of T_{m'} over eligible non-event anchors m' with the same calendar month, |m' − m| ≤ 36 months, m' ≠ m. An anchor is eligible only with **at least 3** such neighbours (changed from 4 in revision 1 because the hawker-centre series is only 7.7 years long and 4 left 57 anchors, below the resolution limit; accepted by WC). This removes seasonality (January repricing) and slow drift using only the sample's own months, and is applied identically to the event anchor and to every placebo anchor.
- **Signed statistic** U_m = sign(Δ)·T*_m. **Pass-through** ρ̂ = T*_a / Δ. For H3 the contrast is D_m = T*_{restaurant/fast-food, m} − T*_{hawker centres, m}, and ρ̂_D = D_a / Δ.

**H1 test statistic (revision 4): level-gap conformal statistic** (Chernozhukov, Wüthrich & Zhu 2021, cyclic-shift permutations). Used for the H1 events E3, E4, E1 and for the secondary UK-E2. T*, U and ρ̂ above are still computed for every UK event (§5.2).
1. **Series.** x_t = monthly log change of the chained matched Jevons index of treated items (the R1 series; the same series as the revision-3 φ̂).
2. **Retained months.** Every t with x_t defined, except changes inside another §2 event's window (t = e′, …, e′ + h − 1 for every §2 event e′ other than the tested one) and the changes into and out of 2020-08. The tested event's own window x_e, …, x_{e+h−1} is retained. A month is used only if x_{t−1} is also retained. The n retained months form a sequence in calendar order; gaps are skipped (the sequence is compressed), as simulated. **Gap rule (WC, 2026-10-24):** the event is **not testable** if any month t with |t − e| ≤ 2 is not in the retained sequence, where e is the event month (the first month of the window). This applies to the conformal test only. A month is not retained if it is unobserved, or if it is excluded as another event's window or by the EOHO rule. On the registered UK calendar (labels only), E1, E3 and E4 have no such gap; **UK-E2 is not testable**, because the EOHO exclusion of the changes into and out of 2020-08 lies within ±2 months of it. UK-E2's descriptive ρ̂ and CI are still reported. The 500-relative rule can add gaps; P0 applies the rule to the final calendar.
3. **Null fit** (H0: no effect, so the observed series is used as is). OLS of x_t on 12 calendar-month dummies and x_{t−1} over the n retained months gives the coefficient φ̃ and residuals u_1, …, u_n.
4. **Window statistics.** For each start position j = 1, …, n: S_j = sign(Δ) · Σ_{l=0}^{h−1} w_l u_{(j+l) mod n}, with w_l = Σ_{i=l}^{h−1} (h − i) φ̃^{i−l}. At h = 2, w = (2 + φ̃, 1). S_j equals the sum, over the window, of observed-minus-forecast log levels when the forecast is the AR(1) forecast from the month before the window. A permanent level step s at e therefore enters S at the event position as h·s. The observed statistic is S_obs = S_{j_e}, where j_e is the position of x_e.
5. **Test.** p = #{j : S_j ≥ S_obs} / n. Reject iff p ≤ α, that is iff S_obs is among the K + 1 largest S_j, with K = ⌊αn⌋ − 1. **Resolution:** n ≥ 60 at α = 0.0167.
6. **No random numbers** are used (the n shifts are enumerated). Code: `analysis/simulation/benchmark_mc.py`, `Conformal(level=True).shift_stats`.

## 5. Inference

### 5.1 Placebo pool (primary, and registered robustness pools R1 to R4; all are reported)

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

**Chinese New Year (CNY) in Singapore: calendar-only check and registered handling.** CNY moves between January and February, and food-service prices rise around it. Same-calendar-month neighbours (§4) do not control a holiday that moves between months. CNY dates 2005 to 2026 (first day of the lunar year; computed and cross-checked with the `lunardate` package; `cny_anchor_counts.py`, output `cny_anchor_counts_output.txt`):

| Class | Years |
|---|---|
| **Jan-CNY** (date in January) | 2006 (29 Jan), 2009 (26 Jan), 2012 (23 Jan), 2014 (31 Jan), 2017 (28 Jan), 2020 (25 Jan), **2023 (22 Jan, the SG-E1 window)**, 2025 (29 Jan) |
| **Feb-CNY** | 2005 (9 Feb), 2007 (18 Feb), 2008 (7 Feb), 2010 (14 Feb), 2011 (3 Feb), 2013 (10 Feb), 2015 (19 Feb), 2016 (8 Feb), 2018 (16 Feb), 2019 (5 Feb), 2021 (12 Feb), 2022 (1 Feb), 2024 (10 Feb, the SG-E2 window), 2026 (17 Feb) |

Define c_m = 1 if the month containing CNY lies in [m + 1, m + h] (the months over which the h-month change is measured), and j_m = 1 if in addition that CNY is a Jan-CNY. The SG-E1 anchor (2022-12) has c = 1 and j = 1 at h = 1 and h = 2. **At h = 2, c = 1 for every December anchor in every year** (CNY falls between 22 Jan and 19 Feb), so the c-deviation of the event anchor from its December neighbours is zero.

Eligible anchors (labels only; "A" = exposure-matched: anchors whose window contains a **Jan-CNY** month; "B" = anchors in Jan-CNY years, i.e. whose first endpoint month falls in a Jan-CNY year; "rule" = after also requiring at least 3 same-month neighbours inside the restricted set; R3-inf = anchors whose own c or j differs from their same-month neighbours' mean, i.e. those that can identify a CNY effect):

| Arm | h | All eligible (§4 rule) | A: base / rule | B: base / rule | any-CNY windows | CNY-free windows | R3-inf |
|---|---|---|---|---|---|---|---|
| Restaurants and fast food (2005-) | 1 | 247 | 7 / 0 | 94 / 0 | 20 | 233 | 35 |
| Restaurants and fast food | 2 | 240 | 14 / 0 | 93 / 0 | 39 | 210 | 52 |
| **Hawker Centres class (2019-)** | 1 | 81 | **2 / 0** | **34 / 0** | 6 | 81 | **5** |
| **Hawker Centres class** | 2 | 74 | **4 / 0** | **33 / 0** | 11 | 73 | **6** |
| Dish arm, 10 series (2015-) | 1 | 131 | 3 / 0 | 46 / 0 | 10 | 125 | 15 |
| Dish arm | 2 | 126 | 6 / 0 | 45 / 0 | 19 | 113 | 22 |

(The "CNY-free windows" column counts base-eligible anchors before the neighbour rule.) **Result:** restricting the primary pool to Jan-CNY years (A or B) falls below the resolution limit for α = 0.0167 (N + 1 ≥ 60) for **both H3 arms at both horizons**, and the neighbour rule inside the restricted set is never met (same-month Jan-CNY years are 2 to 3 years apart, so at most 2 neighbours lie within ±36 months). **The restriction therefore cannot be the primary rule; it is registered as robustness pool R4 (descriptive, reported with its N).**

**Registered CNY-timing adjustment, R3 (defined now).** For each arm and horizon, compute the deviations x^c_m = c_m − mean of c over the anchor's same-month neighbours and x^j_m likewise for j. Estimate (β̂_c, β̂_j) by OLS of T*_m on (x^c_m, x^j_m), no intercept, over the placebo anchors (event excluded), then T**_m = T*_m − β̂_c x^c_m − β̂_j x^j_m for the event anchor and every placebo anchor; ranks, CIs and the gate are then recomputed on T**. For the H3 contrast the adjustment is applied to each side and then differenced. R3 requires **at least 10 informative anchors** (R3-inf column); otherwise R3 is reported as "not estimable". **Result: R3 is estimable for the restaurant/fast-food series (35 and 52 anchors) and the dish arm (15 and 22) but not for the Hawker Centres class (5 and 6).** The consequence is registered openly. **At h = 1 the Hawker Centres test carries an unadjustable CNY exposure mismatch**: the event window (Dec 2022 to Jan 2023) contains CNY, but most of its same-month neighbours' Dec-to-Jan windows (Feb-CNY years) do not. The direction of the bias is unknown (against H3 if hawker prices rise more around CNY than restaurant prices, for H3 if the reverse). **This is why H3's primary horizon is h = 2 (Dec to Feb):** for every December anchor the window contains the CNY month, so exposure matches at month level for the event and all its same-month neighbours (c-deviation zero), and h = 1 is the pre-registered secondary that carries the mismatch.

**Residual CNY limitation at h = 2: temporary bumps (revision 3).** The month-level matching removes a permanent CNY step but not a CNY bump that reverts within a month; see §9 item 4 for the simulated bias. H3 is therefore decided by the intersection-union test of §5.4, which requires the h = 1 test (biased the other way) to reject as well; the limitation remains for the ρ̂ estimates, which are reported at both horizons. **Residual CNY limitation at h = 2: run-up timing.** The window matches on the CNY *month*, not on the CNY *date* relative to price collection. In Feb-CNY years where CNY falls late in February (on or after 15 Feb: 2007, 2015, 2018 and 2026; 19 Feb 2015 is the latest), the CNY run-up may fall after the February collection, while in Jan-CNY years and early-Feb years it falls inside the window. The j-indicator in R3 targets this, but R3 is not estimable for the Hawker Centres class (6 informative anchors at h = 2), so the residual stays unadjusted for that arm; it is reported for the dish arm with and without R3. Within the hawker series' same-month neighbours of the SG-E1 anchor, the December anchor of 2025 (CNY 17 Feb 2026) is the late-CNY case. H3 conclusions are worded with this limitation, and the h = 1 estimate is reported beside the h = 2 estimate.

**SG-E0 (2007-07-01, anchor 2007-06; CNY 18 Feb 2007, a Feb-CNY year).** The windows for h = 1, 2, 3 are July, August and September, which never contain a CNY month (CNY falls in January or February), so c = 0 and no CNY adjustment is needed. The exposure-matched pool is the set of CNY-free windows: 233 (h = 1) and 210 (h = 2) base-eligible anchors for the restaurant/fast-food series. The 2007 event is not CNY-confounded; its issues are the control class and the 2004-based vintage (§3.2).

### 5.2 Tests, point estimates and confidence intervals

- **Test (revision 4).**
  - **H1 events (E3, E4, E1) and the secondary UK-E2:** the level-gap conformal p of §4.
  - **H3 components** (hawker contrast at h = 2 and h = 1), **H3-dish**, and the **secondary SG events** (SG-E2, SG-E0): the one-sided placebo rank p, p = (1 + #{placebo m : U_m ≥ U_a}) / (N + 1), with no calibration (§5.5).
  - **H3 and H3-dish are each decided by the intersection-union test of h = 2 and h = 1** (§5.4).
  - **H3-dish is decided by the same two-horizon rule as H3** (WC, 2026-10-24; simulated, `output/prereg_v4/`, cell `SG-E1 dish IUT`). SG-E2 and SG-E0 are reported per horizon (descriptive secondaries; not simulated as an IUT).
  - For UK events, the revision-3 placebo rank p on U is also reported, as a descriptive figure.
- **Reporting commitment.** For **every evaluable event, whether or not it passes the gate or rejects**, I report ρ̂ with a **95% confidence interval** and the placebo p for each registered horizon. CI by placebo test inversion: with G_m = T*_m / Δ over the placebo pool, CI₉₅ = [ρ̂ − q₀.₉₇₅(G), ρ̂ − q₀.₀₂₅(G)], valid under the shift model (event statistic = placebo-like noise + ρΔ). The same is done for H3's D/Δ and for the descriptive H2 difference (§5.4). Results are reported as estimates with intervals, never as pass/fail alone, for the primary pool and for R1 to R4 (R3 and R4 for SG only). **Revision 4 (WC, 2026-10-24): for H1 the confirmatory decision and the reported estimate are different objects.**
- **The decision** is the conformal test of §4 alone.
- **ρ̂ and its 95% CI** are T*-based, computed exactly as above, and **labelled descriptive**. They are not an inversion of the conformal test. A CI that excludes 0 is not a rejection, and a rejection does not imply that the CI excludes 0; the two can disagree, and both are reported as they come out.
- **The level-gap estimate** ρ̃ = S_obs / (h·Δ) is reported beside ρ̂, also descriptive.

The R1–R4 robustness pools are defined on placebo anchors and apply to the rank-test p on U. For H1 they are reported for that descriptive rank p only. **UK-E2, which is not in H1, gets ρ̂, a 95% CI and its placebo p as a secondary result** (if evaluable), clearly labelled seen and confounded.
- **What the gate does and does not guarantee (revision 4).** The informativeness gate (§5.3) is designed so that **full pass-through (ρ = 1) would be detected with at least 80% power among datasets that pass it**.
  - **Revision-3 claim.** The q₁₀ gate on the calibrated critical value delivered 0.821 to 0.908 in simulation. **But in revision 3 the size of the test among datasets that pass the gate was not α.** It was 0.021–0.032 when the gate passes half the time and up to 0.06 when it passes 10% of the time. The reason is that the gate passed when the placebo spread happened to be small, and that same small spread inflated the calibrated statistic (`analysis/simulation/output/method_fixes/gate_conditional_size.csv`; `docs/math_claims.md` C4). Revision 4 replaces the gate (§5.3) and the tests (§4, §5.5) so that the size among informative events is controlled.
  - **Revision-4 power claim, verified by simulation only** (`output/prereg_v4/gate_guarantee.csv`; Gaussian AR(1) noise, φ ∈ {0, 0.3, 0.6, 0.9, 0.97}, 20,000 runs; minimum over |Δ|/σ of P(reject at ρ = 1 | gate passes)):

| Procedure | Minimum P(reject at ρ = 1 given gate passes) |
|---|---|
| H1 conformal test (UK-E3, E4, E1; UK-E2) | 0.819 to 0.897 |
| H3 IUT | 0.815 to 0.917 |
| H3-dish IUT | 0.857 to 0.937 |

  - **It holds for φ ≥ 0.** At φ = −0.5 the H3 IUT reaches 0.693 (revision 3's procedure 0.665).
  - **It is not a guarantee under other noise.** Under AR(2), seasonal AR, t(3) innovations, a drift break or a level step, the H1 minimum is 0.59–0.88 and the H3 IUT minimum 0.78–0.93.
  - **Why there is no deterministic version.** The revision-3 bound "rejection whenever the noise exceeds c − Δ" does not carry over: the symmetric gate's pooled critical value is at most the test's critical value and equals it only when the test rejects (`docs/math_claims.md` E5).
  - **Partial pass-through.** The gate says nothing about partial pass-through. A non-rejection does not exclude ρ = 0.3 or ρ = 0.6, which published estimates for other settings span (§0). A null here is therefore **uninformative about partial pass-through**, and the CI, not the p-value, is the evidence.

### 5.3 P0 informativeness gate (revision 4: symmetric gate)

**Revision 4 replaces the revision-3 gate** (MDE_ρ = (c − q₁₀)/|Δ| over the placebo pool, with c the calibrated critical value). The revision-3 gate depended on the placebo values only. Conditioning on it inflated the size among informative events (§5.2). The revision-4 gate is a **symmetric function of all the values the test compares, the event's included**. For a test of this kind (a randomization test), passing such a gate leaves the test's size unchanged when the randomization hypothesis holds (`docs/math_claims.md` B4, theorem candidate). In simulation, the size among datasets that pass the gate was within Monte Carlo error of the unconditional size (§5.5 table).

- **Pooled values.**
  - For a rank test (H3 components, H3-dish, SG secondaries): the N + 1 values {U_a} ∪ {U_m : m placebo}, K = ⌊α(N + 1)⌋ − 1.
  - For the conformal test (H1, UK-E2): the n window statistics {S_j}, K = ⌊αn⌋ − 1.
- **c_pool = the (K + 2)-th largest pooled value.** It equals the test's own critical value whenever the test rejects and is never larger. *Why not the (K + 1)-th:* that value is the event's own statistic whenever the test rejects. At K = 0 (H3 hawker, N = 74) the gate would then fail exactly when the true effect is large.
- **q_p = q₀₅, the pooled 5th percentile (numpy linear interpolation).** **MDE_ρ = (c_pool − q₀₅) / (h_S·|Δ|)**, with h_S = 1 for rank tests and h_S = h for the conformal test (a step s moves S_obs by about h·s).
  - **q₀₅ (WC, 2026-10-24) replaces q₁₀, because q₁₀ failed the 80% check** under the symmetric gate: minimum P(reject at ρ = 1 | gate passes) 0.61–0.90 for H1 and 0.64–0.88 for the H3 IUT (`output/prereg_v4/gate_guarantee.csv`).
  - **The 80% claim with q₀₅** (§5.2; simulation only, Gaussian AR(1) noise): minimum P(reject at ρ = 1 | gate passes) of 0.819–0.897 for H1, 0.815–0.917 for the H3 IUT and 0.857–0.937 for the H3-dish IUT, for φ ∈ [0, 0.97].
  - **Exception, stated now: φ = −0.5** (negatively autocorrelated monthly changes). There the minimum is 0.693 for the H3 IUT and 0.748 for the H3-dish IUT, below 0.80 (revision 3's procedure: 0.665). The H1 minimum at φ = −0.5 is within its 0.819–0.897 range. The claim also does not hold under the misspecified noise of §5.4.
  - Cost: the H3 gate passes half the time at |Δ|/σ = 5.68, against 5.46 for revision 3.
- **H3's informativeness is judged on the h = 2 gate** (unchanged). Under the fixed sequence (§5.4), each H1 gate is computed at α = 0.0167.
- **Blinding (changed in revision 4).** The gate now needs the event's value, so the revision-3 rule "computed from the placebo pool only, by a script that cannot read the event windows" no longer applies. Replacement:
  - The P0 script reads the pooled values and **outputs only N (or n), c_pool − q₀₅, MDE_ρ and the pass/fail decision**. All of these are symmetric functions, which carry no information about the event's rank under the null.
  - It never outputs U_a, S_obs, a rank or a p-value.
  - The §8 masking test is replaced by an **invariance test**: the P0 output must be identical whichever pooled value is labelled as the event. The P0 output is committed before event statistics are computed.
  - **Accepted by WC (2026-10-24).** The P0 script and its invariance test are written, were run on synthetic data, and are committed; their SHA-256 hashes are in §8.

An event (or contrast) is **informative** iff MDE_ρ ≤ 1.0 and its test meets the resolution rule (N + 1 ≥ 1/α for rank tests; n ≥ 1/α for the conformal test). Events not evaluable (§4) or not informative are reported descriptively with their ρ̂ and CI and are **excluded from the confirmatory family**, never dropped silently. Threshold 1.0 was fixed before any outcome was evaluated. *(Revision 4 also removes an accidental duplicate of the first sentence of this paragraph.)*

**P0 design for H3 (SG-E1, Jan 2023, Δ = 0.0093).**
- **N.** CPI-class contrast: restaurants/fast-food (247) against Hawker Centres (81 at h = 1; 74 at h = 2): the contrast is defined only where both exist, so at the **primary h = 2, N = 74** (secondary h = 1: 81). Dish arm (H3-dish, 10 full-span M213761 series against the restaurant class, both available 2015-01 onward): **N = 126 at h = 2** (secondary h = 1: 131).
- **Resolution.** At α = 0.0167 the rank test needs N + 1 ≥ 60; both arms meet it at h = 2 (75 and 127).
- **The MDE condition in plain terms.** *(The arithmetic in this item is for the `prereg-v2` statistic q₉₅ − q₂₀ and is kept as written; under revision 4 the condition is c_pool − q₀₅ ≤ Δ on the pooled values, §5.3 above.)* MDE_ρ ≤ 1 means q₉₅ − q₂₀ of the demeaned contrast must be at most Δ = 0.0093, i.e. 0.93 log points. If the placebo contrast were roughly normal that requires a standard deviation of about 0.37 log points for the **h = 2** (two-month) demeaned contrast (q₉₅ − q₂₀ ≈ 2.49 σ). If monthly changes are roughly independent, a two-month change has about 1.4 times the standard deviation of a one-month change, so the primary h = 2 gate is harder to meet than the h = 1 gate would be.
- **Whether this can plausibly be met.** I cannot say from the data without reading the placebo values, which this revision does not do. On general knowledge, month-on-month movements of these CPI food-service classes are of the order of a few tenths of a percent, and a contrast of two classes has a variance equal to the sum of both, so I expect the condition to be **marginal at best and more likely to fail than to pass** for the Hawker Centres contrast at h = 2 (more so than at h = 1), and to be easier for the dish arm only if the dish averages are smooth (they are indicative averages on a changing basket, so I would not expect that). **Registered rule: if the P0 gate fails, H3 is reported as "not testable"** (the rule H2 had before revision 4; H2 is now descriptive), with ρ̂, CI and N, and no confirmatory claim. This outcome is accepted in advance; with a single event the pooled-event variance reduction available in revision 1 is no longer available.
- **UK gates, for reference.** The same MDE_ρ condition applies per UK event (revision 4: (c_pool − q₀₅)/(h·|Δ|) on the conformal window statistics): thresholds ≤ 0.0690 (E3), 0.0645 (E4), 0.0211 (E1) for H1, and 0.1335 (E2) for its secondary result. UK-E2 is not testable under the conformal gap rule (§4), so in practice it is reported descriptively.
- **SG-E2 (Jan 2024, Δ = 0.0092), primary h = 2.** The placebo pool excludes every event window, so its N is the same as for SG-E1 at h = 2: **Hawker Centres class N = 74, 10-dish arm N = 126, restaurants and fast food N = 240**; resolution at α = 0.0167 is met (N + 1 ≥ 60). The informativeness condition is c_pool − q₀₅ ≤ **0.0092** for the h = 2 contrast (revision 4; revision 3 used c − q_p on the placebo pool). SG-E2 is secondary, so a failed gate means descriptive reporting with ρ̂ and CI, as for any non-informative event; it never enters the confirmatory family.
- **CNY and the gate.** The gate is computed on the pooled primary-pool T* (event included, revision 4), which contains CNY-exposed anchors for both arms. Because CNY-exposed windows are likely noisier, the gate can only be easier to meet than a CNY-matched gate would be; the R4 pool is too small to gate. This is a registered limitation of the h = 1 test; at h = 2 the exposure is matched at month level, with the run-up timing limitation of §5.1.

### 5.4 Multiplicity

**Revision 4: two confirmatory hypotheses, H1 and H3** (H2 demoted to descriptive, §1). **α = 0.0167 each, unchanged (WC, 2026-10-24).** H2's former 0.0167 is not reallocated, so the confirmatory family uses 0.0334 of the original α = 0.05 budget. Inside H1, the **three clean events** are tested in the fixed order **E3 (Oct 2021) → E4 (Apr 2022) → E1 (Jan 2011)** (decreasing |Δ|: 0.0690, 0.0645, 0.0211; E2 is not in the sequence), each at α = 0.0167 with the conformal test of §4 (revision 4), stopping at the first non-rejection or non-informative event. Fixed-sequence testing is used because Holm over three events has a first-step threshold of 0.0056, about the placebo resolution 1/(N+1) ≈ 0.006 for N ≈ 170, whereas every step here needs only N + 1 ≥ 60. H1 is claimed if at least E3 rejects (an event that is not informative or not evaluable ends the sequence and is reported descriptively).

**H3 decision rule (revision 3): intersection-union test.** H3 is rejected only if **both** the h = 2 and the h = 1 hawker-contrast tests reject, each at α = 0.0167 by the placebo rank test (revision 4; revision 3 used the calibrated critical value of §5.5). An intersection-union test needs no further multiplicity adjustment: its size is at most α. H3's informativeness is judged on the h = 2 gate (§5.3); the h = 1 test has N = 81 and meets the resolution rule. ρ̂ and CIs are reported at both horizons. *Why:* a temporary CNY bump biases the two horizons in opposite directions (§9 item 4), so requiring both guards against a CNY artefact in either direction. Revision-3 simulation (calibrated components; `output/prereg_v3/iut_power_no_bump.csv`, `iut_cny_scenarios.csv`; φ = 0, σ at the h = 2 gate's 50% point, 0.171 log points; 20,000 runs), kept as the record of why the IUT was adopted:

| Scenario (hawker bump b) | Size, h = 2 only | Size, IUT | Power ρ = 1, h = 2 only | Power ρ = 1, IUT |
|---|---|---|---|---|
| No bump | 0.0171 | 0.0048 | 0.877 | 0.877 |
| Temporary, CNY month, b = +0.25 / +0.5 / +1.0 pts | 0.049 / 0.117 / 0.355 | 0.0013 / 0.0001 / 0.0000 | 0.949 / 0.978 / 0.998 | 0.925 / 0.778 / 0.178 |
| Temporary, CNY month, b = −0.25 / −0.5 / −1.0 pts | 0.0029 / 0.0006 / 0.0001 | 0.0022 / 0.0006 / 0.0001 | 0.727 / 0.475 / 0.095 | same |
| Permanent, CNY month, b = +0.25 / +0.5 / +1.0 pts | 0.015 / 0.014 / 0.012 | 0.0008 / 0.0002 / 0.0000 | 0.873 / 0.867 / 0.852 | 0.862 / 0.781 / 0.283 |
| Permanent, CNY month, b = −0.25 / −0.5 / −1.0 pts | 0.016 / 0.017 / 0.011 | 0.011 / 0.015 / 0.011 | 0.875 / 0.864 / 0.847 | same |
| Temporary, run-up (CNY − 15 d), b = +0.5 / +1.0 pts | 0.037 / 0.074 | 0.0022 / 0.0007 | 0.932 / 0.969 | 0.925 / 0.922 |
| Permanent, run-up, b = ±0.5 pts | 0.018 / 0.018 | 0.0018 / 0.0096 | 0.878 / 0.877 | 0.873 / 0.877 |

Without a bump the IUT keeps power at ρ = 1 (0.877, and min P(IUT reject | h = 2 gate passes) 0.865, 0.870, 0.892 at φ = 0, 0.6, 0.9) and is conservative (size 0.0048 at φ = 0; 0.0088 and 0.0133 at φ = 0.6 and 0.9). It removes the over-rejection that a positive temporary hawker bump causes at h = 2 (0.117 → 0.0001 at +0.5 pts). Its cost is power when the hawker bump is large and positive (0.778 at +0.5 pts, 0.178 to 0.283 at +1.0 pts), because the h = 1 test is then biased against H3. H4 is descriptive. Everything else is exploratory (§7).

**Revision 4, H3 with rank-test components and the symmetric gate** (`analysis/simulation/output/prereg_v4/`; 20,000 runs).
- **Size.**
  - Without a bump, under Gaussian AR(1) noise (φ = −0.5 to 0.97), AR(2), seasonal AR, t(3) innovations, a drift break and a level step: 0.000 to 0.016.
  - Among datasets that pass the h = 2 gate (pass rates 10%, 50%, 90%): 0.000 to 0.018. None more than 2 SE above α.
  - Revision 3's IUT, among datasets that pass its gate: up to 0.032 under Gaussian noise and 0.040 under t(3).
- **Weakness at h = 2 alone.** Each component on its own over-rejects at φ ≥ 0.9 (h = 2: 0.025 and 0.028; the placebo statistics are not exchangeable, `docs/math_claims.md` B3). The IUT absorbs this.
- **CNY scenarios** (`cny.csv`: temporary and permanent hawker bumps of ±0.5 and ±1.0 points, σ = 0.2 and 0.4 points): IUT size at most 0.0155 for both revisions.
- **Power** (probability that the h = 2 gate passes and H3 is rejected), against revision 3:

| φ | |Δ|/σ | ρ = 1, revision 4 | ρ = 1, revision 3 |
|---|---|---|---|
| 0 | 6 | 0.40 | 0.71 |
| 0.6 | 7.1 | 0.35 | 0.53 |
| 0.9 | 7.1 | 0.53 | 0.54 |

  Part of revision 3's apparent power is the conditional over-rejection that revision 4 removes.
- **Considered and not adopted:** a residual-bootstrap calibration of the components. Among datasets that pass the gate, its size was 0.028–0.033 at h = 2 and up to 0.032 under the IUT (`docs/math_claims.md` C7).

**Revision 4, H1** (conformal test, symmetric gate q₀₅).
- **Size of each H1 test,** across the same noise models: 0.004 to 0.019; among datasets that pass the gate, 0.003 to 0.019. The one flagged cell is UK-E3 under the drift break, 0.0187 unconditional.
- **Revision 3's H1 test, among datasets that pass its gate:** 0.016 to 0.057, more than 2 SE above α at gate pass rates of 10% and 50% on every Gaussian setting.
- **Power** (probability that the gate passes and the event is rejected), UK-E3, |Δ|/σ = 5.05:

| φ | ρ | Revision 4 | Revision 3 |
|---|---|---|---|
| 0 | 1 | 0.90 | 0.28 |
| 0 | 0.5 | 0.42 | 0.12 |
| 0.6 | 1 | 0.89 | 0.01 |

- **Robustness to CNY steps.** Revision 4's H1 test, unlike the T* statistic, does not remove a step that moves between calendar months exactly (`docs/math_claims.md` F3). That matters only for Singapore, where it is not used.
- **Variance spike.** A variance spike at the event month (variance × 3) breaks every procedure (sizes 0.035–0.066). This is a stated limitation of any placebo or permutation method, not specific to revision 4.

**H2 (descriptive, revision 4).** No test and no gate; revision 3's H2 test and gate are withdrawn.
- A = mean over the evaluable UK rise events of (T*_e / Δ_e) minus T*_{E2} / Δ_{E2}, i.e. the difference in ρ̂ between the rises and the cut.
- **95% CI by placebo inversion:** B = 9,999 draws of distinct eligible anchors, assigned to the same event slots with the same Δ constants, give placebo values A_b. CI₉₅ = [A − q₀.₉₇₅(A_b), A − q₀.₀₂₅(A_b)], under the same shift model as §5.2.
- Reported with each event's ρ̂ and CI.

### 5.5 Size control (revision 4: the revision-3 calibration is withdrawn)

**Revision 3 (D2-b, tag `prereg-v3` §5.5)** tested every event against a critical value calibrated by Gaussian AR(1) simulation at the Kendall-corrected φ̂. It is **withdrawn** for three reasons, all from synthetic simulation (`docs/math_claims.md` C4, C5, C7):
1. Among datasets that pass the gate, its size was not α (§5.2).
2. Under t(3) innovations its size was 0.030–0.035, and under seasonal AR up to 0.025 (`output/misspec/`).
3. Replacing the Gaussian model by a residual bootstrap fixed (2) but not (1): 0.028–0.033 among datasets that pass the gate, at h = 2.

**Revision-4 rule.** No event is tested against a calibrated critical value. H1 uses the conformal test (§4). H3, H3-dish and the SG secondaries use the placebo rank test (§5.2). Each test's size, unconditionally and among datasets that pass the gate, is controlled by the randomization argument of `docs/math_claims.md` B4. That argument is exact for an idealised exchangeable model only (B3), so the figures below are the evidence. φ̂ is still computed (§5.5 step 1 of revision 3) and reported descriptively. It no longer enters any decision.

**Size, revision 4** (synthetic; `analysis/simulation/output/prereg_v4/size.csv`; 20,000 runs per cell; MC SE ≈ 0.0009 unconditionally). "Given gate" means among datasets that pass the q₀₅ symmetric gate, at gate pass rates of 10%, 50% and 90%. "Gaussian" means AR(1) with φ ∈ {−0.5, 0, 0.3, 0.6, 0.9, 0.97}. "Other noise" means AR(2), seasonal AR(12), t(3) innovations, a drift break and a level step. "Flagged" means more than 2 SE above α. The variance-spike scenario is excluded; every procedure fails it (§5.4).

| Setting (decision) | Gaussian | Given gate, Gaussian | Other noise | Given gate, other noise |
|---|---|---|---|---|
| UK-E3, conformal (H1) | 0.0104–0.0120 | 0.0094–0.0145 | 0.0049–0.0187 (1 flagged: drift break) | 0.0045–0.0188 |
| UK-E4, conformal (H1) | 0.0110–0.0123 | 0.0105–0.0135 | 0.0037–0.0171 | 0.0032–0.0167 |
| UK-E1, conformal (H1) | 0.0100–0.0130 | 0.0055–0.0155 | 0.0046–0.0139 | 0.0025–0.0145 |
| UK-E2, conformal (secondary) | 0.0111–0.0121 | 0.0095–0.0175 | 0.0053–0.0181 | 0.0045–0.0215 |
| **H3 IUT (h = 2 and h = 1), rank** | **0.0013–0.0157** | **0.0010–0.0175** | **0.0001–0.0095** | **0.0002–0.0130** |
| H3-dish IUT, rank (secondary) | 0.0021–0.0176 | 0.0020–0.0205 | 0.0022–0.0099 | 0.0022–0.0125 |
| H3 hawker h = 2 alone, rank (component) | 0.0111–0.0284 (flagged at φ ≥ 0.9) | 0.0113–0.0280 | 0.0019–0.0265 | 0.0022–0.0325 |
| H3 hawker h = 1 alone, rank (component) | 0.0107–0.0202 (flagged at φ = 0.97) | 0.0095–0.0200 | 0.0003–0.0208 | 0.0002–0.0211 |
| Dish h = 2 alone, rank | 0.0147–0.0267 (flagged at φ ≥ 0.9) | 0.0137–0.0335 | 0.0062–0.0214 | 0.0066–0.0300 |

**Stated limitation.** An H3-family test at a single horizon over-rejects when the monthly changes are highly persistent (φ ≥ 0.9). This affects the per-horizon p-values reported for H3 and H3-dish, SG-E2 and SG-E0. The confirmatory H3 decision is the IUT, whose size stays within α in every simulated setting. Per-horizon p-values are reported with this caveat.

## 6. H4: GST registration among hawker stalls (descriptive)

- **What the search can and cannot show (page read, IRAS).** One business name (at least the first five characters) **or** up to four UEN / GST numbers per search; a CAPTCHA each search; no stated result fields. It matches registered names and UENs, not stall signboard names.
- **"Not found" is not "not registered".** A stall registered under a name or UEN that I could not obtain, or recorded under a different name, returns "not found". The registered share computed from found, currently registered stalls is therefore a **lower bound** on the true share.
- **Outcome categories for every sampled stall:** `registered` (a matching entry with current registration, and, if the result shows a registration date, registered on or before 2023-01-01), `not found`, `ambiguous` (several matches), `unmatchable` (no registered name or UEN obtainable for the stall).
- **Estimand and reporting.** Lower bound p_L = registered / n_all; upper bound p_U = (registered + not found + ambiguous + unmatchable) / n_all. Report both with cluster-robust 95% intervals (clusters are hawker centres; Wilson interval as the headline), and the counts of each category. Nothing is dropped.
- **Link to H3 (revised).** If **p_L ≥ 0.5**, H3 is worded as "restaurant and fast-food versus hawker-centre" with no registration interpretation. If **p_U < 0.5**, the registered-versus-unregistered reading is permitted, with the bounds. Otherwise the reading is **indeterminate** and is not used.
- **Frame and sample size (fixed; WC accepted).**
  - **Frame:** the NEA hawker-centre list on data.gov.sg (a centre-level list with cooked-food stall counts; search extract found a 2016 list of 107 centres and a newer NEA dataset; **VERIFY** the current dataset and its stall-count field before sampling). Centres with fewer than 20 cooked-food stalls are excluded from the frame. **Regions:** the five URA planning regions (Central, East, North, North-East, West), assigned from the centre's address or planning area (**VERIFY** the dataset carries one).
  - **Sample:** **12 centres, 10 stalls each, 120 stalls**. **Selection rule (fixed now).** Sort the frame by centre name (ASCII order) within each region. Allocate the 12 centres to regions in proportion to the number of frame centres per region by the largest-remainder method, with a minimum of 1 per region. Within each region draw that many centres without replacement using Python `random.Random(20261010)`, `sample()` on the sorted list, regions processed in alphabetical order; **the seed is 20261010 and is fixed here**. Within a centre with S cooked-food stalls numbered in a fixed walking order from the main entrance, take every k-th stall, k = ⌊S/10⌋, from a random start in 1..k drawn from the same generator after all centre draws (WC's site visit). If a drawn centre is closed or inaccessible, the next centre in that region's sorted draw order replaces it and the replacement is logged. Worst-case Wilson half-width about ±9 percentage points before clustering; a larger design effect is expected.
  - **Feasibility:** names are first matched offline against the ACRA entity datasets on data.gov.sg (metadata read: "ACRA Information on Corporate Entities", split by UEN type, updated 2026-09-16; **VERIFY** that it covers sole-proprietorship business names) to obtain UENs; UEN lookups go four to a search, so 120 stalls need at most 30 IRAS searches, and any stall without a UEN needs one search of its own. At about two minutes per CAPTCHA search, 120 stalls need about 1 to 3 hours of manual lookup. A sample of 150 would be affordable but widens the fieldwork; 120 (12 × 10) is the registered size.
- **Process.** Manual, one person reads the CAPTCHA; no automation; **no NRIC search**; each query's date, time and result category are logged. Only public registered business names are stored.

## 7. Confirmatory versus exploratory

**Confirmatory (this registration):** H1 (UK-E3, E4, E1 in that order, informative events only; level-gap conformal test, revision 4) and H3 (SG-E1, Hawker Centres control, if testable; decided by the h = 2 and h = 1 intersection-union test of placebo rank tests, §5.4). "Confirmatory" carries the §0 qualifier; the "seen" labels for UK-E2 and SG-E2 stay attached.

**Secondary (labelled):** H2 (descriptive since revision 4: the rises-minus-cut difference in ρ̂ with its CI, no test, §5.4); UK-E2 ρ̂ and CI; SG-E2 (2024) and SG-E0 (2007) results, with CIs; **the secondary SG horizon under the §10 rule (h = 1 for SG-E2, h = 2 for SG-E0; for SG-E1, h = 1 is part of the H3 decision since revision 3)**; H3-dish (with and without R3; decided like H3 by the h = 2 and h = 1 intersection-union test, revision 4); R1 and R2 pools for every event, R3 and R4 for SG events (reported alongside the primary); the UK control-item difference-in-differences; sale-price exclusion sensitivity; the COVID-excluded pool.

**Exploratory (labelled "exploratory" wherever it appears):** H3b ("++" menu-price check); M213761 dishes other than the 10 full-span series; "Restaurants and Cafes" and other 2024-only sub-series; any event not in §2; any other control definition; any analysis suggested by looking at the results.

## 8. Exclusions, deviations and stopping rules

- **EOHO.** August 2020 is never an anchor or endpoint and never enters a baseline average. It is a month-level exclusion, not an adjustment. If the August 2020 quote file is found to carry a documented flag that identifies discounted quotes before any outcome is evaluated (none was found in the glossary), flagged quotes may be removed and the month re-admitted as a recorded deviation. The sensitivity that includes August 2020 with raw PRICE is exploratory.
- **Missing months** are never filled. No seasonal adjustment (M213752 is not used).
- **No result-dependent choices.** Horizons, thresholds (500 relatives, MDE_ρ ≤ 1.0, ≥ 3 neighbours, ±36 months), series and controls are fixed. A change after the P0 output is committed is a deviation, listed with a reason.
- **If the specification cannot be executed as written, the run stops and reports.**
- **Code** is frozen at a commit SHA recorded in the results commit. Before real data are used, the placebo procedure is run on **simulated** series with a known injected pass-through (size and power check, simulated data only). **Revision 4:** the P0 script is verified to produce identical output whichever pooled value is labelled as the event, and to output no event value, rank or p-value (§5.3). This replaces the revision-3 check that it cannot read masked event windows. The script, the test and the test's output on synthetic data (PASS) are committed (commit be9f184), with SHA-256:

| File | SHA-256 |
|---|---|
| `analysis/prereg_v4/p0_gate.py` | `624a9c324829e98a9af0e7c88e552128e95112866fa52e2d7c67a2fed785dad1` |
| `analysis/prereg_v4/test_p0_invariance.py` | `d0de103b696ff4a60e3dbd5108f3cea74786957fe991721be38f62e55b623b86` |
| `analysis/prereg_v4/test_p0_invariance_output.txt` | `cae6c02e2acb6a3ae62806b6ad7f6b8f114ee909e22b3ec46c0fac5f403f45c3` |

The test checks four things:
1. The gate output is identical for every choice of event position and under random permutations of the pooled values.
2. The output contains only whitelisted fields.
3. The ±2-month gap rule makes an event not testable.
4. P0's gate statistic equals the revision-4 simulation's on the same synthetic series (maximum difference 4.6 × 10⁻⁹).

The P0 run on real data uses these files unchanged. A file whose hash differs is a deviation.
- **Provenance.** Only public sources: ONS, SingStat, IRAS public search, GOV.UK. No residential-IP live-scrape data and no UICPI index values enter a confirmatory test.

## 9. What must be done before the confirmatory run (item 4 simulation done in revision 3; the rest not done)

1. **Done:** `docs/prereg_v2_uk_item_vat_status.csv` (44 IDs, per-event roles, evidence). Reviewed by WC before merge: the 9 ambiguous and 2 school IDs excluded, and the infeasibility of the control-item difference-in-differences.
2. **Done:** ONS index days for E1, E3, E4 (and E2); SG class weights; service-charge treatment recorded as a limitation.
3. **Open VERIFY:** SG-E0 2004-based class-definition check (§3.2, keeps the drop rule); the 2024-01 vintage switch (flagged limitation, demoted event only); the URA-region field and ACRA name coverage for H4; the `VALIDITY`/`INDICATOR_BOX` filter commit (§3.1) and the per-pair sale-price sensitivity code.
4. The simulation (including a CNY-like calendar shock), P0 script and invariance test (§8). **Simulation: done (revision 3, synthetic data only; `analysis/simulation/`, PR #55 and `prereg_v3_checks.py`). Revision 4: done (`analysis/simulation/prereg_v4_sim.py`, PR #67; size, size among datasets that pass the gate, power, gate check and CNY scenarios for the revision-4 procedure; output `analysis/simulation/output/prereg_v4/`).** The P0 script and the invariance test are written and pass on synthetic data (§8). Size and power of the rank test, the gate (§5.2, §5.3) and the size-control rule (§5.5) are reported there. **CNY-like shock (H3):** a moving holiday bump on the hawker arm at the real CNY dates 2015–2026, magnitudes ±0.25, ±0.5, ±1.0 log points, temporary (one month, then reverts) or permanent (step), timed at the CNY month or at CNY − 15 days (run-up); noise SD of the contrast's monthly change 0.2 and 0.4 log points (`output/prereg_v3/a3_cny_bump.csv`). The bias is exact (T* is linear): bias(ρ̂) = k × b / Δ with b the hawker bump and Δ = 0.0093:

   | Horizon | Bump | Timing | k | ρ̂ bias at b = +0.5 log points | Size of H3 (rank test), b = +0.5 / −0.5 pts, SD 0.2 pts |
   |---|---|---|---|---|---|
   | h = 2 (primary) | temporary | CNY month | **+0.6** | **+0.32** (towards H3) | 0.061 / 0.0005 |
   | h = 2 | permanent | CNY month | 0 | 0 | 0.010 / 0.012 |
   | h = 2 | temporary | run-up | +0.2 | +0.11 | 0.022 / 0.007 |
   | h = 2 | permanent | run-up | 0 | 0 | 0.014 / 0.014 |
   | h = 1 (secondary) | temporary | CNY month | −0.6 | −0.32 (against H3) | 0.000 / 0.052 |
   | h = 1 | permanent | CNY month | −0.6 | −0.32 | 0.000 / 0.134 |

   (No-bump size: 0.0136 at h = 2, 0.0105 at h = 1.) **Consequence, stated now:** the h = 2 demeaning removes a CNY **step** exactly, but **not a temporary CNY bump**. A hawker bump that reverts after one month biases the h = 2 contrast **towards H3**, because in Jan-CNY years (2023) the bump has reverted by the February endpoint while in Feb-CNY neighbour years it is still in the endpoint. The §10 sentence "the demeaning removes the CNY effect by construction" holds only for permanent CNY steps. This is a stated limitation of H3. **Handling (revision 3):** no adjustment is added (R3 remains not estimable for the hawker class); instead H3 is decided by an intersection-union test of h = 2 and h = 1 (§5.4), because a temporary bump biases the two horizons in opposite directions. Under that rule a positive temporary hawker bump no longer inflates size (0.117 → 0.0001 at +0.5 pts), at the cost of power when the bump is large (0.778 at +0.5 pts, 0.178 at +1.0 pts; §5.4 table).
5. H4: verify the NEA frame, then draw the sample with the §6 rule and commit the draw before fieldwork.

## 10. Registration and pre-merge checklist

**Registration (freezing).** Once WC approves, the PR is merged and the merge commit is tagged **`prereg-v2`**. **WC** then deposits `docs/preregistration_v2.md` (and `diagnostics/tax_feasibility/p0_eligibility_counts*`) on OSF as a time-stamped registration, with the tag, the merge SHA and the file hash recorded in the OSF entry. **That deposit must precede the first read of any outcome value** (the UK PRICE column, the SG index or dish values), and the P0 output is committed after it. Any change after registration is a deviation (§8), listed in the results file.

**Singapore horizon rule (single rule, WC, 2026-10-10): Singapore events with a January anchor window (SG-E1, SG-E2) use h = 2 primary and h = 1 secondary; non-January events (SG-E0) use h = 1 primary and h = 2 secondary.** The H3-specific reasoning follows.

**H3 horizon decision (WC, 2026-10-10, on revision 3): h = 2 is primary for H3 (both arms), h = 1 is a pre-registered secondary.** Reasoning, recorded as given: at h = 2 every December same-month neighbour window contains CNY (CNY always falls 22 Jan to 19 Feb), so the demeaning removes the CNY effect by construction; at h = 1 the 2023 window contains CNY but most neighbours' windows do not, and the CNY adjustment R3 cannot be estimated for the hawker class. The H3 gate, thresholds and anchor counts are at h = 2 (Hawker Centres class N = 74, 10-dish arm N = 126; MDE threshold q₉₅ − q₂₀ ≤ 0.0093). Residual CNY run-up timing in late-February CNY years is a stated limitation (§5.1). The same rule applies to SG-E2; SG-E0 (July) keeps h = 1 primary.

**Decisions recorded (WC, 2026-10-24, on revision 4).**
1. **Gaps.** The conformal test compresses gaps, as simulated. An event is not testable if a gap falls within ±2 months of its event month (§4).
2. **H1 estimate and CI.** The T*-based ρ̂ and CI are kept and labelled descriptive. The confirmatory decision is the conformal test, and the two are stated to be different objects (§5.2).
3. **H3-dish** is decided by the two-horizon rule (§5.2).
4. **Power gate** at q₀₅. The 80% claim is updated, with the φ = −0.5 exception stated (§5.2, §5.3).
5. **Blinding.** The output-invariance check is accepted. The P0 script and test are written, run on synthetic data, committed, and hashed (§8).
6. **H2** is demoted to secondary and descriptive: the rises-minus-cut difference in ρ̂ with a CI, no test. The confirmatory family is H1 and H3 (§1, §5.4, §7).
7. **α** stays at 0.0167 per confirmatory hypothesis, with no reallocation (§5.4).

**Decisions recorded (WC, 2026-10-10, on revision 2).** 500 matched relatives; MDE_ρ ≤ 1.0; α = 0.0167 per hypothesis; UK primary h = 2; SG primary h = 1 with h = 2 as a pre-registered secondary for every SG event (**amended in revision 4 by the Singapore horizon rule, below**); neighbour rule of at least 3 within ±36 months; the Hawker Centres class as H3's primary control with the 10-dish arm secondary (justifications kept in §3.2, §4 and §5); the H4 frame (NEA list with ACRA UEN matching) and 120 stalls (10 × 12 centres) with the §6 selection rule and seed 20261010.

- [ ] Open VERIFY items in §9.3 carried or resolved as stated (§11).
- [ ] Merge, tag `prereg-v2`, WC deposits on OSF, record the SHA.
- [x] **Revision 4:** WC decisions applied (above); P0 script and invariance test committed and hashed (§8).
- [ ] **Revision 4:** merge, tag `prereg-v4`, record the SHA-256 of this file. WC deposits on OSF before any outcome value is read: `prereg-v4` alone if `prereg-v3` was never deposited, otherwise as an amendment that names `prereg-v3`. Target: registered by 2026-11-07.

## 11. Verification log and revision history

| Item | Result | Evidence |
|---|---|---|
| UK 4 Jan 2011 VAT rise | "The standard rate of VAT increased to 20% on 4 January 2011 (from 17.5%)." | page read, gov.uk/vat-rates |
| UK 2020-22 rates and dates | 5% from 15 Jul 2020 to 30 Sep 2021; 12.5% from 1 Oct 2021 to 31 Mar 2022; normal rules from 1 Apr 2022; eat-in, hot takeaway and hot takeaway non-alcoholic drinks covered | page read, GOV.UK guidance |
| ONS index days for E1 to E4 | 14 Dec 2010, 11 Jan 2011; 14 Jul, 11 Aug 2020; 14 Sep, 12 Oct 2021; 15 Mar, 12 Apr 2022 (all Tuesdays) | file read (ONS ad hoc 3190 xlsx); bulletins for Jul 2020, Sep 2021, Oct 2021, Mar 2022, Apr 2022 page read |
| ONS imputation in 2020 | From April 2020 prices collected centrally; imputation of index movements for unavailable items; carried-forward not mentioned | page read, same bulletin |
| ONS quote-file flags | VALIDITY TRUE/FALSE; INDICATOR_BOX codes (§3.1); no imputed/carried-forward flag; base prices may be "observed or imputed" | page read (glossary, Feb 2025 onwards xlsx) |
| SG CPI prices tax-inclusive | "inclusive of taxes levied and net of subsidies/ rebates" (¶15) | page read, SingStat rebasing paper ip-e61 |
| SG CPI includes service charge | Not stated in the CPI paper; **IRAS: GST applies to price plus service charge**, so the mechanical log change is ln(1.08/1.07) either way. Limitation only if service-charge rates changed at the GST date | page read (IRAS "Hotel and Food & Beverage") |
| GST-exclusive display ("++") | Permitted for establishments that impose a service charge, with a prominent statement | page read (IRAS, same page) |
| SG class weights | Fixed-basket Laspeyres-type (¶38); 2019-based 537 / 86 apply through Dec 2023, 2024-based 585 / 85 from Jan 2024; earlier vintages' weights not found, so 537 : 86 is used throughout | page read (ip-e61) |
| UK VAT status of the 44 catering IDs | Committed CSV: 23 treated, 6 staff (E1 only), 2 zero-rated, 2 standard-out-of-scope, 11 ambiguous | page read (GOV.UK, Notice 709/1, Notice 701/14); school meals search extract |
| CNY dates 2005-2026 | Jan-CNY: 2006, 2009, 2012, 2014, 2017, 2020, 2023, 2025 | computed (lunardate) |
| 2024-base splice | Constant link factor (annual 2024 ratio) applied to the 2019-based series; overlap year 2024; boundary at 2023-12 | page read, ip-e61 ¶42-43 |
| Whether published table switches to 2024-based values at 2024-01 | Inferred from ¶42-43 and the M213761 footnote; M213751's own footnote describes only the weighting pattern. Carried as a flagged limitation (demoted SG-E2 only) | inference |
| IRAS 9% from 2024-01-01; 8% from 2023-01-01 | "7% to 8% with effect from 1 Jan 2023 (first rate change)"; "8% to 9% with effect from 1 Jan 2024 (second rate change)" | page read, IRAS "GST Rate Change for Consumers" |
| SG 2006-2008 cooked-food class series | 36 of 36 non-empty months for 1.11.1, 1.11.2, 1.11.3 | API read (labels and period keys only) |
| SG 2004-based class definitions | Not found; older info papers returned 404; Sep 2008 release (2004 = 100) names only "Food" | not found |
| IRAS threshold history | Not found | not found |
| NEA hawker centre list | 2016 centre list (107 rows) and a newer NEA dataset with cooked-food stall counts | search extract |
| ACRA entity datasets | Three datasets on data.gov.sg, updated 2026-09-16 | metadata read (dataset listing) |

**Revision 2 (2026-10-10) changes**, by item of WC's review: (1) SG 2007: source found, kept secondary with a conditional class-definition check, "Dropped events" section added; (2) SG 2024 demoted, SG 2023 sole confirmatory H3 event, P0 design with N and the plausibility statement, "not testable" rule; (3) UK imputation-flag check and limitation; placebo pool primary plus R1 and R2; (4) point estimates and 95% CIs for every event, and the limits of the MDE gate; (5) H4 lower-bound framing, frame and sample size; (6) VERIFY items resolved and logged; (7) Registration section. **Unrequested design changes made while doing this**, for WC to accept or revert: neighbour rule changed from at least 4 to at least 3 (the 7.7-year hawker series left only 57 anchors under the old rule, below the resolution limit for α = 0.0167); Holm replaced by fixed-sequence testing in H1 (Holm's first-step threshold is below the placebo resolution); SG primary horizon changed from h = 2 to **h = 1**; H3's "pooled 2023+2024" removed (item 2).

**Revision 3 (2026-10-10) changes**, by item of WC's review: decisions recorded and DECISION tags removed (§10), centre stratification and seed 20261010 fixed (§6), SG h = 2 secondary for every SG event (§4); (1) H1 order is E3 → E4 → E1, E2 moved to H2 and a secondary ρ̂ with CI (§1, §5.2, §5.4); (2) Chinese New Year: classes, anchor counts for the Jan-CNY restriction, R3 adjustment and R4 pool defined, SG-E0 checked (§5.1); (3) service charge downgraded to a limitation (§3.2); VERIFY items: VAT classification committed, ONS index days resolved, SG class weights resolved, SG-E0 class check and 2024-01 vintage switch left open and flagged (§9, §11). **Finding that was not asked for:** the Hawker Centres class has only 5 to 6 anchors that can identify a CNY effect, so the CNY adjustment is not estimable for H3's primary control (§5.1).

**Revision 4 (2026-10-10)**, WC decision on H3: primary horizon h = 2 for H3, h = 1 secondary (§1, §4, §5.1, §5.3, §10); residual late-February CNY run-up timing added as a limitation (§5.1); H3 gate N = 74 (Hawker Centres) and 126 (10 dishes), MDE threshold unchanged at 0.0093.

**Revision 5 (2026-10-10), WC decision:** the Singapore horizon rule (January-anchor events SG-E1 and SG-E2: h = 2 primary, h = 1 secondary; non-January SG-E0: h = 1 primary, h = 2 secondary) is recorded in §10; SG-E2's anchor counts and gate are at h = 2 (§5.3).

**Revision 3 of the registered document (tag `prereg-v3`, 2026-10-16)** (not to be confused with draft revision 3 of 2026-10-10 above). **No outcome value had been read** (no ONS PRICE, SingStat index or dish value); every number below is from synthetic data. **Motivation:** the exploratory Monte Carlo study in PR #55 (`analysis/simulation/SUMMARY.md`), merged into this revision so the evidence is part of the registered version, showed (i) that the `prereg-v2` gate did not deliver its stated 80% power and (ii) over-rejection with persistent changes or few event neighbours. Changes:
1. **Gate (§5.2, §5.3, §5.4 H2), WC decision D1-b:** MDE_ρ = (c − q₁₀)/|Δ| with c the test's own (calibrated) critical value. Evidence (`output/prereg_v3/a1_gate_summary.csv`, variant "REGISTERED D1-b+D2-b"): min P(reject at ρ = 1 | gate passes) 0.821 to 0.908 in every registered setting, against 0.44 to 0.63 for the `prereg-v2` gate; q₂₀ (0.746) and q₁₅ (0.786, checked with the D2-a rule) were checked and miss 0.80 for H3. §5.2 now states the verified claim.
2. **Size control (§5.5, new), WC decision D2-b:** every event is tested with a simulation-calibrated critical value at the Kendall bias-corrected φ̂; statistic, null model, grid (75 points), runs per grid point (20,000), seeds and interpolation fixed in §5.5. Evidence (`a2_size_before_after.csv`, `calibration_tables.csv`): size 0.0155 to 0.0188 in every cell, against up to 0.0267 for the rank test; the trigger rule (D2-a) was considered and not adopted (it left 0.0211 and 0.0208).
3. **CNY: simulation run (§9 item 4) and H3 decided by an intersection-union test of h = 2 and h = 1 (§5.4, §1, §7), WC decision:** temporary CNY bumps bias h = 2 towards H3 (k = +0.6) and h = 1 against it (k = −0.6) (`a3_cny_bump.csv`). With the IUT (`iut_power_no_bump.csv`, `iut_cny_scenarios.csv`): power at ρ = 1 without a bump 0.877 (min given the h = 2 gate passes 0.865 to 0.892), above WC's 0.6 threshold for keeping H3 confirmatory; size 0.0048 to 0.0133; a +0.5-point temporary hawker bump no longer inflates size (h = 2 only 0.117, IUT 0.0001) but cuts power to 0.778 (0.178 at +1.0 point). The §5.1 and §9 item 4 limitation text is updated to match.
4. Not changed: hypotheses' content and direction, events, outcomes, windows, the horizons computed, thresholds (1.0, 500 relatives, ≥ 3 neighbours, ±36 months), α and the H1 fixed sequence. WC's recorded decisions in §10 are left as written; where revision 3 supersedes a number in them (the q₉₅ − q₂₀ threshold), §5.3 governs.

**Revision 4 of the registered document (tag `prereg-v4`, 2026-10-24).** **No outcome value had been read** (no ONS PRICE, SingStat index or dish value). Every number below is from synthetic data in `analysis/simulation/` (PR #67). The evidence is summarised in `analysis/simulation/SUMMARY.md` and the mathematical claims in `docs/math_claims.md`.

*Motivation.* The revision-3 procedure's size among datasets that pass its gate was 0.021–0.032 at a 50% pass rate and up to 0.06 at a 10% pass rate (`output/method_fixes/gate_conditional_size.csv`). Under t(3) innovations and seasonal AR its size was also above α (`output/misspec/`). A level-gap conformal test was more powerful for the UK events (`output/benchmark/`).

*Changes.*
1. **H1 test (§1, §4, §5.2, §5.4):** level-gap conformal statistic with cyclic shifts (Chernozhukov, Wüthrich & Zhu 2021), replacing the calibrated T* test. UK-E2 (secondary) uses the same test.
   - Evidence: `output/prereg_v4/size.csv`, `power.csv`. Size 0.004–0.019; among datasets that pass the gate, 0.003–0.019.
   - Power (gate passes and test rejects) at UK-E3, φ = 0, |Δ|/σ = 5.05: 0.90 against 0.28 for revision 3.
2. **H3 components (§5.2, §5.4):** uncalibrated placebo rank tests on the unchanged demeaned statistic; H3 still decided by the IUT.
   - Evidence: IUT size 0.000–0.016; among datasets that pass the gate, 0.000–0.018 (`size.csv`). CNY scenarios ≤ 0.0155 (`cny.csv`).
   - Power is lower than revision 3's: 0.40 against 0.71 at φ = 0, |Δ|/σ = 6, ρ = 1. Part of revision 3's figure is its conditional over-rejection.
3. **Gate (§5.3):** symmetric gate on the pooled values. c_pool = the (K + 2)-th largest pooled value, q₀₅ in place of q₁₀, and the blinding rule replaced by an output-invariance check.
   - Evidence: `gate_guarantee.csv`. With q₁₀ the 80% check failed (0.61–0.90 for H1, 0.64–0.88 for the H3 IUT). With q₀₅ it holds for φ ≥ 0 (0.819–0.897 H1, 0.815–0.917 H3 IUT, 0.857–0.937 H3-dish IUT).
   - Theory: `docs/math_claims.md` B4 (theorem candidate) and E5.
4. **§5.5 calibration withdrawn.**
   - Considered and rejected: the residual-bootstrap calibration (`docs/math_claims.md` C7; among datasets that pass the gate, 0.028–0.033 at h = 2).
   - Also evaluated and not adopted: indirect-inference φ̂ and a smoothed dense calibration table (`output/method_fixes/`). They changed size by at most 0.0005 and about 0.001.
5. **Secondary events follow their family** (§5.2, §7): UK-E2 uses H1's test (and is not testable under the gap rule); H3-dish uses H3's IUT; SG-E2 and SG-E0 use the rank test per horizon.
6. **H2 demoted (§1, §5.4, §7):** H2 is secondary and descriptive: the rises-minus-cut difference in ρ̂ with a placebo-inversion CI, and no test. The confirmatory family is H1 and H3. α stays at 0.0167 each and is not reallocated.
7. **Gap rule (§4):** for the conformal test, an event is not testable if a month within ±2 of its event month is missing from the retained sequence.
8. **H1 decision versus estimate (§5.2):** the conformal test decides; the T*-based ρ̂ and CI are descriptive and are a different object.
9. **P0 script and invariance test (§5.3, §8):** committed with their SHA-256 hashes; PASS on synthetic data.
10. **Editorial:** removed a duplicated sentence in §5.3.
11. **Not changed:**
   - the hypotheses' content and direction, events, outcomes, windows, horizons, T* and ρ̂;
   - the thresholds (MDE_ρ ≤ 1.0, 500 relatives, ≥ 3 neighbours, ±36 months);
   - α per confirmatory hypothesis, the H1 fixed sequence, the H3 IUT, the CI method, and R1–R4.

*Decisions:* WC, 2026-10-24, recorded in §10.

*Simulation scope and limits:*
- Gaussian AR(1) for φ ∈ [−0.5, 0.97], AR(2), seasonal AR(12), t(3) innovations, a drift break and a level step. A variance spike at the event month is a stated failure for every method.
- **Not simulated:** conformal CI coverage (no conformal CI is reported); SG-E2/SG-E0 as an IUT; gaps from the 500-relative rule beyond the calendar gaps of the real layouts; and the real UK series' exact retained-month set after the 500-relative rule.


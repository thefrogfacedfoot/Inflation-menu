# Addendum: read-only checks, 2026-10-10 (afternoon)

Follows `tax_pass_through_feasibility.md`. No outcome data were analysed. The only data touched: (a) the **keys** (period labels) of non-empty cells in SingStat M213761, to get start dates and month counts, with no value printed or stored; (b) page text of public documentation. Nothing was plotted or computed around any tax-change date.

Labels: **[P]** page opened and read this session; **[S]** search-result extract only (page not opened by me); **[X]** not found.

## a. ONS price quotes before 2010

| Question | Finding | Label |
|---|---|---|
| 1996-2009 monthly quote files on ons.gov.uk | None found. The open monthly quote files I enumerated start 2010-01 (191 of 200 months to 2026-08, see main report) | [X] |
| Older open quotes | Ad hoc 007392 "Consumer price inflation price quotes (1988 to 1996)", released 2017-08-25: zip files labelled "Research quotes", by year and quarter (e.g. 1988 all quarters 67.7 MB; 1994 153.2 MB). The page does not describe the file schema, item IDs or whether catering items are present. No link to a 1996-2009 set | [P] |
| Item indices 1996-2019 | Ad hoc 10673: "Item level indices and weights data for the period January 1996 to August 2019", one .xlsx (about 11.3 MB), released 2019-10-10. Indices and weights, **not quotes** | [P] |
| Secure access | ONS Prices Survey Microdata 1996-2024 is listed as secure-access for accredited researchers (UK Data Service / ADR UK listing). Not opened | [S] |
| "Davies cleaned set" | R. Davies, "Prices and inflation in the UK: a new dataset", CEP Occasional Paper CEPOP55, 5 Feb 2021: 41 million CPI price quotes, 1988-01 to 2020-12. The abstract page does not say whether the data are public or how to get them | [P] abstract only; access [X] |
| Catering item-ID consistency across years | **Within 2010-2026:** 44 distinct IDs, 17 of them present from 2010-01 through 2026-08; several are replaced mid-series (e.g. 220118 restaurant main course 1 to 2016-01, then 220128 from 2016-02; 220205 staff-restaurant main course to 2014-01, then 220214 from 2014-02). See `ons_catering_item_summary.csv`. **Across 1988-96 / 1996-2009 / 2010+:** not checked, because those files were not downloaded and the page gives no schema | counts only |

## b. How ONS treated Eat Out to Help Out (EOHO) in the price quotes

Source: ONS, *Prices Economic Analysis Quarterly: October 2020*, section 6 "Data sources and quality" [P]
(https://www.ons.gov.uk/economy/inflationandpriceindices/articles/priceseconomicanalysisquarterly/october2020).

- Collectors recorded whether a restaurant was in EOHO and whether it passed on the VAT saving; prices fell into four categories, VAT1 to VAT4 ("50% eat out scheme in place").
- "For the EOHO scheme it was assumed that menus were not adjusted to reflect the discount where it was available." Prices were then adjusted to the average across the whole week, weighted by day using Revolut transaction data for the first two weeks of August.
- VAT1: recorded prices reflected the discounted price. VAT2: prices reduced by 12.5% (VAT 20% to 5%). Unclear cases were adjusted manually, which the article says is "likely to be an element of measurement error".
- To isolate effects the ONS team reversed its EOHO adjustments (keeping VAT) and vice versa.
- **Not checked:** whether the published PRICE field in the August 2020 quote file is the raw menu price, the discount-adjusted price, or the weekly-average price. The price column has not been read.
- Consequence used in the pre-registration: August 2020 is excluded as an endpoint of any statistic unless a documented flag identifies and removes EOHO-affected quotes.

## c. IRAS primary sources

| Item | Finding | Label |
|---|---|---|
| GST 9% from 2024-01-01 | IRAS pages "Overview of GST rate change" (business) and "GST rate change for consumers" and TaxBytes "What consumers need to know with the new GST rate from 1 Jan 2024" were returned by search with the text "from 7% to 8% with effect from 1 January 2023 and from 8% to 9% with effect from 1 January 2024"; payments received in 2023 stay at 8% even if delivery falls in 2024; displayed prices must include GST at 9% from 2024-01-01. **I did not open these pages** (two URLs I guessed returned 404) | [S] extract of IRAS pages |
| Registration threshold | IRAS "Do I need to register for GST" [P]: register if taxable turnover is "under the retrospective view, more than $1 million at the end of the calendar year" or "under the prospective view, expected to be more than $1 million in the next 12 months". Announced 2025-02-28: for prospective liability from 2025-07-01, registration takes effect 2 months from the forecast date (previously the 31st day) | [P] |
| **Threshold history** | **Not found.** The IRAS page gives no history of the S$1 million level; no source located for earlier thresholds or when S$1 million was set | [X] |
| Hawkers | The same IRAS page lists "hawker" among persons whose business income counts toward taxable turnover. It says nothing on typical registration status. Exemption from registration is described only for businesses whose turnover is wholly or mainly zero-rated | [P] |

## d. IRAS GST-registered business search

Page: https://mytax.iras.gov.sg/ESVWeb/default.aspx?target=GSTListingSearch [P]. **Not queried.**

- Public, no myTax login. One input field "Business Name or Tax Ref No. (UEN / GST Reg No. / NRIC)".
- Modes: **one business name** (minimum the first five characters) **or up to four tax reference numbers** (UEN, GST Reg No., NRIC) per search. IRAS recommends UEN or GST number for best results.
- **A CAPTCHA is required on each search.** Result fields are not described on the form; search-result summaries say status, registration number and dates, but I could not confirm that.
- Implication: the search is a manual, per-query, human-in-the-loop lookup. It is not a bulk interface and must not be automated or CAPTCHA-circumvented. It matches **registered business names or UENs, not stall trading names**; a stall signboard name often will not match. NRIC lookup of sole proprietors should not be used (privacy). A stall with no findable registered name must be recorded as "unmatchable", which is **not** the same as "not GST-registered".

## e. SingStat Table Builder retry (it is back up)

Table Builder returned HTTP 200 today. M213761 [P] (API metadata and data endpoints).

| Item | Finding |
|---|---|
| Table | M213761 "Average Retail Prices Of Selected Consumer Items, Monthly", 85 series, 2015-01 to 2026-08, 9,632 data points, data last updated 2026-09-23, non-seasonally adjusted |
| Footnote | "Prices of items starting from January 2024 are based on the 2024-based CPI basket. While they are indicative of the average transaction price levels in the same base period, they are not a measure of pure price movements across CPI baskets due to changes in the sample of brands/varieties and outlets priced." |
| Cooked food and drink, 20 series, **full 140 months (2015-01 to 2026-08)** | Coffee/Tea Without Milk (per cup); Coffee/Tea With Condensed Milk (per cup); Fishball Noodles (bowl); Mee Rebus (bowl); Chicken Rice (plate); Chicken Nasi Briyani (plate); Economical Rice 1 meat & 2 veg (plate); Roti Prata plain (piece); Fried Carrot Cake (plate); Ice Kachang (bowl) |
| Cooked food and drink, **from 2024-01 only (32 months)** | Milo With Condensed Milk (cup); Canned Drink With Ice (can); Mee Siam (bowl); Char Kway Teow (plate); Sliced Fish Bee Hoon (bowl); Wanton Noodles (plate); Char Siew Rice (plate); Duck Rice (plate); Saba Fish With Rice (plate); Chicken Chop (plate) |
| What it does not say | Establishment type (hawker centre vs food court vs coffee shop) is not a dimension of this table; the 2019-base hawker-by-establishment-type publication ("Hawker food price trends across cooked food establishment types, 2019 as base year") was found by search but not opened |
| Older base-year CPI tables | Table Builder's `resourceid` search for "consumer price index" returns 27 tables, **all 2024 base**. Keyword searches for "2019 / 2014 / 2009 / 2004 As Base Year" return nothing. Older vintages are not listed in Table Builder; where they are archived is **not established** |
| M213751 | Unchanged from the main report (2024 base, 1961-01 to 2026-08, food-service classes from 2005-01; hawker-centre-only series from 2019-01; "Restaurants and Cafes" separate series from 2024-01) |

## Open items these checks leave unresolved

1. IRAS threshold history (earlier S$ levels, date S$1 million was set).
2. Whether SingStat records restaurant / hawker prices **including GST and service charge** (matters for how a GST change enters the index mechanically). Not stated in anything opened.
3. How the 2024-base series was spliced to earlier vintages at the 2024 boundary (information paper "Rebasing of the CPI (2024 as Base Year)" not opened).
4. Whether the ONS August 2020 PRICE field is raw or EOHO-adjusted.
5. ONS index day for July 2020 (ONS says the index day is the second or third Tuesday and publishes the exact date in each bulletin's background notes; the July 2020 date was not retrieved).

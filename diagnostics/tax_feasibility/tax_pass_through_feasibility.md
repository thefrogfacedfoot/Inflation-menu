# Tax pass-through feasibility scan (2026-10-10)

Feasibility only. No series were plotted and nothing was computed around tax-change dates. The only numbers computed are
**row counts** (ONS quotes, Malaysian observations) and series **coverage** (first/last period with a value). No price column
was read in the ONS or PriceCatcher counts.

Evidence labels: **[P]** primary source opened and read this session; **[M]** official mirror of a primary table; **[S]** secondary
source only (news, blog, search-result summary), not verified; **[X]** not found / could not open.

## 1. SingStat CPI and hawker prices

SingStat Table Builder (`tablebuilder.singstat.gov.sg`, web and API) returned HTTP 502 "undergoing maintenance" on three attempts
on 2026-10-10. Table IDs other than M213751 could therefore not be opened.

| Item | Finding | Label |
|---|---|---|
| 2024=100 CPI table | Table **M213751** (SingStat), mirrored on data.gov.sg as `d_bdaff844e3ef89d39fceb962ff8f0791`, monthly, 207 series, 788 periods, 1961-01 to 2026-08 | [M] |
| Food-service series in that table, first period with a value | Food & Beverage Serving Services 1990-01; Restaurants, Cafes & Pubs 2005-01; Fast Food Restaurants 2005-01; Hawker Centres, And Food Courts, Coffee Shops & Kiosks 2005-01; Other Catering Services (incl. vending machines) 2005-01 | [M] |
| Sub-classes | Hawker Centres and Food Courts, Coffee Shops & Kiosks (separate series): 2019-01 onward (92 months). Restaurants and Cafes (separate series): 2024-01 onward (32 months), so the restaurant/cafe split starts with the 2024 base | [M] |
| How the 2024 rebase renamed classes | 2019-base series were labelled "Hawker Food (Incl. Food Courts)" and "Hawker Centres" (CEIC titles). 2024-base labels are "Hawker Centres, And Food Courts, Coffee Shops & Kiosks" and "Restaurants / Cafes". The information paper "Rebasing of the CPI (2024 as Base Year)" was not opened, so the official mapping is unconfirmed | [S] |
| Base-year schedule | 2019 to 2024 rebase took effect with the January 2025 release; rebasing is every five years | [S] (SingStat press release excerpt) |
| 2019, 2014, 2009 and older base-year table IDs and start dates | Not retrieved (Table Builder down). data.gov.sg carries only the 2024-base table and a small annual "Consumer Price Indices (CPI)" table (general and healthcare, 2008-2024) | [X] |
| **M213761** (hawker dish average prices) | Not opened. Press reports of a SingStat study (May 2024): 16 commonly sold hawker foods and drinks, based on 100+ hawker items at about 1,700 stalls, with 2019 and 2023 averages quoted for chicken rice, fishball noodles, mee rebus, sliced fish bee hoon, mee siam. Which dishes the table holds and how far back it runs: unknown | [S] / [X] |

## 2. IRAS (GST)

| Item | Finding | Label |
|---|---|---|
| Rate history | IRAS table: 3% from 1 Apr 1994; 4% from 1 Jan 2003; 5% from 1 Jan 2004; 7% from 1 Jul 2007; 8% for 1 Jan to 31 Dec 2023. IRAS states the current rate is 9% (page table stops at 2023). The 9% start of 1 Jan 2024 is from Wikipedia and the 2022 announcement | [P] for 1994-2023; [S] for the 9% date |
| Registration threshold now | S$1 million taxable turnover, tested retrospectively (calendar year) or prospectively (next 12 months); voluntary registration below that (reported two-year commitment). Taken from advisory sites quoting IRAS; the IRAS page itself was not read | [S] |
| Threshold history | No source found for earlier thresholds or the date the S$1 million level was set | [X] |
| Are hawker stalls and food-court operators GST-registered? | No source found. Whether a typical stall clears S$1 million turnover is **not established**. This matters for who faces the rate change directly, so it needs the IRAS GST guide or a stall-turnover source before any design is built on it | [X] |

## 3. ONS price quotes (UK)

Source: ONS dataset "Consumer price inflation item indices and price quotes" (now "price quotes and consumption segment indices"). Region is
broadly NUTS1. From March 2026 ONS removes individual quotes for COICOP divisions 1 and 2 (food and non-alcoholic drinks, alcohol). Catering items (IDs 22xxxx) are
still present in the 2026 files through 2026-08. [P]

| Item | Finding |
|---|---|
| Files | Annual 2010-2014; quarterly 2015-2016; monthly from 2017-03. **Not published on the dataset page:** 2017-01, 2017-02, 2019-01 to 2019-07. 191 of the 200 months 2010-01 to 2026-08 are present |
| Fields | QUOTE_DATE, ITEM_ID (renamed CS_ID from the 2025/26 files; both appear in 2025-04), ITEM_DESC, VALIDITY, SHOP_CODE, PRICE, INDICATOR_BOX, REGION, SHOP_TYPE (1-4), SHOP_WEIGHT, STRATUM_* and base-price fields. 2010-2014 files have no ITEM_DESC |
| Catering IDs | **44 distinct IDs** in 2010-2026, all `220xxx` to `2203xx`. Pub hot meal, restaurant main course, restaurant coffee and sweet course, staff and school canteen items, fish & chips, Indian, Chinese, pizza, kebab and chicken takeaway, burger in a bun, sandwich, hot and cold drinks. Full list with first/last month in `ons_catering_item_summary.csv` |
| Items per month | 34 (2010) falling to 25 (2025-26); 9 in 2020-04 and 14 in 2021-02 to 2021-03 (lockdown) |
| Quotes per month (catering rows) | About 10,200 (2010), 8,400 (2014-15), 7,300 (2017-18), 6,600 (2022-24), 6,150-6,650 (2025-26). Lowest: 1,536 (2020-04), 1,769 (2021-02), 1,887 (2021-03), 2,187 (2021-04) |
| Region and shop fields | 12 region codes (2-13) present in every month; SHOP_CODE is an anonymised shop id; mapping of region codes is in the ONS glossary, not read |
| Counts | `ons_catering_monthly_counts.csv` (all 191 months), `ons_catering_counts_by_file.csv` (month by item by region) |
| Caveat | Quote counts include the same outlet quoted for several items. Chain vs independent cannot be read off these fields (SHOP_TYPE is a four-level code, definitions not read) |

## 4. Korea and Japan

| | Korea 참가격 (price.go.kr) | Japan Retail Price Survey (e-Stat) |
|---|---|---|
| Operator | Korea Consumer Agency portal; the dining-out page says the figures are supplied by the Ministry of the Interior and Safety and sourced to the national statistics body | Statistics Bureau of Japan, MIC |
| Dining-out content [P] | 8 items: 냉면, 비빔밥, 김치찌개백반, 삼겹살 (before and after 200 g conversion), 자장면, 삼계탕, 칼국수, 김밥. One portion each; 김밥 changed from one serving to one roll in 2017-01 | 2022 item list has about 23 eating-out items plus 2 school-meal items: udon, ramen (中華そば), soba, spaghetti, sushi (2), tempura bowl, curry rice, gyoza, hamburger (ハンバーガー), gyudon, hamburg steak set, pork cutlet set, pizza (delivery), yakiniku, rice-and-soup set, sandwich, coffee (2), doughnut, fried chicken, beer, yakitori |
| Geography | Province-level (about 17 provinces and "all") | 167 surveyed municipalities nationally; e-Stat city tables for prefectural capitals and cities of 150,000+ (reported monthly from 2000-01) |
| Frequency and start | Monthly. The year selector runs 2009 to 2026; first month with data not tested | Monthly, reference day in the week containing the 12th. Survey since 1950-06. Item list is revised at each CPI rebase, about every five years |
| Download | "Excel save" button on the query page (one query at a time); no bulk file or data.go.kr dataset found for 참가격 | e-Stat web download (CSV/Excel) from the item-by-city and annual-report tables; the e-Stat API needs an application ID |
| Cautions | Values flagged provisional; surveyed shops that close are replaced, so price changes include substitution; cross-province and cross-period quality not constant (page says so) | Brand and specification fixed per item in `hinmoku` lists; take-away excluded for most eating-out items |
| Label | [P] for page content; start dates [X] | [P] for item list and survey design; city-table range [S] |

## 5. Malaysia PriceCatcher

Files: `storage.data.gov.my/pricecatcher/pricecatcher_YYYY-MM.parquet` plus `lookup_item.parquet` and `lookup_premise.parquet`. [P]

| Item | Finding |
|---|---|
| Date range | **2022-01 to 2026-08**, all 56 monthly files present; 2019-2021 files return 404 |
| Item lookup | 797 items. Group `MAKANAN SIAP MASAK` (ready-cooked food) has 191 items and `MINUMAN` 50. The lookup **includes** nasi lemak (wrapped, 1159; plate, 1160), nasi goreng variants, roti canai (1783), teh tarik panas (1789), teh/kopi hot and iced |
| Observations of cooked dishes | Present in **four months only: 2022-01, 02, 03 and 05** (about 46,900 to 54,500 served-unit rows and 168 items per month; nasi lemak about 400-500 rows, teh tarik about 630-720 rows per month). Zero in 2022-04 and in every month from 2022-06 to 2026-08 |
| What the later months contain | 44 items in 2022-06 to 2023, falling to 40 (2025-01) and 31 (2025-07 on). All are packaged retail drinks and mixes (Milo, Nescafe, Coca-Cola, UHT milk, tea bags), not served food or drinks |
| Premise types | Restoran Melayu 297, Restoran India Muslim 223, Restoran Cina 196, Medan Selera 126, Foodcourt 94, plus grocery formats. |
| Counts | `pricecatcher_cooked_counts.csv`, one row per month |

This contradicts the working note in memory that the 191 cooked items give usable coverage and that "39 to 27 items" is the cooked-food series. That series is packaged drinks. **PriceCatcher has no cooked-food prices after 2022-05.**

## 6. Literature scan (abstract level only; papers not read)

| Study | Setting | Reported result | Label |
|---|---|---|---|
| Onnis, Piga, Conti, Bottasso, "VAT Cuts as Emergency Policy Intervention: Evidence from the UK Case", Cardiff Economics WP E2025/4, SSRN 4259245 (ideas.repec.org/p/cdf/wpaper/2025-4.html) | UK 2020 hospitality VAT cut from 20% to 5%, **hotel room prices** (not restaurants) | Pass-through about 20-50%, peak in the second week, discounts negligible for rooms sold two months later | abstract via search result |
| Firgo, "Price effects and pass-through of a VAT increase on restaurants in Germany", arXiv:2409.01180 | Germany, restaurant VAT 7% to 19% on 2024-01-01, synthetic control | 31% passed through in January, about 58% after six months | abstract |
| Irish Fiscal Advisory Council (2025), "VAT rate changes and pass-through: Evidence from the Irish hospitality and ..." (fiscalcouncil.ie PDF returned 403) | Ireland hospitality VAT changes 2011-2026, event study, UK used as a comparison | Increases passed on more than cuts; cuts 0-50% and not statistically distinguishable from zero for takeaway | search-result summary |
| ONS analysis said to find a restaurant price effect of about 0.1 pp in Aug 2020 | UK | Not located | [S] blog only |
| Singapore GST | No peer-reviewed pass-through study found. Policy and commentary only: MTI parliamentary reply on inflation, Nov 2007 (limited effect on basic food, supermarkets absorbed); MAS Macroeconomic Review Oct 2023 (GST step lifted core inflation in 2023); Committee Against Profiteering case studies; a personal GitHub analysis (jacobbuildmodel/gst-passthrough, not peer reviewed) | | [S] |
| UK 2020-22 hospitality VAT (12.5% step, then back to 20%) pass-through | No UK restaurant-menu study found in this scan | | [X] |

## Bottom line for design (counts and coverage only)

- **UK:** ONS catering quotes exist for 191 months with about 6,000-10,000 quotes per month and 25-34 catering items across 12 regions. This is the only source here that spans the 2020-22 VAT episode with outlet-level quotes.
- **Singapore:** the 2024-base CPI table has food-service classes back to 2005 (restaurants, fast food, hawker/food courts) and a hawker vs food-court split from 2019. The hawker dish price table (M213761) is unverified, the older-base tables were unreachable, and no source says whether hawker stalls are GST-registered.
- **Malaysia:** no cooked-food coverage after 2022-05.
- **Korea / Japan:** usable but low-volume (8 items; about 23 items) with substitution and rebase caveats; start dates not tested for Korea.
- **Literature:** nothing on Singapore GST pass-through to food service in the peer-reviewed record found here; UK 2020 evidence is on hotels.

## Files

- `ons_catering_counts.py`, `ons_catering_counts_by_file.csv`, `ons_catering_monthly_counts.csv`, `ons_catering_item_summary.csv`
- `pricecatcher_cooked_counts.py`, `pricecatcher_cooked_counts.csv`

Re-running the ONS script needs the dataset page HTML saved as `page.html` beside it; the script's `done` check uses file names only and skips months already in the output.

UICPI: A Unified Independent-Chain Restaurant Price Index as a Leading Indicator of Consumer Price Inflation

Abstract
[To be written after analysis — must describe: 
what I built, what data I collected, what the 
Granger causality results showed, what the 
pass-through finding showed, and what this means 
for inflation measurement in developing economies. 
Maximum 250 words.]

RESEARCH GAP
The MIT Billion Prices Project demonstrated that online retail prices lead official CPI by several months. However, BPP explicitly excludes services and focuses only on large multichannel retailers. No systematic price index exists for the restaurant and food service sector, and the informal food economy — hawker stalls, street vendors — remains entirely unmeasured in all existing alternative price indices. From The Economist’s Big Mac Index (1986) to MIT’s Billion Prices Project (2016), alternative price measurement has consistently revealed what official statistics miss — yet both remain confined to the formal sector. In economies such as Indonesia, Nigeria, and India, Street food represents 50-65% percent of household expenditure at the national level, according to data from United Nations Development Program — yet remains entirely absent from all existing alternative price indices, including BPP.

RATIONALE
Official consumer price indices rely on infrequent manual data collection that fails to capture rapid price movements in the food service sector. The MIT Billion Prices Project demonstrated that algorithmically-collected online prices lead official CPI by several months, but explicitly excludes services and informal vendors. In developing economies, informal food vendors constitute 40-60% of household food expenditure yet remain entirely absent from all existing alternative price indices. This creates a systematic  measurement gap that leaves developing country central banks without timely inflation signals. This project addresses that gap by constructing the first unified price index covering both formal restaurants and informal vendors across multiple economies.

PRIMARY RESEARCH QUESTION
Does a unified restaurant price index incorporating formal 
and informal sector food vendors serve as a statistically 
significant leading indicator of official CPI food 
components across multiple economies?

SECONDARY HYPOTHESIS
Informal sector vendors exhibit systematically lower cost 
pass-through rates than formal sector vendors, absorbing 
input cost increases rather than transmitting them to 
consumers.

EXPECTED OUTCOMES
1. UIFPI movements precede official CPI changes by a 
   measurable and statistically significant lead time, 
   validated through Granger causality testing across 
   8 countries
2. Informal sector price pass-through rates are 
   systematically lower than formal sector rates
3. A directional forecast model predicting the direction 
   of the next official CPI food release with accuracy 
   exceeding naive baselines


METHODOLOGY
- Archival menu data from TripAdvisor, Zomato, and restaurant PDF menus via Wayback Machine CDX API (historical, 2018-present)
- Live monthly scraping of current menu prices using Foodpanda and Grabfood (forward, commencing June 2026)
- Multimodal NLP pipeline for informal sector price extraction from photographs and social media posts
- Matched model price index construction with hedonic quality adjustment
- Granger causality testing against official CPI food components across 8-country sample
- Benchmarked against BPP methodology and existing leading indicators

Materials

Hardware:
- Personal computer with internet connection

Software:
- Python 3.12 (programming language)
- Playwright (browser automation for data collection)
- BeautifulSoup (HTML parsing)
- pandas, numpy (data processing)
- statsmodels (econometric analysis — Granger causality, VAR)
- SQLite (database storage)

Data Sources:
- Wayback Machine CDX API (archival menu data, free)
- TripAdvisor, Zomato, OpenRice (restaurant menu pages)
- Foodpanda, GrabFood (delivery platform menu pages)
- World Bank Open Data API (official CPI benchmarks, free)
- IMF Data API (supplementary CPI data, free)

No laboratory equipment, chemicals, or biological 
materials required. This is a computational research 
project.

Phase 1 — Data Collection (Months 1-4)
1. Query Wayback Machine CDX API to identify archived 
   restaurant menu pages per country (2018-present)
2. Extract historical price data using Python scrapers 
   with BeautifulSoup for static pages and Playwright 
   for JavaScript-rendered pages
3. Collect live menu prices monthly via automated 
   scraper across 30 Singapore restaurants (15 formal, 
   15 informal), expanding to 7 additional countries
4. Photograph informal sector price boards; extract 
   prices using multimodal vision-language model API
5. Store all data in SQLite database with fields: 
   restaurant name, item name, price, date, country, 
   sector, source

Phase 2 — Index Construction (Months 4-5)
6. Apply matched model methodology — retain only items 
   present in both compared periods
7. Classify items into standardised food categories 
   using LLM-based multilingual classifier
8. Apply hedonic quality adjustment using portion and 
   ingredient quality descriptors
9. Weight formal and informal sector components using 
   World Bank household expenditure survey data
10. Construct monthly UIFPI per country

Phase 3 — Analysis (Months 5-7)
11. Download official CPI food component data via 
    World Bank API for all 8 countries
12. Test stationarity of all price series (ADF test)
13. Run Vector Autoregression and Granger causality 
    tests — does UIFPI lead official CPI?
14. Estimate cost pass-through regression — formal 
    vs informal sector comparison
15. Benchmark against existing leading indicators 
    (PMI, consumer confidence indices)

Phase 4 — Validation and Writeup (Months 7-9)
16. Robustness checks across country subsamples
17. Write research paper and methodology documentation
18. Deploy open-source dashboard showing live UIFPI

RISK AND SAFETY
This project involves no physical, chemical, or 
biological risks.

Data Ethics:
- All data collected from publicly accessible web pages
- No personal data collected at any stage
- Web scraping conducted at low frequency (monthly) 
  to minimise server load on source websites
- Data sources and collection methods documented 
  transparently for reproducibility

Methodological Risks:
- Archival data gaps may reduce historical sample size; 
  mitigated by testing coverage before committing to 
  country sample
- Bot detection by websites may block automated 
  collection; mitigated by running scrapers from 
  residential IP addresses
- Selection bias from informal vendors without digital 
  presence; acknowledged as a limitation in the paper

No IRB approval required as no human subjects, 
animals, or hazardous materials are involved.

CONTRIBUTION
First systematic restaurant price index covering formal and informal sectors simultaneously. Extends BPP to the service sector they explicitly excluded. Open source, publicly accessible — designed for developing country central banks that cannot access commercial alternatives like PriceStats.

1. Stationarity Testing
   Augmented Dickey-Fuller (ADF) test on all price series before any time series modelling

2. Index Construction
   Matched-model Laspeyres price index with quality adjustment, weighted by sector shares from World Bank household surveys

3. Leading Indicator Validation
   Autoregressive Distributed Lag (ADL) specification following Cavallo & Rigobon (2016): ΔIn(CPIt) = α + βΔIn(UIFPIt) + Σαi ΔIn(CPIt-i)+ Σβi ΔIn(UIFPIt-i) Granger causality F-test across 8 countries

4. Cost Pass-Through Analysis
OLS regression of price changes on input cost proxies, estimated separately for formal and  informal sectors; t-test for difference in coefficients

5. Benchmarking
   Directional forecast accuracy compared against PMI and consumer confidence index baselines
   
6. Robustness
   Results replicated across country subsamples and alternative basket specifications

Cavallo, A. & Rigobon, R. (2016). The Billion Prices 
Project: Using Online Prices for Measurement and 
Research. Journal of Economic Perspectives, 30(2), 
151-178.

Bibliography 
The Economist (1986). The Big Mac Index.
[Add 13-18 more as you complete literature review]
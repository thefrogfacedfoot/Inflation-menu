UIFPI: A Unified Informal-Formal Restaurant Price Index as a Leading Indicator of Consumer Price Inflation

RESEARCH GAP
The MIT Billion Prices Project demonstrated that online retail prices lead official CPI by several months. However, BPP explicitly excludes services and focuses only on large multichannel retailers. No systematic price index exists for the restaurant and food service sector, and the informal food economy — hawker stalls, street vendors — remains entirely unmeasured in all existing alternative price indices. From The Economist’s Big Mac Index (1986) to MIT’s Billion Prices Project (2016), alternative price measurement has consistently revealed what official statistics miss — yet both remain confined to the formal sector. In economies such as Indonesia, Nigeria, and India, the informal food sector constitutes 40–60% of household food expenditure — yet remains entirely absent from all existing alternative price indices, including BPP.

PRIMARY RESEARCH QUESTION
Does a unified restaurant price index incorporating both formal and informal sector food vendors serve as a statistically significant leading indicator of official CPI across multiple economies, and if so, by how many months?

SECONDARY HYPOTHESIS
The informal sector exhibits systematically lower cost pass-through rates than the formal sector, meaning informal vendors absorb input cost increases rather than transmitting them to consumers.

METHODOLOGY
- Archival menu data from TripAdvisor, Zomato, and restaurant PDF menus via Wayback Machine CDX API (historical, 2018-present)
- Live monthly scraping of current menu prices using Foodpanda and Grabfood (forward, commencing June 2026)
- Multimodal NLP pipeline for informal sector price extraction from photographs and social media posts
- Matched model price index construction with hedonic quality adjustment
- Granger causality testing against official CPI food components across 8-country sample
- Benchmarked against BPP methodology and existing leading indicators

CONTRIBUTION
First systematic restaurant price index covering formal and informal sectors simultaneously. Extends BPP to the service sector they explicitly excluded. Open source, publicly accessible — designed for developing country central banks that cannot access commercial alternatives like PriceStats.

EXPECTED OUTCOMES
A validated leading indicator with quantified lead time across multiple economies, UIFPI movements precede official CPI changes by an average of N months, validated through Granger causality testing across 8 countries and benchmarked against existing leading indicators (PMI, consumer confidence) 

Evidence that informal sector price pass-through rates are systematically lower than formal sector rates across multiple economies - a finding unavailable in existing literature due to absence of informal sector price data. A directional forecast model predicting whether the next official CPI food release will rise or fall, with accuracy benchmarked against naive forecasting baselines


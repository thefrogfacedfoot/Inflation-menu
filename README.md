# UIFPI — Unified Informal-Formal Price Index

**UIFPI** is the first price index to systematically incorporate both formal
restaurant menus and informal street vendor / hawker stall pricing across
multiple economies. Extending the MIT Billion Prices Project to the food
service sector, UIFPI tests whether algorithmically collected restaurant
prices lead official Consumer Price Index (CPI) readings, and whether
informal-sector vendors exhibit lower cost pass-through than formal ones.
This is an open-source research project submitted for the Singapore Science
and Engineering Fair (SSEF) and targeted at the SSRN economics preprint
series.

---

## Research Questions

1. **Primary:** Does a unified restaurant price index incorporating formal and
   informal sector vendors serve as a statistically significant leading
   indicator of official CPI food components across multiple economies?

2. **Secondary:** Do informal sector vendors exhibit systematically lower cost
   pass-through rates than formal restaurants — absorbing input cost increases
   rather than transmitting them to consumers?

3. **Tertiary:** Does a directional forecast model using UIFPI outperform a
   naive AR(1) baseline in predicting the direction of the next official CPI
   food release?

---

## Methodology

### Data Collection
- **Formal sector:** Restaurant menus scraped from Zomato, GrabFood, GoFood,
  Deliveroo, JustEat, Uber Eats, Yelp, DoorDash, and Menulog.
- **Informal sector:** Hawker centre price data (Singapore), street vendor
  menus, local food courts.
- **Historical backfill:** Wayback Machine archives used to reconstruct price
  histories to 2018.
- **NLP pipeline:** Dish names classified into food categories
  (RICE_DISH, NOODLE_DISH, SOUP_STEW, etc.) using keyword matching and
  language detection.

### Index Construction
Monthly price relatives are computed per food category per country following
the Laspeyres chain-linking method. Formal and informal sub-indices are
combined at configurable weights (default 50/50).

### Statistical Analysis
- **Granger causality** (Cavallo & Rigobon 2016): test whether UIFPI
  Granger-causes CPI after first-differencing; lag order selected by AIC.
- **Pass-through regression:** OLS of ΔUIFPI on ΔCPI by sector.
- **Directional accuracy benchmark:** UIFPI vs AR(1) naive baseline
  on a held-out test set.
- **Robustness checks:** jackknife country subsampling, alternative basket
  specifications, alternative sector weights, formal/informal split.

---

## Country Sample

| Country        | Dev. Status | Sector Coverage    | Archive Coverage |
|----------------|-------------|-------------------|------------------|
| Singapore      | Developed   | Formal + Informal | 2018–present     |
| Malaysia       | Emerging    | Formal + Informal | 2018–present     |
| Indonesia      | Emerging    | Informal          | 2019–present     |
| Thailand       | Emerging    | Formal + Informal | 2018–present     |
| India          | Emerging    | Informal          | 2018–present     |
| United States  | Developed   | Informal          | 2018–present     |
| United Kingdom | Developed   | Formal + Informal | 2019–present     |
| Australia      | Developed   | Formal + Informal | 2018–present     |

---

## How to Run the Full Pipeline

### Prerequisites

```bash
pip install -r requirements.txt
```

Required packages: `pandas`, `numpy`, `scipy`, `statsmodels`, `matplotlib`,
`geopandas`, `anthropic`, `requests`, `beautifulsoup4`.

### Numbered Steps

```bash
# 1. Scrape live restaurant prices
python historical_scraper.py

# 2. Run NLP classification pipeline
python nlp_pipeline.py

# 3. Build UIFPI index from prices database
python index_builder.py

# 4. Fetch official CPI data
python get_monthly_cpi.py

# 5. Run Granger causality and pass-through analysis
python granger_analysis.py

# 6. Run robustness checks
python robustness_checks.py

# 7. Run benchmark comparison against AR(1) baseline
python benchmark_comparison.py

# 8. Generate all figures (saved to figures/)
python generate_figures.py

# 9. Generate paper tables (saved to tables/)
python paper_data_tables.py

# 10. Generate abstract (requires Anthropic API key)
python abstract_generator.py

# 11. Verify SSEF submission checklist
python ssef_checklist.py

# Or run the full pipeline at once:
python run_all.py
```

### Environment Variables

Copy `.env.example` to `.env` and set:

```
ANTHROPIC_API_KEY=sk-ant-...   # for abstract_generator.py
```

---

## File Structure

```
uifpi/
├── uifpi.db                      # SQLite database: prices, NLP results, index
├── uifpi_index.csv               # Monthly UIFPI index per country
│
├── cpi_data/                     # Official CPI JSON files per country
│   ├── monthly_cpi_sg.json
│   └── ...
│
├── analysis_results/             # JSON outputs from all analysis scripts
│   ├── granger_results.json
│   ├── robustness.json
│   └── benchmark_comparison.json
│
├── figures/                      # Paper figures (PNG, 300 DPI)
│   ├── fig1_index_comparison.png
│   ├── fig2_lead_times.png
│   ├── fig3_pass_through.png
│   ├── fig4_benchmark.png
│   └── fig5_country_map.png
│
├── tables/                       # Paper tables (CSV + LaTeX)
│   ├── table1_sample.{csv,tex}
│   ├── table2_descriptive.{csv,tex}
│   ├── table3_granger.{csv,tex}
│   └── table4_passthrough.{csv,tex}
│
├── paper_draft/                  # Draft paper components
│   ├── abstract.md
│   └── abstract_ssef.md
│
├── historical_scraper.py         # Web scraping (historical + live)
├── nlp_pipeline.py               # Dish name classification
├── index_builder.py              # UIFPI index construction
├── granger_analysis.py           # Granger causality + pass-through
├── robustness_checks.py          # Robustness validation
├── benchmark_comparison.py       # AR(1) vs UIFPI benchmark
├── generate_figures.py           # All 5 paper figures
├── paper_data_tables.py          # All 4 paper tables (CSV + LaTeX)
├── abstract_generator.py         # AI-assisted abstract generation
├── ssef_checklist.py             # SSEF submission requirements check
└── run_all.py                    # Full pipeline runner
```

---

## Key Findings

> **Status: Data collection ongoing. Findings below are preliminary.**

- **7,233** price observations collected across **8 countries**, 2018–present.
- **UIFPI construction** validated across both formal (restaurant) and informal
  (hawker/street vendor) sectors.
- **Granger causality** testing underway — preliminary analysis suggests 1–3
  month lead over official CPI. Full monthly time-series pending.
- **Pass-through hypothesis** supported in preliminary analysis: informal
  vendors show lower cost transmission than formal restaurants.
- **Robustness:** Results stable across alternative basket specifications
  and ±10pp informal sector weight variations (Test 2, 3). Jackknife
  stability pending sufficient monthly observations per country (Test 1).

*Full quantitative findings will be updated upon completion of monthly
data collection. All scripts are deterministic and results are reproducible
from the open-source database.*

---

## Citation

If you use this project or dataset in your research, please cite:

```
Chen, E. (2026). UIFPI: A Unified Informal-Formal Restaurant Price Index
as a Leading Indicator of Consumer Price Inflation. Singapore Science and
Engineering Fair Research Paper. Available at: [SSRN preprint — forthcoming]
```

---

## SSRN Preprint

SSRN preprint link will be added once available.

---

## License

MIT License. See `LICENSE` for full terms.

---

## Contact

For questions or collaboration enquiries: open an issue on this repository.

*Built with Claude Code.*

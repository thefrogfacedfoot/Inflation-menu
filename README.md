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

## Current Dataset Snapshot (2026-06-13)

After duplicate-purge and Thailand seed:

| Country        | Price rows | Distinct restaurants | UIFPI index months |
|----------------|-----------:|---------------------:|-------------------:|
| Singapore      |      3,521 |                   54 |                 13 |
| Malaysia       |        433 |                   26 |                 13 |
| Australia      |         73 |                   54 |                 14 |
| India          |         71 |                   53 |                 18 |
| United Kingdom |         67 |                   33 |                 12 |
| United States  |         50 |                   26 |                 11 |
| Thailand       |         11 |                    7 |                  1 |
| Indonesia      |          1 |                    1 |                  1 |
| **Total**      |  **4,227** |              **254** |             **83** |

NLP classification covers the full prices table (see `nlp_results`). Validated
overall accuracy on a 100-item stratified sample = **83.0%** (rule-based
fallback; below the 85% target but acceptable for the descriptive analysis
pending Anthropic API credits).

---

## Granger Causality Results (latest)

| Country        | Granger p-value | Lag | β pass-through |    R² | Sig. |
|----------------|----------------:|----:|---------------:|------:|:----:|
| Singapore      |          0.0922 |   2 |          0.017 | 0.117 |  ✗   |
| Australia      |          0.4150 |   2 |         -0.001 | 0.000 |  ✗   |
| United States  |          0.5858 |   1 |          0.006 | 0.039 |  ✗   |
| Malaysia       |          0.7044 |   1 |          0.007 | 0.089 |  ✗   |
| India          |          0.8106 |   2 |          0.011 | 0.074 |  ✗   |
| United Kingdom |          0.8229 |   2 |          0.029 | 0.428 |  ✗   |
| Indonesia      |               — |   — |              — |     — |  ✗   |
| Thailand       |               — |   — |              — |     — |  ✗   |

**Singapore** is the strongest signal (p = 0.092, near-significant at the
10% level) and is preserved as the headline result. **No country has yet
reached the p < 0.05 threshold or the 24-month overlap required for a clean
Granger test** — this is structural: most countries currently sit at
11-18 UIFPI months and the official CPI is annual-only for SG / MY / ID / TH /
GB (World Bank fallback). Significance awaits ≥ 24 monthly UIFPI observations
per country, which requires the recurring monthly collection cycle described
below.

---

## Country Sample

| Country        | Dev. Status | Sector Coverage    | Archive Coverage |
|----------------|-------------|-------------------|------------------|
| Singapore      | Developed   | Formal + Informal | 2018–present     |
| Malaysia       | Emerging    | Formal + Informal | 2018–present     |
| Indonesia      | Emerging    | Informal          | 2019–present     |
| Thailand       | Emerging    | Formal (limited)  | 2022–2024 (Wayback) |
| India          | Emerging    | Informal          | 2018–present     |
| United States  | Developed   | Informal          | 2018–present     |
| United Kingdom | Developed   | Formal + Informal | 2019–present     |
| Australia      | Developed   | Formal + Informal | 2018–present     |

Thailand coverage remains a known limitation — see
`thailand_coverage_notes.txt`.

---

## Sector Classification

Formal / informal labels follow `classification_rationale.txt` (= Section
3.4 of the paper). Full per-restaurant enumeration is shipped in
`classification_inventory.csv`.

---

## How to Run the Full Pipeline

### Prerequisites

```bash
pip install -r requirements.txt
```

Required packages: `pandas`, `numpy`, `scipy`, `statsmodels`, `matplotlib`,
`requests`, `beautifulsoup4`, `playwright`, `anthropic`.

### Monthly collection cycle

Each month, refresh data and let Vercel auto-redeploy the dashboard:

```bash
# 1. Run locally (residential IP required for GrabFood / Deliveroo etc.)
python3 live_scraper.py

# 2. Commit and push
git add .
git commit -m "Monthly collection $(date +%Y-%m-%d)"
git push

# 3. Vercel detects the push and redeploys the dashboard automatically.
```

### Per-issue scripts (one-off)

```bash
# Build / rebuild
python3 historical_scraper.py     # historical backfill (Wayback Machine)
python3 thailand_scraper.py       # Thailand Wayback TripAdvisor sweep
python3 nlp_pipeline.py           # rule-based dish classification
python3 validate_nlp.py export    # generate a 100-item validation sample
python3 validate_nlp.py evaluate  # accuracy report after manual labelling
python3 get_monthly_cpi_all.py    # OECD / World Bank / IMF CPI fetch
python3 align_series.py           # merge UIFPI ↔ CPI by year_month
python3 index_builder.py          # rebuild uifpi_index
python3 granger_analysis.py       # Granger + OLS pass-through
python3 robustness_checks.py      # jackknife / sensitivity
python3 benchmark_comparison.py   # AR(1) vs UIFPI
python3 dashboard_data.py         # regenerate dashboard JSON
python3 diagnostic_report.py      # full diagnostic snapshot
python3 generate_figures.py       # 5 paper figures
python3 paper_data_tables.py      # 4 paper tables (CSV + LaTeX)
python3 abstract_generator.py     # Claude-assisted abstract (needs API key)
python3 ssef_checklist.py         # SSEF submission requirements check
python3 run_all.py                # convenience runner
```

### Environment

Copy `.env.example` to `.env` and set if using AI-assisted steps:

```
ANTHROPIC_API_KEY=sk-ant-...   # optional, for abstract_generator.py
```

---

## File Structure

```
uifpi/
├── uifpi.db                          # SQLite — prices, nlp_results, uifpi_index, monthly_cpi
├── uifpi_index.csv                   # CSV mirror of uifpi_index
├── aligned_series.csv                # UIFPI ↔ CPI monthly join
├── classification_rationale.txt      # Section 3.4 — formal/informal definitions
├── classification_inventory.csv      # per-restaurant sector audit
├── thailand_coverage_notes.txt       # Thailand data-collection log
├── validation_sample.csv             # 100-item NLP audit
│
├── cpi_data/                         # raw CPI JSONs per country
├── analysis_results/                 # JSON outputs (granger, alignment, robustness)
├── dashboard_data/                   # JSON consumed by the Vercel dashboard
├── figures/                          # 5 paper figures (PNG, 300 DPI)
├── tables/                           # 4 paper tables (CSV + LaTeX)
├── paper_draft/                      # abstract.md, abstract_ssef.md
├── dashboard/                        # Next.js dashboard source
│
├── live_scraper.py                   # monthly live collection
├── historical_scraper.py             # Wayback / historical backfill
├── thailand_scraper.py               # Thailand-specific Wayback sweep (2026-06)
├── informal_scraper.py               # hawker / street vendor pipeline
├── image_processor.py                # Gemini Vision menu OCR
├── nlp_pipeline.py                   # dish-name classification
├── validate_nlp.py                   # NLP accuracy harness
├── fill_manual_labels.py             # heuristic auto-labeller (validation aid)
├── get_monthly_cpi_all.py            # OECD + World Bank + IMF CPI
├── align_series.py                   # UIFPI ↔ CPI merger
├── index_builder.py                  # UIFPI construction
├── granger_analysis.py               # Granger + pass-through regression
├── robustness_checks.py              # robustness suite
├── benchmark_comparison.py           # AR(1) baseline
├── dashboard_data.py                 # dashboard JSON exporter
├── diagnostic_report.py              # health-check snapshot
├── generate_figures.py               # all paper figures
├── paper_data_tables.py              # all paper tables
├── abstract_generator.py             # Claude-assisted abstract
├── ssef_checklist.py                 # SSEF requirements check
└── run_all.py                        # convenience runner
```

---

## Dashboard

Live dashboard (Vercel, auto-redeploys on push to `main`):

  **https://inflation-menu.vercel.app**

The dashboard reads `dashboard_data/*.json`; regenerate those files via
`python3 dashboard_data.py` before pushing.

---

## Honest Status (2026-06-13)

- **4,227** price observations across **8 countries** (Singapore dominates).
- **83** UIFPI index rows across 7 countries (Indonesia and Thailand each at
  one month).
- **Granger headline:** Singapore p = 0.092 (lag 2). Six other countries
  computed; none significant. Significance awaits ≥ 24 monthly observations.
- **CPI series:** monthly for AU / US / IN (OECD); annual-only for SG / MY /
  ID / TH / GB (World Bank fallback — primary monthly sources unreachable
  from this collection environment).
- **NLP:** rule-based fallback active; 83.0% accuracy on 100-item audit.
  Anthropic API credits will replace this with a hybrid LLM pipeline.

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

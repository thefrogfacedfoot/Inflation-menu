# What this project is
UICPI (branded UIFPI in code/DB) — a research project that scrapes restaurant menu prices (live delivery platforms + Wayback Machine archives) across ~10 countries, builds a monthly food-price index, and tests whether it Granger-leads official CPI. Outputs: a research paper (paper_draft/), a Next.js dashboard (dashboard/, deployed on Vercel), and a Flask read-only API.

# Stack
- Python 3.9 (system python3), pandas/numpy/statsmodels, Playwright, Flask
- SQLite in WAL mode: uifpi.db (NOT tracked in git — 112 MB, gitignored; restore from the newest `uifpi.db.backup_*` copy in the repo root)
- Claude API for NLP item classification; Gemini Vision for menu-photo extraction; keys in .env
- dashboard/ is Next.js + TypeScript (npm) and has its own CLAUDE.md/AGENTS.md

# Commands
- Setup: `pip install -r requirements.txt && playwright install chromium`
- Daily scrape: `python3 live_scraper.py` (runs nightly via launchd; needs a residential IP — datacenter IPs are bot-blocked; keep UIFPI_CONCURRENCY=1)
- Rebuild index: `python3 index_builder.py` → Granger: `python3 granger_analysis.py --min-obs 24` → dashboard export: `python3 dashboard_data.py`
- Monthly orchestrator: `scheduled/monthly_ingest.py` (GitHub Actions, 1st of month, runs with --skip-scrape)
- No test suite — verify by running the affected script and checking its output/DB effect.

# Rules for this repo
- No `Co-Authored-By: Claude` (or similar) trailer on commits in this repo.
- Before any destructive DB operation, copy uifpi.db to `uifpi.db.backup_<desc>_<YYYYMMDD_HHMMSS>` (existing repo convention).
- DoorDash is excluded from index construction via `index_builder.EXCLUDED_SOURCES` (it dilutes the US Granger signal); raw rows stay in `prices`. Never let excluded sources back into the index or dashboard aggregates.
- Sector taxonomy: DB labels are `chain`/`independent` (renamed 2026-06-21) but JSON keys and variable names keep legacy `formal`/`informal`. Any sector filter must handle BOTH label generations — partial renames silently drop rows. After any DB label rename, audit every filter/comparison downstream.
- The headline US result is the calendar-true respec: F=4.20, p=0.0499 (2026-07-06). The old F=6.03/p=0.021 is DEPRECATED (gap-mixing) — don't cite it in paper or dashboard.
- Secrets stay in .env — never write a real key into any file.

# Gotchas
- Currency parsing: VND and IDR are dot-grouped thousands with no decimals ("45.000" = 45000); GrabFood VN's `priceInMinorUnit` carries raw VND, not centimes. EUR uses comma decimals.
- FALLBACK_RATES lives in fx_rates.py (single source of truth for active pipeline scripts since 2026-07); the four consumer scripts import it — update rates there only. migrate_db.py, a dormant one-off migration tool, retains its own copy — no production impact.
- Wayback fetches must use the `id_` raw-bytes path or you get rewritten markup and wrong timestamps.
- The repo root is littered with one-off `phase0_*` / `probe_*` scripts and `*.log` files — historical artifacts of the probe-first workflow. The active core is live_scraper.py, historical_html_scraper.py, index_builder.py, granger_analysis.py, dashboard_data.py, get_monthly_cpi_all.py.

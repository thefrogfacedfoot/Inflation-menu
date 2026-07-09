# Blueprint 6 — Quarantine corrupted UAE/VN wayback price slices; verify and repair index contamination

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because it must diagnose two different parser failures, quantify index contamination, and apply a scoped exclusion without collateral damage to healthy sources.

## Context (all of it)

Repo: `/Users/erwenchen/Inflation-menu` (run everything from there). Python 3.9, no test suite — verify by running scripts. SQLite DB `uifpi.db` (~160k rows in `prices`; NOT in git; back up to `uifpi.db.backup_<desc>_<YYYYMMDD_HHMMSS>` before any destructive DB op). Pipeline: `index_builder.py` → `granger_analysis.py --min-obs 24` → `dashboard_data.py`.

**Discovery (2026-07-09).** While shipping the fx-rates consolidation (`blueprints/fx-rates-module.md`, currently parked), a baseline diff exposed two corrupted row slices that had been hidden from dashboard aggregates only because `dashboard_data.py`'s old private FX dict lacked VND/AED (so its null-`price_usd` backfill silently skipped them):

| slice | rows | symptom | example |
|---|---:|---|---|
| `country='United Arab Emirates'`, `source='wayback-deliveroo'`, `currency='AED'` | 9,243 (= 100% of AED rows) | ALL `price_usd IS NULL`; raw prices 1.0–99,909.99, clusters at 90,009 | "Butter Roti 90,009 AED" (2022-08-10) |
| `country='Vietnam'`, `source='wayback-grabfood'`, sector chain | 4,309 (all VN wayback-grabfood) | ALL `price_usd IS NULL`; raw "VND" prices 0.17–6,000, mean 488 | "Salt Coffee 0.17 VND" (2024-07-17) |

Live VN `grabfood` rows (2,196) are healthy (2,000–850,000 VND, `price_usd` populated). Deliveroo and GrabFood are healthy in other countries — any exclusion must be scoped by (country, source), NOT by source alone.

**Panel context (owner, 2026-07-09):** neither Vietnam nor the UAE is in the final 8-country panel reported in the paper (US, UK, Singapore, Malaysia, India, Australia, Indonesia, Thailand). Losing VN/UAE index history to quarantine costs nothing that the paper depends on. The check that DOES matter is zero collateral impact on the 8 panel countries — above all the United States (the Granger headline input).

**The critical part — the index is likely already contaminated.** Unlike the dashboard exporter, `index_builder.py` has had VND/AED in its fallback dict all along, and its loader backfills: `load_price_data` (see ~lines 137–168) maps null-`price_usd` rows through `FALLBACK_RATES` — with **`.fillna(1.0)` for unknown currency codes** (line ~163) — then keeps every row with `price_usd > 0`. So the corrupted rows have been entering the UAE/VN index since ingestion. Suspect symptom: Vietnam's index printed a value of **25,455.82 for 2026-06**. A prior scaling bug of the same family (Vietnam ×100) is discussed in `docs/granger_results_2026-06-18.md`. Relevant currency gotcha (CLAUDE.md): VND and IDR are dot-grouped thousands with no decimals — "45.000" means 45,000; a parser reading it as float 45.0 produces exactly a ÷1000 error.

**Repo conventions that bind you:** raw rows stay in `prices` — quarantine at load/export time like the existing `EXCLUDED_SOURCES = ("wayback-doordash",)` pattern (`index_builder.py` ~line 51, applied ~lines 191–193; `dashboard_data.py` has its own copy near `DB_SECTOR_TO_FIELD`). No `Co-Authored-By`/`Claude-Session` trailers. Branch + PR, never straight to main. Never `git add -A`/`git add .`; do NOT stage `scraper_log.txt`, `exchange_rates.json`, `sapient-split/`, `uifpi.db.backup_*`, or `blueprints/fx-rates-module.md`.

**Working-tree precondition:** the fx-rates refactor edits are stashed as `bp3-fx-parked` (`git stash list` must show it). Do NOT pop, apply, or drop any stash. Apart from `scraper_log.txt` churn and untracked files, the tree must be clean; if tracked pipeline files show unexplained modifications, stop and report.

## Phase A — setup

```bash
git checkout main && git pull
git checkout -b fix/quarantine-corrupt-wayback-slices
git stash list   # must contain bp3-fx-parked — leave it alone
```

## Phase B — root-cause investigation (findings go in a new doc, `docs/data_quality_2026-07.md`)

For EACH slice, using read-only SQL plus reading the relevant parser in `historical_html_scraper.py` (the emitter of `wayback-deliveroo` and `wayback-grabfood` rows — find each source's parser function via the TARGETS list):

1. Distribution: price histogram/deciles, top-20 most frequent price values, count by collection year, count of distinct restaurants.
2. Parser autopsy: read the parsing code and identify the failure mode. For UAE test the hypotheses: digit-fusion of "9.00" with adjacent markup (would explain 90,009 clusters), fils/dirham unit confusion (×100 family, like the prior Vietnam ×100 issue in `docs/granger_results_2026-06-18.md`), or plain extraction of non-price DOM content. For VN test: dot-grouped thousands parsed as decimal (÷1000 — "45.000" → 45.0), USD values passed through mislabeled as VND, or GrabFood `priceInMinorUnit` mishandling.
3. Recoverability note (LIGHT — owner has deprioritized recovery since neither country is in the final panel): if the failure mode makes an obvious deterministic transform apparent (e.g. ×1000 for dot-grouped thousands), note it in the doc in one or two sentences; do NOT run a full recovery validation, do NOT attempt recovery, and do NOT mutate raw rows.

## Phase C — quantify index contamination (the critical check)

1. Confirm the mechanism: show that `index_builder.load_price_data`'s backfill converts the two slices (count backfilled rows per country/currency — add a temporary print or run the logic in a scratch script; do not commit temporary instrumentation).
2. Rebuild the index twice from the current DB — once as-is, once with the two slices excluded (scratch-script variant of the loader, or a temporary env-guarded filter you then remove) — and diff `uifpi_index.csv` for the United Arab Emirates and Vietnam rows. Record before/after for every affected (country, month), and specifically whether VN 2026-06 = 25,455.82 is explained by the corrupt slice.
3. Collateral check: all OTHER countries' index rows must be byte-identical between the two builds — especially the United States (the Granger headline input). If any non-AE/VN row changes, stop and report.

## Phase D — the fix: scoped quarantine at load/export

1. Create `data_quality.py` at the repo root: module docstring explaining the two slices and pointing to `docs/data_quality_2026-07.md`, then

```python
QUARANTINED_SLICES = (
    # (country, source) — raw rows stay in `prices`; excluded from index
    # construction and dashboard aggregates. See docs/data_quality_2026-07.md.
    ("United Arab Emirates", "wayback-deliveroo"),
    ("Vietnam", "wayback-grabfood"),
)
```

2. `index_builder.py`: import it and drop quarantined (country, source) rows in `load_price_data` immediately after the existing `EXCLUDED_SOURCES` drop (~lines 191–193), printing an exclusion line in the same style (e.g. `Quarantined N rows: <country>/<source> (kept in raw DB)`).
3. `dashboard_data.py`: same filter in `load_price_counts`, next to its `EXCLUDED_SOURCES` handling. Prefer a post-fetch Python filter over SQL-string surgery if that is simpler and matches the existing code style.
4. Do NOT touch `granger_analysis.py` (its per-source stratification deliberately bypasses exclusions) or any parser in `historical_html_scraper.py` (dead code for these slices until a re-scrape; note it in the doc instead).
5. **Avoid touching the `FALLBACK_RATES` import region of either file** — the parked fx-rates stash edits those lines and must apply cleanly afterwards.

## Phase E — rebuild, verify, ship

1. `python3 index_builder.py && python3 granger_analysis.py --min-obs 24 && python3 dashboard_data.py` — all exit 0; the two quarantine exclusion lines print.
2. Acceptance (stop and report on any failure):
   - `uifpi_index.csv`: AE/VN rows match the "excluded" build from Phase C; **all other countries byte-identical** to the pre-quarantine build.
   - `dashboard/public/data/country_summary.json`: `United Arab Emirates.avg_price_formal_usd` and Vietnam's values computed WITHOUT the quarantined rows; United States values unchanged (items_formal etc. identical to committed).
   - Granger: United States entry unchanged from committed `analysis_results/granger_results.json` (n=31; it still reports the deprecated in-script spec — expected, do not "fix").
   - Future-proof check (this is what unblocks the fx-rates blueprint): `python3 -c` snippet proving zero rows reaching `dashboard_data.load_price_counts` have `price_usd IS NULL` with `currency IN ('VND','AED')`.
3. Write `docs/data_quality_2026-07.md` (Phase B findings, Phase C quantification incl. the VN 19-months-of-history consequence, recovery recommendations). Add a newest-first CHANGELOG.md section dated with the execution date summarizing slice, cause, quarantine, and index impact.
4. ONE commit: `data_quality.py`, `index_builder.py`, `dashboard_data.py`, regenerated `uifpi_index.csv` + `analysis_results/*` + `dashboard_data/*.json` + `dashboard/public/data/*.json`, `docs/data_quality_2026-07.md`, `CHANGELOG.md`, `blueprints/quarantine-corrupt-wayback-slices.md`. Message: `Quarantine corrupted UAE/VN wayback slices from index and dashboard aggregates` (no trailers). Push; `gh pr create` to main; PR body: incident summary, index-impact numbers, the VN history-loss consequence, recovery recommendation, ending `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
5. STOP after opening the PR. In the PR body and your final report note: **the fx-rates blueprint resumes only after this PR merges** (fresh branch from updated main, `git stash pop` of `bp3-fx-parked`, rerun its baseline diff — which should now be clean).

In your final report: the two root-cause verdicts with evidence, recoverability verdicts with validation numbers, the AE/VN index before/after table, confirmation of zero collateral change to other countries, and the PR URL.

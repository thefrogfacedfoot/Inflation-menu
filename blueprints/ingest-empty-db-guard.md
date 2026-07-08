# Blueprint 1 — Repair the 2026-07 ingest damage and guard monthly_ingest against a missing database

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because this touches CI and requires verifying pipeline output values.

## Context (all of it — you have no other memory)

Repo: `/Users/erwenchen/Inflation-menu` (run everything from this directory). UICPI/UIFPI is a research project: Python 3.9 scrapers → SQLite `uifpi.db` → `index_builder.py` → `granger_analysis.py` → `dashboard_data.py` (exports JSON consumed by a Next.js dashboard on Vercel). There is no test suite; you verify by running scripts and checking their output/DB effect.

**The incident.** `uifpi.db` (112 MB, ~155,852 rows in `prices` as of 2026-07-07) is listed in `.gitignore` and is NOT tracked in git. The GitHub Actions workflow `.github/workflows/monthly_ingest.yml` runs `scheduled/monthly_ingest.py --skip-scrape` on the 1st of each month on a GitHub-hosted runner. On 2026-07-01 the runner's checkout had **no `uifpi.db` at all**, so the orchestrator ran the whole pipeline against a fresh empty database and committed the resulting garbage as commit `aa0fbb7` ("Monthly ingest 2026-07"): zeroed `dashboard/public/data/*.json`, zeroed `dashboard_data/*.json`, a broken `analysis_results/granger_results.json`, and two all-zero sections in `docs/ingest_log.md` (including a spurious "United States dropped below Granger threshold" event). That commit was then merged into local work via `d2bd832` ("Merging issues?"). The local `uifpi.db` is fine; only the committed export artifacts are garbage.

Evidence you can re-verify: `dashboard/public/data/country_summary.json` → `United States` has `items_formal: 0`; `analysis_results/granger_results.json` → `Malaysia` says `"note": "no_cpi_data"` even though `sqlite3 uifpi.db "SELECT COUNT(*) FROM monthly_cpi WHERE country_code='MY'"` returns 136 and `granger_analysis.load_cpi('Malaysia')` returns a 136-obs series.

**Repo rules that bind you:**
- Before any destructive DB operation, copy `uifpi.db` to `uifpi.db.backup_<desc>_<YYYYMMDD_HHMMSS>`.
- No `Co-Authored-By: Claude` (or similar) trailer on commits in this repo.
- Code changes go on a branch with a PR — never push straight to main.
- Do NOT run `live_scraper.py` (needs residential IP; not needed here).

## Phase A — repair the committed artifacts

1. `cp uifpi.db "uifpi.db.backup_pre_ingest_repair_$(date +%Y%m%d_%H%M%S)"`
2. Create a branch: `git checkout -b fix/ingest-empty-db-guard`
3. Run, in order, checking each exits 0:
   ```bash
   python3 index_builder.py
   python3 granger_analysis.py --min-obs 24
   python3 dashboard_data.py
   ```
4. Acceptance checks (all must pass; if one fails, stop and report the failure — do not improvise):
   - `dashboard/public/data/country_summary.json`: `United States.items_formal > 0`, `Singapore.items_formal > 0`.
   - `analysis_results/granger_results.json`: `Malaysia.note != "no_cpi_data"` and `Malaysia.n_obs > 0`; `India.n_obs >= 30`.
   - **Expected and correct:** the US entry will be non-significant (p ≈ 0.4–0.5). The default `granger_analysis.py` spec is deprecated as the headline; the real headline (F=4.20, p=0.0499) lives in `analysis_results/gap_robustness.json` and is produced by `gap_robustness.py`. Do NOT try to "fix" granger_analysis.py to make the US significant.

## Phase B — annotate the garbage ingest-log sections

In `docs/ingest_log.md` there are two sections headed `## 2026-07-01 06:16`. Immediately after **each** of those two header lines, insert this line:

```
**INVALID RUN** — the GitHub Actions runner had no `uifpi.db` (the file is gitignored and never present on runners); the all-zero rows and the "United States dropped below Granger threshold" event below are artifacts of running against an empty database. See CHANGELOG 2026-07-07.
```

Do not delete the sections (the log is append-only by design).

## Phase C — guard in `scheduled/monthly_ingest.py`

In `main()`, directly after these existing lines (~line 170–173):

```python
    before = _snap(DB)
    granger_before = _granger_snap(DB)
    total_before = sum(r[0] for r in before.values())
    print(f'\nBefore: {total_before:,} total price rows across {len(COUNTRIES)} countries')
```

insert:

```python
    MIN_EXPECTED_ROWS = 50_000  # local DB had ~156k rows on 2026-07-07; a near-empty
                                # table means uifpi.db is missing from this checkout
    if total_before < MIN_EXPECTED_ROWS and not args.allow_empty_db:
        print(f'\n  ✗ ABORT: prices table has {total_before:,} rows '
              f'(< {MIN_EXPECTED_ROWS:,}). uifpi.db is missing or empty in this '
              f'checkout — running the pipeline would produce and commit garbage '
              f'(this happened on 2026-07-01). No stages were run, nothing was '
              f'written. Pass --allow-empty-db to override.')
        return 2
```

And add to the argparse block:

```python
    ap.add_argument('--allow-empty-db', action='store_true',
                    help='Bypass the minimum-row sanity guard (fresh-start scenarios only).')
```

The guard intentionally fires in `--dry-run` too: the workflow runs a dry-run first, so a missing DB now turns the run red at the earliest step.

## Phase D — workflow and docs fixes

1. `.github/workflows/monthly_ingest.yml`: in the "Commit and push" step's `git add` list, delete the line `uifpi.db \` (it is gitignored — the line silently no-ops). Add this comment line directly under the existing `# IMPORTANT:` comment block at the top of the file:
   ```
   # NOTE (2026-07-07): uifpi.db is gitignored and never present on GitHub-hosted
   # runners, so scheduled runs will fail red at monthly_ingest.py's row-count
   # guard. That is intentional: it beats committing zeroed exports (see the
   # 2026-07-01 incident in CHANGELOG.md). To make cloud ingest work, attach a
   # self-hosted runner that has the real uifpi.db.
   ```
2. `CLAUDE.md` (repo root): replace the line
   `- SQLite in WAL mode: uifpi.db (committed to git — restore with \`git checkout HEAD -- uifpi.db\`)`
   with
   `- SQLite in WAL mode: uifpi.db (NOT tracked in git — 112 MB, gitignored; restore from the newest \`uifpi.db.backup_*\` copy in the repo root)`
3. Append to `CHANGELOG.md` a new top section:
   ```
   ## 2026-07-07 — Repair 2026-07 ingest artifacts; guard against empty-DB runs

   The 2026-07-01 GitHub Actions ingest ran on a runner with no uifpi.db
   (the file is gitignored) and committed zeroed dashboard/analysis exports
   (aa0fbb7), later merged in d2bd832. Repaired by rebuilding index/Granger/
   dashboard exports locally from the intact 156k-row database.
   monthly_ingest.py now aborts (exit 2) when the prices table has fewer
   than 50,000 rows unless --allow-empty-db is passed; the workflow no
   longer stages the gitignored uifpi.db.
   ```
   CHANGELOG sections are newest-first: insert it directly under the `# Changelog` intro lines, above the `## 2026-06-18` section.

## Phase E — verify the guard, then ship

1. Verify the guard fires: `python3 -c "import sqlite3,os; os.makedirs('/tmp/uifpi_guard_test',exist_ok=True); sqlite3.connect('/tmp/uifpi_guard_test/uifpi.db').execute('CREATE TABLE IF NOT EXISTS prices (country TEXT, price REAL, collection_date TEXT)')"` then run the orchestrator pointed at an empty DB is not supported (DB path is hardcoded) — instead verify by temporary override: `python3 - <<'EOF'` … — **simpler, do this:** run `python3 scheduled/monthly_ingest.py --dry-run --skip-scrape` against the real DB and confirm it does NOT abort (156k rows > 50k), and confirm by code-reading that `total_before` would be 0 when `DB` doesn't exist (`_snap` returns zeros for a missing file — it already handles this at the top of the function).
2. Commit everything (the regenerated JSON/CSV artifacts from Phase A, the ingest-log annotation, monthly_ingest.py, the workflow, CLAUDE.md, CHANGELOG.md) on the branch with message:
   `Repair 2026-07 ingest artifacts; abort monthly ingest when uifpi.db is missing`
   No Co-Authored-By trailer.
3. Push the branch and open a PR against `main` with `gh pr create`. PR body: summarize the incident and fix in 4–6 sentences (reuse the CHANGELOG text), and end with:
   `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
4. In your final report, state the before/after values of `United States.items_formal` and the Malaysia granger note, and paste the tail of each pipeline script's output.

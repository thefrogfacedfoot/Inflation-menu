# Blueprint 3 — Finish the sector-label rename (7,571 stale `formal` rows) and close the dashboard exclusion gap

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because two bugs currently cancel each other and the fix order matters.

## Context (all of it)

Repo: `/Users/erwenchen/Inflation-menu`. SQLite DB `uifpi.db`, table `prices` (columns include `country`, `sector`, `source`, `restaurant_name`, `item_name`, `price`, `currency`, `price_usd`, `collection_date`).

On 2026-06-21 the sector taxonomy was renamed in the DB: `formal` → `chain`, `informal` → `independent`. JSON keys and variable names deliberately keep the legacy `formal`/`informal` spelling. Repo rule: any sector filter must handle BOTH label generations — partial renames silently drop rows.

Current state of `SELECT sector, COUNT(*) FROM prices GROUP BY 1` (2026-07-07):

| sector | rows | note |
|---|---:|---|
| chain | 94,069 | correct |
| independent | 15,996 | correct |
| grocery | 38,216 | all `source='official_price_series_bls_apu'` (US BLS grocery series) — intentional third label, excluded from the index by `index_builder.py`'s sector filter. DO NOT touch. |
| **formal** | **7,571** | **stale** — all `source='wayback-doordash'`, ingested after the rename because `historical_html_scraper.py`'s TARGETS tuples still say `'formal'` |

**The cancelling-bugs trap.** `wayback-doordash` is excluded from index construction via `index_builder.py` line 51 `EXCLUDED_SOURCES = ("wayback-doordash",)` (it dilutes the US Granger signal — repo rule: never let excluded sources back into the index or dashboard aggregates). But `dashboard_data.py::load_price_counts` (lines ~204–247) has **no source-exclusion filter at all**; the only reason DoorDash rows don't inflate the US dashboard counts today is that their stale `formal` label isn't in `DB_SECTOR_TO_FIELD = {"chain": "formal", "independent": "informal"}` (line 201), so they're accidentally skipped. **If you relabel the rows without first adding the source exclusion, 7,571 excluded rows enter the dashboard counts.** Therefore do step 2 before step 3.

**Repo rules:** back up `uifpi.db` to `uifpi.db.backup_<desc>_<YYYYMMDD_HHMMSS>` before any destructive DB op; no `Co-Authored-By` trailer; changes go on a branch + PR, never straight to main; no test suite — verify by running scripts.

## Steps (in this exact order)

### 1. Record the "before" dashboard counts and back up

```bash
git checkout -b fix/sector-label-cleanup
cp uifpi.db "uifpi.db.backup_pre_formal_relabel_$(date +%Y%m%d_%H%M%S)"
python3 dashboard_data.py
python3 -c "
import json
d = json.load(open('dashboard/public/data/country_summary.json'))
us = d['United States']
print('BEFORE:', us['items_formal'], us['items_informal'], us['restaurants_formal'])"
```
Save the printed values — step 5 compares against them.

### 2. Add source exclusion to `dashboard_data.py`

(a) Directly above the existing line `DB_SECTOR_TO_FIELD = {"chain": "formal", "independent": "informal"}` (~line 201), add:

```python
# Sources excluded from ALL dashboard aggregates — keep in sync with
# index_builder.EXCLUDED_SOURCES (DoorDash dilutes the US Granger signal;
# raw rows stay in `prices`). See CLAUDE.md.
EXCLUDED_SOURCES = ("wayback-doordash",)
```

(b) In `load_price_counts`, replace the query

```python
        cur = conn.execute(
            "SELECT country, sector, restaurant_name, price, currency, price_usd "
            "FROM prices "
            "WHERE price IS NOT NULL AND price > 0"
        )
```

with

```python
        placeholders = ",".join("?" for _ in EXCLUDED_SOURCES)
        cur = conn.execute(
            "SELECT country, sector, restaurant_name, price, currency, price_usd "
            "FROM prices "
            "WHERE price IS NOT NULL AND price > 0 "
            f"AND source NOT IN ({placeholders})",
            EXCLUDED_SOURCES,
        )
```

### 3. Relabel the stale rows

```bash
sqlite3 uifpi.db "UPDATE prices SET sector='chain' WHERE sector='formal' AND source='wayback-doordash'; SELECT changes();"
```
Must print `7571`. Then verify the label space is clean:
```bash
sqlite3 uifpi.db "SELECT sector, COUNT(*) FROM prices GROUP BY 1;"
```
Must show exactly three labels: `chain 101640`, `grocery 38216`, `independent 15996`. If any `formal`/`informal` rows remain, stop and report — do not delete anything.

### 4. Fix the emitter — `historical_html_scraper.py`

The TARGETS list (a Python list of tuples, begins ~line 504 with the comment `# (country, sector, platform_label, source_key, url_pattern, currency, parser_fn)`) has `'formal'` as the second field of every tuple. Within the TARGETS list **only**, replace every `'formal'` with `'chain'` and every `'informal'` with `'independent'` (if present). Do not rename anything outside the TARGETS list (function names, comments elsewhere are fine as-is). Verify: `python3 -c "import ast; ast.parse(open('historical_html_scraper.py').read())"` exits 0, and `grep -n "'formal'" historical_html_scraper.py` returns no hits inside the TARGETS block.

### 5. Rerun and compare

```bash
python3 dashboard_data.py
python3 -c "
import json
d = json.load(open('dashboard/public/data/country_summary.json'))
us = d['United States']
print('AFTER:', us['items_formal'], us['items_informal'], us['restaurants_formal'])"
```
**Acceptance: AFTER values equal the BEFORE values from step 1** (the relabelled DoorDash rows are now excluded by source instead of accidentally by label). Also run `python3 index_builder.py` — its log must still print the exclusion message for `wayback-doordash`, and it must complete without error (`index_builder.py` already maps both label generations at its lines 190–193 — do not change that).

### 6. Downstream filter audit (repo rule after any label change)

Run `grep -n "formal\|informal\|chain\|independent" granger_analysis.py nlp_pipeline.py get_monthly_cpi_all.py scheduled/monthly_ingest.py | grep -i "sector\|WHERE\|== \|!= "` and read each hit. Pass criterion: no SQL filter or equality comparison matches only one label generation. (Expected result: no violations — `granger_analysis.py` reads `uifpi_index`, not `prices`; report anything you find instead of fixing beyond this blueprint's scope.)

### 7. CHANGELOG + ship

Append a newest-first CHANGELOG.md section:

```
## 2026-07-07 — Sector-label cleanup: stale `formal` rows relabelled, dashboard source-exclusion added

7,571 wayback-doordash rows still carried the pre-2026-06-21 `formal` label
(historical_html_scraper.py TARGETS were never updated after the rename).
Relabelled to `chain` (backup: uifpi.db.backup_pre_formal_relabel_*), TARGETS
now emit `chain`/`independent`. dashboard_data.load_price_counts previously
had no source-exclusion filter and only skipped DoorDash by the accident of
the stale label; it now excludes EXCLUDED_SOURCES explicitly, so dashboard
counts are unchanged and DoorDash stays out of all aggregates.
```

Commit message: `Relabel stale formal sector rows; exclude EXCLUDED_SOURCES from dashboard counts` (no Co-Authored-By trailer). Push branch `fix/sector-label-cleanup`, open PR to main with `gh pr create`, PR body ending `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Commit the regenerated `dashboard_data/*.json` and `dashboard/public/data/*.json` too. Report the BEFORE/AFTER count comparison in your final message.

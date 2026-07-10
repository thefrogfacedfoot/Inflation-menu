# Blueprint 5 — Purge the deprecated US Granger stat (F=6.03 / p=0.021) from the live dashboard

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because the fix spans a Python exporter and JSX copy, and every number must be read from a JSON file, never typed from memory.

## Context (all of it)

Repo: `/Users/erwenchen/Inflation-menu` (run everything from there). Python 3.9, no test suite — verify by running scripts. The Next.js dashboard lives in `dashboard/` (its own CLAUDE.md/AGENTS.md — read them before touching it; build with `npm run build` from `dashboard/`), deployed on Vercel from main.

On 2026-07-06 the US Granger headline was respecified. The old spec — F = 6.0336, p = 0.021, n = 31 — is a gap-mixing artifact and is DEPRECATED: repo rule (CLAUDE.md) says it must not be cited in the paper or on the dashboard. The authoritative numbers live in `analysis_results/gap_robustness.json` (git-tracked, always present), top-level key `country` = "United States", key `specs`:

- `calendar_true` (role: headline): F = 4.2012, p_analytic = 0.0499, n = 31; permutation p 0.0519 (shuffle) / 0.0689 (block).
- `interp_ffill` (robustness): n = 38, F = 9.0542, p_analytic = 0.0048; permutation 0.017 / 0.013.

**Read every number you write from that JSON at execution time — do not trust the values above.**

The problem: `granger_analysis.py` still implements the deprecated spec (the respec was never backported — deliberate; do NOT modify `granger_analysis.py`), so the deprecated numbers reach the live dashboard through TWO independent paths:

1. **Data path:** `dashboard_data.py` reads `analysis_results/granger_results.json` (constant `GRANGER_JSON`, line ~24; loaded via `load_granger`, line ~65; consumed by `build_country_summary`, line ~255, which exports `granger_significant` and `granger_p_value` per country into `dashboard_data/country_summary.json` and `dashboard/public/data/country_summary.json`). The US entry carries `granger_p_value: 0.021, granger_significant: true`.
2. **Hardcoded JSX copy:**
   - `dashboard/app/page.tsx` line ~178: hero copy `finds they do in the US, with a 1-month lead (p = 0.021)`.
   - `dashboard/app/[country]/page.tsx`, component `USGrangerCallout` (starts ~line 357, rendered only for the US at line ~176): `<dd>` cells hardcode F `6.034` and p `0.021` (n `31` and Lag `1 mo` are still correct); the prose paragraph below cites per-lag p-values (0.090/0.138/0.146) and a pass-through p = 0.083 from the deprecated run; `FULL_RESULTS_URL` (~line 354) points at `docs/granger_results_2026-06-18.md`, which now carries a DEPRECATED banner.

`dashboard/.next/` also contains compiled copies of the old numbers — it is gitignored build cache; ignore it entirely.

`granger_results.json` itself (in `analysis_results/`) may keep the deprecated spec's output — it is analysis output, not a dashboard surface. Other scripts read it (`paper_data_tables.py`, `generate_figures.py`, `abstract_generator.py`, …); they feed the paper, which the author is rewriting personally. Do not touch them.

**Repo rules:** no `Co-Authored-By`/`Claude-Session` trailer on commits; changes on a branch + PR, never straight to main; keep changes minimal; never `git add -A` / `git add .`; do NOT stage `scraper_log.txt`, `exchange_rates.json`, `sapient-split/`, or `uifpi.db.backup_*`.

## GATE (binding)

Do not start until BOTH are true; if either is not, stop and report:
1. The `fix/ingest-empty-db-guard` PR (Blueprint 1) is merged to main and its Vercel deploy is live (the dashboard JSONs this blueprint regenerates must start from the repaired state).
2. The `docs/deprecate-old-granger-headline` PR (Blueprint "deprecated-granger-purge") is merged — step 4 below links the dashboard to `docs/ssef_data_status.md`, which that PR rewrites.

Then `git checkout main && git pull && git checkout -b fix/dashboard-headline-respec`.

## Steps

### 1. `dashboard_data.py` — override the US entry from the respec

(a) Next to `GRANGER_JSON` (~line 24) add:

```python
GAP_ROBUSTNESS_JSON = "analysis_results/gap_robustness.json"
```

(b) After `load_granger` add:

```python
def apply_headline_respec(granger: dict,
                          path: str = GAP_ROBUSTNESS_JSON) -> dict:
    """Override the deprecated gap-mixing Granger spec with the calendar-true
    respec for the country covered by gap_robustness.json (US).

    granger_analysis.py still emits the deprecated spec (F=6.0336, p=0.021 —
    a gap-mixing artifact, respecified 2026-07-06); repo rule: those numbers
    must never reach the dashboard. Fails loud if the respec file is missing
    (it is git-tracked) — silently falling back would republish deprecated
    numbers.
    """
    with open(path) as f:          # let FileNotFoundError propagate
        respec = json.load(f)
    country = respec["country"]
    spec = respec["specs"]["calendar_true"]
    if country in granger:
        granger[country]["granger_p_value"] = spec["p_analytic"]
        granger[country]["granger_f_statistic"] = spec["F"]
        granger[country]["granger_significant"] = spec["p_analytic"] < 0.05
        granger[country]["granger_spec"] = "calendar_true (gap_robustness respec 2026-07-06)"
    return granger
```

(c) In the main flow, directly after `granger = load_granger(granger_json)` (~line 440), insert:

```python
    granger = apply_headline_respec(granger)
```

Do not change `build_country_summary` — it already picks up the overridden values via `g.get(...)`. Leave `n_obs` alone (31 under both specs).

### 2. `dashboard/app/page.tsx` — hero copy

Replace (in the line ~178 region):

```
finds they do in the US, with a 1-month lead (p = 0.021)
```

with (p from `specs.calendar_true.p_analytic`, 4 dp):

```
finds they do in the US, with a 1-month lead (p = 0.0499)
```

### 3. `dashboard/app/[country]/page.tsx` — `USGrangerCallout`

(a) In the `<dd>` cells: F `6.034` → `4.201` (from `specs.calendar_true.F`, 3 dp), p `0.021` → `0.0499`. Leave n = 31 and Lag = 1 mo.

(b) Replace the prose paragraph (`AIC selected lag = 4, but lag = 1 dominates … not a level coincidence.`) — keeping the surrounding `<p className=…>` markup and the existing `<span className="font-semibold">timing signal</span>` element — with:

```
Calendar-true specification: exact 1-month lags on full-calendar CPI
changes, no imputation (permutation p = 0.052 shuffle / 0.069 block).
Forward-filling single-month menu gaps with past information only
strengthens the result (n = 38, F = 9.05, p = 0.0048). The result is a{" "}
<span className="font-semibold">timing signal</span>, not a level
coincidence.
```

(every number above must be re-read from `gap_robustness.json` before writing).

(c) Change `FULL_RESULTS_URL` to
`https://github.com/thefrogfacedfoot/Inflation-menu/blob/main/docs/ssef_data_status.md`
(the old target now opens on a DEPRECATED banner under a green "significant" callout — misleading).

### 4. Regenerate and verify

```bash
python3 dashboard_data.py
```

Then all of the following must pass (stop and report on any failure — do not improvise):

```bash
python3 - <<'EOF'
import json
for p in ("dashboard/public/data/country_summary.json", "dashboard_data/country_summary.json"):
    d = json.load(open(p))
    us = d["United States"]
    assert us["granger_p_value"] == 0.0499, (p, us["granger_p_value"])
    assert us["granger_significant"] is True, p
    # no country anywhere may carry the deprecated p-value
    for c, v in d.items():
        if isinstance(v, dict):
            assert v.get("granger_p_value") != 0.021, (p, c)
print("JSON checks PASS")
EOF
grep -rn "6\.0336\|6\.034" dashboard_data/ dashboard/public/data/ dashboard/app/   # must return NOTHING
grep -rn "0\.021" dashboard/app/                                                   # must return NOTHING
cd dashboard && npm run build && cd ..                                             # must exit 0
```

Also diff-sanity: `git diff --stat dashboard/public/data/` should show changes confined to the granger fields in `country_summary.json` (plus timestamp churn) — if `index_series.json` values move, stop and report.

### 5. Wider-pattern audit (report-only — fix nothing beyond the US)

The US turned out to have deprecated numbers on two independent surfaces; confirm it is not a wider pattern:

(a) `python3 -c "import json; d=json.load(open('analysis_results/granger_results.json')); print([c for c,v in d.items() if isinstance(v,dict) and v.get('granger_significant')])"` — expected: only `United States` (verified 2026-07-08). Any other country flagged significant is running on the gap-mixed spec with no respec available — report it prominently; do not fix.

(b) `grep -n "Callout" "dashboard/app/[country]/page.tsx"` — for every per-country callout component (e.g. `IndiaGrangerCallout`, hardcoded F=0.521 / n=47), compare its hardcoded numbers against the current `analysis_results/granger_results.json` entry for that country and report any drift. Null-result callouts citing the gap-mixed spec are a known limitation, not an error — report, don't edit.

(c) Report (don't touch) that `paper_data_tables.py` / `generate_figures.py` / `abstract_generator.py` still consume the deprecated `granger_results.json` — paper-side surfaces, owner is handling the paper personally.

## Ship

ONE commit on `fix/dashboard-headline-respec`. Stage: `dashboard_data.py`, the two `.tsx` files, the regenerated `dashboard_data/*.json` + `dashboard/public/data/*.json`, and `blueprints/dashboard-headline-respec.md`. Message:
`Dashboard: source US Granger headline from calendar-true respec; purge deprecated F=6.03/p=0.021`
(no trailers). Push; `gh pr create` to main, body summarizing the two purged surfaces and ending
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

In your final report: the before/after US granger fields, the output of every step-4 check, and the step-5 audit findings.

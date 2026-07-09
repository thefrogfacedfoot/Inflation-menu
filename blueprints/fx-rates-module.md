# Blueprint 4 — Single source of truth for FALLBACK_RATES (`fx_rates.py`)

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because one of the four copies uses an inverted convention and its call site must be flipped correctly.

## Context (all of it)

Repo: `/Users/erwenchen/Inflation-menu`. Python 3.9, no test suite — verify by running scripts. The hardcoded fallback FX dict `FALLBACK_RATES` is duplicated in four files and has drifted:

| file | line | currencies | convention |
|---|---|---|---|
| `live_scraper.py` | 68–71 | 8 (SGD MYR IDR THB INR USD GBP AUD) | **local-per-USD** (divide: `price / rate`, see its `to_usd` at line 143–145) |
| `index_builder.py` | 74–78 | 10 (adds VND 25_400.0, AED 3.67) | local-per-USD (`price / rate`) |
| `dashboard_data.py` | 180–183 | 8 | local-per-USD (`usd = price / rate`, line 230) |
| `image_processor.py` | 47–51 | 9 (adds EUR 1.08, missing VND/AED) | **INVERTED: USD-per-local** (multiplies: `price_local * rate`, lines 220 & 224) |

The inverted values are approximate reciprocals (0.74 ≈ 1/1.35), so converting `image_processor.py` to the shared convention changes outputs only in the 3rd decimal — that is expected and fine.

**Repo rules:** no `Co-Authored-By` trailer; changes on a branch + PR, never straight to main; keep changes minimal — do NOT touch `live_scraper.py`'s `get_usd_rates()` / `exchange_rates.json` live-rate logic, only the fallback dict.

## Steps

### 1. Create `fx_rates.py` at the repo root, exactly:

```python
"""Canonical hardcoded fallback FX rates for the UIFPI pipeline.

Convention: 1 USD = FALLBACK_RATES[code] units of local currency
(divide a local price by its rate to get USD).

Single source of truth — previously duplicated (and drifted) across
live_scraper.py / index_builder.py / dashboard_data.py / image_processor.py.
Update rates here only.
"""

FALLBACK_RATES = {
    "SGD": 1.35, "MYR": 4.70, "IDR": 15_750.0, "THB": 36.0,
    "INR": 83.5, "USD": 1.0, "GBP": 0.79, "AUD": 1.55,
    "VND": 25_400.0, "AED": 3.67, "EUR": 0.93,
}
```

(EUR 0.93 = 1/1.08 from image_processor's old USD-per-EUR value; VND/AED carried over from index_builder.)

### 2. Replace each duplicate with an import at the same spot

`live_scraper.py` — replace lines 67–71:
```python
# Hardcoded fallbacks used when the API call fails
FALLBACK_RATES = {
    'SGD': 1.35, 'MYR': 4.70, 'IDR': 15_750.0, 'THB': 36.0,
    'INR': 83.5,  'USD': 1.0,  'GBP': 0.79,     'AUD': 1.55,
}
```
with:
```python
# Hardcoded fallbacks used when the API call fails (single source of truth)
from fx_rates import FALLBACK_RATES
```

`index_builder.py` — replace its `FALLBACK_RATES = { ... }` block (lines ~74–78, the 10-currency version) with the same two lines (adjust the comment to match whatever comment sits above it, or drop the comment).

`dashboard_data.py` — replace its `FALLBACK_RATES = { ... }` block (lines ~180–183) the same way.

### 3. Fix `image_processor.py` (inverted convention)

(a) Replace lines 47–51:
```python
FALLBACK_RATES: Dict[str, float] = {
    "SGD": 0.74, "MYR": 0.21, "IDR": 0.000064, "THB": 0.028,
    "INR": 0.012, "USD": 1.0, "GBP": 1.27, "AUD": 0.66,
    "EUR": 1.08,
}
```
with:
```python
# 1 USD = rate units of local currency — divide to convert to USD.
from fx_rates import FALLBACK_RATES
```
(b) In its `to_usd` (lines 210–224), change both conversions from multiply to divide:
`return round(price_local * rate, 4)` → `return round(price_local / rate, 4)` (line 220), and
`return round(price_local * rate, 4)` → `return round(price_local / rate, 4)` (line 224).
The `rate = FALLBACK_RATES.get(currency, 1.0)` default of 1.0 stays correct under the new convention.
(c) If `Dict` was imported from `typing` solely for this dict's annotation, leave the import alone (other annotations use it).

### 4. Acceptance

```bash
python3 -c "from fx_rates import FALLBACK_RATES; assert len(FALLBACK_RATES) == 11"
python3 -c "import image_processor; print(image_processor.to_usd(10.0, 'sg', None))"    # expect ≈ 7.4074 (10/1.35)
python3 -c "import dashboard_data, index_builder"                                        # both import clean
grep -rn "FALLBACK_RATES = {" live_scraper.py index_builder.py dashboard_data.py image_processor.py   # must return NOTHING
```
Note: the original symbol-form check `to_usd(10.0, 'sg', 'S$')` trips a pre-existing symbol-matcher bug ("S$" → "SUSD" substring-matches "USD" before "SGD" is considered, returning rate 1.0) that predates this refactor and returns the same wrong 10.0 before and after it — behavior preserved, bug out of scope.

Then run the two pipeline consumers end-to-end and confirm they behave identically to before (same currencies, same values for the 8 shared codes):
```bash
python3 index_builder.py
python3 dashboard_data.py
git diff --stat dashboard/public/data/   # expect no changes, or timestamp-only churn
```
If `dashboard/public/data/*.json` shows value changes beyond float noise in the last decimal, stop and report — something imported wrong.

Note: `python3 -c "import live_scraper"` is NOT a required check (importing it configures logging and requires Playwright; skip it). Instead verify with `python3 -c "import ast; ast.parse(open('live_scraper.py').read())"`.

### 5. Ship

Branch `refactor/fx-rates-module`. Make TWO commits, in this order (no Co-Authored-By trailer on either):

1. `Add fx_rates.py; point live_scraper/index_builder/dashboard_data at it` — steps 1–2 only (zero behavior change), plus the CLAUDE.md gotcha-line update below and `blueprints/fx-rates-module.md` (it carries uncommitted amendments).
2. `image_processor: use shared FALLBACK_RATES; fix inverted USD conversion (multiply to divide)` — ALL of step 3 in this single commit. The import swap and the multiply→divide flip must land together — either one alone is broken. This isolates the only behavior-changing edit so it is bisectable.

Do NOT stage `scraper_log.txt`, `exchange_rates.json`, or `sapient-split/`. Push; `gh pr create` to main, PR body ending `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Update the CLAUDE.md gotcha line `- FALLBACK_RATES dicts are duplicated across ...` to read `- FALLBACK_RATES lives in fx_rates.py (single source of truth since 2026-07); the four consumer scripts import it — update rates there only.`

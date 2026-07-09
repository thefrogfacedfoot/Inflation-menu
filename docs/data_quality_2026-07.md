# Data quality incident 2026-07 — corrupted UAE/VN wayback price slices

Date: 2026-07-09. Discovered while validating a baseline diff for the parked
fx-rates consolidation: two (country, source) slices in `prices` carry
systematically corrupted price values. Both slices are now quarantined from
index construction and dashboard aggregates via `data_quality.QUARANTINED_SLICES`
(raw rows untouched in `prices`). Neither country is in the final 8-country
panel (US, UK, Singapore, Malaysia, India, Australia, Indonesia, Thailand),
so no paper result depends on either series.

| slice | rows | restaurants | years |
|---|---:|---:|---|
| United Arab Emirates / `wayback-deliveroo` (AED) | 9,243 | 112 | 2018–2026 |
| Vietnam / `wayback-grabfood` (VND) | 4,309 | 98 | 2019–2025 |

Both slices have `price_usd IS NULL` on 100% of rows — normal for wayback
ingests (price_usd is backfilled at load time), which is exactly why the
corruption reached the index: `index_builder.load_price_data` backfills
null `price_usd` through `FALLBACK_RATES` (VND=25,400, AED=3.67) and keeps
every row with `price_usd > 0`. The dashboard exporter's old private FX dict
lacked VND/AED, so dashboard aggregates had silently skipped these rows —
hiding the problem.

## Root cause 1 — United Arab Emirates / wayback-deliveroo

**Verdict: digit-fusion of Deliveroo's structured price object by the generic
JSON walker, affecting every snapshot from 2022-01 onward.**

- 2018–2021 snapshots (7,869 rows) use the old Deliveroo template with a typed
  `raw_price` float; `extract_deliveroo_body_json` parses them correctly and
  the stored AED values are plausible (deciles 1–79, median 25.2).
- From 2022-01, the Deliveroo AE template stores price as a structured object:
  `{"code":"AED","fractional":900,"formatted":"AED 9"}` and has no
  `raw_price`. The body-JSON extractor returns nothing, so `parse_deliveroo_uk`
  falls back to `extract_nextdata` → `_walk_ld`
  (`historical_html_scraper.py` ~line 140), which does
  `float(re.sub(r'[^\d.]', '', str(price_node)))` on the price **dict**.
  `str()` of the dict repr-escapes the non-breaking space as literal `\xa0`,
  so digit-stripping fuses: fractional minor-units (`900`) + the `0` from
  `\xa0` + the formatted major-units digits (`9`) → **90009** for an AED 9.00
  item. This produces the observed clusters (AED 5 → 50005, AED 2 → 20002,
  AED 3 → 30003, …).
- Verified live against Wayback snapshot `20220810164430` of
  `deliveroo.ae/menu/abu-dhabi/al-bahyah/india-palace-restaurant-shahama`:
  the archived page carries `"name":"Butter Roti" … "fractional":900,
  "formatted":"AED 9"`, and running the repo parser on that HTML reproduces
  `('Butter Roti', 90009.0)` — the exact DB row.
- Corruption census: 0 rows ≥ 1,000 in 2018–2021; **100%** of rows ≥ 1,000
  in every year from 2022 on (300/300 in 2022, …, 298/298 in 2026).

Backfilled through AED=3.67 the fused rows imply menu items up to $27,223
(slice mean $1,533/item), which drove the AE index from ~100-scale (2021-12:
86.5) to ~98,662 in 2022-01 and 5,775–156,099 thereafter.

**Recoverability (light, per owner deprioritization):** the 2018–2021 subset
(7,869 rows) appears valid as stored; the 2022+ fused values could in
principle be inverted (leading digits = `fractional`, i.e. price =
fractional/100) but this needs per-row validation — not attempted. A re-scrape
with a fixed parser is the cleaner path if AE ever re-enters the panel.

## Root cause 2 — Vietnam / wayback-grabfood

**Verdict: unconditional ÷100 of GrabFood's `priceInMinorUnit`, which for
Vietnam carries raw VND (no minor subunit) — every price is ~2 orders of
magnitude too small.**

- The `priceInMinorUnit` handler in `_walk_ld` (`historical_html_scraper.py`
  ~line 97, added 2026-06-18 for GrabFood MY/SG) computes
  `p = float(node['priceInMinorUnit']) / 100.0`. That is correct for MYR/SGD
  cents but wrong for VND, where GrabFood's `priceInMinorUnit` already holds
  the raw VND amount (see the existing CLAUDE.md currency gotcha).
- Verified live against Wayback snapshot `20240717135350` of the GrabFood VN
  page for "Cafe phin Phan Rang": the archived JSON has `"name":"Salt Coffee",
  "priceInMinorUnit":18000` (= 18,000 VND) → DB row 180.0; an unavailable
  placeholder item with `priceInMinorUnit":17` → the DB's "Salt Coffee
  0.17 VND" row.
- Distribution fits ÷100 exactly: wayback slice median 360 "VND" vs healthy
  live VN `grabfood` median 65,000 VND (2,000–850,000 range, price_usd
  populated). Not the dot-grouped-thousands ÷1000 error and not mislabeled
  USD — the ÷100 scale plus placeholder items explains the full 0.17–6,000
  range.

Backfilled through VND=25,400 the rows imply $0.0000–$0.24 menu items
(mean $0.019).

**Recoverability (light):** the transform is the obvious deterministic ×100
(placeholder rows like `priceInMinorUnit=17` remain junk and would need a
sanity floor). Not attempted — Vietnam is not in the final panel; a re-scrape
with a VND-aware parser is preferable if it ever is.

## Index contamination (quantified 2026-07-09)

Method: rebuilt `uifpi_index.csv` from the current DB twice — as-is vs. with
the two slices excluded — and diffed. Backfill mechanism confirmed:
`load_price_data` backfilled 55,971 null-price_usd rows in the as-is build,
of which 9,243 were AE/AED and 4,309 VN/VND (100% of both slices).

- **United Arab Emirates:** 57 index months (2018-07 → 2026-04), all from the
  quarantined slice. 2018-07 → 2021-12 look level-plausible (22–111) because
  the underlying rows are the healthy raw_price era; from 2022-01 the index
  explodes (98,662 in 2022-01; peak 156,099 in 2023-03; 12,045 in 2026-04).
  After quarantine the AE series is **empty** (no other AE source exists) and
  AE drops out of index/Granger/dashboard outputs.
- **Vietnam:** 21 index months before; **2 after** (2026-06, 2026-07 from live
  scrapes). 19 months of wayback-derived history (2019-12 → 2025-10) are lost
  — accepted, since every one of those months was built on ÷100-scaled prices.
- **VN 2026-06 = 25,455.82 is explained by the corrupt slice.** It was the
  crossover month where healthy live `grabfood` rows (correct USD) first
  chained onto the ÷100-scaled wayback level (2025-10: 213.0) — a ~×119 jump
  consistent with the ~×100 scale mismatch. In the quarantined build, 2026-06
  becomes the VN base month: formal_index = 100.0, combined = 100.0. (Its
  numeric resemblance to the 25,400 VND fallback rate is coincidental.)
- **Zero collateral:** all non-AE/VN rows of `uifpi_index.csv` are
  byte-identical between the two builds (196 rows, including all 36 US rows).
  The United States entries of `analysis_results/granger_results.json` and
  `country_summary.json` are unchanged from the committed state (n=31,
  F=6.0336, p=0.021 as recorded there — the deprecated in-script spec; the
  current headline is the calendar-true respec in
  `analysis_results/gap_robustness.json`), as are all other panel countries.

## Fix shipped

- `data_quality.py` — `QUARANTINED_SLICES = (("United Arab Emirates",
  "wayback-deliveroo"), ("Vietnam", "wayback-grabfood"))`.
- `index_builder.load_price_data` and `dashboard_data.load_price_counts` drop
  quarantined (country, source) rows right after their `EXCLUDED_SOURCES`
  handling, printing `Quarantined N rows: … (kept in raw DB)`.
- `granger_analysis.py` untouched (its per-source stratification deliberately
  bypasses exclusions).
- The defective parsers in `historical_html_scraper.py` are **not** fixed in
  this change: they are dead code for these slices until a re-scrape, and the
  fix belongs with whoever re-scrapes (Deliveroo AE needs a
  `price.fractional`-aware extractor; GrabFood needs a currency-conditional
  minor-unit divisor).

Future-proof check (unblocks the fx-rates blueprint): after the quarantine,
zero rows reaching `dashboard_data.load_price_counts` have
`price_usd IS NULL` with `currency IN ('VND','AED')` (138,785 rows reach it,
0 match).

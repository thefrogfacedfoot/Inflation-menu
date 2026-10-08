# Archival feasibility report: can the registered study be run on Wayback data?

**Status: draft, written 2026-10-08.** Counts only. No index value, relative, price, Granger statistic or p-value appears in this report or was viewed to write it. It reports data-count facts that §3 of `docs/preregistration.md` says are evaluated before any test is run.

Scope: the `wayback-*` rows of `uifpi.db` (426,882 rows with a positive price) under the V1 to V3 validation logic proposed in `docs/prereg_implementation_notes.md` §6 (PR #46). Live-scrape rows are not archival and are not counted here. Scripts and counts: branch `audit/wayback-feasibility` (`diagnostics/wayback_existing_feasibility.py`, `wayback_matching_check.py`, and their `*_counts.csv` files).

## 1. Finding

On the archival rows now in the database, **no country reaches n ≥ 36 under the registered chained rule, and none reaches n ≥ 100.** The best case is a single month (UK and US, 2025-07) with at least 15 contributing restaurants. The country count for the panel is therefore **N = 0**, below N_PANEL = 4.

This is a statement about the rows already stored. Whether the archive could supply more is a separate question, being tested by a CDX capture-count crawl (§6); this report is updated when that crawl answers.

## 2. What the registered rule requires

- §3: a country is in the confirmatory family only if it has n ≥ 36 calendar-true monthly observations, a verified monthly official series over that span, a reproducible index, and **at least 15 matched restaurants in every country-month** (same restaurant observed in months t and t−1; clarified in the implementation notes as at least 15 contributing restaurants, each with at least one item priced in both months).
- §4.5: a month below 15 is missing, never filled; a gap restarts the chain.
- D8: if N = 0, or the common calendar window is shorter than 36 months, "the panel cannot be run as registered. The run **stops and reports**; it does not shorten the threshold, drop countries post hoc, or substitute another test."

## 3. Results on existing archival rows

n is the number of months in the longest run of consecutive months. "Registered" requires at least 15 contributing restaurants in each month; "TPD-style" requires at least 15 restaurants observed in the month with no t−1 requirement and is shown for comparison only.

### 3.1 Name matching vs stable-ID matching

Name matching keys restaurants by `restaurant_name` and items by exact name. ID matching keys restaurants by a stable ID from the URL (Deliveroo slug, DoorDash store ID, GrabFood merchant ID, last path segment otherwise) and normalises item names (lowercase, punctuation and whitespace removed). For about a third of DoorDash rows (22,575 of 64,922) the URL carries no store identity, so the ID key falls back to the page-derived restaurant name.

| country | n (registered) | window | n (TPD-style) | window | peak contributing, name → ID | months with ≥ 15 contributing, name → ID |
|---|---|---|---|---|---|---|
| United Kingdom | 1 | 2025-07 | 11 | 2024-12 to 2025-10 | 23 → 23 | 1 → 1 |
| United States | 1 | 2025-07 | 5 | 2025-03 to 2025-07 | 20 → 20 | 1 → 1 |
| Malaysia | 0 | – | 4 | 2025-07 to 2025-10 | 8 → 10 | 0 → 0 |
| Vietnam | 0 | – | 1 | 2024-12 | 1 → 1 | 0 → 0 |
| United Arab Emirates | 0 | – | 0 | – | 2 → 2 | 0 → 0 |
| Australia | 0 | – | 0 | – | 0 → 0 | 0 → 0 |
| India | 0 | – | 0 | – | 1 → 1 | 0 → 0 |
| Indonesia | 0 | – | 0 | – | 0 → 0 | 0 → 0 |
| Singapore | 0 | – | 0 | – | 0 → 0 | 0 → 0 |
| Thailand | 0 | – | 0 | – | 0 → 0 | 0 → 0 |

Matching on stable IDs changes the peak only for Malaysia (8 → 10). **The shortfall is not a name-matching artifact.** With pure ID keying and no fallback, the US peak would fall from 20 to 3 because a third of DoorDash rows have no store ID in the URL; the fallback above is the version reported.

Countries reaching n ≥ 36: none (registered or TPD-style). Countries reaching n ≥ 100: none. N_PANEL = 4 is not met (N = 0).

### 3.2 Sources behind the longest runs

| country | source driving the runs | notes |
|---|---|---|
| United Kingdom | wayback-deliveroo (100% of contributing restaurant-months) | 65 months with data, 57 consecutive-month pairs, 14 months with ≥ 15 observed restaurants, 1 with ≥ 15 contributing |
| United States | wayback-doordash (100%) | 54 months with data, 36 consecutive pairs, 18 months with ≥ 15 observed, 1 with ≥ 15 contributing |
| Malaysia | wayback-grabfood | 31 months with data, 10 with ≥ 15 observed (peak 100 observed), 0 with ≥ 15 contributing |
| Vietnam | wayback-grabfood | 19 months with data, 1 with ≥ 15 observed |
| Singapore, Australia, Indonesia, Thailand, India, UAE | wayback-grabfood, menulog, zomato, TripAdvisor/wongnai, deliveroo | at most 3 to 8 restaurants observed in any month |

(Month counts are from the name-matched run; the ID-matched run gives the same ordering.)

### 3.3 Event-study coverage

**DoorDash, US (ID key).** California and non-California restaurants cannot be separated: the database has no state or address field, and the URL carries only the store ID. A state split needs a fetch of each store page. Counts for all states: distinct stores observed per month were 23, 25, 28 in 2023-01 to 2023-03, 95 in 2023-06, 149 in 2023-09, 96 in 2023-12, 36 in 2024-02 and 29 in 2024-03. **There are no DoorDash rows between 2024-04 and 2024-11** (raw rows: 2024-01 148, 2024-02 2,235, 2024-03 1,802, then 2024-12 277). Stores observed in 2023-10 to 2024-03: 189; in 2024-04 to 2024-09: 0; in both windows: 0. A name match against about 60 known fast-food brands flags 4 to 56 stores in the high months (for example 56 of 149 in 2023-09); stores with numeric-only names cannot be flagged.

**Deliveroo, UK, 2019-06 to 2022-12 (slug key).** Distinct restaurants per month are 0 to 10 for most months, with peaks of 39 in 2021-10 and 17 in 2022-07. Restaurants observed on both sides of each event (three calendar months either side):

| event date | before | after | both sides | both sides with ≥ 1 common normalised item |
|---|---|---|---|---|
| 2020-07-15 | 0 | 8 | 0 | 0 |
| 2021-10-01 | 21 | 45 | 1 | 1 |
| 2022-04-01 | 1 | 6 | 0 | 0 |

These are restaurants with at least one valid item price after V1 and V2, not raw capture counts.

## 4. Binding constraint

The constraint is **the number of restaurants matched across consecutive calendar months, not the number of months with data.** The UK has data in 65 months and 57 consecutive-month pairs, yet only one month has 15 or more contributing restaurants. Snapshots are sparse and uneven: a restaurant is captured in one month and not the next, and V2 and V3 remove few rows (V2 removed 13,733 item-date cells, V3 35 of 25,761 relatives, in the ID-matched run). Where more than 15 restaurants are observed in a month (UK 240, US 153, Malaysia 100 at peak), the consecutive-month overlap is small, so the contributing count stays below 15.

## 5. Implication for the registered study

If the archive cannot supply more than the rows stored, then under §3 and D8: no country enters the family, N = 0, and the run **stops and reports**. The threshold is not shortened, no country is dropped or added after the fact, and no substitute test is run. The report that results is this one. Country-level tests on a country's own window are secondary and require that window to meet the same inclusion rule, so none exists.

What this report does not claim: it does not say the archive holds no further data (§6), and it says nothing about live-scrape data, which are not archival and are not covered by the registered archival family.

## 6. Open question and update rule

A CDX crawl (single-threaded, 3 to 5 seconds between requests, deadline 2026-10-09 20:00 SGT) is scoped to one question: **does any source have at least 15 restaurants captured in each of at least 36 consecutive months, for any country?** It counts distinct captured URLs per pattern-month, an upper bound, since captured URLs may not parse and may not match across months. A "no" confirms §1 for the archive as a whole. A "yes" is necessary, not sufficient, and names the candidate source and window to backfill. If the crawl is incomplete at the deadline, the result is "blocked on archive availability" with the checkpoint state, and no partial counts are reported as results. This report is amended with the outcome.

## 7. Limitations

- Restaurant identity in the name-matched run is the exact `restaurant_name` string; the ID-matched run corrects name variants but uses the page-derived name where a URL has no ID.
- V1 to V3 are proposed in PR #46 and not yet registered; the counts use them as written there. Without V2 the counts could only be higher in observed restaurants, not in matched ones that survive V3.
- "Registered currency" is the most common currency among a country's live rows; wayback rows in another currency would be dropped (none were: V1 removed no wayback row).
- Known parser-garbage slices (for example some UAE and Vietnam wayback rows) are not removed here beyond V1 to V3.

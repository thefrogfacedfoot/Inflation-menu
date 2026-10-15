# Data provenance

Scope of this version: **archival (Wayback Machine) price data**, and the one fact about live-scrape data that is needed to read it. The official datasets used by prereg v2 (ONS, SingStat, IRAS) and v1 (official CPI) are not covered yet.

## The two date columns

`prices.collection_date` means different things for different sources.

- **Archival rows** (`source` starting `wayback`, case-insensitive):
  - `collection_date` is the **Wayback snapshot date**, the date the Internet Archive captured the page. It is **not** the date this project retrieved it. A row with `collection_date = 2018-07-21` was retrieved in June 2026.
  - `prices.retrieved_at` holds the retrieval date. This column was added on 2026-10-15 and is reconstructed (see below); `retrieved_at_basis` is `reconstructed_id_bracket` on every such row.
- **Live-scrape rows** (`direct`, `grabfood`, `js`, `foodpanda`):
  - `collection_date` **is** the retrieval date: the local (SGT) date when the scrape run started.
  - `retrieved_at` is NULL on these rows.
- `official_price_series_bls_apu`: `collection_date` is the reference month of the BLS series. Not covered here.

All archival pages were fetched through the raw-bytes endpoint, `https://web.archive.org/web/<timestamp>id_/<original URL>`. The `url` column holds the original or archived URL.

## How the retrieval dates were reconstructed

Nothing in the database recorded the retrieval date at insert time. Three pieces of evidence give it back.

1. **Row ids (row-level).**
   - `prices.id` is `INTEGER PRIMARY KEY AUTOINCREMENT`, so ids follow insertion order.
   - Live-scrape rows carry their true scrape date. Across all 611,963 live rows, the date never decreases as the id increases.
   - So for each archival row: *retrieved on or after* = the scrape date of the nearest live row below its id, and *retrieved on or before* = the scrape date of the nearest live row above it.
   - `retrieved_at` stores the **on-or-before** bound.
   - Script: `diagnostics/provenance/reconstruct_retrieval_dates.py`.
   - Per-bracket output: `docs/data_provenance_retrieval_brackets.csv`.
2. **DB backups (consistency check).** There are 22 dated `uifpi.db.backup_*` files in the repo root. These files are not tracked in git; they live only in WC's working copy. For each backup, the largest archival id it contains has a reconstructed lower bound on or before the date in its filename. The next archival id in the current DB has an upper bound on or after that date. **All 22 pass.**
3. **Sweep logs and commits (corroboration, per sweep).** These are listed in the table below.
   - The logs are gitignored since `c0bad78` (2026-06-22) and exist only in WC's working copy. File modification times are given as "mtime".
   - Commit times come from `git log` and are in SGT.

**Limits.**
- The brackets cover rows **still in the current DB**. Rows inserted and later deleted (deduplication on 07-31, the zero-price delete on 06-19, quarantines) are not dated here.
- Later UPDATEs do not change a row's retrieval date. These include the name backfills on 08-01 and 08-02, the mojibake fix on 08-02, and the label renames.
- No archival row in the current DB was inserted after 2026-08-07. The largest archival id (1,231,999) is the same in the 2026-10-08 backup and in the current DB.

## Retrieval by platform and sweep

"Rows" counts rows in the DB on 2026-10-15. The "retrieved" dates are the id bracket, giving the earliest and latest possible date.

| # | Retrieved (on/after .. on/before) | Platform, country | Rows | Snapshot dates covered | Evidence |
|---|---|---|---|---|---|
| S0 | 2026-06-12 .. 06-13 | generic `wayback` (US 9, AU 6, UK 4, MY 2, ID 1); TH `Wayback/TripAdvisor` 10, `Wayback/wongnai` 1 | 33 | 2019-07 .. 2023-05; TH rows dated 2026-06-13 | Commit `662999e` 2026-06-13 12:24, "Expand UIFPI index: +67 historical prices via Wayback Machine" |
| S1 | 2026-06-16 | generic `wayback` (US 25, MY 12, UK 4, ID 4, AU 3) | 48 | 2018-04 .. 2025-11 | Commit `cc36b51` 2026-06-16 19:35, "Time-distributed Wayback rescrape" |
| S2 | 2026-06-16 .. 06-17 | `wayback-menupages` US 8,282; `wayback-zomato` IN 635, ID 29; `wayback-grabfood` SG 842 | 9,788 | 2018-01 .. 2026-05 | Commits `a6f7245` 06-16 20:26 and `2a6220a` 06-17 08:52 (Zomato extractor). Backup `pre_tier_purge_20260617_204040` holds max archival id 25,307, the last SG GrabFood row |
| S3 | 2026-06-18 .. 06-19 | `wayback-menulog` AU 1,652; `wayback-deliveroo` UK 12,098; `wayback-grabfood` MY 7,504 | 21,254 | 2021-05 .. 2026-05 | `au_resweep_run.log` mtime 06-18 13:22 with commit `89de391` 06-18 13:27 (AU Menulog). `uk_sweep_run2.log` mtime 06-18 14:27 with commit `79d97e3` 06-18 14:29 (Deliveroo UK). `my_sweep_run.log` mtime 06-19 08:49 with commit `e0194a5` 06-19 09:06 (MY GrabFood). Backup `pre_my_zero_delete_20260619_085250` |
| S4 | 2026-06-19 .. 06-20 | `wayback-deliveroo` UAE 9,243; `wayback-grabfood` VN 4,309 (both quarantined from the index) | 13,552 | 2018-07 .. 2026-04 | `ae_sweep_run.log` mtime 06-19 22:23; commit `b398941` 06-19 22:34 "save VN sweep progress (240/345 done)"; `vn_sweep_run.log` mtime 06-20 07:44. Backup `post_ae_vn_partial_20260619` |
| S5 | 2026-06-21 .. 06-22 | `wayback-doordash` US 7,412 (excluded from the index) | 7,412 | 2023-01 .. 2026-03 | `us_doordash_sweep.log` mtime 06-22 11:54; commit `c0bad78` 06-22 14:22 "Record DoorDash US sweep completion". Backup `pre_doordash_index_20260622_120809` holds max id 534,215 |
| S6 | 2026-07-26 .. 07-27 | `wayback-deliveroo` UK 267,998; `wayback-grabfood` MY 10,415 | 278,413 | 2019-09 .. 2026-05 | Backup `pre_sweep_expansion_20260726_190653` (taken before; its max archival id is still 534,215). `sweep_grabfood_my_output.log` mtime 07-27 00:37; `sweep_deliveroo_uk_output.log` 07-27 09:02 and `…output2.log` 07-27 11:33; commit `27ff026` 07-27 11:57 "expand and fix wayback sweeps" |
| S7 | 2026-07-30 .. 07-31 | `wayback-doordash` US 11,186 | 11,186 | 2023-01 .. 2026-03 | `sweep_doordash_us_2023_test_v2.log` mtime 07-31 11:02; `sweep_doordash_us_2023_full.log` mtime 07-31 18:39 ("Rows inserted: 10709"). Backup `pre_doordash_dedup_20260731_185830` holds max id 1,129,358 |
| S8 | 2026-08-01 .. 08-03 | `wayback-doordash` US 46,094; `wayback-grabfood` MY 22,108; `wayback-deliveroo` UK 5,673 | 73,875 | 2019-08 .. 2026-03 | Backups `pre_deliveroo_uk_continue_20260801_230533` and `pre_doordash_us_continue_20260801_230623` (taken before; max 1,129,358); `pre_doordash_us_name_backfill_20260801_233842` (max 1,135,896); `pre_*_20260802_13xxxx` (max 1,140,164). Commit `e481bc8` 08-02 23:34 "save GrabFood MY / DoorDash US 2023+ sweep progress" |
| S9 | 2026-08-06 .. 08-07 | `wayback-deliveroo` UK 11,091; `wayback-doordash` US 230 | 11,321 | 2021-05 .. 2026-03 | `doordash_us_2023_continue_20260807.log` and `my_grabfood_resume_20260807.log` (mtime 08-13 12:34); `uk_sweep_run_20260807.log` (empty, mtime 08-07 09:10); commit `a9f6e2b` 08-07 14:14 "Resume Wayback expansion: MY GrabFood 34/380, DoorDash US in progress, UK Deliveroo hang confirmed". No MY GrabFood rows from this resume are in the current DB |

The total is 426,882 archival rows. Every one was retrieved between **2026-06-12 and 2026-08-07**.

## Reproduce or refresh

```
python3 diagnostics/provenance/reconstruct_retrieval_dates.py            # read-only: brackets + backup check
python3 diagnostics/provenance/reconstruct_retrieval_dates.py --write    # backs up uifpi.db, then (re)populates retrieved_at
```

`--write` refuses to run while `live_scraper.py` is running. On 2026-10-15 it was run once, after a backup to `uifpi.db.backup_pre_retrieved_at_20261015_210351`.

No current insert path sets `retrieved_at`. Archival rows added by a future sweep would have NULL until the script is rerun, and their dates would then also be reconstructed, not recorded.

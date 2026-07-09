# UIFPI ingest log

Append-only audit trail. Each `## YYYY-MM-DD HH:MM` section is
one monthly_ingest.py run; per-country deltas, Granger crossover
events, and skipped stages are recorded for the SSEF paper.


## 2026-06-18 13:38
**Mode**: DRY-RUN — no stages were executed.

| Country | Items before | Items after | Δ | Months before | Months after |
|---|---:|---:|---:|---:|---:|
| Singapore | 9557 | 9557 | 0 | 9 | 9 |
| Malaysia | 3505 | 3505 | 0 | 7 | 7 |
| Indonesia | 34 | 34 | 0 | 21 | 21 |
| Thailand | 11 | 11 | 0 | 1 | 1 |
| India | 635 | 635 | 0 | 49 | 49 |
| United States | 8319 | 8319 | 0 | 35 | 35 |
| United Kingdom | 1526 | 1526 | 0 | 6 | 6 |
| Australia | 1831 | 1831 | 0 | 24 | 24 |

## 2026-07-01 06:16
**INVALID RUN** — the GitHub Actions runner had no `uifpi.db` (the file is gitignored and never present on runners); the all-zero rows and the "United States dropped below Granger threshold" event below are artifacts of running against an empty database. See CHANGELOG 2026-07-08.
**Mode**: DRY-RUN — no stages were executed.
**Skipped stages**: live_scraper

| Country | Items before | Items after | Δ | Months before | Months after |
|---|---:|---:|---:|---:|---:|
| Singapore | 0 | 0 | 0 | 0 | 0 |
| Malaysia | 0 | 0 | 0 | 0 | 0 |
| Indonesia | 0 | 0 | 0 | 0 | 0 |
| Thailand | 0 | 0 | 0 | 0 | 0 |
| India | 0 | 0 | 0 | 0 | 0 |
| United States | 0 | 0 | 0 | 0 | 0 |
| United Kingdom | 0 | 0 | 0 | 0 | 0 |
| Australia | 0 | 0 | 0 | 0 | 0 |

## 2026-07-01 06:16
**INVALID RUN** — the GitHub Actions runner had no `uifpi.db` (the file is gitignored and never present on runners); the all-zero rows and the "United States dropped below Granger threshold" event below are artifacts of running against an empty database. See CHANGELOG 2026-07-08.
**Skipped stages**: live_scraper

| Country | Items before | Items after | Δ | Months before | Months after |
|---|---:|---:|---:|---:|---:|
| Singapore | 0 | 0 | 0 | 0 | 0 |
| Malaysia | 0 | 0 | 0 | 0 | 0 |
| Indonesia | 0 | 0 | 0 | 0 | 0 |
| Thailand | 0 | 0 | 0 | 0 | 0 |
| India | 0 | 0 | 0 | 0 | 0 |
| United States | 0 | 0 | 0 | 0 | 0 |
| United Kingdom | 0 | 0 | 0 | 0 | 0 |
| Australia | 0 | 0 | 0 | 0 | 0 |

**Granger crossover events**:
  - **United States** dropped below Granger threshold

## 2026-07-08 22:53
**Mode**: DRY-RUN — no stages were executed.
**Skipped stages**: live_scraper

| Country | Items before | Items after | Δ | Months before | Months after |
|---|---:|---:|---:|---:|---:|
| Singapore | 29366 | 29366 | 0 | 10 | 10 |
| Malaysia | 19508 | 19508 | 0 | 33 | 33 |
| Indonesia | 34 | 34 | 0 | 21 | 21 |
| Thailand | 11 | 11 | 0 | 1 | 1 |
| India | 635 | 635 | 0 | 49 | 49 |
| United States | 54162 | 54162 | 0 | 559 | 559 |
| United Kingdom | 37744 | 37744 | 0 | 21 | 21 |
| Australia | 2700 | 2700 | 0 | 25 | 25 |

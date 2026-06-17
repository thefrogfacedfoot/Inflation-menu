# Track B / Track C — Phase 0 probe findings

**Date**: 2026-06-17
**Inputs**: `coverage_report_br_de_za.md`, `coverage_report_track_b.md`

## TL;DR

| Track | Country | Best source | Sample $-hits | Verdict |
|---|---|---|---:|---|
| C | Brazil | **Uber Eats BR** | 218 BRL | ✓ queue (largest single-page yield in this round) |
| C | Brazil | iFood RJ (alt) | 5 BRL | ✓ keep as fallback (LD + ND) |
| C | Germany | **Lieferando** | 102 EUR | ✓ queue |
| C | Germany | Wolt DE (alt) | 50 EUR | ✓ keep as fallback |
| C | South Africa | **TripAdvisor ZA** | 16 ZAR | ✓ queue |
| C | South Africa | Uber Eats ZA (alt) | 6 ZAR | ✓ keep as fallback |
| B | Australia | **Menulog revisit** | 48 AUD | ✓ extend (existing 12% yield is parser undercount, not source limit) |
| B | Indonesia | GoFood | 0 IDR | ✗ bail — pure JS shell, no prices in static HTML |
| B | Thailand | GrabFood TH | 4 THB | ✗ bail — captcha-blocked on Wayback playback |

**Three new countries (BR/DE/ZA) join the formal-sector roster pipeline.** Both ID GoFood and TH GrabFood are dead ends as far as Wayback is concerned. ID and TH formal coverage stays where it was — Zomato cost-for-two for ID, the single-snapshot Wayback TripAdvisor/Wongnai sweep for TH.

## Track C — BR / DE / ZA detail

### Brazil

- **Uber Eats BR** (`ubereats.com/br/*`) — 4,590 ≥2-cap restaurants, sample 218 BRL hits in 776 KB, JSON-LD present, no NEXT_DATA. Decisive winner.
- **iFood RJ** (`ifood.com.br/delivery/rio-de-janeiro-rj/*`) — 3,760 ≥2-cap, 5 BRL hits, LD + ND. Cleanest archived sample of any iFood URL; SP and the global `rappi.com.br/restaurantes/*` both returned HTTP 503 on Wayback playback.
- TripAdvisor BR has 2,860 ≥2-cap restaurants but the sampled page had **0 BRL hits** in 1,320 KB — same JS-shell pattern as the original Mexico TripAdvisor MX probe.

### Germany

- **Lieferando** (`lieferando.de/speisekarte/*`) — 6,464 ≥2-cap, 102 EUR hits in a 617 KB page, LD + ND. Strongest single signal in this whole probe round.
- **Wolt DE** (`wolt.com/de/deu/*`) — 4,358 ≥2-cap, 50 EUR hits, LD only. Solid fallback; Wolt entered DE around late 2020, so it's a shorter window.
- Yelp DE: 5,536 ≥2-cap but 0 EUR hits — JS shell.
- TripAdvisor DE + Uber Eats DE: HTTP 503 on Wayback playback.

### South Africa

- **TripAdvisor ZA** (`tripadvisor.co.za/Restaurant_Review*`) — 2,744 ≥2-cap, 16 ZAR hits in 1,229 KB, JSON-LD. Note: "ZAR hits" here uses `\bR\s?\d+(?:[.,]\d{2})?` which has potential overlap with random capital-R tokens; need to validate in the actual parser.
- **Uber Eats ZA** (`ubereats.com/za/*`) — 1,845 ≥2-cap, 6 ZAR hits, LD only.
- Mr D Food (`mrdfood.com/*`) — 5,966 ≥2-cap but HTTP 503 on sample fetch. Probably blocks Wayback by user-agent or referrer.
- EatOut ZA returned 0 rows.

## Track B detail

### Australia — Menulog revisit

The existing `wayback-menulog` source has 15 rows in `prices` from 128 fetched snapshots — a 12% parser yield that prior docs (`data_gaps.md`) noted as the source's apparent ceiling. The revisit probe sample shows **48 AUD hits in 851 KB** with both JSON-LD and NEXT_DATA present, which means the parser is leaving the majority of menu items on the table, not that the source is thin.

Recommended next pass:
1. Inspect 5 actual Menulog NEXT_DATA blobs to confirm where the prices sit (the existing `extract_nextdata` walks generically but probably hits a non-MenuItem path).
2. Re-run `historical_html_scraper.py 'Australia: menulog' --per-period 15` after clearing the AU Menulog entry from `historical_html_progress.json` so the sweep widens beyond the 128-snapshot cache.

Not run in this session because a full sweep with `per_period=15` is on the order of 30+ minutes of Wayback calls.

### Indonesia — GoFood

- `gofood.co.id/*` — 4,901 ≥2-cap, 1,024 KB sample, **0 IDR hits**. LD + ND both present, but the JSON blobs contain restaurant metadata only (the actual menu items hydrate via XHR after page render). Both `gofood.co.id/jakarta/*` (more targeted) and `gojek.com/*/food/*` (alternative URL convention) returned the same shape — JS shell, prices not in static HTML.
- ID formal coverage stays at the Zomato cost-for-two restaurant-aggregate signal (29 obs across 21 months).

### Thailand — GrabFood

- Both `food.grab.com/th/en/*` and `food.grab.com/th/th/*` returned **captcha pages** on Wayback playback — the 4 THB hits found by regex were inside the captcha challenge HTML, not menu data. Grab actively blocks archive crawlers.
- LineMan TH (`lineman.co.th/*`) had **0 archived URLs** matching this pattern at all.
- TH formal coverage stays at the single 2026-06-13 Wayback TripAdvisor/Wongnai THB-regex sweep (11 items, 9 restaurants).

## Implications

1. **Roster expands from 8 → 11 countries**: US, SG, MY, UK, IN, AU, TH, ID, plus **BR, DE, ZA**. Mexico stays proxy-only (no archival source clears threshold; nothing in this probe round changed that).
2. **The dashboard's `COUNTRIES` constant should expand to 11** after the first BR / DE / ZA scrape sweeps actually produce rows. Until then, BR / DE / ZA could optionally be added as proxy-only tiles (Numbeo + Big Mac + WB CPI), same template as Mexico.
3. **`historical_html_scraper.py` gains three targets**: BR Uber Eats, DE Lieferando, ZA TripAdvisor (with the existing TripAdvisor parser). Each needs a smoke-test of 10–20 snapshots before a full sweep.
4. **`floor_datasets.py` ROSTER must add BR / DE / ZA** so Numbeo + Big Mac + WB CPI data is loaded — currently the ROSTER stops at the 8 + VN panel.

## Known issue: probe roll-up logic

Both probe scripts pick the "best platform" via `(n_restaurants_ge2, sample_price_hits or 0)` tuple comparison. When the sample fetch fails (HTTP 503), `sample_price_hits` is `''`, which `or 0`-coalesces to 0 and the largest-but-blocked source wins the tuple. The BR table in `coverage_report_br_de_za.md` therefore shows "Rappi BR — best platform" even though Rappi's sample fetch failed and a working Uber Eats BR sample returned 218 hits. The matrix itself is correct; only the roll-up section is misleading. Fix queued: skip rows where `sample_status` starts with `error:` before ranking.

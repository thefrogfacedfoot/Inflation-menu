# UIFPI — Final country roster (Phase 1 deliverable)

**Generated**: 2026-06-17

## Roster decision per country

The thesis target was an 8-country panel for formal-vs-informal price pass-through. Every country listed below clears the formal-sector threshold (≥15 archived restaurants with ≥2 captures inside the 2018-01 → 2026-06 window). Vietnam is included as a floor-only proxy per the agreed methodology.

| Country | Formal source | Item-level? | Rows | Restaurants | Months | Floor (Numbeo + Big Mac + WB CPI) | Verdict |
|---|---|---|---:|---:|---:|:---:|:---:|
| United States | MenuPages (Wayback) + TripAdvisor | item-level | 8,594 | 265 | 76 | ✓ | ✓ keep |
| Singapore | GrabFood (live + Wayback) + TripAdvisor | item-level | 7,807 | 70 | 19 | ✓ | ✓ keep |
| Malaysia | foodpanda/GrabFood (live) + TripAdvisor | item-level | 2,660 | 163 | 71 | ✓ | ✓ keep |
| United Kingdom | Deliveroo (live) + TripAdvisor + direct chain | item-level | 1,067 | 247 | 78 | ✓ | ✓ keep |
| India | Zomato cost-for-two (Wayback) + TripAdvisor | restaurant-aggregate | 872 | 237 | 79 | ✓ | ✓ keep |
| Australia | direct chains (live) + Menulog (Wayback) + TripAdvisor | item-level (sparse) | 331 | 180 | 59 | ✓ | ✓ keep |
| Thailand | TripAdvisor priceRange tiers + live (one-day) | tier-only | 290 | 226 | 79 | ✓ | ✓ keep (formal weak, floor strong) |
| Indonesia | Zomato cost-for-two (Wayback) + TripAdvisor | restaurant-aggregate | 152 | 130 | 57 | ✓ | ✓ keep |
| Vietnam | — (no extractable archival source) | — | 0 | — | — | ✓ | ✓ keep as **proxy-only** |

**Final 8-country formal roster**: US, SG, MY, UK, IN, AU, TH, ID.
**9th country (proxy-only)**: Vietnam — Numbeo / Big Mac / World Bank CPI panels only, flagged in `data_gaps.md`.

## Why each country qualifies

Each country is judged against three filters:
1. **Formal restaurants ≥ 15** with ≥2 in-window captures — Phase 0 coverage matrix.
2. **Extractable prices** in the archived HTML — Phase 1c parser validation.
3. **Always-on floor datasets** (Numbeo restaurant rankings, Big Mac index, World Bank CPI) loaded so cross-country comparison is still possible when archival sources are thin.

- **US**: MenuPages has 2,866 Wayback restaurants with full Schema.org Menu / MenuSection / MenuItem markup pre-2019. The collection sampled 77 distinct restaurants and extracted 8,282 item-level prices spanning 29 months. Strongest item-level coverage in the panel.
- **SG**: archived GrabFood pages serve NEXT_DATA with menu items; 842 item-level rows from 12 archived restaurants supplement the 6,965 live foodpanda + GrabFood rows already in DB.
- **MY**: covered entirely by the existing live foodpanda + GrabFood pipeline; 2,499 rows pre-Phase 1, no Wayback addition needed.
- **UK**: covered by Deliveroo (live) + 3 direct chains + 45 TripAdvisor wayback rows. Adequate breadth.
- **IN**: Zomato pre-2020 archived pages don't expose item-level prices but do expose "cost for two" as a restaurant-level average meal price. Extracted 635 restaurant-level data points spanning 79 months across NCR — methodologically a restaurant-aggregate inflation signal, not item-level.
- **AU**: covered by live direct chains (Oporto, Nando's) + 158 historical TripAdvisor rows + 15 from Menulog NEXT_DATA. Menulog yield was marginal (10/104 fetches) but counts.
- **TH**: TripAdvisor wayback gives priceRange tier markers (1–4 ordinals); Eatigo archival sources had no extractable prices. Formal sector is weak — paper uses TH primarily via floor datasets + the one-day 2026-06-13 live snapshot.
- **ID**: Zomato Jakarta cost-for-two extracted 29 restaurant-level data points; floor datasets fill the panel.
- **VN**: no extractable archival source confirmed. foody.vn URLs returned 0-byte Wayback playbacks; TripAdvisor HCMC/Hanoi pages have 0 VND tokens in static HTML. Vietnam is kept as a **proxy-only** country: cross-country comparison via Numbeo Restaurants Price Index + Big Mac Index + World Bank CPI, with no item-level UIFPI computed.

## What changed from the Phase 0 matrix

Phase 0 winners that delivered as expected:
- ✓ MenuPages (US) — JSON-LD Menu pipeline cleanest in the panel.
- ✓ GrabFood SG — NEXT_DATA archived works.
- ✓ Zomato NCR + Jakarta — yielded cost_for_two via dedicated extractor (not the item-level JSON-LD I had originally guessed).

Phase 0 winners that under-delivered after parser validation:
- ⚠ Menulog AU — NEXT_DATA mostly restaurant-level metadata, not item prices. 15 rows / 1 restaurant.
- ✗ Eatigo TH — JSON-LD didn't carry prices; URLs at the pattern level are mostly categories. 0 rows.
- ✗ Zomato Manila PH — same regex but PHP-marker variant didn't match the pages' actual cost-for-two phrasing. 0 rows.
- ✗ TripAdvisor MX — exposes only priceRange tier markers, which the parser correctly skips. 0 rows.

Outcome: 4 of 8 platforms gave high-quality item or restaurant-aggregate prices; 4 yielded little or nothing. Coverage gaps are documented in `data_gaps.md`.

## Cron / forward collection

The existing live scraper (`live_scraper.py`) continues running:
- Daily at 21:00 (`0 21 * * *`)
- Monthly on the 1st at 10:00 (`0 10 1 * *`)

That will keep adding rows for SG, MY, UK, AU each day, providing the going-forward monthly series for the index and Granger analysis. The Wayback pipeline is the historical backfill; live is the going-forward.

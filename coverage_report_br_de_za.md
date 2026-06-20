# Phase 0 — BR / DE / ZA candidate-country probe

Generated: 2026-06-17T21:21:32.523805
  
Window: 20180101 → 20260601
  
CDX limit per query: 30,000 (rows ≥ limit = truncated).

Same yields-table format as `coverage_report.md`. Each row probes one (country, platform) pair: counts distinct archived URLs and snapshots in-window, then fetches one sample archived page (id_ raw, no Wayback toolbar) and counts currency-shaped price tokens in the static HTML.

## Matrix

| Country | Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Notes |
|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|
| Brazil | tripadvisor BR | `tripadvisor.com.br/Restaurant_Review*` | 2,860 | 30,000 | 20180101–20260311 | 1320 | 0 | Y | N | truncated |
| Brazil | ifood SP | `ifood.com.br/delivery/sao-paulo-sp/*` | 4,853 | 30,000 | 20180815–20260526 |  |  |  |  | truncated; sample error:HTTP 503 |
| Brazil | ifood RJ | `ifood.com.br/delivery/rio-de-janeiro-rj/*` | 3,760 | 27,556 | 20180815–20260524 | 43 | 5 | Y | Y | ok |
| Brazil | rappi BR | `rappi.com.br/restaurantes/*` | 4,885 | 30,000 | 20180829–20260520 |  |  |  |  | truncated; sample error:HTTP 503 |
| Brazil | ubereats BR | `ubereats.com/br/*` | 4,590 | 30,000 | 20200312–20260531 | 776 | 218 | Y | N | truncated |
| Germany | tripadvisor DE | `tripadvisor.de/Restaurant_Review*` | 2,972 | 30,000 | 20180103–20260513 |  |  |  |  | truncated; sample error:HTTP 503 |
| Germany | lieferando | `lieferando.de/speisekarte/*` | 6,464 | 30,000 | 20210202–20260531 | 617 | 102 | Y | Y | truncated |
| Germany | wolt DE | `wolt.com/de/deu/*` | 4,358 | 30,000 | 20200924–20260530 | 920 | 50 | Y | N | truncated |
| Germany | ubereats DE | `ubereats.com/de/*` | 2,588 | 30,000 | 20180121–20260531 |  |  |  |  | truncated; sample error:HTTP 503 |
| Germany | yelp DE | `yelp.de/biz/*` | 5,536 | 30,000 | 20180101–20251129 | 372 | 0 | Y | N | truncated |
| South Africa | tripadvisor ZA | `tripadvisor.co.za/Restaurant_Review*` | 2,744 | 30,000 | 20180101–20260310 | 1229 | 16 | Y | N | truncated |
| South Africa | mrdfood | `mrdfood.com/*` | 5,966 | 30,000 | 20180224–20251212 |  |  |  |  | truncated; sample error:HTTP 503 |
| South Africa | ubereats ZA | `ubereats.com/za/*` | 1,845 | 13,850 | 20200415–20260529 | 742 | 6 | Y | N | ok |
| South Africa | eatout ZA | `eatout.co.za/listings/*` | 0 | 0 | — |  |  |  |  | empty |

## Country roll-up (best platform per country)

> The original auto-generated roll-up below picks the largest-by-CDX source,
> but `Brazil — rappi BR` and `South Africa — mrdfood` both had their sample
> fetch fail (HTTP 503) and therefore returned no signal. The probe script
> ranked them above working samples because it coalesces failed `$-hits` to
> 0 — see `docs/track_b_c_findings_2026-06-17.md` for the corrected reading.
> The script logic is fixed for future runs (`sample_status` starts with
> `error:` is now filtered before ranking).

### Corrected roll-up (failed samples excluded)

| Country | Best platform | ≥2-cap restaurants | Sample $-hits | Clears formal threshold (≥15 + prices visible)? |
|---|---|---:|---:|---|
| Brazil | **ubereats BR** | 4,590 | 218 | ✓ |
| Germany | **lieferando** | 6,464 | 102 | ✓ |
| South Africa | **tripadvisor ZA** | 2,744 | 16 | ✓ |

### Original auto-generated roll-up (biased by 503 failures)

| Country | Best platform | ≥2-cap restaurants | Sample $-hits | Clears formal threshold (≥15 + prices visible)? |
|---|---|---:|---:|---|
| Brazil | rappi BR | 4,885 |  | ✗ |
| Germany | lieferando | 6,464 | 102 | ✓ |
| South Africa | mrdfood | 5,966 |  | ✗ |

## Reading the matrix

- `≥2-cap restaurants` = distinct archived URLs with two or more captures inside the window. Gating metric for the formal-sector roster (≥15 required).
- `Sample $-hits` = currency-token count in ONE randomly-chosen archived page. Low or zero hits ⇒ HTML doesn't contain prices (JS shell that loaded prices via API after render).
- `LD` / `ND` = JSON-LD or `__NEXT_DATA__` present; either gives a clean structured-data path.
- A country clears the formal threshold only when BOTH ≥2-cap ≥ 15 **and** sample $-hits ≥ 5.

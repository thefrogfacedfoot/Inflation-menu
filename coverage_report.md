# Phase 0 — Wayback CDX coverage matrix

Generated: 2026-06-16T21:45:02.495539
  
Window: 20180101 → 20260601
  
CDX limit per query: 30,000 (rows ≥ limit = truncated).

Each row probes one (country, platform) pair: counts distinct
archived URLs and snapshots in-window, then fetches one sample
archived page (id_ raw, no Wayback toolbar) and counts currency-
shaped price tokens in the static HTML — i.e., the data we'd
actually be able to extract without re-running JavaScript.

## Matrix

| Country | Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Notes |
|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|
| United States | allmenus.com | `allmenus.com/*` | 7,021 | 30,000 | 20180224–20260521 | 14 | 0 | Y | N | truncated |
| United States | menupages.com | `menupages.com/*` | 2,866 | 30,000 | 20180104–20260521 | 269 | 34 | Y | N | truncated |
| United States | yelp.com/biz NYC | `yelp.com/biz/*new-york*` | 0 | 0 | — |  |  |  |  | empty |
| United States | yelp.com/menu | `yelp.com/menu/*` | 0 | 0 | — |  |  |  |  | error:HTTP 504 |
| India | zomato Mumbai | `zomato.com/mumbai/*` | 0 | 0 | — |  |  |  |  | error:Expecting value: line 6146 column 1 (char 542305) |
| India | zomato NCR | `zomato.com/ncr/*` | 1,355 | 12,359 | 20180104–20260519 | 283 | 43 | Y | N | ok |
| India | swiggy Mumbai | `swiggy.com/mumbai/*` | 1 | 14 | 20180129–20211023 | 154 | 51 | N | N | ok |
| India | swiggy Bangalore | `swiggy.com/bangalore/*` | 3 | 44 | 20180125–20211023 | 117 | 4 | Y | N | ok |
| India | burrp Mumbai | `burrp.com/mumbai/*` | 456 | 10,074 | 20180101–20191016 | 84 | 20 | N | N | ok |
| India | dineout.co.in | `dineout.co.in/*` | 3,758 | 30,000 | 20180103–20250402 | 157 | 1 | Y | N | truncated |
| Indonesia | zomato Jakarta | `zomato.com/jakarta/*` | 111 | 1,011 | 20180103–20240808 | 331 | 40 | N | N | ok |
| Indonesia | qraved Jakarta | `qraved.com/jakarta/*` | 6,727 | 30,000 | 20180104–20260316 | 42 | 0 | N | N | truncated |
| Indonesia | pergikuliner | `pergikuliner.com/restaurants/*` | 6,582 | 30,000 | 20180122–20260521 | 237 | 12 | N | N | truncated |
| Thailand | wongnai BKK | `wongnai.com/bangkok/*` | 2 | 9 | 20190822–20241113 | 1024 | 6 | N | N | ok |
| Thailand | wongnai restaurants | `wongnai.com/restaurants/*` | 5,545 | 30,000 | 20180306–20260521 | 504 | 0 | Y | N | truncated |
| Thailand | eatigo BKK | `eatigo.com/th/bangkok/*` | 3,410 | 17,349 | 20180809–20241114 | 206 | 14 | N | N | ok |
| Australia | zomato Sydney | `zomato.com/sydney/*` | 280 | 3,429 | 20180101–20250331 | 178 | 5 | N | N | ok |
| Australia | zomato Melbourne | `zomato.com/melbourne/*` | 147 | 2,658 | 20180101–20260107 | 435 | 32 | N | N | ok |
| Australia | urbanspoon | `urbanspoon.com/n/*` | 0 | 0 | — |  |  |  |  | empty |
| Australia | menulog | `menulog.com.au/restaurants/*` | 6,173 | 30,000 | 20180104–20251126 | 879 | 12 | Y | Y | truncated |
| Vietnam | foody HCMC | `foody.vn/ho-chi-minh/*` | 5,387 | 30,000 | 20180903–20260529 | 3 | 0 | N | N | truncated |
| Philippines | zomato Manila | `zomato.com/manila/*` | 52 | 1,362 | 20180107–20250822 | 218 | 37 | Y | N | ok |
| Malaysia | zomato KL | `zomato.com/kuala-lumpur/*` | 30 | 1,290 | 20180101–20240613 | 248 | 2 | Y | N | ok |
| Singapore | hungrygowhere | `hungrygowhere.com/dining-guide/restaurants/*` | 0 | 0 | — |  |  |  |  | empty |
| Singapore | foodpanda SG | `foodpanda.sg/restaurant/*` | 1,819 | 9,111 | 20180102–20260203 | 320 | 0 | Y | N | ok |
| Singapore | food.grab SG | `food.grab.com/sg/en/restaurant/*` | 2,591 | 9,970 | 20191018–20260531 | 259 | 12 | Y | Y | ok |
| Mexico | tripadvisor MX | `tripadvisor.com.mx/Restaurant_Review*` | 2,873 | 30,000 | 20180101–20260211 | 1167 | 9 | Y | N | truncated |

## Country roll-up (best platform per country)

| Country | Best platform | ≥2-cap restaurants | Sample $-hits | Clears formal threshold (≥15 + prices visible)? |
|---|---|---:|---:|---|
| Australia | menulog | 6,173 | 12 | ✓ |
| India | dineout.co.in | 3,758 | 1 | ✗ |
| Indonesia | qraved Jakarta | 6,727 | 0 | ✗ |
| Malaysia | zomato KL | 30 | 2 | ✗ |
| Mexico | tripadvisor MX | 2,873 | 9 | ✓ |
| Philippines | zomato Manila | 52 | 37 | ✓ |
| Singapore | food.grab SG | 2,591 | 12 | ✓ |
| Thailand | wongnai restaurants | 5,545 | 0 | ✗ |
| United States | allmenus.com | 7,021 | 0 | ✗ |
| Vietnam | foody HCMC | 5,387 | 0 | ✗ |

## Reading the matrix

- `≥2-cap restaurants` = distinct archived URLs with two or more captures inside the window. This is the gating metric for the formal-sector roster (≥15 required).
- `Sample $-hits` = currency-token count in ONE randomly-chosen archived page. Low or zero hits mean even though Wayback has captures, the captured HTML doesn't contain prices — usually because the site is/was a JS shell that loaded prices via API.
- `LD` / `ND` = whether the sample HTML has JSON-LD or `__NEXT_DATA__`; presence of either gives a clean structured data path that's usually more reliable than DOM regex.
- A country clears the formal threshold only when BOTH ≥2-cap ≥ 15 **and** sample $-hits ≥ 5.
- Common Crawl was not probed in this pass. It is a secondary archive available for Phase 1 if Wayback gaps are narrow.

## Phase 0 re-probe — 2026-06-16 22:07
### (1) Vietnam alternative URL patterns
| Pattern | ≥2-cap restaurants | Snapshots | Sample $-hits | Sample bytes | Notes |
|---|---:|---:|---:|---:|---|
| `foody.vn/*-restaurant*` | 0 | 0 |  |  |  |
| `foody.vn/*/` | 0 | 0 |  |  |  |
| `foody.vn/restaurant/*` | 33 | 77 | 0 | 0 | tiny sample (redirect/stub) |
| `foody.vn/ho-chi-minh/*/restaurant` | 0 | 0 |  |  |  |
| `tripadvisor.com/Restaurant_Review-g293925*` | 732 | 5,133 | 0 | 1291 |  |
| `tripadvisor.com/Restaurant_Review-g293924*` | 484 | 3,450 | 0 | 581 |  |

### (2) JSON-LD deep-parse re-probes (5 samples each)
| Platform | Pattern | ≥2-cap restaurants | Samples with LD prices | Mean LD prices/sample | Example item, price |
|---|---|---:|---:|---:|---|
| allmenus restaurant page | `allmenus.com/*/restaurant*` | 0 | — | — | empty |
| allmenus city slug | `allmenus.com/il/chicago/*` | 2,291 | 0/5 | 0.0 |  |
| wongnai restaurants | `wongnai.com/restaurants/*` | 5,545 | 1/5 | 0.2 | `ข้าวหมูแดงนายเคี้ยงคันคลอง หัวหิน` @ 55.0 |
| dineout restaurants | `dineout.co.in/*-restaurants` | 0 | — | — | empty |
| qraved jakarta restaurants | `qraved.com/jakarta/*-restaurant*` | 0 | — | — | empty |

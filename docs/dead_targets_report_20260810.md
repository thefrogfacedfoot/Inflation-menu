# Dead / non-producing TARGETS — audit 2026-08-10

Reporting only. **No entry described here has been edited, commented out, or
removed from `live_scraper.py`.**

Method: every entry in `live_scraper.TARGETS` was matched by query-stripped URL
against the `prices` table, taking its total row count and most recent
`collection_date`. "Producing" means it contributed at least one row on or
after 2026-07-11 (~30 days). Read-only connection; the DB was not modified.

## Headline

| | Count |
|---|---:|
| TARGETS entries | 103 |
| Producing (rows since 2026-07-11) | **69** |
| Stale (produced once, nothing recent) | 23 |
| Never produced a single row | 11 |

The scraper is healthy where it works — the 69 producing targets last wrote on
2026-08-09. The 34 non-producing entries are not a recent regression; they
split into two distinct, unrelated causes.

## Cause 1 — Foodpanda: 23 entries, IP-blocked (not dead URLs)

All 23 stopped on the **same day, 2026-06-15**, and all 23 are Foodpanda. That
is the signature of the per-IP Akamai block already recorded for this project
(baseline 0/29 Foodpanda success on the project IP), not of 23 restaurants
independently closing.

| Country | Entries | Producing | Last row |
|---|---:|---:|---|
| Singapore foodpanda | 19 | 5 | 2026-06-15 |
| Malaysia foodpanda | 10 | 1 | 2026-06-15 |

Singapore (14 stale): Crave Nasi Lemak, Crystal Jade GO, Crystal Jade Hong Kong
Kitchen, Crystal Jade La Mian Xiao Long Bao, Nam Kee Chicken Rice, No Signboard
Prawn Noodles and Carrot, Old Chang Kee, Paradise Dynasty, Pepper Lunch,
Putien, Rubato, Song Fa Bak Kut Teh, Tai Wah Pork Noodles, Toast Box.

Malaysia (9 stale): Family Seafood, Hameed Pata Mee Sotong, Ichiban Boshi KL,
Jerung Char Koay Teow, Kim Lian Kee, Kluang Rail Coffee, Nasi Kandar Pelita,
Pepper Lunch KL, Restoran Yusoof Dan Zakhir.

**Recommendation: leave these in place.** The URLs are almost certainly fine;
the network path is the problem. Removing them would destroy the ability to
resume Foodpanda collection the moment a residential-IP route is available, and
would silently drop Singapore and Malaysia coverage that the index depends on.
This is the pending A/B test, not a cleanup item.

## Cause 2 — US direct sites: 11 entries, never produced anything

These have **no rows at all**, ever — not stale, never working. Only
Applebee's (47 rows) and Buffalo Wild Wings (70 rows) of the 13 US direct
targets have ever produced data, both current as of 2026-08-09.

Captain D's, Cava, Denny's, IHOP, Olive Garden, Outback Steakhouse,
Sonic Drive-In, Wendy's, Whataburger, White Castle, Zaxby's.

This is consistent with a fresh probe run today: **35 new US chain sites
probed, 1 nominal pass** (Miller's Ale House, and that "pass" was a single
banner row, `Raise Your Cups $7.00` — not a menu). Breakdown: 17× HTTP 403
WAF, 14× location-gated React shell with no prices, 3× ACCESS_DENIED.

US chain websites do not publish prices without a store location. This is a
structural property of the market, not a fixable scraper bug, and it matches
the 16 US chains already in the `live_scraper.py` graveyard.

**Recommendation: US direct expansion room is effectively zero.** Whether to
retire the 11 non-producers is a judgement call — they cost nightly scrape time
and inflate the target count, but retiring them makes the US panel depend
entirely on two restaurants.

### Duplicate entry

`Whataburger` (`https://whataburger.com/menu`, `independent`, `direct`, `USD`)
appears **twice**: once as an active entry in `TARGETS`, and again as an
identical commented-out tuple in the dead-target graveyard. It has never
produced a row. Whichever way the US entries go, this one is unambiguously
redundant.

## Separate finding — USD conversion is running on stale rates

Not a TARGETS issue, but it affects every row the scraper writes.

`live_scraper.get_usd_rates()` calls `requests.get(...)`, but `live_scraper.py`
never imports `requests` — there is no `import requests` anywhere in the file,
at HEAD or in the working tree.

Verified by executing it under the production interpreter
(`/Users/erwenchen/venv/bin/python`):

```
⚠  Exchange rate fetch failed (name 'requests' is not defined)
↩  Falling back to stale cached rates
```

The live fetch therefore raises `NameError` on **every** run and is swallowed by
the `except Exception` fallback. `exchange_rates.json` was last successfully
written **2026-08-03**, so every `price_usd` computed since has used rates that
are at least a week old and will keep drifting. `requests` 2.32.5 *is*
installed — the import line is simply missing.

One-line fix (`import requests`), but it is outside the scope of this
expansion, so it has not been applied.

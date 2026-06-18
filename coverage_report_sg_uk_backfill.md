# Phase 0 — SG + UK month-depth backfill probe

Generated: 2026-06-18T09:36:33.077589
  
Window: 20180101 → 20260601
  
Probes new Wayback URL patterns aimed at extending the
month-coverage of SG (9 mo / 8,674 items today) and UK
(6 mo / 1,150 items). Same yields-table format as
`coverage_report.md`. NO scraping triggered by this run.

## Matrix

| Country | Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Block | Notes |
|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|---|
| Singapore | deliveroo SG | `deliveroo.com.sg/menu/*` | 5,421 | 30,000 | 20190916–20260213 | 181 | 0 | N | N | — | truncated |
| Singapore | deliveroo SG (slug) | `deliveroo.com.sg/menu/singapore/*` | 5,421 | 30,000 | 20190916–20260213 | 378 | 0 | N | N | — | truncated |
| Singapore | foodpanda SG menu | `foodpanda.sg/menu/*` | 0 | 0 | — |  |  |  |  | — | empty |
| Singapore | foodpanda SG rest | `foodpanda.sg/restaurant/*` | 1,819 | 9,111 | 20180102–20260203 | 401 | 0 | Y | N | captcha | ok; sample block:captcha |
| Singapore | hungrygowhere | `hungrygowhere.com/*-restaurant-*` | 0 | 0 | — |  |  |  |  | — | empty |
| United Kingdom | deliveroo UK | `deliveroo.co.uk/menu/*` | 3,080 | 30,000 | 20180903–20260511 | 391 | 321 | N | N | — | truncated |
| United Kingdom | deliveroo UK london | `deliveroo.co.uk/menu/london/*` | 3,716 | 30,000 | 20180122–20260530 | 363 | 99 | N | Y | cloudflare-challenge | truncated; sample block:cloudflare-challenge |
| United Kingdom | just-eat UK | `just-eat.co.uk/restaurants-*/menu` | 0 | 0 | — |  |  |  |  | — | empty |
| United Kingdom | just-eat UK alt | `just-eat.co.uk/restaurants/*` | 5,303 | 30,000 | 20180104–20260530 | 894 | 18 | Y | Y | cloudflare-challenge | truncated; sample block:cloudflare-challenge |
| United Kingdom | foodhub UK | `foodhub.co.uk/*-menu` | 0 | 0 | — |  |  |  |  | — | empty |

## Decision

A (source, country) pair is **queue-worthy** only when
BOTH ≥2-cap ≥ 15 **and** sample $-hits ≥ 5 **and** Block is
empty.

| Country | Best platform | ≥2-cap | $-hits | Block | Verdict |
|---|---|---:|---:|---|---|
| Singapore | deliveroo SG | 5,421 | 0 | — | bail (no prices visible) |
| United Kingdom | just-eat UK alt | 5,303 | 18 | cloudflare-challenge | bail (bot-blocked) |

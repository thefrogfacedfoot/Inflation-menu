# Phase 0 — Track B candidate-source probe

Generated: 2026-06-17T21:22:28.147987
  
Window: 20180101 → 20260601
  
CDX limit per query: 30,000.

Same yields-table format as `coverage_report.md`. Adds a `Block` column flagging Cloudflare/captcha/tiny-page responses so we can bail on bot-blocked sources fast.

## Matrix

| Country | Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Block | Notes |
|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|---|
| Indonesia | gofood | `gofood.co.id/*` | 4,901 | 30,000 | 20191119–20251101 | 1024 | 0 | Y | Y | — | truncated |
| Indonesia | gojek food | `gojek.com/*/food/*` | 0 | 0 | — |  |  |  |  | — | empty |
| Indonesia | gofood jakarta | `gofood.co.id/jakarta/*` | 1,344 | 9,791 | 20200214–20251101 | 313 | 0 | Y | Y | — | ok |
| Thailand | grabfood TH | `food.grab.com/th/en/*` | 3,724 | 30,000 | 20190817–20241222 | 555 | 4 | Y | Y | captcha | truncated; sample block:captcha |
| Thailand | grabfood TH (TH) | `food.grab.com/th/th/*` | 5,037 | 30,000 | 20190716–20241214 | 253 | 4 | Y | Y | captcha | truncated; sample block:captcha |
| Thailand | lineman TH | `lineman.co.th/*` | 0 | 0 | — |  |  |  |  | — | empty |
| Australia | menulog (revisit) | `menulog.com.au/restaurants/*` | 6,173 | 30,000 | 20180104–20251126 | 851 | 48 | Y | Y | — | truncated |

## Decision: which targets to add to `historical_html_scraper.py`?

| Country | Best platform | ≥2-cap | $-hits | Block | Verdict |
|---|---|---:|---:|---|---|
| Australia | menulog (revisit) | 6,173 | 48 | — | ✓ queue |
| Indonesia | gofood | 4,901 | 0 | — | bail (no prices visible) |
| Thailand | grabfood TH (TH) | 5,037 | 4 | captcha | bail (bot-blocked) |

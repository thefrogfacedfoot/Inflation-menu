# Phase 0 — ID/TH alternative-source probe

Generated: 2026-06-18T04:05:30.581771
  
Window: 20180101 → 20260601
  
Probes alternative routes to escape the dead GoFood / GrabFood paths identified in `coverage_report_track_b.md`.

## Matrix

| Country | Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | Sample $-hits | LD | ND | Block | Notes |
|---|---|---|---:|---:|---|---:|---:|:---:|:---:|---|---|
| Indonesia | shopeefood SP | `shopee.co.id/m/shopeefood-*` | 47 | 7,636 | 20210226–20260209 | 37 | 0 | N | N | captcha | ok; sample block:captcha |
| Indonesia | shopeefood | `shopeefood.co.id/*` | 4 | 29 | 20221031–20260215 | 16 | 0 | Y | Y | — | ok |
| Indonesia | shopeefood jkt | `shopeefood.co.id/jakarta/*` | 0 | 0 | — |  |  |  |  | — | empty |
| Thailand | wongnai restaurants | `wongnai.com/restaurants/*` | 5,545 | 30,000 | 20180306–20260521 |  |  |  |  | — | truncated; sample error:('Connection aborted.', ConnectionResetError(54, 'Connection |
| Thailand | wongnai bangkok | `wongnai.com/bangkok/*` | 2 | 9 | 20190822–20241113 | 1024 | 6 | N | N | — | ok |
| Thailand | lineman wongnai | `lineman.line.me/r/wongnai/*` | 0 | 0 | — |  |  |  |  | — | empty |
| Thailand | wongnai restaurant detail | `wongnai.com/restaurants/*-*` | 0 | 0 | — |  |  |  |  | — | empty |

## Decision

| Country | Best platform | ≥2-cap | $-hits | Block | Verdict |
|---|---|---:|---:|---|---|
| Indonesia | shopeefood SP | 47 | 0 | captcha | bail (bot-blocked) |
| Thailand | wongnai bangkok | 2 | 6 | — | bail (no prices visible) |

If both ID and TH bail again, the documented plan is to ship them as floor-only countries — see the user direction 2026-06-18.

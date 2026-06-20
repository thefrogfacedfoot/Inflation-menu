# Phase 0 — UK alt-source probe

Generated: 2026-06-19T09:48:20.355543
  
Window: 20180101 → 20260601
  
Probes 7 UK Wayback patterns not previously covered:
JustEat menu path, Uber Eats GB, and five chain direct
sites (Pret, Greggs, Wagamama, Nando's, Itsu). NO scraping
triggered by this run.

## Matrix

| Platform | URL pattern | ≥2-cap restaurants | Snapshots | Range | Sample KB | £-hits | LD | ND | Block | Notes |
|---|---|---:|---:|---|---:|---:|:---:|:---:|---|---|
| just-eat UK menu | `just-eat.co.uk/restaurants/*/menu` | 0 | 0 | — |  |  |  |  | — | empty |
| ubereats UK | `ubereats.com/gb/store/*` | 3,000 | 30,000 | 20210612–20260531 | 1071 | 156 | Y | N | captcha | truncated; sample block:captcha |
| pret | `pret.co.uk/en-gb/menu/*` | 0 | 0 | — |  |  |  |  | — | empty |
| greggs | `greggs.co.uk/*menu*` | 0 | 0 | — |  |  |  |  | — | empty |
| wagamama | `wagamama.com/menu/*` | 23 | 238 | 20231001–20260522 | 1226 | 4 | N | N | captcha | ok; sample block:captcha |
| nandos UK | `nandos.co.uk/*menu*` | 0 | 0 | — |  |  |  |  | — | empty |
| itsu | `itsu.com/*menu*` | 0 | 0 | — |  |  |  |  | — | empty |

## Decision

A pattern is **queue-worthy** only when BOTH ≥2-cap ≥ 15
**and** sample £-hits ≥ 5 **and** Block is empty.

| Platform | ≥2-cap | £-hits | Block | Verdict |
|---|---:|---:|---|---|
| just-eat UK menu | 0 |  | — | bail (no archive coverage) |
| ubereats UK | 3,000 | 156 | captcha | bail (bot-blocked) |
| pret | 0 |  | — | bail (no archive coverage) |
| greggs | 0 |  | — | bail (no archive coverage) |
| wagamama | 23 | 4 | captcha | bail (bot-blocked) |
| nandos UK | 0 |  | — | bail (no archive coverage) |
| itsu | 0 |  | — | bail (no archive coverage) |

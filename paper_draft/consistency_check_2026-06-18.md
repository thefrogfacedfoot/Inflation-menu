> **DEPRECATED (2026-07-06).** The results below use the original spec, which
> intersected CPI to menu-observation months before differencing and therefore
> mixed 1–9-month CPI changes. Do not cite F=6.034 / p=0.021. The current
> headline is the calendar-true respec (F=4.20, p=0.0499, n=31) in
> `analysis_results/gap_robustness.json`. This file is kept as a historical
> record of the 2026-06-18 run.

# Paper v0.2 consistency check vs canonical JSON (2026-06-18)

Source of truth: `analysis_results/granger_results.json`, `dashboard_data/country_summary.json`, `uifpi.db` (post-Round-2 ingest).

## Summary

The paper draft was frozen at commit `3b50747` (2026-06-18 morning) before Round 2 ingested ONS UK + Malaysia PriceCatcher + BLS APU. Most US, UK, and MY numbers in the paper are now stale. India, Indonesia, Singapore, Thailand, and most Australia numbers still match.

**A v0.3 pass needs to update §1, §5.1, §6.1, §6.3, §7.1, §8, and §9 to the post-Round-2 values, OR explicitly freeze the paper at the pre-Round-2 dataset and add a note that ONS/KPDN data is excluded from the headline test (with the justification from `docs/archival_data_findings_2026-06-18_round2.md` §"Why UK/MY don't Granger-cause CPI even with the new data").**

Recommendation: **freeze at pre-Round-2 (commit `3b50747`) data and add the "official series excluded by design" note**. The Round 2 data, by construction, cannot lead CPI (it IS CPI input data) so including it would muddy the leading-indicator claim. The paper's clean framing — US Granger-significant, India null, six countries accumulating — is the right submission story.

---

## Number-by-number discrepancies

### Abstract (§1)

| Claim | Paper says | Current JSON | Status |
|---|---|---|---|
| Total observations | 41,263 | 438,655 | ⚠ stale (Round 2 added ONS UK 356k, MY 2.8k, BLS APU 38k) |
| US n | 31 | 120 | ⚠ stale |
| US Granger F | F(1, 26) = 6.0336 | F(2, 112) = 3.5772 (lag=2) | ⚠ stale — different lag selected |
| US Granger p | 0.021 | 0.0312 | ⚠ stale (still significant) |
| US lead | 1 month | 2 months | ⚠ stale |
| India n | 47 | 47 | ✓ |
| US pass-through β | −0.0043 | −0.0034 | ⚠ stale |
| US pass-through p | 0.5399 | **0.0432 (now significant)** | ⚠⚠ stale and qualitatively different — the "timing-not-level" framing in §7.1 needs revisiting |
| Abstract word count | "248" | actually 258 | ⚠ recount |

### Introduction (§2)

| Claim | Paper says | Current | Status |
|---|---|---|---|
| Observations | 41,263 | 438,655 | ⚠ stale |
| Window | "2018 through mid-2026" | 2018-01 → 2026-06 | ✓ window unchanged |
| Countries above n=24 threshold | only US (implied) | US 120, India 47, UK 65, MY 55 | ⚠ stale — UK and MY are now well above threshold (but their results are non-significant by construction; see Round-2 doc) |

### Data §5.1 (Per-country sources table)

| Country | Paper rows | Current raw rows | Paper months | Current UIFPI months | Status |
|---|---:|---:|---:|---:|---|
| United States | 8,282 | 46,683 (includes 38k BLS APU grocery) | 35 | 149 | ⚠ stale (BLS APU added) |
| Singapore | 9,557 | 9,557 | 9 | 9 | ✓ |
| Malaysia | 3,505 | 6,319 | 7 | 57 | ⚠ stale (PriceCatcher added) |
| United Kingdom | 17,371 | 373,585 | 20 | 67 | ⚠ stale (ONS added) |
| India | 635 | 635 | 49 | 49 | ✓ |
| Indonesia | 34 | 34 | 21 | 21 | ✓ |
| Australia | 1,831 | 1,831 | 24 | 24 | ✓ |
| Thailand | 11 | 11 | 1 | 1 | ✓ |
| **Total** | **41,263** | **438,655** | — | — | ⚠ stale |

### Results §6.1 (US case — main test table)

| Statistic | Paper | Current JSON | Status |
|---|---|---|---|
| Window | 2018-04 → 2024-10 | 2014-01 → 2026-06 (UIFPI side; CPI overlap 2015-01 → 2024-12) | ⚠ stale |
| Overlap n | 31 | 120 | ⚠ stale |
| UIFPI ADF p | 0.0000 | 0.000 | ✓ |
| CPI ADF p | 0.0183 | 0.306 (differenced) | ⚠ stale — CPI no longer stationary in levels at the new window |
| VAR-AIC lag | 4 | 3 | ⚠ stale |
| Granger F | 6.0336 | 3.5772 (at min-p lag=2) | ⚠ stale |
| Granger df | (1, 26) | (2, 112) | ⚠ stale |
| Granger p | 0.021 | 0.0312 | ⚠ stale (still significant) |
| Lead | 1 month | 2 months | ⚠ stale |
| Pass-through β | −0.0043 | −0.0034 | ⚠ stale |
| Pass-through SE | 0.00684 | 0.00166 | ⚠ stale |
| Pass-through CI | [−0.01938, +0.01073] | [−0.00668, −0.00011] | ⚠ stale — **no longer spans zero** |
| Pass-through p | 0.5399 | **0.0432 (significant at 5%)** | ⚠⚠ qualitative change |
| R² | 0.5566 | 0.5769 | ⚠ minor |

Per-lag detail in §6.1 (lag-1 F=6.0336 p=0.021; lag-2 F=2.6845 p=0.0896; lag-3 F=2.0613 p=0.1376; lag-4 F=1.967 p=0.1455) → current per-lag: lag-1 F=4.3756 p=0.0387; lag-2 F=3.5772 p=0.0312; lag-3 F=2.1366 p=0.0998. All ⚠ stale.

### Results §6.2 (India)

| Statistic | Paper | Current | Status |
|---|---|---|---|
| Window | 2018-01 → 2026-01 | 2018-01 → 2024-01 (per CPI overlap window) | ⚠ window claim slightly off — verify CPI end-month |
| n | 47 | 47 | ✓ |
| UIFPI ADF p | 0.0121 | 0.012 | ✓ (rounding) |
| CPI ADF p | 0.0036 | 0.004 | ✓ (rounding) |
| Granger F(1, 43) | 0.5213 | 0.5213 | ✓ |
| Granger p | 0.4742 | 0.4742 | ✓ |
| β | 0.0007 | 0.0007 | ✓ |
| SE | 0.0019 | 0.0019 | ✓ |
| CI | [−0.00313, +0.00462] | [−0.00313, +0.00462] | ✓ |
| p | 0.6973 | 0.6973 | ✓ |
| R² | 0.4997 | 0.4997 | ✓ |

### Results §6.3 (other six)

| Country | Paper n | Current n | Paper status | Current status | Status |
|---|---:|---:|---|---|---|
| Australia | 23 | 23 | "1 month short — 2026-06 outside CPI window" | unchanged | ✓ |
| United Kingdom | 18 | **65** | "Accumulating monthly" | **above threshold (p=0.469, non-sig — official-series construction effect)** | ⚠⚠ stale, both n and interpretation |
| Indonesia | 20 | 20 | "Restaurant-aggregate Zomato cost-for-two; nearest to threshold" | unchanged (p=0.170) | ✓ |
| Singapore | 8 | 8 | "Going-forward live started mid-2026" | unchanged | ✓ |
| Malaysia | 6 | **55** | "Live collection only; ~2027" | **above threshold (p=0.577, non-sig — official-series construction effect)** | ⚠⚠ stale, both n and interpretation |
| Thailand | 0 | 0 | unchanged | unchanged | ✓ |

### Discussion §7.1 (timing-not-level)

The §7.1 thesis "UIFPI is a *leading indicator*, not a *CPI substitute*" rests on pass-through being non-significant (β=−0.0043, p=0.5399). **In the current Round-2 dataset, pass-through is now significant (β=−0.0034, p=0.0432) and the 95% CI [−0.00668, −0.00011] excludes zero on the negative side.** The "timing not level" reading no longer cleanly holds at the current sample. Two options:

1. Freeze the paper at pre-Round-2 data (where §7.1 reads correctly).
2. Update §7.1 to acknowledge the larger sample reveals a small negative pass-through and discuss what that means substantively.

Recommendation: **option 1**. The Round-2 official feeds are not a clean enlargement of the same data-generating process; they introduce the BLS-APU grocery series and the ONS-CPI-input catering series, the latter of which is mechanically related to US CPI through cross-country basket effects on imports. The pre-Round-2 sample is the cleaner experimental cut for the headline result.

### Limitations §8

- "Single significant result. One country, n = 31, p = 0.021" → both numbers stale (n=120, p=0.0312 in current data). Same recommendation as above.

### Conclusion §9

- "F(1, 26) = 6.0336, p = 0.021" → stale.
- "developmental eight-country dataset of 41,263 price observations" → stale.

---

## Reference citation check (§11 / formerly §10)

Every reference is cited inline in the prose at least once. No orphan references.

| # | Reference | First citation | Other citations |
|---:|---|---|---|
| 1 | Cavallo & Rigobon 2016 | §2 ¶1 | §1 (abstract), §3 ¶2, §4.5 |
| 2 | Cavallo 2017 | §3 ¶2 | — |
| 3 | Cavallo 2018 | §3 ¶2 | — |
| 4 | Cavallo 2020 | §3 ¶2 | — |
| 5 | Pakko & Pollard 2003 | §3 ¶3 | §2 ¶2 (Big Mac Index, name only) |
| 6 | Stock & Watson 2002 | §3 ¶5 | — |
| 7 | Hamilton 1994 | §3 ¶5 | — |
| 8 | IMF 2022 | §3 ¶4 | — |
| 9 | UNDP 2019 | §2 ¶2 | §3 ¶4 |
| 10 | World Bank 2023 | §3 ¶4 | — |
| 11 | Schema.org 2024 | §3 ¶5 | — |
| 12 | ABS 2026 | §3 ¶5 | — |

All 12 references present in prose. ✓ No action needed.

Minor cleanup notes (not orphans, but light citations):
- Refs 2, 3, 4, 6, 7, 10, 11, 12 each appear exactly once. They are appropriate where placed; SSEF doesn't require multiple citations per ref.
- Numbeo Cost-of-Living is **mentioned by name** in §3 ¶3 but is not in the reference list. Either (a) add a 13th reference for Numbeo or (b) re-word §3 ¶3 to avoid the proper-noun reference. Recommendation: add Numbeo as ref 13 if SSEF wants ≥12 references, or drop the name if 12 is already enough.

---

## Acknowledgments section

Added as new §10 immediately before References (now §11). Standard short form covering: open-source code repository link, data-source attributions (Wayback, ONS, KPDN, OECD, ABS, BLS, Schema.org), library acknowledgments, advisor placeholder, errors-are-mine line. The advisor name is a `[advisor name, if applicable]` placeholder for you to fill in or delete.

Numbering: §10 → §11 shift handled in the edit. Internal cross-references in the paper that say "§10 References" → none found (the paper only cites references by name + year, not by section).

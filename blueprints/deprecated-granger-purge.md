# Blueprint 2 — Purge the deprecated US Granger numbers (F=6.03 / p=0.021) from docs and paper

BUILDER: Claude Sonnet, working alone, cold start, cannot ask questions. Chosen over Haiku because the edits are text-surgical and must not disturb surrounding prose.

## Context (all of it)

Repo: `/Users/erwenchen/Inflation-menu`. UICPI/UIFPI is a restaurant-menu-price research project with a paper draft in `paper_draft/` and status docs in `docs/`.

On 2026-07-06 the headline US Granger result was **respecified**. The original pipeline intersected CPI down to menu-observation months *before* differencing, so "lag 1" actually mixed 1–9-month CPI changes ("gap-mixing"). The old headline **F = 6.0336, p = 0.021, n = 31 is DEPRECATED and must not be cited**. The authoritative numbers live in `analysis_results/gap_robustness.json` (produced by `gap_robustness.py`), key `specs`:

- `calendar_true` (role: headline): F = 4.2012, analytic p = 0.0499, n = 31; permutation p = 0.0519 (shuffle) / 0.0689 (block). Exact 1-month lags, full-calendar CPI changes, no imputation.
- `interp_ffill` (role: robustness): forward-fills single-month menu gaps causally (no look-ahead); n = 38, F ≈ 9.05, p = 0.0048, permutation ≤ 0.017. **Read the exact F/p from the JSON before writing them anywhere.**
- `interp_1mo` (secondary robustness): n = 38, F = 8.0434, p = 0.0075 — carries a look-ahead caveat; prefer ffill.
- `strict_pairs` (footnote): n = 10, F = 2.3162, p = 0.1718 — directionally consistent, uninformative.
- `original` (deprecated): F = 6.0336, p = 0.021.

**Critical constraint:** the project owner is personally rewriting the Results section of `paper_draft/paper.md` around p = 0.0499. You must NOT rewrite or re-number the prose of `paper.md`. Your only edit there is a warning banner (step 1).

**Repo rules:** no `Co-Authored-By` trailer on commits; code/doc changes go on a branch with a PR, never straight to main.

## Edits

### 1. `paper_draft/paper.md` — banner only

Insert as the very first lines of the file (before the existing first line):

```
<!-- ⚠ STALE NUMBERS (2026-07-07): this draft still cites the DEPRECATED US
     Granger spec F(1,26)=6.0336, p=0.021 (gap-mixing artifact — see
     analysis_results/gap_robustness.json "framing"). The headline is now the
     calendar-true spec: F=4.20, p=0.0499, n=31; ffill robustness F=9.05,
     p=0.0048, n=38. The Results rewrite is being done BY THE AUTHOR — do not
     mechanically re-number this file. Stale citations as of 2026-07-07 are
     near lines 45, 201, 212, 265, 279, 292. -->
```

Change nothing else in this file.

### 2. `docs/granger_results_2026-06-18.md` — deprecation banner

Insert as the very first lines:

```
> **DEPRECATED (2026-07-06).** The results below use the original spec, which
> intersected CPI to menu-observation months before differencing and therefore
> mixed 1–9-month CPI changes. Do not cite F=6.034 / p=0.021. The current
> headline is the calendar-true respec (F=4.20, p=0.0499, n=31) in
> `analysis_results/gap_robustness.json`. This file is kept as a historical
> record of the 2026-06-18 run.
```

Change nothing else.

### 3. `paper_draft/consistency_check_2026-06-18.md` — same banner

Insert the identical blockquote from step 2 as the first lines. Change nothing else.

### 4. `docs/ssef_data_status.md` — update the live status doc

(a) Replace the entire `## Headline finding` section (the heading plus its one paragraph, ending just before `## Per-country roll-up`) with:

```
## Headline finding (respecified 2026-07-06)

**United States — the UIFPI menu index Granger-leads CPI at an exact 1-month
lag.** Calendar-true specification: F = 4.20, analytic p = 0.0499, n = 31
(permutation p: 0.052 shuffle / 0.069 block). Robustness: forward-filling
single-month menu gaps with past information only strengthens the result
(n = 38, F = 9.05, p = 0.0048; permutation ≤ 0.017). The strict
adjacent-pairs cut (n = 10) is directionally consistent but uninformative.

**Deprecated:** the original F = 6.034, p = 0.021 spec intersected CPI down to
menu-observation months *before* differencing, so its "lag 1" mixed 1–9-month
CPI changes. Do not cite it. Authoritative numbers:
`analysis_results/gap_robustness.json` (script: `gap_robustness.py`).
```

(b) In the `## Per-country roll-up` table, change the United States row's Granger p cell from `**0.021** ✓` to `**0.0499** ✓ (calendar-true respec)`.

(c) Directly under that table there is a line `Significant Granger results: **1 / 8** (United States).` — leave it (still true).

### 5. Leave alone (deliberately)

- `CHANGELOG.md` — append-only history; its 2026-06-18 entry stays as written.
- `docs/archival_data_findings_2026-06-16.md` line ~17 mentions "MY p=0.021" — that is a coincidental tier-bug artifact discussion, unrelated. Do not touch.
- `README.md` — verified to contain no deprecated Granger numbers as of 2026-07-07; re-grep to confirm, edit only if a bare "6.03"/"p = 0.021" US citation appears.

## Acceptance

1. `grep -rn "6\.0336\|6\.034\|p = 0.021\|p=0.021" README.md docs/ paper_draft/` — every hit must be inside one of: the banners you added, `CHANGELOG.md`-style dated history inside `docs/granger_results_2026-06-18.md` / `consistency_check_2026-06-18.md` body (below your banner), `paper_draft/paper.md` body (below your banner), or the archival-findings MY line. No other file may match.
2. `grep -n "0.0499" docs/ssef_data_status.md` returns ≥ 2 hits.
3. Confirm the exact ffill F/p you wrote match `analysis_results/gap_robustness.json` (`python3 -c "import json; print(json.load(open('analysis_results/gap_robustness.json'))['specs']['interp_ffill'])"`).

## Ship

Branch `docs/deprecate-old-granger-headline`; commit message `Mark old US Granger spec deprecated; update status docs to calendar-true respec` (no Co-Authored-By trailer); push; open PR to main with `gh pr create`, PR body ending `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

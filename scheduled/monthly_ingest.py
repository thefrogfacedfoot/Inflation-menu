#!/usr/bin/env python3
"""
Monthly ingest orchestrator.

Runs the pipeline in order:
  1. live_scraper.py            — collect today's prices (8 countries)
  2. get_monthly_cpi_all.py     — refresh CPI from OECD / WB sources
  3. index_builder.py           — rebuild uifpi_index
  4. granger_analysis.py        — re-test Granger causality (--min-obs 24)
  5. dashboard_data.py          — regenerate dashboard JSON

Per-country yields appended to docs/ingest_log.md (never overwritten).

Fail-loud rules:
  - If a country's prices delta is 0 AND it had prior rows AND --skip-scrape
    is not set, log a warning (could be bot-block, network error, or genuine
    no-new-prices day). Print, don't abort — the pipeline still runs.
  - Granger is invoked with --min-obs 24; countries below the threshold
    self-skip with insufficient_data.

Modes:
  --dry-run     : skip every stage that writes. Reports the current DB state
                  + which stages would run. Useful for verifying the
                  orchestrator structure in CI before unleashing it on prod.
  --skip-scrape : skip live_scraper.py only (useful for cloud runners that
                  don't have residential IP — Foodpanda + GrabFood
                  bot-block datacenter IPs).
  --skip-cpi    : skip the CPI refresh.

The 'fetches but does not write' interpretation of --dry-run requires
forking live_scraper.py to honour a NULL_DB env var; for now --dry-run
is a preview mode (no subprocesses are invoked), and --skip-scrape lets
operators trigger the same pipeline against the existing prices table.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE = Path(__file__).resolve().parent.parent
DB = BASE / 'uifpi.db'
INGEST_LOG = BASE / 'docs' / 'ingest_log.md'

COUNTRIES = ['Singapore', 'Malaysia', 'Indonesia', 'Thailand', 'India',
             'United States', 'United Kingdom', 'Australia']


def _snap(db_path: Path) -> dict:
    """Return {country: (rows, distinct_months)} from prices table.

    Counts only `price > 0` to ignore any stray garbage rows.
    """
    if not db_path.exists():
        return {c: (0, 0) for c in COUNTRIES}
    conn = sqlite3.connect(str(db_path))
    out = {}
    for c in COUNTRIES:
        row = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT substr(collection_date,1,7)) "
            "FROM prices WHERE country = ? AND price > 0",
            (c,),
        ).fetchone()
        out[c] = (row[0] or 0, row[1] or 0)
    conn.close()
    return out


def _granger_snap(db_path: Path) -> dict:
    """Latest granger_significant flags from country_summary.json if it
    exists. Used to spot countries that have just crossed the threshold."""
    summary_path = BASE / 'dashboard' / 'public' / 'data' / 'country_summary.json'
    if not summary_path.exists():
        return {}
    import json
    try:
        d = json.loads(summary_path.read_text())
    except Exception:
        return {}
    return {c: bool(r.get('granger_significant')) for c, r in d.items()}


def _run(label: str, cmd: list, dry: bool, extra_args: Optional[list] = None) -> int:
    full = list(cmd) + (extra_args or [])
    print(f"\n=== {label} ===")
    print(f"  cmd: {' '.join(full)}")
    if dry:
        print("  DRY-RUN: skipped")
        return 0
    try:
        rc = subprocess.call(full, cwd=str(BASE))
    except FileNotFoundError as e:
        print(f"  ⚠  {e}")
        return 127
    if rc != 0:
        print(f"  ⚠  exited with {rc}")
    return rc


def _append_log(stamp: str, before: dict, after: dict,
                granger_before: dict, granger_after: dict,
                dry_run: bool, skipped: list) -> None:
    """Append a per-run section to docs/ingest_log.md."""
    INGEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not INGEST_LOG.exists():
        INGEST_LOG.write_text(
            "# UIFPI ingest log\n\n"
            "Append-only audit trail. Each `## YYYY-MM-DD HH:MM` section is\n"
            "one monthly_ingest.py run; per-country deltas, Granger crossover\n"
            "events, and skipped stages are recorded for the SSEF paper.\n\n"
        )
    lines = [f"\n## {stamp}\n"]
    if dry_run:
        lines.append("**Mode**: DRY-RUN — no stages were executed.\n")
    if skipped:
        lines.append(f"**Skipped stages**: {', '.join(skipped)}\n")
    lines.append("\n| Country | Items before | Items after | Δ | Months before | Months after |\n")
    lines.append("|---|---:|---:|---:|---:|---:|\n")
    for c in COUNTRIES:
        rb, mb = before.get(c, (0, 0))
        ra, ma = after.get(c, (0, 0))
        d = ra - rb
        marker = f"+{d}" if d > 0 else ("0" if d == 0 else str(d))
        lines.append(f"| {c} | {rb} | {ra} | {marker} | {mb} | {ma} |\n")
    # Granger crossover events
    crossovers = []
    for c in COUNTRIES:
        was = granger_before.get(c, False)
        now = granger_after.get(c, False)
        if not was and now:
            crossovers.append(f"  - **{c}** crossed Granger threshold (now significant)")
        elif was and not now:
            crossovers.append(f"  - **{c}** dropped below Granger threshold")
    if crossovers:
        lines.append("\n**Granger crossover events**:\n")
        lines.extend(c + "\n" for c in crossovers)
    with INGEST_LOG.open('a') as fh:
        fh.writelines(lines)
    print(f"\n  Logged → {INGEST_LOG.relative_to(BASE)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true',
                    help='Preview mode — no subprocesses invoked, no DB writes.')
    ap.add_argument('--skip-scrape', action='store_true',
                    help='Skip live_scraper (use for cloud runners without residential IP).')
    ap.add_argument('--skip-cpi', action='store_true',
                    help='Skip the OECD/WB CPI refresh.')
    ap.add_argument('--min-obs', type=int, default=24,
                    help='Granger min observations (default 24).')
    ap.add_argument('--allow-empty-db', action='store_true',
                    help='Bypass the minimum-row sanity guard (fresh-start scenarios only).')
    args = ap.parse_args()

    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    print('=' * 60)
    print(f'  Monthly Ingest — {stamp}')
    print('=' * 60)
    if args.dry_run:
        print('  Mode: DRY-RUN (no writes, no subprocess calls)')
    skipped = []
    if args.skip_scrape: skipped.append('live_scraper')
    if args.skip_cpi:    skipped.append('cpi_refresh')

    before = _snap(DB)
    granger_before = _granger_snap(DB)
    total_before = sum(r[0] for r in before.values())
    print(f'\nBefore: {total_before:,} total price rows across {len(COUNTRIES)} countries')

    MIN_EXPECTED_ROWS = 50_000  # local DB had ~156k rows on 2026-07-07; a near-empty
                                # table means uifpi.db is missing from this checkout
    if total_before < MIN_EXPECTED_ROWS and not args.allow_empty_db:
        print(f'\n  ✗ ABORT: prices table has {total_before:,} rows '
              f'(< {MIN_EXPECTED_ROWS:,}). uifpi.db is missing or empty in this '
              f'checkout — running the pipeline would produce and commit garbage '
              f'(this happened on 2026-07-01). No stages were run, nothing was '
              f'written. Pass --allow-empty-db to override.')
        return 2

    # 1. live_scraper
    if not args.skip_scrape:
        _run('Live scraper (8 countries)',
             ['python3', 'live_scraper.py'], args.dry_run)

    # 2. CPI refresh
    if not args.skip_cpi:
        _run('Monthly CPI refresh (OECD + World Bank)',
             ['python3', 'get_monthly_cpi_all.py', '--countries', 'all'],
             args.dry_run)

    after = _snap(DB)

    # Per-country yields + fail-loud check
    print(f'\nPer-country yield (this run):')
    print(f'  {"Country":<18} {"items_b":>8} {"items_a":>8} {"Δ":>8}  '
          f'{"months_b":>9} {"months_a":>9}')
    print(f'  {"-"*18} {"-"*8} {"-"*8} {"-"*8}  {"-"*9} {"-"*9}')
    zero_yield = []
    for c in COUNTRIES:
        rb, mb = before[c]; ra, ma = after[c]
        delta = ra - rb
        marker = f'+{delta}' if delta > 0 else ('0' if delta == 0 else str(delta))
        flag = ' ⚠' if (delta == 0 and rb > 0 and not args.skip_scrape and not args.dry_run) else ''
        print(f'  {c:<18} {rb:>8} {ra:>8} {marker:>8}  {mb:>9} {ma:>9}{flag}')
        if delta == 0 and rb > 0 and not args.skip_scrape and not args.dry_run:
            zero_yield.append(c)
    if zero_yield:
        print(f'\n  ⚠⚠⚠  Zero new items for: {", ".join(zero_yield)}')
        print('       (bot-block, network error, or genuine no-new-prices day)')
        print('       Inspect verify_targets_report.json + run url-health digest.')

    # 3. index_builder
    _run('Index builder', ['python3', 'index_builder.py'], args.dry_run)

    # 4. Granger (built-in --min-obs guard already skips countries below threshold)
    _run('Granger analysis',
         ['python3', 'granger_analysis.py'],
         args.dry_run,
         extra_args=['--min-obs', str(args.min_obs)])

    # 5. dashboard_data
    _run('Dashboard data exporter',
         ['python3', 'dashboard_data.py'], args.dry_run)

    granger_after = _granger_snap(DB)

    # Append to ingest log
    _append_log(stamp, before, after, granger_before, granger_after,
                args.dry_run, skipped)

    # Surface crossover events on stdout too
    crossovers_new = [c for c in COUNTRIES
                      if granger_after.get(c) and not granger_before.get(c)]
    if crossovers_new:
        print(f'\n  🎯 Granger crossovers this run: {crossovers_new}')

    print(f'\n  Done.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

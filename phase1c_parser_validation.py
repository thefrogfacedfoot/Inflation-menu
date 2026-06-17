"""
Phase 1c — parser validation.

For each Phase 1 target, query CDX for a small set of in-window snapshots,
fetch each, run the platform's parser, and report items extracted per
sample. Write digest to parse_validation.md.

Does NOT insert into the DB. Pure read-only validation.
"""
import os
import random
import sys
import time

# Reuse everything from the production scraper
from historical_html_scraper import (
    TARGETS, get_distributed_snapshots, fetch_snapshot,
)

BASE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_PER_TARGET = 5


def main():
    md_path = os.path.join(BASE, 'parse_validation.md')
    rnd = random.Random(20260616)
    summary = []
    with open(md_path, 'w') as fh:
        fh.write('# Phase 1c — parser validation\n\n')
        fh.write(f'Random {SAMPLES_PER_TARGET} samples per target, in-window. '
                 'No DB writes — pure parser exercise.\n\n')
        fh.write('| Target | Hits | Mean items/page | Best sample (items) | '
                 'Failure modes |\n')
        fh.write('|---|---:|---:|---:|---|\n')

    for t in TARGETS:
        country, sector, label, src_key, pat, currency, parser = t
        key = f'{country}: {label}'
        print(f"\n[{key}]  pattern={pat}")
        snaps = get_distributed_snapshots(
            pat, per_period=2, max_snapshots=SAMPLES_PER_TARGET * 4,
        )
        if not snaps:
            print('  no snapshots from CDX walk')
            with open(md_path, 'a') as fh:
                fh.write(f'| {key} | 0 | — | — | CDX returned 0 snapshots |\n')
            continue
        sample = rnd.sample(snaps, min(SAMPLES_PER_TARGET, len(snaps)))
        per_sample = []
        failures = []
        for s in sample:
            ts, url = s['timestamp'], s['url']
            time.sleep(1.5)
            html = fetch_snapshot(ts, url)
            if html is None:
                per_sample.append(0); failures.append('fetch fail')
                print(f'  {ts[:8]} {url[:60]} → fetch fail'); continue
            try:
                items = parser(html, currency)
            except Exception as e:
                per_sample.append(0); failures.append(f'parse exc: {str(e)[:30]}')
                print(f'  {ts[:8]} {url[:60]} → parse exc: {str(e)[:30]}'); continue
            per_sample.append(len(items))
            print(f'  {ts[:8]} {url[:60]} → {len(items)} items')
            if items[:3]:
                for name, price, cur in items[:3]:
                    print(f'      "{name[:40]}" {price} {cur}')
        hits = sum(1 for n in per_sample if n > 0)
        mean = sum(per_sample) / len(per_sample) if per_sample else 0
        best = max(per_sample) if per_sample else 0
        # Most-common failure
        from collections import Counter
        fail_summary = ''
        if failures:
            top = Counter(failures).most_common(2)
            fail_summary = '; '.join(f'{c}× {f}' for f, c in top)
        elif hits == 0:
            fail_summary = '0 items / page (parser found no prices)'
        summary.append({'target': key, 'hits': hits, 'mean': mean,
                        'best': best, 'fail': fail_summary})
        with open(md_path, 'a') as fh:
            fh.write(f'| {key} | {hits}/{len(per_sample)} | {mean:.1f} | '
                     f'{best} | {fail_summary} |\n')
        time.sleep(2)

    print('\n=== Validation summary ===')
    for s in summary:
        print(f'  {s["target"]:<40} {s["hits"]:>2}/{SAMPLES_PER_TARGET} hits, '
              f'mean {s["mean"]:.1f}, best {s["best"]}, {s["fail"]}')
    print(f'\nDigest → {md_path}')


if __name__ == '__main__':
    main()

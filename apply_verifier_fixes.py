"""
Take the verify_targets_report.json output and apply it to live_scraper.py.

For every target classified as DEAD, NAV_ERROR, or WRONG_PAGE, comment out
that target's tuple in live_scraper.py with a leading '#' on each line of
the tuple, plus an inline note showing the reason.

Targets classified as OK, OK_TITLE_ONLY, or BLOCKED stay live (BLOCKED just
means headed Chromium got bot-blocked — the URL itself is real).

Idempotent: re-running with a fresh report re-evaluates each target.

Run after the verifier finishes:
    python3 apply_verifier_fixes.py            # dry-run by default
    python3 apply_verifier_fixes.py --apply    # actually edit the file
"""
import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(BASE, 'live_scraper.py')
REPORT = os.path.join(BASE, 'verify_targets_report.json')

# Treat these statuses as definitively broken — comment them out
REMOVE_STATUSES = {'DEAD', 'NAV_ERROR', 'WRONG_PAGE'}


def load_report():
    with open(REPORT) as fh:
        return json.load(fh)


def patch(content, removals, verbose=True):
    """
    For each (name, url, reason) to remove, find the tuple starting with
    ("name", and comment out its lines until the matching closing paren.
    """
    lines = content.splitlines(keepends=True)
    out_lines = list(lines)
    patched = []
    for name, url, status, reason in removals:
        # Locate the tuple by exact "name" match
        needle = f'    ("{name}",'
        for i, line in enumerate(out_lines):
            if line.startswith(needle):
                # Find the end of the tuple (line ending with ),)
                j = i
                while j < len(out_lines):
                    if out_lines[j].rstrip().endswith('"),'):
                        break
                    j += 1
                if j >= len(out_lines):
                    print(f"  WARN: couldn't find tuple end for {name!r}")
                    break
                # Comment out lines i..j and add a note above
                clean_reason = ' '.join(reason.split())[:160]
                note = (f"    # [verifier:{status}] {clean_reason}\n")
                for k in range(i, j + 1):
                    if not out_lines[k].lstrip().startswith('#'):
                        # preserve indentation
                        stripped = out_lines[k].lstrip('\n')
                        indent_len = len(out_lines[k]) - len(out_lines[k].lstrip())
                        prefix = out_lines[k][:indent_len]
                        out_lines[k] = f"{prefix}# {out_lines[k][indent_len:]}"
                # Insert note line before the tuple (only once)
                if i == 0 or '[verifier:' not in (out_lines[i - 1] if i > 0 else ''):
                    out_lines.insert(i, note)
                patched.append((name, status))
                if verbose:
                    print(f"  patched: {name}  ({status})")
                break
        else:
            print(f"  WARN: target {name!r} not found in live_scraper.py")
    return ''.join(out_lines), patched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='Write changes to live_scraper.py (default: dry-run)')
    args = ap.parse_args()

    report = load_report()
    by_status = {}
    for r in report['results']:
        by_status.setdefault(r['status'], []).append(r)

    print("Verifier summary:")
    for s in sorted(by_status):
        print(f"  {s}: {len(by_status[s])}")

    removals = []
    for status in REMOVE_STATUSES:
        for r in by_status.get(status, []):
            removals.append((r['name'], r['url'], r['status'], r['reason']))

    print(f"\nWill remove {len(removals)} targets")

    with open(LIVE) as fh:
        content = fh.read()

    patched_content, patched_list = patch(content, removals, verbose=True)

    if not args.apply:
        print("\n(dry-run; pass --apply to write)")
        return

    bak = LIVE + '.bak'
    with open(bak, 'w') as fh:
        fh.write(content)
    print(f"Backup: {bak}")
    with open(LIVE, 'w') as fh:
        fh.write(patched_content)
    print(f"Wrote {len(patched_list)} comment-outs to {LIVE}")


if __name__ == '__main__':
    main()

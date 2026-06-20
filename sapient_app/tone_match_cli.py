#!/usr/bin/env python3
"""Adapt a Reddit reply draft to a subreddit's tone, without changing meaning.

Reads creds from .env (or environment): REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
REDDIT_USER_AGENT, ANTHROPIC_API_KEY.

Examples:
    # draft piped from stdin
    cat draft.txt | python tone_match_cli.py \\
        --url https://reddit.com/r/foo/comments/abc123/... --sub foo

    # draft from a file
    python tone_match_cli.py --draft draft.txt \\
        --url https://reddit.com/r/foo/comments/abc123/... --sub foo

    # JSON output (for scripting)
    python tone_match_cli.py --json ... < draft.txt
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from dataclasses import asdict

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app.tone_match import DEFAULT_MODEL, fetch_sample, revise

logging.basicConfig(
    level=logging.WARNING, format="%(levelname)s: %(message)s"
)


def _read_draft(path: str | None) -> str:
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    if sys.stdin.isatty():
        sys.exit(
            "error: no draft provided. Pass --draft FILE or pipe text on stdin."
        )
    return sys.stdin.read().strip()


def _diff(original: str, revised: str) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            revised.splitlines(keepends=True),
            fromfile="draft",
            tofile="revised",
            n=2,
        )
    )


_RISK_BADGE = {"low": "LOW ", "med": "MED ", "high": "HIGH"}


def _render_human(original: str, result, diff: str) -> str:
    badge = _RISK_BADGE[result.promo_risk]
    out = [
        "=" * 60,
        f"PROMO RISK: [{badge}]  {result.promo_reasoning}",
        "=" * 60,
        "",
        "TONE NOTES:",
        f"  {result.tone_notes}",
        "",
        "REVISED DRAFT:",
        "-" * 60,
        result.revised_draft,
        "-" * 60,
    ]
    if result.reframe_suggestion:
        out += [
            "",
            "REFRAME SUGGESTION (alternative framing):",
            "-" * 60,
            result.reframe_suggestion,
            "-" * 60,
        ]
    out += ["", "DIFF (draft → revised):"]
    out.append(diff if diff.strip() else "  (no textual changes)")
    out += ["", "Reminder: this tool does not post. Review and post yourself."]
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="parent Reddit post URL")
    p.add_argument("--sub", required=True, help="subreddit name (without r/)")
    p.add_argument("--draft", help="path to draft file (else read stdin)")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    draft = _read_draft(args.draft)
    if not draft:
        sys.exit("error: draft is empty")

    sample = fetch_sample(args.url, args.sub)
    result = revise(draft, sample, model=args.model)
    diff = _diff(draft, result.revised_draft)

    if args.json:
        payload = {
            **asdict(result),
            "diff": diff,
            "subreddit": sample.subreddit,
            "parent_title": sample.parent_title,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_render_human(draft, result, diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

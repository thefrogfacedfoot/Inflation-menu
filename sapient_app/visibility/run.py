"""CLI + entry point.

Examples:
    python run.py api
    python run.py poll-once --query-id 1 --source chatgpt
    python run.py generate-tasks
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _api() -> int:
    import uvicorn

    uvicorn.run("visibility.api:app", host="0.0.0.0", port=8001, reload=False)
    return 0


def _poll_once(args: argparse.Namespace) -> int:
    from visibility.db import init_db, session_scope
    from visibility.runner import run_query

    init_db()

    async def _do() -> None:
        with session_scope() as session:
            run = await run_query(session, args.query_id, args.source, force=args.force)
            if run is None:
                print("skipped (idempotent or inactive)")
            else:
                print(f"run {run.id} ok ({len(run.raw_response)} chars)")

    asyncio.run(_do())
    return 0


def _gen_tasks(_args: argparse.Namespace) -> int:
    from visibility.db import init_db, session_scope
    from visibility.tasks import generate_gap_tasks

    init_db()
    with session_scope() as session:
        created = generate_gap_tasks(session)
        print(f"created {len(created)} tasks")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="visibility")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("api")
    pq = sub.add_parser("poll-once")
    pq.add_argument("--query-id", type=int, required=True)
    pq.add_argument("--source", required=True)
    pq.add_argument("--force", action="store_true")
    sub.add_parser("generate-tasks")
    args = p.parse_args()

    if args.cmd in (None, "api"):
        return _api()
    if args.cmd == "poll-once":
        return _poll_once(args)
    if args.cmd == "generate-tasks":
        return _gen_tasks(args)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

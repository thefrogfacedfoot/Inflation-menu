"""Entry points: run the API (with poller) or run a single polling cycle.

Usage:
    python run.py api          # start FastAPI on :8000 with background poller
    python run.py poll-once    # run one cycle and exit (respects DRY_RUN)
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] == "api":
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
        return 0
    if sys.argv[1] == "poll-once":
        from app.db import init_db
        from app.poller import run_cycle

        init_db()
        run_cycle()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

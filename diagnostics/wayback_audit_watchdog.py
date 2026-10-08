"""Watchdog for wayback_feasibility_audit.py crawl.

Runs the single test CDX query (retries every 60 min on failure), starts the crawler under caffeinate, then every
5 min checks the heartbeat file; if it is older than 15 min the crawler is killed and restarted from the checkpoint
(logged). Max 5 restarts, then stop and report. After a clean pass it runs the `question` stage; if patterns are incomplete it re-runs the crawl (max 3 extra passes). Stops at the audit DEADLINE with a BLOCKED report if incomplete.
Usage: python diagnostics/wayback_audit_watchdog.py <logfile>
"""
import datetime
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
HB = HERE / "wayback_audit" / "heartbeat.txt"
SCRIPT = HERE / "wayback_feasibility_audit.py"
UA = "UICPI-research-audit (erwenchen56@gmail.com; academic feasibility audit)"
DEADLINE = datetime.datetime(2026, 10, 9, 20, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
MAX_RESTARTS, STALE_S, CHECK_S = 5, 15 * 60, 5 * 60
MAX_PASSES = 3


def now():
    return datetime.datetime.now().astimezone()


def say(msg):
    print(f"{now().isoformat(timespec='seconds')} {msg}", flush=True)


def test_query():
    try:
        r = requests.get("https://web.archive.org/cdx/search/cdx", timeout=(10, 60), headers={"User-Agent": UA},
                         params={"url": "kfc.com/menu", "limit": 1, "output": "json"})
        return r.status_code == 200
    except requests.RequestException as e:
        say(f"test query error: {type(e).__name__}")
        return False


def hb_age():
    return time.time() - HB.stat().st_mtime if HB.exists() else float("inf")


def start():
    return subprocess.Popen(["caffeinate", "-i", sys.executable, "-u", str(SCRIPT), "crawl"], start_new_session=True)


def stop(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    p.wait()


def main():
    while not test_query():
        if now() >= DEADLINE:
            say("BLOCKED on archive availability: test query never succeeded before deadline")
            return
        say("test query failed; waiting 60 min")
        time.sleep(3600)
    say("test query ok; starting crawler")
    restarts, passes, p, started = 0, 0, start(), time.time()
    while True:
        time.sleep(CHECK_S)
        if now() >= DEADLINE:
            if p.poll() is None:
                stop(p)
            say("DEADLINE reached; crawler stopped. Check checkpoint: if any pattern not done -> report BLOCKED, no partial counts")
            return
        if p.poll() is not None:
            if p.returncode == 0:
                r = subprocess.run([sys.executable, "-W", "ignore", str(SCRIPT), "question"], capture_output=True, text=True)
                say("crawl pass complete; question stage:\n" + r.stdout.strip())
                if "BLOCKED" not in r.stdout:
                    return
                if passes >= MAX_PASSES:
                    say(f"{MAX_PASSES} extra passes used; patterns still incomplete. STOPPING, report BLOCKED with checkpoint state")
                    return
                passes += 1
                say(f"extra pass {passes}/{MAX_PASSES} to retry failed cells")
                p, started = start(), time.time()
                continue
            age = f"exit code {p.returncode}"
        elif max(hb_age(), 0) > STALE_S and time.time() - started > STALE_S:
            age = f"heartbeat stale {hb_age() / 60:.0f} min"
            stop(p)
        else:
            continue
        if restarts >= MAX_RESTARTS:
            say(f"{age}; {MAX_RESTARTS} restarts used. STOPPING, report to user")
            return
        restarts += 1
        say(f"RESTART {restarts}/{MAX_RESTARTS} ({age}); resuming from checkpoint")
        p, started = start(), time.time()


if __name__ == "__main__":
    main()

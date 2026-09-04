#!/bin/bash
# Same as run_scraper_background.sh, but forces UIFPI_CONCURRENCY=3.
# live_scraper.py itself is untouched -- SCRAPE_CONCURRENCY already reads
# UIFPI_CONCURRENCY from the environment (default 1). This wrapper exists
# so a concurrency-3 run can be launched without remembering to set the
# env var by hand each time.
#
# Default mode is HEADED Chromium (foodpanda/grabfood detect headless),
# which requires a logged-in desktop session -- don't lock the screen
# mid-run. For a true headless run set UIFPI_HEADLESS=1 before invoking.
#
# Usage:   ./run_scraper_background_concurrency3.sh
# Logs:    tail -f scraper_log.txt
# Stdout:  tail -f scraper_output.txt
# Stop:    kill <PID>  (PID is printed below and recorded in scraper.pid)

cd /Users/erwenchen/Inflation-menu || exit 1

UIFPI_CONCURRENCY=3 nohup /Users/erwenchen/venv/bin/python live_scraper.py >> scraper_output.txt 2>&1 &
PID=$!
echo "$PID" > scraper.pid

echo "Scraper started in background at UIFPI_CONCURRENCY=3. PID: $PID"
echo "Check progress: tail -f scraper_log.txt"
echo "Check output:   tail -f scraper_output.txt"
echo "Stop:           kill $PID"

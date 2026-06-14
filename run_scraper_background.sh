#!/bin/bash
# Launch live_scraper.py detached from the terminal so it survives
# the SSH/Terminal window closing. Headless Chromium does not need a
# visible screen here — Mac LaunchServices keeps the process alive.
#
# Usage:   ./run_scraper_background.sh
# Logs:    tail -f scraper_log.txt
# Stdout:  tail -f scraper_output.txt
# Stop:    kill <PID>  (PID is printed below and recorded in scraper.pid)

cd /Users/erwenchen/Inflation-menu || exit 1

nohup python3 live_scraper.py > scraper_output.txt 2>&1 &
PID=$!
echo "$PID" > scraper.pid

echo "Scraper started in background. PID: $PID"
echo "Check progress: tail -f scraper_log.txt"
echo "Check output:   tail -f scraper_output.txt"
echo "Stop:           kill $PID"

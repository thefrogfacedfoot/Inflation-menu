#!/bin/zsh
# macOS notifications for the nightly. Run by launchd user agents (GUI session), not by cron.
#   notify.sh remind  18:45 reminder (com.uicpi.notify-remind)
#   notify.sh done    fires when ~/scraper_watch changes (com.uicpi.notify-done); once per run, only after
#                     watch_next.sh wrote its last watch.log line and touched done_<date>
#   notify.sh test    sends a test banner
# Test hooks (env): W, REPO, NOTIFY_DRY=1 (print the message instead of posting it).
W=${W:-/Users/erwenchen/scraper_watch}; L=$W/watch.log; REPO=${REPO:-/Users/erwenchen/Inflation-menu}; D=$(date +%F)
notify() { if [ -n "$NOTIFY_DRY" ]; then echo "NOTIFY: $1"; else /usr/bin/osascript -e "display notification \"$1\" with title \"UIFPI\""; fi; }
case "$1" in
  remind) notify "Scrape at 19:00 — keep the Mac on and plugged in until 'run done'" ;;
  test)   notify "Notification test $(date +%T)" ;;
  done)
    # the done_<date> name carries the run's start date (watch_next.sh sets it at 18:50), so a run that ends after
    # midnight still notifies: any done_* touched in the last 10 min that has no notified_<date> marker.
    for f in $(find $W -maxdepth 1 -name 'done_*' -mmin -10); do
      d=${f##*done_}; [ -e $W/notified_$d ] && continue; touch $W/notified_$d
      total=$(grep "^$d.*Run config" $REPO/scraper_log.txt 2>/dev/null | tail -1 | sed 's/.*targets=\([0-9]*\).*/\1/'); total=${total:-?}
      n=$(sqlite3 $REPO/uifpi.db "select count(distinct restaurant_name) from prices where collection_date like '$d%' and source in ('js','grabfood','direct')" 2>/dev/null); n=${n:-?}
      last=$(grep "^$d" $L | grep -E "CLEAN COMPLETION|WITHOUT DONE LINE|REBOOT during|never started" | tail -1)
      case "$last" in
        *"CLEAN COMPLETION"*) notify "UIFPI run done: $n/$total targets" ;;
        *"WITHOUT DONE LINE"*) notify "UIFPI run ENDED WITHOUT DONE LINE: $n/$total targets (see watch.log)" ;;
        *"REBOOT during"*) notify "UIFPI run INTERRUPTED by a reboot: $n/$total targets" ;;
        *"never started"*) notify "UIFPI: scraper never started tonight" ;;
        *) notify "UIFPI watch finished: $n/$total targets (see watch.log)" ;;
      esac
    done ;;
  *) echo "usage: notify.sh remind|done|test" >&2; exit 2 ;;
esac

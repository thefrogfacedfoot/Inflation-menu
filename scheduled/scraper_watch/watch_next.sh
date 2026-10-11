#!/bin/zsh
# Death-watch for the 19:00 nightly (reboot-aware). Logs every 2 min while live_scraper.py runs. On exit: clean finish ("Done.
# Results in uifpi.db" in scraper_log.txt) vs death (saves a log-show capture). If the machine rebooted while a run was in
# progress TONIGHT, the next start reports it (the run is gone; cron does not resume it). A state_inrun left by an earlier
# night (other date, or >12 h old) is stale: it is cleared and logged, and the watch arms normally for tonight's run.
# Test hooks (env): W (watch dir), REPO (repo dir), WATCH_DRYRUN=1 (exit right after the arm decision).
W=${W:-/Users/erwenchen/scraper_watch}; L=$W/watch.log; D=$(date +%F); cd ${REPO:-/Users/erwenchen/Inflation-menu}
bt() { sysctl -n kern.boottime | sed 's/.*sec = \([0-9]*\).*/\1/'; }
if [ -e $W/state_inrun ]; then
  sd=$(cat $W/state_inrun); se=$(date -j -f '%F %T' "$sd" +%s 2>/dev/null || echo 0)
  if [ "${sd%% *}" != "$D" ] || [ $(( $(date +%s) - se )) -gt 43200 ]; then
    echo "$(date '+%F %T') stale state_inrun from ${sd%% *} cleared" >> $L; rm -f $W/state_inrun
  elif [ "$(cat $W/state_boot 2>/dev/null)" != "$(bt)" ]; then
    echo "$(date '+%F %T') REBOOT during a run: last poll $sd; scraper killed, no cron resume. last log: $(tail -1 scraper_log.txt | cut -c1-140)" >> $L
    rm -f $W/state_inrun; touch $W/done_$D; exit 0
  fi
fi
echo "$(date '+%F %T') armed" >> $L
[ -n "$WATCH_DRYRUN" ] && exit 0
until pgrep -f '[Pp]ython.* live_scraper.py' >/dev/null; do
  [ "$(date +%H%M)" -ge 2330 ] && { echo "$(date '+%F %T') scraper never started by 23:30" >> $L; touch $W/done_$D; exit 0; }
  sleep 20
done
echo "$(date '+%F %T') scraper started" >> $L
while true; do
  now=$(date '+%F %T'); echo "$now" > $W/state_inrun; bt > $W/state_boot
  sp=$(pgrep -f '[Pp]ython.* live_scraper.py' | tr '\n' ','); ch=$(pgrep -fc -i 'chrom')
  last=$(tail -1 scraper_log.txt | cut -c1-140)
  as=$(pmset -g assertions | grep -E 'PreventUserIdleSystemSleep|PreventSystemSleep' | tr -s ' ' | tr '\n' ';')
  sl=$(/usr/bin/log show --last 3m --predicate 'eventMessage CONTAINS "Entering Sleep" OR eventMessage CONTAINS "Wake reason"' 2>/dev/null | grep -v 'log run noninteractively' | grep -c -E 'Entering Sleep|Wake reason')
  echo "$now pids=[$sp] chromium=$ch sleep_events_3m=$sl assertions=$as last=$last" >> $L
  if [ -z "$sp" ]; then
    if tail -30 scraper_log.txt | grep -q 'Done. Results in uifpi.db'; then echo "$now CLEAN COMPLETION (last: $last)" >> $L
    else
      echo "$now SCRAPER EXITED WITHOUT DONE LINE (last: $last)" >> $L
      /usr/bin/log show --start "$(date -v-5M '+%F %T')" --end "$(date -v+2M '+%F %T')" --predicate 'eventMessage CONTAINS[c] "kill" OR eventMessage CONTAINS[c] "screentime" OR eventMessage CONTAINS[c] "downtime" OR eventMessage CONTAINS[c] "sleep" OR process == "kernel"' 2>/dev/null | grep -v 'log run noninteractively' | tail -300 > $W/death_$(date +%H%M).log
      echo "$now death log: $W/death_$(date +%H%M).log" >> $L
    fi
    rm -f $W/state_inrun; touch $W/done_$D; exit 0
  fi
  sleep 120
done

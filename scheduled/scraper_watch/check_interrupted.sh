#!/bin/zsh
# Login-time check (launchd RunAtLoad). If the last 19:00 nightly that has had >= 6 h to finish left no done_<date> file
# (done_ is written by watch_next.sh on clean finish, death, reboot report and "never started"), append one line to
# watch.log. Also clears a stale state_inrun left by an interrupted run, so the 18:50 death-watch does not report a
# REBOOT and touch today's done_ file (which would leave tonight's run unwatched).
W=${W:-/Users/erwenchen/scraper_watch}; L=$W/watch.log
LOG=${LOG:-/Users/erwenchen/Inflation-menu/scraper_log.txt}
NOW=${NOW:-$(date +%s)}
D=$(date -r $((NOW - 90000)) +%F)                    # now - 25 h: newest 19:00 slot that is >= 6 h old
bt=$(sysctl -n kern.boottime | sed 's/.*sec = \([0-9]*\).*/\1/')           # same (greedy -> usec) id as watch_next.sh, so state_boot compares equal
bs=$(sysctl -n kern.boottime | sed 's/.*{ sec = \([0-9]*\),.*/\1/')       # real boot epoch, for display only
if [ -e $W/state_inrun ] && [ "$(cat $W/state_boot 2>/dev/null)" != "$bt" ]; then
  stale="; last in-run poll $(cat $W/state_inrun)"; rm -f $W/state_inrun
fi
# Same-day check: logging in at or after 19:30 with no sign of tonight's run (no "scraper started" line for
# today in watch.log, no done_ file, no live_scraper.py process) means the 19:00 slot was missed today.
T=$(date -r $NOW +%F)
if [ "$(date -r $NOW +%H%M)" -ge 1930 ] && [ ! -e $W/done_$T ] && ! grep -q "^$T.*scraper started" $L 2>/dev/null \
   && ! pgrep -f '[Pp]ython.* live_scraper.py' >/dev/null && [ ! -e $W/alert_${T}_missed ]; then
  echo "$(date -r $NOW '+%F %T') 19:00 slot missed today (login check at $(date -r $NOW +%H:%M); no run started)" >> $L
  touch $W/alert_${T}_missed
fi
[ -e $W/done_$D ] && exit 0
grep -q "interrupted: no done file for $D" $L 2>/dev/null && exit 0
last=$(grep "^$D" $LOG 2>/dev/null | tail -1 | cut -c1-140)
echo "$(date -r $NOW '+%F %T') interrupted: no done file for $D (login check; boot $(date -r $bs '+%F %T')${stale}; last scraper_log line of $D: ${last:-none})" >> $L
touch $W/alert_${D}_interrupted

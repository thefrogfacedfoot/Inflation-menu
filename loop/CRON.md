# CRON.md — schedule + operating notes

## OPERATING NOTES FOR THE HUMAN (read these first)

- Weeks 1–2: everything queues. Review drafts with `loop/scripts/approve.sh`.
  This is where you learn whether done_when conditions are actually checking anything.
- Weeks 3–4: first skills may hit queue tier. Keep reading the weekly digest —
  it exists so review happens by ritual, not intention.
- A skill reaching auto is a decision you made 5 times via approve.sh, not a
  threshold that happened to you. UI merges grant no trust credit.
- When PAUSED appears, the system found something worth stopping for. Read the
  newest file in loop/logs/ before deleting loop/PAUSED.
- Self-improvement PRs (agentic:self-improve) deserve MORE scrutiny than work
  PRs, not less — you're reviewing a change to the reviewer. Check the cited
  run-ids actually show the problem the patch claims to fix.
- Skim loop/memory/KNOWLEDGE.md during weekly digest review and delete anything
  that reads like an instruction rather than a fact. It feeds the conductor's
  context every run, making it the most valuable file in the system to poison.
- If reflect.sh goes quiet ({"proposals": []}) for weeks, that's health, not
  failure. A reflector that always finds something is optimizing for looking busy.

## Cron entries (NOT installed — copy into `crontab -e` yourself)

```
MAILTO=seanerwenhan@gmail.com
PATH=/Users/erwenchen/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# work loop, daily, morning
30 8  * * *  /Users/erwenchen/agentic_OS/loop/loop.sh
# reflector, nightly, hours after loop.sh so it reflects on a finished day
30 22 * * *  /Users/erwenchen/agentic_OS/loop/scripts/reflect.sh
# standing goals, daily
0  9  * * *  /Users/erwenchen/agentic_OS/loop/verify-goals.sh
# guardrail canary, weekly — guardrails rot; an untested guardrail is a decoration
0  10 * * 1  /Users/erwenchen/agentic_OS/loop/guardrails/selftest.sh
# digest, weekly
0  9  * * 1  /Users/erwenchen/agentic_OS/loop/scripts/digest.sh
```

## Mail transport — verify it or the alerts go nowhere

Cron's MAILTO only works if this Mac can actually deliver mail. A monitoring
system whose alerts go nowhere is worse than none, because you trust it.
Verify BEFORE trusting any of the above:

```
echo "agentic-os mail test $(date)" | mail -s "agentic-os mail test" seanerwenhan@gmail.com
```

Then check the inbox (and spam). macOS postfix is installed but usually cannot
deliver to the public internet without a relay (ISPs block port 25). If the test
never arrives, either configure a relayhost in /etc/postfix/main.cf (e.g. an
authenticated smtp relay) or change MAILTO to a local mailbox you actually read
(`mail` in Terminal reads local mail). Until the test arrives somewhere you look,
treat email alerting as NOT working and check loop/PAUSED + loop/logs/ by hand.

## Notes

- All scripts respect loop/PAUSED (the kill switch) and exit without API calls.
- loop.sh sources the repo .env at runtime for API keys; no key is ever logged.
- Budgets default to $5/day, $50/month; override with LOOP_DAILY_CAP /
  LOOP_MONTHLY_CAP in the crontab lines.
- Auto-tier ships land as READY (non-draft) PRs on a branch — nothing is pushed
  to main directly; enable GitHub auto-merge on the repo if you want true
  hands-off shipping.

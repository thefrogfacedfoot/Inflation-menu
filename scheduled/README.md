# Scheduled tasks

## Weekly URL health check

`com.uifpi.url-health.plist` runs `verify_targets.py` every Monday at 09:00 local time:
- Re-classifies every TARGET in `live_scraper.py` as OK / BLOCKED / DEAD / WRONG_PAGE / NAV_ERROR
- Writes the full JSON report to `verify_targets_report.json`
- Writes a human-readable markdown digest to `verify_digest_<date>.md`

### Install (one-time)

```sh
cp scheduled/com.uifpi.url-health.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.uifpi.url-health.plist
```

### Trigger a manual run

```sh
launchctl kickstart -k "gui/$(id -u)/com.uifpi.url-health"
```

### View the next/last fire time

```sh
launchctl print "gui/$(id -u)/com.uifpi.url-health" | grep -E 'state|last exit'
```

### Uninstall

```sh
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.uifpi.url-health.plist
rm ~/Library/LaunchAgents/com.uifpi.url-health.plist
```

### Logs

- stdout → `scheduled/url-health.log`
- stderr → `scheduled/url-health.err`

### Acting on findings

Open the latest `verify_digest_<date>.md`. For each item under "Needs action", either replace the URL in `live_scraper.py` or run `python3 apply_verifier_fixes.py --apply` to comment them out automatically.

Note: foodpanda / GrabFood targets often show as `BLOCKED` because the verifier shares your residential IP with the live scraper — this is transient, not a dead URL, and is listed separately in the digest.

/**
 * Polls for delete requests whose grace period has elapsed and processes
 * them. Started from instrumentation.ts alongside the account-health
 * scheduler.
 *
 * Once-per-hour is plenty: a 30-day grace doesn't need sub-hour precision,
 * and the alternative (per-minute) hammers the DB with the same query.
 */
import { processDueDeletes } from "./gdpr";
import { log } from "./logging";

const HOUR_MS = 60 * 60 * 1000;
let _interval: NodeJS.Timeout | null = null;
let _started = false;

async function tick(): Promise<void> {
  try {
    const processed = await processDueDeletes();
    if (processed.length > 0) {
      log.info("gdpr_scheduler_tick", { processed: processed.length });
    }
  } catch (e) {
    log.warn("gdpr_scheduler_tick_failed", {
      message: e instanceof Error ? e.message : String(e),
    });
  }
}

export function startGdprScheduler(): { stop: () => void } {
  if (_started) return { stop: stopGdprScheduler };
  _started = true;
  // First sweep five minutes after boot — no point hammering during the
  // post-deploy warm-up window.
  setTimeout(() => void tick(), 5 * 60 * 1000).unref();
  _interval = setInterval(() => void tick(), HOUR_MS);
  _interval.unref();
  log.info("gdpr_scheduler_started", {});
  return { stop: stopGdprScheduler };
}

export function stopGdprScheduler(): void {
  if (_interval) clearInterval(_interval);
  _interval = null;
  _started = false;
}

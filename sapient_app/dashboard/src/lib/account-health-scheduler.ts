/**
 * Background scheduler for account-health checks. Started from the Next.js
 * instrumentation hook so it runs in the Node process, not the edge runtime.
 *
 * Cadence:
 *   - shadowban: daily per user
 *   - karma trend: daily per user
 *   - slow-burn removal: hourly during 9-21 UTC (the posting hours where
 *     fresh removals can show up; off-hours runs would just re-evaluate
 *     the same window over and over)
 *
 * We deliberately don't pull in node-cron — Next instrumentation is already
 * a singleton entry point and a small setInterval loop is plenty for this
 * cadence. If the cadence ever needs per-user staggering or backoff, swap
 * to a job queue.
 */
import { eq } from "drizzle-orm";
import { db } from "@/db/client";
import { userProfiles } from "@/db/schema";
import {
  checkKarmaTrend,
  checkShadowban,
  checkSlowBurnRemoval,
  runCheck,
} from "./account-health";
import {
  karmaDeps,
  shadowbanDeps,
  slowBurnDeps,
} from "./account-health-deps";
import { log, runWithLogContext } from "./logging";

const DAY_MS = 24 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

type Handle = { stop: () => void };

async function listActiveUsers(): Promise<Array<{ userId: string; redditUsername: string }>> {
  const rows = await db
    .select({
      userId: userProfiles.userId,
      redditUsername: userProfiles.redditUsername,
    })
    .from(userProfiles)
    .where(eq(userProfiles.isPaused, false));
  return rows;
}

async function runDailyCheck(): Promise<void> {
  for (const u of await listActiveUsers()) {
    // Each user gets its own correlation id so a per-user failure is
    // greppable without a request handler in the picture.
    const correlationId = crypto.randomUUID();
    await runWithLogContext({ correlationId, userId: u.userId }, async () => {
      try {
        await runCheck({
          userId: u.userId,
          checkType: "shadowban",
          run: () => checkShadowban(u.userId, u.redditUsername, shadowbanDeps),
        });
      } catch (e) {
        log.warn("scheduler_shadowban_failed", { user_id: u.userId, message: errMessage(e) });
      }
      try {
        await runCheck({
          userId: u.userId,
          checkType: "karma_trend",
          run: () => checkKarmaTrend(u.userId, karmaDeps),
        });
      } catch (e) {
        log.warn("scheduler_karma_failed", { user_id: u.userId, message: errMessage(e) });
      }
    });
  }
}

async function runHourlyCheck(): Promise<void> {
  const hour = new Date().getUTCHours();
  if (hour < 9 || hour >= 21) return;
  for (const u of await listActiveUsers()) {
    const correlationId = crypto.randomUUID();
    await runWithLogContext({ correlationId, userId: u.userId }, async () => {
      try {
        await runCheck({
          userId: u.userId,
          checkType: "slow_removal",
          run: () => checkSlowBurnRemoval(u.userId, slowBurnDeps),
        });
      } catch (e) {
        log.warn("scheduler_slow_burn_failed", {
          user_id: u.userId,
          message: errMessage(e),
        });
      }
    });
  }
}

function errMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

let _started = false;
let _daily: NodeJS.Timeout | null = null;
let _hourly: NodeJS.Timeout | null = null;

export function startAccountHealthScheduler(): Handle {
  if (_started) return { stop: stopAccountHealthScheduler };
  _started = true;
  // Run first iterations after a short delay so app boot finishes first; the
  // intervals then take over at their cadence.
  setTimeout(() => void runDailyCheck(), 30_000).unref();
  setTimeout(() => void runHourlyCheck(), 60_000).unref();
  _daily = setInterval(() => void runDailyCheck(), DAY_MS);
  _hourly = setInterval(() => void runHourlyCheck(), HOUR_MS);
  _daily.unref();
  _hourly.unref();
  log.info("account_health_scheduler_started", {});
  return { stop: stopAccountHealthScheduler };
}

export function stopAccountHealthScheduler(): void {
  if (_daily) clearInterval(_daily);
  if (_hourly) clearInterval(_hourly);
  _daily = null;
  _hourly = null;
  _started = false;
}

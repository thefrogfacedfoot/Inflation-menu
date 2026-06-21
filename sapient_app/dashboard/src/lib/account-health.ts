/**
 * Account-health monitoring. Detects silent Reddit penalties the existing
 * 20%-removal-rate auto-pause in src/lib/guardrails.ts can't see:
 *   - shadowbans (anon view sees materially fewer items than authed view)
 *   - karma-trend collapses (7d / 14d delta vs baseline)
 *   - slow-burn removal patterns (high std-dev between removals — sustained,
 *     not bursty, so the rolling-10 trigger doesn't fire)
 *
 * The check functions are pure-ish — they take a clock and a Reddit-IO
 * surface as dependencies — so the tests can drive deterministic scenarios
 * without standing up an HTTP mock. The scheduler in
 * src/lib/account-health-scheduler.ts wires the production dependencies.
 */
import { and, desc, eq, lte, sql } from "drizzle-orm";
import { db } from "@/db/client";
import {
  accountHealthCheck,
  accountHealthState,
  karmaSnapshots,
  posts,
  userProfiles,
} from "@/db/schema";
import { getCorrelationId, log } from "./logging";
import {
  accountHealthAlertsTotal,
  accountHealthCheckDurationSeconds,
  accountHealthWarningsTotal,
} from "./metrics";

export type CheckType = "shadowban" | "karma_trend" | "slow_removal";
export type CheckStatus = "ok" | "warning" | "alert";

export type CheckResult = {
  status: CheckStatus;
  details: Record<string, unknown>;
};

/* ---------- thresholds ----------
 * Pulled out so tests assert against named constants instead of magic numbers,
 * and so an ops change is a one-line env override.
 */
export const SHADOWBAN_GAP_THRESHOLD = Number(
  process.env.ACCOUNT_HEALTH_SHADOWBAN_GAP ?? 0.3,
);
export const KARMA_7D_ABSOLUTE_DROP = -50;
export const KARMA_7D_RELATIVE_DROP = 0.3;
export const SLOW_BURN_WINDOW = 30;
export const SLOW_BURN_MIN_REMOVAL_RATE = 0.1;
// Total span between first and last removal (seconds). Above this = sustained
// slow burn; below = clustered burst (already caught by guardrails.ts's 20%
// rolling-10 trigger). Tuned to ~one week: a steady "1 every few days"
// stretches removals over weeks; a burst lives in hours-to-days.
//
// Note: the original spec called this out as a std-dev heuristic, but
// std-dev alone can't separate "evenly spaced over a month" (low std-dev,
// large mean) from "clustered burst" (low std-dev, small mean). Span is the
// cleaner discriminator — std-dev is reported in details for ops audit.
export const SLOW_BURN_MIN_SPAN_SECONDS = 7 * 24 * 3600;

/* ============================================================ */
/* 1) SHADOWBAN DETECTION                                       */
/* ============================================================ */

export type UserAboutCounts = {
  link_karma: number;
  comment_karma: number;
  // Visible-item counts. Reddit's /user/:name/about.json doesn't include
  // total submission/comment counts directly; the deps layer is expected
  // to populate these by paging /user/:name/{submitted,comments} or by
  // pulling the analogous "total_karma" + listing sizes.
  visibleSubmissions: number;
  visibleComments: number;
};

/** Side effects the shadowban check needs from the outside world. Mocked in
 *  tests; wired to lib/reddit.ts in production. */
export type ShadowbanDeps = {
  fetchAuthed(userId: string, username: string): Promise<UserAboutCounts>;
  fetchAnon(username: string): Promise<UserAboutCounts>;
  now(): Date;
};

function relativeGap(authed: number, anon: number): number {
  if (authed <= 0) return 0;
  return Math.max(0, (authed - anon) / authed);
}

/**
 * Compare the authed view to the anon view of a user's profile. A material
 * gap on a single check is a warning; a gap sustained across two consecutive
 * checks ≥24h apart is an alert.
 */
export async function checkShadowban(
  userId: string,
  username: string,
  deps: ShadowbanDeps,
): Promise<CheckResult> {
  const [authed, anon] = await Promise.all([
    deps.fetchAuthed(userId, username),
    deps.fetchAnon(username),
  ]);

  const subGap = relativeGap(authed.visibleSubmissions, anon.visibleSubmissions);
  const commentGap = relativeGap(authed.visibleComments, anon.visibleComments);
  const maxGap = Math.max(subGap, commentGap);

  const baseDetails = {
    authed_submissions: authed.visibleSubmissions,
    authed_comments: authed.visibleComments,
    anon_submissions: anon.visibleSubmissions,
    anon_comments: anon.visibleComments,
    submission_gap: subGap,
    comment_gap: commentGap,
  };

  if (maxGap <= SHADOWBAN_GAP_THRESHOLD) {
    return { status: "ok", details: baseDetails };
  }

  // Anomaly. Single anomaly = warning. Two consecutive anomalies ≥24h apart
  // = alert. The "≥24h" guard prevents two retries-in-an-hour from
  // double-counting as confirmation.
  const previous = await db
    .select({ status: accountHealthCheck.status, checkedAt: accountHealthCheck.checkedAt })
    .from(accountHealthCheck)
    .where(
      and(
        eq(accountHealthCheck.userId, userId),
        eq(accountHealthCheck.checkType, "shadowban"),
      ),
    )
    .orderBy(desc(accountHealthCheck.checkedAt))
    .limit(1);

  const now = deps.now();
  const ONE_DAY_MS = 24 * 60 * 60 * 1000;
  const prior = previous[0];
  const priorWasAnomaly = prior && (prior.status === "warning" || prior.status === "alert");
  const priorAgeMs = prior ? now.getTime() - prior.checkedAt.getTime() : 0;

  if (priorWasAnomaly && priorAgeMs >= ONE_DAY_MS) {
    return {
      status: "alert",
      details: { ...baseDetails, threshold: SHADOWBAN_GAP_THRESHOLD, prior_status: prior.status },
    };
  }
  return {
    status: "warning",
    details: { ...baseDetails, threshold: SHADOWBAN_GAP_THRESHOLD },
  };
}

/* ============================================================ */
/* 2) KARMA TREND                                               */
/* ============================================================ */

export type KarmaDeps = {
  fetchCurrentKarma(userId: string): Promise<{ link_karma: number; comment_karma: number }>;
  now(): Date;
};

function totalKarma(s: { linkKarma: number; commentKarma: number }): number {
  return s.linkKarma + s.commentKarma;
}

/**
 * Snapshot current karma to karma_snapshot, then judge the rolling 7d delta:
 *   - absolute drop ≤ -50 OR a 30% drop relative to the 7d-ago baseline
 *     → warning
 *   - same condition sustained over 14d → alert
 *   - otherwise → ok
 */
export async function checkKarmaTrend(
  userId: string,
  deps: KarmaDeps,
): Promise<CheckResult> {
  const current = await deps.fetchCurrentKarma(userId);
  const now = deps.now();

  await db.insert(karmaSnapshots).values({
    userId,
    takenAt: now,
    linkKarma: current.link_karma,
    commentKarma: current.comment_karma,
  });

  const SEVEN_D = 7 * 24 * 3600 * 1000;
  const FOURTEEN_D = 14 * 24 * 3600 * 1000;
  const since7d = new Date(now.getTime() - SEVEN_D);
  const since14d = new Date(now.getTime() - FOURTEEN_D);

  // The current insert is the newest row; the baseline is the OLDEST snapshot
  // at or before the 7d-ago / 14d-ago boundary. If none exists, we don't have
  // enough history to judge — return ok with `insufficient_history=true`.
  const baseline7d = await newestSnapshotAtOrBefore(userId, since7d);
  const nowTotal = current.link_karma + current.comment_karma;

  const baseDetails = {
    current_total: nowTotal,
    baseline_7d_total: baseline7d ? totalKarma(baseline7d) : null,
  };

  if (!baseline7d) {
    return {
      status: "ok",
      details: { ...baseDetails, insufficient_history: true },
    };
  }

  const base7d = totalKarma(baseline7d);
  const delta7d = nowTotal - base7d;
  const relDrop7d = base7d > 0 ? (base7d - nowTotal) / base7d : 0;
  const breach7d = delta7d <= KARMA_7D_ABSOLUTE_DROP || relDrop7d >= KARMA_7D_RELATIVE_DROP;

  const details = {
    ...baseDetails,
    delta_7d: delta7d,
    relative_drop_7d: relDrop7d,
  };

  if (!breach7d) return { status: "ok", details };

  // Sustained over 14d? Check the 14d-ago baseline — if the breach holds
  // against that older baseline too, we escalate.
  const baseline14d = await newestSnapshotAtOrBefore(userId, since14d);
  if (baseline14d) {
    const base14d = totalKarma(baseline14d);
    const delta14d = nowTotal - base14d;
    const relDrop14d = base14d > 0 ? (base14d - nowTotal) / base14d : 0;
    const breach14d = delta14d <= KARMA_7D_ABSOLUTE_DROP || relDrop14d >= KARMA_7D_RELATIVE_DROP;
    if (breach14d) {
      return {
        status: "alert",
        details: { ...details, delta_14d: delta14d, relative_drop_14d: relDrop14d },
      };
    }
  }
  return { status: "warning", details };
}

async function newestSnapshotAtOrBefore(
  userId: string,
  threshold: Date,
): Promise<{ linkKarma: number; commentKarma: number } | null> {
  // We want the NEWEST sample taken at-or-before the threshold, i.e. the
  // most recent snapshot that's at least N days old. For the 7d baseline,
  // a user with only 7 days of monitoring history hits exactly one row;
  // a 14d baseline lookup with no snapshot ≥ 14d old returns null (we can't
  // claim "sustained over 14d" without a 14d-old reference point).
  const rows = await db
    .select({
      linkKarma: karmaSnapshots.linkKarma,
      commentKarma: karmaSnapshots.commentKarma,
    })
    .from(karmaSnapshots)
    .where(and(eq(karmaSnapshots.userId, userId), lte(karmaSnapshots.takenAt, threshold)))
    .orderBy(desc(karmaSnapshots.takenAt))
    .limit(1);
  return rows[0] ?? null;
}

/* ============================================================ */
/* 3) SLOW-BURN REMOVAL                                         */
/* ============================================================ */

export type SlowBurnDeps = {
  now(): Date;
};

/**
 * The 20% trigger in guardrails.ts catches bursty failure modes — 3 of the
 * last 10 posts removed in quick succession. It doesn't catch a steady drip:
 * a removal every 3-5 days over a month is still consequential but never
 * lights up the rolling-10 window.
 *
 * We look at the last SLOW_BURN_WINDOW (30) posts. If removal rate > 10%
 * AND the inter-removal-time std-dev is high (≥ SLOW_BURN_STDDEV_THRESHOLD_SECONDS),
 * we flag — the high std-dev is what distinguishes "slow drip" from "burst".
 * Bursts have tight inter-removal times (low std-dev) and are already caught
 * by the 20% trigger.
 */
export async function checkSlowBurnRemoval(
  userId: string,
  _deps: SlowBurnDeps,
): Promise<CheckResult> {
  const recent = await db
    .select({ isRemoved: posts.isRemoved, postedAt: posts.postedAt })
    .from(posts)
    .where(eq(posts.userId, userId))
    .orderBy(desc(posts.postedAt))
    .limit(SLOW_BURN_WINDOW);

  if (recent.length < SLOW_BURN_WINDOW) {
    return {
      status: "ok",
      details: { window_size: recent.length, insufficient_history: true },
    };
  }

  const removed = recent.filter((r) => r.isRemoved);
  const rate = removed.length / recent.length;

  if (rate <= SLOW_BURN_MIN_REMOVAL_RATE) {
    return { status: "ok", details: { window_size: recent.length, rate } };
  }

  // Compute std-dev of inter-removal times. recent is sorted DESC, so we
  // reverse to ASC then take the diffs between consecutive removals.
  const removedAscMs = removed
    .map((r) => r.postedAt.getTime())
    .sort((a, b) => a - b);
  const stddevSeconds = stddevOfDiffsSeconds(removedAscMs);
  const spanSeconds = removedAscMs.length > 1
    ? (removedAscMs[removedAscMs.length - 1] - removedAscMs[0]) / 1000
    : 0;

  const details = {
    window_size: recent.length,
    removals: removed.length,
    rate,
    inter_removal_stddev_seconds: stddevSeconds,
    span_seconds: spanSeconds,
    span_threshold_seconds: SLOW_BURN_MIN_SPAN_SECONDS,
  };

  // Span ≥ threshold = removals spread out over time = slow burn → alert.
  // Below threshold = removals clustered in a short window = burst, which the
  // 20% rolling-10 guardrail already catches — we return ok so we don't
  // double-flag the same failure mode through two surfaces.
  if (removed.length >= 2 && spanSeconds >= SLOW_BURN_MIN_SPAN_SECONDS) {
    return { status: "alert", details };
  }
  return { status: "ok", details: { ...details, classified_as: "burst_caught_elsewhere" } };
}

function stddevOfDiffsSeconds(ascMs: number[]): number {
  if (ascMs.length < 2) return 0;
  const diffs: number[] = [];
  for (let i = 1; i < ascMs.length; i++) {
    diffs.push((ascMs[i] - ascMs[i - 1]) / 1000);
  }
  const mean = diffs.reduce((a, b) => a + b, 0) / diffs.length;
  const variance =
    diffs.reduce((acc, d) => acc + (d - mean) * (d - mean), 0) / diffs.length;
  return Math.sqrt(variance);
}

/* ============================================================ */
/* PERSISTENCE                                                  */
/* ============================================================ */

/**
 * Run a single check, persist the result to account_health_check, and update
 * the rollup row in account_health_state. Returns the persisted result so
 * the caller can decide what to do (the scheduler logs; an API can return
 * directly).
 */
export async function runCheck(args: {
  userId: string;
  checkType: CheckType;
  run: () => Promise<CheckResult>;
  /** Override the persisted checkedAt. Tests pass a fixed clock here so the
   *  "two checks ≥24h apart" shadowban escalation rule is reproducible. In
   *  production, defaults to wallclock now. */
  now?: () => Date;
}): Promise<{ status: CheckStatus; details: Record<string, unknown> }> {
  const end = accountHealthCheckDurationSeconds.startTimer({ check_type: args.checkType });
  let result: CheckResult;
  try {
    result = await args.run();
  } catch (e) {
    end();
    const err = e instanceof Error ? e : new Error(String(e));
    log.warn("account_health_check_failed", {
      user_id: args.userId,
      check_type: args.checkType,
      message: err.message,
    });
    throw e;
  }
  end();

  if (result.status === "warning") {
    accountHealthWarningsTotal.inc({ check_type: args.checkType });
  } else if (result.status === "alert") {
    accountHealthAlertsTotal.inc({ check_type: args.checkType });
  }

  const at = args.now?.() ?? new Date();
  await db.insert(accountHealthCheck).values({
    userId: args.userId,
    checkType: args.checkType,
    status: result.status,
    details: result.details,
    correlationId: getCorrelationId() ?? null,
    checkedAt: at,
  });

  await updateState(args.userId, args.checkType, result, at);
  log.info("account_health_check", {
    user_id: args.userId,
    check_type: args.checkType,
    status: result.status,
  });
  return result;
}

async function updateState(
  userId: string,
  checkType: CheckType,
  result: CheckResult,
  now: Date,
): Promise<void> {
  const patch: Record<string, unknown> = { lastCheckRunAt: now };

  if (checkType === "shadowban") {
    if (result.status === "ok") {
      patch.shadowbanSuspectedAt = null;
    } else {
      // Only set the first-suspected-at the FIRST time we flag. Don't
      // overwrite an earlier timestamp with a newer one — that erases the
      // history of when the pattern started, which is what ops wants to see.
      const existing = await db
        .select({ at: accountHealthState.shadowbanSuspectedAt })
        .from(accountHealthState)
        .where(eq(accountHealthState.userId, userId));
      if (!existing[0]?.at) {
        patch.shadowbanSuspectedAt = now;
      }
    }
  }
  if (checkType === "karma_trend") {
    patch.lastKarmaCheckAt = now;
    const delta = result.details.delta_7d;
    if (typeof delta === "number") patch.karma7dDelta = Math.round(delta);
  }

  // Upsert. The state row may not exist yet for first-time users.
  await db
    .insert(accountHealthState)
    .values({ userId, ...patch })
    .onConflictDoUpdate({
      target: accountHealthState.userId,
      set: patch,
    });
}

/* ============================================================ */
/* READS                                                        */
/* ============================================================ */

export type AccountHealthSnapshot = {
  userId: string;
  shadowbanSuspectedAt: Date | null;
  lastKarmaCheckAt: Date | null;
  karma7dDelta: number | null;
  lastCheckRunAt: Date | null;
  // Most recent check per type — what the banner / ops table actually shows.
  latest: {
    shadowban?: { status: CheckStatus; checkedAt: Date; details: unknown };
    karma_trend?: { status: CheckStatus; checkedAt: Date; details: unknown };
    slow_removal?: { status: CheckStatus; checkedAt: Date; details: unknown };
  };
};

export async function getAccountHealthSnapshot(
  userId: string,
): Promise<AccountHealthSnapshot> {
  const stateRow = await db
    .select()
    .from(accountHealthState)
    .where(eq(accountHealthState.userId, userId));
  const state = stateRow[0];

  // Latest check per type. SQL is simpler than three round-trips.
  const latestRows = await db.execute(sql`
    SELECT DISTINCT ON (check_type)
      check_type, status, checked_at, details
    FROM account_health_check
    WHERE "userId" = ${userId}
    ORDER BY check_type, checked_at DESC
  `);
  const rows = extractRows(latestRows) as Array<{
    check_type: string;
    status: CheckStatus;
    checked_at: Date | string;
    details: unknown;
  }>;
  const latest: AccountHealthSnapshot["latest"] = {};
  for (const r of rows) {
    const key = r.check_type as CheckType;
    latest[key] = {
      status: r.status,
      checkedAt: r.checked_at instanceof Date ? r.checked_at : new Date(r.checked_at),
      details: r.details,
    };
  }

  return {
    userId,
    shadowbanSuspectedAt: state?.shadowbanSuspectedAt ?? null,
    lastKarmaCheckAt: state?.lastKarmaCheckAt ?? null,
    karma7dDelta: state?.karma7dDelta ?? null,
    lastCheckRunAt: state?.lastCheckRunAt ?? null,
    latest,
  };
}

/** Returns the highest severity across the three checks. `null` if no check
 *  has run yet (used by the banner: "no banner if no data"). */
export function highestSeverity(snapshot: AccountHealthSnapshot): CheckStatus | null {
  let worst: CheckStatus | null = null;
  for (const v of Object.values(snapshot.latest)) {
    if (!v) continue;
    if (v.status === "alert") return "alert";
    if (v.status === "warning") worst = "warning";
    if (v.status === "ok" && worst === null) worst = "ok";
  }
  return worst;
}

export async function getAllSnapshots(): Promise<AccountHealthSnapshot[]> {
  const all = await db
    .select({ userId: userProfiles.userId })
    .from(userProfiles);
  // O(N) round-trips — fine for an ops view at our scale. If this becomes
  // a hotspot, fold the latest-per-type query into a single SQL.
  const out: AccountHealthSnapshot[] = [];
  for (const u of all) {
    out.push(await getAccountHealthSnapshot(u.userId));
  }
  return out;
}

function extractRows(result: unknown): unknown[] {
  if (Array.isArray(result)) return result;
  if (
    result &&
    typeof result === "object" &&
    Array.isArray((result as { rows?: unknown[] }).rows)
  ) {
    return (result as { rows: unknown[] }).rows;
  }
  return [];
}

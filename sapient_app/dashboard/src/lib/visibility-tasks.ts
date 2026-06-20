/**
 * Integration layer between the dashboard's feed and the visibility service's
 * smart-tasks table. Visibility tasks are a SOURCE of opportunities — they go
 * through the same chokepoint (assertCanClaim / assertCanMarkPosted) as
 * organic finder opportunities. No new posting privileges.
 *
 * Reads `visibility.tasks` (declared read-only in src/db/schema.ts) and
 * writes only the four columns the contract owns: status, claimed_by_user_id,
 * claimed_at, dashboard_post_id.
 */
import { and, desc, eq, inArray, isNotNull } from "drizzle-orm";
import { db } from "@/db/client";
import {
  claims,
  opportunities,
  userActiveSubs,
  visibilityTasks,
} from "@/db/schema";
import { GuardrailError, claimOpportunity, reject } from "@/lib/guardrails";
import { log } from "@/lib/logging";

/**
 * Synthetic opportunity-id offset for visibility-sourced opportunities.
 * The finder writes integer ids starting at 1; we partition them by adding
 * 1B so visibility-synthesized rows can never collide with organic ones.
 * Postgres `integer` max is ~2.1B; this leaves room for ~1.1B visibility
 * tasks before we'd need to widen the column.
 */
export const VISIBILITY_OPP_ID_OFFSET = 1_000_000_000;

export function isRedditKind(kind: string): boolean {
  return kind.startsWith("reddit_");
}

export type EligibleVisibilityTasks = {
  reddit: (typeof visibilityTasks.$inferSelect)[];
  content: (typeof visibilityTasks.$inferSelect)[];
};

/**
 * Visibility-side feed query, gated server-side by the same active-sub +
 * expertise rules organic opportunities use. Resilient: any failure (schema
 * missing, connection refused, permission denied) returns `null` — the
 * caller decides whether to surface a notice or fail silent.
 */
export async function getEligibleVisibilityTasks(
  userId: string,
): Promise<EligibleVisibilityTasks | null> {
  try {
    const expertiseSubs = await db
      .select({ subreddit: userActiveSubs.subreddit })
      .from(userActiveSubs)
      .where(
        and(eq(userActiveSubs.userId, userId), eq(userActiveSubs.matchesExpertise, true)),
      );
    const eligibleSubs = expertiseSubs.map((s) => s.subreddit);

    const allOpen = await db
      .select()
      .from(visibilityTasks)
      .where(eq(visibilityTasks.status, "open"))
      .orderBy(desc(visibilityTasks.createdAt));

    const reddit = allOpen.filter(
      (t) =>
        isRedditKind(t.kind) &&
        t.suggestedSubreddit !== null &&
        eligibleSubs.includes(t.suggestedSubreddit),
    );
    const content = allOpen.filter((t) => !isRedditKind(t.kind));
    return { reddit, content };
  } catch (e) {
    // Schema not present, connection failure, permission denied, etc.
    // Caller (feed page or API route) decides whether to show a notice.
    return null;
  }
}

/**
 * Claim a reddit_* visibility task. Synthesizes an opportunity if no organic
 * one is linked, then routes through claimOpportunity — which runs ALL
 * existing guardrails (active-sub gate, expertise match, weekly cap). After
 * a successful claim, marks the visibility task `claimed`.
 *
 * Throws GuardrailError on any failure — same shape the organic flow uses,
 * so the UI can reuse its error rendering.
 */
export async function claimVisibilityTask(taskId: number, userId: string) {
  const task = await db.query.visibilityTasks.findFirst({
    where: eq(visibilityTasks.id, taskId),
  });
  if (!task) {
    reject("task_not_found", "visibility task not found");
  }
  if (task.status !== "open") {
    reject(
      "task_not_open",
      `visibility task is ${task.status}, not claimable`,
    );
  }
  if (!isRedditKind(task.kind)) {
    reject(
      "not_claimable_kind",
      `kind ${task.kind} has no posting flow; use the content tab`,
    );
  }
  if (!task.suggestedSubreddit) {
    reject(
      "no_suggested_subreddit",
      "task is missing suggested_subreddit; cannot gate against active subs",
    );
  }

  // Server-side re-validation of the suggested sub against user_active_sub —
  // the UI filter is advisory, this is authoritative.
  const active = await db.query.userActiveSubs.findFirst({
    where: and(
      eq(userActiveSubs.userId, userId),
      eq(userActiveSubs.subreddit, task.suggestedSubreddit),
    ),
  });
  if (!active) {
    reject(
      "not_preexisting_active",
      `user has no pre-existing activity in r/${task.suggestedSubreddit}`,
    );
  }
  if (!active.matchesExpertise) {
    reject(
      "not_expertise_match",
      `r/${task.suggestedSubreddit} is not marked as matching user expertise`,
    );
  }

  // Find or synthesize the opportunity row. If the visibility task already
  // links to a finder opportunity, use that. Otherwise synthesize one with
  // a partitioned id so claimOpportunity can run unchanged.
  const opportunityId =
    task.finderOpportunityId ?? VISIBILITY_OPP_ID_OFFSET + task.id;
  const existingOpp = await db.query.opportunities.findFirst({
    where: eq(opportunities.id, opportunityId),
  });
  if (!existingOpp) {
    await db.insert(opportunities).values({
      id: opportunityId,
      postId: `vis_${task.id}`,
      postUrl: task.relatedUrl ?? "",
      subreddit: task.suggestedSubreddit,
      title: task.recommendation.slice(0, 200),
      body: task.recommendation,
      score: 60,
      reason: task.recommendation,
      suggestedAngle: task.recommendation,
      status: "new",
      createdAt: new Date(),
    });
  }

  // Single chokepoint — same guardrails as organic claims (weekly cap fires
  // here for users at the limit, surfaces as code='weekly_cap').
  const claim = await claimOpportunity(userId, opportunityId, {
    source: "visibility",
    visibilityTaskId: task.id,
  });

  log.info("visibility_task_claim_writeback", {
    task_id: task.id,
    user_id: userId,
    target_schema: "visibility",
    target_table: "tasks",
  });
  await db
    .update(visibilityTasks)
    .set({
      status: "claimed",
      claimedByUserId: userId,
      claimedAt: new Date(),
    })
    .where(eq(visibilityTasks.id, task.id));

  return claim;
}

/** Called by /api/mark-posted after a successful post insert. No-op when the
 *  claim isn't visibility-sourced. Resilient: failures here don't unwind the
 *  user's posted record. We DO log every swallowed error — a stuck "claimed"
 *  task on the visibility side is invisible to ops otherwise. */
export async function markPostedFromVisibility(
  claimId: number,
  postId: number,
): Promise<void> {
  try {
    const [claim] = await db
      .select({
        source: claims.source,
        visibilityTaskId: claims.visibilityTaskId,
      })
      .from(claims)
      .where(eq(claims.id, claimId));
    if (!claim || claim.source !== "visibility" || claim.visibilityTaskId === null) {
      return;
    }
    log.info("visibility_task_posted_writeback", {
      task_id: claim.visibilityTaskId,
      claim_id: claimId,
      dashboard_post_id: postId,
      target_schema: "visibility",
      target_table: "tasks",
    });
    await db
      .update(visibilityTasks)
      .set({ status: "done", dashboardPostId: postId })
      .where(eq(visibilityTasks.id, claim.visibilityTaskId));
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    // Structured shape so log aggregators can extract the fields.
    console.warn("visibility writeback failed", {
      claimId,
      postId,
      exceptionClass: (err.constructor && err.constructor.name) || "Error",
      message: err.message,
    });
  }
}

/** Dismiss a task. Idempotent against repeats; valid from any state. The
 *  reason is persisted so ops can audit why suggestions are being rejected. */
export async function dismissVisibilityTask(
  taskId: number,
  reason?: string,
): Promise<void> {
  log.info("visibility_task_dismiss_writeback", {
    task_id: taskId,
    has_reason: !!reason,
    target_schema: "visibility",
    target_table: "tasks",
  });
  await db
    .update(visibilityTasks)
    .set({
      status: "dismissed",
      // Only overwrite when the caller supplied a reason; a re-dismiss
      // without one preserves the original.
      ...(reason ? { dismissReason: reason } : {}),
    })
    .where(eq(visibilityTasks.id, taskId));
}

/** By-id read. Returns the full row regardless of status, so the audit UI
 *  can show dismissed tasks with their captured reason. Resilient like the
 *  feed: returns null on any error. */
export async function getVisibilityTaskById(
  taskId: number,
): Promise<typeof visibilityTasks.$inferSelect | null> {
  try {
    const row = await db.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    return row ?? null;
  } catch {
    return null;
  }
}

/** Returns true when the dashboard's user has an `ops` role on their profile
 *  (so the feed should surface the "visibility tracker not configured" notice
 *  if the cross-schema read fails). All other users get a silent fallback. */
export async function isOpsUser(userId: string): Promise<boolean> {
  try {
    const row = await db.query.userProfiles.findFirst({
      where: (p, { eq }) => eq(p.userId, userId),
      columns: { role: true },
    });
    return row?.role === "ops";
  } catch {
    return false;
  }
}

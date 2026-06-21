/**
 * GDPR data export + right-to-erasure flows. Single endpoint pair per the
 * spec; the work fans out across the dashboard's own tables AND the
 * visibility schema.
 *
 * Atomicity model:
 *   - Export: read-only side. No transaction needed; we just snapshot.
 *   - Delete: one PG transaction wraps BOTH the dashboard tables and the
 *     visibility writes. Both schemas live in the same Postgres instance,
 *     so a single tx is both correct (no partial deletion) and simplest.
 *     If we ever shard visibility off, swap this to a saga / two-phase.
 *
 * Audit:
 *   - gdpr_request itself is the audit record. After a delete completes its
 *     userId is NULLed and erased=true is set. The row is queryable by id
 *     forever so we can answer "did we delete on 2026-09-01? show me".
 *   - receiptCorrelationId threads every log line for the request.
 */
import { randomUUID } from "node:crypto";
import { and, asc, eq, lte, sql } from "drizzle-orm";
import { db } from "@/db/client";
import {
  accountHealthCheck,
  accountHealthState,
  claims,
  contentDraftEvents,
  contentDraftQuota,
  contentDrafts,
  gdprRequests,
  karmaSnapshots,
  posts,
  userActiveSubs,
  userProfiles,
  users,
  visibilityTasks,
} from "@/db/schema";
import { log, runWithLogContext } from "./logging";
import {
  gdprRequestDurationSeconds,
  gdprRequestsTotal,
} from "./metrics";
import { uploadExportBundle, type ExportStorage } from "./gdpr-storage";

export type GdprKind = "export" | "delete";
export type GdprState =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "cancelled";

export const DELETE_GRACE_DAYS = Number(process.env.GDPR_DELETE_GRACE_DAYS ?? 30);

export class GdprStateError extends Error {
  code = "invalid_state" as const;
  constructor(message: string) {
    super(message);
  }
}

/* ============================================================ */
/* REQUEST CREATION                                             */
/* ============================================================ */

export type GdprRequestRow = {
  id: number;
  userId: string | null;
  kind: GdprKind;
  state: GdprState;
  requestedAt: Date;
  scheduledFor: Date;
  completedAt: Date | null;
  receiptCorrelationId: string;
  downloadUrl: string | null;
  erased: boolean;
  errorDetails: unknown;
};

function rowToTyped(r: typeof gdprRequests.$inferSelect): GdprRequestRow {
  return {
    id: r.id,
    userId: r.userId,
    kind: r.kind as GdprKind,
    state: r.state as GdprState,
    requestedAt: r.requestedAt,
    scheduledFor: r.scheduledFor,
    completedAt: r.completedAt,
    receiptCorrelationId: r.receiptCorrelationId,
    downloadUrl: r.downloadUrl,
    erased: r.erased,
    errorDetails: r.errorDetails,
  };
}

export async function createRequest(
  userId: string,
  kind: GdprKind,
  now: Date = new Date(),
): Promise<GdprRequestRow> {
  const scheduledFor =
    kind === "delete"
      ? new Date(now.getTime() + DELETE_GRACE_DAYS * 24 * 3600 * 1000)
      : now;
  const correlationId = randomUUID();
  const [row] = await db
    .insert(gdprRequests)
    .values({
      userId,
      kind,
      state: "pending",
      requestedAt: now,
      scheduledFor,
      receiptCorrelationId: correlationId,
    })
    .returning();
  log.info("gdpr_request_created", {
    correlation_id: correlationId,
    user_id: userId,
    kind,
    request_id: row.id,
    scheduled_for: scheduledFor.toISOString(),
  });
  return rowToTyped(row);
}

/* ============================================================ */
/* READS                                                        */
/* ============================================================ */

export async function getRequestById(id: number): Promise<GdprRequestRow | null> {
  const row = await db
    .select()
    .from(gdprRequests)
    .where(eq(gdprRequests.id, id))
    .limit(1);
  return row[0] ? rowToTyped(row[0]) : null;
}

export async function listUserRequests(userId: string): Promise<GdprRequestRow[]> {
  const rows = await db
    .select()
    .from(gdprRequests)
    .where(eq(gdprRequests.userId, userId))
    .orderBy(sql`requested_at DESC`);
  return rows.map(rowToTyped);
}

/* ============================================================ */
/* CANCEL                                                       */
/* ============================================================ */

export async function cancelRequest(
  id: number,
  args: { actorUserId: string; isOps: boolean; reason?: string },
): Promise<GdprRequestRow> {
  const existing = await getRequestById(id);
  if (!existing) throw new GdprStateError("request_not_found");
  if (existing.kind !== "delete") {
    throw new GdprStateError("cancel_only_valid_for_delete");
  }
  if (existing.state !== "pending") {
    // The deletion has already started or completed — no take-backs.
    throw new GdprStateError(`cannot_cancel_in_state_${existing.state}`);
  }
  if (!args.isOps && existing.userId !== args.actorUserId) {
    throw new GdprStateError("not_request_owner");
  }
  const [updated] = await db
    .update(gdprRequests)
    .set({
      state: "cancelled",
      completedAt: new Date(),
      errorDetails: args.reason ? { cancel_reason: args.reason } : null,
    })
    .where(eq(gdprRequests.id, id))
    .returning();

  recordTerminal(updated.kind as GdprKind, "cancelled", updated.requestedAt);
  log.info("gdpr_request_cancelled", {
    correlation_id: updated.receiptCorrelationId,
    request_id: id,
    actor_user_id: args.actorUserId,
    is_ops: args.isOps,
    reason: args.reason ?? null,
  });
  return rowToTyped(updated);
}

function recordTerminal(
  kind: GdprKind,
  state: "completed" | "failed" | "cancelled",
  requestedAt: Date,
): void {
  gdprRequestsTotal.inc({ kind, terminal_state: state });
  gdprRequestDurationSeconds.observe(
    { kind },
    (Date.now() - requestedAt.getTime()) / 1000,
  );
}

/* ============================================================ */
/* EXPORT                                                       */
/* ============================================================ */

export type ExportBundle = {
  exported_at: string;
  user_id: string;
  dashboard: {
    user: unknown;
    user_profile: unknown;
    user_active_sub: unknown[];
    claim: unknown[];
    post: unknown[];
    karma_snapshot: unknown[];
    content_draft: unknown[];
    content_draft_event: unknown[];
    content_draft_quota: unknown[];
    account_health_check: unknown[];
    account_health_state: unknown;
    gdpr_request: unknown[];
  };
  visibility: {
    tasks_claimed: unknown[];
  };
};

/**
 * Read-only collection of every row that references the user. Stored in a
 * stable shape so the bundle file can be re-read by tooling. Other users'
 * data is filtered server-side (every query is keyed on userId).
 */
export async function collectExportBundle(userId: string): Promise<ExportBundle> {
  const [user] = await db.select().from(users).where(eq(users.id, userId));
  const [profile] = await db
    .select()
    .from(userProfiles)
    .where(eq(userProfiles.userId, userId));
  const subs = await db.select().from(userActiveSubs).where(eq(userActiveSubs.userId, userId));
  const claimRows = await db.select().from(claims).where(eq(claims.userId, userId));
  const postRows = await db.select().from(posts).where(eq(posts.userId, userId));
  const karma = await db.select().from(karmaSnapshots).where(eq(karmaSnapshots.userId, userId));
  const drafts = await db.select().from(contentDrafts).where(eq(contentDrafts.userId, userId));
  const draftEvents = await db
    .select()
    .from(contentDraftEvents)
    .where(eq(contentDraftEvents.userId, userId));
  const draftQuota = await db
    .select()
    .from(contentDraftQuota)
    .where(eq(contentDraftQuota.userId, userId));
  const healthChecks = await db
    .select()
    .from(accountHealthCheck)
    .where(eq(accountHealthCheck.userId, userId));
  const [healthState] = await db
    .select()
    .from(accountHealthState)
    .where(eq(accountHealthState.userId, userId));
  const gdprRows = await db.select().from(gdprRequests).where(eq(gdprRequests.userId, userId));

  let tasksClaimed: unknown[] = [];
  try {
    tasksClaimed = await db
      .select()
      .from(visibilityTasks)
      .where(eq(visibilityTasks.claimedByUserId, userId));
  } catch (e) {
    // Visibility unreachable — bundle still represents what the dashboard
    // has. The route reports tasks_claimed as the empty list and ops can
    // re-run the export later.
    log.warn("gdpr_export_visibility_unreachable", {
      user_id: userId,
      message: e instanceof Error ? e.message : String(e),
    });
  }

  return {
    exported_at: new Date().toISOString(),
    user_id: userId,
    dashboard: {
      user: user ?? null,
      user_profile: profile ?? null,
      user_active_sub: subs,
      claim: claimRows,
      post: postRows,
      karma_snapshot: karma,
      content_draft: drafts,
      content_draft_event: draftEvents,
      content_draft_quota: draftQuota,
      account_health_check: healthChecks,
      account_health_state: healthState ?? null,
      gdpr_request: gdprRows,
    },
    visibility: { tasks_claimed: tasksClaimed },
  };
}

/**
 * Process an export request end-to-end. Designed to be safe to call from a
 * fire-and-forget POST handler (sets state, runs collection, uploads, sets
 * download_url). Returns the final request row.
 */
export async function processExport(
  request: GdprRequestRow,
  storage?: ExportStorage,
): Promise<GdprRequestRow> {
  if (!request.userId) {
    throw new GdprStateError("export_request_missing_user");
  }
  return runWithLogContext(
    { correlationId: request.receiptCorrelationId, userId: request.userId },
    async () => {
      await db
        .update(gdprRequests)
        .set({ state: "in_progress" })
        .where(eq(gdprRequests.id, request.id));
      log.info("gdpr_export_started", { request_id: request.id });

      try {
        const bundle = await collectExportBundle(request.userId!);
        const { url } = await uploadExportBundle(
          {
            requestId: request.id,
            userId: request.userId!,
            bundle,
            correlationId: request.receiptCorrelationId,
          },
          storage,
        );
        const completedAt = new Date();
        const [done] = await db
          .update(gdprRequests)
          .set({ state: "completed", completedAt, downloadUrl: url })
          .where(eq(gdprRequests.id, request.id))
          .returning();
        recordTerminal("export", "completed", request.requestedAt);
        log.info("gdpr_export_completed", {
          request_id: request.id,
          download_url_set: true,
        });
        return rowToTyped(done);
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        const [failed] = await db
          .update(gdprRequests)
          .set({
            state: "failed",
            completedAt: new Date(),
            errorDetails: { message: err.message, exception: err.constructor.name },
          })
          .where(eq(gdprRequests.id, request.id))
          .returning();
        recordTerminal("export", "failed", request.requestedAt);
        log.error("gdpr_export_failed", { request_id: request.id, message: err.message });
        return rowToTyped(failed);
      }
    },
  );
}

/* ============================================================ */
/* DELETE                                                       */
/* ============================================================ */

/**
 * Perform the actual deletion. Idempotent against re-runs of an already-
 * completed request (returns the existing row). All writes happen inside
 * a single transaction so a visibility-side failure leaves the dashboard
 * untouched.
 */
export async function processDelete(
  request: GdprRequestRow,
): Promise<GdprRequestRow> {
  if (request.state === "completed") return request;
  if (!request.userId) {
    throw new GdprStateError("delete_request_missing_user");
  }
  return runWithLogContext(
    { correlationId: request.receiptCorrelationId, userId: request.userId },
    async () => {
      await db
        .update(gdprRequests)
        .set({ state: "in_progress" })
        .where(eq(gdprRequests.id, request.id));
      log.info("gdpr_delete_started", { request_id: request.id });

      try {
        await db.transaction(async (tx) => {
          const userId = request.userId!;

          // Visibility first — if this fails, the surrounding tx rolls
          // everything back (dashboard rows stay intact).
          await tx
            .update(visibilityTasks)
            .set({ claimedByUserId: null })
            .where(eq(visibilityTasks.claimedByUserId, userId));

          // Dashboard tables. Order matters where FKs lack cascade — we
          // delete child rows before the parent user row.
          await tx.delete(contentDraftEvents).where(eq(contentDraftEvents.userId, userId));
          await tx.delete(contentDrafts).where(eq(contentDrafts.userId, userId));
          await tx.delete(contentDraftQuota).where(eq(contentDraftQuota.userId, userId));
          await tx.delete(posts).where(eq(posts.userId, userId));
          await tx.delete(claims).where(eq(claims.userId, userId));
          await tx.delete(karmaSnapshots).where(eq(karmaSnapshots.userId, userId));
          await tx.delete(userActiveSubs).where(eq(userActiveSubs.userId, userId));
          await tx.delete(accountHealthCheck).where(eq(accountHealthCheck.userId, userId));
          await tx.delete(accountHealthState).where(eq(accountHealthState.userId, userId));
          await tx.delete(userProfiles).where(eq(userProfiles.userId, userId));

          // Anonymize the auth row — set NULL on PII and tokens. Keeping
          // the id keeps existing FK targets satisfied (we use ON DELETE
          // SET NULL on gdpr_request.userId, but in-flight migrations may
          // not have applied it).
          await tx
            .update(users)
            .set({ email: null, name: null, image: null })
            .where(eq(users.id, userId));

          // Mark the request as erased BEFORE the surrounding update runs;
          // this keeps `erased=true` + `state=completed` consistent inside
          // the tx.
          await tx
            .update(gdprRequests)
            .set({
              state: "completed",
              completedAt: new Date(),
              erased: true,
              userId: null,
            })
            .where(eq(gdprRequests.id, request.id));
        });
        // Re-read after commit (the tx body already wrote state=completed
        // + userId=NULL, but the in-memory `request` object is stale).
        const [done] = await db
          .select()
          .from(gdprRequests)
          .where(eq(gdprRequests.id, request.id));
        recordTerminal("delete", "completed", request.requestedAt);
        log.info("gdpr_delete_completed", { request_id: request.id });
        return rowToTyped(done);
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        const [failed] = await db
          .update(gdprRequests)
          .set({
            state: "failed",
            completedAt: new Date(),
            errorDetails: { message: err.message, exception: err.constructor.name },
          })
          .where(eq(gdprRequests.id, request.id))
          .returning();
        recordTerminal("delete", "failed", request.requestedAt);
        log.error("gdpr_delete_failed", {
          request_id: request.id,
          message: err.message,
        });
        return rowToTyped(failed);
      }
    },
  );
}

/* ============================================================ */
/* SCHEDULER HELPERS                                            */
/* ============================================================ */

/**
 * Find delete requests past their grace period. Used by the scheduler tick
 * and exposed for tests that want to drive the worker deterministically.
 */
export async function findDueDeletes(now: Date = new Date()): Promise<GdprRequestRow[]> {
  const rows = await db
    .select()
    .from(gdprRequests)
    .where(
      and(
        eq(gdprRequests.kind, "delete"),
        eq(gdprRequests.state, "pending"),
        lte(gdprRequests.scheduledFor, now),
      ),
    )
    .orderBy(asc(gdprRequests.scheduledFor));
  return rows.map(rowToTyped);
}

/** Process every due delete request once. Returns the processed rows. */
export async function processDueDeletes(
  now: Date = new Date(),
): Promise<GdprRequestRow[]> {
  const due = await findDueDeletes(now);
  const out: GdprRequestRow[] = [];
  for (const r of due) {
    out.push(await processDelete(r));
  }
  return out;
}

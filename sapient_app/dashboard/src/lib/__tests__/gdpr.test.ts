import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { eq, sql } from "drizzle-orm";
import { createTestDb, pgFor, resetDb, type TestDb } from "./_helpers/db";
import {
  resetSeedCounters,
  seedActiveSub,
  seedUser,
  seedVisibilityTask,
} from "./_helpers/seed";
import {
  accountHealthCheck,
  claims,
  gdprRequests,
  karmaSnapshots,
  posts,
  userActiveSubs,
  userProfiles,
  visibilityTasks,
} from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let lib: typeof import("@/lib/gdpr");
let storage: typeof import("@/lib/gdpr-storage");

beforeAll(async () => {
  lib = await import("@/lib/gdpr");
  storage = await import("@/lib/gdpr-storage");
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
  storage.setDefaultStorage({
    put: async ({ requestId, userId }) => ({
      url: `mem://gdpr-${requestId}-${userId}`,
    }),
  });
});

afterEach(() => {
  storage.resetDefaultStorage();
});

/* ---------- helpers ---------- */

async function seedUserWithData(testDb: TestDb, id: string): Promise<void> {
  await seedUser(testDb, { id });
  await seedActiveSub(testDb, id, "sub1", true);
  const [claim] = await testDb
    .insert(claims)
    .values({ userId: id, opportunityId: hashIntegerForUser(id, 1), state: "posted" })
    .returning({ id: claims.id });
  await testDb.insert(posts).values({
    claimId: claim.id,
    userId: id,
    subreddit: "sub1",
    redditThingId: `t1_${id}`,
    permalink: "https://r/x",
    body: "post",
    mentionsProduct: false,
    includesDisclosure: false,
  });
  await testDb.insert(karmaSnapshots).values({
    userId: id,
    linkKarma: 100,
    commentKarma: 50,
  });
  await testDb.insert(accountHealthCheck).values({
    userId: id,
    checkType: "shadowban",
    status: "ok",
    details: {},
  });
}

// Stable per-user opportunity ids so two seeded users don't collide on
// opportunity_id (which is just an integer, not FK-checked here). Bounded
// well under int32 max so pglite accepts the insert.
function hashIntegerForUser(userId: string, idx: number): number {
  let h = 0;
  for (let i = 0; i < userId.length; i++) h = (h * 31 + userId.charCodeAt(i)) | 0;
  return (Math.abs(h) % 100_000) * 100 + idx;
}

/* ============================================================ */
/* EXPORT                                                       */
/* ============================================================ */

describe("export", () => {
  it("bundle includes all referenced tables", async () => {
    const u = "u_export";
    await seedUserWithData(testDb, u);

    const bundle = await lib.collectExportBundle(u);
    expect(bundle.user_id).toBe(u);
    expect(bundle.dashboard.user).not.toBeNull();
    expect(bundle.dashboard.user_active_sub.length).toBe(1);
    expect(bundle.dashboard.claim.length).toBe(1);
    expect(bundle.dashboard.post.length).toBe(1);
    expect(bundle.dashboard.karma_snapshot.length).toBe(1);
    expect(bundle.dashboard.account_health_check.length).toBe(1);
  });

  it("bundle excludes other users' data", async () => {
    const u1 = "u_alpha";
    const u2 = "u_bravo";
    await seedUserWithData(testDb, u1);
    await seedUserWithData(testDb, u2);

    const bundle = await lib.collectExportBundle(u1);
    // u1's bundle should only contain u1's rows.
    expect((bundle.dashboard.user as { id: string }).id).toBe(u1);
    expect((bundle.dashboard.claim as Array<{ userId: string }>).every((c) => c.userId === u1)).toBe(
      true,
    );
    expect((bundle.dashboard.post as Array<{ userId: string }>).every((p) => p.userId === u1)).toBe(
      true,
    );
  });

  it("processExport flips state to completed and persists download_url", async () => {
    const u = "u_proc";
    await seedUser(testDb, { id: u });
    const req = await lib.createRequest(u, "export");
    const done = await lib.processExport(req);
    expect(done.state).toBe("completed");
    expect(done.downloadUrl).toContain("mem://gdpr-");
    expect(done.completedAt).not.toBeNull();
  });

  it("processExport marks state=failed when storage throws", async () => {
    const u = "u_storage_fail";
    await seedUser(testDb, { id: u });
    const req = await lib.createRequest(u, "export");
    const done = await lib.processExport(req, {
      put: async () => {
        throw new Error("s3 timeout");
      },
    });
    expect(done.state).toBe("failed");
    expect((done.errorDetails as { message: string }).message).toBe("s3 timeout");
  });
});

/* ============================================================ */
/* DELETE                                                       */
/* ============================================================ */

describe("delete", () => {
  it("after grace, processDelete cascades dashboard rows and nulls visibility claim", async () => {
    const u = "u_del";
    await seedUserWithData(testDb, u);
    await seedVisibilityTask(testDb, { id: 5001, suggestedSubreddit: "sub1" });
    await testDb
      .update(visibilityTasks)
      .set({ claimedByUserId: u, status: "claimed", claimedAt: new Date() })
      .where(eq(visibilityTasks.id, 5001));

    const req = await lib.createRequest(u, "delete");
    const done = await lib.processDelete(req);

    expect(done.state).toBe("completed");
    expect(done.erased).toBe(true);
    // Audit row survives with userId nulled.
    expect(done.userId).toBeNull();

    // Dashboard rows gone.
    const subs = await testDb.select().from(userActiveSubs).where(eq(userActiveSubs.userId, u));
    expect(subs).toHaveLength(0);
    const claimsLeft = await testDb.select().from(claims).where(eq(claims.userId, u));
    expect(claimsLeft).toHaveLength(0);
    const profile = await testDb
      .select()
      .from(userProfiles)
      .where(eq(userProfiles.userId, u));
    expect(profile).toHaveLength(0);

    // Visibility row preserved with claimed_by_user_id nulled.
    const [task] = await testDb
      .select()
      .from(visibilityTasks)
      .where(eq(visibilityTasks.id, 5001));
    expect(task.claimedByUserId).toBeNull();
  });

  it("user_id stays NULLed in the surviving gdpr_request audit row", async () => {
    const u = "u_audit";
    await seedUser(testDb, { id: u });
    const req = await lib.createRequest(u, "delete");
    await lib.processDelete(req);

    // The completed request is queryable by id even after the user is gone.
    const fetched = await lib.getRequestById(req.id);
    expect(fetched).not.toBeNull();
    expect(fetched!.userId).toBeNull();
    expect(fetched!.erased).toBe(true);
    expect(fetched!.state).toBe("completed");
    expect(fetched!.receiptCorrelationId).toBe(req.receiptCorrelationId);
  });

  it("when visibility update fails, dashboard rows stay intact (no partial deletion)", async () => {
    const u = "u_partial";
    const otherUser = "u_intact";
    await seedUserWithData(testDb, u);
    await seedUserWithData(testDb, otherUser);

    // Sabotage the visibility schema mid-tx by dropping it BEFORE the run.
    // processDelete's transaction body will fail when it tries to write
    // visibility.tasks, rolling back the dashboard deletes too.
    await pgFor(testDb).exec("DROP SCHEMA visibility CASCADE");

    const req = await lib.createRequest(u, "delete");
    const done = await lib.processDelete(req);
    expect(done.state).toBe("failed");
    expect(done.errorDetails).not.toBeNull();

    // u's dashboard rows must still exist — the deletion was rolled back.
    const subs = await testDb.select().from(userActiveSubs).where(eq(userActiveSubs.userId, u));
    expect(subs.length).toBe(1);
    const profile = await testDb.select().from(userProfiles).where(eq(userProfiles.userId, u));
    expect(profile.length).toBe(1);

    // The other user's rows must also be intact (control).
    const otherSubs = await testDb
      .select()
      .from(userActiveSubs)
      .where(eq(userActiveSubs.userId, otherUser));
    expect(otherSubs.length).toBe(1);
  });
});

/* ============================================================ */
/* CANCEL                                                       */
/* ============================================================ */

describe("cancel", () => {
  it("cancel during pending → state=cancelled, no deletion runs", async () => {
    const u = "u_cancel";
    await seedUserWithData(testDb, u);
    const req = await lib.createRequest(u, "delete");
    const cancelled = await lib.cancelRequest(req.id, {
      actorUserId: u,
      isOps: false,
    });
    expect(cancelled.state).toBe("cancelled");

    // Dashboard data is intact — we never ran processDelete.
    const subs = await testDb.select().from(userActiveSubs).where(eq(userActiveSubs.userId, u));
    expect(subs.length).toBe(1);
  });

  it("cancel after deletion started → 409 (cannot cancel)", async () => {
    const u = "u_in_progress";
    await seedUser(testDb, { id: u });
    const req = await lib.createRequest(u, "delete");
    // Simulate the worker having picked it up.
    await testDb
      .update(gdprRequests)
      .set({ state: "in_progress" })
      .where(eq(gdprRequests.id, req.id));

    await expect(
      lib.cancelRequest(req.id, { actorUserId: u, isOps: false }),
    ).rejects.toThrow(/cannot_cancel_in_state_in_progress/);
  });

  it("cancel for an export request is rejected (only deletes are cancellable)", async () => {
    const u = "u_exp_cancel";
    await seedUser(testDb, { id: u });
    const req = await lib.createRequest(u, "export");
    await expect(
      lib.cancelRequest(req.id, { actorUserId: u, isOps: false }),
    ).rejects.toThrow(/cancel_only_valid_for_delete/);
  });

  it("non-owner cancel attempt is rejected with not_request_owner", async () => {
    const owner = "u_owner";
    const intruder = "u_intruder";
    await seedUser(testDb, { id: owner });
    await seedUser(testDb, { id: intruder });
    const req = await lib.createRequest(owner, "delete");
    await expect(
      lib.cancelRequest(req.id, { actorUserId: intruder, isOps: false }),
    ).rejects.toThrow(/not_request_owner/);
  });

  it("ops can cancel anyone's delete with a logged reason", async () => {
    const owner = "u_anyone";
    await seedUser(testDb, { id: owner });
    const req = await lib.createRequest(owner, "delete");
    const cancelled = await lib.cancelRequest(req.id, {
      actorUserId: "u_ops",
      isOps: true,
      reason: "user reached out by email",
    });
    expect(cancelled.state).toBe("cancelled");
    expect((cancelled.errorDetails as { cancel_reason: string }).cancel_reason).toBe(
      "user reached out by email",
    );
  });
});

/* ============================================================ */
/* SCHEDULER                                                    */
/* ============================================================ */

describe("scheduler", () => {
  it("findDueDeletes picks up requests past their scheduled_for and skips future ones", async () => {
    const u1 = "u_due";
    const u2 = "u_not_yet";
    await seedUser(testDb, { id: u1 });
    await seedUser(testDb, { id: u2 });

    const now = new Date("2026-08-01T00:00:00Z");
    // u1's request is overdue.
    await testDb.insert(gdprRequests).values({
      userId: u1,
      kind: "delete",
      state: "pending",
      requestedAt: new Date("2026-07-01"),
      scheduledFor: new Date("2026-07-31"),
      receiptCorrelationId: "c1",
    });
    // u2's request is in the future.
    await testDb.insert(gdprRequests).values({
      userId: u2,
      kind: "delete",
      state: "pending",
      requestedAt: now,
      scheduledFor: new Date("2026-09-01"),
      receiptCorrelationId: "c2",
    });
    const due = await lib.findDueDeletes(now);
    expect(due.map((r) => r.userId)).toEqual([u1]);
  });

  it("processDueDeletes runs every due request to completion", async () => {
    const u1 = "u_run1";
    const u2 = "u_run2";
    await seedUserWithData(testDb, u1);
    await seedUserWithData(testDb, u2);
    const now = new Date();
    const ago = new Date(now.getTime() - 24 * 3600 * 1000);
    await testDb.insert(gdprRequests).values([
      {
        userId: u1,
        kind: "delete",
        state: "pending",
        requestedAt: ago,
        scheduledFor: ago,
        receiptCorrelationId: "r1",
      },
      {
        userId: u2,
        kind: "delete",
        state: "pending",
        requestedAt: ago,
        scheduledFor: ago,
        receiptCorrelationId: "r2",
      },
    ]);
    const processed = await lib.processDueDeletes(now);
    expect(processed.length).toBe(2);
    expect(processed.every((r) => r.state === "completed")).toBe(true);
    expect(processed.every((r) => r.erased)).toBe(true);
  });
});

/* ============================================================ */
/* CREATE                                                       */
/* ============================================================ */

describe("createRequest", () => {
  it("delete request has scheduledFor = requestedAt + 30d", async () => {
    const u = "u_grace";
    await seedUser(testDb, { id: u });
    const now = new Date("2026-08-15T12:00:00Z");
    const req = await lib.createRequest(u, "delete", now);
    const expected = now.getTime() + 30 * 24 * 3600 * 1000;
    expect(req.scheduledFor.getTime()).toBe(expected);
  });

  it("export request schedules immediately", async () => {
    const u = "u_now";
    await seedUser(testDb, { id: u });
    const now = new Date("2026-08-15T12:00:00Z");
    const req = await lib.createRequest(u, "export", now);
    expect(req.scheduledFor.getTime()).toBe(now.getTime());
  });

  it("every request gets a unique correlation_id", async () => {
    const u = "u_corr";
    await seedUser(testDb, { id: u });
    const a = await lib.createRequest(u, "export");
    const b = await lib.createRequest(u, "export");
    expect(a.receiptCorrelationId).not.toBe(b.receiptCorrelationId);
  });
});

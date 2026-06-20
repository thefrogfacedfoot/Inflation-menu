/**
 * Coverage for src/lib/content-gap.ts — the 8 cases from the feature spec:
 *
 *   1. generate creates one draft + increments user's daily counter
 *   2. generate at daily cap → rate_limited
 *   3. partial-unique violation on second generate → ActiveDraftExistsError
 *      with the existing draftId
 *   4. patch updates body + bumps updated_at + recomputes edit_markers when
 *      the user resolves a [VERIFY]
 *   5. mark-edited with edit_markers > 0 → succeeds + returns warning payload
 *   6. mark-edited with edit_markers = 0 → succeeds, clean
 *   7. publish writes published_url + flips visibility.tasks.status=done +
 *      inserts a content_draft_event
 *   8. archive excludes from subsequent list reads + allows new generation
 *      for the same task
 *
 * The LLM is injected (stub returns deterministic markdown with one
 * [VERIFY] marker). No network calls.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { and, eq } from "drizzle-orm";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters, seedUser, seedVisibilityTask } from "./_helpers/seed";
import {
  contentDraftEvents,
  contentDraftQuota,
  contentDrafts,
  visibilityTasks,
} from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let lib: typeof import("@/lib/content-gap");

beforeAll(async () => {
  lib = await import("@/lib/content-gap");
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

afterEach(() => {
  vi.useRealTimers();
});

/** Stub LLM. Returns a draft with exactly one [VERIFY] marker so the
 *  edit-markers counter has something to work with. */
function stubLLM(overrides?: {
  title?: string;
  body?: string;
}): import("@/lib/content-gap").LLMClient {
  return {
    async generate() {
      return {
        title: overrides?.title ?? "Test draft title",
        body:
          overrides?.body ??
          "# Test draft title\n\nWe shipped widgets last quarter [VERIFY: exact ship date?].",
      };
    },
  };
}

async function generateBlogTask(): Promise<{
  userId: string;
  taskId: number;
}> {
  const userId = await seedUser(testDb);
  const taskId = await seedVisibilityTask(testDb, {
    kind: "blog_post",
    suggestedSubreddit: null,
    relatedUrl: null,
    recommendation: "Write a long post on widget alternatives",
  });
  return { userId, taskId };
}

/* -------- 1. generate creates a draft + bumps counter -------- */

describe("generateDraft — happy path", () => {
  it("creates one draft and increments the user's daily counter", async () => {
    const { userId, taskId } = await generateBlogTask();
    const result = await lib.generateDraft(taskId, userId, { llm: stubLLM() });

    expect(result.draftId).toBeGreaterThan(0);
    expect(result.draft.status).toBe("draft");
    expect(result.draft.editMarkersCount).toBe(1);
    expect(result.draft.title).toBe("Test draft title");

    const drafts = await testDb.select().from(contentDrafts);
    expect(drafts).toHaveLength(1);
    expect(drafts[0].visibilityTaskId).toBe(taskId);
    expect(drafts[0].userId).toBe(userId);
    expect(drafts[0].editMarkersCount).toBe(1);
    expect(drafts[0].targetQuery).toContain("widget alternatives");

    // Counter: one row at count=1 for today.
    const today = new Date().toISOString().slice(0, 10);
    const quota = await testDb
      .select()
      .from(contentDraftQuota)
      .where(
        and(
          eq(contentDraftQuota.userId, userId),
          eq(contentDraftQuota.day, today),
        ),
      );
    expect(quota).toHaveLength(1);
    expect(quota[0].count).toBe(1);

    // Audit: one event, null → draft.
    const events = await testDb
      .select()
      .from(contentDraftEvents)
      .where(eq(contentDraftEvents.draftId, result.draftId));
    expect(events).toHaveLength(1);
    expect(events[0].fromStatus).toBeNull();
    expect(events[0].toStatus).toBe("draft");
  });
});

/* -------- 2. generate at daily cap -------- */

describe("generateDraft — rate limit", () => {
  it("rejects with RateLimitedError once the user is at the daily cap", async () => {
    const userId = await seedUser(testDb);
    // Pre-seed the quota row at the cap. The cap default is 5.
    const today = new Date().toISOString().slice(0, 10);
    await testDb
      .insert(contentDraftQuota)
      .values({ userId, day: today, count: lib.__test.DAILY_GENERATION_CAP });

    const taskId = await seedVisibilityTask(testDb, {
      kind: "blog_post",
      suggestedSubreddit: null,
      relatedUrl: null,
      recommendation: "Another blog post",
    });

    await expect(
      lib.generateDraft(taskId, userId, { llm: stubLLM() }),
    ).rejects.toBeInstanceOf(lib.RateLimitedError);

    // No draft persisted.
    const drafts = await testDb.select().from(contentDrafts);
    expect(drafts).toHaveLength(0);
  });
});

/* -------- 3. partial-unique violation -> ActiveDraftExistsError -------- */

describe("generateDraft — duplicate active draft", () => {
  it("second generate for the same task → ActiveDraftExistsError carrying the existing id", async () => {
    const { userId, taskId } = await generateBlogTask();
    const first = await lib.generateDraft(taskId, userId, { llm: stubLLM() });

    let err: unknown = null;
    try {
      await lib.generateDraft(taskId, userId, { llm: stubLLM() });
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(lib.ActiveDraftExistsError);
    expect((err as InstanceType<typeof lib.ActiveDraftExistsError>).existingDraftId).toBe(
      first.draftId,
    );
    expect(
      (err as InstanceType<typeof lib.ActiveDraftExistsError>).code,
    ).toBe("active_draft_exists");

    // Counter did NOT advance on the duplicate attempt.
    const today = new Date().toISOString().slice(0, 10);
    const quota = await testDb
      .select()
      .from(contentDraftQuota)
      .where(eq(contentDraftQuota.userId, userId));
    expect(quota[0].day).toBe(today);
    expect(quota[0].count).toBe(1);
  });
});

/* -------- 4. patch updates body, bumps updated_at, recomputes markers -------- */

describe("patchDraft", () => {
  it("updates body, bumps updated_at, recomputes edit_markers when the user resolves a [VERIFY]", async () => {
    const { userId, taskId } = await generateBlogTask();
    const created = await lib.generateDraft(taskId, userId, {
      llm: stubLLM({
        body:
          "# T\n\nClaim A [VERIFY: source?]. Claim B [VERIFY: needs cite].",
      }),
    });
    expect(created.draft.editMarkersCount).toBe(2);

    const originalUpdatedAt = (
      await testDb.query.contentDrafts.findFirst({
        where: eq(contentDrafts.id, created.draftId),
      })
    )?.updatedAt;
    expect(originalUpdatedAt).toBeInstanceOf(Date);

    // Jump the clock so updated_at changes observably.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.now() + 5_000));

    const patched = await lib.patchDraft(created.draftId, userId, {
      body: "# T\n\nClaim A is shipped 2026-04-01. Claim B [VERIFY: needs cite].",
    });

    expect(patched.editMarkersCount).toBe(1);
    expect(patched.updatedAt.getTime()).toBeGreaterThan(
      originalUpdatedAt!.getTime(),
    );
    expect(patched.body).toContain("2026-04-01");
  });
});

/* -------- 5 + 6. mark-edited with markers > 0 (warning) and = 0 (clean) -------- */

describe("markEdited", () => {
  it("returns a warning payload when edit_markers > 0", async () => {
    const { userId, taskId } = await generateBlogTask();
    const created = await lib.generateDraft(taskId, userId, { llm: stubLLM() });
    expect(created.draft.editMarkersCount).toBe(1);

    const { draft, warning } = await lib.markEdited(created.draftId, userId);
    expect(draft.status).toBe("edited");
    expect(warning).not.toBeNull();
    expect(warning!.code).toBe("unresolved_verify_markers");
    expect(warning!.count).toBe(1);

    // Event row records the transition.
    const events = await testDb
      .select()
      .from(contentDraftEvents)
      .where(eq(contentDraftEvents.draftId, created.draftId));
    expect(events.find((e) => e.fromStatus === "draft" && e.toStatus === "edited"))
      .toBeDefined();
  });

  it("returns clean (no warning) when edit_markers = 0", async () => {
    const { userId, taskId } = await generateBlogTask();
    const created = await lib.generateDraft(taskId, userId, {
      llm: stubLLM({ body: "# T\n\nNo markers here, all verified facts." }),
    });
    expect(created.draft.editMarkersCount).toBe(0);

    const { draft, warning } = await lib.markEdited(created.draftId, userId);
    expect(draft.status).toBe("edited");
    expect(warning).toBeNull();
  });
});

/* -------- 7. publish writes URL + flips visibility task + writes event -------- */

describe("publish", () => {
  it("writes published_url, flips visibility.tasks.status=done, dashboard_content_draft_id, and writes an event", async () => {
    const { userId, taskId } = await generateBlogTask();
    const created = await lib.generateDraft(taskId, userId, {
      llm: stubLLM({ body: "# Final\n\nAll claims verified, ready to ship." }),
    });
    await lib.markEdited(created.draftId, userId);

    const url = "https://blog.example.com/widget-alternatives";
    const published = await lib.publish(created.draftId, userId, url);

    expect(published.status).toBe("published");
    expect(published.publishedUrl).toBe(url);
    expect(published.publishedAt).toBeInstanceOf(Date);

    // Visibility task is closed.
    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("done");
    expect(task?.dashboardContentDraftId).toBe(created.draftId);

    // Event for edited → published exists.
    const events = await testDb
      .select()
      .from(contentDraftEvents)
      .where(eq(contentDraftEvents.draftId, created.draftId));
    expect(
      events.find(
        (e) => e.fromStatus === "edited" && e.toStatus === "published",
      ),
    ).toBeDefined();
  });
});

/* -------- 8. archive excludes from list + allows new generation -------- */

describe("archive", () => {
  it("excludes from listActiveDrafts AND allows a new generation for the same task", async () => {
    const { userId, taskId } = await generateBlogTask();
    const first = await lib.generateDraft(taskId, userId, { llm: stubLLM() });

    // Archive it.
    const archived = await lib.archive(first.draftId, userId);
    expect(archived.status).toBe("archived");

    // listActiveDrafts no longer returns it.
    const active = await lib.listActiveDrafts(userId);
    expect(active.find((d) => d.id === first.draftId)).toBeUndefined();

    // New generation for the SAME task succeeds (partial unique idx
    // ignores archived rows).
    const second = await lib.generateDraft(taskId, userId, { llm: stubLLM() });
    expect(second.draftId).not.toBe(first.draftId);

    // Now active list has exactly the new draft.
    const active2 = await lib.listActiveDrafts(userId);
    expect(active2.map((d) => d.id)).toEqual([second.draftId]);
  });
});

/* -------- Per-(task, user) active-draft isolation -------- */

describe("active-draft uniqueness is scoped per user", () => {
  async function seedBlogTask(): Promise<number> {
    return seedVisibilityTask(testDb, {
      kind: "blog_post",
      suggestedSubreddit: null,
      relatedUrl: null,
      recommendation: "Write a long post on widget alternatives",
    });
  }

  it("User A and User B can both generate active drafts for the same task", async () => {
    const userA = await seedUser(testDb);
    const userB = await seedUser(testDb);
    const taskId = await seedBlogTask();

    const a = await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    const b = await lib.generateDraft(taskId, userB, { llm: stubLLM() });

    expect(a.draftId).not.toBe(b.draftId);

    const drafts = await testDb.select().from(contentDrafts);
    expect(drafts).toHaveLength(2);
    expect(new Set(drafts.map((d) => d.userId))).toEqual(
      new Set([userA, userB]),
    );
  });

  it("User A generating twice for the same task → ActiveDraftExistsError with A's existing draftId", async () => {
    const userA = await seedUser(testDb);
    const taskId = await seedBlogTask();

    const first = await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    let err: unknown = null;
    try {
      await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    } catch (e) {
      err = e;
    }
    expect(err).toBeInstanceOf(lib.ActiveDraftExistsError);
    expect(
      (err as InstanceType<typeof lib.ActiveDraftExistsError>).existingDraftId,
    ).toBe(first.draftId);
  });

  it("User A archives, then generates again → new draft id; another user's draft was unaffected", async () => {
    const userA = await seedUser(testDb);
    const userB = await seedUser(testDb);
    const taskId = await seedBlogTask();

    const a1 = await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    const bDraft = await lib.generateDraft(taskId, userB, { llm: stubLLM() });
    await lib.archive(a1.draftId, userA);

    const a2 = await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    expect(a2.draftId).not.toBe(a1.draftId);
    expect(a2.draftId).not.toBe(bDraft.draftId);

    // B's draft is still the same, still active.
    const bAfter = await testDb.query.contentDrafts.findFirst({
      where: eq(contentDrafts.id, bDraft.draftId),
    });
    expect(bAfter?.status).toBe("draft");
  });

  it("listActiveDrafts is scoped per user — A sees only A's, B sees only B's", async () => {
    const userA = await seedUser(testDb);
    const userB = await seedUser(testDb);
    const taskId = await seedBlogTask();

    const a = await lib.generateDraft(taskId, userA, { llm: stubLLM() });
    const b = await lib.generateDraft(taskId, userB, { llm: stubLLM() });

    const aList = await lib.listActiveDrafts(userA);
    const bList = await lib.listActiveDrafts(userB);

    expect(aList.map((d) => d.id)).toEqual([a.draftId]);
    expect(bList.map((d) => d.id)).toEqual([b.draftId]);
  });
});

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { and, eq, sql } from "drizzle-orm";
import { createTestDb, pgFor, resetDb, type TestDb } from "./_helpers/db";
import {
  resetSeedCounters,
  seedActiveSub,
  seedAliases,
  seedUser,
  seedVisibilityTask,
  setOpsRole,
} from "./_helpers/seed";
import { claims, posts, visibilityTasks } from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let lib: typeof import("@/lib/visibility-tasks");
let guardrails: typeof import("@/lib/guardrails");
let clearAliasCache: () => void;

beforeAll(async () => {
  lib = await import("@/lib/visibility-tasks");
  guardrails = await import("@/lib/guardrails");
  clearAliasCache = (await import("@/lib/product-detect"))._clearAliasCache;
});

const SUB = "widgets";

async function setupEligibleUser(): Promise<string> {
  await seedAliases(testDb, ["Acme", "acmewidget.com"]);
  const userId = await seedUser(testDb);
  await seedActiveSub(testDb, userId, SUB, true);
  return userId;
}

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
  clearAliasCache();
});

afterEach(() => {
  clearAliasCache();
});

describe("getEligibleVisibilityTasks", () => {
  it("returns reddit tasks only for subs the user matches as expertise", async () => {
    const userId = await setupEligibleUser();
    const tInEligible = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const tInOther = await seedVisibilityTask(testDb, { suggestedSubreddit: "other" });

    const result = await lib.getEligibleVisibilityTasks(userId);
    expect(result).not.toBeNull();
    expect(result!.reddit.map((t) => t.id)).toEqual([tInEligible]);
    expect(result!.reddit.find((t) => t.id === tInOther)).toBeUndefined();
  });

  it("puts non-reddit kinds in the content tab and bypasses the sub gate", async () => {
    const userId = await setupEligibleUser();
    const blog = await seedVisibilityTask(testDb, {
      kind: "blog_post",
      suggestedSubreddit: null,
      relatedUrl: null,
      recommendation: "Write a long post on widget alternatives",
    });
    const result = await lib.getEligibleVisibilityTasks(userId);
    expect(result!.content.map((t) => t.id)).toEqual([blog]);
    expect(result!.reddit).toHaveLength(0);
  });

  it("excludes non-open statuses", async () => {
    const userId = await setupEligibleUser();
    await seedVisibilityTask(testDb, { suggestedSubreddit: SUB, status: "dismissed" });
    await seedVisibilityTask(testDb, { suggestedSubreddit: SUB, status: "claimed" });
    const visibleId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const result = await lib.getEligibleVisibilityTasks(userId);
    expect(result!.reddit.map((t) => t.id)).toEqual([visibleId]);
  });

  it("returns null (resilient) when the visibility schema is unreachable", async () => {
    const userId = await setupEligibleUser();
    // Simulate "schema doesn't exist" by dropping it.
    await testDb.execute(sql`DROP SCHEMA visibility CASCADE`);
    const result = await lib.getEligibleVisibilityTasks(userId);
    expect(result).toBeNull();
  });

  it("isOpsUser flags ops accounts", async () => {
    const userId = await setupEligibleUser();
    expect(await lib.isOpsUser(userId)).toBe(false);
    await setOpsRole(testDb, userId);
    expect(await lib.isOpsUser(userId)).toBe(true);
  });
});

describe("claimVisibilityTask — routed through the same guardrails", () => {
  it("eligible reddit_* task → opportunity_claim created, task status=claimed", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const claim = await lib.claimVisibilityTask(taskId, userId);

    expect(claim.source).toBe("visibility");
    expect(claim.visibilityTaskId).toBe(taskId);
    expect(claim.state).toBe("claimed");

    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("claimed");
    expect(task?.claimedByUserId).toBe(userId);
    expect(task?.claimedAt).not.toBeNull();

    // Synthesized opportunity must exist for the rest of the flow to work.
    const oppId = lib.VISIBILITY_OPP_ID_OFFSET + taskId;
    const claimRow = await testDb.query.claims.findFirst({ where: eq(claims.id, claim.id) });
    expect(claimRow?.opportunityId).toBe(oppId);
  });

  it("INELIGIBLE sub → rejected with the same error code organic flow uses", async () => {
    const userId = await setupEligibleUser();
    // Task in a sub the user is NOT active in.
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: "stranger" });

    await expect(lib.claimVisibilityTask(taskId, userId)).rejects.toMatchObject({
      code: "not_preexisting_active",
    });

    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("open"); // unchanged
  });

  it("sub present but matchesExpertise=false → not_expertise_match", async () => {
    await seedAliases(testDb, ["Acme"]);
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, /*matches*/ false);
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });

    await expect(lib.claimVisibilityTask(taskId, userId)).rejects.toMatchObject({
      code: "not_expertise_match",
    });
  });

  it("user at weekly cap → rejected with weekly_cap, task stays open", async () => {
    const userId = await setupEligibleUser();
    // Seed three product-mentioning posts in the last week (cap = 3).
    for (let i = 0; i < 3; i++) {
      const [claim] = await testDb
        .insert(claims)
        .values({ userId, opportunityId: 9_000_000 + i, state: "posted" })
        .returning({ id: claims.id });
      await testDb.insert(posts).values({
        claimId: claim.id,
        userId,
        subreddit: SUB,
        redditThingId: `t1_cap${i}`,
        permalink: "https://r/x",
        body: "Acme blah",
        mentionsProduct: true,
        includesDisclosure: true,
      });
    }

    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    await expect(lib.claimVisibilityTask(taskId, userId)).rejects.toMatchObject({
      code: "weekly_cap_reached",
    });

    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("open");
  });

  it("blog_post / non-reddit kind → not claimable from the claim endpoint", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, {
      kind: "blog_post",
      suggestedSubreddit: null,
      relatedUrl: null,
    });
    await expect(lib.claimVisibilityTask(taskId, userId)).rejects.toMatchObject({
      code: "not_claimable_kind",
    });
  });
});

describe("mark-posted hook (markPostedFromVisibility)", () => {
  async function claimAndReturnClaimId(userId: string, taskId: number) {
    const claim = await lib.claimVisibilityTask(taskId, userId);
    return claim.id;
  }

  it("on a synthesized opportunity → task.status=done, dashboardPostId set", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const claimId = await claimAndReturnClaimId(userId, taskId);

    // Simulate the mark-posted route: insert post then call the hook.
    const [post] = await testDb
      .insert(posts)
      .values({
        claimId,
        userId,
        subreddit: SUB,
        redditThingId: "t1_mp1",
        permalink: "https://reddit.com/x/mp1",
        body: "helpful response",
        mentionsProduct: false,
        includesDisclosure: false,
      })
      .returning({ id: posts.id });
    await testDb.update(claims).set({ state: "posted" }).where(eq(claims.id, claimId));
    await lib.markPostedFromVisibility(claimId, post.id);

    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("done");
    expect(task?.dashboardPostId).toBe(post.id);
  });

  it("product mention without disclosure → disclosure_required, task stays claimed, no post", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const claim = await lib.claimVisibilityTask(taskId, userId);

    const oppId = lib.VISIBILITY_OPP_ID_OFFSET + taskId;

    await expect(
      guardrails.assertCanMarkPosted({
        userId,
        opportunityId: oppId,
        subreddit: SUB,
        redditThingId: "t1_disc",
        permalink: "https://reddit.com/x/disc",
        body: "You should really try Acme, it's great",
      }),
    ).rejects.toMatchObject({ code: "disclosure_required" });

    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("claimed");
    const postRows = await testDb.select().from(posts).where(eq(posts.claimId, claim.id));
    expect(postRows).toHaveLength(0);
  });

  it("is a no-op for organic claims (no visibilityTaskId)", async () => {
    const userId = await setupEligibleUser();
    // Manually insert an organic claim — no visibility task linked.
    const [claim] = await testDb
      .insert(claims)
      .values({ userId, opportunityId: 12345, state: "posted", source: "organic" })
      .returning({ id: claims.id });
    // No visibility task exists — markPostedFromVisibility must not throw.
    await expect(lib.markPostedFromVisibility(claim.id, 42)).resolves.toBeUndefined();
  });

  it("swallowed writeback failure is logged once with structured payload", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });
    const claim = await lib.claimVisibilityTask(taskId, userId);

    // Simulate visibility outage by dropping the schema. The UPDATE inside
    // markPostedFromVisibility will throw; the function must NOT re-throw,
    // but MUST log a structured warning.
    await pgFor(testDb).exec("DROP SCHEMA visibility CASCADE");

    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      await expect(lib.markPostedFromVisibility(claim.id, 99)).resolves.toBeUndefined();
      expect(warnSpy).toHaveBeenCalledTimes(1);
      const [msg, payload] = warnSpy.mock.calls[0];
      expect(msg).toBe("visibility writeback failed");
      expect(payload).toMatchObject({
        claimId: claim.id,
        postId: 99,
        exceptionClass: expect.any(String),
        message: expect.any(String),
      });
      expect((payload as { exceptionClass: string }).exceptionClass).not.toBe("");
      expect((payload as { message: string }).message.length).toBeGreaterThan(0);
    } finally {
      warnSpy.mockRestore();
    }
  });
});

describe("dismissVisibilityTask", () => {
  it("sets status=dismissed and excludes from subsequent eligibility queries", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });

    await lib.dismissVisibilityTask(taskId);
    const task = await testDb.query.visibilityTasks.findFirst({
      where: eq(visibilityTasks.id, taskId),
    });
    expect(task?.status).toBe("dismissed");

    const result = await lib.getEligibleVisibilityTasks(userId);
    expect(result!.reddit.find((t) => t.id === taskId)).toBeUndefined();
  });

  it("persists the reason; feed excludes the task but by-id read returns it with reason", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });

    await lib.dismissVisibilityTask(taskId, "not relevant");

    // Feed excludes it (open-only).
    const feed = await lib.getEligibleVisibilityTasks(userId);
    expect(feed!.reddit.find((t) => t.id === taskId)).toBeUndefined();

    // By-id read returns it with the captured reason.
    const byId = await lib.getVisibilityTaskById(taskId);
    expect(byId).not.toBeNull();
    expect(byId!.status).toBe("dismissed");
    expect(byId!.dismissReason).toBe("not relevant");
  });

  it("re-dismiss without a reason preserves the original reason", async () => {
    const userId = await setupEligibleUser();
    const taskId = await seedVisibilityTask(testDb, { suggestedSubreddit: SUB });

    await lib.dismissVisibilityTask(taskId, "original reason");
    await lib.dismissVisibilityTask(taskId); // no reason this time

    const byId = await lib.getVisibilityTaskById(taskId);
    expect(byId!.dismissReason).toBe("original reason");
  });
});

describe("DDL splitter (audit)", () => {
  it("applies multi-statement DDL with a DO $$ block containing semicolons in strings", async () => {
    // The point: a naive ';' splitter would chop the INSERTs below into
    // fragments because of the semicolons inside the string literal AND the
    // dollar-quoted body. We route through PGlite.exec() which uses the
    // simple query protocol and lets the Postgres parser handle it.
    const pg = pgFor(testDb);
    await pg.exec(`
      DROP TABLE IF EXISTS public.splitter_marker;
      CREATE TABLE public.splitter_marker (note text);
      DO $$
      BEGIN
        INSERT INTO public.splitter_marker (note) VALUES ('semis ; ; inside');
        INSERT INTO public.splitter_marker (note) VALUES ('one;two;three');
      END
      $$;
      INSERT INTO public.splitter_marker (note) VALUES ('after-block');
    `);

    const result = await pg.query<{ note: string }>(
      `SELECT note FROM public.splitter_marker ORDER BY note`,
    );
    expect(result.rows.map((r) => r.note).sort()).toEqual(
      ["after-block", "one;two;three", "semis ; ; inside"].sort(),
    );

    // And resetDb still works after this — proving the helper handles the
    // same shape it's now using internally.
    await expect(resetDb(testDb)).resolves.toBeUndefined();
  });
});

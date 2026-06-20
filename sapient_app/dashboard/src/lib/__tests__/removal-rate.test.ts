import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { eq } from "drizzle-orm";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters, seedActiveSub, seedUser } from "./_helpers/seed";
import { claims, posts, userProfiles } from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let enforceRemovalRate: typeof import("@/lib/guardrails").enforceRemovalRate;

beforeAll(async () => {
  enforceRemovalRate = (await import("@/lib/guardrails")).enforceRemovalRate;
});

const SUB = "ratesub";

async function insertPost(userId: string, idx: number, isRemoved: boolean): Promise<void> {
  const [claim] = await testDb
    .insert(claims)
    .values({ userId, opportunityId: 800_000 + idx, state: "posted" })
    .returning({ id: claims.id });
  await testDb.insert(posts).values({
    claimId: claim.id,
    userId,
    subreddit: SUB,
    redditThingId: `t1_rt${idx}`,
    permalink: "https://r/x",
    body: "post",
    mentionsProduct: false,
    includesDisclosure: false,
    isRemoved,
    // Stagger postedAt so the "last 10" ordering is deterministic.
    postedAt: new Date(Date.now() - idx * 60_000),
  });
}

async function makePosts(userId: string, removedCount: number, total = 10): Promise<void> {
  for (let i = 0; i < total; i++) {
    await insertPost(userId, i, i < removedCount);
  }
}

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

describe("removal-rate auto-pause (threshold = 20%, window = 10)", () => {
  it("2/10 removed = exactly 20% → allowed (not paused)", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await makePosts(userId, 2);

    const result = await enforceRemovalRate(userId);
    expect(result.paused).toBe(false);
    expect(result.rate).toBeCloseTo(0.2);

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile?.isPaused).toBe(false);
  });

  it("3/10 removed = 30% → paused with pausedCode=removal_rate_exceeded", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await makePosts(userId, 3);

    const result = await enforceRemovalRate(userId);
    expect(result.paused).toBe(true);
    expect(result.rate).toBeCloseTo(0.3);

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile?.isPaused).toBe(true);
    expect(profile?.pausedCode).toBe("removal_rate_exceeded");
  });

  it("fewer than 10 posts → no decision, not paused", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await makePosts(userId, 5, 9); // 5/9 = 55% but only 9 posts → too few to judge

    const result = await enforceRemovalRate(userId);
    expect(result.paused).toBe(false);
    expect(result.windowSize).toBe(9);

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile?.isPaused).toBe(false);
  });
});

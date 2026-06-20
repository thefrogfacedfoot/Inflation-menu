import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { eq } from "drizzle-orm";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters, seedActiveSub, seedUser } from "./_helpers/seed";
import { claims, posts, userProfiles } from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let assertWeeklyPromoCap: typeof import("@/lib/guardrails").assertWeeklyPromoCap;
let GuardrailError: typeof import("@/lib/guardrails").GuardrailError;

beforeAll(async () => {
  const guardrails = await import("@/lib/guardrails");
  assertWeeklyPromoCap = guardrails.assertWeeklyPromoCap;
  GuardrailError = guardrails.GuardrailError;
});

const SUB = "weeklysub";

async function insertPromoPost(userId: string, daysAgo: number): Promise<void> {
  const [claim] = await testDb
    .insert(claims)
    .values({ userId, opportunityId: 999_000 + Math.floor(Math.random() * 1000), state: "posted" })
    .returning({ id: claims.id });
  await testDb.insert(posts).values({
    claimId: claim.id,
    userId,
    subreddit: SUB,
    redditThingId: `t1_${Math.random().toString(36).slice(2, 10)}`,
    permalink: "https://r/x",
    body: "test",
    mentionsProduct: true,
    includesDisclosure: true,
    postedAt: new Date(Date.now() - daysAgo * 24 * 3600 * 1000),
  });
}

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
  vi.useRealTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("weekly promo cap (cap = 3)", () => {
  it("3 posts at -1d/-3d/-6d → next attempt blocked and user paused", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await insertPromoPost(userId, 1);
    await insertPromoPost(userId, 3);
    await insertPromoPost(userId, 6);

    await expect(assertWeeklyPromoCap(userId)).rejects.toBeInstanceOf(GuardrailError);

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile?.isPaused).toBe(true);
    expect(profile?.pausedCode).toBe("weekly_cap_reached");
  });

  it("after the -6d post falls out of the 7d window, next attempt is allowed", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await insertPromoPost(userId, 1);
    await insertPromoPost(userId, 3);
    await insertPromoPost(userId, 6);

    // Advance system clock by 2 days. The -6d post is now -8d, outside the
    // 7-day window, leaving only 2 posts inside → under the cap.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.now() + 2 * 24 * 3600 * 1000));

    await expect(assertWeeklyPromoCap(userId)).resolves.toBeUndefined();
  });

  it("under the cap → does not pause", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, SUB, true);
    await insertPromoPost(userId, 1);
    await insertPromoPost(userId, 3);

    await expect(assertWeeklyPromoCap(userId)).resolves.toBeUndefined();

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile?.isPaused).toBe(false);
  });
});

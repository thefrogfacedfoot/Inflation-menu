import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters, seedActiveSub, seedOpportunity, seedUser } from "./_helpers/seed";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let claimOpportunity: typeof import("@/lib/guardrails").claimOpportunity;
let GuardrailError: typeof import("@/lib/guardrails").GuardrailError;

beforeAll(async () => {
  const guardrails = await import("@/lib/guardrails");
  claimOpportunity = guardrails.claimOpportunity;
  GuardrailError = guardrails.GuardrailError;
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

describe("claim race", () => {
  it("two users claiming the same opportunity simultaneously — exactly one wins", async () => {
    const userA = await seedUser(testDb);
    const userB = await seedUser(testDb);
    const SUB = "racesub";
    await seedActiveSub(testDb, userA, SUB, true);
    await seedActiveSub(testDb, userB, SUB, true);
    const oppId = await seedOpportunity(testDb, { subreddit: SUB });

    const results = await Promise.allSettled([
      claimOpportunity(userA, oppId),
      claimOpportunity(userB, oppId),
    ]);

    const fulfilled = results.filter((r) => r.status === "fulfilled");
    const rejected = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];
    expect(fulfilled).toHaveLength(1);
    expect(rejected).toHaveLength(1);

    const err = rejected[0].reason;
    expect(err).toBeInstanceOf(GuardrailError);
    expect(err.code).toBe("already_claimed");
  });

  it("the losing user can still claim a different opportunity", async () => {
    const userA = await seedUser(testDb);
    const userB = await seedUser(testDb);
    const SUB = "racesub";
    await seedActiveSub(testDb, userA, SUB, true);
    await seedActiveSub(testDb, userB, SUB, true);
    const opp1 = await seedOpportunity(testDb, { subreddit: SUB });
    const opp2 = await seedOpportunity(testDb, { subreddit: SUB });

    await claimOpportunity(userA, opp1);
    await claimOpportunity(userB, opp2);

    await expect(claimOpportunity(userA, opp2)).rejects.toMatchObject({
      code: "already_claimed",
    });
  });
});

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { seedActiveSub, seedAliases, seedOpportunity, seedUser, resetSeedCounters } from "./_helpers/seed";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

// Import AFTER vi.mock so the module resolves against the mocked db.
let assertCanMarkPosted: typeof import("@/lib/guardrails").assertCanMarkPosted;
let GuardrailError: typeof import("@/lib/guardrails").GuardrailError;
let clearAliasCache: () => void;

beforeAll(async () => {
  const guardrails = await import("@/lib/guardrails");
  assertCanMarkPosted = guardrails.assertCanMarkPosted;
  GuardrailError = guardrails.GuardrailError;
  clearAliasCache = (await import("@/lib/product-detect"))._clearAliasCache;
});

const SUB = "testsub";

async function setup(): Promise<string> {
  await seedAliases(testDb, ["Acme", "acmewidget.com"]);
  const userId = await seedUser(testDb);
  await seedActiveSub(testDb, userId, SUB, true);
  await seedOpportunity(testDb, { id: 1, subreddit: SUB });
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

describe("assertCanMarkPosted — disclosure gate", () => {
  it("rejects when product is mentioned but no disclosure phrase is present", async () => {
    const userId = await setup();
    await expect(
      assertCanMarkPosted({
        userId,
        opportunityId: 1,
        subreddit: SUB,
        redditThingId: "t1_abc",
        permalink: "https://r/x",
        body: "Acme is great, give it a try.",
      }),
    ).rejects.toMatchObject({
      code: "disclosure_required",
    });
  });

  it("includes matchedAliases and acceptedDisclosurePhrases in the error payload", async () => {
    const userId = await setup();
    let captured: InstanceType<typeof GuardrailError> | null = null;
    try {
      await assertCanMarkPosted({
        userId,
        opportunityId: 1,
        subreddit: SUB,
        redditThingId: "t1_abc",
        permalink: "https://r/x",
        body: "Acme is great",
      });
    } catch (e) {
      if (e instanceof GuardrailError) captured = e;
    }
    expect(captured).not.toBeNull();
    expect(captured!.payload.matchedAliases).toEqual(["Acme"]);
    expect(Array.isArray(captured!.payload.acceptedDisclosurePhrases)).toBe(true);
    expect((captured!.payload.acceptedDisclosurePhrases as string[]).length).toBeGreaterThan(0);
  });

  it("allows when alias is present AND a disclosure phrase is present", async () => {
    const userId = await setup();
    const result = await assertCanMarkPosted({
      userId,
      opportunityId: 1,
      subreddit: SUB,
      redditThingId: "t1_abc",
      permalink: "https://r/x",
      body: "Disclosure: I work on Acme. Here's what we do.",
    });
    expect(result.mentionsProduct).toBe(true);
    expect(result.includesDisclosure).toBe(true);
    expect(result.matchedAliases).toEqual(["Acme"]);
    expect(result.acceptedDisclosurePhrases).toContain("disclosure:");
    expect(result.acceptedDisclosurePhrases).toContain("i work on");
  });

  it("allows posts that do not mention the product, regardless of disclosure", async () => {
    const userId = await setup();
    const result = await assertCanMarkPosted({
      userId,
      opportunityId: 1,
      subreddit: SUB,
      redditThingId: "t1_abc",
      permalink: "https://r/x",
      body: "Generic helpful comment with no brand reference.",
    });
    expect(result.mentionsProduct).toBe(false);
    expect(result.includesDisclosure).toBe(false);
  });

  it("self-reported mention forces the disclosure check even when detector misses", async () => {
    const userId = await setup();
    await expect(
      assertCanMarkPosted({
        userId,
        opportunityId: 1,
        subreddit: SUB,
        redditThingId: "t1_abc",
        permalink: "https://r/x",
        body: "Our thing helps with this — you might check it out.",
        selfReportedMentionsProduct: true,
      }),
    ).rejects.toMatchObject({ code: "disclosure_required" });
  });

  it("self-reported mention + disclosure phrase passes", async () => {
    const userId = await setup();
    const result = await assertCanMarkPosted({
      userId,
      opportunityId: 1,
      subreddit: SUB,
      redditThingId: "t1_abc",
      permalink: "https://r/x",
      body: "I'm one of the makers of an alternative — happy to chat.",
      selfReportedMentionsProduct: true,
    });
    expect(result.mentionsProduct).toBe(true);
    expect(result.includesDisclosure).toBe(true);
  });
});

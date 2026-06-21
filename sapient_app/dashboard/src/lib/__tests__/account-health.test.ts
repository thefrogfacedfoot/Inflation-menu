import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { eq } from "drizzle-orm";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import {
  resetSeedCounters,
  seedActiveSub,
  seedUser,
} from "./_helpers/seed";
import {
  accountHealthCheck,
  accountHealthState,
  claims,
  karmaSnapshots,
  posts,
} from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let lib: typeof import("@/lib/account-health");

beforeAll(async () => {
  lib = await import("@/lib/account-health");
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

/* ---------- shadowban ---------- */

function mkShadowbanDeps(
  authed: { subs: number; comments: number },
  anon: { subs: number; comments: number },
  now = new Date(),
) {
  return {
    fetchAuthed: async () => ({
      link_karma: 100,
      comment_karma: 100,
      visibleSubmissions: authed.subs,
      visibleComments: authed.comments,
    }),
    fetchAnon: async () => ({
      link_karma: 100,
      comment_karma: 100,
      visibleSubmissions: anon.subs,
      visibleComments: anon.comments,
    }),
    now: () => now,
  };
}

describe("shadowban detection", () => {
  it("matched counts → ok", async () => {
    const userId = await seedUser(testDb);
    const result = await lib.checkShadowban(
      userId,
      "u",
      mkShadowbanDeps({ subs: 20, comments: 30 }, { subs: 20, comments: 30 }),
    );
    expect(result.status).toBe("ok");
  });

  it("30% gap once → warning, no alert", async () => {
    const userId = await seedUser(testDb);
    const deps = mkShadowbanDeps(
      { subs: 100, comments: 100 },
      { subs: 50, comments: 50 }, // 50% gap > 30% threshold
    );
    const result = await lib.runCheck({
      userId,
      checkType: "shadowban",
      run: () => lib.checkShadowban(userId, "u", deps),
    });
    expect(result.status).toBe("warning");

    // State row reflects the warning but no alert yet.
    const state = await testDb
      .select()
      .from(accountHealthState)
      .where(eq(accountHealthState.userId, userId));
    expect(state[0].shadowbanSuspectedAt).not.toBeNull();
  });

  it("30% gap two checks in a row (≥24h apart) → alert", async () => {
    const userId = await seedUser(testDb);
    const t0 = new Date("2026-01-01T00:00:00Z");
    const t1 = new Date("2026-01-02T01:00:00Z"); // 25h later

    await lib.runCheck({
      userId,
      checkType: "shadowban",
      run: () => lib.checkShadowban(
        userId,
        "u",
        mkShadowbanDeps({ subs: 100, comments: 100 }, { subs: 50, comments: 50 }, t0),
      ),
      now: () => t0,
    });
    const second = await lib.runCheck({
      userId,
      checkType: "shadowban",
      run: () => lib.checkShadowban(
        userId,
        "u",
        mkShadowbanDeps({ subs: 100, comments: 100 }, { subs: 50, comments: 50 }, t1),
      ),
      now: () => t1,
    });
    expect(second.status).toBe("alert");
  });

  it("anomaly then ok clears the state row's shadowbanSuspectedAt", async () => {
    const userId = await seedUser(testDb);
    await lib.runCheck({
      userId,
      checkType: "shadowban",
      run: () => lib.checkShadowban(
        userId,
        "u",
        mkShadowbanDeps({ subs: 100, comments: 100 }, { subs: 50, comments: 50 }),
      ),
    });
    await lib.runCheck({
      userId,
      checkType: "shadowban",
      run: () => lib.checkShadowban(
        userId,
        "u",
        mkShadowbanDeps({ subs: 100, comments: 100 }, { subs: 100, comments: 100 }),
      ),
    });
    const state = await testDb
      .select()
      .from(accountHealthState)
      .where(eq(accountHealthState.userId, userId));
    expect(state[0].shadowbanSuspectedAt).toBeNull();
  });
});

/* ---------- karma trend ---------- */

async function insertKarmaSnapshot(userId: string, total: number, takenAt: Date) {
  await testDb.insert(karmaSnapshots).values({
    userId,
    takenAt,
    linkKarma: total,
    commentKarma: 0,
  });
}

function mkKarmaDeps(current: number, now: Date) {
  return {
    fetchCurrentKarma: async () => ({ link_karma: current, comment_karma: 0 }),
    now: () => now,
  };
}

describe("karma trend", () => {
  it("-50 absolute in 7d → warning", async () => {
    const userId = await seedUser(testDb);
    const now = new Date("2026-01-15T00:00:00Z");
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    await insertKarmaSnapshot(userId, 1000, sevenDaysAgo);

    const result = await lib.checkKarmaTrend(userId, mkKarmaDeps(940, now));
    expect(result.status).toBe("warning");
  });

  it("sustained 14d → alert", async () => {
    const userId = await seedUser(testDb);
    const now = new Date("2026-01-20T00:00:00Z");
    const fourteenDaysAgo = new Date(now.getTime() - 14 * 24 * 3600 * 1000);
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    // 14d-ago: 1000. 7d-ago: 960. now: 900. So 7d delta = -60 (breach),
    // 14d delta = -100 (breach). Sustained → alert.
    await insertKarmaSnapshot(userId, 1000, fourteenDaysAgo);
    await insertKarmaSnapshot(userId, 960, sevenDaysAgo);

    const result = await lib.checkKarmaTrend(userId, mkKarmaDeps(900, now));
    expect(result.status).toBe("alert");
  });

  it("+50 in 7d → ok", async () => {
    const userId = await seedUser(testDb);
    const now = new Date("2026-01-15T00:00:00Z");
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    await insertKarmaSnapshot(userId, 1000, sevenDaysAgo);

    const result = await lib.checkKarmaTrend(userId, mkKarmaDeps(1050, now));
    expect(result.status).toBe("ok");
  });
});

/* ---------- slow-burn removals ---------- */

async function makePost(
  userId: string,
  idx: number,
  isRemoved: boolean,
  postedAt: Date,
): Promise<void> {
  const [claim] = await testDb
    .insert(claims)
    .values({ userId, opportunityId: 900_000 + idx, state: "posted" })
    .returning({ id: claims.id });
  await testDb.insert(posts).values({
    claimId: claim.id,
    userId,
    subreddit: "sub",
    redditThingId: `t1_sb${idx}`,
    permalink: "https://r/x",
    body: "body",
    mentionsProduct: false,
    includesDisclosure: false,
    isRemoved,
    postedAt,
  });
}

describe("slow-burn removal", () => {
  it("4/30 removals evenly spaced over 25 days → alert (slow burn)", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, "sub", true);
    // 30 posts total; 4 of them removed, spaced ~7 days apart over 25 days.
    // Non-removed posts fill in around them. Std-dev of removal diffs is
    // dominated by the ~7-day gaps → well above threshold (3 days).
    const dayMs = 24 * 3600 * 1000;
    const baseTime = new Date("2026-02-15T00:00:00Z").getTime();
    const removalIndexes = new Set<number>([0, 8, 16, 24]);
    for (let i = 0; i < 30; i++) {
      // Stagger so post 0 is most recent, post 29 oldest (matches DESC order).
      const postedAt = new Date(baseTime - i * dayMs);
      await makePost(userId, i, removalIndexes.has(i), postedAt);
    }

    const result = await lib.checkSlowBurnRemoval(userId, { now: () => new Date(baseTime) });
    expect(result.status).toBe("alert");
    expect((result.details as { rate: number }).rate).toBeCloseTo(4 / 30);
  });

  it("4/10 in 2 days (burst pattern) → ok (caught by existing 20% trigger, not this check)", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, "sub", true);
    // 30 posts total. 4 removed, all within a 2-day window (tight cluster).
    // The other 26 posts spread over a long history. Std-dev of removal
    // diffs is small → this check classifies as "burst caught elsewhere".
    const baseTime = new Date("2026-02-15T00:00:00Z").getTime();
    const hourMs = 3600 * 1000;
    const dayMs = 24 * 3600 * 1000;
    // 4 removed posts within a 12h cluster (recent end).
    for (let i = 0; i < 4; i++) {
      await makePost(userId, i, true, new Date(baseTime - i * hourMs * 3));
    }
    // 26 non-removed posts spread back over weeks.
    for (let i = 4; i < 30; i++) {
      await makePost(userId, i, false, new Date(baseTime - (i + 4) * dayMs));
    }

    const result = await lib.checkSlowBurnRemoval(userId, { now: () => new Date(baseTime) });
    expect(result.status).toBe("ok");
    expect((result.details as { classified_as?: string }).classified_as).toBe(
      "burst_caught_elsewhere",
    );
  });

  it("under window size → ok with insufficient_history", async () => {
    const userId = await seedUser(testDb);
    await seedActiveSub(testDb, userId, "sub", true);
    for (let i = 0; i < 5; i++) {
      await makePost(userId, i, i === 0, new Date(Date.now() - i * 86400_000));
    }
    const result = await lib.checkSlowBurnRemoval(userId, { now: () => new Date() });
    expect(result.status).toBe("ok");
    expect((result.details as { insufficient_history?: boolean }).insufficient_history).toBe(true);
  });
});

/* ---------- snapshots / aggregate ---------- */

describe("snapshots", () => {
  it("getAccountHealthSnapshot returns latest per type", async () => {
    const userId = await seedUser(testDb);
    // Two shadowban checks; the snapshot should expose only the latest.
    await testDb.insert(accountHealthCheck).values([
      {
        userId,
        checkType: "shadowban",
        status: "ok",
        details: { a: 1 },
        checkedAt: new Date("2026-01-01"),
      },
      {
        userId,
        checkType: "shadowban",
        status: "warning",
        details: { a: 2 },
        checkedAt: new Date("2026-01-02"),
      },
    ]);
    const snap = await lib.getAccountHealthSnapshot(userId);
    expect(snap.latest.shadowban?.status).toBe("warning");
    expect(lib.highestSeverity(snap)).toBe("warning");
  });

  it("getAllSnapshots returns one per user", async () => {
    const u1 = await seedUser(testDb);
    const u2 = await seedUser(testDb);
    await testDb.insert(accountHealthCheck).values([
      { userId: u1, checkType: "shadowban", status: "ok", details: {} },
      { userId: u2, checkType: "shadowban", status: "alert", details: {} },
    ]);
    const all = await lib.getAllSnapshots();
    const byUser = new Map(all.map((s) => [s.userId, s]));
    expect(byUser.size).toBe(2);
    expect(lib.highestSeverity(byUser.get(u1)!)).toBe("ok");
    expect(lib.highestSeverity(byUser.get(u2)!)).toBe("alert");
  });
});

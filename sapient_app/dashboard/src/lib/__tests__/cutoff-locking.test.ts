import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { and, eq } from "drizzle-orm";
import { createTestDb, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters } from "./_helpers/seed";
import { userActiveSubs, userProfiles } from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

// Controllable history feed for syncUserHistory.
type HistoryItem = { kind: "submitted" | "comments"; subreddit: string; created_utc: number };
const _historyQueue: HistoryItem[][] = [];

vi.mock("@/lib/reddit", () => ({
  getMe: vi.fn(async () => ({
    name: "alice",
    created_utc: 1_000_000,
    link_karma: 100,
    comment_karma: 100,
  })),
  iterUserHistory: vi.fn(async function* () {
    const items = _historyQueue.shift() ?? [];
    for (const item of items) yield item;
  }),
}));

let syncUserHistory: typeof import("@/lib/onboarding").syncUserHistory;

beforeAll(async () => {
  syncUserHistory = (await import("@/lib/onboarding")).syncUserHistory;
});

const T1 = new Date("2025-01-01T12:00:00Z");
const T2 = new Date("2025-03-01T12:00:00Z");
const utc = (d: Date) => Math.floor(d.getTime() / 1000);

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
  _historyQueue.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("preexisting-cutoff locking", () => {
  it("activity after the locked cutoff never marks the user active in a new sub", async () => {
    const userId = "alice-uid";
    await testDb.insert((await import("@/db/schema")).users).values({
      id: userId,
      email: "alice@example.test",
    });

    // First sync at T1: only pre-T1 activity in r/foo and r/bar.
    vi.useFakeTimers();
    vi.setSystemTime(T1);
    _historyQueue.push([
      { kind: "submitted", subreddit: "foo", created_utc: utc(T1) - 30 * 86_400 },
      { kind: "comments", subreddit: "foo", created_utc: utc(T1) - 20 * 86_400 },
      { kind: "comments", subreddit: "bar", created_utc: utc(T1) - 10 * 86_400 },
    ]);
    await syncUserHistory(userId);

    let subs = await testDb
      .select({ subreddit: userActiveSubs.subreddit })
      .from(userActiveSubs)
      .where(eq(userActiveSubs.userId, userId));
    expect(new Set(subs.map((s) => s.subreddit))).toEqual(new Set(["foo", "bar"]));

    const profile = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    // Cutoff must be locked at T1.
    expect(profile?.preexistingCutoff?.toISOString()).toBe(T1.toISOString());

    // Second sync at T2: same pre-T1 items PLUS new post-T1 activity in r/baz.
    vi.setSystemTime(T2);
    _historyQueue.push([
      { kind: "submitted", subreddit: "foo", created_utc: utc(T1) - 30 * 86_400 },
      { kind: "comments", subreddit: "foo", created_utc: utc(T1) - 20 * 86_400 },
      { kind: "comments", subreddit: "bar", created_utc: utc(T1) - 10 * 86_400 },
      // Post-cutoff activity — must NOT make user active in r/baz.
      { kind: "submitted", subreddit: "baz", created_utc: utc(T1) + 86_400 },
      { kind: "submitted", subreddit: "baz", created_utc: utc(T2) - 86_400 },
    ]);
    await syncUserHistory(userId);

    subs = await testDb
      .select({ subreddit: userActiveSubs.subreddit })
      .from(userActiveSubs)
      .where(eq(userActiveSubs.userId, userId));
    expect(new Set(subs.map((s) => s.subreddit))).toEqual(new Set(["foo", "bar"]));
    expect(subs.find((s) => s.subreddit === "baz")).toBeUndefined();

    // Cutoff still locked at T1 — never moved forward.
    const profile2 = await testDb.query.userProfiles.findFirst({
      where: eq(userProfiles.userId, userId),
    });
    expect(profile2?.preexistingCutoff?.toISOString()).toBe(T1.toISOString());
  });

  it("activity exactly at the cutoff (created_utc === cutoff) is treated as post-cutoff", async () => {
    const userId = "bob-uid";
    await testDb.insert((await import("@/db/schema")).users).values({
      id: userId,
      email: "bob@example.test",
    });

    vi.useFakeTimers();
    vi.setSystemTime(T1);
    _historyQueue.push([
      // exactly at cutoff — strict `<` excludes it
      { kind: "submitted", subreddit: "edge", created_utc: utc(T1) },
    ]);
    await syncUserHistory(userId);

    const subs = await testDb
      .select()
      .from(userActiveSubs)
      .where(and(eq(userActiveSubs.userId, userId), eq(userActiveSubs.subreddit, "edge")));
    expect(subs).toHaveLength(0);
  });
});

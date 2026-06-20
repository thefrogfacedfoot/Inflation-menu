import { eq } from "drizzle-orm";
import {
  opportunities,
  productAliases,
  userActiveSubs,
  userProfiles,
  users,
  visibilityTasks,
} from "@/db/schema";
import type { TestDb } from "./db";

let opportunityCounter = 1;
let userCounter = 1;
let visibilityTaskCounter = 1;

export function resetSeedCounters(): void {
  opportunityCounter = 1;
  userCounter = 1;
  visibilityTaskCounter = 1;
}

export async function seedUser(
  db: TestDb,
  opts: { id?: string; cutoff?: Date } = {},
): Promise<string> {
  const id = opts.id ?? `u_${userCounter++}`;
  await db.insert(users).values({ id, email: `${id}@example.test` });
  await db.insert(userProfiles).values({
    userId: id,
    redditUsername: id,
    preexistingCutoff: opts.cutoff ?? new Date(),
    expertiseTags: [],
  });
  return id;
}

export async function seedActiveSub(
  db: TestDb,
  userId: string,
  subreddit: string,
  matches = true,
): Promise<void> {
  await db.insert(userActiveSubs).values({
    userId,
    subreddit,
    matchesExpertise: matches,
    postCount: 5,
    commentCount: 5,
  });
}

export async function seedOpportunity(
  db: TestDb,
  opts: { subreddit?: string; score?: number; id?: number } = {},
): Promise<number> {
  const id = opts.id ?? opportunityCounter++;
  const subreddit = opts.subreddit ?? "testsub";
  await db.insert(opportunities).values({
    id,
    postId: `pid_${id}`,
    postUrl: `https://reddit.com/r/${subreddit}/comments/${id}`,
    subreddit,
    title: "test opportunity",
    body: "test body",
    score: opts.score ?? 70,
    reason: "test reason",
    suggestedAngle: "test angle",
    status: "new",
    createdAt: new Date(),
  });
  return id;
}

export async function seedAliases(db: TestDb, aliases: string[]): Promise<void> {
  if (aliases.length === 0) return;
  await db.insert(productAliases).values(
    aliases.map((alias, i) => ({ alias, isPrimary: i === 0 })),
  );
}

export async function setOpsRole(db: TestDb, userId: string): Promise<void> {
  await db
    .update(userProfiles)
    .set({ role: "ops" })
    .where(eq(userProfiles.userId, userId));
}

export type VisibilityTaskSeed = {
  id?: number;
  kind?: string;
  queryId?: number;
  suggestedSubreddit?: string | null;
  relatedUrl?: string | null;
  recommendation?: string;
  status?: string;
  finderOpportunityId?: number | null;
};

export async function seedVisibilityTask(
  db: TestDb,
  opts: VisibilityTaskSeed = {},
): Promise<number> {
  const id = opts.id ?? visibilityTaskCounter++;
  const kind = opts.kind ?? "reddit_top_voted_answer";
  const suggestedSubreddit =
    opts.suggestedSubreddit === undefined ? "testsub" : opts.suggestedSubreddit;
  await db.insert(visibilityTasks).values({
    id,
    kind,
    queryId: opts.queryId ?? 1,
    suggestedSubreddit,
    relatedUrl:
      opts.relatedUrl === undefined
        ? `https://reddit.com/r/${suggestedSubreddit ?? "x"}/comments/${id}`
        : opts.relatedUrl,
    recommendation: opts.recommendation ?? `do the thing for task ${id}`,
    finderOpportunityId: opts.finderOpportunityId ?? null,
    status: opts.status ?? "open",
    createdAt: new Date(),
  });
  return id;
}

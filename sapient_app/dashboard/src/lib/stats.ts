import { and, desc, eq, gte, sql } from "drizzle-orm";
import { db } from "@/db/client";
import { claims, karmaSnapshots, posts } from "@/db/schema";

export type UserStats = {
  claimed: number;
  posted: number;
  upvotesLast30d: number;
  removalRate: number;
  removalWindow: number;
  karma: { takenAt: Date; total: number }[];
};

export async function getUserStats(userId: string): Promise<UserStats> {
  const since30 = new Date(Date.now() - 30 * 24 * 3600 * 1000);

  const claimAgg = await db
    .select({
      claimed: sql<number>`count(*) filter (where state = 'claimed')::int`,
      posted: sql<number>`count(*) filter (where state = 'posted')::int`,
    })
    .from(claims)
    .where(eq(claims.userId, userId));

  const upvoteAgg = await db
    .select({ upvotes: sql<number>`coalesce(sum(${posts.upvotes}), 0)::int` })
    .from(posts)
    .where(and(eq(posts.userId, userId), gte(posts.postedAt, since30)));

  const recent = await db
    .select({ isRemoved: posts.isRemoved })
    .from(posts)
    .where(eq(posts.userId, userId))
    .orderBy(desc(posts.postedAt))
    .limit(10);
  const removalRate = recent.length
    ? recent.filter((p) => p.isRemoved).length / recent.length
    : 0;

  const karma = await db
    .select({
      takenAt: karmaSnapshots.takenAt,
      total: sql<number>`(${karmaSnapshots.linkKarma} + ${karmaSnapshots.commentKarma})::int`,
    })
    .from(karmaSnapshots)
    .where(eq(karmaSnapshots.userId, userId))
    .orderBy(karmaSnapshots.takenAt);

  return {
    claimed: claimAgg[0]?.claimed ?? 0,
    posted: claimAgg[0]?.posted ?? 0,
    upvotesLast30d: upvoteAgg[0]?.upvotes ?? 0,
    removalRate,
    removalWindow: recent.length,
    karma,
  };
}

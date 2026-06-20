import { and, desc, eq, gte, inArray, notInArray, sql } from "drizzle-orm";
import { db } from "@/db/client";
import { claims, opportunities, userActiveSubs } from "@/db/schema";

export type FeedItem = {
  id: number;
  postUrl: string;
  subreddit: string;
  title: string;
  score: number;
  reason: string;
  suggestedAngle: string;
  createdAt: Date;
};

/**
 * Opportunities the user is allowed to see, filtered to:
 *  - subs where they had pre-existing activity, AND
 *  - subs they marked as matching their tagged expertise, AND
 *  - not already claimed by anyone (active claim).
 */
export async function getFeed(userId: string, minScore = 60): Promise<FeedItem[]> {
  const eligibleSubs = await db
    .select({ subreddit: userActiveSubs.subreddit })
    .from(userActiveSubs)
    .where(
      and(eq(userActiveSubs.userId, userId), eq(userActiveSubs.matchesExpertise, true)),
    );
  if (eligibleSubs.length === 0) return [];
  const subs = eligibleSubs.map((s) => s.subreddit);

  const activeClaims = await db
    .select({ opportunityId: claims.opportunityId })
    .from(claims)
    .where(inArray(claims.state, ["claimed", "posted"]));
  const claimedIds = activeClaims.map((c) => c.opportunityId);

  const rows = await db
    .select()
    .from(opportunities)
    .where(
      and(
        inArray(opportunities.subreddit, subs),
        gte(opportunities.score, minScore),
        claimedIds.length > 0 ? notInArray(opportunities.id, claimedIds) : sql`true`,
      ),
    )
    .orderBy(desc(opportunities.score), desc(opportunities.createdAt))
    .limit(100);

  return rows.map((r) => ({
    id: r.id,
    postUrl: r.postUrl,
    subreddit: r.subreddit,
    title: r.title,
    score: r.score,
    reason: r.reason,
    suggestedAngle: r.suggestedAngle,
    createdAt: r.createdAt,
  }));
}

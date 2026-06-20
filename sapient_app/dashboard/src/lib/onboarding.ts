import { sql } from "drizzle-orm";
import { db } from "@/db/client";
import { karmaSnapshots, userActiveSubs, userProfiles } from "@/db/schema";
import { getMe, iterUserHistory } from "./reddit";

type SubAggregate = {
  posts: number;
  comments: number;
  firstSeen: number;
  lastSeen: number;
};

/**
 * Reads the user's Reddit history and writes the pre-existing-active-sub set.
 *
 * "Pre-existing" = items with created_utc < the cutoff stored on the profile
 * (set at first sync to "now" and never moved forward). This is the data the
 * eligibility guardrail will read from later — it must be locked in.
 */
export async function syncUserHistory(userId: string): Promise<{
  username: string;
  preexistingCutoff: Date;
  subsAdded: number;
}> {
  const me = await getMe(userId);

  const profile = await db.query.userProfiles.findFirst({
    where: (p, { eq }) => eq(p.userId, userId),
  });
  const cutoff = profile?.preexistingCutoff ?? new Date();
  const cutoffUtc = cutoff.getTime() / 1000;

  if (!profile) {
    await db.insert(userProfiles).values({
      userId,
      redditUsername: me.name,
      redditCreatedUtc: me.created_utc,
      preexistingCutoff: cutoff,
      expertiseTags: [],
    });
  } else if (profile.redditUsername !== me.name) {
    throw new Error(
      `linked Reddit account changed: was ${profile.redditUsername}, now ${me.name}`,
    );
  }

  const agg = new Map<string, SubAggregate>();
  for await (const thing of iterUserHistory(userId, me.name)) {
    if (thing.created_utc >= cutoffUtc) continue; // post-join, not eligible signal
    const sub = thing.subreddit;
    const a = agg.get(sub) ?? {
      posts: 0,
      comments: 0,
      firstSeen: thing.created_utc,
      lastSeen: thing.created_utc,
    };
    if (thing.kind === "submitted") a.posts += 1;
    else a.comments += 1;
    a.firstSeen = Math.min(a.firstSeen, thing.created_utc);
    a.lastSeen = Math.max(a.lastSeen, thing.created_utc);
    agg.set(sub, a);
  }

  const rows = [...agg.entries()].map(([sub, a]) => ({
    userId,
    subreddit: sub,
    postCount: a.posts,
    commentCount: a.comments,
    firstSeen: new Date(a.firstSeen * 1000),
    lastSeen: new Date(a.lastSeen * 1000),
    matchesExpertise: false,
  }));

  if (rows.length > 0) {
    await db
      .insert(userActiveSubs)
      .values(rows)
      .onConflictDoUpdate({
        target: [userActiveSubs.userId, userActiveSubs.subreddit],
        set: {
          postCount: sql`excluded.post_count`,
          commentCount: sql`excluded.comment_count`,
          firstSeen: sql`LEAST(${userActiveSubs.firstSeen}, excluded.first_seen)`,
          lastSeen: sql`GREATEST(${userActiveSubs.lastSeen}, excluded.last_seen)`,
        },
      });
  }

  await db.insert(karmaSnapshots).values({
    userId,
    linkKarma: me.link_karma,
    commentKarma: me.comment_karma,
  });

  await db
    .update(userProfiles)
    .set({ lastHistorySync: new Date() })
    .where(sql`${userProfiles.userId} = ${userId}`);

  return { username: me.name, preexistingCutoff: cutoff, subsAdded: rows.length };
}

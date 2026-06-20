import { NextResponse } from "next/server";
import { desc, eq, inArray } from "drizzle-orm";
import { auth } from "../../../../../auth";
import { db } from "@/db/client";
import { posts } from "@/db/schema";
import { fetchThings, getMe } from "@/lib/reddit";
import { enforceRemovalRate } from "@/lib/guardrails";
import { karmaSnapshots } from "@/db/schema";

/** Re-fetch the user's recent posts from Reddit, update removal/upvote state,
 *  snapshot karma, then evaluate the removal-rate auto-pause. */
export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const userId = session.user.id;

  const recent = await db
    .select({ redditThingId: posts.redditThingId })
    .from(posts)
    .where(eq(posts.userId, userId))
    .orderBy(desc(posts.postedAt))
    .limit(50);

  const ids = recent.map((r) => r.redditThingId);
  if (ids.length > 0) {
    const fetched = await fetchThings(userId, ids);
    const now = new Date();
    for (const t of fetched) {
      await db
        .update(posts)
        .set({ isRemoved: t.isRemoved, upvotes: t.score, lastCheckedAt: now })
        .where(eq(posts.redditThingId, t.redditThingId));
    }
  }

  const me = await getMe(userId);
  await db.insert(karmaSnapshots).values({
    userId,
    linkKarma: me.link_karma,
    commentKarma: me.comment_karma,
  });

  const removal = await enforceRemovalRate(userId);
  return NextResponse.json({ synced: ids.length, removal });
}

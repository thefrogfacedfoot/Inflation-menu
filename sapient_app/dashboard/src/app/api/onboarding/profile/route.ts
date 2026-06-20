import { NextResponse } from "next/server";
import { and, eq, inArray, sql } from "drizzle-orm";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { db } from "@/db/client";
import { userActiveSubs, userProfiles } from "@/db/schema";

const Body = z.object({
  expertiseTags: z.array(z.string().min(1).max(40)).max(20),
  expertiseSubs: z.array(z.string().min(1).max(40)).max(100),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const parsed = Body.safeParse(await req.json());
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.message }, { status: 400 });
  }
  const userId = session.user.id;

  await db
    .update(userProfiles)
    .set({ expertiseTags: parsed.data.expertiseTags })
    .where(eq(userProfiles.userId, userId));

  // Reset all matches, then mark the chosen subs. Server-side intersection
  // with the active-sub set means the client can't sneak in a sub the user
  // wasn't actually active in.
  await db
    .update(userActiveSubs)
    .set({ matchesExpertise: false })
    .where(eq(userActiveSubs.userId, userId));

  if (parsed.data.expertiseSubs.length > 0) {
    await db
      .update(userActiveSubs)
      .set({ matchesExpertise: true })
      .where(
        and(
          eq(userActiveSubs.userId, userId),
          inArray(userActiveSubs.subreddit, parsed.data.expertiseSubs),
        ),
      );
  }

  const counts = await db
    .select({ n: sql<number>`count(*)::int` })
    .from(userActiveSubs)
    .where(
      and(eq(userActiveSubs.userId, userId), eq(userActiveSubs.matchesExpertise, true)),
    );

  return NextResponse.json({ expertiseSubsMatched: counts[0]?.n ?? 0 });
}

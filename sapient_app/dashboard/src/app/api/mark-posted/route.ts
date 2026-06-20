import { NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { auth } from "../../../../auth";
import { db } from "@/db/client";
import { claims, opportunities, posts } from "@/db/schema";
import {
  GuardrailError,
  assertCanMarkPosted,
  assertWeeklyPromoCap,
  enforceRemovalRate,
} from "@/lib/guardrails";
import { dashboardClaimToPostedSeconds, dashboardPostsTotal } from "@/lib/metrics";
import { log } from "@/lib/logging";

const Body = z.object({
  claimId: z.number().int().positive(),
  redditThingId: z.string().regex(/^t[13]_[a-z0-9]+$/i), // t1_=comment, t3_=submission
  permalink: z.string().url(),
  body: z.string().min(1).max(40_000),
  // Self-report: can flip the stored value false → true, never true → false.
  mentionsProduct: z.boolean().optional(),
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

  const claim = await db.query.claims.findFirst({
    where: and(eq(claims.id, parsed.data.claimId), eq(claims.userId, userId)),
  });
  if (!claim || claim.state !== "claimed") {
    return NextResponse.json(
      { error: "claim not found or not in claimable state" },
      { status: 404 },
    );
  }

  const opp = await db.query.opportunities.findFirst({
    where: eq(opportunities.id, claim.opportunityId),
  });
  if (!opp) {
    return NextResponse.json({ error: "opportunity vanished" }, { status: 404 });
  }

  let check;
  try {
    check = await assertCanMarkPosted({
      userId,
      opportunityId: opp.id,
      subreddit: opp.subreddit,
      redditThingId: parsed.data.redditThingId,
      permalink: parsed.data.permalink,
      body: parsed.data.body,
      selfReportedMentionsProduct: parsed.data.mentionsProduct,
    });
  } catch (e) {
    if (e instanceof GuardrailError) {
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status: 403 },
      );
    }
    throw e;
  }

  let insertedPostId = 0;
  await db.transaction(async (tx) => {
    const [inserted] = await tx
      .insert(posts)
      .values({
        claimId: claim.id,
        userId,
        subreddit: opp.subreddit,
        redditThingId: parsed.data.redditThingId,
        permalink: parsed.data.permalink,
        body: parsed.data.body,
        mentionsProduct: check.mentionsProduct,
        includesDisclosure: check.includesDisclosure,
      })
      .returning({ id: posts.id });
    insertedPostId = inserted.id;
    await tx.update(claims).set({ state: "posted" }).where(eq(claims.id, claim.id));
  });

  dashboardPostsTotal.inc({
    source: claim.source ?? "organic",
    mentioned_product: check.mentionsProduct ? "true" : "false",
  });
  // claimedAt is set by the DB on insert, so it's non-null at this point.
  const claimedAtMs = claim.claimedAt?.getTime();
  if (claimedAtMs) {
    dashboardClaimToPostedSeconds.observe((Date.now() - claimedAtMs) / 1000);
  }
  log.info("post_recorded", {
    user_id: userId,
    claim_id: claim.id,
    post_id: insertedPostId,
    source: claim.source ?? "organic",
    mentioned_product: check.mentionsProduct,
  });

  // If this claim came from a visibility task, write the post id back so
  // the visibility tracker shows the task as done. No-op for organic claims.
  const { markPostedFromVisibility } = await import("@/lib/visibility-tasks");
  await markPostedFromVisibility(claim.id, insertedPostId);

  // Re-check the weekly cap AFTER inserting — if this post pushed the user
  // over the limit, pause kicks in NOW. Swallow the throw because the post
  // already happened; the user is paused for next time.
  if (check.mentionsProduct) {
    try {
      await assertWeeklyPromoCap(userId);
    } catch {
      /* pause flag set inside */
    }
  }

  const removal = await enforceRemovalRate(userId);
  return NextResponse.json({ ok: true, check, removal });
}

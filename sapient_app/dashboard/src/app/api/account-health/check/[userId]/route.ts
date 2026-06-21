import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { auth } from "../../../../../../auth";
import { db } from "@/db/client";
import { userProfiles } from "@/db/schema";
import {
  checkKarmaTrend,
  checkShadowban,
  checkSlowBurnRemoval,
  runCheck,
} from "@/lib/account-health";
import {
  karmaDeps,
  shadowbanDeps,
  slowBurnDeps,
} from "@/lib/account-health-deps";
import { isOpsUser } from "@/lib/visibility-tasks";

export const dynamic = "force-dynamic";

/**
 * Ops-only force-run. Useful when an ops engineer wants to confirm a
 * shadowban suspicion right now rather than wait for the daily cadence.
 * Runs all three checks for the given user and returns the results.
 */
export async function POST(
  _req: Request,
  ctx: { params: { userId: string } },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!(await isOpsUser(session.user.id))) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const userId = ctx.params.userId;
  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, userId),
  });
  if (!profile) {
    return NextResponse.json({ error: "user not found" }, { status: 404 });
  }

  const results: Record<string, unknown> = {};
  try {
    results.shadowban = await runCheck({
      userId,
      checkType: "shadowban",
      run: () => checkShadowban(userId, profile.redditUsername, shadowbanDeps),
    });
  } catch (e) {
    results.shadowban = { error: e instanceof Error ? e.message : String(e) };
  }
  try {
    results.karma_trend = await runCheck({
      userId,
      checkType: "karma_trend",
      run: () => checkKarmaTrend(userId, karmaDeps),
    });
  } catch (e) {
    results.karma_trend = { error: e instanceof Error ? e.message : String(e) };
  }
  try {
    results.slow_removal = await runCheck({
      userId,
      checkType: "slow_removal",
      run: () => checkSlowBurnRemoval(userId, slowBurnDeps),
    });
  } catch (e) {
    results.slow_removal = { error: e instanceof Error ? e.message : String(e) };
  }
  return NextResponse.json({ userId, results });
}

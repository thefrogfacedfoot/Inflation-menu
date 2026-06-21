import { NextResponse } from "next/server";
import { auth } from "../../../../../../auth";
import { cancelRequest, GdprStateError } from "@/lib/gdpr";
import { isOpsUser } from "@/lib/visibility-tasks";

export const dynamic = "force-dynamic";

/**
 * Cancel a pending delete. Owners cancel their own; ops can cancel anyone's
 * with an optional reason. 409 if the request has progressed past pending —
 * once the worker starts touching rows, it's too late.
 */
export async function DELETE(
  req: Request,
  ctx: { params: { id: string } },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const id = Number(ctx.params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "bad_id" }, { status: 400 });
  }
  const ops = await isOpsUser(session.user.id);
  let reason: string | undefined;
  try {
    const body = (await req.json().catch(() => ({}))) as { reason?: string };
    reason = body.reason;
  } catch {
    /* body optional */
  }
  try {
    const updated = await cancelRequest(id, {
      actorUserId: session.user.id,
      isOps: ops,
      reason,
    });
    return NextResponse.json({ request: updated });
  } catch (e) {
    if (e instanceof GdprStateError) {
      // 409 on state conflicts (e.g. already in_progress), 403 on
      // ownership, 404 on not-found. The code message tells the UI which.
      const status =
        e.message === "request_not_found"
          ? 404
          : e.message === "not_request_owner"
            ? 403
            : 409;
      return NextResponse.json({ error: e.message }, { status });
    }
    throw e;
  }
}

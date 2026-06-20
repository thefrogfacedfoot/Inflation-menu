import { NextResponse } from "next/server";
import { auth } from "../../../../../../auth";
import { GuardrailError } from "@/lib/guardrails";
import { claimVisibilityTask } from "@/lib/visibility-tasks";

export async function POST(
  _req: Request,
  ctx: { params: { id: string } },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const taskId = Number(ctx.params.id);
  if (!Number.isFinite(taskId) || taskId <= 0) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  try {
    const claim = await claimVisibilityTask(taskId, session.user.id);
    return NextResponse.json({ claim });
  } catch (e) {
    if (e instanceof GuardrailError) {
      const status = e.code === "already_claimed" ? 409 : 403;
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status },
      );
    }
    throw e;
  }
}

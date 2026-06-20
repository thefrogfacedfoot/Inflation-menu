import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../../auth";
import { dismissVisibilityTask } from "@/lib/visibility-tasks";

const Body = z.object({ reason: z.string().min(1).max(500).optional() });

export async function POST(req: Request, ctx: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const taskId = Number(ctx.params.id);
  if (!Number.isFinite(taskId) || taskId <= 0) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const parsed = Body.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.message }, { status: 400 });
  }
  await dismissVisibilityTask(taskId, parsed.data.reason);
  return NextResponse.json({ ok: true });
}

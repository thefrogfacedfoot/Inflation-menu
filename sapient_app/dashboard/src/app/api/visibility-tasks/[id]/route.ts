import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { getVisibilityTaskById } from "@/lib/visibility-tasks";

export async function GET(_req: Request, ctx: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const taskId = Number(ctx.params.id);
  if (!Number.isFinite(taskId) || taskId <= 0) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const task = await getVisibilityTaskById(taskId);
  if (task === null) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ task });
}

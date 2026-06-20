import { NextResponse } from "next/server";
import { auth } from "../../../../auth";
import {
  getEligibleVisibilityTasks,
  isOpsUser,
} from "@/lib/visibility-tasks";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const result = await getEligibleVisibilityTasks(session.user.id);
  if (result === null) {
    const ops = await isOpsUser(session.user.id);
    // Silent fallback for end users; visible notice for ops.
    return NextResponse.json(
      ops
        ? { reddit: [], content: [], unavailable: true, notice: "visibility tracker not configured" }
        : { reddit: [], content: [] },
    );
  }
  return NextResponse.json(result);
}

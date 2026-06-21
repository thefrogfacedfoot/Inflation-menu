import { NextResponse } from "next/server";
import { auth } from "../../../../auth";
import {
  getEligibleVisibilityTasks,
  isOpsUser,
} from "@/lib/visibility-tasks";
import { requireSetupComplete, WizardIncompleteError } from "@/lib/wizard";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    await requireSetupComplete();
  } catch (e) {
    if (e instanceof WizardIncompleteError) {
      return NextResponse.json(
        { error: "setup_required", setupStep: e.setupStep },
        { status: 503 },
      );
    }
    throw e;
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

import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { getAllSnapshots, highestSeverity } from "@/lib/account-health";
import { isOpsUser } from "@/lib/visibility-tasks";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!(await isOpsUser(session.user.id))) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const snapshots = await getAllSnapshots();
  return NextResponse.json({
    items: snapshots.map((s) => ({ snapshot: s, severity: highestSeverity(s) })),
  });
}

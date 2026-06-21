import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import {
  getAccountHealthSnapshot,
  highestSeverity,
} from "@/lib/account-health";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const snapshot = await getAccountHealthSnapshot(session.user.id);
  return NextResponse.json({
    snapshot,
    severity: highestSeverity(snapshot),
  });
}

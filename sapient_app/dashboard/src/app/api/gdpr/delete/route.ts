import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { createRequest } from "@/lib/gdpr";

export const dynamic = "force-dynamic";

/**
 * Create a delete request. The actual deletion runs after the 30-day grace
 * period (the scheduler in @/lib/gdpr-scheduler picks it up). The route
 * returns the pending request row so the UI can display the scheduledFor
 * date.
 */
export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const request = await createRequest(session.user.id, "delete");
  return NextResponse.json({ request });
}

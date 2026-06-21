import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { createRequest, processExport } from "@/lib/gdpr";

export const dynamic = "force-dynamic";

/**
 * Kick off an export. The collection + upload runs async after the response
 * lands. The client polls /api/gdpr/requests for state=completed to surface
 * the download URL.
 *
 * Synchronous behavior under GDPR_PROCESS_INLINE=1 makes test wiring easy
 * (route handler returns AFTER the bundle has been written) without the
 * fire-and-forget timing.
 */
export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const request = await createRequest(session.user.id, "export");
  if (process.env.GDPR_PROCESS_INLINE === "1") {
    const done = await processExport(request);
    return NextResponse.json({ request: done });
  }
  // Don't await — the response should return immediately. The promise is
  // intentionally not held; processExport persists state to the DB so the
  // user can poll for completion.
  void processExport(request).catch(() => {
    // processExport already records failure into the DB row; nothing else
    // to do here. Swallow to avoid an unhandledRejection.
  });
  return NextResponse.json({ request });
}

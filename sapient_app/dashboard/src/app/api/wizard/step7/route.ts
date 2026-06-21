import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { markSetupComplete, runSmokeTest } from "@/lib/wizard";

export const dynamic = "force-dynamic";

/**
 * POST runs the smoke test. POST?confirm=1 marks the wizard complete after
 * the operator has reviewed the smoke-test result. Separation matters:
 * smoke results may include errors that are fine to acknowledge (e.g.
 * ChatGPT 429), but the operator should explicitly confirm.
 */
export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const url = new URL(req.url);
  if (url.searchParams.get("confirm") === "1") {
    await markSetupComplete();
    return NextResponse.json({ ok: true, completed: true });
  }
  const result = await runSmokeTest();
  return NextResponse.json({ ok: true, result });
}

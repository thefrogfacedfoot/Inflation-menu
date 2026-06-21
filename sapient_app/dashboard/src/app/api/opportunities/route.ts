import { NextResponse } from "next/server";
import { auth } from "../../../../auth";
import { getFeed } from "@/lib/feed";
import { requireSetupComplete, WizardIncompleteError } from "@/lib/wizard";

export async function GET(req: Request) {
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
  const url = new URL(req.url);
  const minScore = Number(url.searchParams.get("min_score") ?? "60");
  const items = await getFeed(session.user.id, minScore);
  return NextResponse.json({ items });
}

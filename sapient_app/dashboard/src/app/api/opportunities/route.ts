import { NextResponse } from "next/server";
import { auth } from "../../../../auth";
import { getFeed } from "@/lib/feed";

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const url = new URL(req.url);
  const minScore = Number(url.searchParams.get("min_score") ?? "60");
  const items = await getFeed(session.user.id, minScore);
  return NextResponse.json({ items });
}

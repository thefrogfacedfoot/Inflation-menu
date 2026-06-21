import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { suggestQueries } from "@/lib/wizard";

export const dynamic = "force-dynamic";

export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    const queries = await suggestQueries();
    return NextResponse.json({ queries });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "suggest failed" },
      { status: 500 },
    );
  }
}

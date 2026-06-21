import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { getBrandConfig } from "@/lib/wizard";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const cfg = await getBrandConfig();
  return NextResponse.json({
    config: cfg,
    setupStep: cfg?.setupStep ?? 0,
    setupCompletedAt: cfg?.setupCompletedAt ?? null,
  });
}

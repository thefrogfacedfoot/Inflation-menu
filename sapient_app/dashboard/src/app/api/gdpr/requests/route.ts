import { NextResponse } from "next/server";
import { auth } from "../../../../../auth";
import { listUserRequests } from "@/lib/gdpr";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const requests = await listUserRequests(session.user.id);
  return NextResponse.json({ requests });
}

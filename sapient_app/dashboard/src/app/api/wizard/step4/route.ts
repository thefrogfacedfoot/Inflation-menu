import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { saveStep4 } from "@/lib/wizard";

const Body = z.object({
  approvedSubs: z.array(z.string().min(1).max(64)).min(1).max(50),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const parsed = Body.safeParse(await req.json());
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.message }, { status: 400 });
  }
  await saveStep4(parsed.data.approvedSubs);
  return NextResponse.json({ ok: true });
}

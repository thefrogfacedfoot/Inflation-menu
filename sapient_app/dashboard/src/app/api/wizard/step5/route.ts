import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { saveStep5 } from "@/lib/wizard";

const Body = z.object({
  add: z.array(z.string().min(1).max(200)).max(50).default([]),
  remove: z.array(z.string().min(1).max(200)).max(50).default([]),
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
  await saveStep5({ ...parsed.data, userId: session.user.id });
  return NextResponse.json({ ok: true });
}

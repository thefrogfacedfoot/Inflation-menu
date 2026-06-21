import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { saveStep2 } from "@/lib/wizard";

const Body = z.object({
  competitors: z
    .array(
      z.object({
        name: z.string().min(1).max(120),
        aliases: z.array(z.string().min(1).max(80)).max(20),
      }),
    )
    .min(3)
    .max(10),
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
  try {
    await saveStep2(parsed.data.competitors);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "step2 failed" },
      { status: 500 },
    );
  }
}

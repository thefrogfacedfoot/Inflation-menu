import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { saveStep3 } from "@/lib/wizard";

const Body = z.object({
  queries: z.array(z.string().min(1).max(300)).min(1).max(50),
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
    await saveStep3(parsed.data.queries);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "step3 failed" },
      { status: 500 },
    );
  }
}

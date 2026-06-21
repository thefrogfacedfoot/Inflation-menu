import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { discoverAdjacentSubs } from "@/lib/wizard";

const Body = z.object({
  seeds: z.array(z.string().min(1).max(64)).min(1).max(20),
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
    const expanded = await discoverAdjacentSubs(parsed.data.seeds);
    return NextResponse.json({ subs: expanded });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "discover failed" },
      { status: 500 },
    );
  }
}

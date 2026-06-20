import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../auth";
import { GuardrailError, claimOpportunity } from "@/lib/guardrails";

const Body = z.object({ opportunityId: z.number().int().positive() });

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
    const claim = await claimOpportunity(session.user.id, parsed.data.opportunityId);
    return NextResponse.json({ claim });
  } catch (e) {
    if (e instanceof GuardrailError) {
      const status = e.code === "already_claimed" ? 409 : 403;
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status },
      );
    }
    throw e;
  }
}

import { NextResponse } from "next/server";
import { auth } from "../../../../../../auth";
import { GuardrailError } from "@/lib/guardrails";
import { archive } from "@/lib/content-gap";

export async function POST(
  _req: Request,
  ctx: { params: { id: string } },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const draftId = Number(ctx.params.id);
  if (!Number.isFinite(draftId) || draftId <= 0) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  try {
    const draft = await archive(draftId, session.user.id);
    return NextResponse.json({ draft });
  } catch (e) {
    if (e instanceof GuardrailError) {
      const status = e.code === "draft_not_found" ? 404 : 409;
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status },
      );
    }
    throw e;
  }
}

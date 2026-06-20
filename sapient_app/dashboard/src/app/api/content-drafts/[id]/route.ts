import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../auth";
import { GuardrailError } from "@/lib/guardrails";
import { getDraft, patchDraft } from "@/lib/content-gap";

const Body = z.object({
  title: z.string().min(1).max(500).optional(),
  body: z.string().min(0).max(200_000).optional(),
});

export async function GET(
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
  const draft = await getDraft(draftId, session.user.id);
  if (!draft) {
    return NextResponse.json({ error: "draft not found" }, { status: 404 });
  }
  return NextResponse.json({ draft });
}

export async function PATCH(
  req: Request,
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
  const parsed = Body.safeParse(await req.json());
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.message }, { status: 400 });
  }
  try {
    const draft = await patchDraft(draftId, session.user.id, parsed.data);
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

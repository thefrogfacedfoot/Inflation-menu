import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../../../auth";
import { GuardrailError } from "@/lib/guardrails";
import { publish } from "@/lib/content-gap";

const Body = z.object({ url: z.string().url() });

export async function POST(
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
    const draft = await publish(draftId, session.user.id, parsed.data.url);
    return NextResponse.json({ draft });
  } catch (e) {
    if (e instanceof GuardrailError) {
      const status =
        e.code === "draft_not_found"
          ? 404
          : e.code === "already_published"
            ? 409
            : 422;
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status },
      );
    }
    throw e;
  }
}

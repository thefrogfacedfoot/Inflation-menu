import { NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "../../../../auth";
import { GuardrailError } from "@/lib/guardrails";
import {
  ActiveDraftExistsError,
  RateLimitedError,
  defaultLLMClient,
  generateDraft,
} from "@/lib/content-gap";

const Body = z.object({ taskId: z.number().int().positive() });

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
    const result = await generateDraft(parsed.data.taskId, session.user.id, {
      llm: defaultLLMClient(),
    });
    return NextResponse.json(result, { status: 201 });
  } catch (e) {
    if (e instanceof RateLimitedError) {
      return NextResponse.json(
        { error: e.message, code: e.code, cap: e.cap, used: e.used },
        { status: 429 },
      );
    }
    if (e instanceof ActiveDraftExistsError) {
      return NextResponse.json(
        { error: e.message, code: e.code, draftId: e.existingDraftId },
        { status: 409 },
      );
    }
    if (e instanceof GuardrailError) {
      const status = e.code === "task_not_found" ? 404 : 403;
      return NextResponse.json(
        { error: e.message, code: e.code, ...e.payload },
        { status },
      );
    }
    throw e;
  }
}

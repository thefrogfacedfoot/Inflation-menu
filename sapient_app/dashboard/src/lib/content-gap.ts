/**
 * Content-gap drafting flow. Companion to src/lib/visibility-tasks.ts but on
 * a different axis: visibility-tasks.ts deals with reddit_* kinds via the
 * existing claim/post pipeline. This module deals with blog_post (and other
 * non-reddit) kinds via a draft → edit → publish state machine. The user
 * publishes EXTERNALLY (their own CMS); the dashboard only tracks state and
 * keeps an audit trail.
 *
 * State machine:
 *   draft → edited → published
 *   draft → archived
 *   edited → archived
 * Every transition writes a `content_draft_event` row. The state field is
 * the only thing readers should treat as authoritative; the event log is
 * for ops.
 *
 * Rate limit: 5 draft generations per user per UTC day. Separate counter
 * from the weekly_promo_cap — content generation isn't promotional posting,
 * it's just LLM cost protection. We DO NOT pause users for hitting this; we
 * just refuse to generate more drafts today.
 */
import { and, eq, sql } from "drizzle-orm";
import { db } from "@/db/client";
import {
  contentDraftEvents,
  contentDraftQuota,
  contentDrafts,
  visibilityTasks,
} from "@/db/schema";
import { GuardrailError } from "./guardrails";
import { log } from "./logging";

const DAILY_GENERATION_CAP = Number(
  process.env.CONTENT_DRAFT_DAILY_CAP ?? 5,
);

const VERIFY_MARKER_RE = /\[VERIFY:[^\]]*\]/g;

export type DraftStatus = "draft" | "edited" | "published" | "archived";

/** What the LLM returns to us. The lib does not trust the model's status —
 *  generated drafts always land as 'draft'. */
export type GeneratedDraft = {
  title: string;
  body: string;
};

export type LLMClient = {
  /** Send a prompt, get the model's draft back. Implementations are responsible
   *  for parsing whatever wire format they prefer (JSON-mode, XML tags, etc.)
   *  and producing the title + body. */
  generate(input: {
    query: string;
    recommendation: string;
    relatedUrl: string | null;
  }): Promise<GeneratedDraft>;
};

/** Counts `[VERIFY: ...]` markers in markdown body. Single source of truth —
 *  every place we need the count (insert, patch, mark-edited warning) goes
 *  through here. Empty string ⇒ 0 (regex without match returns null). */
export function countEditMarkers(body: string): number {
  const matches = body.match(VERIFY_MARKER_RE);
  return matches ? matches.length : 0;
}

/** Stable system prompt. Pinned values:
 *   - factual claims only the brand can verify
 *   - no fabricated statistics
 *   - first-person voice tagged as the brand
 *   - explicit [VERIFY: …] markers where uncertain
 *
 *  The prompt is exported so tests can assert that the contract didn't drift.
 */
export const SYSTEM_PROMPT = `You are a draft-writer for a brand-owned blog. Output a draft the brand's team will edit before publishing.

Hard constraints:
1. Only state factual claims the brand itself can verify (its own product, its own customers, its own pricing). Do not invent third-party statistics, dates, or quotations.
2. Write in first-person plural ("we", "our team") as the brand.
3. Wrap every uncertain claim in [VERIFY: …] markers. Example: "Our integration cuts onboarding time [VERIFY: by what %?]." The editor will replace these before publishing.
4. Markdown only. Title on its own first line as "# Title".
5. No call-to-action that promises a feature the brand may not have shipped — use [VERIFY: ship date?] if unsure.

Output a JSON object: { "title": "...", "body": "..." } with body as a markdown string starting with the H1.`;

/* ============== Generation ============== */

export type GenerateDraftResult = {
  draftId: number;
  draft: {
    id: number;
    title: string;
    body: string;
    status: DraftStatus;
    editMarkersCount: number;
  };
};

export class RateLimitedError extends Error {
  code = "rate_limited" as const;
  constructor(public cap: number, public used: number) {
    super(`content draft daily cap reached (${used}/${cap})`);
  }
}

export class ActiveDraftExistsError extends Error {
  code = "active_draft_exists" as const;
  constructor(public existingDraftId: number) {
    super(`an active draft already exists for this task (id=${existingDraftId})`);
  }
}

/** UTC day key. Stored as YYYY-MM-DD. */
function dayKey(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/** Reserve a quota slot. Returns the post-increment count so the caller can
 *  log it. Throws RateLimitedError when over the cap. Atomic via
 *  `INSERT … ON CONFLICT DO UPDATE … WHERE count < cap` so two concurrent
 *  generations can't both squeeze through the 5th slot. */
async function reserveQuota(userId: string, cap: number): Promise<number> {
  const day = dayKey();
  // The WHERE clause on the UPDATE branch is what gates the increment.
  // RETURNING gives us the new count when the update fires; nothing when
  // the cap blocks it. The INSERT branch fires when no row exists for the
  // day yet and is allowed unconditionally (counts as the first slot).
  const rows = await db
    .insert(contentDraftQuota)
    .values({ userId, day, count: 1 })
    .onConflictDoUpdate({
      target: [contentDraftQuota.userId, contentDraftQuota.day],
      set: { count: sql`${contentDraftQuota.count} + 1` },
      setWhere: sql`${contentDraftQuota.count} < ${cap}`,
    })
    .returning({ count: contentDraftQuota.count });
  if (rows.length === 0) {
    // The setWhere blocked the update — read the current count for the error.
    const [existing] = await db
      .select({ count: contentDraftQuota.count })
      .from(contentDraftQuota)
      .where(
        and(eq(contentDraftQuota.userId, userId), eq(contentDraftQuota.day, day)),
      );
    throw new RateLimitedError(cap, existing?.count ?? cap);
  }
  return rows[0].count;
}

/** Reverse a quota slot when the surrounding operation fails AFTER the
 *  reservation. Best-effort — we'd rather over-count than under-count
 *  (the cap is a soft limit on LLM cost, not a billing system), but we try. */
async function refundQuota(userId: string): Promise<void> {
  const day = dayKey();
  try {
    await db
      .update(contentDraftQuota)
      .set({ count: sql`GREATEST(${contentDraftQuota.count} - 1, 0)` })
      .where(
        and(eq(contentDraftQuota.userId, userId), eq(contentDraftQuota.day, day)),
      );
  } catch {
    // Refund is best-effort; ignore failures.
  }
}

export type GenerateDraftOpts = {
  llm: LLMClient;
  now?: Date;
};

/** Public entry point — generates a draft for the given visibility task and
 *  persists it. The LLM client is injectable so tests don't need network. */
export async function generateDraft(
  taskId: number,
  userId: string,
  opts: GenerateDraftOpts,
): Promise<GenerateDraftResult> {
  const task = await db.query.visibilityTasks.findFirst({
    where: eq(visibilityTasks.id, taskId),
  });
  if (!task) {
    throw new GuardrailError("task_not_found", "visibility task not found");
  }
  if (task.status !== "open") {
    throw new GuardrailError(
      "task_not_open",
      `visibility task is ${task.status}, not draftable`,
    );
  }

  // Active-draft check BEFORE we burn the quota — a duplicate generate
  // shouldn't cost the user a slot. Scoped to (task, this user): another
  // user's draft for the same task is intentionally ignored.
  const existing = await db.query.contentDrafts.findFirst({
    where: and(
      eq(contentDrafts.visibilityTaskId, taskId),
      eq(contentDrafts.userId, userId),
      sql`${contentDrafts.status} <> 'archived'`,
    ),
  });
  if (existing) {
    throw new ActiveDraftExistsError(existing.id);
  }

  const newCount = await reserveQuota(userId, DAILY_GENERATION_CAP);

  let generated: GeneratedDraft;
  try {
    generated = await opts.llm.generate({
      query: task.recommendation, // best available "what's the gap"
      recommendation: task.recommendation,
      relatedUrl: task.relatedUrl,
    });
  } catch (e) {
    await refundQuota(userId);
    throw e;
  }

  const editMarkers = countEditMarkers(generated.body);

  try {
    const [inserted] = await db
      .insert(contentDrafts)
      .values({
        visibilityTaskId: taskId,
        userId,
        title: generated.title,
        body: generated.body,
        // Snapshot of what the user thought they were writing about. The
        // visibility task's recommendation is the closest stable thing.
        targetQuery: task.recommendation,
        status: "draft",
        editMarkersCount: editMarkers,
      })
      .returning({
        id: contentDrafts.id,
        title: contentDrafts.title,
        body: contentDrafts.body,
        status: contentDrafts.status,
        editMarkersCount: contentDrafts.editMarkersCount,
      });

    // First event: NULL → draft. The state-transition log starts here.
    await db.insert(contentDraftEvents).values({
      draftId: inserted.id,
      fromStatus: null,
      toStatus: "draft",
      userId,
    });

    log.info("content_draft_generated", {
      draft_id: inserted.id,
      task_id: taskId,
      user_id: userId,
      edit_markers: editMarkers,
      quota_used_today: newCount,
    });

    return {
      draftId: inserted.id,
      draft: {
        id: inserted.id,
        title: inserted.title,
        body: inserted.body,
        status: inserted.status as DraftStatus,
        editMarkersCount: inserted.editMarkersCount,
      },
    };
  } catch (e) {
    if (isUniqueViolation(e)) {
      // Lost a race against another generate for the same (task, user).
      // Refund the quota slot and surface the existing draft id so the
      // caller can route the user there. Scoped to this user because the
      // unique index is per (visibility_task_id, "userId").
      await refundQuota(userId);
      const concurrent = await db.query.contentDrafts.findFirst({
        where: and(
          eq(contentDrafts.visibilityTaskId, taskId),
          eq(contentDrafts.userId, userId),
          sql`${contentDrafts.status} <> 'archived'`,
        ),
      });
      if (concurrent) throw new ActiveDraftExistsError(concurrent.id);
    }
    await refundQuota(userId);
    throw e;
  }
}

function isUniqueViolation(e: unknown): boolean {
  if (!e || typeof e !== "object") return false;
  const code = (e as { code?: unknown }).code;
  if (code === "23505") return true;
  const message = (e as { message?: unknown }).message;
  return typeof message === "string" && /unique|duplicate key/i.test(message);
}

/* ============== Edits ============== */

export type PatchDraftInput = {
  title?: string;
  body?: string;
};

/** Patch title and/or body. Recomputes edit_markers_count from the new body.
 *  Returns the patched row. Does NOT change status — that's mark-edited. */
export async function patchDraft(
  draftId: number,
  userId: string,
  patch: PatchDraftInput,
): Promise<typeof contentDrafts.$inferSelect> {
  const draft = await loadOwnDraft(draftId, userId);
  if (draft.status === "published" || draft.status === "archived") {
    throw new GuardrailError(
      "draft_locked",
      `draft is ${draft.status}; create a new one to keep editing`,
    );
  }
  const nextBody = patch.body ?? draft.body;
  const nextTitle = patch.title ?? draft.title;
  const editMarkers = countEditMarkers(nextBody);
  const [updated] = await db
    .update(contentDrafts)
    .set({
      title: nextTitle,
      body: nextBody,
      editMarkersCount: editMarkers,
      updatedAt: new Date(),
    })
    .where(eq(contentDrafts.id, draftId))
    .returning();
  return updated;
}

/* ============== Transitions ============== */

export type MarkEditedResult = {
  draft: typeof contentDrafts.$inferSelect;
  warning: { code: "unresolved_verify_markers"; count: number } | null;
};

/** Flip status draft → edited. Soft warning when there are still unresolved
 *  [VERIFY: …] markers — the spec is explicit that this is NOT a block, it's
 *  a hint to the user. Idempotent on a draft already in `edited` (returns
 *  with no warning). */
export async function markEdited(
  draftId: number,
  userId: string,
): Promise<MarkEditedResult> {
  const draft = await loadOwnDraft(draftId, userId);
  if (draft.status === "edited") {
    return { draft, warning: null };
  }
  if (draft.status !== "draft") {
    throw new GuardrailError(
      "invalid_transition",
      `cannot mark-edited from status=${draft.status}`,
    );
  }
  const [updated] = await db
    .update(contentDrafts)
    .set({ status: "edited", updatedAt: new Date() })
    .where(eq(contentDrafts.id, draftId))
    .returning();
  await db.insert(contentDraftEvents).values({
    draftId,
    fromStatus: "draft",
    toStatus: "edited",
    userId,
  });
  log.info("content_draft_marked_edited", {
    draft_id: draftId,
    user_id: userId,
    edit_markers: updated.editMarkersCount,
  });
  const warning =
    updated.editMarkersCount > 0
      ? {
          code: "unresolved_verify_markers" as const,
          count: updated.editMarkersCount,
        }
      : null;
  return { draft: updated, warning };
}

/** Flip status → published. Stamps published_at, writes published_url. Also
 *  closes the upstream visibility.tasks row: status='done', sets the new
 *  dashboard_content_draft_id column. */
export async function publish(
  draftId: number,
  userId: string,
  publishedUrl: string,
): Promise<typeof contentDrafts.$inferSelect> {
  const draft = await loadOwnDraft(draftId, userId);
  if (draft.status === "published") {
    throw new GuardrailError(
      "already_published",
      "draft is already published",
    );
  }
  if (draft.status !== "edited") {
    throw new GuardrailError(
      "invalid_transition",
      `cannot publish from status=${draft.status}; mark-edited first`,
    );
  }
  const now = new Date();
  const [updated] = await db
    .update(contentDrafts)
    .set({
      status: "published",
      publishedUrl,
      publishedAt: now,
      updatedAt: now,
    })
    .where(eq(contentDrafts.id, draftId))
    .returning();
  await db.insert(contentDraftEvents).values({
    draftId,
    fromStatus: "edited",
    toStatus: "published",
    userId,
  });

  // Visibility writeback. Symmetric with markPostedFromVisibility for Reddit
  // posts — failure here is logged but not re-thrown; the draft is already
  // published from the user's POV.
  try {
    log.info("visibility_task_published_writeback", {
      task_id: draft.visibilityTaskId,
      draft_id: draftId,
      target_schema: "visibility",
      target_table: "tasks",
    });
    await db
      .update(visibilityTasks)
      .set({
        status: "done",
        dashboardContentDraftId: draftId,
      })
      .where(eq(visibilityTasks.id, draft.visibilityTaskId));
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    console.warn("visibility content-draft writeback failed", {
      draftId,
      taskId: draft.visibilityTaskId,
      exceptionClass: (err.constructor && err.constructor.name) || "Error",
      message: err.message,
    });
  }
  return updated;
}

/** Flip status → archived. Frees the visibility task for a fresh generation
 *  (the partial unique index excludes archived rows). Does NOT touch the
 *  visibility row's status — only publish does that. Idempotent. */
export async function archive(
  draftId: number,
  userId: string,
): Promise<typeof contentDrafts.$inferSelect> {
  const draft = await loadOwnDraft(draftId, userId);
  if (draft.status === "archived") return draft;
  const [updated] = await db
    .update(contentDrafts)
    .set({ status: "archived", updatedAt: new Date() })
    .where(eq(contentDrafts.id, draftId))
    .returning();
  await db.insert(contentDraftEvents).values({
    draftId,
    fromStatus: draft.status,
    toStatus: "archived",
    userId,
  });
  log.info("content_draft_archived", {
    draft_id: draftId,
    user_id: userId,
    from_status: draft.status,
  });
  return updated;
}

/* ============== Reads ============== */

export async function getDraft(
  draftId: number,
  userId: string,
): Promise<typeof contentDrafts.$inferSelect | null> {
  const draft = await db.query.contentDrafts.findFirst({
    where: eq(contentDrafts.id, draftId),
  });
  if (!draft) return null;
  // Don't leak other users' drafts through this endpoint.
  if (draft.userId !== userId) return null;
  return draft;
}

/** List active (non-archived) drafts for a user. Archived rows are excluded
 *  per spec — the archive operation's whole purpose is to remove the draft
 *  from the user's working set. */
export async function listActiveDrafts(
  userId: string,
): Promise<Array<typeof contentDrafts.$inferSelect>> {
  return db.query.contentDrafts.findMany({
    where: and(
      eq(contentDrafts.userId, userId),
      sql`${contentDrafts.status} <> 'archived'`,
    ),
    orderBy: (d, { desc }) => [desc(d.updatedAt)],
  });
}

/** Internal: load a draft and assert ownership. Throws task_not_found-shaped
 *  errors so the API layer can reuse its existing 404 mapping. */
async function loadOwnDraft(draftId: number, userId: string) {
  const draft = await db.query.contentDrafts.findFirst({
    where: eq(contentDrafts.id, draftId),
  });
  if (!draft || draft.userId !== userId) {
    throw new GuardrailError("draft_not_found", "draft not found");
  }
  return draft;
}

/* ============== Default LLM client ============== */
//
// Bypassed in tests — they construct their own stub LLMClient and pass it to
// generateDraft. Production uses Claude via the Anthropic Messages API.
// We hand-roll the call rather than depend on @anthropic-ai/sdk to keep the
// dashboard bundle slim; the surface we need is one POST.

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_VERSION = "2023-06-01";
const ANTHROPIC_MODEL = "claude-opus-4-7";

export function defaultLLMClient(): LLMClient {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    // Lazy throw — route only fails when someone actually generates.
    return {
      async generate() {
        throw new Error("ANTHROPIC_API_KEY is not set");
      },
    };
  }
  return {
    async generate({ query, recommendation, relatedUrl }) {
      const userMsg = [
        `Visibility gap: ${recommendation}`,
        `Target search query: ${query}`,
        relatedUrl ? `Related thread for tone reference: ${relatedUrl}` : "",
        "",
        "Write the draft now.",
      ]
        .filter(Boolean)
        .join("\n");
      const res = await fetch(ANTHROPIC_API, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": apiKey,
          "anthropic-version": ANTHROPIC_VERSION,
        },
        body: JSON.stringify({
          model: ANTHROPIC_MODEL,
          max_tokens: 2000,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: userMsg }],
        }),
      });
      if (!res.ok) {
        throw new Error(`anthropic ${res.status}: ${await res.text()}`);
      }
      const json: { content: Array<{ type: string; text?: string }> } =
        await res.json();
      const text =
        json.content
          ?.filter((b) => b.type === "text" && typeof b.text === "string")
          .map((b) => b.text as string)
          .join("\n") ?? "";
      // The system prompt asks for a JSON object — try parsing. If the model
      // wraps the JSON in prose, extract the first {...} block.
      const parsed = parseGeneratedDraft(text);
      return parsed;
    },
  };
}

function parseGeneratedDraft(text: string): GeneratedDraft {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    // Treat the whole thing as body, derive a title from the first H1.
    const titleMatch = text.match(/^#\s+(.+)$/m);
    return { title: titleMatch?.[1] ?? "Untitled draft", body: text };
  }
  const slice = text.slice(start, end + 1);
  try {
    const obj = JSON.parse(slice) as Partial<GeneratedDraft>;
    if (typeof obj.title === "string" && typeof obj.body === "string") {
      return { title: obj.title, body: obj.body };
    }
  } catch {
    // fall through
  }
  const titleMatch = text.match(/^#\s+(.+)$/m);
  return { title: titleMatch?.[1] ?? "Untitled draft", body: text };
}

export const __test = {
  DAILY_GENERATION_CAP,
  reserveQuota,
  refundQuota,
  parseGeneratedDraft,
};

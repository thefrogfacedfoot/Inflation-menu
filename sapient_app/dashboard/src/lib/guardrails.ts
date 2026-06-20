/**
 * Server-side guardrails. These are the load-bearing safety checks: every
 * write path through the dashboard MUST funnel through this module. The UI
 * mirrors these checks for feedback but never authorizes — these functions do.
 */

import { and, desc, eq, gte, sql } from "drizzle-orm";
import { db } from "@/db/client";
import {
  claims,
  opportunities,
  posts,
  userActiveSubs,
  userProfiles,
} from "@/db/schema";
import { detectProductMention, getAllAliases } from "./product-detect";
import { findDisclosurePhrases, getDisclosurePhrases } from "./disclosure-phrases";
import {
  dashboardGuardrailPauses,
  dashboardGuardrailRejections,
} from "./metrics";
import { log } from "./logging";

const WEEKLY_PROMO_CAP = Number(process.env.WEEKLY_PROMO_CAP ?? 3);
const REMOVAL_RATE_THRESHOLD = Number(process.env.REMOVAL_RATE_THRESHOLD ?? 0.2);
const REMOVAL_RATE_WINDOW = Number(process.env.REMOVAL_RATE_WINDOW ?? 10);

export type GuardrailPayload = Record<string, unknown>;

export class GuardrailError extends Error {
  code: string;
  payload: GuardrailPayload;
  constructor(code: string, message: string, payload: GuardrailPayload = {}) {
    super(message);
    this.code = code;
    this.payload = payload;
  }
}

/** Counter-incrementing reject helper. Every rejection — wherever it
 *  originates — ticks the `code` label so the runaway-user alert PromQL has
 *  a reliable signal. Exported so peer modules (visibility-tasks) funnel
 *  through the same instrumentation. */
export function reject(code: string, message: string, payload: GuardrailPayload = {}): never {
  dashboardGuardrailRejections.inc({ code });
  log.warn("guardrail_rejected", { code, message });
  throw new GuardrailError(code, message, payload);
}

/* ---------- Pause helpers ---------- */

async function pause(userId: string, code: string, reason: string): Promise<void> {
  await db
    .update(userProfiles)
    .set({ isPaused: true, pausedCode: code, pausedReason: reason, pausedAt: new Date() })
    .where(eq(userProfiles.userId, userId));
  dashboardGuardrailPauses.inc({ reason: code });
  log.warn("user_paused", { user_id: userId, code, reason });
}

async function profileOrThrow(userId: string) {
  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, userId),
  });
  if (!profile) reject("no_profile", "user has not onboarded");
  return profile;
}

/* ---------- Eligibility (claim time) ---------- */

export async function assertCanClaim(
  userId: string,
  opportunityId: number,
): Promise<{ subreddit: string }> {
  const profile = await profileOrThrow(userId);
  if (profile.isPaused) {
    reject("paused", `user is paused: ${profile.pausedReason ?? "unknown"}`);
  }

  const opp = await db.query.opportunities.findFirst({
    where: eq(opportunities.id, opportunityId),
  });
  if (!opp) reject("no_opportunity", "opportunity not found");

  const active = await db.query.userActiveSubs.findFirst({
    where: and(
      eq(userActiveSubs.userId, userId),
      eq(userActiveSubs.subreddit, opp.subreddit),
    ),
  });
  if (!active) {
    reject(
      "not_preexisting_active",
      `user has no pre-existing activity in r/${opp.subreddit}`,
    );
  }
  if (!active.matchesExpertise) {
    reject(
      "not_expertise_match",
      `r/${opp.subreddit} is not marked as matching user expertise`,
    );
  }

  await assertWeeklyPromoCap(userId);
  return { subreddit: opp.subreddit };
}

/**
 * Atomic claim. The partial unique index
 *   uniqueIndex(opportunity_id) WHERE state IN ('claimed','posted')
 * is the actual race guard — even if two callers pass assertCanClaim
 * simultaneously, only one INSERT wins.
 *
 * `provenance` lets a caller (today: the visibility-tasks claim flow) tag the
 * row at insert time. We don't change the guardrails — the assertions still
 * fire — but the row records WHERE the opportunity came from. mark-posted
 * later reads `visibilityTaskId` to write back to visibility.tasks.
 */
export async function claimOpportunity(
  userId: string,
  opportunityId: number,
  provenance: { source?: string; visibilityTaskId?: number } = {},
): Promise<{
  id: number;
  userId: string;
  opportunityId: number;
  state: string;
  source: string;
  visibilityTaskId: number | null;
}> {
  await assertCanClaim(userId, opportunityId);
  try {
    const [row] = await db
      .insert(claims)
      .values({
        userId,
        opportunityId,
        state: "claimed",
        source: provenance.source ?? "organic",
        visibilityTaskId: provenance.visibilityTaskId ?? null,
      })
      .returning({
        id: claims.id,
        userId: claims.userId,
        opportunityId: claims.opportunityId,
        state: claims.state,
        source: claims.source,
        visibilityTaskId: claims.visibilityTaskId,
      });
    return row;
  } catch (e) {
    if (isUniqueViolation(e)) {
      reject("already_claimed", "opportunity already claimed");
    }
    throw e;
  }
}

function isUniqueViolation(e: unknown): boolean {
  if (!e || typeof e !== "object") return false;
  const code = (e as { code?: unknown }).code;
  if (code === "23505") return true;
  // pglite surfaces Postgres errors but the wrapper varies — fall back to text.
  const message = (e as { message?: unknown }).message;
  return typeof message === "string" && /unique|duplicate key/i.test(message);
}

/* ---------- Weekly product-mention cap ---------- */

export async function assertWeeklyPromoCap(userId: string): Promise<void> {
  const since = new Date(Date.now() - 7 * 24 * 3600 * 1000);
  const rows = await db
    .select({ n: sql<number>`count(*)::int` })
    .from(posts)
    .where(
      and(
        eq(posts.userId, userId),
        eq(posts.mentionsProduct, true),
        gte(posts.postedAt, since),
      ),
    );
  const count = rows[0]?.n ?? 0;
  if (count >= WEEKLY_PROMO_CAP) {
    await pause(
      userId,
      "weekly_cap_reached",
      `${count} product-mentioning posts in the last 7 days (cap ${WEEKLY_PROMO_CAP})`,
    );
    reject(
      "weekly_cap_reached",
      `user has ${count} product-mentioning posts in the last 7 days (cap ${WEEKLY_PROMO_CAP})`,
      { count, cap: WEEKLY_PROMO_CAP },
    );
  }
}

/* ---------- mark-posted validation ---------- */

export type MarkPostedInput = {
  userId: string;
  opportunityId: number;
  subreddit: string;
  redditThingId: string;
  permalink: string;
  body: string;
  /**
   * Client-supplied "I think this mentions the product" hint. Can flip the
   * stored value from false → true (catches oblique references the detector
   * misses) but never from true → false. The server-detected value is
   * authoritative for "is this product mention?".
   */
  selfReportedMentionsProduct?: boolean;
};

export type MarkPostedCheck = {
  mentionsProduct: boolean;
  matchedAliases: string[];
  acceptedDisclosurePhrases: string[];
  includesDisclosure: boolean;
};

export async function assertCanMarkPosted(input: MarkPostedInput): Promise<MarkPostedCheck> {
  const profile = await profileOrThrow(input.userId);
  if (profile.isPaused) {
    reject("paused", `user is paused: ${profile.pausedReason ?? "unknown"}`);
  }

  const active = await db.query.userActiveSubs.findFirst({
    where: and(
      eq(userActiveSubs.userId, input.userId),
      eq(userActiveSubs.subreddit, input.subreddit),
    ),
  });
  if (!active || !active.matchesExpertise) {
    reject(
      "not_eligible_sub",
      `r/${input.subreddit} is not eligible for this user`,
    );
  }

  const opp = await db.query.opportunities.findFirst({
    where: eq(opportunities.id, input.opportunityId),
  });
  if (!opp) reject("no_opportunity", "opportunity not found");

  const detection = await detectProductMention(input.body);
  // Client may flip false → true, never true → false.
  const mentions = detection.mentioned || input.selfReportedMentionsProduct === true;

  // For [brand]-templated phrases we expand against the matched aliases. If
  // detection found nothing but the user self-reported, fall back to all
  // aliases so they still have a way to satisfy the gate.
  const brandTerms =
    detection.matchedAliases.length > 0
      ? detection.matchedAliases
      : mentions
        ? await getAllAliases()
        : [];
  const matchedPhrases = mentions ? findDisclosurePhrases(input.body, brandTerms) : [];
  const includesDisclosure = matchedPhrases.length > 0;

  if (mentions && !includesDisclosure) {
    reject(
      "disclosure_required",
      "post mentions the product but does not include an explicit disclosure phrase",
      {
        matchedAliases: detection.matchedAliases,
        acceptedDisclosurePhrases: getDisclosurePhrases(),
      },
    );
  }

  return {
    mentionsProduct: mentions,
    matchedAliases: detection.matchedAliases,
    acceptedDisclosurePhrases: matchedPhrases,
    includesDisclosure,
  };
}

/* ---------- Removal-rate auto-pause ---------- */

export async function enforceRemovalRate(userId: string): Promise<{
  paused: boolean;
  rate: number;
  windowSize: number;
}> {
  const recent = await db
    .select({ isRemoved: posts.isRemoved })
    .from(posts)
    .where(eq(posts.userId, userId))
    .orderBy(desc(posts.postedAt))
    .limit(REMOVAL_RATE_WINDOW);

  if (recent.length < REMOVAL_RATE_WINDOW) {
    return { paused: false, rate: 0, windowSize: recent.length };
  }
  const removed = recent.filter((p) => p.isRemoved).length;
  const rate = removed / recent.length;
  if (rate > REMOVAL_RATE_THRESHOLD) {
    await pause(
      userId,
      "removal_rate_exceeded",
      `${(rate * 100).toFixed(0)}% over last ${recent.length} posts`,
    );
    return { paused: true, rate, windowSize: recent.length };
  }
  return { paused: false, rate, windowSize: recent.length };
}

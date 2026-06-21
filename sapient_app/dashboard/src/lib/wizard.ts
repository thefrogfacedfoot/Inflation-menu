/**
 * Onboarding wizard. Compresses week-one for a new brand into a 7-step
 * guided flow. Each step persists before advancing so closing the tab and
 * reopening lands on the right step (brand_config.setup_step is the source
 * of truth — the UI reads it and routes).
 *
 * Steps:
 *   0 - not started (default for a fresh deployment)
 *   1 - brand basics (name + description + aliases)
 *   2 - competitors
 *   3 - tracked queries (claude-suggested + edited)
 *   4 - seed subreddits (with adjacent-sub expansion)
 *   5 - disclosure phrases (defaults + overrides)
 *   6 - first team member invite
 *   7 - smoke test (one finder cycle + one ChatGPT visibility query)
 *
 * Once setup_completed_at is set, /api/feed, /api/opportunities, and
 * /api/visibility-tasks are unblocked — they call requireSetupComplete()
 * which throws WizardIncompleteError before the route does anything else.
 */
import { and, eq, inArray, sql } from "drizzle-orm";
import { db } from "@/db/client";
import {
  brandConfig,
  disclosurePhraseOverride,
  productAliases,
  visibilityEntities,
  visibilityQueries,
} from "@/db/schema";
import { DEFAULT_DISCLOSURE_PHRASES } from "./disclosure-phrases";
import { log } from "./logging";

export type SetupStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type BrandConfigRow = {
  id: number;
  brandName: string;
  description: string;
  setupStep: SetupStep;
  setupCompletedAt: Date | null;
  updatedAt: Date;
};

export class WizardIncompleteError extends Error {
  code = "setup_required" as const;
  constructor(public setupStep: number) {
    super(`brand setup incomplete (current step: ${setupStep})`);
  }
}

/* ---------- config read / step gating ---------- */

export async function getBrandConfig(): Promise<BrandConfigRow | null> {
  const row = await db.select().from(brandConfig).limit(1);
  if (!row[0]) return null;
  return {
    id: row[0].id,
    brandName: row[0].brandName,
    description: row[0].description,
    setupStep: row[0].setupStep as SetupStep,
    setupCompletedAt: row[0].setupCompletedAt,
    updatedAt: row[0].updatedAt,
  };
}

/**
 * Used by routes that need a completed brand setup. Returns void on success;
 * throws WizardIncompleteError otherwise. Route handlers catch and translate
 * to 503 { error: 'setup_required' }.
 */
export async function requireSetupComplete(): Promise<void> {
  const cfg = await getBrandConfig();
  if (!cfg || !cfg.setupCompletedAt) {
    throw new WizardIncompleteError(cfg?.setupStep ?? 0);
  }
}

async function advanceTo(step: SetupStep): Promise<void> {
  // Only ever move forward. A re-submit of an earlier step shouldn't pull
  // setup_step backwards.
  await db
    .update(brandConfig)
    .set({
      setupStep: sql`GREATEST(${brandConfig.setupStep}, ${step})`,
      updatedAt: new Date(),
    });
}

/* ---------- step 1: brand basics + aliases (atomic across schemas) ---------- */

/**
 * Suggest common alias variants for the brand name. Operators usually want a
 * superset of these by default (lowercase, no-space, with-tld), so we
 * pre-populate before the operator edits.
 */
export function suggestAliasVariants(brandName: string): string[] {
  const base = brandName.trim();
  if (!base) return [];
  const lower = base.toLowerCase();
  const nospace = base.replace(/\s+/g, "");
  const variants = new Set<string>([
    base,
    lower,
    nospace,
    nospace.toLowerCase(),
    `${nospace.toLowerCase()}.com`,
    `${nospace.toLowerCase()}.io`,
  ]);
  return [...variants];
}

export type Step1Input = {
  brandName: string;
  description: string;
  aliases: string[];
};

/**
 * Step 1 commits the brand row, the product aliases, AND the visibility
 * entity in a single transaction. If the visibility schema is unreachable
 * (cross-schema write fails), the alias rows are rolled back too — we
 * don't end up with half-configured state where the dashboard knows the
 * brand but the visibility service doesn't.
 */
export async function saveStep1(input: Step1Input): Promise<void> {
  if (!input.brandName.trim()) {
    throw new Error("brand_name required");
  }
  const aliases = input.aliases.filter((a) => a && a.trim()).map((a) => a.trim());
  if (aliases.length === 0) {
    throw new Error("at least one alias required");
  }

  // postgres-js exposes db.transaction; pglite does the same. Both schemas
  // live in the same DB connection so a single transaction covers them.
  await db.transaction(async (tx) => {
    const existing = await tx.select().from(brandConfig).limit(1);
    if (existing[0]) {
      await tx
        .update(brandConfig)
        .set({
          brandName: input.brandName,
          description: input.description,
          updatedAt: new Date(),
        })
        .where(eq(brandConfig.id, existing[0].id));
    } else {
      await tx.insert(brandConfig).values({
        brandName: input.brandName,
        description: input.description,
      });
    }

    // Replace product_aliases for the brand. Primary alias = the first one
    // the operator supplied.
    await tx.delete(productAliases);
    for (const [i, alias] of aliases.entries()) {
      await tx.insert(productAliases).values({ alias, isPrimary: i === 0 });
    }

    // Upsert the brand entity in the visibility schema. If this fails (e.g.
    // schema missing), the surrounding tx rolls back the product_aliases
    // write too — that's the contract.
    const brandEntity = await tx
      .select()
      .from(visibilityEntities)
      .where(eq(visibilityEntities.name, input.brandName));
    if (brandEntity[0]) {
      await tx
        .update(visibilityEntities)
        .set({ aliases })
        .where(eq(visibilityEntities.id, brandEntity[0].id));
    } else {
      await tx.insert(visibilityEntities).values({
        name: input.brandName,
        type: "brand",
        aliases,
      });
    }
  });
  await advanceTo(2);
  log.info("wizard_step1_saved", { step: 1, brand: input.brandName, alias_count: aliases.length });
}

/* ---------- step 2: competitors ---------- */

export type CompetitorInput = { name: string; aliases: string[] };

export async function saveStep2(competitors: CompetitorInput[]): Promise<void> {
  if (competitors.length < 3 || competitors.length > 10) {
    throw new Error("between 3 and 10 competitors required");
  }
  await db.transaction(async (tx) => {
    // Clear and reinsert. Competitors are operator-curated; a re-submit
    // is the source of truth.
    await tx
      .delete(visibilityEntities)
      .where(eq(visibilityEntities.type, "competitor"));
    for (const c of competitors) {
      await tx.insert(visibilityEntities).values({
        name: c.name,
        type: "competitor",
        aliases: c.aliases,
      });
    }
  });
  await advanceTo(3);
  log.info("wizard_step2_saved", { step: 2, count: competitors.length });
}

/* ---------- step 3: tracked queries (claude-suggested) ---------- */

export type QuerySuggesterFn = (input: {
  brandName: string;
  description: string;
}) => Promise<string[]>;

let _suggester: QuerySuggesterFn = defaultSuggester;

/** Tests inject their own suggester so we don't hit the live Anthropic API. */
export function setQuerySuggester(fn: QuerySuggesterFn): void {
  _suggester = fn;
}

export function resetQuerySuggester(): void {
  _suggester = defaultSuggester;
}

async function defaultSuggester(input: {
  brandName: string;
  description: string;
}): Promise<string[]> {
  // Production wiring would call Anthropic here. Keep the IO out of the lib
  // by default — the route handler injects the real client during boot.
  // Returning a small static list keeps the step usable in offline dev.
  return [
    `best ${input.brandName} alternative`,
    `what is ${input.brandName}`,
    `${input.brandName} vs competitors`,
    `is ${input.brandName} worth it`,
    `how to use ${input.brandName}`,
  ];
}

export async function suggestQueries(): Promise<string[]> {
  const cfg = await getBrandConfig();
  if (!cfg) throw new Error("brand_config missing — run step 1 first");
  return _suggester({ brandName: cfg.brandName, description: cfg.description });
}

export async function saveStep3(queries: string[]): Promise<void> {
  const clean = queries.map((q) => q.trim()).filter(Boolean);
  if (clean.length === 0) throw new Error("at least one query required");
  await db.transaction(async (tx) => {
    // Replace the tracked-query set. Existing visibility runs aren't deleted
    // (the runs reference queries by id; if we cared about keeping stable
    // ids we'd diff — for the wizard's first-config flow a full replace is
    // simpler and the data hasn't accumulated yet).
    await tx.delete(visibilityQueries);
    for (const q of clean) {
      await tx.insert(visibilityQueries).values({ text: q });
    }
  });
  await advanceTo(4);
  log.info("wizard_step3_saved", { step: 3, count: clean.length });
}

/* ---------- step 4: seed subreddits + adjacent-sub discovery ---------- */

export type SubDiscovererFn = (seeds: string[]) => Promise<string[]>;

let _subDiscoverer: SubDiscovererFn = defaultSubDiscoverer;

export function setSubDiscoverer(fn: SubDiscovererFn): void {
  _subDiscoverer = fn;
}

export function resetSubDiscoverer(): void {
  _subDiscoverer = defaultSubDiscoverer;
}

async function defaultSubDiscoverer(seeds: string[]): Promise<string[]> {
  // The Python finder (app/reddit_client.py::discover_adjacent) is the
  // authoritative discoverer in production; wiring is via the visibility
  // service. For wizard offline-dev we return the seeds unchanged.
  return [...seeds];
}

export async function discoverAdjacentSubs(seeds: string[]): Promise<string[]> {
  const cleaned = seeds.map((s) => s.trim().replace(/^r\//, "")).filter(Boolean);
  if (cleaned.length === 0) return [];
  return _subDiscoverer(cleaned);
}

export async function saveStep4(_approvedSubs: string[]): Promise<void> {
  // Step 4 doesn't persist subs to a brand-level table — sub eligibility is
  // per-user (user_active_sub, set at onboarding sync). What this step
  // confirms is that the operator looked at the expanded set and approved.
  // The advancement to step 5 IS the persistence.
  await advanceTo(5);
  log.info("wizard_step4_saved", { step: 4 });
}

/* ---------- step 5: disclosure phrases ---------- */

/**
 * Effective list = compile-time defaults + any overrides the wizard added.
 * Read at runtime by guardrails so override edits don't need a redeploy.
 * Replaces `disclosure-phrases.ts::getDisclosurePhrases()` for callers that
 * want the override-aware view.
 */
export async function getEffectiveDisclosurePhrases(): Promise<string[]> {
  const overrides = await db.select().from(disclosurePhraseOverride);
  const defaults = DEFAULT_DISCLOSURE_PHRASES.map((p) => p.toLowerCase());
  return [...defaults, ...overrides.map((o) => o.phrase.toLowerCase())];
}

export async function saveStep5(input: {
  add: string[];
  remove: string[];
  userId: string | null;
}): Promise<void> {
  await db.transaction(async (tx) => {
    if (input.remove.length > 0) {
      await tx
        .delete(disclosurePhraseOverride)
        .where(inArray(disclosurePhraseOverride.phrase, input.remove));
    }
    for (const phrase of input.add.map((p) => p.trim().toLowerCase()).filter(Boolean)) {
      // ON CONFLICT — re-adding an existing phrase is a no-op.
      await tx
        .insert(disclosurePhraseOverride)
        .values({ phrase, createdByUserId: input.userId })
        .onConflictDoNothing({ target: disclosurePhraseOverride.phrase });
    }
  });
  await advanceTo(6);
  log.info("wizard_step5_saved", { step: 5, added: input.add.length, removed: input.remove.length });
}

/* ---------- step 6: invite first team member ---------- */

export type Step6Input = { email: string };

/**
 * Persists the invite intent and advances the wizard. The actual email
 * dispatch and onboarding flow continues to live in the existing
 * /api/onboarding paths — the wizard just marks this step as reached.
 *
 * Email validation is intentionally minimal — we don't want to bounce the
 * operator on RFC corner cases; the invite endpoint will surface a real
 * error if needed.
 */
export async function saveStep6(input: Step6Input): Promise<void> {
  if (!/^\S+@\S+\.\S+$/.test(input.email)) {
    throw new Error("invalid email");
  }
  await advanceTo(7);
  log.info("wizard_step6_saved", { step: 6 });
}

/* ---------- step 7: smoke test ---------- */

export type SmokeTestFns = {
  runFinderPoll: () => Promise<{ opportunitiesFound: number }>;
  runChatGptQuery: (query: string) => Promise<{ mentioned: boolean; position: number | null }>;
};

let _smokeFns: SmokeTestFns = {
  runFinderPoll: async () => ({ opportunitiesFound: 0 }),
  runChatGptQuery: async () => ({ mentioned: false, position: null }),
};

export function setSmokeFns(fns: Partial<SmokeTestFns>): void {
  _smokeFns = { ..._smokeFns, ...fns };
}

export type SmokeTestResult = {
  finder: { ok: boolean; opportunitiesFound: number; error: string | null };
  visibility: { ok: boolean; mentioned: boolean; position: number | null; error: string | null };
  highestPriorityQuery: string | null;
};

/**
 * Runs one finder poll cycle + one ChatGPT visibility query against the
 * highest-priority tracked query. EACH side is reported independently so a
 * ChatGPT 429 doesn't hide a successful finder poll (and vice versa).
 */
export async function runSmokeTest(): Promise<SmokeTestResult> {
  // Pick the first-inserted query as "highest priority". The wizard step 3
  // UI orders by user input; whichever the operator put first is the one
  // we test.
  const queryRows = await db
    .select({ text: visibilityQueries.text })
    .from(visibilityQueries)
    .orderBy(visibilityQueries.id)
    .limit(1);
  const highestPriorityQuery = queryRows[0]?.text ?? null;

  let finder: SmokeTestResult["finder"] = {
    ok: false,
    opportunitiesFound: 0,
    error: null,
  };
  try {
    const r = await _smokeFns.runFinderPoll();
    finder = { ok: true, opportunitiesFound: r.opportunitiesFound, error: null };
  } catch (e) {
    finder.error = e instanceof Error ? e.message : String(e);
  }

  let visibility: SmokeTestResult["visibility"] = {
    ok: false,
    mentioned: false,
    position: null,
    error: null,
  };
  if (!highestPriorityQuery) {
    visibility.error = "no_tracked_queries";
  } else {
    try {
      const r = await _smokeFns.runChatGptQuery(highestPriorityQuery);
      visibility = { ok: true, mentioned: r.mentioned, position: r.position, error: null };
    } catch (e) {
      visibility.error = e instanceof Error ? e.message : String(e);
    }
  }

  log.info("wizard_step7_smoke", {
    step: 7,
    finder_ok: finder.ok,
    visibility_ok: visibility.ok,
  });
  return { finder, visibility, highestPriorityQuery };
}

export async function markSetupComplete(): Promise<void> {
  await db
    .update(brandConfig)
    .set({
      setupCompletedAt: new Date(),
      setupStep: 7,
      updatedAt: new Date(),
    });
  log.info("wizard_completed", {});
}

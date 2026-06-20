import { db } from "@/db/client";
import { productAliases } from "@/db/schema";

export type DetectResult = {
  mentioned: boolean;
  matchedAliases: string[];
};

const REGEX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

function escape(s: string): string {
  return s.replace(REGEX_SPECIAL, "\\$&");
}

/**
 * Build a Unicode-aware, case-insensitive matcher for a single alias. We use
 * `\p{L}` and `\p{N}` lookarounds instead of `\b` because `\b` is ASCII-only —
 * it would (wrongly) treat the boundary between "café" and "x" as a word
 * boundary, and miss the one between "Acme" and "·" inside Unicode text.
 */
function buildAliasRegex(alias: string): RegExp {
  const pattern = `(?<![\\p{L}\\p{N}])${escape(alias)}(?![\\p{L}\\p{N}])`;
  return new RegExp(pattern, "iu");
}

let _cache: { aliases: string[]; loadedAt: number } | null = null;
const CACHE_TTL_MS = 60_000;

async function loadAliases(): Promise<string[]> {
  const now = Date.now();
  if (_cache && now - _cache.loadedAt < CACHE_TTL_MS) return _cache.aliases;
  const rows = await db.select({ alias: productAliases.alias }).from(productAliases);
  _cache = { aliases: rows.map((r) => r.alias), loadedAt: now };
  return _cache.aliases;
}

export function _clearAliasCache(): void {
  _cache = null;
}

/**
 * Synchronous detector — accepts the alias list directly. Use this in tests
 * and from any caller that already has the list in hand.
 */
export function detectWithAliases(body: string, aliases: string[]): DetectResult {
  if (!body || aliases.length === 0) {
    return { mentioned: false, matchedAliases: [] };
  }
  const matched = new Set<string>();
  for (const alias of aliases) {
    if (!alias) continue;
    if (buildAliasRegex(alias).test(body)) matched.add(alias);
  }
  return { mentioned: matched.size > 0, matchedAliases: [...matched] };
}

/** Loads aliases from the DB (cached) and runs detection. */
export async function detectProductMention(body: string): Promise<DetectResult> {
  const aliases = await loadAliases();
  return detectWithAliases(body, aliases);
}

export async function getAllAliases(): Promise<string[]> {
  return loadAliases();
}

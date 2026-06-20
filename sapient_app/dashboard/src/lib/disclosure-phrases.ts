/**
 * Configurable list of disclosure phrases. A post that mentions the product
 * must contain at least one of these (case-insensitive substring match) to
 * pass the disclosure gate.
 *
 * Phrases containing the literal token "[brand]" are expanded against the
 * matched aliases at check time, so "[brand] employee" with brand "Acme"
 * accepts "Acme employee" but not the unexpanded phrase.
 *
 * Override by setting DISCLOSURE_PHRASES env var to a pipe-separated list.
 */

export const DEFAULT_DISCLOSURE_PHRASES: readonly string[] = [
  "disclosure:",
  "disclaimer:",
  "full disclosure",
  "i work on",
  "i work at",
  "i work for",
  "i'm one of the makers",
  "i'm one of the founders",
  "i'm a founder",
  "i'm a co-founder",
  "i'm the founder",
  "i help build",
  "i help make",
  "i built",
  "i made",
  "i co-founded",
  "[brand] employee",
  "[brand] team",
];

export function getDisclosurePhrases(): string[] {
  const env = process.env.DISCLOSURE_PHRASES;
  if (env && env.trim()) {
    return env
      .split("|")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
  }
  return DEFAULT_DISCLOSURE_PHRASES.map((p) => p.toLowerCase());
}

/**
 * Returns the disclosure phrases that actually appear in the body, with
 * `[brand]` placeholders expanded against the supplied brand terms.
 */
export function findDisclosurePhrases(body: string, brandTerms: string[] = []): string[] {
  const text = body.toLowerCase();
  const accepted: string[] = [];
  for (const raw of getDisclosurePhrases()) {
    if (raw.includes("[brand]")) {
      for (const brand of brandTerms) {
        const filled = raw.replaceAll("[brand]", brand.toLowerCase());
        if (text.includes(filled)) accepted.push(filled);
      }
    } else if (text.includes(raw)) {
      accepted.push(raw);
    }
  }
  return accepted;
}

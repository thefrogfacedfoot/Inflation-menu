/**
 * Coverage for src/lib/metrics.ts. The contract under test:
 * every guardrail error code listed in the ops spec must increment
 * `dashboard_guardrail_rejections_total{code=<that code>}`. The unit under
 * test is the `reject()` helper in guardrails.ts — every code in the
 * codebase funnels through it (peer modules like visibility-tasks.ts import
 * it directly), so one assertion per code keeps regressions at the choke
 * point.
 *
 * We do NOT mock the DB here. `reject()` increments the counter, logs, then
 * throws — no DB access. The pause counter is exercised in a separate test
 * because it requires a real DB write.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import {
  CLAIM_TO_POSTED_BUCKETS,
  __resetMetrics,
  dashboardClaimToPostedSeconds,
  dashboardGuardrailPauses,
  dashboardGuardrailRejections,
  registry,
} from "@/lib/metrics";

let reject: typeof import("@/lib/guardrails").reject;
let GuardrailError: typeof import("@/lib/guardrails").GuardrailError;

beforeAll(async () => {
  const guardrails = await import("@/lib/guardrails");
  reject = guardrails.reject;
  GuardrailError = guardrails.GuardrailError;
});

async function counterValue(
  metric: typeof dashboardGuardrailRejections | typeof dashboardGuardrailPauses,
  labels: Record<string, string>,
): Promise<number> {
  // Cheap way to read a label combo without poking at prom-client internals:
  // prom-client's registry can emit JSON for tests.
  const data = await (
    metric as unknown as { get(): Promise<{ values: Array<{ value: number; labels: Record<string, string> }> }> }
  ).get();
  for (const v of data.values) {
    if (
      Object.entries(labels).every(([k, val]) => v.labels[k] === val)
    ) {
      return v.value;
    }
  }
  return 0;
}

beforeEach(() => {
  __resetMetrics();
});

afterEach(() => {
  __resetMetrics();
});

/* ---------- rejections, one per code ---------- */

// Codes from the ops spec.
const GUARDRAIL_CODES = [
  "weekly_cap_reached",
  "removal_rate_exceeded",
  "disclosure_required",
  "not_preexisting_active",
  "not_expertise_match",
  "already_claimed",
  "not_claimable_kind",
] as const;

describe("dashboard_guardrail_rejections_total", () => {
  for (const code of GUARDRAIL_CODES) {
    it(`increments for code=${code}`, async () => {
      expect(() => reject(code, `rejected: ${code}`)).toThrow(GuardrailError);
      expect(await counterValue(dashboardGuardrailRejections, { code })).toBe(1);
    });
  }

  it("each call adds 1 (cumulative)", async () => {
    expect(() => reject("weekly_cap_reached", "x")).toThrow();
    expect(() => reject("weekly_cap_reached", "y")).toThrow();
    expect(() => reject("weekly_cap_reached", "z")).toThrow();
    expect(
      await counterValue(dashboardGuardrailRejections, {
        code: "weekly_cap_reached",
      }),
    ).toBe(3);
  });

  it("labels segregate counts", async () => {
    expect(() => reject("disclosure_required", "x")).toThrow();
    expect(() => reject("already_claimed", "y")).toThrow();
    expect(
      await counterValue(dashboardGuardrailRejections, {
        code: "disclosure_required",
      }),
    ).toBe(1);
    expect(
      await counterValue(dashboardGuardrailRejections, {
        code: "already_claimed",
      }),
    ).toBe(1);
    // Untouched code stays at 0.
    expect(
      await counterValue(dashboardGuardrailRejections, {
        code: "weekly_cap_reached",
      }),
    ).toBe(0);
  });
});

describe("/metrics registration", () => {
  it("rejections counter is registered in the shared registry", async () => {
    const text = await registry.metrics();
    expect(text).toContain("dashboard_guardrail_rejections_total");
    expect(text).toContain("dashboard_guardrail_pauses_total");
    expect(text).toContain("dashboard_posts_total");
    expect(text).toContain("dashboard_claim_to_posted_seconds");
  });
});

/* ---------- claim-to-posted histogram buckets ---------- */

function parseBuckets(promText: string): Record<string, number> {
  // Pull `dashboard_claim_to_posted_seconds_bucket{le="..."} N` lines.
  const buckets: Record<string, number> = {};
  for (const line of promText.split("\n")) {
    const m = line.match(
      /^dashboard_claim_to_posted_seconds_bucket\{le="([^"]+)"\}\s+(\d+(?:\.\d+)?)/,
    );
    if (m) buckets[m[1]] = Number(m[2]);
  }
  return buckets;
}

describe("dashboard_claim_to_posted_seconds buckets", () => {
  it("uses the documented bucket boundaries (1m/5m/15m/1h/4h/1d)", async () => {
    // prom-client only emits bucket lines once the histogram has at least
    // one observation. One nudge is enough to materialize the schema.
    dashboardClaimToPostedSeconds.observe(0);
    const text = await registry.metrics();
    const buckets = parseBuckets(text);
    const finite = Object.keys(buckets)
      .filter((k) => k !== "+Inf")
      .map(Number)
      .sort((a, b) => a - b);
    expect(finite).toEqual([...CLAIM_TO_POSTED_BUCKETS]);
  });

  it("observations land in the expected cumulative buckets", async () => {
    // prom-client buckets are cumulative — every bucket count is "number
    // of observations with value ≤ that boundary." So 60 lands in every
    // bucket ≥60, 3600 lands in buckets ≥3600, etc.
    dashboardClaimToPostedSeconds.observe(60); // 1m
    dashboardClaimToPostedSeconds.observe(3600); // 1h
    dashboardClaimToPostedSeconds.observe(86400); // 1d
    dashboardClaimToPostedSeconds.observe(172800); // 2d — over the top finite bucket

    const text = await registry.metrics();
    const b = parseBuckets(text);

    // 60 ≤ every bucket; 3600 ≤ 3600/14400/86400/Inf; 86400 ≤ 86400/Inf;
    // 172800 ≤ Inf only.
    expect(b["60"]).toBe(1); // 60 only
    expect(b["300"]).toBe(1); // 60 only
    expect(b["900"]).toBe(1); // 60 only
    expect(b["3600"]).toBe(2); // 60 + 3600
    expect(b["14400"]).toBe(2); // 60 + 3600
    expect(b["86400"]).toBe(3); // 60 + 3600 + 86400
    expect(b["+Inf"]).toBe(4); // all four
  });

  it("count and sum match the four observations", async () => {
    dashboardClaimToPostedSeconds.observe(60);
    dashboardClaimToPostedSeconds.observe(3600);
    dashboardClaimToPostedSeconds.observe(86400);
    dashboardClaimToPostedSeconds.observe(172800);

    const text = await registry.metrics();
    const countLine = text
      .split("\n")
      .find((l) => l.startsWith("dashboard_claim_to_posted_seconds_count"));
    const sumLine = text
      .split("\n")
      .find((l) => l.startsWith("dashboard_claim_to_posted_seconds_sum"));
    expect(countLine?.split(/\s+/).pop()).toBe("4");
    expect(Number(sumLine?.split(/\s+/).pop())).toBe(60 + 3600 + 86400 + 172800);
  });
});

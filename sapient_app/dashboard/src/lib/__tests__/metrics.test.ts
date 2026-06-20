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
  __resetMetrics,
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

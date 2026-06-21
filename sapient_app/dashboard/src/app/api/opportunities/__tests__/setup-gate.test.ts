/**
 * /api/opportunities is gated on brand_config.setup_completed_at — until the
 * wizard finishes step 7 the route returns 503 with error="setup_required".
 * Same gate is wired into /api/visibility-tasks via @/lib/wizard.
 */
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createTestDb, resetDb, type TestDb } from "../../../../lib/__tests__/_helpers/db";
import { resetSeedCounters, seedUser } from "../../../../lib/__tests__/_helpers/seed";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

// Inject a fixed session so the route handler bypasses real auth.
vi.mock("../../../../../auth", () => ({
  auth: async () => ({ user: { id: "u_session" } }),
}));

let route: typeof import("../route");
let wizard: typeof import("@/lib/wizard");

beforeAll(async () => {
  route = await import("../route");
  wizard = await import("@/lib/wizard");
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

describe("/api/opportunities — setup gate", () => {
  it("returns 503 setup_required when wizard isn't complete", async () => {
    await seedUser(testDb, { id: "u_session" });
    const req = new Request("http://localhost/api/opportunities?min_score=60");
    const res = await route.GET(req);
    expect(res.status).toBe(503);
    const json = (await res.json()) as { error: string };
    expect(json.error).toBe("setup_required");
  });

  it("returns 200 (with possibly-empty items) after markSetupComplete", async () => {
    await seedUser(testDb, { id: "u_session" });
    await wizard.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await wizard.markSetupComplete();
    const req = new Request("http://localhost/api/opportunities?min_score=60");
    const res = await route.GET(req);
    expect(res.status).toBe(200);
    const json = (await res.json()) as { items: unknown[] };
    expect(Array.isArray(json.items)).toBe(true);
  });
});

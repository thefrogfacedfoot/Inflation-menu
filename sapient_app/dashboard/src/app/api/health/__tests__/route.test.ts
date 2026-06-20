/**
 * Schema-aware /health on the dashboard. Both public.claim and
 * visibility.tasks must resolve to a real relation. We exercise both
 * failure shapes against the pglite test DB:
 *   - drop public.claim → 503 names public.claim missing
 *   - drop visibility schema → 503 names visibility.tasks missing
 *   - both present → 200
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createTestDb, pgFor, resetDb, type TestDb } from "../../../../lib/__tests__/_helpers/db";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let route: typeof import("../route");

beforeAll(async () => {
  route = await import("../route");
});

// Read the full test-schema.sql once so tests that drop tables can
// reinstall everything from scratch on the next beforeEach. resetDb()
// alone TRUNCATES — it can't restore a dropped table.
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const DDL = readFileSync(
  join(__dirname, "../../../../db/test-schema.sql"),
  "utf8",
);

beforeEach(async () => {
  // Drop+recreate guarantees a clean slate even if the previous test
  // dropped a table the truncate path needs.
  const pg = pgFor(testDb);
  await pg.exec(`
    DROP SCHEMA IF EXISTS visibility CASCADE;
    DROP TABLE IF EXISTS
      content_draft_event, content_draft, content_draft_quota,
      post, claim, user_active_sub, user_profile, opportunities,
      product_aliases, karma_snapshot, "user", verificationToken,
      session, account
    CASCADE;
  `);
  await pg.exec(DDL);
});

describe("/api/health", () => {
  it("returns 200 ok when both checks pass", async () => {
    const res = await route.GET();
    expect(res.status).toBe(200);
    const json = (await res.json()) as { status: string; service: string };
    expect(json).toEqual({ status: "ok", service: "dashboard" });
  });

  it("returns 503 with reason when visibility.tasks is missing", async () => {
    await pgFor(testDb).exec("DROP SCHEMA visibility CASCADE");
    const res = await route.GET();
    expect(res.status).toBe(503);
    const json = (await res.json()) as { check: string };
    expect(json.check).toBe("visibility.tasks missing");
  });

  it("returns 503 with reason when public.claim is missing", async () => {
    await pgFor(testDb).exec("DROP TABLE claim CASCADE");
    const res = await route.GET();
    expect(res.status).toBe(503);
    const json = (await res.json()) as { check: string };
    expect(json.check).toBe("public.claim missing");
  });
});

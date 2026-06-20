/**
 * Per-file pglite instance for guardrail tests. Each test file calls
 * `createTestDb()` from inside a vi.mock factory; the same instance is reused
 * across tests in that file, with `resetDb()` truncating between tests.
 */
import { PGlite } from "@electric-sql/pglite";
import { drizzle } from "drizzle-orm/pglite";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as schema from "@/db/schema";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const DDL_PATH = join(__dirname, "../../../db/test-schema.sql");

export type TestDb = ReturnType<typeof drizzle<typeof schema>>;

// We keep a sidecar map of (TestDb → underlying PGlite) so callers can run
// multi-statement DDL directly through pg.exec(). Drizzle's db.execute() goes
// through the extended/prepared protocol, which rejects multi-cmd strings.
const _pgByDb = new WeakMap<TestDb, PGlite>();

export function pgFor(db: TestDb): PGlite {
  const pg = _pgByDb.get(db);
  if (!pg) throw new Error("TestDb missing PGlite backref — was it built with createTestDb?");
  return pg;
}

export async function createTestDb(): Promise<TestDb> {
  const pg = new PGlite();
  const ddl = readFileSync(DDL_PATH, "utf8");
  await pg.exec(ddl);
  const db = drizzle(pg, { schema });
  _pgByDb.set(db, pg);
  return db;
}

/** Idempotent DDL for the visibility schema + tasks table. Re-run on every
 *  reset so a test that DROPs the schema (to simulate "tracker unreachable")
 *  doesn't poison subsequent tests. Keep in sync with src/db/test-schema.sql.
 *  Multi-statement is fine — we route through PGlite.exec() (simple query
 *  protocol), not the prepared statement path. */
const VISIBILITY_DDL = `
  CREATE SCHEMA IF NOT EXISTS visibility;
  CREATE TABLE IF NOT EXISTS visibility.tasks (
    id                            integer PRIMARY KEY,
    kind                          text NOT NULL,
    query_id                      integer NOT NULL,
    entity_id                     integer,
    related_url                   text,
    suggested_subreddit           text,
    recommendation                text NOT NULL,
    finder_opportunity_id         integer,
    status                        text NOT NULL DEFAULT 'open',
    claimed_by_user_id            text,
    claimed_at                    timestamptz,
    dashboard_post_id             integer,
    dashboard_content_draft_id    integer,
    dismiss_reason                text,
    created_at                    timestamptz NOT NULL DEFAULT now()
  );
`;

const TRUNCATE_ALL = `
  TRUNCATE TABLE visibility.tasks, content_draft_event, content_draft,
    content_draft_quota, post, claim, user_active_sub,
    user_profile, opportunities, product_aliases, karma_snapshot, "user"
    RESTART IDENTITY CASCADE;
`;

export async function resetDb(db: TestDb): Promise<void> {
  const pg = pgFor(db);
  await pg.exec(VISIBILITY_DDL);
  await pg.exec(TRUNCATE_ALL);
}

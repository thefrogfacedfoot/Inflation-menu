// Vitest setup: ensure DATABASE_URL is set before any module loads
// src/db/client.ts (which throws on missing URL). Tests don't use the real
// postgres-js client — guardrail tests vi.mock("@/db/client") with a pglite
// instance, and pure-function tests never call into it.
process.env.DATABASE_URL ??= "postgres://test:test@localhost:5432/test";

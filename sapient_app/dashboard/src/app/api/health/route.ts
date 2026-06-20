import { NextResponse } from "next/server";
import { sql } from "drizzle-orm";
import { db } from "@/db/client";

export const dynamic = "force-dynamic";

/**
 * Schema-aware readiness probe. pg_isready (used by the postgres container's
 * own healthcheck) only verifies the protocol layer; this catches the "DB
 * accepted the connection but the dashboard's migrations didn't land" case
 * — and the parallel "visibility service never ran its migrations either"
 * case, which manifests as silent feed degradation rather than a 500.
 *
 * Both tables must exist. The check is split (claim → dashboard's own
 * migrations; visibility.tasks → cross-schema readiness) so the failure
 * reason names which side regressed.
 *
 * Returns 200 only when both checks pass; 503 with the failing check name
 * otherwise. The k8s/loose-restart scenario this guards against: app comes
 * up before migrate.sh has run, accepts traffic, errors immediately.
 */
type Check = {
  ok: boolean;
  // `null` on the ok path; the failure reason otherwise so callers don't
  // have to parse messages.
  reason: string | null;
};

export async function _schemaCheck(): Promise<Check> {
  try {
    // drizzle's db.execute returns different shapes per driver — postgres-js
    // hands back a Result whose iterable rows are at the top level, pglite
    // wraps them in `.rows`. Normalize to a row array so the route doesn't
    // care which is wired up.
    const result = (await db.execute(sql`
      SELECT
        to_regclass('public.claim')      AS claim_oid,
        to_regclass('visibility.tasks')  AS tasks_oid
    `)) as unknown;
    const rows = extractRows(result);
    const row = rows[0] as
      | { claim_oid: string | null; tasks_oid: string | null }
      | undefined;
    if (!row?.claim_oid) return { ok: false, reason: "public.claim missing" };
    if (!row?.tasks_oid) {
      return { ok: false, reason: "visibility.tasks missing" };
    }
    return { ok: true, reason: null };
  } catch (e) {
    const err = e instanceof Error ? e : new Error(String(e));
    return {
      ok: false,
      reason: `db_query_failed: ${(err.constructor && err.constructor.name) || "Error"}: ${err.message}`,
    };
  }
}

function extractRows(result: unknown): unknown[] {
  if (Array.isArray(result)) return result;
  if (
    result &&
    typeof result === "object" &&
    Array.isArray((result as { rows?: unknown[] }).rows)
  ) {
    return (result as { rows: unknown[] }).rows;
  }
  return [];
}

export async function GET() {
  const check = await _schemaCheck();
  if (!check.ok) {
    return NextResponse.json(
      { status: "error", service: "dashboard", check: check.reason },
      { status: 503 },
    );
  }
  return NextResponse.json({ status: "ok", service: "dashboard" });
}

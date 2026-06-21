/**
 * Storage backend for export bundles. The lib accepts an ExportStorage
 * implementation so tests inject an in-memory fake; production wires the
 * S3 / local-volume default.
 *
 * Default behavior (no impl passed): write the bundle to disk under
 * GDPR_EXPORT_DIR (defaults to /tmp/gdpr-exports), return a file:// URL.
 * For real prod, swap in an S3 presigned-URL impl via setDefaultStorage.
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

export type ExportStorage = {
  put: (args: {
    requestId: number;
    userId: string;
    bundle: unknown;
    correlationId: string;
  }) => Promise<{ url: string }>;
};

const EXPORT_DIR = process.env.GDPR_EXPORT_DIR ?? "/tmp/gdpr-exports";
const URL_TTL_DAYS = 7;

const localStorage: ExportStorage = {
  put: async ({ requestId, userId, bundle }) => {
    mkdirSync(EXPORT_DIR, { recursive: true });
    const path = join(EXPORT_DIR, `gdpr-${requestId}-${userId}.json`);
    writeFileSync(path, JSON.stringify(bundle, null, 2));
    // file:// is fine for the local-volume dev path; the prod impl returns
    // a signed S3 URL with an explicit expiry. URL_TTL_DAYS is a contract
    // hint the UI surfaces to the user.
    return { url: `file://${path}` };
  },
};

let _default: ExportStorage = localStorage;

export function setDefaultStorage(s: ExportStorage): void {
  _default = s;
}

export function resetDefaultStorage(): void {
  _default = localStorage;
}

export function getUrlTtlDays(): number {
  return URL_TTL_DAYS;
}

export async function uploadExportBundle(
  args: Parameters<ExportStorage["put"]>[0],
  override?: ExportStorage,
): Promise<{ url: string }> {
  return (override ?? _default).put(args);
}

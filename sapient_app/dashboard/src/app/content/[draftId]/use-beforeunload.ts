/**
 * Pulls the beforeunload-flush logic out of editor.tsx so it can be tested
 * without rendering the React tree. Editor uses both exports:
 *   - useBeforeUnloadFlush(): React hook that wires the handler to
 *     window.beforeunload.
 *   - makeBeforeUnloadHandler(): the underlying factory — pure function,
 *     no React, easy to assert against in unit tests.
 *
 * Contract:
 *   - When hasPendingChanges() returns true, the handler PATCHes the draft
 *     with the latest body + title under fetch's keepalive flag so the
 *     request survives page unload.
 *   - When there are no pending changes, the handler does nothing.
 *   - The handler does NOT preventDefault(): browsers would otherwise show
 *     a "leave the page?" confirm dialog. We want a silent save.
 *   - The handler does NOT dedupe across repeated calls. Two unloads = two
 *     PATCHes; the server's idempotent on body content.
 */
import { useEffect } from "react";

export type BeforeUnloadOpts = {
  draftId: number;
  hasPendingChanges: () => boolean;
  getPayload: () => { title: string; body: string };
  /** Inject in tests; defaults to global fetch in production. */
  fetchImpl?: typeof fetch;
};

export function makeBeforeUnloadHandler(opts: BeforeUnloadOpts): () => void {
  return () => {
    if (!opts.hasPendingChanges()) return;
    const f = opts.fetchImpl ?? fetch;
    const { title, body } = opts.getPayload();
    f(`/api/content-drafts/${opts.draftId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, body }),
      keepalive: true,
    });
  };
}

/** React hook wrapper. The factory above is what tests target; this just
 *  attaches it to the window. */
export function useBeforeUnloadFlush(opts: BeforeUnloadOpts): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = makeBeforeUnloadHandler(opts);
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
    // The opts object is rebuilt every render in the caller, but the
    // factory reads its closures at call time — so attaching a fresh
    // listener per render is the right behavior, not a leak.
  }, [opts]);
}

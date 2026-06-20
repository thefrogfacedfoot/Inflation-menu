/**
 * Coverage for the beforeunload-flush factory used by the content-draft
 * editor. We target the factory directly rather than rendering Editor + a
 * DOM — the contract that matters lives in the closure here, and skipping
 * JSDOM + testing-library keeps the test surface small.
 *
 * Three cases per the spec:
 *   1. Edits present → PATCH with the latest body.
 *   2. No pending changes → no fetch.
 *   3. Two unload events with pending changes → two PATCHes (no dedupe;
 *      cheap and the server is idempotent on body content).
 */
import { describe, expect, it, vi } from "vitest";
import { makeBeforeUnloadHandler } from "../use-beforeunload";

type FetchInit = RequestInit | undefined;
function makeStubFetch() {
  return vi.fn(
    async (_url: RequestInfo | URL, _init?: FetchInit) =>
      new Response("ok", { status: 200 }),
  );
}

describe("makeBeforeUnloadHandler", () => {
  it("PATCHes the draft with keepalive when there are pending changes", () => {
    const fetchImpl = makeStubFetch();
    const handler = makeBeforeUnloadHandler({
      draftId: 42,
      hasPendingChanges: () => true,
      getPayload: () => ({ title: "T", body: "latest body" }),
      fetchImpl,
    });

    handler();

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/content-drafts/42");
    expect(init?.method).toBe("PATCH");
    expect(init?.keepalive).toBe(true);
    expect(init?.headers).toMatchObject({
      "Content-Type": "application/json",
    });
    const parsed = JSON.parse(init?.body as string);
    expect(parsed).toEqual({ title: "T", body: "latest body" });
  });

  it("reads the LATEST body on each invocation (via the closure)", () => {
    const fetchImpl = makeStubFetch();
    let title = "first";
    let body = "first body";
    const handler = makeBeforeUnloadHandler({
      draftId: 1,
      hasPendingChanges: () => true,
      getPayload: () => ({ title, body }),
      fetchImpl,
    });

    title = "second";
    body = "second body";
    handler();

    const parsed = JSON.parse(fetchImpl.mock.calls[0][1]?.body as string);
    expect(parsed).toEqual({ title: "second", body: "second body" });
  });

  it("does NOT fetch when hasPendingChanges returns false", () => {
    const fetchImpl = makeStubFetch();
    const handler = makeBeforeUnloadHandler({
      draftId: 99,
      hasPendingChanges: () => false,
      getPayload: () => ({ title: "x", body: "y" }),
      fetchImpl,
    });

    handler();

    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("two invocations with pending changes → two fetches (no dedupe)", () => {
    const fetchImpl = makeStubFetch();
    const handler = makeBeforeUnloadHandler({
      draftId: 7,
      hasPendingChanges: () => true,
      getPayload: () => ({ title: "T", body: "B" }),
      fetchImpl,
    });

    handler();
    handler();

    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("dispatches no fetch when hasPendingChanges flips between calls", () => {
    const fetchImpl = makeStubFetch();
    let pending = true;
    const handler = makeBeforeUnloadHandler({
      draftId: 5,
      hasPendingChanges: () => pending,
      getPayload: () => ({ title: "T", body: "B" }),
      fetchImpl,
    });

    handler();
    expect(fetchImpl).toHaveBeenCalledTimes(1);

    pending = false;
    handler();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});

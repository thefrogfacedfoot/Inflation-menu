/**
 * Composes auth + correlation-id propagation. Runs at the edge (Next.js
 * middleware runtime), so it CANNOT touch the AsyncLocalStorage store —
 * that's a Node-runtime API. Instead, it injects/forwards the
 * X-Correlation-Id header; route handlers (under Node) read it via
 * `withLogContext` and stash it into ALS.
 */
import { NextResponse } from "next/server";
import { auth } from "./auth";

const HEADER = "x-correlation-id";

function newId(): string {
  // crypto.randomUUID is available in the Edge runtime.
  return globalThis.crypto.randomUUID();
}

export default auth(async (req) => {
  const incoming = req.headers.get(HEADER) ?? newId();
  // Pass through to downstream handlers AND echo on the response so callers
  // can correlate. The header is added to the request via the rewrite
  // pattern Next supports out of the box.
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set(HEADER, incoming);
  const res = NextResponse.next({ request: { headers: requestHeaders } });
  res.headers.set(HEADER, incoming);
  return res;
});

export const config = {
  matcher: ["/((?!api/auth|api/health|_next/static|_next/image|favicon.ico|signin).*)"],
};

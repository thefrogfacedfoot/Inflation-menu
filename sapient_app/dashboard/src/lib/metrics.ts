/**
 * Prometheus metrics for the dashboard.
 *
 * The /metrics endpoint runs on a sidecar port (METRICS_PORT, default 9091),
 * NOT on the Next.js port. Boot is wired through Next's instrumentation hook
 * — see dashboard/instrumentation.ts.
 *
 * Counter labels are kept low-cardinality. `code` enumerates known guardrail
 * codes; we avoid arbitrary user-supplied strings.
 */
import http from "node:http";
import {
  Counter,
  Histogram,
  Registry,
  collectDefaultMetrics,
} from "prom-client";

export const registry = new Registry();
collectDefaultMetrics({ register: registry });

export const dashboardGuardrailRejections = new Counter({
  name: "dashboard_guardrail_rejections_total",
  help: "Server-side guardrail rejections by code",
  labelNames: ["code"] as const,
  registers: [registry],
});

export const dashboardGuardrailPauses = new Counter({
  name: "dashboard_guardrail_pauses_total",
  help: "Times a user was auto-paused, by reason",
  labelNames: ["reason"] as const,
  registers: [registry],
});

export const dashboardPostsTotal = new Counter({
  name: "dashboard_posts_total",
  help: "Posts recorded via mark-posted",
  labelNames: ["source", "mentioned_product"] as const,
  registers: [registry],
});

// Bucket boundaries: 1m / 5m / 15m / 1h / 4h / 1d. Tuned to the actual
// distribution of "user claims an opportunity then comes back to post" —
// most resolve in under an hour, a long tail stretches to a day, beyond
// that the claim is effectively abandoned (Inf catches it). Don't expand
// the high end without confirming the abandonment threshold first; extra
// buckets cost cardinality.
export const CLAIM_TO_POSTED_BUCKETS = [60, 300, 900, 3600, 14400, 86400] as const;

export const dashboardClaimToPostedSeconds = new Histogram({
  name: "dashboard_claim_to_posted_seconds",
  help: "Wall time between claim and mark-posted for the same claim",
  buckets: [...CLAIM_TO_POSTED_BUCKETS],
  registers: [registry],
});

let _server: http.Server | null = null;

export function startMetricsServer(port?: number): http.Server {
  if (_server) return _server;
  const p = port ?? Number(process.env.METRICS_PORT ?? 9091);
  _server = http.createServer(async (req, res) => {
    if (req.url === "/metrics") {
      res.setHeader("Content-Type", registry.contentType);
      res.end(await registry.metrics());
      return;
    }
    if (req.url === "/health") {
      res.setHeader("Content-Type", "application/json");
      res.end('{"status":"ok"}');
      return;
    }
    res.statusCode = 404;
    res.end();
  });
  _server.listen(p);
  return _server;
}

/** Test-only: reset counter values without unregistering the metrics. */
export function __resetMetrics(): void {
  registry.resetMetrics();
}

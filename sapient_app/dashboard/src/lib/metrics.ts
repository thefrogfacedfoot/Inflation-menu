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

export const dashboardClaimToPostedSeconds = new Histogram({
  name: "dashboard_claim_to_posted_seconds",
  help: "Wall time between claim and mark-posted for the same claim",
  buckets: [60, 300, 900, 3600, 10800, 43200, 86400, 259200, 604800],
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

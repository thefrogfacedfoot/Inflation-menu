/**
 * Next.js boot hook. Runs once per process, before request handling.
 * We use it to start the metrics sidecar — the Next.js port stays free of
 * scrape traffic.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (process.env.METRICS_DISABLED === "1") return;
  const { startMetricsServer } = await import("@/lib/metrics");
  startMetricsServer();
}

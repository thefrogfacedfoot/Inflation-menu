/**
 * Structured logging for the dashboard.
 *
 * Required fields on every line per the ops spec:
 *   ts (ISO 8601), level, service, correlation_id, user_id (when known),
 *   event (snake_case verb), plus arbitrary context.
 *
 * Correlation id propagates via Node's AsyncLocalStorage so the same
 * request's logs share an id across `await` boundaries without callers
 * threading it through. Next.js middleware runs at the edge and can't
 * touch ALS — it generates/forwards the X-Correlation-Id header, and route
 * handlers (or the wrapper below) drop it into the ALS store.
 */
import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";
import pino from "pino";

export type LogContext = {
  correlationId?: string;
  userId?: string;
};

const als = new AsyncLocalStorage<LogContext>();

export function getLogContext(): LogContext {
  return als.getStore() ?? {};
}

export function getCorrelationId(): string | undefined {
  return als.getStore()?.correlationId;
}

export function runWithLogContext<T>(
  ctx: LogContext,
  fn: () => T | Promise<T>,
): T | Promise<T> {
  return als.run(ctx, fn);
}

/**
 * Route-handler wrapper. Extracts X-Correlation-Id from the incoming request
 * (or generates a UUID), then runs the handler under ALS. Use this on routes
 * where you want auto-propagation without hand-threading context.
 */
export function withLogContext<A, T>(
  handler: (req: Request, ctx: A) => Promise<T>,
): (req: Request, ctx: A) => Promise<T> {
  return (req, ctx) => {
    const correlationId =
      req.headers.get("x-correlation-id") ?? randomUUID();
    return als.run({ correlationId }, () => handler(req, ctx));
  };
}

// ---- pino instance -----------------------------------------------------------

// We use a custom destination in tests; tests inject their own via
// `__setTestDestination`. In prod the default pino sink (stdout) applies.
let _destination: pino.DestinationStream | undefined = undefined;

const SERVICE = process.env.SERVICE_NAME ?? "dashboard";

function buildLogger(): pino.Logger {
  return pino(
    {
      level: process.env.LOG_LEVEL ?? "info",
      timestamp: pino.stdTimeFunctions.isoTime,
      formatters: {
        level: (label) => ({ level: label }),
        bindings: () => ({ service: SERVICE }),
      },
      messageKey: "event",
    },
    _destination,
  );
}

let _logger = buildLogger();

export function __setTestDestination(dest: pino.DestinationStream): void {
  _destination = dest;
  _logger = buildLogger();
}

export function __resetTestDestination(): void {
  _destination = undefined;
  _logger = buildLogger();
}

type Level = "debug" | "info" | "warn" | "error";

function emit(
  level: Level,
  event: string,
  fields: Record<string, unknown> = {},
): void {
  const store = als.getStore() ?? {};
  _logger[level]({
    correlation_id: store.correlationId,
    user_id: store.userId,
    ...fields,
    event,
  });
}

export const log = {
  debug: (event: string, fields?: Record<string, unknown>) => emit("debug", event, fields),
  info: (event: string, fields?: Record<string, unknown>) => emit("info", event, fields),
  warn: (event: string, fields?: Record<string, unknown>) => emit("warn", event, fields),
  error: (event: string, fields?: Record<string, unknown>) => emit("error", event, fields),
};

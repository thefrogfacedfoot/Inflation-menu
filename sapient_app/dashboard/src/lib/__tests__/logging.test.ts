/**
 * Coverage for src/lib/logging.ts.
 *
 * Two properties matter most:
 *   1. correlation_id propagates across `await` boundaries via ALS
 *   2. every emitted line carries the required fields
 *      (ts, level, service, correlation_id, user_id when known, event)
 *
 * We swap pino's destination for a buffer via __setTestDestination so we can
 * read raw lines back as JSON without involving stdout capture.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  __resetTestDestination,
  __setTestDestination,
  getCorrelationId,
  log,
  runWithLogContext,
  withLogContext,
} from "@/lib/logging";

type LogLine = {
  ts?: string;
  time?: string;
  level: string;
  service: string;
  correlation_id?: string;
  user_id?: string;
  event: string;
  [k: string]: unknown;
};

function makeBuffer() {
  let chunks = "";
  return {
    write(s: string) {
      chunks += s;
    },
    lines(): LogLine[] {
      return chunks
        .split("\n")
        .filter((l) => l.startsWith("{"))
        .map((l) => JSON.parse(l) as LogLine);
    },
    reset() {
      chunks = "";
    },
  };
}

let buf: ReturnType<typeof makeBuffer>;

beforeEach(() => {
  buf = makeBuffer();
  __setTestDestination({ write: buf.write });
});

afterEach(() => {
  __resetTestDestination();
});

describe("structured logging", () => {
  it("emits required fields on every line", () => {
    runWithLogContext({ correlationId: "cid-aaaa", userId: "u-1" }, () => {
      log.info("test_event", { extra: 42 });
    });
    const [line] = buf.lines();
    expect(line.event).toBe("test_event");
    expect(line.level).toBe("info");
    expect(line.service).toBe("dashboard");
    expect(line.correlation_id).toBe("cid-aaaa");
    expect(line.user_id).toBe("u-1");
    expect(line.extra).toBe(42);
    // pino's isoTime emits ISO 8601 in the `time` field.
    expect(typeof line.time).toBe("string");
    expect(line.time).toMatch(/T.*Z$/);
  });

  it("propagates correlation_id across awaits", async () => {
    await runWithLogContext({ correlationId: "cid-await" }, async () => {
      expect(getCorrelationId()).toBe("cid-await");
      await Promise.resolve();
      await new Promise((r) => setTimeout(r, 1));
      // Still here after two awaits — that's the property under test.
      expect(getCorrelationId()).toBe("cid-await");
      log.info("after_await");
    });
    const [line] = buf.lines();
    expect(line.correlation_id).toBe("cid-await");
  });

  it("isolates contexts between concurrent runs", async () => {
    const seen: string[] = [];
    await Promise.all([
      runWithLogContext({ correlationId: "cid-a" }, async () => {
        await new Promise((r) => setTimeout(r, 5));
        seen.push(getCorrelationId() ?? "");
        log.info("from_a");
      }),
      runWithLogContext({ correlationId: "cid-b" }, async () => {
        await new Promise((r) => setTimeout(r, 1));
        seen.push(getCorrelationId() ?? "");
        log.info("from_b");
      }),
    ]);
    expect(seen.sort()).toEqual(["cid-a", "cid-b"]);
    const events = Object.fromEntries(
      buf.lines().map((l) => [l.event, l.correlation_id]),
    );
    expect(events).toEqual({ from_a: "cid-a", from_b: "cid-b" });
  });

  it("withLogContext wraps a route handler and forwards an incoming header", async () => {
    let observed: string | undefined;
    const handler = withLogContext(async (_req: Request) => {
      observed = getCorrelationId();
      log.info("inside_handler");
      return new Response("ok");
    });
    const req = new Request("https://x.test/", {
      headers: { "x-correlation-id": "cid-from-edge" },
    });
    await handler(req, {} as never);
    expect(observed).toBe("cid-from-edge");
    expect(buf.lines()[0].correlation_id).toBe("cid-from-edge");
  });

  it("withLogContext synthesizes a UUID when the header is missing", async () => {
    let observed: string | undefined;
    const handler = withLogContext(async (_req: Request) => {
      observed = getCorrelationId();
      return new Response("ok");
    });
    await handler(new Request("https://x.test/"), {} as never);
    expect(observed).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
  });

  it("omits user_id when not set in context", () => {
    runWithLogContext({ correlationId: "cid-only" }, () => {
      log.info("no_user");
    });
    const [line] = buf.lines();
    expect(line.user_id).toBeUndefined();
  });
});

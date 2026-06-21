import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { eq, sql } from "drizzle-orm";
import { createTestDb, pgFor, resetDb, type TestDb } from "./_helpers/db";
import { resetSeedCounters, seedUser } from "./_helpers/seed";
import {
  brandConfig,
  disclosurePhraseOverride,
  productAliases,
  visibilityEntities,
  visibilityQueries,
} from "@/db/schema";

let testDb: TestDb;
vi.mock("@/db/client", async () => {
  testDb = await createTestDb();
  return { db: testDb, schema: await import("@/db/schema") };
});

let lib: typeof import("@/lib/wizard");

beforeAll(async () => {
  lib = await import("@/lib/wizard");
});

beforeEach(async () => {
  await resetDb(testDb);
  resetSeedCounters();
});

afterEach(() => {
  lib.resetQuerySuggester();
  lib.resetSubDiscoverer();
});

/* ---------- step persistence ---------- */

describe("step persistence", () => {
  it("advancing past step 3 then re-reading returns setupStep=4", async () => {
    await lib.saveStep1({
      brandName: "Acme",
      description: "an acme",
      aliases: ["Acme", "acme.com"],
    });
    await lib.saveStep2([
      { name: "Beta", aliases: ["b"] },
      { name: "Gamma", aliases: ["g"] },
      { name: "Delta", aliases: ["d"] },
    ]);
    await lib.saveStep3(["best acme alternative", "what is acme"]);

    const cfg = await lib.getBrandConfig();
    expect(cfg?.setupStep).toBe(4);
    expect(cfg?.setupCompletedAt).toBeNull();
  });
});

/* ---------- atomic write across schemas ---------- */

describe("step 1 atomic write", () => {
  it("commits to product_aliases AND visibility.entities atomically", async () => {
    await lib.saveStep1({
      brandName: "Acme",
      description: "",
      aliases: ["Acme", "acmewidget.com"],
    });

    const aliases = await testDb.select().from(productAliases);
    expect(aliases.map((a) => a.alias).sort()).toEqual(["Acme", "acmewidget.com"]);
    expect(aliases.find((a) => a.alias === "Acme")?.isPrimary).toBe(true);

    const entity = await testDb
      .select()
      .from(visibilityEntities)
      .where(eq(visibilityEntities.type, "brand"));
    expect(entity[0]?.name).toBe("Acme");
    expect(entity[0]?.aliases).toEqual(["Acme", "acmewidget.com"]);
  });

  it("rolls back product_aliases when visibility schema is unreachable", async () => {
    // Drop the visibility schema to simulate "tracker unreachable" mid-write.
    await pgFor(testDb).exec("DROP SCHEMA visibility CASCADE");

    await expect(
      lib.saveStep1({
        brandName: "Acme",
        description: "",
        aliases: ["Acme"],
      }),
    ).rejects.toBeTruthy();

    // Atomicity contract: NEITHER side commits when one fails.
    const aliases = await testDb.select().from(productAliases);
    expect(aliases).toHaveLength(0);
    const cfg = await testDb.select().from(brandConfig);
    expect(cfg).toHaveLength(0);
  });
});

/* ---------- suggested queries (mocked claude) ---------- */

describe("suggested queries", () => {
  it("returns the injected suggester's output", async () => {
    await lib.saveStep1({
      brandName: "Acme",
      description: "test",
      aliases: ["Acme"],
    });
    lib.setQuerySuggester(async ({ brandName }) => [
      `mock query 1 for ${brandName}`,
      `mock query 2 for ${brandName}`,
    ]);
    const queries = await lib.suggestQueries();
    expect(queries).toEqual(["mock query 1 for Acme", "mock query 2 for Acme"]);
  });
});

/* ---------- smoke test independence ---------- */

describe("smoke test", () => {
  it("reports finder + visibility independently — chatgpt 429 doesn't hide finder success", async () => {
    await lib.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await lib.saveStep2([
      { name: "B", aliases: [] },
      { name: "C", aliases: [] },
      { name: "D", aliases: [] },
    ]);
    await lib.saveStep3(["highest priority query", "second query"]);

    lib.setSmokeFns({
      runFinderPoll: async () => ({ opportunitiesFound: 3 }),
      runChatGptQuery: async () => {
        throw new Error("chatgpt 429");
      },
    });
    const result = await lib.runSmokeTest();
    expect(result.finder.ok).toBe(true);
    expect(result.finder.opportunitiesFound).toBe(3);
    expect(result.visibility.ok).toBe(false);
    expect(result.visibility.error).toContain("429");
    expect(result.highestPriorityQuery).toBe("highest priority query");
  });

  it("reports finder failure independently of visibility success", async () => {
    await lib.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await lib.saveStep2([
      { name: "B", aliases: [] },
      { name: "C", aliases: [] },
      { name: "D", aliases: [] },
    ]);
    await lib.saveStep3(["q1"]);

    lib.setSmokeFns({
      runFinderPoll: async () => {
        throw new Error("finder unreachable");
      },
      runChatGptQuery: async () => ({ mentioned: true, position: 2 }),
    });
    const result = await lib.runSmokeTest();
    expect(result.finder.ok).toBe(false);
    expect(result.finder.error).toContain("unreachable");
    expect(result.visibility.ok).toBe(true);
    expect(result.visibility.mentioned).toBe(true);
  });
});

/* ---------- setup-required gate ---------- */

describe("requireSetupComplete", () => {
  it("throws WizardIncompleteError when setupCompletedAt is null", async () => {
    await lib.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await expect(lib.requireSetupComplete()).rejects.toBeInstanceOf(
      lib.WizardIncompleteError,
    );
  });

  it("passes after markSetupComplete", async () => {
    await lib.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await lib.markSetupComplete();
    await expect(lib.requireSetupComplete()).resolves.toBeUndefined();
  });
});

/* ---------- disclosure overrides ---------- */

describe("disclosure overrides", () => {
  it("layers user-added phrases on top of compile-time defaults", async () => {
    const userId = await seedUser(testDb);
    await lib.saveStep5({
      add: ["i am a partner at acme", "acme partner"],
      remove: [],
      userId,
    });
    const effective = await lib.getEffectiveDisclosurePhrases();
    expect(effective).toContain("i am a partner at acme");
    expect(effective).toContain("acme partner");
    // Defaults still present.
    expect(effective).toContain("disclosure:");
  });

  it("remove deletes existing override", async () => {
    const userId = await seedUser(testDb);
    await lib.saveStep5({ add: ["custom phrase"], remove: [], userId });
    await lib.saveStep5({ add: [], remove: ["custom phrase"], userId });
    const rows = await testDb.select().from(disclosurePhraseOverride);
    expect(rows.find((r) => r.phrase === "custom phrase")).toBeUndefined();
  });
});

/* ---------- step 3 stores queries ---------- */

describe("step 3 query persistence", () => {
  it("saveStep3 writes to visibility.queries", async () => {
    await lib.saveStep1({ brandName: "Acme", description: "", aliases: ["Acme"] });
    await lib.saveStep2([
      { name: "B", aliases: [] },
      { name: "C", aliases: [] },
      { name: "D", aliases: [] },
    ]);
    await lib.saveStep3(["q1", "q2", "q3"]);
    const rows = await testDb.select().from(visibilityQueries);
    expect(rows.map((r) => r.text).sort()).toEqual(["q1", "q2", "q3"]);
  });
});

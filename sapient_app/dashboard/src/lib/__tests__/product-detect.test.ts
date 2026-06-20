import { describe, expect, it } from "vitest";
import { detectWithAliases } from "@/lib/product-detect";

describe("detectWithAliases", () => {
  it("matches case-insensitively", () => {
    const r = detectWithAliases("I love ACME widgets", ["Acme"]);
    expect(r.mentioned).toBe(true);
    expect(r.matchedAliases).toEqual(["Acme"]);
  });

  it("respects word boundaries — 'macme' must not match 'acme'", () => {
    const r = detectWithAliases("the macme protocol is unrelated", ["acme"]);
    expect(r.mentioned).toBe(false);
  });

  it("does not match 'AcmeWidget' as a hit for 'Acme'", () => {
    const r = detectWithAliases("AcmeWidget is a thing", ["Acme"]);
    expect(r.mentioned).toBe(false);
  });

  it("matches at start and end of string", () => {
    expect(detectWithAliases("Acme is great", ["Acme"]).mentioned).toBe(true);
    expect(detectWithAliases("I tried Acme", ["Acme"]).mentioned).toBe(true);
  });

  it("escapes regex specials in aliases — C++", () => {
    expect(detectWithAliases("I write C++ daily", ["C++"]).mentioned).toBe(true);
    expect(detectWithAliases("I write CPlusPlus daily", ["C++"]).mentioned).toBe(false);
  });

  it("escapes regex specials in aliases — .NET", () => {
    expect(detectWithAliases("Working in .NET today", [".NET"]).mentioned).toBe(true);
    // ASP.NET is a distinct token — the alias .NET should not match inside it
    // because of the alphanumeric lookbehind ("p" before ".").
    expect(detectWithAliases("Working in ASP.NET today", [".NET"]).mentioned).toBe(false);
  });

  it("is Unicode-aware on the boundary check (no false-positive in café)", () => {
    // "café" contains an accented letter; the alias "fe" must not match here
    // because "é" is a Unicode letter on the right and the lookahead rejects.
    const r = detectWithAliases("I drink café every morning", ["fe"]);
    expect(r.mentioned).toBe(false);
  });

  it("matches Unicode aliases case-insensitively", () => {
    const r = detectWithAliases("our brand is Café Acme", ["café"]);
    expect(r.mentioned).toBe(true);
  });

  it("returns the actual matched aliases (audit-friendly)", () => {
    const r = detectWithAliases("Acme and acmewidget.com are both us", [
      "Acme",
      "acmewidget.com",
    ]);
    expect(new Set(r.matchedAliases)).toEqual(new Set(["Acme", "acmewidget.com"]));
  });

  it("returns no match when alias list is empty", () => {
    expect(detectWithAliases("Acme", [])).toEqual({ mentioned: false, matchedAliases: [] });
  });

  it("returns no match for empty body", () => {
    expect(detectWithAliases("", ["Acme"])).toEqual({ mentioned: false, matchedAliases: [] });
  });
});

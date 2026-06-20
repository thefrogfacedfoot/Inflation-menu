/**
 * XSS posture + happy-path coverage for src/lib/markdown.ts.
 *
 * Posture: nothing the user types can introduce active HTML/JS in the
 * preview. The renderer reintroduces a fixed set of tags itself; everything
 * else is escaped first, including inside fenced code and [VERIFY:] markers.
 *
 * Happy paths: headings, bold, inline code, and fenced code with
 * HTML-looking content still render correctly.
 */
import { describe, expect, it } from "vitest";
import { escapeHtml, renderMarkdown } from "@/lib/markdown";

function noActiveScriptTag(html: string): void {
  // No raw <script> tag of any kind.
  expect(html).not.toMatch(/<script(\s|>)/i);
  // No real tag (raw `<...>`, not entity-encoded `&lt;...&gt;`) carries an
  // on-event handler attribute. We walk every raw tag's attribute substring
  // — escaped text shows up as `&lt;...` and is excluded by design.
  const tagRegex = /<([a-z][a-z0-9]*)(\b[^>]*)>/gi;
  let m: RegExpExecArray | null;
  while ((m = tagRegex.exec(html)) !== null) {
    expect(m[2]).not.toMatch(/\son[a-z]+\s*=/i);
  }
}

describe("escapeHtml", () => {
  it("escapes the five XSS-relevant characters", () => {
    expect(escapeHtml(`& < > " '`)).toBe("&amp; &lt; &gt; &quot; &#39;");
  });

  it("is idempotent against already-escaped input only at character level", () => {
    // Note: escaping &amp; would produce &amp;amp; — that's correct, not
    // idempotent. The test documents the contract.
    expect(escapeHtml("&amp;")).toBe("&amp;amp;");
  });
});

describe("renderMarkdown — XSS", () => {
  it("<script>alert(1)</script> in body renders as literal escaped text", () => {
    const out = renderMarkdown("<script>alert(1)</script>");
    expect(out).toContain("&lt;script&gt;");
    expect(out).toContain("alert(1)");
    expect(out).toContain("&lt;/script&gt;");
    noActiveScriptTag(out);
  });

  it("<img src=x onerror=alert(1)> renders as escaped text", () => {
    const out = renderMarkdown("<img src=x onerror=alert(1)>");
    expect(out).toContain("&lt;img");
    expect(out).toContain("onerror=alert(1)&gt;");
    noActiveScriptTag(out);
  });

  it("javascript: link in markdown link syntax shows up escaped", () => {
    // The renderer doesn't implement markdown link syntax at all, but the
    // literal "[click](javascript:alert(1))" text still must come through
    // inert.
    const out = renderMarkdown("[click](javascript:alert(1))");
    expect(out).toContain("javascript:alert(1)");
    noActiveScriptTag(out);
  });

  it("[VERIFY: <em>html in marker</em>] renders escaped content inside <mark>", () => {
    const out = renderMarkdown("[VERIFY: <em>html in marker</em>]");
    // Marker wrapper present
    expect(out).toMatch(/<mark[^>]*>\[VERIFY:/);
    // Content inside marker is escaped — no actual <em> active tag
    expect(out).toContain("&lt;em&gt;html in marker&lt;/em&gt;");
    expect(out).not.toMatch(/<em>html in marker<\/em>/);
    noActiveScriptTag(out);
  });

  it("fenced code block with HTML-looking content stays inert", () => {
    const out = renderMarkdown("```\n<script>alert(1)</script>\n```");
    expect(out).toMatch(/<pre[^>]*><code>/);
    expect(out).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    noActiveScriptTag(out);
  });

  it("combined: [VERIFY:] inside an H1 plus a fenced HTML block render inert", () => {
    const src = [
      "# Title with [VERIFY: <b>danger</b>]",
      "",
      "Some prose with **bold**.",
      "",
      "```",
      "<img src=x onerror=alert(2)>",
      "```",
    ].join("\n");
    const out = renderMarkdown(src);
    // H1 wraps the title; <mark> wraps the verify; escaped HTML inside both
    expect(out).toMatch(/<h1>Title with <mark/);
    expect(out).toContain("&lt;b&gt;danger&lt;/b&gt;");
    expect(out).toMatch(/<pre[^>]*><code>&lt;img/);
    noActiveScriptTag(out);
  });
});

describe("renderMarkdown — happy path still works", () => {
  it("H1 heading", () => {
    expect(renderMarkdown("# Title")).toContain("<h1>Title</h1>");
  });

  it("H2 and H3 headings", () => {
    expect(renderMarkdown("## Sub")).toContain("<h2>Sub</h2>");
    expect(renderMarkdown("### Subsub")).toContain("<h3>Subsub</h3>");
  });

  it("**bold** → <strong>", () => {
    expect(renderMarkdown("**hello**")).toContain("<strong>hello</strong>");
  });

  it("*italic* → <em>", () => {
    expect(renderMarkdown("*hello*")).toContain("<em>hello</em>");
  });

  it("`code` → <code>", () => {
    expect(renderMarkdown("`x`")).toMatch(/<code[^>]*>x<\/code>/);
  });

  it("fenced code block produces <pre><code>", () => {
    const out = renderMarkdown("```\nconst x = 1;\n```");
    expect(out).toMatch(/<pre[^>]*><code>const x = 1;<\/code><\/pre>/);
  });

  it("plain paragraphs are wrapped in <p>", () => {
    const out = renderMarkdown("one two three");
    expect(out).toBe("<p>one two three</p>");
  });

  it("hyphen list → <ul><li>", () => {
    const out = renderMarkdown("- one\n- two");
    expect(out).toMatch(/<ul><li>one<\/li><li>two<\/li><\/ul>/);
  });
});

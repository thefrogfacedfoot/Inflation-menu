/**
 * Tiny markdown → HTML renderer used by the content-draft editor preview.
 *
 * XSS posture: the pre-pass ALWAYS html-escapes the entire input, so the
 * markdown rules below operate on a string that can no longer contain raw
 * tags. The renderer reintroduces a fixed, hand-written set of tags
 * (<h1>/<h2>/<h3>, <strong>, <em>, <code>, <pre>, <ul>/<li>, <p>, <br>,
 * <mark>) — and nothing else. Any HTML the user typed shows up as literal
 * escaped text in the preview, including inside fenced code blocks and
 * inside [VERIFY: …] markers.
 *
 * The "monaco-style preview" goals only need a handful of constructs, so
 * the renderer stays inline rather than pulling in a dep like
 * react-markdown / remark.
 */

export function escapeHtml(s: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return s.replace(/[&<>"']/g, (c) => map[c]);
}

export function renderMarkdown(src: string): string {
  // 1. Escape first. Every subsequent transformation rewrites THIS string —
  // none of them ever sees raw HTML from the user.
  let html = escapeHtml(src);

  // 2. Fenced code blocks. Run before inline rules so their contents aren't
  // re-parsed for **bold** / `code` / [VERIFY:] markup.
  html = html.replace(
    /```([\s\S]*?)```/g,
    (_, code: string) =>
      `<pre style="background:#0d1117;padding:12px;border-radius:6px;overflow-x:auto"><code>${code.trim()}</code></pre>`,
  );

  // 3. Headings.
  html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");

  // 4. Inline code.
  html = html.replace(
    /`([^`]+)`/g,
    '<code style="background:#1d2129;padding:2px 4px;border-radius:3px">$1</code>',
  );

  // 5. Bold then italic. Order matters — bold tokens contain the italic
  // delimiter and would be eaten by a greedy italic pass.
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // 6. [VERIFY: …] highlight. After escape, `<`/`>`/`&`/etc inside the
  // marker are already entity-encoded, so the <mark> wraps inert text.
  html = html.replace(
    /\[VERIFY:([^\]]*)\]/g,
    (_, body: string) =>
      `<mark style="background:#3a2f1f;color:#ffcc88;padding:2px 6px;border-radius:4px;font-weight:600">[VERIFY:${body}]</mark>`,
  );

  // 7. Lists.
  html = html.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>[\s\S]+?<\/li>)/g, "<ul>$1</ul>");
  html = html.replace(/<\/ul>\s*<ul>/g, "");

  // 8. Paragraphs from runs of plain text. Anything not already wrapped in
  // a block-level element gets a <p>; single newlines inside a paragraph
  // become <br/>. Naive but adequate for preview.
  html = html
    .split(/\n{2,}/)
    .map((chunk) => {
      const trimmed = chunk.trim();
      if (!trimmed) return "";
      if (/^<(h\d|ul|ol|pre|p|blockquote)/.test(trimmed)) return trimmed;
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    })
    .join("\n");

  return html;
}

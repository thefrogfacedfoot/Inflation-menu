"use client";

/**
 * Split-pane markdown editor with [VERIFY: …] highlighting in the preview,
 * 1-second autosave debounce, and mark-edited / mark-published actions.
 *
 * We do NOT pull in monaco — it's heavy and SSR-clunky in Next.js. A
 * textarea + a tiny markdown renderer covers the spec ("monaco-style split
 * pane editor") without the bundle cost. The markdown renderer is
 * intentionally minimal: headings, paragraphs, bold/italic, code, lists,
 * and the [VERIFY: …] highlighting. Anything richer can swap in later.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type Status = "draft" | "edited" | "published" | "archived";
type Warning = { code: "unresolved_verify_markers"; count: number } | null;

const SAVE_DEBOUNCE_MS = 1000;
const VERIFY_RE = /\[VERIFY:[^\]]*\]/g;

export default function Editor(props: {
  draftId: number;
  initialTitle: string;
  initialBody: string;
  initialStatus: Status;
  initialEditMarkers: number;
  publishedUrl: string | null;
}) {
  const router = useRouter();
  const [title, setTitle] = useState(props.initialTitle);
  const [body, setBody] = useState(props.initialBody);
  const [status, setStatus] = useState<Status>(props.initialStatus);
  const [markers, setMarkers] = useState(props.initialEditMarkers);
  const [saveState, setSaveState] = useState<"clean" | "dirty" | "saving" | "error">(
    "clean",
  );
  const [warning, setWarning] = useState<Warning>(null);
  const [showPublish, setShowPublish] = useState(false);
  const [publishUrl, setPublishUrl] = useState(props.publishedUrl ?? "");
  const [publishError, setPublishError] = useState<string | null>(null);

  // Recompute markers locally as the user types so the count displayed in
  // the UI doesn't lag the autosave roundtrip. Server's authoritative on
  // save — this is purely a UX hint.
  useEffect(() => {
    const matches = body.match(VERIFY_RE);
    setMarkers(matches ? matches.length : 0);
  }, [body]);

  const lastSavedTitle = useRef(props.initialTitle);
  const lastSavedBody = useRef(props.initialBody);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushSave = useCallback(async () => {
    if (title === lastSavedTitle.current && body === lastSavedBody.current) {
      setSaveState("clean");
      return;
    }
    setSaveState("saving");
    try {
      const res = await fetch(`/api/content-drafts/${props.draftId}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, body }),
      });
      if (!res.ok) {
        setSaveState("error");
        return;
      }
      lastSavedTitle.current = title;
      lastSavedBody.current = body;
      setSaveState("clean");
    } catch {
      setSaveState("error");
    }
  }, [props.draftId, title, body]);

  useEffect(() => {
    if (status === "published" || status === "archived") return;
    if (title === lastSavedTitle.current && body === lastSavedBody.current) {
      return;
    }
    setSaveState("dirty");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(flushSave, SAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [title, body, status, flushSave]);

  const onMarkEdited = async () => {
    // Flush any pending edit so the server sees the latest body before it
    // recomputes markers for the warning.
    if (saveState === "dirty" || saveState === "saving") {
      await flushSave();
    }
    const res = await fetch(
      `/api/content-drafts/${props.draftId}/mark-edited`,
      { method: "POST" },
    );
    if (!res.ok) return;
    const json: { draft: { status: Status }; warning: Warning } =
      await res.json();
    setStatus(json.draft.status);
    setWarning(json.warning);
  };

  const onPublish = async () => {
    setPublishError(null);
    const res = await fetch(`/api/content-drafts/${props.draftId}/publish`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url: publishUrl }),
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      setPublishError(json.error ?? `publish failed (${res.status})`);
      return;
    }
    const json: { draft: { status: Status; publishedUrl: string | null } } =
      await res.json();
    setStatus(json.draft.status);
    setShowPublish(false);
    router.refresh();
  };

  const onArchive = async () => {
    const res = await fetch(`/api/content-drafts/${props.draftId}/archive`, {
      method: "POST",
    });
    if (!res.ok) return;
    setStatus("archived");
    router.refresh();
  };

  const previewHtml = useMemo(() => renderMarkdown(body), [body]);
  const readOnly = status === "published" || status === "archived";

  return (
    <div style={page}>
      <header style={header}>
        <div>
          <input
            value={title}
            disabled={readOnly}
            onChange={(e) => setTitle(e.target.value)}
            style={titleInput}
            placeholder="Untitled draft"
          />
          <div style={metaRow}>
            <Badge status={status} />
            <span style={muted}>
              {markers === 0
                ? "0 [VERIFY] markers"
                : `${markers} [VERIFY] marker${markers === 1 ? "" : "s"}`}
            </span>
            <SaveIndicator state={saveState} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {status === "draft" && (
            <button onClick={onMarkEdited} style={btnPrimary}>
              Mark edited
            </button>
          )}
          {status === "edited" && (
            <button onClick={() => setShowPublish(true)} style={btnPrimary}>
              Mark published
            </button>
          )}
          {!readOnly && (
            <button onClick={onArchive} style={btnSecondary}>
              Archive
            </button>
          )}
        </div>
      </header>

      {warning && (
        <div style={warnBox}>
          You have {warning.count} unresolved [VERIFY] marker
          {warning.count === 1 ? "" : "s"} — review before publishing.
        </div>
      )}

      {status === "published" && props.publishedUrl && (
        <div style={publishedBox}>
          Published at{" "}
          <a href={props.publishedUrl} target="_blank" rel="noreferrer">
            {props.publishedUrl}
          </a>
        </div>
      )}

      <div style={split}>
        <textarea
          value={body}
          disabled={readOnly}
          onChange={(e) => setBody(e.target.value)}
          style={textarea}
          spellCheck
          placeholder="Markdown body…"
        />
        <div style={preview} dangerouslySetInnerHTML={{ __html: previewHtml }} />
      </div>

      {showPublish && (
        <PublishModal
          url={publishUrl}
          onChange={setPublishUrl}
          onCancel={() => setShowPublish(false)}
          onConfirm={onPublish}
          error={publishError}
        />
      )}
    </div>
  );
}

function Badge({ status }: { status: Status }) {
  const colors: Record<Status, [string, string]> = {
    draft: ["#1f2a44", "#88aaff"],
    edited: ["#1f4434", "#88ffaa"],
    published: ["#3a2f1f", "#ffcc88"],
    archived: ["#2a2a2a", "#888"],
  };
  const [bg, fg] = colors[status];
  return <span style={{ ...badge, background: bg, color: fg }}>{status}</span>;
}

function SaveIndicator({
  state,
}: {
  state: "clean" | "dirty" | "saving" | "error";
}) {
  const labels = {
    clean: "saved",
    dirty: "unsaved",
    saving: "saving…",
    error: "save failed",
  };
  const colors = {
    clean: "#88ff88",
    dirty: "#ffcc88",
    saving: "#aaaaff",
    error: "#ff8888",
  };
  return <span style={{ color: colors[state], fontSize: 12 }}>{labels[state]}</span>;
}

function PublishModal(props: {
  url: string;
  onChange: (s: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  error: string | null;
}) {
  return (
    <div style={modalScrim} onClick={props.onCancel}>
      <div style={modal} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Mark published</h3>
        <p style={muted}>
          Paste the URL where you published this draft. The dashboard records
          the final URL and closes the upstream visibility task.
        </p>
        <input
          value={props.url}
          onChange={(e) => props.onChange(e.target.value)}
          placeholder="https://blog.example.com/your-post"
          style={publishInput}
          autoFocus
        />
        {props.error && (
          <p style={{ color: "#ff8888", fontSize: 13 }}>{props.error}</p>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={props.onCancel} style={btnSecondary}>
            Cancel
          </button>
          <button onClick={props.onConfirm} style={btnPrimary}>
            Mark published
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- tiny markdown → HTML renderer ---------- */
//
// Covers what the editor needs: headings, paragraphs, lists, **bold**,
// *italic*, `code`, fenced ``` blocks, and the [VERIFY: …] highlight that's
// the whole point of this view. All inputs are escaped before any markdown
// rewrites, so user-typed `<script>` shows up as literal text.
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(src: string): string {
  const escaped = escapeHtml(src);
  let html = escaped;

  // Fenced code blocks first so their contents aren't re-parsed.
  html = html.replace(
    /```([\s\S]*?)```/g,
    (_, code: string) =>
      `<pre style="background:#0d1117;padding:12px;border-radius:6px;overflow-x:auto"><code>${code.trim()}</code></pre>`,
  );

  // Headings (#, ##, ###).
  html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");

  // Inline code.
  html = html.replace(
    /`([^`]+)`/g,
    '<code style="background:#1d2129;padding:2px 4px;border-radius:3px">$1</code>',
  );

  // Bold then italic. Order matters — bold tokens contain the italic delim.
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // [VERIFY: ...] highlight. Run AFTER escape so the brackets are literal.
  html = html.replace(
    /\[VERIFY:([^\]]*)\]/g,
    (_, body: string) =>
      `<mark style="background:#3a2f1f;color:#ffcc88;padding:2px 6px;border-radius:4px;font-weight:600">[VERIFY:${body}]</mark>`,
  );

  // Lists (-, *).
  html = html.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>[\s\S]+?<\/li>)/g, "<ul>$1</ul>");
  // Collapse adjacent <ul></ul> from the previous step.
  html = html.replace(/<\/ul>\s*<ul>/g, "");

  // Paragraphs from runs of plain text. Anything not already wrapped in a
  // block-level element gets a <p>. Naive but adequate for preview.
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

/* ---------- styles ---------- */

const page: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100vh",
  background: "#0d0e12",
  color: "#eee",
};
const header: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  padding: "12px 16px",
  borderBottom: "1px solid #2a2d3a",
};
const titleInput: React.CSSProperties = {
  background: "transparent",
  color: "white",
  border: "none",
  fontSize: 22,
  fontWeight: 700,
  width: "60ch",
  maxWidth: "100%",
  padding: 0,
};
const metaRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  marginTop: 8,
};
const badge: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: 0.5,
};
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 13 };
const warnBox: React.CSSProperties = {
  background: "#3a2f1f",
  color: "#ffcc88",
  padding: 10,
  margin: "8px 16px",
  borderRadius: 6,
  fontSize: 13,
};
const publishedBox: React.CSSProperties = {
  background: "#1f2a44",
  color: "#88aaff",
  padding: 10,
  margin: "8px 16px",
  borderRadius: 6,
  fontSize: 13,
};
const split: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  flex: 1,
  borderTop: "1px solid #2a2d3a",
  minHeight: 0,
};
const textarea: React.CSSProperties = {
  resize: "none",
  background: "#11131a",
  color: "#eee",
  border: "none",
  padding: 16,
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  fontSize: 14,
  lineHeight: 1.6,
  outline: "none",
  borderRight: "1px solid #2a2d3a",
};
const preview: React.CSSProperties = {
  padding: 16,
  overflowY: "auto",
  lineHeight: 1.6,
  fontSize: 14,
  background: "#0d0e12",
};
const btnPrimary: React.CSSProperties = {
  padding: "8px 16px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
};
const btnSecondary: React.CSSProperties = {
  padding: "8px 16px",
  background: "#2a2d3a",
  color: "#eee",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
};
const modalScrim: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(0,0,0,0.6)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
const modal: React.CSSProperties = {
  background: "#11131a",
  padding: 24,
  borderRadius: 8,
  width: 480,
  border: "1px solid #2a2d3a",
};
const publishInput: React.CSSProperties = {
  background: "#0d0e12",
  color: "white",
  border: "1px solid #2a2d3a",
  padding: 10,
  borderRadius: 6,
  width: "100%",
  marginBottom: 12,
};

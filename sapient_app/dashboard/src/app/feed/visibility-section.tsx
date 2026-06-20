"use client";

import { useState, useTransition } from "react";

type RedditTask = {
  id: number;
  kind: string;
  suggestedSubreddit: string | null;
  relatedUrl: string | null;
  recommendation: string;
};

type ContentTask = {
  id: number;
  kind: string;
  relatedUrl: string | null;
  recommendation: string;
};

export default function VisibilitySection({
  reddit,
  content,
  disabled,
}: {
  reddit: RedditTask[];
  content: ContentTask[];
  disabled: boolean;
}) {
  const [tab, setTab] = useState<"reddit" | "content">("reddit");
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [pending, start] = useTransition();

  if (reddit.length === 0 && content.length === 0) return null;

  const claim = (id: number) =>
    start(async () => {
      const res = await fetch(`/api/visibility-tasks/${id}/claim`, { method: "POST" });
      const json = await res.json();
      if (res.ok) {
        const next = new Set(removed);
        next.add(id);
        setRemoved(next);
      } else {
        setErrors({ ...errors, [id]: json.error ?? "claim failed" });
      }
    });

  const dismiss = (id: number) =>
    start(async () => {
      const res = await fetch(`/api/visibility-tasks/${id}/dismiss`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const next = new Set(removed);
        next.add(id);
        setRemoved(next);
      }
    });

  const visibleReddit = reddit.filter((t) => !removed.has(t.id));
  const visibleContent = content.filter((t) => !removed.has(t.id));

  return (
    <section style={section}>
      <h2 style={{ marginTop: 0 }}>Suggested by visibility tracker</h2>
      <div style={tabs}>
        <button
          onClick={() => setTab("reddit")}
          style={{ ...tabBtn, ...(tab === "reddit" ? tabBtnActive : {}) }}
        >
          Reddit ({visibleReddit.length})
        </button>
        <button
          onClick={() => setTab("content")}
          style={{ ...tabBtn, ...(tab === "content" ? tabBtnActive : {}) }}
        >
          Content gaps ({visibleContent.length})
        </button>
      </div>

      {tab === "reddit" &&
        (visibleReddit.length === 0 ? (
          <p style={muted}>No eligible Reddit suggestions right now.</p>
        ) : (
          visibleReddit.map((t) => (
            <article key={t.id} style={card}>
              <header style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>r/{t.suggestedSubreddit}</strong>
                <span style={muted}>{t.kind}</span>
              </header>
              <p style={{ margin: "8px 0" }}>{t.recommendation}</p>
              {t.relatedUrl && (
                <a href={t.relatedUrl} target="_blank" rel="noreferrer" style={link}>
                  {t.relatedUrl}
                </a>
              )}
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => claim(t.id)}
                  disabled={pending || disabled}
                  style={btn}
                >
                  Claim
                </button>
                <button
                  onClick={() => dismiss(t.id)}
                  disabled={pending}
                  style={{ ...btn, background: "#444" }}
                >
                  Dismiss
                </button>
                {errors[t.id] && (
                  <span style={{ color: "#ff8888", marginLeft: 12 }}>{errors[t.id]}</span>
                )}
              </div>
            </article>
          ))
        ))}

      {tab === "content" &&
        (visibleContent.length === 0 ? (
          <p style={muted}>No content gap suggestions right now.</p>
        ) : (
          visibleContent.map((t) => (
            <article key={t.id} style={card}>
              <header style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{t.kind}</strong>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(t.recommendation);
                  }}
                  style={{ ...btn, background: "#444" }}
                >
                  Copy prompt
                </button>
              </header>
              <p style={{ margin: "8px 0" }}>{t.recommendation}</p>
              {t.relatedUrl && (
                <a href={t.relatedUrl} target="_blank" rel="noreferrer" style={link}>
                  {t.relatedUrl}
                </a>
              )}
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => dismiss(t.id)}
                  disabled={pending}
                  style={{ ...btn, background: "#444" }}
                >
                  Dismiss
                </button>
              </div>
            </article>
          ))
        ))}
    </section>
  );
}

const section: React.CSSProperties = {
  background: "#11131a",
  padding: 16,
  borderRadius: 8,
  margin: "16px 0",
  border: "1px solid #2a2d3a",
};
const tabs: React.CSSProperties = { display: "flex", gap: 8, marginBottom: 12 };
const tabBtn: React.CSSProperties = {
  padding: "6px 12px",
  background: "transparent",
  color: "#aaa",
  border: "1px solid #2a2d3a",
  borderRadius: 6,
  cursor: "pointer",
};
const tabBtnActive: React.CSSProperties = { color: "white", borderColor: "#ff4500" };
const card: React.CSSProperties = {
  background: "#16161a",
  padding: 12,
  borderRadius: 6,
  margin: "8px 0",
};
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 13, margin: 0 };
const link: React.CSSProperties = { color: "#88aaff", fontSize: 13 };
const btn: React.CSSProperties = {
  padding: "6px 12px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
  marginRight: 8,
};

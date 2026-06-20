"use client";

import { useState, useTransition } from "react";
import type { FeedItem } from "@/lib/feed";

export default function FeedList({
  items,
  disabled,
}: {
  items: FeedItem[];
  disabled: boolean;
}) {
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [pending, start] = useTransition();

  const claim = (id: number) =>
    start(async () => {
      const res = await fetch("/api/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opportunityId: id }),
      });
      const json = await res.json();
      if (res.ok) {
        const next = new Set(removed);
        next.add(id);
        setRemoved(next);
      } else {
        setErrors({ ...errors, [id]: json.error ?? "claim failed" });
      }
    });

  const visible = items.filter((i) => !removed.has(i.id));
  if (visible.length === 0) {
    return <p style={{ color: "#9aa0a6" }}>No opportunities right now.</p>;
  }

  return (
    <div>
      {visible.map((item) => (
        <article key={item.id} style={card}>
          <header style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <strong>r/{item.subreddit}</strong>
            <span style={{ color: "#ff4500" }}>score {item.score}</span>
          </header>
          <h3 style={{ margin: "8px 0" }}>
            <a href={item.postUrl} target="_blank" rel="noreferrer" style={{ color: "#e7e7ea" }}>
              {item.title}
            </a>
          </h3>
          <p style={muted}><b>why:</b> {item.reason}</p>
          <p style={muted}><b>angle:</b> {item.suggestedAngle}</p>
          <button
            onClick={() => claim(item.id)}
            disabled={pending || disabled}
            style={btn}
          >
            Claim
          </button>
          {errors[item.id] && (
            <span style={{ color: "#ff8888", marginLeft: 12 }}>
              {errors[item.id]}
            </span>
          )}
        </article>
      ))}
    </div>
  );
}

const card: React.CSSProperties = {
  background: "#16161a",
  padding: 16,
  borderRadius: 8,
  margin: "12px 0",
};
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 14, margin: "4px 0" };
const btn: React.CSSProperties = {
  padding: "6px 12px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
};

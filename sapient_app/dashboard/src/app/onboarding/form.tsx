"use client";

import { useState, useTransition } from "react";

type Sub = { subreddit: string; posts: number; comments: number; checked: boolean };

export default function OnboardingForm({
  initialTags,
  subs: initialSubs,
  lastSyncIso,
}: {
  initialTags: string[];
  subs: Sub[];
  lastSyncIso: string | null;
}) {
  const [tagInput, setTagInput] = useState(initialTags.join(", "));
  const [subs, setSubs] = useState(initialSubs);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const syncHistory = () => start(async () => {
    setStatus("Syncing history…");
    const res = await fetch("/api/onboarding/sync", { method: "POST" });
    const json = await res.json();
    setStatus(res.ok ? `Synced ${json.subsAdded} subs. Refresh to see them.` : `Error: ${json.error}`);
  });

  const saveProfile = () => start(async () => {
    const tags = tagInput.split(",").map((s) => s.trim()).filter(Boolean);
    const expertiseSubs = subs.filter((s) => s.checked).map((s) => s.subreddit);
    const res = await fetch("/api/onboarding/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expertiseTags: tags, expertiseSubs }),
    });
    const json = await res.json();
    setStatus(res.ok
      ? `Saved. ${json.expertiseSubsMatched} subs flagged as expertise-matched.`
      : `Error: ${json.error}`);
  });

  return (
    <div>
      <section style={card}>
        <h2>1. Sync Reddit history</h2>
        <p style={muted}>Last sync: {lastSyncIso ?? "never"}</p>
        <button onClick={syncHistory} disabled={pending} style={btn}>
          {pending ? "Working…" : "Sync now"}
        </button>
      </section>

      <section style={card}>
        <h2>2. Expertise tags</h2>
        <p style={muted}>Comma-separated.</p>
        <input
          value={tagInput}
          onChange={(e) => setTagInput(e.target.value)}
          placeholder="e.g. workflow automation, no-code, small business ops"
          style={input}
        />
      </section>

      <section style={card}>
        <h2>3. Subs that match your expertise</h2>
        <p style={muted}>
          Only checked subs will show opportunities. You can only check subs you were
          already active in before today.
        </p>
        {subs.length === 0 && <p style={muted}>No subs found — run a sync first.</p>}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
          {subs.map((s, i) => (
            <label key={s.subreddit} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={s.checked}
                onChange={(e) => {
                  const next = [...subs];
                  next[i] = { ...s, checked: e.target.checked };
                  setSubs(next);
                }}
              />
              <span>r/{s.subreddit}</span>
              <span style={muted}>
                {s.posts}p / {s.comments}c
              </span>
            </label>
          ))}
        </div>
      </section>

      <button onClick={saveProfile} disabled={pending} style={btn}>
        Save profile
      </button>
      {status && <p style={{ marginTop: 12 }}>{status}</p>}
    </div>
  );
}

const card: React.CSSProperties = {
  background: "#16161a",
  padding: 16,
  borderRadius: 8,
  margin: "16px 0",
};
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 13 };
const btn: React.CSSProperties = {
  padding: "8px 14px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
};
const input: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  background: "#0b0b0d",
  color: "#e7e7ea",
  border: "1px solid #2a2a30",
  borderRadius: 6,
};

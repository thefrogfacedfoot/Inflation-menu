"use client";

import { useState, useTransition } from "react";

type RequestRow = {
  id: number;
  kind: string;
  state: string;
  requestedAt: string;
  scheduledFor: string;
  completedAt: string | null;
  downloadUrl: string | null;
  erased: boolean;
};

export default function PrivacyClient({
  initialRequests,
}: {
  initialRequests: RequestRow[];
}) {
  const [requests, setRequests] = useState(initialRequests);
  const [showDelete, setShowDelete] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, start] = useTransition();

  const refresh = () =>
    start(async () => {
      const res = await fetch("/api/gdpr/requests");
      if (res.ok) setRequests((await res.json()).requests);
    });

  const requestExport = () =>
    start(async () => {
      setStatus("Requesting export…");
      const res = await fetch("/api/gdpr/export", { method: "POST" });
      if (res.ok) {
        setStatus("Export queued. Refresh to check status.");
        await refresh();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });

  const requestDelete = () =>
    start(async () => {
      setStatus("Scheduling deletion…");
      const res = await fetch("/api/gdpr/delete", { method: "POST" });
      if (res.ok) {
        const { request } = await res.json();
        setStatus(
          `Deletion scheduled for ${new Date(request.scheduledFor).toLocaleDateString()}. ` +
            `You can cancel any time before then.`,
        );
        setShowDelete(false);
        await refresh();
      } else {
        setStatus(`Error: ${(await res.json()).error}`);
      }
    });

  const cancel = (id: number) =>
    start(async () => {
      const res = await fetch(`/api/gdpr/request/${id}`, { method: "DELETE" });
      if (res.ok) {
        setStatus("Cancelled.");
        await refresh();
      } else {
        setStatus(`Cancel failed: ${(await res.json()).error}`);
      }
    });

  return (
    <div>
      <section style={card}>
        <h2>Export your data</h2>
        <p style={muted}>
          We bundle everything we store about you into a downloadable JSON
          archive. The link is valid for 7 days.
        </p>
        <button style={btn} disabled={pending} onClick={requestExport}>
          {pending ? "Working…" : "Request export"}
        </button>
      </section>

      <section style={card}>
        <h2>Delete your account</h2>
        {!showDelete ? (
          <button style={btnDanger} disabled={pending} onClick={() => setShowDelete(true)}>
            Request deletion
          </button>
        ) : (
          <div>
            <p>
              <strong>Heads-up:</strong> deletion runs after a 30-day grace
              period. During that window you can cancel the request from this
              page. Once the grace ends, your dashboard data is removed and
              your name shows as &ldquo;deleted user&rdquo; everywhere we kept
              an audit reference.
            </p>
            <button style={btnDanger} disabled={pending} onClick={requestDelete}>
              I understand — schedule deletion
            </button>
            <button style={btn} disabled={pending} onClick={() => setShowDelete(false)}>
              Cancel
            </button>
          </div>
        )}
      </section>

      <section style={card}>
        <h2>Request history</h2>
        {requests.length === 0 && <p style={muted}>No requests yet.</p>}
        {requests.map((r) => (
          <div key={r.id} style={{ borderTop: "1px solid #2a2a30", padding: "8px 0" }}>
            <div>
              <strong>{r.kind}</strong> — {r.state}
              {r.erased && " (data erased)"}
            </div>
            <div style={muted}>
              requested {new Date(r.requestedAt).toLocaleString()} —
              {r.kind === "delete"
                ? ` scheduled for ${new Date(r.scheduledFor).toLocaleDateString()}`
                : r.completedAt
                  ? ` completed ${new Date(r.completedAt).toLocaleString()}`
                  : ""}
            </div>
            {r.downloadUrl && (
              <a href={r.downloadUrl} style={{ color: "#9aceff" }}>
                Download bundle
              </a>
            )}
            {r.kind === "delete" && r.state === "pending" && (
              <button style={btnLink} disabled={pending} onClick={() => cancel(r.id)}>
                Cancel
              </button>
            )}
          </div>
        ))}
      </section>

      {status && <p style={{ marginTop: 12 }}>{status}</p>}
    </div>
  );
}

const card: React.CSSProperties = { background: "#16161a", padding: 16, borderRadius: 8, margin: "16px 0" };
const muted: React.CSSProperties = { color: "#9aa0a6", fontSize: 13 };
const btn: React.CSSProperties = {
  padding: "8px 14px",
  background: "#2a2a30",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
  marginRight: 8,
};
const btnDanger: React.CSSProperties = { ...btn, background: "#cc3333" };
const btnLink: React.CSSProperties = {
  background: "transparent",
  color: "#9aceff",
  border: 0,
  cursor: "pointer",
  padding: "2px 6px",
  marginLeft: 6,
};

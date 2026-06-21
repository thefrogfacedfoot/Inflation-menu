import Link from "next/link";
import type {
  AccountHealthSnapshot,
  CheckStatus,
} from "@/lib/account-health";

/**
 * Inline banner on /dashboard for warning/alert states. The wording is
 * specific — we cite the actual counts that drove the flag — because a
 * generic "we noticed something" warning gets ignored.
 */
export default function AccountHealthBanner({
  severity,
  snapshot,
}: {
  severity: CheckStatus;
  snapshot: AccountHealthSnapshot;
}) {
  const lines = describeLatest(snapshot);
  const isAlert = severity === "alert";
  return (
    <div
      style={{
        background: isAlert ? "#3a0e0e" : "#3a2e0e",
        border: `1px solid ${isAlert ? "#ff4444" : "#ffaa44"}`,
        borderRadius: 8,
        padding: 16,
        margin: "12px 0",
      }}
    >
      <strong style={{ color: isAlert ? "#ff8888" : "#ffcc88" }}>
        {isAlert ? "Account health alert" : "Account health warning"}
      </strong>
      <ul style={{ margin: "8px 0 0 20px", padding: 0 }}>
        {lines.map((l, i) => (
          <li key={i} style={{ marginBottom: 4 }}>
            {l}
          </li>
        ))}
      </ul>
      <p style={{ marginTop: 8 }}>
        <Link href="/account-health/guide" style={{ color: "#9aceff" }}>
          What does this mean? &rarr;
        </Link>
      </p>
    </div>
  );
}

function describeLatest(snapshot: AccountHealthSnapshot): string[] {
  const out: string[] = [];
  const sb = snapshot.latest.shadowban;
  if (sb && sb.status !== "ok") {
    const d = sb.details as {
      authed_submissions?: number;
      anon_submissions?: number;
      authed_comments?: number;
      anon_comments?: number;
    };
    out.push(
      `Shadowban check: anon view shows ${d.anon_submissions ?? "?"} submissions / ${d.anon_comments ?? "?"} comments, ` +
        `your authed view shows ${d.authed_submissions ?? "?"} / ${d.authed_comments ?? "?"}.`,
    );
  }
  const kt = snapshot.latest.karma_trend;
  if (kt && kt.status !== "ok") {
    const d = kt.details as { delta_7d?: number; delta_14d?: number };
    if (d.delta_14d !== undefined) {
      out.push(
        `Karma dropped by ${Math.abs(d.delta_14d)} over the last 14 days — sustained decline.`,
      );
    } else if (d.delta_7d !== undefined) {
      out.push(`Karma dropped by ${Math.abs(d.delta_7d)} over the last 7 days.`);
    }
  }
  const sr = snapshot.latest.slow_removal;
  if (sr && sr.status !== "ok") {
    const d = sr.details as { removals?: number; window_size?: number };
    out.push(
      `Slow-burn removals detected: ${d.removals ?? "?"} of your last ${d.window_size ?? 30} posts removed, ` +
        `spread out over time (not a recent burst).`,
    );
  }
  return out;
}

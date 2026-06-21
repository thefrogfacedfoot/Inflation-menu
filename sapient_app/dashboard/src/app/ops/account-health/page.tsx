import { redirect } from "next/navigation";
import { auth } from "../../../../auth";
import {
  getAllSnapshots,
  highestSeverity,
  type CheckStatus,
} from "@/lib/account-health";
import { isOpsUser } from "@/lib/visibility-tasks";

export const dynamic = "force-dynamic";

export default async function OpsAccountHealthPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/");
  if (!(await isOpsUser(session.user.id))) {
    return (
      <div>
        <h1>Account health (ops)</h1>
        <p style={{ color: "#ff8888" }}>
          You need the ops role to view this page.
        </p>
      </div>
    );
  }
  const snapshots = await getAllSnapshots();
  const sorted = snapshots
    .map((s) => ({ snapshot: s, severity: highestSeverity(s) }))
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity));

  return (
    <div>
      <h1>Account health (ops)</h1>
      <p style={{ color: "#9aa0a6" }}>
        Latest check per user. Rows colored by highest severity across the
        three check types.
      </p>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #2a2a30" }}>
            <th style={th}>User</th>
            <th style={th}>Severity</th>
            <th style={th}>Shadowban</th>
            <th style={th}>Karma</th>
            <th style={th}>Slow-burn</th>
            <th style={th}>Last run</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(({ snapshot: s, severity }) => (
            <tr key={s.userId} style={{ background: rowColor(severity) }}>
              <td style={td}>{s.userId}</td>
              <td style={td}>{severity ?? "—"}</td>
              <td style={td}>{s.latest.shadowban?.status ?? "—"}</td>
              <td style={td}>
                {s.latest.karma_trend?.status ?? "—"}
                {typeof s.karma7dDelta === "number" && (
                  <span style={{ color: "#9aa0a6", marginLeft: 6 }}>
                    Δ{s.karma7dDelta}
                  </span>
                )}
              </td>
              <td style={td}>{s.latest.slow_removal?.status ?? "—"}</td>
              <td style={td}>
                {s.lastCheckRunAt ? s.lastCheckRunAt.toISOString() : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function severityRank(s: CheckStatus | null): number {
  if (s === "alert") return 3;
  if (s === "warning") return 2;
  if (s === "ok") return 1;
  return 0;
}

function rowColor(s: CheckStatus | null): string {
  if (s === "alert") return "#2a1010";
  if (s === "warning") return "#2a200f";
  return "transparent";
}

const th: React.CSSProperties = { padding: "8px 6px", fontWeight: 600 };
const td: React.CSSProperties = {
  padding: "8px 6px",
  borderBottom: "1px solid #18181c",
};

import { eq } from "drizzle-orm";
import { auth } from "../../../auth";
import { db } from "@/db/client";
import { userProfiles } from "@/db/schema";
import { getUserStats } from "@/lib/stats";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) return null;

  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, session.user.id),
  });
  const stats = await getUserStats(session.user.id);

  const karmaTrend = stats.karma.length >= 2
    ? stats.karma[stats.karma.length - 1].total - stats.karma[0].total
    : 0;

  return (
    <div>
      <h1>Your stats</h1>
      {profile?.isPaused && (
        <p style={{ color: "#ff8888" }}>Paused — {profile.pausedReason}</p>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Card label="Claimed" value={String(stats.claimed)} />
        <Card label="Posted" value={String(stats.posted)} />
        <Card label="Upvotes (30d)" value={String(stats.upvotesLast30d)} />
        <Card
          label={`Removal rate (last ${stats.removalWindow})`}
          value={`${(stats.removalRate * 100).toFixed(0)}%`}
          warn={stats.removalRate > 0.2}
        />
      </div>
      <div style={{ marginTop: 24 }}>
        <h2>Karma trend</h2>
        <p style={{ color: karmaTrend >= 0 ? "#8fffa0" : "#ff8888" }}>
          {karmaTrend >= 0 ? "+" : ""}{karmaTrend} over {stats.karma.length} snapshots
        </p>
      </div>
    </div>
  );
}

function Card({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{
      background: "#16161a",
      padding: 16,
      borderRadius: 8,
      border: warn ? "1px solid #ff4444" : "1px solid transparent",
    }}>
      <div style={{ color: "#9aa0a6", fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

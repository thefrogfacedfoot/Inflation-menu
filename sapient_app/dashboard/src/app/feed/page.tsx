import { eq } from "drizzle-orm";
import { auth } from "../../../auth";
import { db } from "@/db/client";
import { userProfiles } from "@/db/schema";
import { getFeed } from "@/lib/feed";
import {
  getEligibleVisibilityTasks,
  isOpsUser,
} from "@/lib/visibility-tasks";
import FeedList from "./list";
import VisibilitySection from "./visibility-section";

export default async function FeedPage() {
  const session = await auth();
  if (!session?.user?.id) return null;
  const userId = session.user.id;

  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, userId),
  });
  const items = await getFeed(userId);

  // Visibility data is best-effort: failures must not 500 the feed.
  const visibility = await getEligibleVisibilityTasks(userId);
  const visibilityUnavailable = visibility === null;
  const showOpsNotice = visibilityUnavailable && (await isOpsUser(userId));

  return (
    <div>
      <h1>Feed</h1>
      {profile?.isPaused && (
        <div style={pauseBox}>
          You are paused: {profile.pausedReason}. Claims and posts are blocked
          until an admin reviews.
        </div>
      )}

      {showOpsNotice && (
        <div style={noticeBox}>
          Visibility tracker not configured. End users see a feed without the
          Suggested section; ops users (you) see this notice.
        </div>
      )}

      {!visibilityUnavailable && (
        <VisibilitySection
          reddit={visibility.reddit.map((t) => ({
            id: t.id,
            kind: t.kind,
            suggestedSubreddit: t.suggestedSubreddit,
            relatedUrl: t.relatedUrl,
            recommendation: t.recommendation,
          }))}
          content={visibility.content.map((t) => ({
            id: t.id,
            kind: t.kind,
            relatedUrl: t.relatedUrl,
            recommendation: t.recommendation,
          }))}
          disabled={!!profile?.isPaused}
        />
      )}

      <h2 style={{ marginTop: 32 }}>Organic opportunities</h2>
      <FeedList items={items} disabled={!!profile?.isPaused} />
    </div>
  );
}

const pauseBox: React.CSSProperties = {
  background: "#3a1f1f",
  border: "1px solid #ff4444",
  padding: 12,
  borderRadius: 6,
  margin: "12px 0",
};

const noticeBox: React.CSSProperties = {
  background: "#1f1f3a",
  border: "1px solid #6666ff",
  padding: 12,
  borderRadius: 6,
  margin: "12px 0",
  fontSize: 13,
};

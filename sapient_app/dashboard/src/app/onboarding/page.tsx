import { desc, eq } from "drizzle-orm";
import { auth } from "../../../auth";
import { db } from "@/db/client";
import { userActiveSubs, userProfiles } from "@/db/schema";
import OnboardingForm from "./form";

export default async function OnboardingPage() {
  const session = await auth();
  if (!session?.user?.id) return null;

  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, session.user.id),
  });
  const subs = await db
    .select()
    .from(userActiveSubs)
    .where(eq(userActiveSubs.userId, session.user.id))
    .orderBy(desc(userActiveSubs.postCount), desc(userActiveSubs.commentCount));

  return (
    <div>
      <h1>Onboarding</h1>
      <p style={{ color: "#9aa0a6" }}>
        Step 1 — pull your Reddit history. We only count activity from before today;
        you cannot become &ldquo;active in r/X&rdquo; by posting there after joining.
      </p>
      <OnboardingForm
        initialTags={profile?.expertiseTags ?? []}
        subs={subs.map((s) => ({
          subreddit: s.subreddit,
          posts: s.postCount,
          comments: s.commentCount,
          checked: s.matchesExpertise,
        }))}
        lastSyncIso={profile?.lastHistorySync?.toISOString() ?? null}
      />
    </div>
  );
}

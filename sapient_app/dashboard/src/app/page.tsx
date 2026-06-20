import { redirect } from "next/navigation";
import { eq } from "drizzle-orm";
import { auth, signIn } from "../../auth";
import { db } from "@/db/client";
import { userProfiles } from "@/db/schema";

export default async function Home() {
  const session = await auth();
  if (!session?.user?.id) {
    return (
      <div>
        <h1>Opportunity Dashboard</h1>
        <p>Connect your Reddit account to get started.</p>
        <form
          action={async () => {
            "use server";
            await signIn("reddit", { redirectTo: "/onboarding" });
          }}
        >
          <button type="submit" style={btn}>Connect Reddit</button>
        </form>
      </div>
    );
  }

  const profile = await db.query.userProfiles.findFirst({
    where: eq(userProfiles.userId, session.user.id),
  });
  if (!profile?.lastHistorySync) redirect("/onboarding");
  redirect("/feed");
}

const btn: React.CSSProperties = {
  padding: "10px 16px",
  background: "#ff4500",
  color: "white",
  border: 0,
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 600,
};

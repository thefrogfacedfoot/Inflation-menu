import { auth } from "../../../../auth";
import { listUserRequests } from "@/lib/gdpr";
import PrivacyClient from "./client";

export const dynamic = "force-dynamic";

export default async function PrivacySettingsPage() {
  const session = await auth();
  if (!session?.user?.id) return null;
  const requests = await listUserRequests(session.user.id);
  return (
    <div>
      <h1>Privacy & data</h1>
      <p style={{ color: "#9aa0a6" }}>
        Export everything we store about you, or request deletion. Deletion
        runs after a 30-day grace period — you can cancel during that window.
      </p>
      <PrivacyClient
        initialRequests={requests.map((r) => ({
          id: r.id,
          kind: r.kind,
          state: r.state,
          requestedAt: r.requestedAt.toISOString(),
          scheduledFor: r.scheduledFor.toISOString(),
          completedAt: r.completedAt?.toISOString() ?? null,
          downloadUrl: r.downloadUrl,
          erased: r.erased,
        }))}
      />
    </div>
  );
}

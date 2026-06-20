import { redirect } from "next/navigation";
import { auth } from "../../../../auth";
import { getDraft } from "@/lib/content-gap";
import Editor from "./editor";

export default async function ContentDraftPage({
  params,
}: {
  params: { draftId: string };
}) {
  const session = await auth();
  if (!session?.user?.id) redirect("/signin");

  const draftId = Number(params.draftId);
  if (!Number.isFinite(draftId) || draftId <= 0) {
    return <div style={{ padding: 24 }}>Invalid draft id.</div>;
  }
  const draft = await getDraft(draftId, session.user.id);
  if (!draft) {
    return <div style={{ padding: 24 }}>Draft not found.</div>;
  }

  return (
    <Editor
      draftId={draft.id}
      initialTitle={draft.title}
      initialBody={draft.body}
      initialStatus={draft.status as "draft" | "edited" | "published" | "archived"}
      initialEditMarkers={draft.editMarkersCount}
      publishedUrl={draft.publishedUrl ?? null}
    />
  );
}

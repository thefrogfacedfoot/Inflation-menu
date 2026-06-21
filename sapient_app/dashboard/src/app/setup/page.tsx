import { auth } from "../../../auth";
import { getBrandConfig, suggestAliasVariants } from "@/lib/wizard";
import WizardClient from "./client";

export const dynamic = "force-dynamic";

export default async function SetupPage() {
  const session = await auth();
  if (!session?.user?.id) return null;
  const cfg = await getBrandConfig();
  return (
    <div>
      <h1>Onboarding wizard</h1>
      <p style={{ color: "#9aa0a6" }}>
        Step {Math.max(1, cfg?.setupStep ?? 0)} of 7
        {cfg?.setupCompletedAt && " — complete"}
      </p>
      <WizardClient
        initialStep={cfg?.setupStep ?? 0}
        initialBrandName={cfg?.brandName ?? ""}
        initialDescription={cfg?.description ?? ""}
        suggestedAliases={suggestAliasVariants(cfg?.brandName ?? "")}
        completed={!!cfg?.setupCompletedAt}
      />
    </div>
  );
}

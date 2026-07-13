# skill: bump-deps-patch

description: Bump exactly ONE dependency by a PATCH-level version only
(x.y.Z -> x.y.Z+n). Unconstrained dependency bumping handed to a cheap model is
a supply-chain incident with a cron schedule — this skill stays narrow or it
doesn't exist.

steps:
1. Pick ONE dependency with an available patch release (sapient_app/requirements.txt
   or dashboard/package.json).
2. Bump only the patch component; regenerate the lockfile if applicable.
3. Run the full checks.

never:
- Never bump major or minor versions.
- Never bump anything with install scripts (npm preinstall/postinstall, setup.py
  with custom commands).
- Never bump more than one dependency per run.
- Never add a new dependency — that is a NEVER in CLAUDE.md.
- Lockfiles are excluded from diff line counts but are ALWAYS secret-scanned.

done_when (verifiable):
- Exactly one dependency line changed, patch component only.
- `verify.sh` passes in the worktree.
- scan-secrets.sh is clean, including the lockfile.

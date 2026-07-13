# skill: fix-lint-debt

description: Remove one existing lint/typecheck warning or error from the codebase
without changing behavior.

steps:
1. Run the repo's real checks (`cd sapient_app && python3 -m pytest -q`,
   `cd dashboard && npx tsc --noEmit`) and pick ONE reported warning/error.
2. Make the smallest change that resolves it.
3. Re-run both checks; both must be green.

never:
- Never disable, suppress, or reconfigure a lint/typecheck rule to silence it.
- Never edit or delete a test.
- Never touch more than one warning per run.
- Never change runtime behavior — "cleanup" means tests green before and after.

done_when (verifiable):
- The chosen warning no longer appears in the check output.
- `verify.sh` passes in the worktree.
- Diff is under 50 lines.

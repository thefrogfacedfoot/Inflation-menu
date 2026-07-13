# skill: fix-flaky-test

description: Make one intermittently failing test deterministic by fixing its
root cause (timing, ordering, shared state) — never by weakening it.

steps:
1. Reproduce the flake: run the failing test alone at least 5 times.
2. Identify the nondeterminism (sleep-based waits, unordered collections,
   leaked state between tests, wall-clock dependence).
3. Fix the ROOT CAUSE in test setup or the code under test.
4. Run the test 10 times in a row; all 10 must pass. Run the full suite.

never:
- Never delete, skip, or mark-xfail a test to make it pass. That is a fail, always.
- Never widen an assertion tolerance without evidence the old tolerance was wrong.
- Never add retries around a flaky assertion — that hides the flake.

done_when (verifiable):
- The target test passes 10 consecutive runs.
- The full suite passes (`verify.sh`).
- No test was deleted, skipped, or weakened (verifier checks the diff).

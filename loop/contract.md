## acts alone
draft PRs on branches; fix lint and test debt; update STATE.md; label issues;
append evidence-cited facts to KNOWLEDGE.md (reflector only, capped at 150 lines)
(work skills only at auto tier — which requires the human-approval gate)

## queues for me
auth, payments, migrations; any skill below auto; any diff over 400 lines;
anything sourced from a non-allowlisted author; anything on blocked-items.txt;
ANY change the system proposes to its own prompts, skills, or thresholds
(self-improvement PRs, labeled agentic:self-improve — no exceptions, ever)

## the system may never modify, even via PR it opens itself
CLAUDE.md, contract.md, guardrails/*, loop.sh, reflect.sh, trust-log.sh,
allowed-authors.txt — proposals about these become digest notes for a human,
enforced by a path allowlist in reflect.sh, not by asking the model nicely

## wakes me up (and trips the circuit breaker where marked ⛔)
verify fails twice on the same item
⛔ a standing goal is violated
⛔ three consecutive runs end in failure
⛔ secrets scan flags anything
daily or monthly budget breached
anything requests a secret
run.lock older than 2 hours found (crashed run)
⛔ = loop.sh creates loop/PAUSED itself; no further runs until a human deletes it

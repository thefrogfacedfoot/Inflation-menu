-- Dashboard migration: account-health monitoring.
--
-- Detects silent Reddit penalties that the 20% removal-rate guardrail in
-- src/lib/guardrails.ts misses:
--   - shadowbans (anon view sees fewer items than authed view)
--   - karma-trend collapses (7d delta vs baseline)
--   - slow-burn removal patterns (high std-dev between removals — sustained,
--     not bursty, so the rolling-10 trigger doesn't fire)
--
-- account_health_check is an append-only log of every run.
-- account_health_state is the latest-state row per user, read by the dashboard
-- banner + ops view.

BEGIN;

CREATE TABLE IF NOT EXISTS account_health_check (
  id              serial PRIMARY KEY,
  "userId"        text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  check_type      text NOT NULL,           -- shadowban | karma_trend | slow_removal
  checked_at      timestamptz NOT NULL DEFAULT now(),
  status          text NOT NULL,           -- ok | warning | alert
  details         jsonb NOT NULL DEFAULT '{}'::jsonb,
  correlation_id  text
);
CREATE INDEX IF NOT EXISTS ix_account_health_check_user_type_at
  ON account_health_check ("userId", check_type, checked_at DESC);

CREATE TABLE IF NOT EXISTS account_health_state (
  "userId"                  text PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  shadowban_suspected_at    timestamptz,
  last_karma_check_at       timestamptz,
  karma_7d_delta            integer,
  last_check_run_at         timestamptz
);

COMMIT;

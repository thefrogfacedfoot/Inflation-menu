-- Dashboard migration: GDPR data export + right-to-erasure (RTBF) requests.
--
-- A single gdpr_request row is the audit-essential record of the user's
-- intent and the system's response. The row survives erasure (the user_id
-- is NULLed; erased=true is the flag the ops queries gate on) so we can
-- prove WHEN we deleted WITHOUT keeping any user PII tied to it.
--
-- States: pending → in_progress → completed | failed | cancelled.
-- - export: pending → in_progress (background) → completed (download_url set)
-- - delete: pending (until scheduled_for) → in_progress (worker picks up)
--           → completed (erased=true, user_id=NULL) | failed
--           - cancelled only valid from pending
--
-- The receipt_correlation_id is the single thread that ties every log line
-- emitted across services (dashboard, visibility) for this request.

BEGIN;

CREATE TABLE IF NOT EXISTS gdpr_request (
  id                       serial PRIMARY KEY,
  -- NULL after a successful erasure. The row itself stays for audit.
  "userId"                 text REFERENCES "user"(id) ON DELETE SET NULL,
  kind                     text NOT NULL,            -- export | delete
  state                    text NOT NULL DEFAULT 'pending', -- pending | in_progress | completed | failed | cancelled
  requested_at             timestamptz NOT NULL DEFAULT now(),
  -- For deletes: now() + 30d at insert. For exports: same as requested_at.
  scheduled_for            timestamptz NOT NULL DEFAULT now(),
  completed_at             timestamptz,
  -- Always set on insert; every log line about this request emits it.
  receipt_correlation_id   text NOT NULL,
  -- Export only: the signed URL the user downloads from. NULL until ready.
  download_url             text,
  -- Set when state=completed AND kind=delete. Survives the user_id nulling.
  erased                   boolean NOT NULL DEFAULT false,
  error_details            jsonb
);
CREATE INDEX IF NOT EXISTS ix_gdpr_request_user ON gdpr_request ("userId");
CREATE INDEX IF NOT EXISTS ix_gdpr_request_due
  ON gdpr_request (scheduled_for)
  WHERE state = 'pending' AND kind = 'delete';

COMMIT;

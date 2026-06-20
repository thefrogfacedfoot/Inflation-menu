-- Visibility schema migration: persist dismissal reasons.
--
-- The dashboard's POST /api/visibility-tasks/:id/dismiss already accepts a
-- `reason` body field. Before this migration it was discarded; after, it is
-- written to this column and surfaced on by-id reads.

BEGIN;

ALTER TABLE visibility.tasks
    ADD COLUMN IF NOT EXISTS dismiss_reason text;

COMMIT;

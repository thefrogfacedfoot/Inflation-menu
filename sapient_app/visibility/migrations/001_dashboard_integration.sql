-- Visibility schema migration: dashboard integration.
--
-- Run once against an existing Postgres database before deploying the
-- dashboard's visibility-tasks feature. Idempotent: each statement uses
-- IF [NOT] EXISTS guards where Postgres allows.

BEGIN;

-- Rename the state column to status. The dashboard claim flow writes
-- status='claimed', a value that wasn't in the old open|done|dismissed set.
ALTER TABLE visibility.tasks RENAME COLUMN state TO status;

-- Update the index that was named after the old column.
ALTER INDEX IF EXISTS visibility.ix_tasks_state_created
    RENAME TO ix_tasks_status_created;

ALTER TABLE visibility.tasks
    ADD COLUMN IF NOT EXISTS suggested_subreddit   varchar(64),
    ADD COLUMN IF NOT EXISTS claimed_by_user_id    text,
    ADD COLUMN IF NOT EXISTS claimed_at            timestamptz,
    ADD COLUMN IF NOT EXISTS dashboard_post_id     integer;

COMMIT;

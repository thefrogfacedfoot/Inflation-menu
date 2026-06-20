-- Dashboard migration: per-(task, user) isolation for content drafts.
--
-- Before this migration, ux_content_draft_active_per_task scoped uniqueness
-- to the visibility task only. That meant User B generating a draft for a
-- task User A already had open routed B into A's WIP. We now scope active-
-- draft uniqueness to (visibility_task_id, "userId"). Two users working the
-- same content gap each get their own draft.
--
-- Apply this BEFORE the next `drizzle-kit push` on existing deploys.
-- `push` would attempt the same swap automatically, but doing it explicitly
-- here avoids any risk of push interpreting the rename as drop+recreate
-- across two columns and momentarily losing the constraint.
--
-- New deploys (clean DB → drizzle-kit push from scratch) pick up the new
-- index name directly from src/db/schema.ts; this file is a no-op there
-- because the OLD index never existed to drop.

BEGIN;

DROP INDEX IF EXISTS ux_content_draft_active_per_task;

CREATE UNIQUE INDEX IF NOT EXISTS ux_content_draft_active_per_task_user
    ON content_draft (visibility_task_id, "userId")
    WHERE status <> 'archived';

COMMIT;

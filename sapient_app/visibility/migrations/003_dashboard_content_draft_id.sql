-- Visibility schema migration: blog_post tasks closed by publishing a
-- content draft.
--
-- The dashboard adds a `content_draft` table (see src/db/schema.ts) and a
-- new mark-published path that flips visibility.tasks.status='done' when
-- a draft is published. We track which draft closed the task — symmetric
-- with dashboard_post_id, which tracks Reddit posts.
--
-- App-level invariant: at most one of dashboard_post_id /
-- dashboard_content_draft_id is set on any given task. Not enforced as a
-- DB constraint because the column is optional and historical rows
-- predate the second path.

BEGIN;

ALTER TABLE visibility.tasks
    ADD COLUMN IF NOT EXISTS dashboard_content_draft_id integer;

COMMIT;

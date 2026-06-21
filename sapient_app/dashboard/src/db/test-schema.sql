-- DDL for the in-memory pglite test database. Mirrors src/db/schema.ts for
-- the tables the guardrail tests exercise. Kept narrow so drift between this
-- and prod is small — extend only when new guardrail behavior needs it.

CREATE TABLE "user" (
  id              text PRIMARY KEY,
  name            text,
  email           text UNIQUE,
  "emailVerified" timestamp,
  image           text,
  "joinedAt"      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_profile (
  "userId"             text PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  reddit_username      text NOT NULL,
  reddit_created_utc   double precision,
  preexisting_cutoff   timestamptz NOT NULL,
  expertise_tags       text[] NOT NULL DEFAULT '{}',
  role                 text NOT NULL DEFAULT 'member',
  is_paused            boolean NOT NULL DEFAULT false,
  paused_code          text,
  paused_reason        text,
  paused_at            timestamptz,
  last_history_sync    timestamptz
);

CREATE TABLE user_active_sub (
  "userId"           text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  subreddit          text NOT NULL,
  post_count         integer NOT NULL DEFAULT 0,
  comment_count      integer NOT NULL DEFAULT 0,
  first_seen         timestamptz,
  last_seen          timestamptz,
  matches_expertise  boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("userId", subreddit)
);

CREATE TABLE claim (
  id                  serial PRIMARY KEY,
  "userId"            text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  opportunity_id      integer NOT NULL,
  claimed_at          timestamptz NOT NULL DEFAULT now(),
  state               text NOT NULL DEFAULT 'claimed',
  source              text NOT NULL DEFAULT 'organic',
  visibility_task_id  integer
);
CREATE UNIQUE INDEX ux_claim_active_per_opp
  ON claim (opportunity_id)
  WHERE state IN ('claimed', 'posted');

CREATE TABLE post (
  id                    serial PRIMARY KEY,
  claim_id              integer NOT NULL REFERENCES claim(id) ON DELETE CASCADE,
  "userId"              text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  subreddit             text NOT NULL,
  reddit_thing_id       text NOT NULL UNIQUE,
  permalink             text NOT NULL,
  body                  text NOT NULL,
  mentions_product      boolean NOT NULL,
  includes_disclosure   boolean NOT NULL,
  posted_at             timestamptz NOT NULL DEFAULT now(),
  is_removed            boolean NOT NULL DEFAULT false,
  upvotes               integer NOT NULL DEFAULT 0,
  last_checked_at       timestamptz
);

CREATE TABLE opportunities (
  id                integer PRIMARY KEY,
  post_id           text NOT NULL,
  post_url          text NOT NULL,
  subreddit         text NOT NULL,
  title             text NOT NULL,
  body              text NOT NULL,
  score             integer NOT NULL,
  reason            text NOT NULL,
  suggested_angle   text NOT NULL,
  status            text NOT NULL,
  created_at        timestamptz NOT NULL
);

CREATE TABLE product_aliases (
  id          serial PRIMARY KEY,
  alias       text NOT NULL UNIQUE,
  is_primary  boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE karma_snapshot (
  "userId"        text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  taken_at        timestamptz NOT NULL DEFAULT now(),
  link_karma      bigint NOT NULL,
  comment_karma   bigint NOT NULL,
  PRIMARY KEY ("userId", taken_at)
);

-- GDPR export + erasure requests. See src/lib/gdpr.ts.
CREATE TABLE gdpr_request (
  id                       serial PRIMARY KEY,
  "userId"                 text REFERENCES "user"(id) ON DELETE SET NULL,
  kind                     text NOT NULL,
  state                    text NOT NULL DEFAULT 'pending',
  requested_at             timestamptz NOT NULL DEFAULT now(),
  scheduled_for            timestamptz NOT NULL DEFAULT now(),
  completed_at             timestamptz,
  receipt_correlation_id   text NOT NULL,
  download_url             text,
  erased                   boolean NOT NULL DEFAULT false,
  error_details            jsonb
);
CREATE INDEX ix_gdpr_request_user ON gdpr_request ("userId");
CREATE INDEX ix_gdpr_request_due
  ON gdpr_request (scheduled_for)
  WHERE state = 'pending' AND kind = 'delete';

-- Brand config + disclosure overrides (wizard). See src/lib/wizard.ts.
CREATE TABLE brand_config (
  id                    serial PRIMARY KEY,
  brand_name            text NOT NULL,
  description           text NOT NULL DEFAULT '',
  setup_step            integer NOT NULL DEFAULT 0,
  setup_completed_at    timestamptz,
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE disclosure_phrase_override (
  id                  serial PRIMARY KEY,
  phrase              text NOT NULL UNIQUE,
  created_at          timestamptz NOT NULL DEFAULT now(),
  created_by_user_id  text REFERENCES "user"(id) ON DELETE SET NULL
);

-- Account-health monitoring. See src/lib/account-health.ts.
CREATE TABLE account_health_check (
  id              serial PRIMARY KEY,
  "userId"        text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  check_type      text NOT NULL,
  checked_at      timestamptz NOT NULL DEFAULT now(),
  status          text NOT NULL,
  details         jsonb NOT NULL DEFAULT '{}'::jsonb,
  correlation_id  text
);
CREATE INDEX ix_account_health_check_user_type_at
  ON account_health_check ("userId", check_type, checked_at DESC);

CREATE TABLE account_health_state (
  "userId"                  text PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  shadowban_suspected_at    timestamptz,
  last_karma_check_at       timestamptz,
  karma_7d_delta            integer,
  last_check_run_at         timestamptz
);

-- Content drafts: blog_post visibility tasks worked through the dashboard.
-- See src/lib/content-gap.ts for the state machine.
CREATE TABLE content_draft (
  id                    serial PRIMARY KEY,
  visibility_task_id    integer NOT NULL,
  "userId"              text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  title                 text NOT NULL,
  body                  text NOT NULL,
  target_query          text NOT NULL,
  status                text NOT NULL DEFAULT 'draft',
  edit_markers_count    integer NOT NULL DEFAULT 0,
  published_url         text,
  published_at          timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
-- Per-(task, user) — see content_draft Drizzle definition for rationale.
CREATE UNIQUE INDEX ux_content_draft_active_per_task_user
  ON content_draft (visibility_task_id, "userId")
  WHERE status <> 'archived';
CREATE INDEX ix_content_draft_user ON content_draft ("userId");

CREATE TABLE content_draft_event (
  id            serial PRIMARY KEY,
  draft_id      integer NOT NULL REFERENCES content_draft(id) ON DELETE CASCADE,
  from_status   text,
  to_status     text NOT NULL,
  "userId"      text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_content_draft_event_draft ON content_draft_event (draft_id, at);

CREATE TABLE content_draft_quota (
  "userId"   text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  day        text NOT NULL,
  count      integer NOT NULL DEFAULT 0,
  PRIMARY KEY ("userId", day)
);

-- The visibility service owns this schema in prod. Mirrored here only so
-- the dashboard's claim/mark-posted plumbing can read and (selectively)
-- write the columns it needs to. Tests can drop the schema to simulate the
-- "visibility tracker unreachable" branch.
CREATE SCHEMA visibility;

-- The wizard writes here (entity rows for brand + competitors, query rows
-- for the tracked queries). Mirrors visibility/visibility/models.py shape.
CREATE TABLE visibility.entities (
  id          serial PRIMARY KEY,
  name        text NOT NULL UNIQUE,
  type        text NOT NULL,          -- brand | competitor
  aliases     jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE visibility.queries (
  id          serial PRIMARY KEY,
  text        text NOT NULL,
  category    text NOT NULL DEFAULT 'general',
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE visibility.tasks (
  id                            integer PRIMARY KEY,
  kind                          text NOT NULL,
  query_id                      integer NOT NULL,
  entity_id                     integer,
  related_url                   text,
  suggested_subreddit           text,
  recommendation                text NOT NULL,
  finder_opportunity_id         integer,
  status                        text NOT NULL DEFAULT 'open',
  claimed_by_user_id            text,
  claimed_at                    timestamptz,
  dashboard_post_id             integer,
  dashboard_content_draft_id    integer,
  dismiss_reason                text,
  created_at                    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_visibility_tasks_status_kind ON visibility.tasks (status, kind);

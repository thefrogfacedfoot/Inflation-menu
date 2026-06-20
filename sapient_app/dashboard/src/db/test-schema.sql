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

-- The visibility service owns this schema in prod. Mirrored here only so
-- the dashboard's claim/mark-posted plumbing can read and (selectively)
-- write the columns it needs to. Tests can drop the schema to simulate the
-- "visibility tracker unreachable" branch.
CREATE SCHEMA visibility;

CREATE TABLE visibility.tasks (
  id                     integer PRIMARY KEY,
  kind                   text NOT NULL,
  query_id               integer NOT NULL,
  entity_id              integer,
  related_url            text,
  suggested_subreddit    text,
  recommendation         text NOT NULL,
  finder_opportunity_id  integer,
  status                 text NOT NULL DEFAULT 'open',
  claimed_by_user_id     text,
  claimed_at             timestamptz,
  dashboard_post_id      integer,
  dismiss_reason         text,
  created_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_visibility_tasks_status_kind ON visibility.tasks (status, kind);

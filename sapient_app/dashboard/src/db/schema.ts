import {
  bigint,
  boolean,
  doublePrecision,
  index,
  integer,
  pgSchema,
  pgTable,
  primaryKey,
  serial,
  text,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import type { AdapterAccountType } from "next-auth/adapters";

/* ---------- Auth.js tables (matches @auth/drizzle-adapter pg schema) ---------- */

export const users = pgTable("user", {
  id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  name: text("name"),
  email: text("email").unique(),
  emailVerified: timestamp("emailVerified", { mode: "date" }),
  image: text("image"),
  joinedAt: timestamp("joinedAt", { mode: "date", withTimezone: true }).defaultNow().notNull(),
});

export const accounts = pgTable(
  "account",
  {
    userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
    type: text("type").$type<AdapterAccountType>().notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("providerAccountId").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (a) => ({ pk: primaryKey({ columns: [a.provider, a.providerAccountId] }) }),
);

export const sessions = pgTable("session", {
  sessionToken: text("sessionToken").primaryKey(),
  userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
  expires: timestamp("expires", { mode: "date" }).notNull(),
});

export const verificationTokens = pgTable(
  "verificationToken",
  {
    identifier: text("identifier").notNull(),
    token: text("token").notNull(),
    expires: timestamp("expires", { mode: "date" }).notNull(),
  },
  (vt) => ({ pk: primaryKey({ columns: [vt.identifier, vt.token] }) }),
);

/* ---------- Domain tables ---------- */

export const userProfiles = pgTable("user_profile", {
  userId: text("userId").primaryKey().references(() => users.id, { onDelete: "cascade" }),
  redditUsername: text("reddit_username").notNull(),
  redditCreatedUtc: doublePrecision("reddit_created_utc"),
  // The cutoff before which Reddit activity counts as "pre-existing".
  // Locked in at first onboarding sync — must never move forward.
  preexistingCutoff: timestamp("preexisting_cutoff", { withTimezone: true }).notNull(),
  expertiseTags: text("expertise_tags").array().notNull().default([]),
  // member | ops. Ops users see the "visibility tracker not configured"
  // notice on the feed when the cross-schema read fails; everyone else gets
  // a silent fallback.
  role: text("role").notNull().default("member"),
  isPaused: boolean("is_paused").notNull().default(false),
  pausedCode: text("paused_code"),
  pausedReason: text("paused_reason"),
  pausedAt: timestamp("paused_at", { withTimezone: true }),
  lastHistorySync: timestamp("last_history_sync", { withTimezone: true }),
});

// Operator-configured set of strings that count as a product mention.
// Seed at least the primary brand name. Read by detectProductMention.
export const productAliases = pgTable("product_aliases", {
  id: serial("id").primaryKey(),
  alias: text("alias").notNull().unique(),
  isPrimary: boolean("is_primary").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
});

// Subs the user was active in BEFORE joining the dashboard. The eligibility gate.
export const userActiveSubs = pgTable(
  "user_active_sub",
  {
    userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
    subreddit: text("subreddit").notNull(),
    postCount: integer("post_count").notNull().default(0),
    commentCount: integer("comment_count").notNull().default(0),
    firstSeen: timestamp("first_seen", { withTimezone: true }),
    lastSeen: timestamp("last_seen", { withTimezone: true }),
    // User flags this as matching their tagged expertise. Feed requires this true.
    matchesExpertise: boolean("matches_expertise").notNull().default(false),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.userId, t.subreddit] }),
    bySub: index("ix_active_sub_subreddit").on(t.subreddit),
  }),
);

// A claim links a user to an opportunity. Only ever one active claim per opp.
export const claims = pgTable(
  "claim",
  {
    id: serial("id").primaryKey(),
    userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
    opportunityId: integer("opportunity_id").notNull(),
    claimedAt: timestamp("claimed_at", { withTimezone: true }).defaultNow().notNull(),
    state: text("state").notNull().default("claimed"), // claimed | posted | abandoned
    // organic = surfaced by the finder service; visibility = synthesized
    // from a visibility.tasks row claimed via /api/visibility-tasks/:id/claim.
    source: text("source").notNull().default("organic"),
    visibilityTaskId: integer("visibility_task_id"),
  },
  (t) => ({
    uniqOpp: uniqueIndex("ux_claim_active_per_opp")
      .on(t.opportunityId)
      .where(__raw("state in ('claimed','posted')")),
    byUser: index("ix_claim_user").on(t.userId),
  }),
);

// Records of actual posts/comments the user reports back as posted from their account.
export const posts = pgTable(
  "post",
  {
    id: serial("id").primaryKey(),
    claimId: integer("claim_id").notNull().references(() => claims.id, { onDelete: "cascade" }),
    userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
    subreddit: text("subreddit").notNull(),
    redditThingId: text("reddit_thing_id").notNull(), // e.g. t1_abc123
    permalink: text("permalink").notNull(),
    body: text("body").notNull(),
    mentionsProduct: boolean("mentions_product").notNull(),
    includesDisclosure: boolean("includes_disclosure").notNull(),
    postedAt: timestamp("posted_at", { withTimezone: true }).defaultNow().notNull(),
    // Updated by the periodic check-in sync.
    isRemoved: boolean("is_removed").notNull().default(false),
    upvotes: integer("upvotes").notNull().default(0),
    lastCheckedAt: timestamp("last_checked_at", { withTimezone: true }),
  },
  (t) => ({
    byUserPosted: index("ix_post_user_posted").on(t.userId, t.postedAt),
    uniqThing: uniqueIndex("ux_post_thing").on(t.redditThingId),
  }),
);

// Snapshot of total karma over time so we can show a trend without polling on read.
export const karmaSnapshots = pgTable(
  "karma_snapshot",
  {
    userId: text("userId").notNull().references(() => users.id, { onDelete: "cascade" }),
    takenAt: timestamp("taken_at", { withTimezone: true }).defaultNow().notNull(),
    linkKarma: bigint("link_karma", { mode: "number" }).notNull(),
    commentKarma: bigint("comment_karma", { mode: "number" }).notNull(),
  },
  (t) => ({ pk: primaryKey({ columns: [t.userId, t.takenAt] }) }),
);

// The Python finder writes here. The dashboard only reads. Schema must match
// app/models.py::Opportunity.
export const opportunities = pgTable("opportunities", {
  id: integer("id").primaryKey(),
  postId: text("post_id").notNull(),
  postUrl: text("post_url").notNull(),
  subreddit: text("subreddit").notNull(),
  title: text("title").notNull(),
  body: text("body").notNull(),
  score: integer("score").notNull(),
  reason: text("reason").notNull(),
  suggestedAngle: text("suggested_angle").notNull(),
  status: text("status").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull(),
});

// Small helper for the partial unique index above. Drizzle's `.where` on
// uniqueIndex accepts a SQL chunk — keeping it isolated so the rest of the
// schema stays declarative.
import { sql, type SQL } from "drizzle-orm";
function __raw(s: string): SQL {
  return sql.raw(s);
}

/* ---------- visibility schema (read + write specific columns) ----------
 *
 * The visibility service owns this schema and its DDL — the dashboard never
 * runs migrations against it. We read the `tasks` table to surface gap
 * suggestions in the feed, and we update four columns when a user claims
 * or completes a visibility-sourced task:
 *   status, claimed_by_user_id, claimed_at, dashboard_post_id.
 */

const visibilitySchema = pgSchema("visibility");

export const visibilityTasks = visibilitySchema.table("tasks", {
  id: integer("id").primaryKey(),
  kind: text("kind").notNull(),
  queryId: integer("query_id").notNull(),
  entityId: integer("entity_id"),
  relatedUrl: text("related_url"),
  suggestedSubreddit: text("suggested_subreddit"),
  recommendation: text("recommendation").notNull(),
  finderOpportunityId: integer("finder_opportunity_id"),
  status: text("status").notNull().default("open"),
  claimedByUserId: text("claimed_by_user_id"),
  claimedAt: timestamp("claimed_at", { withTimezone: true }),
  dashboardPostId: integer("dashboard_post_id"),
  dismissReason: text("dismiss_reason"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull(),
});

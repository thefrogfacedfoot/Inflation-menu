-- Dashboard migration: onboarding wizard (brand_config + disclosure overrides).
--
-- brand_config is intentionally singleton-style (one row per deployment). The
-- wizard advances setup_step from 0 → 7; routes that need the brand to be
-- fully configured (api/opportunities, /feed, /api/visibility-tasks) gate on
-- setup_completed_at via lib/wizard.ts:requireSetupComplete.
--
-- disclosure_phrase_override layers on top of the defaults in
-- src/lib/disclosure-phrases.ts. Ops can add brand-specific phrases without
-- editing the env or redeploying.

BEGIN;

CREATE TABLE IF NOT EXISTS brand_config (
  id                    serial PRIMARY KEY,
  brand_name            text NOT NULL,
  description           text NOT NULL DEFAULT '',
  setup_step            integer NOT NULL DEFAULT 0,
  setup_completed_at    timestamptz,
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS disclosure_phrase_override (
  id                  serial PRIMARY KEY,
  phrase              text NOT NULL UNIQUE,
  created_at          timestamptz NOT NULL DEFAULT now(),
  created_by_user_id  text REFERENCES "user"(id) ON DELETE SET NULL
);

COMMIT;

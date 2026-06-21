/**
 * Production deps for account-health checks. Pulled out so the check
 * functions in account-health.ts can be exercised with deterministic
 * in-memory fakes from the tests.
 *
 * The shadowban check needs two views of the same /user/<name>/about.json:
 *   - authoritative (the user's OAuth token — shows the user's full profile)
 *   - anonymous (no token — shows what everyone else sees; a shadowbanned
 *     user's posts disappear here)
 *
 * Reddit's about.json doesn't include exact submission/comment totals; we
 * approximate by paging the visible portion of /user/<name>/{submitted,
 * comments} listings. The gap, not the exact count, is the signal.
 */
import { getMe, getValidAccessToken } from "./reddit";
import type {
  KarmaDeps,
  ShadowbanDeps,
  SlowBurnDeps,
  UserAboutCounts,
} from "./account-health";

const REDDIT_API = "https://oauth.reddit.com";
const REDDIT_ANON = "https://www.reddit.com";
const UA = process.env.REDDIT_USER_AGENT ?? "opportunity-dashboard/0.1";
// Page size for the visible-count probe. We don't need to enumerate every
// post — we just need enough samples that "shadowbanned vs not" produces a
// measurable gap. 100 is the max page size; one page is usually enough.
const VISIBLE_PROBE_LIMIT = 100;

type Listing = {
  data: { children: unknown[]; after: string | null };
};

async function fetchListingCount(url: string, headers: HeadersInit): Promise<number> {
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(`reddit listing ${url} failed: ${res.status}`);
  const json = (await res.json()) as Listing;
  return json.data.children.length;
}

async function authedAbout(userId: string, username: string): Promise<UserAboutCounts> {
  const token = await getValidAccessToken(userId);
  const auth = { Authorization: `Bearer ${token}`, "User-Agent": UA };
  // Karma comes from /api/v1/me (authoritative for the calling user).
  const me = await getMe(userId);
  const [subs, comments] = await Promise.all([
    fetchListingCount(
      `${REDDIT_API}/user/${username}/submitted?limit=${VISIBLE_PROBE_LIMIT}`,
      auth,
    ),
    fetchListingCount(
      `${REDDIT_API}/user/${username}/comments?limit=${VISIBLE_PROBE_LIMIT}`,
      auth,
    ),
  ]);
  return {
    link_karma: me.link_karma,
    comment_karma: me.comment_karma,
    visibleSubmissions: subs,
    visibleComments: comments,
  };
}

async function anonAbout(username: string): Promise<UserAboutCounts> {
  // No Authorization header — this is the "what does the rest of the world
  // see" view. If the user is shadowbanned, the listings collapse.
  const headers = { "User-Agent": UA };
  const [aboutRes, subs, comments] = await Promise.all([
    fetch(`${REDDIT_ANON}/user/${username}/about.json`, { headers }),
    fetchListingCount(
      `${REDDIT_ANON}/user/${username}/submitted.json?limit=${VISIBLE_PROBE_LIMIT}`,
      headers,
    ),
    fetchListingCount(
      `${REDDIT_ANON}/user/${username}/comments.json?limit=${VISIBLE_PROBE_LIMIT}`,
      headers,
    ),
  ]);
  if (!aboutRes.ok) {
    // 404 is the strongest possible shadowban signal — the public profile
    // is gone. Report zero so the gap calc lights up.
    return { link_karma: 0, comment_karma: 0, visibleSubmissions: 0, visibleComments: 0 };
  }
  const about = (await aboutRes.json()) as {
    data: { link_karma: number; comment_karma: number };
  };
  return {
    link_karma: about.data.link_karma,
    comment_karma: about.data.comment_karma,
    visibleSubmissions: subs,
    visibleComments: comments,
  };
}

export const shadowbanDeps: ShadowbanDeps = {
  fetchAuthed: authedAbout,
  fetchAnon: anonAbout,
  now: () => new Date(),
};

export const karmaDeps: KarmaDeps = {
  fetchCurrentKarma: async (userId: string) => {
    const me = await getMe(userId);
    return { link_karma: me.link_karma, comment_karma: me.comment_karma };
  },
  now: () => new Date(),
};

export const slowBurnDeps: SlowBurnDeps = {
  now: () => new Date(),
};

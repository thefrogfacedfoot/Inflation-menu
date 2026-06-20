import { and, eq } from "drizzle-orm";
import { db } from "@/db/client";
import { accounts } from "@/db/schema";

const REDDIT_API = "https://oauth.reddit.com";
const REDDIT_TOKEN = "https://www.reddit.com/api/v1/access_token";
const UA = process.env.REDDIT_USER_AGENT ?? "opportunity-dashboard/0.1";

type StoredAccount = typeof accounts.$inferSelect;

async function refreshAccessToken(account: StoredAccount): Promise<string> {
  if (!account.refresh_token) throw new Error("no refresh_token on account");

  const basic = Buffer.from(
    `${process.env.AUTH_REDDIT_ID}:${process.env.AUTH_REDDIT_SECRET}`,
  ).toString("base64");

  const res = await fetch(REDDIT_TOKEN, {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": UA,
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: account.refresh_token,
    }),
  });
  if (!res.ok) throw new Error(`refresh failed: ${res.status} ${await res.text()}`);
  const json = (await res.json()) as { access_token: string; expires_in: number };

  const expiresAt = Math.floor(Date.now() / 1000) + json.expires_in;
  await db
    .update(accounts)
    .set({ access_token: json.access_token, expires_at: expiresAt })
    .where(
      and(
        eq(accounts.provider, account.provider),
        eq(accounts.providerAccountId, account.providerAccountId),
      ),
    );
  return json.access_token;
}

async function getAccount(userId: string): Promise<StoredAccount> {
  const row = await db.query.accounts.findFirst({
    where: and(eq(accounts.userId, userId), eq(accounts.provider, "reddit")),
  });
  if (!row) throw new Error(`no Reddit account linked for user ${userId}`);
  return row;
}

export async function getValidAccessToken(userId: string): Promise<string> {
  const account = await getAccount(userId);
  const now = Math.floor(Date.now() / 1000);
  if (!account.access_token || !account.expires_at || account.expires_at - 60 <= now) {
    return refreshAccessToken(account);
  }
  return account.access_token;
}

/** Generic GET to oauth.reddit.com with the user's token + 429 backoff. */
async function redditGet<T>(userId: string, path: string, params?: Record<string, string>): Promise<T> {
  const token = await getValidAccessToken(userId);
  const url = new URL(`${REDDIT_API}${path}`);
  for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, v);
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}`, "User-Agent": UA },
    });
    if (res.status === 429) {
      const retryAfter = Number(res.headers.get("retry-after") ?? "5");
      await new Promise((r) => setTimeout(r, Math.min(60_000, retryAfter * 1000)));
      continue;
    }
    if (!res.ok) throw new Error(`reddit GET ${path} failed: ${res.status}`);
    return (await res.json()) as T;
  }
  throw new Error(`reddit GET ${path} exhausted retries`);
}

export type Me = {
  name: string;
  created_utc: number;
  link_karma: number;
  comment_karma: number;
};

export async function getMe(userId: string): Promise<Me> {
  return redditGet<Me>(userId, "/api/v1/me");
}

type Listing<T> = { data: { children: { data: T }[]; after: string | null } };
type Thing = {
  id: string;
  name: string;
  subreddit: string;
  created_utc: number;
  body?: string;
  selftext?: string;
  title?: string;
  score?: number;
};

/** Walk the user's submissions + comments via /user/<name>/{submitted,comments}. */
export async function* iterUserHistory(userId: string, username: string) {
  for (const kind of ["submitted", "comments"] as const) {
    let after: string | null = null;
    for (let page = 0; page < 10; page++) {
      const listing: Listing<Thing> = await redditGet<Listing<Thing>>(
        userId,
        `/user/${username}/${kind}`,
        { limit: "100", ...(after ? { after } : {}) },
      );
      for (const c of listing.data.children) yield { kind, ...c.data };
      after = listing.data.after;
      if (!after) break;
    }
  }
}

export type FetchedThing = { redditThingId: string; isRemoved: boolean; score: number };

/** Look up posts/comments by fullname (t1_*, t3_*) and report current state. */
export async function fetchThings(userId: string, fullnames: string[]): Promise<FetchedThing[]> {
  if (fullnames.length === 0) return [];
  const listing = await redditGet<Listing<{
    name: string;
    removed_by_category?: string | null;
    banned_by?: string | null;
    score: number;
  }>>(userId, "/api/info", { id: fullnames.join(",") });
  return listing.data.children.map((c) => ({
    redditThingId: c.data.name,
    isRemoved: Boolean(c.data.removed_by_category || c.data.banned_by),
    score: c.data.score ?? 0,
  }));
}

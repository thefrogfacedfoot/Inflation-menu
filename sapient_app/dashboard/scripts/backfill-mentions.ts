/**
 * Backfill posts.mentions_product using the server-side detector.
 *
 * Run after seeding product_aliases:
 *   pnpm tsx scripts/backfill-mentions.ts
 *
 * Idempotent — runs detection over the stored body and updates the row. The
 * server-detected value is authoritative, so this overwrites whatever the
 * client-supplied value was at post time.
 */
import { eq } from "drizzle-orm";
import { db } from "@/db/client";
import { posts } from "@/db/schema";
import { detectProductMention } from "@/lib/product-detect";

async function main() {
  const all = await db.select({ id: posts.id, body: posts.body }).from(posts);
  let updated = 0;
  for (const row of all) {
    const { mentioned } = await detectProductMention(row.body);
    await db
      .update(posts)
      .set({ mentionsProduct: mentioned })
      .where(eq(posts.id, row.id));
    updated += 1;
  }
  // eslint-disable-next-line no-console
  console.log(`backfilled ${updated} posts`);
}

main().then(
  () => process.exit(0),
  (e) => {
    // eslint-disable-next-line no-console
    console.error(e);
    process.exit(1);
  },
);

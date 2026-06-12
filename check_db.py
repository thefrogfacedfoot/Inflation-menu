"""
UIFPI Database Diagnostic Tool
Shows collection status, coverage gaps, and data quality flags.
"""
import sqlite3
import sys

DB_PATH = 'uifpi.db'

TARGET_COUNTRIES = [
    'Singapore', 'Malaysia', 'Indonesia', 'Thailand',
    'India', 'United States', 'United Kingdom', 'Australia',
]
MIN_ITEMS = 10


def fmt(n):
    return f"{n:,}"


def check_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    print("=" * 65)
    print("UIFPI — Database Status Report")
    print("=" * 65)

    # ── Total rows ──────────────────────────────────────────────────
    c.execute('SELECT COUNT(*) FROM prices')
    total = c.fetchone()[0]
    print(f"\nTotal rows: {fmt(total)}")

    # ── By country ──────────────────────────────────────────────────
    print("\n┌── By Country " + "─" * 51 + "┐")
    c.execute(
        'SELECT country, COUNT(*) FROM prices GROUP BY country ORDER BY country'
    )
    country_counts = dict(c.fetchall())
    for country in TARGET_COUNTRIES:
        count = country_counts.get(country, 0)
        warn = "  ⚠  UNDER TARGET" if count < MIN_ITEMS else ""
        bar = "█" * min(count // 50, 20)
        print(f"  {country:<22} {fmt(count):>6}  {bar}{warn}")
    # Unexpected countries
    for country, count in country_counts.items():
        if country not in TARGET_COUNTRIES:
            print(f"  {country:<22} {fmt(count):>6}  (not in target list)")
    print("└" + "─" * 65 + "┘")

    # ── By sector ───────────────────────────────────────────────────
    print("\n┌── By Sector " + "─" * 52 + "┐")
    c.execute(
        'SELECT COALESCE(sector,"NULL"), COUNT(*) FROM prices GROUP BY sector ORDER BY sector'
    )
    for sector, count in c.fetchall():
        print(f"  {sector:<22} {fmt(count):>6}")
    print("└" + "─" * 65 + "┘")

    # ── By source ───────────────────────────────────────────────────
    print("\n┌── By Source " + "─" * 52 + "┐")
    c.execute(
        'SELECT COALESCE(source,"NULL"), COUNT(*) FROM prices GROUP BY source ORDER BY source'
    )
    for source, count in c.fetchall():
        print(f"  {source:<22} {fmt(count):>6}")
    print("└" + "─" * 65 + "┘")

    # ── Date range ──────────────────────────────────────────────────
    print("\n┌── Collection Dates " + "─" * 45 + "┐")
    c.execute('SELECT MIN(collection_date), MAX(collection_date) FROM prices')
    d_min, d_max = c.fetchone()
    print(f"  Earliest:  {d_min}")
    print(f"  Latest:    {d_max}")
    c.execute(
        '''SELECT collection_date, COUNT(*) FROM prices
           GROUP BY collection_date ORDER BY collection_date DESC LIMIT 10'''
    )
    rows = c.fetchall()
    if rows:
        print(f"\n  Most recent dates:")
        for d, cnt in rows:
            print(f"    {d}   {fmt(cnt)} items")
    print("└" + "─" * 65 + "┘")

    # ── Data quality flags ──────────────────────────────────────────
    print("\n┌── Data Quality " + "─" * 49 + "┐")
    c.execute("SELECT COUNT(*) FROM prices WHERE price IS NULL OR price = 0")
    null_prices = c.fetchone()[0]
    flag = "  ⚠ " if null_prices else "  ✓ "
    print(f"{flag}Null/zero prices:  {fmt(null_prices)}")

    # Check for price_usd column
    c.execute("PRAGMA table_info(prices)")
    cols = [row[1] for row in c.fetchall()]
    if 'price_usd' in cols:
        c.execute("SELECT COUNT(*) FROM prices WHERE price_usd IS NULL")
        null_usd = c.fetchone()[0]
        flag = "  ⚠ " if null_usd else "  ✓ "
        print(f"{flag}Missing price_usd: {fmt(null_usd)}")
    else:
        print("  ⚠  price_usd column missing — run: python3 migrate_db.py")

    c.execute(
        "SELECT COUNT(*) FROM prices WHERE item_name IS NULL OR item_name = ''"
    )
    null_names = c.fetchone()[0]
    flag = "  ⚠ " if null_names else "  ✓ "
    print(f"{flag}Null item names:   {fmt(null_names)}")

    # Countries under target
    under = [c_ for c_ in TARGET_COUNTRIES if country_counts.get(c_, 0) < MIN_ITEMS]
    if under:
        print(f"\n  Countries needing more data ({MIN_ITEMS}+ items each):")
        for c_ in under:
            print(f"    ⚠  {c_}  ({country_counts.get(c_, 0)} collected)")
    else:
        print(f"\n  ✓ All {len(TARGET_COUNTRIES)} countries meet the {MIN_ITEMS}-item minimum")
    print("└" + "─" * 65 + "┘")

    # ── Sample rows per country ─────────────────────────────────────
    print("\n┌── Sample Rows (up to 5 per country) " + "─" * 28 + "┐")
    for country in TARGET_COUNTRIES:
        c.execute(
            '''SELECT restaurant_name, item_name, price, currency, sector, collection_date
               FROM prices WHERE country = ?
               ORDER BY RANDOM() LIMIT 5''',
            (country,),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n  {country}:")
            for rest, item, price, curr, sector, dt in rows:
                price_str = f"{curr or '?'} {price:.2f}" if price else "NULL"
                print(f"    [{(sector or '?'):<8}] {(rest or '?')[:22]:<22} "
                      f"{(item or '?')[:35]:<35} {price_str:>12}  {dt}")
        else:
            print(f"\n  {country}: ⚠  NO DATA COLLECTED")
    print("\n└" + "─" * 65 + "┘")

    conn.close()
    print()


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    check_db(path)

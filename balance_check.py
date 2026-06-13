"""
Reports current row counts per country and gaps vs. 200-row minimum target.
Does NOT modify data.
"""
import sqlite3

DB_PATH = 'uifpi.db'
TARGET = 200

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT country, COUNT(*) as cnt FROM prices GROUP BY country ORDER BY cnt DESC")
rows = cur.fetchall()
conn.close()

print(f"{'Country':<22} {'Rows':>6}  {'Target':>6}  {'Gap':>6}  Status")
print("-" * 60)
for country, cnt in rows:
    gap = max(0, TARGET - cnt)
    status = "✓ OK" if cnt >= TARGET else f"✗ NEEDS +{gap}"
    print(f"{country:<22} {cnt:>6}  {TARGET:>6}  {gap:>6}  {status}")

print()
under = [(c, cnt) for c, cnt in rows if cnt < TARGET]
if under:
    print("Countries under 200 rows — historical_scraper.py targets needed:")
    for country, cnt in under:
        print(f"  {country} ({cnt} rows) — run: python3 historical_scraper.py --country '{country}'")
else:
    print("All countries meet the 200-row minimum.")

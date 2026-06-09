import sqlite3

conn = sqlite3.connect('uifpi.db')
c = conn.cursor()

# How many rows collected?
c.execute('SELECT COUNT(*) FROM prices')
print(f"Total items collected: {c.fetchone()[0]}")

# Show first 10 rows
c.execute('SELECT restaurant_name, item_name, price_sgd, sector FROM prices LIMIT 10')
rows = c.fetchall()
for row in rows:
    print(row)

conn.close()

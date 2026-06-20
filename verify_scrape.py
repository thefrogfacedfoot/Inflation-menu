import sqlite3
from datetime import date

conn = sqlite3.connect('uifpi.db')
c = conn.cursor()

# Count total records
c.execute("SELECT COUNT(*) FROM prices")
total = c.fetchone()[0]

# Get records from today
today = date.today().isoformat()
c.execute("SELECT COUNT(*) FROM prices WHERE collection_date = ?", (today,))
today_count = c.fetchone()[0]

# Show sample data
print(f"\n📊 SCRAPER RESULTS")
print(f"{'='*50}")
print(f"Total records in database: {total}")
print(f"Records from today ({today}): {today_count}")

if today_count > 0:
    print(f"\n✓ SUCCESS! Collected {today_count} menu items")
    print(f"\nSample items:")
    c.execute("""
        SELECT restaurant_name, item_name, price_sgd 
        FROM prices 
        WHERE collection_date = ? 
        LIMIT 5
    """, (today,))
    
    for restaurant, item, price in c.fetchall():
        print(f"  • {restaurant}: {item} (S${price})")
else:
    print(f"\n✗ No data collected. Possible issues:")
    print(f"  - Website structure changed")
    print(f"  - Network/timeout issue")
    print(f"  - No aria-label buttons found")

conn.close()

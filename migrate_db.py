"""
One-time migration: adds price_usd column to the prices table.
Safe to run repeatedly — no-ops if the column already exists.
"""
import sqlite3
import sys

DB_PATH = 'uifpi.db'


def migrate(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Add price_usd column
    try:
        c.execute('ALTER TABLE prices ADD COLUMN price_usd REAL')
        conn.commit()
        print("✓ Added price_usd column to prices table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("price_usd column already exists — nothing to do")
        else:
            raise

    # Verify schema
    c.execute('PRAGMA table_info(prices)')
    cols = [row[1] for row in c.fetchall()]
    print(f"Current columns: {', '.join(cols)}")

    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    migrate(path)

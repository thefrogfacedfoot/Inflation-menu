"""
Print the current state of live_scraper.py and recent DB activity.

Usage:
    python3 scraper_status.py
"""
import os
import sqlite3
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_scraper


def main():
    targets = live_scraper.TARGETS
    print('═' * 70)
    print('UIFPI live_scraper — current state')
    print('═' * 70)
    print(f'Total active TARGETS:           {len(targets)}')
    print(f'SCRAPE_MAX_ATTEMPTS:            {live_scraper.SCRAPE_MAX_ATTEMPTS}')
    print(f'SCRAPE_BLOCK_WAIT_S:            {live_scraper.SCRAPE_BLOCK_WAIT_S}')
    print(f'HEADLESS:                       {live_scraper.HEADLESS}')
    print()
    print('By country:')
    for k, v in Counter(t[5] for t in targets).most_common():
        print(f'  {k:<22} {v}')
    print()
    print('By source:')
    for k, v in Counter(t[3] for t in targets).most_common():
        print(f'  {k:<22} {v}')

    db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uifpi.db')
    if not os.path.exists(db):
        return
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('SELECT DISTINCT restaurant_name FROM prices')
    ever = {r[0] for r in c.fetchall()}
    proven = [t for t in targets if t[0] in ever]
    unproven = [t for t in targets if t[0] not in ever]
    print()
    print(f'Proven (ever in DB):     {len(proven)}')
    print(f'Unproven (never in DB):  {len(unproven)}')

    today = date.today().isoformat()
    c.execute('SELECT COUNT(DISTINCT restaurant_name) FROM prices WHERE collection_date = ?',
              (today,))
    today_rest = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM prices WHERE collection_date = ?', (today,))
    today_items = c.fetchone()[0]
    print()
    print(f"Today ({today}): {today_rest} restaurants, {today_items} items")
    conn.close()

    print()
    print('Unproven targets remaining:')
    for t in unproven:
        print(f"  - {t[0]:<48} {t[3]:<10} {t[5]}")


if __name__ == '__main__':
    main()

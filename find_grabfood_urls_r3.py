"""Round 3: search GrabFood SG for Tim Ho Wan, Hokkaido-ya, Swee Choon Tim Sum."""
import json
import os
import random
import time

from find_grabfood_urls import search_grabfood

SEARCHES = [
    ('Tim Ho Wan',         'Singapore', 'formal'),
    ('Hokkaido-ya',        'Singapore', 'formal'),
    ('Hokkaido Ya Ramen',  'Singapore', 'formal'),
    ('Swee Choon',         'Singapore', 'informal'),
    ('Swee Choon Tim Sum', 'Singapore', 'informal'),
]


def main():
    results = []
    for name, country, sector in SEARCHES:
        print(f"\n→ {name} ({country}) …", flush=True)
        try:
            matches = search_grabfood(country, name)
        except Exception as e:
            print(f"    ERROR: {e}", flush=True)
            matches = []
        if matches:
            for m in matches[:8]:
                print(f"    {m['title'][:60]!r}  {m['url']}", flush=True)
        else:
            print("    (no matches)", flush=True)
        results.append({
            'query': name, 'country': country, 'sector': sector,
            'matches': matches[:10],
        })
        time.sleep(random.uniform(8, 14))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'candidate_grabfood_urls_r3.json')
    with open(out, 'w') as fh:
        json.dump(results, fh, indent=2)
    print(f"\nWrote {out}", flush=True)


if __name__ == '__main__':
    main()

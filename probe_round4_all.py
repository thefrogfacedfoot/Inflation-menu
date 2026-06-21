"""Round 4: Vietnam GrabFood (discovered + chain-slug guesses) +
fresh US chains + UK Deliveroo expansion + AU non-direct (Menulog).
Single-attempt mode for fast iteration.
"""
import json
import sqlite3
import time
import live_scraper as L

L.SCRAPE_MAX_ATTEMPTS = 1


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_name TEXT, item_name TEXT, price REAL,
            country TEXT DEFAULT 'Singapore', sector TEXT, source TEXT,
            collection_date TEXT, url TEXT, currency TEXT, price_usd REAL
        )
    """)
    return conn


# ------------ Vietnam ------------
# (1) URLs discovered from GrabFood VN home page
VN_DISCOVERED = [
    ("XIANG BA LAO Chinese", "https://food.grab.com/vn/en/restaurant/xiang-ba-lao-chinese-food-delivery/5-C7V2NFTTCKKTAT"),
    ("MAD ROOSTA Burgers", "https://food.grab.com/vn/en/restaurant/mad-roosta-burgers-grill-delivery/5-C6NDJRMFPCKXRX"),
    ("McDonald's Nguyen Hue", "https://food.grab.com/vn/en/restaurant/mcdonald-s-nguy%E1%BB%85n-hu%E1%BB%87-delivery/VNGFVN000006i3"),
    ("Jollibee Pasteur", "https://food.grab.com/vn/en/restaurant/jollibee-pasteur-delivery/AWjmnWhPfYWaYaQC46R_"),
    ("Robata AN Le Thanh Ton", "https://food.grab.com/vn/en/restaurant/robata-an-le-thanh-ton-delivery/5-CZNZJPT3EFXFT2"),
    ("Cơm Tấm 5 Sao", "https://food.grab.com/vn/en/restaurant/c%C6%A1m-t%E1%BA%A5m-5-sao-delivery/5-C7LUJ4DJN323ME"),
    ("Cơm Phần Winwin", "https://food.grab.com/vn/en/restaurant/c%C6%A1m-c%C6%A1m-ph%E1%BA%A7n-c%C6%A1m-s%C6%B0%E1%BB%9Dn-winwin-delivery/5-C3BERTKGG66CHE"),
    ("Thế Giới Cơm Tấm", "https://food.grab.com/vn/en/restaurant/th%E1%BA%BF-gi%E1%BB%9Bi-c%C6%A1m-t%E1%BA%A5m-b%C3%BAn-th%E1%BB%8Bt-n%C6%B0%E1%BB%9Bng-x%C3%B4i-m%E1%BA%B7n-delivery/5-C3AJMCDFVUXWTN"),
    ("Chóp Chép Bánh Tráng", "https://food.grab.com/vn/en/restaurant/ch%C3%B3p-ch%C3%A9p-b%C3%A1nh-tr%C3%A1ng-tr%E1%BB%99n-t%C3%B3p-m%E1%BB%A1-tr%E1%BB%A9ng-l%C3%B2ng-%C4%91%C3%A0o-l%C3%AA-lai-delivery/5-C63FJPLYCGJ3ME"),
    ("Cơm Canh Korean", "https://food.grab.com/vn/en/restaurant/c%C6%A1m-canh-th%E1%BB%8Bt-l%E1%BB%A3n-d%E1%BB%93i-h%C3%A0n-qu%E1%BB%91c-c%C6%A1m-canh-x%C6%B0%C6%A1ng-b%C3%B2-ch%C3%A2n-gi%C3%B2-bossam-korean-food-jinhan-kupbap-delivery/5-C7T1A2NJJYEKSA"),
]

# (2) Common VN chain slugs — guesses based on SG/MY pattern
VN_CHAIN_GUESSES = [
    ("Highlands Coffee (chain)", "https://food.grab.com/vn/en/chain/highlands-coffee-delivery"),
    ("The Coffee House (chain)", "https://food.grab.com/vn/en/chain/the-coffee-house-delivery"),
    ("Phuc Long (chain)", "https://food.grab.com/vn/en/chain/phuc-long-delivery"),
    ("Pizza Hut VN (chain)", "https://food.grab.com/vn/en/chain/pizza-hut-delivery"),
    ("KFC VN (chain)", "https://food.grab.com/vn/en/chain/kfc-delivery"),
    ("Lotteria (chain)", "https://food.grab.com/vn/en/chain/lotteria-delivery"),
    ("Starbucks VN (chain)", "https://food.grab.com/vn/en/chain/starbucks-delivery"),
    ("Domino's VN (chain)", "https://food.grab.com/vn/en/chain/dominos-pizza-delivery"),
    ("Texas Chicken VN (chain)", "https://food.grab.com/vn/en/chain/texas-chicken-delivery"),
    ("Burger King VN (chain)", "https://food.grab.com/vn/en/chain/burger-king-delivery"),
]

# Mark each VN candidate with the correct tuple shape
def vn_targets():
    out = []
    for name, url in VN_DISCOVERED:
        # All discovered are restaurant pages — treat per-restaurant
        sector = "chain" if any(k in name.lower() for k in ("mcdonald", "jollibee")) else "independent"
        out.append((name, url, sector, "grabfood", "VND", "Vietnam"))
    for name, url in VN_CHAIN_GUESSES:
        out.append((name, url, "chain", "grabfood", "VND", "Vietnam"))
    return out


# ------------ US fresh batch (none previously tried) ------------
US_FRESH = [
    ("Cheesecake Factory", "https://www.thecheesecakefactory.com/menu/", "chain", "direct", "USD", "United States"),
    ("Jersey Mike's", "https://www.jerseymikes.com/menu", "chain", "direct", "USD", "United States"),
    ("Firehouse Subs", "https://www.firehousesubs.com/menu", "chain", "direct", "USD", "United States"),
    ("Jimmy John's", "https://www.jimmyjohns.com/menu", "chain", "direct", "USD", "United States"),
    ("Potbelly", "https://www.potbelly.com/menu", "chain", "direct", "USD", "United States"),
    ("Panda Express", "https://www.pandaexpress.com/menu", "chain", "direct", "USD", "United States"),
    ("Longhorn Steakhouse", "https://www.longhornsteakhouse.com/menu", "chain", "direct", "USD", "United States"),
    ("P.F. Chang's", "https://www.pfchangs.com/menu", "chain", "direct", "USD", "United States"),
    ("Carrabba's", "https://www.carrabbas.com/menu/", "chain", "direct", "USD", "United States"),
    ("Bonefish Grill", "https://www.bonefishgrill.com/menu", "chain", "direct", "USD", "United States"),
    ("Maggiano's", "https://www.maggianos.com/menu/", "chain", "direct", "USD", "United States"),
    ("Tropical Smoothie Cafe", "https://www.tropicalsmoothiecafe.com/menu", "chain", "direct", "USD", "United States"),
    ("McAlister's Deli", "https://www.mcalistersdeli.com/menu", "chain", "direct", "USD", "United States"),
    ("Schlotzsky's", "https://www.schlotzskys.com/menu", "chain", "direct", "USD", "United States"),
    ("Yard House", "https://www.yardhouse.com/menu", "chain", "direct", "USD", "United States"),
    ("Cracker Barrel breakfast", "https://www.crackerbarrel.com/menu/breakfast", "chain", "direct", "USD", "United States"),
    ("Olive Garden lunch", "https://www.olivegarden.com/menu/pasta", "chain", "direct", "USD", "United States"),
]

# ------------ UK Deliveroo expansion (different locations not previously tried) ------------
UK_DELIVEROO = [
    ("Dishoom King's Cross (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/kings-cross/dishoom-kings-cross",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Dishoom Carnaby (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/dishoom-carnaby",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Pho Battersea (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/battersea/pho-battersea",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Pho Shoreditch (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/shoreditch/pho-shoreditch",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Pizza Pilgrims West End (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/west-end/pizza-pilgrims-west-end",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Wagamama Camden (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/camden-town/wagamama-camden",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Nando's Shoreditch (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/shoreditch/nandos-shoreditch",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Pret Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/pret-a-manger-soho",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Itsu Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/itsu-soho",
     "chain", "deliveroo", "GBP", "United Kingdom"),
    ("Leon Soho (Deliveroo)",
     "https://deliveroo.co.uk/menu/london/soho/leon-soho",
     "chain", "deliveroo", "GBP", "United Kingdom"),
]

# ------------ AU via Menulog (Deliveroo no longer operates AU) ------------
AU_MENULOG = [
    ("McDonald's AU (Menulog)",
     "https://www.menulog.com.au/restaurants-mcdonalds-australia-fair-southport/menu",
     "chain", "js", "AUD", "Australia"),
    ("KFC Sydney CBD (Menulog)",
     "https://www.menulog.com.au/restaurants-kfc-sydney-cbd/menu",
     "chain", "js", "AUD", "Australia"),
    ("Hungry Jack's Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-hungry-jacks-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Pizza Hut Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-pizza-hut-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Subway Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-subway-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Red Rooster Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-red-rooster-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Domino's Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-dominos-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Guzman y Gomez Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-guzman-y-gomez-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Boost Juice Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-boost-juice-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Krispy Kreme Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-krispy-kreme-sydney/menu",
     "chain", "js", "AUD", "Australia"),
    ("Grill'd Sydney (Menulog)",
     "https://www.menulog.com.au/restaurants-grilld-sydney/menu",
     "chain", "js", "AUD", "Australia"),
]

USD_RATES = {
    "SGD": 1.29, "MYR": 4.13, "IDR": 17785.84, "THB": 32.88, "VND": 24500.0,
    "GBP": 0.79, "USD": 1.0, "AUD": 1.53, "INR": 83.0,
}


def probe(targets, label):
    print(f"\n========== {label} ({len(targets)}) ==========", flush=True)
    rows = []
    for tgt in targets:
        name = tgt[0]
        conn = make_db()
        t0 = time.time()
        err = None
        count = 0
        try:
            count = L._scrape_one(tgt, conn, "2026-06-21", USD_RATES)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:100]}"
        dur = time.time() - t0
        status = "OK" if count > 0 else "FAIL"
        rows.append((status, name, count, dur, err, tgt))
        print(f"   [{status:4}] {name:38} {count:5d} items  ({dur:5.1f}s)   {err or ''}", flush=True)
        conn.close()
    return rows


def main():
    all_rows = []
    all_rows += probe(vn_targets(), "Vietnam (10 discovered + 10 chain guesses)")
    all_rows += probe(UK_DELIVEROO, "UK Deliveroo expansion")
    all_rows += probe(AU_MENULOG, "AU Menulog")
    all_rows += probe(US_FRESH, "US fresh")

    print("\n\n=== FINAL — OK candidates only ===", flush=True)
    for status, name, count, dur, err, tgt in all_rows:
        if status == "OK":
            print(f"   {name:38} {count:5d} items   {tgt[1]}", flush=True)


if __name__ == "__main__":
    main()

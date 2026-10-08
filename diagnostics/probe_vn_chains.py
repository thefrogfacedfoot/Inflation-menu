"""Verify candidate GrabFood VN chain outlets have a live, scrapable listing (in-memory DB; no real DB writes).

Calls live_scraper._scrape_one exactly like the nightly does. Guard (docs: GrabFood throttle false deaths): on >= 6
consecutive failures the verdicts are discarded, the probe cools down 300 s and re-queues those candidates once.
Pacing 8-16 s between probes. Never run while the nightly scraper is running.
Usage (from the repo root, UIFPI_HEADLESS=1): python3 diagnostics/probe_vn_chains.py
"""
import json
import os
import random
import sqlite3
import sys
import time
from datetime import date
from urllib.parse import quote

sys.path.insert(0, os.getcwd())
from live_scraper import _scrape_one, get_usd_rates  # noqa: E402

B = "https://food.grab.com/vn/en/restaurant/"
# (name, slug, id, city)  city = HCMC / HN / other (from the outlet's street or mall name; best effort)
RAW = [
    ("Highlands Coffee - Pullman HN", "highlands-coffee-pullman-hn-delivery", "5-CZDFCNTJKEVTTJ", "HN"),
    ("Highlands Coffee - Kiosk Hồ Tây", "highlands-coffee-kiosk-hồ-tây-delivery", "5-CZDXGYKZLUXFC6", "HN"),
    ("Highlands Coffee - 402 Trần Hưng Đạo D5", "highlands-coffee-402-trần-hưng-đạo-d5-delivery", "5-C2LVTF23RTLJLA", "HCMC"),
    ("Highlands Coffee - Vincom Phan Văn Trị", "highlands-coffee-vincom-phan-văn-trị-delivery", "5-CZCYNYKXSF5GE6", "HCMC"),
    ("Highlands Coffee - Lê Quang Định", "highlands-coffee-lê-quang-định-delivery", "5-CZCYNYKXRB6HAN", "HCMC"),
    ("Highlands Coffee - Nguyễn Trọng Tuyển", "highlands-coffee-nguyễn-trọng-tuyển-delivery", "AWjrFQ3vR-bAtZoKZshD", "HCMC"),
    ("Highlands Coffee - Nguyễn Văn Quá", "highlands-coffee-nguyễn-văn-quá-delivery", "5-CZCYNYKXNEJUVT", "HCMC"),
    ("Highlands Coffee - Flora Thủ Đức", "highlands-coffee-flora-thủ-đức-delivery", "5-C2LVTF23R36AAN", "HCMC"),
    ("Highlands Coffee - 299 Lê Duẩn Long Thành", "highlands-coffee-299-lê-duẩn-long-thành-delivery", "5-CZCXR8NZTBLDHE", "other"),
    ("KFC - Nguyễn Xí", "kfc-nguyễn-xí-delivery", "5-C253CXXBVAEUR2", "HCMC"),
    ("KFC - Mỹ Đình", "kfc-mỹ-đình-delivery", "5-CYMAPCDGEPMDEN", "HN"),
    ("KFC - TTTM Big C Hà Nội", "kfc-tttm-big-c-hà-nội-delivery", "5-CYMAAGABJAJ1AX", "HN"),
    ("KFC - Hoàn Kiếm", "kfc-hoàn-kiếm-delivery", "5-CYMAAFTDCRAEAN", "HN"),
    ("KFC - TTTM Big C An Lạc", "kfc-tttm-big-c-an-lạc-delivery", "5-CYMAEEEJTUJJET", "HCMC"),
    ("KFC - Cầu Giấy", "kfc-cầu-giấy-delivery", "5-CYL3WGK2TX31VE", "HN"),
    ("KFC - Bạch Mai", "kfc-bạch-mai-delivery", "5-CYMAALK2MFXASA", "HN"),
    ("Lotteria - TTTM Lotte Center", "lotteria-tttm-lotte-center-delivery", "5-CYXGE6AAG4MKWE", "HN"),
    ("Lotteria - TTTM The Garden", "lotteria-tttm-the-garden-delivery", "5-CYXGE6AAGNJZE2", "HN"),
    ("Lotteria - Trần Đại Nghĩa", "lotteria-trần-đại-nghĩa-delivery", "VNGFVN000004za", "HN"),
    ("Lotteria - Ngô Gia Tự", "lotteria-ngô-gia-tự-delivery", "VNGFVN0000046g", "HN"),
    ("Lotteria - Lò Đúc", "lotteria-lò-đúc-delivery", "VNGFVN000004z3", "HN"),
    ("Lotteria - Phú Mỹ Hưng", "lotteria-phú-mỹ-hưng-delivery", "VNGFVN00000458", "HCMC"),
    ("Lotteria - Xô Viết Nghệ Tĩnh", "lotteria-xô-viết-nghệ-tĩnh-delivery", "VNGFVN0000045w", "HCMC"),
    ("Lotteria - Khâm Thiên", "lotteria-khâm-thiên-delivery", "VNGFVN000004z8", "HN"),
    ("Lotteria - TTTM Royal City", "lotteria-tttm-royal-city-delivery", "5-CYXGE6AAGXCXNT", "HN"),
    ("Phúc Long - Nguyễn Thái Học", "phúc-long-coffee-tea-house-nguyễn-thái-học-delivery", "VNGFVN000003lk", "HCMC"),
    ("Phúc Long - 382 Trần Hưng Đạo", "phúc-long-coffee-tea-house-trần-hưng-đạo-delivery", "VNGFVN000003lr", "HCMC"),
    ("Phúc Long - 317 Ngô Gia Tự", "phúc-long-coffee-tea-house-ngô-gia-tự-delivery", "5-CY5AGYMCV7V3EA", "HCMC"),
    ("Phúc Long - TTTM Vietjet Plaza", "phúc-long-tttm-vietjet-plaza-delivery", "5-CY5AGYMCWCB1VJ", "HCMC"),
    ("Phúc Long - Sky Garden", "phúc-long-sky-garden-delivery", "VNGFVN000003qn", "HCMC"),
    ("Phúc Long - Phổ Quang", "phúc-long-coffee-tea-house-phổ-quang-delivery", "5-CY5AGYMCV2XCBE", "HCMC"),
    ("Phúc Long - 82 Hàng Điếu", "phúc-long-82-hàng-điếu-delivery", "5-CYLTGZMUGPB1SA", "HN"),
    ("Katinat - Nguyễn Du", "katinat-sài-gòn-nguyễn-du-delivery", "VNGFVN00000713", "HCMC"),
    ("The Coffee House - Hai Bà Trưng", "the-coffee-house-hai-bà-trưng-delivery", "5-C3DGGU41FGK3TJ", "HCMC"),
    ("The Coffee House - Trung Hòa", "the-coffee-house-trung-hòa-delivery", "5-C3DGGU41E7KXEN", "HN"),
    ("Jollibee - Tiến Bộ Plaza", "jollibee-tiến-bộ-plaza-hà-nội-delivery", "5-C7NFCUBXT722JT", "HN"),
    ("Jollibee - Tô Hiệu", "jollibee-tô-hiệu-delivery", "AWjmn1Cn2bMmVZfr_kgB", "HN"),
    ("Jollibee - EC Đà Nẵng", "jollibee-ec-đà-nẵng-delivery", "AWjmnpbKcEjWIUmPsqs7", "other"),
    ("Texas Chicken - Võ Văn Ngân", "texas-chicken-võ-văn-ngân-delivery", "5-C6AJCNKTN4KVVN", "HCMC"),
    ("Pizza 4P's - Hoàng Thành Tower", "pizza-4p’s-hoàng-thành-tower-delivery", "5-C2U2GELXMCLEET", "HN"),
    ("Pizza Hut - Đỗ Xuân Hợp", "pizza-hut-đỗ-xuân-hợp-delivery", "5-CYUGRACERLAYJX", "HCMC"),
    ("Burger King - Trung Hòa", "burger-king-trung-hòa-delivery", "5-CZNDJ4MDC4MDCE", "HN"),
    ("Coffee House (generic) - control for brand match", "coffee-house-delivery", "5-CZBFCUETERDDN6", "other"),
]
# the last row is NOT a chain outlet (an unrelated restaurant that happens to match "coffee house"); dropped below
RAW = [r for r in RAW if "control for brand match" not in r[0]]
CANDIDATES = [(n, B + quote(s, safe="-_") + "/" + i, "chain", "grabfood", "VND", "Vietnam") for n, s, i, _ in RAW]
CITY = {n: c for n, _, _, c in RAW}


def mem_db():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE prices (id INTEGER PRIMARY KEY AUTOINCREMENT, restaurant_name TEXT, item_name TEXT, price REAL,"
              " currency TEXT, price_usd REAL, country TEXT, sector TEXT, source TEXT, collection_date TEXT, url TEXT, platform TEXT)")
    return c


def main():
    today, rates, conn = date.today().isoformat(), get_usd_rates(), mem_db()
    queue, results, consec, requeued = list(CANDIDATES), {}, [], set()
    while queue:
        t = queue.pop(0)
        t0 = time.time()
        try:
            status, detail = "OK", _scrape_one(t, conn, today, rates)
        except Exception as e:
            status, detail = "FAIL", str(e)[:140]
        results[t[0]] = dict(url=t[1], status=status, detail=detail, city=CITY[t[0]], s=round(time.time() - t0, 1))
        print(f"{len(results):>2}/{len(CANDIDATES)} {t[0]:<48} {status} {detail}", flush=True)
        consec = (consec + [t[0]] if status == "FAIL" else [])
        if len(consec) >= 6:
            print("GUARD: >= 6 consecutive failures; discarding those verdicts, cooling 300 s", flush=True)
            for n in consec:
                results.pop(n, None)
                if n not in requeued:
                    requeued.add(n)
                    queue.append(next(c for c in CANDIDATES if c[0] == n))
            consec = []
            time.sleep(300)
        else:
            time.sleep(random.uniform(8, 16))
    json.dump(results, open("diagnostics/probe_vn_chains_results.json", "w"), indent=1, ensure_ascii=False)
    ok = [n for n, r in results.items() if r["status"] == "OK"]
    print(f"\nOK {len(ok)}/{len(results)}; HCMC {sum(CITY[n]=='HCMC' for n in ok)}, HN {sum(CITY[n]=='HN' for n in ok)}, other {sum(CITY[n]=='other' for n in ok)}")


if __name__ == "__main__":
    main()

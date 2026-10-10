"""ONS price-quote files: catering (ITEM_ID 22xxxx) quote COUNTS only. Price columns are never read.
Output: ons_catering_counts.csv (file, quote_date, item_id, item_desc, region, n_quotes, n_shops_item_region)
"""
import io, re, sys, zipfile, time, urllib.request
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
B = "https://www.ons.gov.uk/file?uri=/economy/inflationandpriceindices/datasets/consumerpriceindicescpiandretailpricesindexrpiitemindicesandpricequotes/"
page = (HERE / "page.html").read_text()
paths = sorted(set(re.findall(r'/file\?uri=[^"]*quotes/(pric[^"]+)', page)))
paths = [p for p in paths if re.search(r"pricequote|pricesquote", p.split("/")[-1])]
out = HERE / "ons_catering_counts.csv"
done = set(pd.read_csv(out).file) if out.exists() else set()
want = ["QUOTE_DATE", "ITEM_ID", "ITEM_DESC", "SHOP_CODE", "REGION", "CS_ID", "CS_DESC"]
rows = []


def handle(name, raw):
    d = pd.read_csv(io.BytesIO(raw), usecols=lambda c: c.strip().upper() in want, encoding="latin-1", low_memory=False)
    d.columns = [c.strip().upper() for c in d.columns]
    d = d.rename(columns={"CS_ID": "ITEM_ID", "CS_DESC": "ITEM_DESC"})
    if "ITEM_DESC" not in d: d["ITEM_DESC"] = ""
    d["ITEM_ID"] = pd.to_numeric(d.ITEM_ID, errors="coerce")
    tot = d.groupby("QUOTE_DATE").size().rename("n_all_quotes")
    c = d[(d.ITEM_ID >= 220000) & (d.ITEM_ID < 230000)]
    g = (c.groupby(["QUOTE_DATE", "ITEM_ID", "ITEM_DESC", "REGION"])
          .agg(n_quotes=("SHOP_CODE", "size"), n_shops=("SHOP_CODE", "nunique")).reset_index())
    g["file"] = name
    g = g.join(tot, on="QUOTE_DATE")
    return g


for p in paths:
    name = p.split("/")[-1]
    if name in done:
        continue
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(B + p, headers={"User-Agent": "Mozilla/5.0"}), timeout=180).read()
            break
        except Exception as e:
            print("retry", name, e, flush=True); time.sleep(5); raw = None
    if raw is None:
        print("FAILED", name, flush=True); continue
    try:
        if name.endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(raw))
            gs = [handle(name + "::" + m, z.read(m)) for m in z.namelist() if m.lower().endswith(".csv")]
            g = pd.concat(gs) if gs else pd.DataFrame()
        elif name.endswith(".xlsx"):
            x = pd.read_excel(io.BytesIO(raw), usecols=lambda c: str(c).strip().upper() in want)
            g = handle(name, x.to_csv(index=False).encode())
        else:
            g = handle(name, raw)
    except Exception as e:
        print("PARSE-FAIL", name, e, flush=True); continue
    g.to_csv(out, mode="a", header=not out.exists(), index=False)
    print("ok", name, len(g), flush=True)
    time.sleep(1)

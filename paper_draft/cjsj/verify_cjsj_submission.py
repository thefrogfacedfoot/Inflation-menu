"""Verification pass for paper_draft/UICPI_CJSJ_submission.docx (run from anywhere).

    python3 paper_draft/cjsj/verify_cjsj_submission.py [path/to/submission.docx]

Checks the docx against its sources: statistics vs analysis_results/*.json and the DB, required
hedges and known-bad phrasings, an expanded grep list, hidden content/metadata, the CJSJ template's
own XML, the full paper (.md and PDF), and a LibreOffice render (2 pages). Exits 1 on any FAIL.

Inputs that are not in the repo (set the env var, or the default location is used):
  CJSJ_TEMPLATE  the template .docx        (default ~/Downloads/CJSJ+Original+Research+Template+(1).docx)
  UICPI_DB_DIR   dir holding uifpi.db and  (default: repo root). uifpi.db is gitignored.
                 uifpi.db.backup_pre_my_zero_delete_20260619_085250
Needs: python3, git, pdftotext/pdfinfo (poppler); soffice optional (render check is SKIPped without it).
NOT covered: Microsoft Word layout. Open the docx in Word and confirm it is 2 pages.
"""
import re, sys, json, zipfile, sqlite3, html, struct, subprocess, os

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2])
DBDIR = os.environ.get("UICPI_DB_DIR", REPO)
DOCX = sys.argv[1] if len(sys.argv) > 1 else f"{REPO}/paper_draft/UICPI_CJSJ_submission.docx"
TPL = os.environ.get("CJSJ_TEMPLATE", os.path.expanduser("~/Downloads/CJSJ+Original+Research+Template+(1).docx"))
for _p, _what in ((DOCX, "docx"), (TPL, "CJSJ template (set CJSJ_TEMPLATE)"), (f"{DBDIR}/uifpi.db", "uifpi.db (set UICPI_DB_DIR)")):
    if not os.path.exists(_p): sys.exit(f"missing input: {_what}: {_p}")
PAPER = f"{REPO}/paper_draft/UICPI_A_Method_for_Collecting_Chain_and_Independent.md"

res = []  # (id, status, evidence)
def rec(i, ok, ev, held=False, advisory=False):
    res.append((i, "HELD" if held else ("ADVISORY" if (advisory and not ok) else ("PASS" if ok else "FAIL")), ev))
def skip(i, why): res.append((i, "SKIP", why))

z = zipfile.ZipFile(DOCX)
D = z.read("word/document.xml").decode(); FN = z.read("word/footnotes.xml").decode()
ST = z.read("word/styles.xml").decode(); NU = z.read("word/numbering.xml").decode()
CORE = z.read("docProps/core.xml").decode(); APP = z.read("docProps/app.xml").decode()
tx = lambda p: html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)))
PARAS = [p for p in re.findall(r"<w:p[ >].*?</w:p>", D, re.S)]
P = [tx(p) for p in PARAS if tx(p)]
TEXT = "\n".join(P)
FNTEXT = tx(re.search(r'<w:footnote [^>]*w:id="1".*?</w:footnote>', FN, re.S).group(0))
ALL = TEXT + "\n" + FNTEXT + "\n" + re.sub(r"<[^>]+>", " ", CORE + APP)

gap = json.load(open(f"{REPO}/analysis_results/gap_robustness.json"))["specs"]
gr = json.load(open(f"{REPO}/analysis_results/granger_results.json"))
con = sqlite3.connect(f"file:{DBDIR}/uifpi.db?mode=ro", uri=True)

# ============ A. NUMBERS ============
ct = gap["calendar_true"]; ff = gap["interp_ffill"]
rec("A1 US F/p/n/df (calendar_true, headline)", ct["role"] == "headline" and f"F(1,{ct['n']-3})={ct['F']:.2f}" in TEXT and f"p={ct['p_analytic']}" in TEXT and f"(n={ct['n']})" in TEXT,
    f"json: role={ct['role']} F={ct['F']} p={ct['p_analytic']} n={ct['n']} -> df(1,{ct['n']-3}); docx has F(1,28)=4.20, p=0.0499, n=31")
rec("A1b deprecated original spec absent", gap["original"]["role"] == "deprecated" and not re.search(r"6\.03|0\.021", ALL), f"json marks original 6.0336/0.021 'deprecated'; docx hits: {re.findall(r'6\.03|0\.021', ALL) or 'none'}")
sh, bl = ct["p_permutation"]["shuffle"], ct["p_permutation"]["block"]
rec("A2 permutation shuffle/block", f"p={sh:.3f}" in TEXT and f"p={bl:.3f}" in TEXT and f"{sh:.3f}–{bl:.3f}" in TEXT, f"json {sh}/{bl} -> {sh:.3f}/{bl:.3f}; docx has 0.052, 0.069 and range 0.052–0.069")
ind, mal = gr["India"], gr["Malaysia"]
rec("A3 n: US 31 / India 47 / Malaysia 30", ct["n"] == 31 and ind["n_obs"] == 47 and mal["n_obs"] == 30 and "India (n=47)" in TEXT and "Malaysia (n=30)" in TEXT, f"json n: US {ct['n']}, IN {ind['n_obs']}, MY {mal['n_obs']}")
rec("A4 India F/p", f"F={ind['granger_f_statistic']:.3f}, p={ind['granger_p_value']:.3f}" in TEXT, f"json F={ind['granger_f_statistic']} p={ind['granger_p_value']}")
rec("A5 Malaysia F/p", f"F={mal['granger_f_statistic']:.3f}, p={mal['granger_p_value']:.3f}" in TEXT, f"json F={mal['granger_f_statistic']} p={mal['granger_p_value']}")
rec("A6 forward-fill F(1,35)/p/n", f"F(1,{ff['n']-3})={ff['F']:.2f}, p={ff['p_analytic']}, n={ff['n']}" in TEXT, f"json interp_ffill F={ff['F']} p={ff['p_analytic']} n={ff['n']} -> df(1,{ff['n']-3})")
fw = 1 - 0.95 ** 3
rec("A7 1-0.95^3 = 14.3%", abs(fw - 0.143) < 0.001 and "≈14.3%" in TEXT, f"1-0.95^3 = {fw:.6f}")
tested = [c for c, v in gr.items() if v.get("granger_p_value") is not None]
rec("A8 family size = 3 (committed outputs)", sorted(tested) == ["India", "Malaysia", "United States"], f"countries with a committed Granger p-value: {sorted(tested)}")
thr = {"United Kingdom": 18, "Australia": 23, "Indonesia": 20, "Singapore": 8, "Thailand": 0}
rec("A9 threshold list (UK 18, AU 23, ID 20, SG 8, TH 0)", all(gr[c]["n_obs"] == n for c, n in thr.items()) and "(United Kingdom 18, Australia 23, Indonesia 20, Singapore 8, Thailand 0)" in TEXT, f"json n_obs: { {c: gr[c]['n_obs'] for c in thr} }")
codes = {"United States": "US", "United Kingdom": "GB", "Malaysia": "MY", "India": "IN", "Australia": "AU"}
ov = {}
for c, cc in codes.items():
    idx = {r[0] for r in con.execute("select year_month from uifpi_index where country=? and uifpi_combined is not null", (c,))}
    cpi = {r[0] for r in con.execute("select year_month from monthly_cpi where country_code=?", (cc,))}
    ov[c] = len(idx & cpi)
exp = {"United States": 31, "United Kingdom": 18, "Malaysia": 30, "India": 47, "Australia": 23}
rec("A10 live-DB overlap == committed n", ov == exp, f"fresh overlap from uifpi.db: {ov}")
usi = {r[0] for r in con.execute("select year_month from uifpi_index where country='United States' and uifpi_combined is not null")}
usc = {r[0] for r in con.execute("select year_month from monthly_cpi where country_code='US'")}
w = sorted(usi & usc)
rec("A11 US window 2018-04..2024-10", (w[0], w[-1]) == ("2018-04", "2024-10") and "2018-04–2024-10" in TEXT, f"DB overlap window {w[0]}..{w[-1]} ({len(w)} months)")
Qs = {("United Arab Emirates", "wayback-deliveroo"), ("Vietnam", "wayback-grabfood")}
_pn = {"United States", "United Kingdom", "Malaysia", "Singapore", "India", "Indonesia", "Australia", "Thailand"}
_d = [d for c, s_, src, d in con.execute("select country, sector, source, collection_date from prices where price>0 and source!='wayback-doordash' and collection_date is not null") if c in _pn and (c, src) not in Qs and (s_ or "").lower() in ("chain", "independent")]
dmin, dmax = min(_d), max(_d)
srcs = {cc: con.execute("select source from monthly_cpi where country_code=? limit 1", (cc,)).fetchone()[0] for cc in ["SG", "ID", "TH", "AU", "US", "GB", "MY", "IN"]}
ok = all("World Bank" in srcs[c] and "annual" in srcs[c] for c in ("SG", "ID", "TH")) and "quarterly" in srcs["AU"] and all("monthly" in srcs[c] for c in ("US", "GB", "MY", "IN"))
rec("A13 CPI classes in new Analysis sentence", ok and "Singapore, Indonesia and Thailand rely on annually-interpolated World Bank CPI, and Australia on quarterly-interpolated CPI" in TEXT, f"monthly_cpi.source: {srcs}")
ib = open(f"{REPO}/index_builder.py").read()
rec("A14 cap = 300 rows per (country, year_month)", re.search(r"MAX_ROWS_PER_COUNTRY\s*=\s*300", ib) and 'groupby(["country", "year_month"]' in ib and "capped at 300 rows per (country, year_month)" in TEXT, "index_builder.py:37 MAX_ROWS_PER_COUNTRY=300; groupby(['country','year_month'])")

# ============ B. CLAIMS ============
must = ["not a validated finding", "suggestive rather than confirmatory", "not as one demonstrated to be distinguishable from chance",
        "most favourable defensible accounting rather than a conservative one", "not pre-registered", "has not been re-verified under the calendar-true specification",
        "unconditional ÷100 of GrabFood’s priceInMinorUnit", "digit-fusion in archived price objects", "300 rows per (country, year_month)", "MenuPages US menu directory",
        "Before any Wayback sweep, a Phase 0 probe", "a sample-size limit rather than an exclusion by CPI type", "publicly available"]
mustnot = ["thousands-grouping", "chain sites", "capped per source", "reliant on interpolated", "five other", "five panel", "collapses", "consistent with delivery-platform",
           "open-source", "open source", "open, auditable", "informal", "Before scraping any source", "excluded from formal testing"]
miss = [m for m in must if m not in TEXT]; bad = [m for m in mustnot if m.lower() in ALL.lower()]
rec("B1 required hedges/accurate phrasing present", not miss, "all present" if not miss else f"MISSING: {miss}")
rec("B2 known-bad phrasings absent", not bad, "none found" if not bad else f"FOUND: {bad}")
dd = re.search(r"Delivery-platform data from DoorDash.*?not tested here\.", TEXT, re.S)
rec("B3 DoorDash sentence: decision + direction + spec caveat, no tested-mechanism claim", bool(dd) and "AIC-selected VAR" in dd.group(0) and "not been re-verified" in dd.group(0) and not re.search(r"\d\.\d+ to \d|F from|consistent with", dd.group(0)), dd.group(0) if dd else "sentence not found")
ab = next(s for s in P if s.startswith("Abstract"))
rec("B4 abstract <=150 words", len(ab.split()) <= 150, f"{len(ab.split())} words (incl. 'Abstract')")
mt = re.search(r"Three tests meet.*?chance\.", TEXT, re.S).group(0)
rec("B5 multiple-testing sentence carries all three hedges", all(k in mt for k in ["no multiplicity correction", "not pre-registered", "most favourable defensible accounting", "would raise it"]), mt[:0] + "no correction; not pre-registered; 'most favourable defensible accounting'; 'would raise it'")
pap = open(PAPER, encoding="utf-8").read()
diff = subprocess.run(["git", "-C", REPO, "diff", "--numstat", "--", "paper_draft/UICPI_A_Method_for_Collecting_Chain_and_Independent.md"], capture_output=True, text=True).stdout.split()
rec("B6 full paper: VN mechanism fixed, stale cause gone", "dot-grouped-thousands" not in pap and pap.count("unconditionally divides GrabFood's `priceInMinorUnit` by 100") == 1 and "unconditional ÷100 of GrabFood's `priceInMinorUnit`" in pap, f"paper has the corrected mechanism in §4.7 and the §6.3 row; 'dot-grouped-thousands' occurrences: {pap.count('dot-grouped-thousands')}")

# ============ C. EXPANDED GREP ============
pats = {"UIFPI": r"UIFPI", "10 countries / ten-country": r"\b10[ -]countr|ten[ -]countr", "informal": r"informal", "Uniform": r"Uniform", "F=6.03/p=0.021": r"6\.03|0\.021|6\.0336",
        "placeholders": r"TODO|FLAG|TBD|XXX|\?\?\?|lorem|placeholder", "stale venue/author/email": r"LNCS|IRC-SET|SSEF|seanerwenhan", "bracketed placeholder": r"\[[A-Za-z]",
        "'validated' w/o negation": r"(?<!not a )validated", "'significan*' bare": r"significan\w*"}
c_ok = True; c_ev = []
for k, p in pats.items():
    h = re.findall(p, ALL, re.I)
    if k == "'significan*' bare": good = all("significance is assessed" in TEXT for _ in h) and len(h) == 1
    elif k == "'validated' w/o negation": good = not h
    else: good = not h
    c_ok &= good; c_ev.append(f"{k}: {len(h)}")
rec("C1 expanded grep (zero forbidden hits)", c_ok, "; ".join(c_ev) + "  ('significance' x1 = 'significance is assessed via...')")
rec("C2 'Unified' (not 'Uniform') Independent-Chain", "Unified Independent-Chain Price Index" in TEXT, "present")

# ============ D. METADATA / HIDDEN ============
hid = {n: sum(len(re.findall(p, z.read(n).decode(errors="ignore"))) for p in (r"<w:vanish", r"<w:ins ", r"<w:del ", r"commentRangeStart", r"<w:comment ", r"<w:highlight")) for n in z.namelist() if n.endswith(".xml")}
rec("D1 no tracked changes / comments / hidden text", not any(hid.values()), "all XML parts clean")
png = [n for n in z.namelist() if n.endswith(".png")][0]; b = z.read(png); i = 8; chunks = []
while i < len(b):
    ln, = struct.unpack(">I", b[i:i + 4]); t = b[i + 4:i + 8].decode("latin1")
    if t in ("tEXt", "iTXt", "zTXt"): chunks.append(b[i + 8:i + 8 + ln][:70])
    i += 12 + ln
rec("D2 PNG metadata has no stale title/description", all(b"Software" in c for c in chunks), f"{chunks}")
creator = re.search(r"<dc:creator>(.*?)</dc:creator>", CORE).group(1); title = re.search(r"<dc:title>(.*?)</dc:title>", CORE)

# ============ F. TEMPLATE DIFF ============
tz = zipfile.ZipFile(TPL); TD = tz.read("word/document.xml").decode(); TF = tz.read("word/footnotes.xml").decode(); TN = tz.read("word/numbering.xml").decode(); TS = tz.read("word/styles.xml").decode()
def sect(x):
    s = re.search(r"<w:sectPr.*?</w:sectPr>", x, re.S).group(0)
    m = dict(re.findall(r'w:(\w+)="([^"]*)"', re.search(r"<w:pgMar[^>]*>", s).group(0)))
    sz = dict(re.findall(r'w:(\w+)="([^"]*)"', re.search(r"<w:pgSz[^>]*>", s).group(0)))
    return m, sz, s
tm, tsz, ts_ = sect(TD); om, osz, os_ = sect(D)
keys = ["top", "bottom", "left", "right", "header", "footer"]
rec("F1 page size + margins + header/footer distance", all(tm[k] == om[k] for k in keys) and tsz["w"] == osz["w"] and tsz["h"] == osz["h"], f"template {[tm[k] for k in keys]} == docx {[om[k] for k in keys]}; page {tsz['w']}x{tsz['h']}")
tw = int(re.search(r'<w:col w:space="288" w:w="(\d+)"', ts_).group(1)); avail = int(osz["w"]) - int(om["left"]) - int(om["right"]); ocols = re.search(r'<w:cols w:space="(\d+)" w:num="(\d+)"', os_)
rec("F2 two columns, equal width & gap", ocols.group(2) == "2" and ocols.group(1) == "288" and (avail - 288) // 2 == tw, f"template 2 x {tw} twips gap 288; docx 2 cols gap {ocols.group(1)} -> {(avail-288)//2} each")
def spec(p):
    g = lambda pat, d="-": (re.search(pat, p).group(1) if re.search(pat, p) else d)
    return dict(jc=g(r'<w:jc w:val="(\w+)"'), before=g(r'w:before="(\d+)"'), after=g(r'w:after="(\d+)"'), line=g(r'w:line="([\d.]+)"'), first=g(r'w:firstLine="(\d+)"'),
                sz=sorted(set(re.findall(r'<w:sz w:val="(\d+)"', p)))[-1:] , keep=bool(re.search(r'<w:keepNext w:val="1"|<w:keepNext/>', p)), sc=bool(re.search(r'<w:smallCaps w:val="1"|<w:smallCaps/>', p)),
                bold=bool(re.search(r'<w:b w:val="1"|<w:b/>', p)))
def find(x, pref): return next(p for p in re.findall(r"<w:p[ >].*?</w:p>", x, re.S) if tx(p).startswith(pref))
def cmp(name, tp, op, keys):
    a, b = spec(tp), spec(op); diffs = {k: (a[k], b[k]) for k in keys if a[k] != b[k]}
    rec(name, not diffs, f"matched on {keys}" if not diffs else f"DIFFERENCES (template, docx): {diffs}")
cmp("F3 abstract run-in paragraph", find(TD, "Abstract—"), find(D, "Abstract—"), ["jc", "before", "after", "line", "first"])
cmp("F4 body paragraph", find(TD, "Headings may be used"), find(D, "We assembled"), ["jc", "before", "after", "line", "first", "sz"])
tt = re.search(r'w:styleId="Title".*?</w:style>', TS, re.S).group(0)
rec("F5 title = template Title style (16pt, bold, centered, before 360)", 'w:jc w:val="center"' in tt and spec(find(D, "UICPI: A Method"))["jc"] == "center" and 'w:sz w:val="32"' in tt and '<w:b w:val="1"/>' in tt and 'w:before="360"' in tt and spec(find(D, "UICPI: A Method"))["sz"] == ["32"] and spec(find(D, "UICPI: A Method"))["bold"] and spec(find(D, "UICPI: A Method"))["before"] == "360", "template Title style sz32 bold before360 == docx")
cmp("F6 author line", find(TD, "First A. Author"), find(D, "Wen Chen"), ["jc", "before", "after", "line", "sz", "bold"])
cmp("F7 Acknowledgment/Acknowledgements heading", find(TD, "Acknowledgment"), find(D, "Acknowledgements"), ["jc", "before", "after", "line", "sz", "keep", "sc", "bold"])
cmp("F8 References heading", find(TD, "References"), find(D, "References"), ["jc", "before", "after", "line", "sz", "keep", "sc", "bold"])
h1s = re.search(r'w:styleId="Heading1".*?</w:style>', TS, re.S).group(0); h2s = re.search(r'w:styleId="Heading2".*?</w:style>', TS, re.S).group(0)
m1, m2 = spec(find(D, "I. Methods")), spec(find(D, "Data Collection"))
rec("F9 H1 (I./II.) = template Heading1 (center, smallCaps, before240/after80, keepNext, unbolded)", 'smallCaps w:val="1"' in h1s and 'w:jc w:val="center"' in h1s and m1["jc"] == "center" and m1["sc"] and m1["before"] == "240" and m1["after"] == "80" and m1["keep"] and not m1["bold"], f"docx {m1}")
rec("F10 H2 sub-heads = template Heading2 (italic, indent 144, before120/after60, keepNext)", '<w:i w:val="1"/>' in h2s and 'w:left="144"' in h2s and m2["before"] == "120" and m2["after"] == "60" and m2["keep"] and 'w:left="144"' in find(D, "Data Collection"), f"docx {m2}")
tfp = [p for p in re.findall(r"<w:p[ >].*?</w:p>", TF, re.S) if tx(p).startswith("F. A. Author")][0]; ofp = re.search(r'<w:footnote [^>]*w:id="1".*?</w:footnote>', FN, re.S).group(0)
cmp("F11 footnote paragraph (justified, firstLine 202, single, 8pt)", tfp, ofp, ["jc", "line", "first", "sz"])
tl = re.search(r'<w:abstractNum w:abstractNumId="2".*?<w:numFmt w:val="(\w+)"/><w:lvlText w:val="([^"]+)"/><w:lvlJc w:val="(\w+)"/><w:pPr><w:ind w:left="(\d+)" w:hanging="(\d+)"', TN, re.S).groups()
rp = find(D, "A. Cavallo"); num = re.search(r'<w:numId w:val="(\d+)"', rp).group(1)
absid = re.search(r'<w:num w:numId="%s"[^>]*>\s*<w:abstractNumId w:val="(\d+)"' % num, NU, re.S).group(1)
ol = re.search(r'<w:abstractNum w:abstractNumId="%s".*?<w:numFmt w:val="(\w+)"/>\s*<w:lvlText w:val="([^"]+)"/>\s*<w:lvlJc w:val="(\w+)"/>\s*<w:pPr><w:ind w:left="(\d+)" w:hanging="(\d+)"' % absid, NU, re.S).groups()
rec("F12 references: real auto-numbered [%1] list, decimal, hanging 360, 8pt", tl == ol and spec(rp)["sz"] == ["16"] and "A. Cavallo" in tx(rp) and not tx(rp).startswith("["), f"template numFmt/lvlText/jc/left/hanging = {tl}; docx = {ol}; ref run sz={spec(rp)['sz']}; typed '[1]' in text: {tx(rp).startswith('[')}")
cap = spec(find(D, "Figure 1.")); tcap = spec(find(TD, "Example of a figure caption"))
rec("F13 figure caption: 'Figure 1.', 8pt, centered, below image", cap["sz"] == ["16"] and cap["jc"] == "center" and tcap["sz"] == ["16"] and tcap["jc"] == "center" and P[[i for i, s in enumerate(P) if s.startswith("Figure 1.")][0]].startswith("Figure 1."), f"template {tcap['sz']}/{tcap['jc']} docx {cap['sz']}/{cap['jc']}")
order = [("IMG" if "<w:drawing" in p else tx(p)[:9]) for p in PARAS if ("<w:drawing" in p or tx(p))]; k = order.index("IMG")
rec("F14 caption placed immediately below the figure", order[k + 1] == "Figure 1.", f"sequence: [{order[k-1]}] -> [IMG] -> [{order[k+1]}]")
fonts = set(re.findall(r'w:ascii="([^"]+)"', D + FN + ST + NU))
rec("F15 fonts: Times New Roman only", fonts == {"Times New Roman"}, str(fonts))
# figure geometry
pw = int(re.search(r'<wp:extent cx="(\d+)"', D).group(1)) / 914400; pxw, pxh = struct.unpack(">II", b[16:24])
rec("F16 figure fits column and is placed 1:1 (8pt stays 8pt)", pw <= (avail - 288) // 2 / 1440 and abs(pw / (pxw / 400) - 1) < 0.01, f"placed {pw:.3f}in in a {((avail-288)//2)/1440:.3f}in column; native {pxw/400:.3f}in @400dpi -> scale {pw/(pxw/400):.3f}")
# template: "Insert figures ... after they are cited in the text. Use the abbreviation 'Fig. 1,' even at the beginning of a sentence."
_seq = [("IMG" if "<w:drawing" in p else tx(p)) for p in PARAS if ("<w:drawing" in p or tx(p))]; _ki = _seq.index("IMG")
_cited = [i for i, s in enumerate(_seq[:_ki]) if "Fig. 1" in s]
_spelled = [s[:40] for s in _seq if s != "IMG" and not s.startswith("Figure 1.") and "Figure 1" in s]
rec("F17 figure cited in text as 'Fig. 1' before it appears; no spelled-out 'Figure 1' outside the caption", bool(_cited) and not _spelled, f"first citation in paragraph {_cited[0] + 1 if _cited else None}, figure at paragraph {_ki + 1}; spelled-out uses outside caption: {_spelled}")

# word counts
ri = P.index("References"); ci = next(i for i, s in enumerate(P) if s.startswith("Figure 1."))
res.append(("W  word counts", "INFO", f"total {len(' '.join(P).split())}; excl. References+caption {len(' '.join(s for i,s in enumerate(P) if i<ri and i!=ci).split())}; abstract {len(ab.split())}"))


# ============ ROUND 3: observation count, both files, PDF, metadata, AU / validated fixes ============
import subprocess as _sp
rows = []
for l in pap.split("\n"):
    m = re.match(r"\|\s*([A-Za-z ]+?)\s*\|.*?\|\s*(?:item-level|restaurant-aggregate|item-level \(sparse\))\s*\|\s*([\d,]+)\s*\|\s*(\d+)\s*\|", l)
    if m and m.group(1) != "Country": rows.append((m.group(1), int(m.group(2).replace(",", ""))))
tsum = sum(r[1] for r in rows)
BK = f"{DBDIR}/uifpi.db.backup_pre_my_zero_delete_20260619_085250"
if os.path.exists(BK):
    bk = sqlite3.connect(f"file:{BK}?immutable=1", uri=True)
    bc = {}
    for c, n in bk.execute("select country, count(*) from prices where price>0 and (country in ('Singapore','Malaysia','United Kingdom','India','Indonesia','Australia','Thailand') or (country='United States' and source='wayback-menupages')) group by country"): bc[c] = n
    bdates = [d for (d,) in bk.execute("select collection_date from prices where price>0 and collection_date is not null and (country in ('Singapore','Malaysia','United Kingdom','India','Indonesia','Australia','Thailand') or (country='United States' and source='wayback-menupages'))")]
    rec("A12 observation count: full paper's own table sum", tsum == 48730 and len(rows) == 8, f"parsed {len(rows)} table rows from full paper §5.1: {dict(rows)} -> sum {tsum:,}")
    rec("A12b table reproduces exactly from the dated 2026-06-19 DB backup", all(bc.get(c) == n for c, n in rows) and sum(bc.values()) == tsum, f"backup_pre_my_zero_delete_20260619_085250: per-country rows == table for {sum(1 for c,n in rows if bc.get(c)==n)}/8; total {sum(bc.values()):,} (US = wayback-menupages only, as the table's source column says)")
    rec("A12c date range 2018 to June 2026 (snapshot rows)", min(bdates).startswith("2018") and max(bdates) <= "2026-06-19" and max(bdates).startswith("2026-06"), f"snapshot rows span {min(bdates)}..{max(bdates)}; docx says '2018–June 2026'")
else:
    skip("A12b/A12c observation count vs 2026-06-19 backup", f"backup not found: {BK}")
rec("A12d docx count/stamp: 48,730 x2, 41,263 gone, snapshot stamp present", TEXT.count("48,730") == 2 and "41,263" not in ALL and "(snapshot of 2026-06-19)" in TEXT and "2018–June 2026" in TEXT, f"48,730 x{TEXT.count('48,730')}; 41,263 x{ALL.count('41,263')}")
rec("A12e full paper count: 48,730 x4 date-stamped, 41,263 gone", pap.count("48,730") == 4 and "41,263" not in pap and pap.count("2026-06-19") >= 4, f"48,730 x{pap.count('48,730')}; 41,263 x{pap.count('41,263')}; '2026-06-19' x{pap.count('2026-06-19')}")
wc = len(" ".join(l for l in pap.split("\n")[11:17] if l.strip() and not l.startswith("#")).replace("**", "").replace("*", "").split())
rec("A12f full-paper abstract 'Word count' label matches actual", f"*Word count: {wc}*" in pap, f"actual {wc}; label {re.search(r'Word count: (\d+)', pap).group(1)}")
rec("B7 open-source claim gone from BOTH files (no LICENSE exists)", not re.search(r"open[- ]source|existing licen[cs]e", pap + "\n" + ALL, re.I) and TEXT.count("publicly available") == 3 and pap.count("publicly available") >= 5 and not [f for f in os.listdir(REPO) if f.upper().startswith(("LICENSE", "COPYING"))], f"docx 'publicly available' x{TEXT.count('publicly available')}; paper x{pap.count('publicly available')}; LICENSE file present: {[f for f in os.listdir(REPO) if f.upper().startswith(('LICENSE','COPYING'))]}")
rec("B8 Australia removed from replication framing (docx + full paper)", "United Kingdom — the only country on real monthly CPI still below the 24-month threshold — crosses it" in TEXT and "and Australia cross" not in TEXT and "Replication in the UK" in pap and "AU and UK crossing" not in pap and "Replication in AU and UK" not in pap and "would not meet the family's real-monthly-CPI condition" in pap, "docx: UK only; paper §8.1 + §8.9 UK only, AU/SG/ID/TH stated as interpolated-CPI (not clean-test) cases")
rec("B9 full paper: 'validated' contradictions removed", "one validated Granger result" not in pap and "validates the pipeline" not in pap and "method validation" not in pap and "not a validated Granger result" not in pap and "one numerically interesting but not validated Granger result" in pap, "§2 'one validated result', §2 'validates the pipeline', §6.1 heading 'method validation' -> hedged")
pt = _sp.run(["pdftotext", f"{REPO}/paper_draft/UICPI_A_Method_for_Collecting_Chain_and_Independent.pdf", "-"], capture_output=True, text=True).stdout; pf = re.sub(r"\s+", " ", pt)
pi = _sp.run(["pdfinfo", f"{REPO}/paper_draft/UICPI_A_Method_for_Collecting_Chain_and_Independent.pdf"], capture_output=True, text=True).stdout
rec("B10 full-paper PDF regenerated: matches corrected .md", "41,263" not in pf and pf.count("48,730") == 4 and not re.search(r"open[- ]source|dot-grouped-thousands|Replication in AU and UK|one validated Granger", pf, re.I) and "unconditionally divides GrabFood" in pf and "Replication in the UK" in pf and f"Word count: {re.search(r'Word count: (\d+)', pap).group(1)}" in pf, f"PDF: {re.search(r'Pages:\s+(\d+)', pi).group(1)} pages, {re.search(r'Page size:\s+(.*)', pi).group(1).strip()}; 48,730 x{pf.count('48,730')}, 41,263 x{pf.count('41,263')}")
core_names = re.findall(r"<dc:creator>(.*?)</dc:creator>|<cp:lastModifiedBy>(.*?)</cp:lastModifiedBy>", CORE)
rec("D3 metadata generic/blank (blind-safe): no author name, email, or title in properties", "Wen" not in CORE + APP and "wcerbiz" not in CORE + APP and "<dc:title>" not in CORE and "Er " not in CORE, f"creator/lastModifiedBy = {[x for t in core_names for x in t if x]} (docx-js default), no dc:title. NOTE: the byline + footnote in the body carry the name/email, as the CJSJ template requires")


# ============ E. RENDER (LibreOffice only; Word is NOT tested) ============
import shutil, tempfile
_so = shutil.which("soffice")
if _so:
    with tempfile.TemporaryDirectory() as _td:
        _sp.run([_so, "--headless", "--convert-to", "pdf", DOCX, "--outdir", _td], capture_output=True, timeout=240)
        _pdf = os.path.join(_td, os.path.splitext(os.path.basename(DOCX))[0] + ".pdf")
        _info = _sp.run(["pdfinfo", _pdf], capture_output=True, text=True).stdout if os.path.exists(_pdf) else ""
        _pg = re.search(r"Pages:\s+(\d+)", _info); _sz = re.search(r"Page size:\s+(.*)", _info)
        rec("E1 renders to 2 pages, US Letter (LibreOffice; NOT Word)", bool(_pg) and _pg.group(1) == "2" and "letter" in _sz.group(1), f"{_pg.group(1) if _pg else '?'} pages, {_sz.group(1).strip() if _sz else '?'}")
else:
    skip("E1 render page count", "soffice not on PATH")

for i, st, ev in res:
    print(f"{st:5s} {i}\n        {ev}")
print("\nSUMMARY:", {s: sum(1 for _, x, _ in res if x == s) for s in ("PASS", "FAIL", "HELD", "ADVISORY", "SKIP", "INFO")})
sys.exit(1 if any(x == "FAIL" for _, x, _ in res) else 0)

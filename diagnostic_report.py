"""
UIFPI Project Diagnostic — generates diagnostic_report_v3.txt
Run after all pipeline scripts to check overall data quality.
"""

import json
import os
import sqlite3
from datetime import date

DB_PATH = "uifpi.db"
OUT_FILE = "diagnostic_report_v3.txt"

COUNTRY_100_THRESHOLD = 100
REQUIRED_SCRIPTS = [
    "live_scraper.py", "historical_scraper.py", "nlp_pipeline.py",
    "index_builder.py", "granger_analysis.py", "dashboard_data.py",
    "migrate_db.py", "run_all.py", "requirements.txt", "balance_check.py",
]


def check(label, passed, detail=""):
    sym = "✓" if passed else "✗"
    line = f"  {sym}  {label}"
    if detail:
        line += f"  ({detail})"
    return line, passed


def run():
    lines = []
    checks = []

    def w(s=""):
        lines.append(s)

    w("=" * 80)
    w(f"UIFPI PROJECT DIAGNOSTIC REPORT — VERSION 3")
    w(f"Date: {date.today()}")
    w("=" * 80)

    # ── DATABASE ──────────────────────────────────────────────────────────────
    w()
    w("━" * 80)
    w("DATABASE CHECKS (uifpi.db)")
    w("━" * 80)
    w()

    conn = sqlite3.connect(DB_PATH)

    # Total rows
    total = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    c, p = check(f"prices table — total rows: {total:,}", total > 0)
    w(c); checks.append(p)

    # Per-country
    w()
    w("   ROWS PER COUNTRY:")
    rows_by_country = conn.execute(
        "SELECT country, COUNT(*) FROM prices GROUP BY country ORDER BY COUNT(*) DESC"
    ).fetchall()
    country_counts = dict(rows_by_country)
    expected_countries = [
        "Singapore", "Malaysia", "Indonesia", "Thailand", "India",
        "United States", "United Kingdom", "Australia",
    ]
    for cc in expected_countries:
        n = country_counts.get(cc, 0)
        ok = n >= COUNTRY_100_THRESHOLD
        sym = "✓" if ok else "✗"
        flag = "" if ok else f"  ← UNDER {COUNTRY_100_THRESHOLD}"
        w(f"   {sym}  {cc:<22} {n:>5} rows{flag}")
        checks.append(ok)

    # Sector breakdown
    w()
    w("   ROWS PER SECTOR:")
    for sector, n in conn.execute(
        "SELECT sector, COUNT(*) FROM prices GROUP BY sector"
    ).fetchall():
        w(f"   ✓  {sector:<12} {n:>6}")

    # Date range
    earliest, latest = conn.execute(
        "SELECT MIN(collection_date), MAX(collection_date) FROM prices"
    ).fetchone()
    w()
    c, p = check(f"Date range: {earliest} → {latest}", bool(earliest and latest))
    w(c); checks.append(p)

    # price_usd coverage
    usd_ok = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE price_usd IS NOT NULL AND price_usd > 0"
    ).fetchone()[0]
    usd_pct = 100 * usd_ok / total if total else 0
    c, p = check(
        f"price_usd populated: {usd_ok:,} of {total:,} rows ({usd_pct:.1f}%)",
        usd_pct >= 99
    )
    w(c); checks.append(p)

    # Null prices
    null_prices = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE price IS NULL OR price <= 0"
    ).fetchone()[0]
    c, p = check(f"NULL/zero prices: {null_prices}", null_prices == 0)
    w(c); checks.append(p)

    # Out-of-range
    oor = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE price_usd < 0.01 OR price_usd > 10000"
    ).fetchone()[0]
    c, p = check(f"Out-of-range price_usd (<0.01 or >10k): {oor}", oor == 0)
    w(c); checks.append(p)

    # nlp_results
    w()
    nlp_total = conn.execute("SELECT COUNT(*) FROM nlp_results").fetchone()[0]
    c, p = check(f"nlp_results populated: {nlp_total:,} rows", nlp_total > 0)
    w(c); checks.append(p)

    nlp_high = conn.execute(
        "SELECT COUNT(*) FROM nlp_results WHERE confidence > 0.85"
    ).fetchone()[0]
    nlp_pct = 100 * nlp_high / nlp_total if nlp_total else 0
    c, p = check(
        f"NLP confidence >0.85: {nlp_high:,}/{nlp_total:,} ({nlp_pct:.1f}%)",
        nlp_pct > 0,
        "need API key with credits to exceed 0.85"
    )
    w(c); checks.append(p)

    # NLP breakdown
    w()
    w("   NLP CATEGORY BREAKDOWN:")
    for cat, n in conn.execute(
        "SELECT category, COUNT(*) FROM nlp_results GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall():
        w(f"      {cat:<22} {n:>5}")

    # uifpi_index
    w()
    idx_total = conn.execute("SELECT COUNT(*) FROM uifpi_index").fetchone()[0]
    c, p = check(f"uifpi_index rows: {idx_total}", idx_total > 0)
    w(c); checks.append(p)

    idx_countries = conn.execute(
        "SELECT COUNT(DISTINCT country) FROM uifpi_index"
    ).fetchone()[0]
    c, p = check(f"uifpi_index countries: {idx_countries}", idx_countries >= 7)
    w(c); checks.append(p)

    conn.close()

    # ── FILE CHECKS ───────────────────────────────────────────────────────────
    w()
    w("━" * 80)
    w("FILE CHECKS")
    w("━" * 80)
    w()
    w("   REQUIRED SCRIPTS:")
    for script in REQUIRED_SCRIPTS:
        exists = os.path.exists(script)
        c, p = check(script, exists)
        w(c); checks.append(p)

    # CPI data
    cpi_files = [f for f in os.listdir("cpi_data") if f.endswith(".json")] if os.path.isdir("cpi_data") else []
    c, p = check(f"cpi_data/ — {len(cpi_files)} JSON files", len(cpi_files) >= 8)
    w(c); checks.append(p)

    c, p = check("analysis_results/ folder exists", os.path.isdir("analysis_results"))
    w(c); checks.append(p)

    granger_exists = os.path.exists("analysis_results/granger_results.json")
    granger_populated = False
    if granger_exists:
        with open("analysis_results/granger_results.json") as f:
            gd = json.load(f)
        granger_populated = len(gd) > 0
    c, p = check(f"granger_results.json — {len(gd) if granger_exists else 0} country entries",
                 granger_populated)
    w(c); checks.append(p)

    csv_lines = 0
    if os.path.exists("uifpi_index.csv"):
        with open("uifpi_index.csv") as f:
            csv_lines = sum(1 for _ in f) - 1  # minus header
    c, p = check(f"uifpi_index.csv — {csv_lines} data rows", csv_lines > 0)
    w(c); checks.append(p)

    # Dashboard JSON
    w()
    w("   DASHBOARD JSON:")
    for fname in ["index_series.json", "country_summary.json", "latest_values.json"]:
        path = os.path.join("dashboard", "public", "data", fname)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        c, p = check(f"{fname} ({size:,} bytes)", exists and size > 0)
        w(c); checks.append(p)

    # ── GRANGER SUMMARY ───────────────────────────────────────────────────────
    w()
    w("━" * 80)
    w("GRANGER CAUSALITY SUMMARY")
    w("━" * 80)
    w()
    if granger_exists and gd:
        w(f"  {'Country':<22} {'n_obs':>6} {'p-value':>10} {'Lead':>6} {'Sig':>5}  Note")
        w(f"  {'─'*70}")
        for country, r in sorted(gd.items()):
            n = r.get("n_obs", 0)
            gp = f"{r['granger_p_value']:.3f}" if r.get("granger_p_value") is not None else "—"
            lead = str(r.get("lead_months", "—"))
            sig = "✓" if r.get("granger_significant") else "✗"
            note = r.get("note", "")[:30]
            w(f"  {country:<22} {n:>6} {gp:>10} {lead:>6} {sig:>5}  {note}")
        n_sig = sum(1 for r in gd.values() if r.get("granger_significant"))
        w()
        c, p = check(f"Granger significant: {n_sig}/{len(gd)} countries", n_sig > 0)
        w(c); checks.append(p)
        # Best p-value
        best_p = min((r.get("granger_p_value") or 1.0) for r in gd.values())
        best_country = min(gd.items(), key=lambda x: x[1].get("granger_p_value") or 1.0)[0]
        c, p = check(
            f"Best Granger p-value: {best_p:.3f} ({best_country})",
            best_p < 0.15
        )
        w(c); checks.append(p)
    else:
        w("  ✗  No Granger results found")
        checks.append(False)

    # ── SUMMARY TABLE ─────────────────────────────────────────────────────────
    w()
    w("━" * 80)
    w("SUMMARY TABLE")
    w("━" * 80)
    w()
    total_checks = len(checks)
    passed_checks = sum(checks)
    w(f"  Passed: {passed_checks}/{total_checks} checks")
    w()

    verdict = "READY" if passed_checks / total_checks >= 0.85 else "NOT READY"
    w(f"  VERDICT: {'*** ' if verdict == 'NOT READY' else ''}{verdict}")
    w()
    w("=" * 80)
    w("END OF REPORT")
    w("=" * 80)

    report = "\n".join(lines)
    with open(OUT_FILE, "w") as f:
        f.write(report)
    print(report)
    print(f"\n✓ Saved to {OUT_FILE}")


if __name__ == "__main__":
    run()

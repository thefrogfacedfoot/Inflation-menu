"""
UIFPI — NLP Validation Tool
Creates a random sample for manual review and, after the researcher has
filled in the manual_category column, calculates accuracy metrics.

Usage:
    python3 validate_nlp.py export              # Export 100-item sample CSV
    python3 validate_nlp.py evaluate            # Evaluate after manual review
    python3 validate_nlp.py evaluate path.csv   # Evaluate a specific CSV
"""

import csv
import json
import os
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import date

DB_PATH = "uifpi.db"
SAMPLE_CSV = "validation_sample.csv"
RESULTS_DIR = "validation_results"
SAMPLE_SIZE = 100
ACCURACY_THRESHOLD = 0.85

VALID_CATEGORIES = [
    "GRILLED_PROTEIN", "NOODLE_DISH", "RICE_DISH", "SOUP_STEW",
    "DIM_SUM_DUMPLING", "BREAD_PASTRY", "BEVERAGE", "DESSERT",
    "FAST_FOOD", "SEAFOOD_DISH", "SALAD_VEGETABLE", "SNACK_SIDE",
    "SET_MEAL", "OTHER",
]


# ── Export ────────────────────────────────────────────────────────────────────

def export_sample(db_path: str = DB_PATH, out_path: str = SAMPLE_CSV,
                  n: int = SAMPLE_SIZE) -> None:
    """
    Draw a stratified random sample of n items from nlp_results (balanced
    across countries where possible) and write to CSV for manual review.
    Prints all items to terminal so the researcher can inspect them inline.
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT item_name, country, category, quality_signals, language_detected,
               restaurant_name
        FROM nlp_results
        ORDER BY RANDOM()
    """).fetchall()
    conn.close()

    if not rows:
        print("✗  nlp_results table is empty — run nlp_pipeline.py first.")
        return

    # Stratify by country then random-sample within each stratum
    by_country: dict = defaultdict(list)
    for row in rows:
        by_country[row[1]].append(row)

    countries = list(by_country.keys())
    per_country = max(1, n // len(countries))
    sample = []
    for c in countries:
        pool = by_country[c]
        sample.extend(random.sample(pool, min(per_country, len(pool))))

    # Top up to n if needed
    remaining_pool = [r for r in rows if r not in sample]
    random.shuffle(remaining_pool)
    sample.extend(remaining_pool[:max(0, n - len(sample))])
    sample = sample[:n]

    # Write CSV
    fieldnames = [
        "item_name", "restaurant_name", "country",
        "assigned_category", "quality_signals", "language_detected",
        "manual_category",   # researcher fills this in
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (item, country, cat, qs, lang, rest) in sample:
            writer.writerow({
                "item_name":         item,
                "restaurant_name":   rest,
                "country":           country,
                "assigned_category": cat,
                "quality_signals":   qs or "[]",
                "language_detected": lang,
                "manual_category":   "",   # blank — researcher fills this in
            })

    # Print to terminal for inline review
    print(f"\n{'='*70}")
    print(f"Validation sample — {len(sample)} items")
    print(f"{'='*70}")
    print(f"{'#':<4} {'Item':<45} {'Country':<12} {'Assigned':<22} {'Lang'}")
    print("-" * 70)
    for idx, (item, country, cat, qs, lang, rest) in enumerate(sample, 1):
        print(f"{idx:<4} {item[:44]:<45} {(country or '')[:11]:<12} "
              f"{(cat or '')[:21]:<22} {lang}")

    print(f"\n✓  Written to {out_path}")
    print("\nNext step:")
    print("  1. Open validation_sample.csv in a spreadsheet or text editor.")
    print("  2. For each row, fill in 'manual_category' with the correct category.")
    print("     Valid categories:", ", ".join(VALID_CATEGORIES))
    print("  3. Save and run:  python3 validate_nlp.py evaluate")


# ── Evaluate ──────────────────────────────────────────────────────────────────

def calculate_accuracy(csv_path: str = SAMPLE_CSV) -> None:
    """
    Read back the validation CSV (with manual_category filled in) and compute:
    - Overall accuracy
    - Confusion matrix by category
    - Accuracy by language
    - Accuracy by country
    Saves a JSON report and prints a summary.
    """
    if not os.path.exists(csv_path):
        print(f"✗  File not found: {csv_path}")
        print("   Run 'python3 validate_nlp.py export' first.")
        return

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Filter to rows where manual_category has been filled in
    reviewed = [r for r in rows if r.get("manual_category", "").strip()]
    if not reviewed:
        print("✗  No rows have a manual_category filled in yet.")
        print("   Open validation_sample.csv, fill in the column, then re-run.")
        return

    total = len(reviewed)
    correct = sum(
        1 for r in reviewed
        if r["assigned_category"].strip() == r["manual_category"].strip()
    )
    accuracy = correct / total

    # Confusion matrix: rows = true (manual), cols = predicted (assigned)
    confusion: dict = defaultdict(lambda: defaultdict(int))
    for r in reviewed:
        true_cat  = r["manual_category"].strip()
        pred_cat  = r["assigned_category"].strip()
        confusion[true_cat][pred_cat] += 1

    # Per-category accuracy
    cat_accuracy: dict = {}
    for cat in VALID_CATEGORIES:
        true_total = sum(confusion[cat].values())
        if true_total == 0:
            continue
        cat_correct = confusion[cat].get(cat, 0)
        cat_accuracy[cat] = round(cat_correct / true_total, 3)

    # Per-language accuracy
    lang_stats: dict = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in reviewed:
        lang = r.get("language_detected", "en")
        lang_stats[lang]["total"] += 1
        if r["assigned_category"].strip() == r["manual_category"].strip():
            lang_stats[lang]["correct"] += 1
    lang_accuracy = {
        lang: round(v["correct"] / v["total"], 3)
        for lang, v in lang_stats.items()
    }

    # Per-country accuracy
    country_stats: dict = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in reviewed:
        c = r.get("country", "Unknown")
        country_stats[c]["total"] += 1
        if r["assigned_category"].strip() == r["manual_category"].strip():
            country_stats[c]["correct"] += 1
    country_accuracy = {
        c: round(v["correct"] / v["total"], 3)
        for c, v in country_stats.items()
    }

    # Weakest categories
    weak_cats = [
        cat for cat, acc in cat_accuracy.items() if acc < ACCURACY_THRESHOLD
    ]

    # Print summary
    print(f"\n{'='*60}")
    print("NLP Accuracy Report")
    print(f"{'='*60}")
    print(f"  Reviewed:    {total}")
    print(f"  Correct:     {correct}")
    print(f"  Accuracy:    {accuracy:.1%}  "
          f"({'✓ above' if accuracy >= ACCURACY_THRESHOLD else '⚠  BELOW'} "
          f"threshold of {ACCURACY_THRESHOLD:.0%})")

    print("\n── Per-category accuracy ─────────────────────────────")
    for cat in VALID_CATEGORIES:
        if cat in cat_accuracy:
            flag = "⚠" if cat_accuracy[cat] < ACCURACY_THRESHOLD else " "
            print(f"  {flag} {cat:<24} {cat_accuracy[cat]:.1%}")

    print("\n── Per-language accuracy ─────────────────────────────")
    for lang, acc in sorted(lang_accuracy.items(), key=lambda x: -x[1]):
        n = lang_stats[lang]["total"]
        print(f"  {lang:<10}  {acc:.1%}  (n={n})")

    print("\n── Per-country accuracy ──────────────────────────────")
    for c, acc in sorted(country_accuracy.items(), key=lambda x: -x[1]):
        n = country_stats[c]["total"]
        print(f"  {c:<22} {acc:.1%}  (n={n})")

    if weak_cats:
        print(f"\n⚠  Weakest categories (below {ACCURACY_THRESHOLD:.0%}):")
        for cat in weak_cats:
            print(f"   - {cat}  ({cat_accuracy[cat]:.1%})")

    # Save report
    os.makedirs(RESULTS_DIR, exist_ok=True)
    report = {
        "date":             date.today().isoformat(),
        "total_reviewed":   total,
        "correct":          correct,
        "overall_accuracy": round(accuracy, 4),
        "threshold":        ACCURACY_THRESHOLD,
        "above_threshold":  accuracy >= ACCURACY_THRESHOLD,
        "per_category":     cat_accuracy,
        "per_language":     lang_accuracy,
        "per_country":      country_accuracy,
        "weak_categories":  weak_cats,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
    }
    report_path = os.path.join(RESULTS_DIR, "accuracy_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n✓  Full report saved to {report_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "export"

    if mode == "export":
        export_sample()
    elif mode == "evaluate":
        csv_path = sys.argv[2] if len(sys.argv) > 2 else SAMPLE_CSV
        calculate_accuracy(csv_path)
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 validate_nlp.py [export|evaluate] [csv_path]")
        sys.exit(1)

"""
UIFPI — Full Pipeline Orchestrator
Runs each stage of the pipeline in order, with clear status output.

Stages:
  1. get_monthly_cpi.py    — download official CPI data
  2. historical_scraper.py — scrape Wayback Machine archives
  3. nlp_pipeline.py       — classify menu items via Claude API
  4. validate_nlp.py       — MANUAL REVIEW PAUSE: export validation sample
  ** Stops here — researcher must fill in manual_category in CSV **
  5. index_builder.py      — build UIFPI index
  6. granger_analysis.py   — Granger causality + pass-through tests
  7. dashboard_data.py     — export JSON for Next.js dashboard

Usage:
    python3 run_all.py                 # Full pipeline (pauses at step 4)
    python3 run_all.py --from-index    # Skip to step 5 (after manual review done)
    python3 run_all.py --dashboard     # Run only steps 6-7
"""

import subprocess
import sys
import time
from datetime import datetime


# ── Stage runner ──────────────────────────────────────────────────────────────

def run_stage(label: str, script: str, args: list[str] = None) -> bool:
    """
    Run one pipeline stage. Returns True on success, False on failure.
    Streams stdout/stderr live so progress is visible.
    """
    cmd = [sys.executable, script] + (args or [])
    width = 60
    print(f"\n{'─' * width}")
    print(f"  STAGE: {label}")
    print(f"  Script: {script}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─' * width}\n")

    t0 = time.time()
    result = subprocess.run(cmd, check=False)
    elapsed = time.time() - t0

    if result.returncode == 0:
        print(f"\n  ✓  {label} completed in {elapsed:.1f}s")
        return True
    else:
        print(f"\n  ✗  {label} FAILED (exit code {result.returncode}) "
              f"after {elapsed:.1f}s")
        return False


def pause_for_manual_review() -> None:
    """Print instructions for the manual validation step and exit cleanly."""
    width = 60
    print(f"\n{'='*width}")
    print("  MANUAL REVIEW REQUIRED")
    print(f"{'='*width}")
    print("""
  The NLP pipeline has exported a validation sample to:
    validation_sample.csv

  Steps:
    1. Open validation_sample.csv in a spreadsheet or text editor.
    2. For each row, fill in the 'manual_category' column with the
       correct category from the list in validate_nlp.py.
    3. Save the file.
    4. Re-run the pipeline from the index stage:
         python3 run_all.py --from-index

  Valid categories:
    GRILLED_PROTEIN, NOODLE_DISH, RICE_DISH, SOUP_STEW,
    DIM_SUM_DUMPLING, BREAD_PASTRY, BEVERAGE, DESSERT,
    FAST_FOOD, SEAFOOD_DISH, SALAD_VEGETABLE, SNACK_SIDE,
    SET_MEAL, OTHER
""")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    from_index  = "--from-index"  in args
    dashboard   = "--dashboard"   in args

    print("=" * 60)
    print("  UIFPI Full Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    failed_stages = []

    if not from_index and not dashboard:
        # Stage 1: CPI download
        ok = run_stage("Download monthly CPI data", "get_monthly_cpi.py")
        if not ok:
            failed_stages.append("get_monthly_cpi.py")
            print("  Continuing despite CPI failure — index will use cached data if any.")

        # Stage 2: Historical scraper
        ok = run_stage("Scrape historical archives (Wayback Machine)", "historical_scraper.py")
        if not ok:
            failed_stages.append("historical_scraper.py")

        # Stage 3: NLP pipeline
        ok = run_stage("Classify menu items (NLP pipeline)", "nlp_pipeline.py")
        if not ok:
            failed_stages.append("nlp_pipeline.py")
            print("  NLP pipeline failed — downstream index build may have incomplete categories.")

        # Stage 4: Export validation sample (manual review gate)
        ok = run_stage("Export NLP validation sample", "validate_nlp.py", ["export"])
        if ok:
            pause_for_manual_review()
            sys.exit(0)
        else:
            failed_stages.append("validate_nlp.py export")
            print("  Validation export failed — proceeding anyway.")

    if from_index or dashboard:
        if from_index:
            # Run validate_nlp evaluate first (checks manual review results)
            ok = run_stage("Evaluate NLP accuracy (post manual review)", "validate_nlp.py", ["evaluate"])
            if not ok:
                print("  Accuracy evaluation failed or no manual review found.")
                print("  Continuing to index build regardless.")
                failed_stages.append("validate_nlp.py evaluate")

    if not dashboard:
        # Stage 5: Index builder
        ok = run_stage("Build UIFPI index", "index_builder.py")
        if not ok:
            failed_stages.append("index_builder.py")
            print("\n  ✗  Index build failed — cannot proceed to Granger analysis.")
            sys.exit(1)

    # Stage 6: Granger analysis
    ok = run_stage("Granger causality + pass-through analysis", "granger_analysis.py")
    if not ok:
        failed_stages.append("granger_analysis.py")

    # Stage 7: Dashboard data export
    ok = run_stage("Export dashboard JSON", "dashboard_data.py")
    if not ok:
        failed_stages.append("dashboard_data.py")

    # Final summary
    print(f"\n{'='*60}")
    print("  Pipeline Complete")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if failed_stages:
        print(f"\n  Stages with errors:")
        for s in failed_stages:
            print(f"    ✗  {s}")
    else:
        print("\n  All stages completed successfully.")

    print(f"\n  Output files:")
    print("    uifpi_index.csv")
    print("    analysis_results/granger_results.json")
    print("    analysis_results/summary.csv")
    print("    dashboard_data/index_series.json")
    print("    dashboard_data/country_summary.json")
    print("    dashboard_data/latest_values.json")
    print(f"{'='*60}\n")

    sys.exit(1 if failed_stages else 0)


if __name__ == "__main__":
    main()

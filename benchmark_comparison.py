"""
UIFPI — Benchmark Comparison
Compares directional prediction accuracy of UIFPI against an AR(1) naive
baseline using available CPI and UIFPI data.

Test set: last 3 annual observations (or 24 months if monthly data available).
Training set: everything prior.

Results saved to analysis_results/benchmark_comparison.json.
"""

import json
import os
import sqlite3
import warnings
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DB_PATH    = "uifpi.db"
CPI_DIR    = "cpi_data"
RESULTS_DIR = "analysis_results"
MIN_TRAIN  = 3   # min training obs
MIN_TEST   = 2   # min test obs

COUNTRY_CPI_FILES = {
    "Singapore":     "monthly_cpi_sg.json",
    "Malaysia":      None,
    "Indonesia":     "monthly_cpi_id.json",
    "Thailand":      "monthly_cpi_th.json",
    "India":         "monthly_cpi_in.json",
    "United States": "monthly_cpi_us.json",
    "United Kingdom":"monthly_cpi_gb.json",
    "Australia":     "monthly_cpi_au.json",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_cpi(country: str) -> Optional[pd.Series]:
    cpi_file = COUNTRY_CPI_FILES.get(country)
    if not cpi_file:
        return None
    path = os.path.join(CPI_DIR, cpi_file)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = json.load(f)
    rows = raw.get("data", [])
    if not rows:
        return None
    s = pd.Series(
        {r["period"]: float(r["cpi"]) for r in rows},
        name="cpi",
    )
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def load_uifpi_annual(country: str) -> Optional[pd.Series]:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT year_month, uifpi_combined FROM uifpi_index "
        "WHERE country = ? ORDER BY year_month",
        conn, params=[country],
    )
    conn.close()
    if df.empty:
        return None
    s = pd.Series(
        df["uifpi_combined"].values,
        index=pd.to_datetime(df["year_month"]),
        name="uifpi",
    )
    # Resample to annual (mean) to align with annual CPI observations
    return s.resample("YS").mean().dropna()


# ---------------------------------------------------------------------------
# Prediction models
# ---------------------------------------------------------------------------

def directional_accuracy(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Fraction of months where predicted direction matches actual direction."""
    actual_dir   = np.sign(np.diff(actual))
    predicted_dir = np.sign(np.diff(predicted))
    if len(actual_dir) == 0:
        return float("nan")
    return float(np.mean(actual_dir == predicted_dir))


def ar1_predict(train: np.ndarray, n_steps: int) -> np.ndarray:
    """AR(1) forecast: next value = last value + mean change."""
    if len(train) < 2:
        return np.full(n_steps, train[-1])
    mean_change = np.mean(np.diff(train))
    preds = []
    last = train[-1]
    for _ in range(n_steps):
        last = last + mean_change
        preds.append(last)
    return np.array(preds)


def uifpi_predict(train_cpi: np.ndarray, train_uifpi: np.ndarray,
                  test_uifpi: np.ndarray) -> Optional[np.ndarray]:
    """Use UIFPI change as a directional signal for CPI."""
    if len(train_cpi) < 2 or len(train_uifpi) < 2:
        return None
    # OLS: Δcpi = α + β * Δuifpi
    d_cpi   = np.diff(train_cpi)
    d_uifpi = np.diff(train_uifpi)
    n = min(len(d_cpi), len(d_uifpi))
    if n < 2:
        return None
    d_cpi_t   = d_cpi[-n:]
    d_uifpi_t = d_uifpi[-n:]
    # OLS via numpy
    X = np.column_stack([np.ones(n), d_uifpi_t])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(X, d_cpi_t, rcond=None)
    except np.linalg.LinAlgError:
        return None
    alpha, beta = coeffs
    # predict test set CPI changes
    d_test_uifpi = np.diff(np.concatenate([[train_uifpi[-1]], test_uifpi]))
    d_pred = alpha + beta * d_test_uifpi
    # reconstruct level predictions
    preds = []
    last_cpi = train_cpi[-1]
    for d in d_pred:
        last_cpi += d
        preds.append(last_cpi)
    return np.array(preds)


def uifpi_ar1_combined(train_cpi, train_uifpi, test_uifpi) -> Optional[np.ndarray]:
    """Average of AR(1) and UIFPI predictions."""
    ar1_preds  = ar1_predict(train_cpi, len(test_uifpi))
    uifpi_preds = uifpi_predict(train_cpi, train_uifpi, test_uifpi)
    if uifpi_preds is None:
        return ar1_preds
    return (ar1_preds + uifpi_preds) / 2.0


# ---------------------------------------------------------------------------
# Per-country benchmark
# ---------------------------------------------------------------------------

def benchmark_country(country: str) -> dict:
    cpi   = load_cpi(country)
    uifpi = load_uifpi_annual(country)

    if cpi is None:
        return {"skip": "no_cpi_data"}
    if uifpi is None:
        return {"skip": "no_uifpi_data"}

    # Align on common years
    common = cpi.index.intersection(uifpi.index)
    if len(common) < MIN_TRAIN + MIN_TEST:
        return {
            "skip": f"insufficient_overlap ({len(common)} common years, "
                    f"need {MIN_TRAIN + MIN_TEST})",
        }

    cpi_a   = cpi.reindex(common).values
    uifpi_a = uifpi.reindex(common).values

    # Split: last MIN_TEST years for test
    n_test  = MIN_TEST
    n_train = len(common) - n_test

    train_cpi   = cpi_a[:n_train]
    test_cpi    = cpi_a[n_train:]
    train_uifpi = uifpi_a[:n_train]
    test_uifpi  = uifpi_a[n_train:]

    # AR(1) baseline
    ar1_preds  = ar1_predict(train_cpi, n_test)
    ar1_acc    = directional_accuracy(
        np.concatenate([[train_cpi[-1]], test_cpi]),
        np.concatenate([[train_cpi[-1]], ar1_preds]),
    )

    # UIFPI model
    uifpi_preds = uifpi_predict(train_cpi, train_uifpi, test_uifpi)
    if uifpi_preds is not None:
        uifpi_acc = directional_accuracy(
            np.concatenate([[train_cpi[-1]], test_cpi]),
            np.concatenate([[train_cpi[-1]], uifpi_preds]),
        )
    else:
        uifpi_acc = float("nan")

    # Combined
    combo_preds = uifpi_ar1_combined(train_cpi, train_uifpi, test_uifpi)
    if combo_preds is not None:
        combo_acc = directional_accuracy(
            np.concatenate([[train_cpi[-1]], test_cpi]),
            np.concatenate([[train_cpi[-1]], combo_preds]),
        )
    else:
        combo_acc = float("nan")

    adds_value = (
        not np.isnan(uifpi_acc) and not np.isnan(ar1_acc) and uifpi_acc > ar1_acc
    )

    return {
        "n_total":          int(len(common)),
        "n_train":          int(n_train),
        "n_test":           int(n_test),
        "ar1_accuracy":     round(float(ar1_acc), 4) if not np.isnan(ar1_acc) else None,
        "uifpi_accuracy":   round(float(uifpi_acc), 4) if not np.isnan(uifpi_acc) else None,
        "uifpi_ar1_combined": round(float(combo_acc), 4) if not np.isnan(combo_acc) else None,
        "uifpi_adds_value": bool(adds_value),
        "note": (f"Annual data used ({n_train} train / {n_test} test years). "
                 "Monthly data will strengthen these estimates once collection completes."),
    }


# ---------------------------------------------------------------------------
# Print comparison table
# ---------------------------------------------------------------------------

def print_table(results: dict):
    print("\n" + "=" * 80)
    print("BENCHMARK COMPARISON — Directional Accuracy")
    print("=" * 80)
    print(f"{'Country':15s}  {'AR(1)':>8s}  {'UIFPI':>8s}  {'Combined':>10s}  {'Adds value':>10s}")
    print("-" * 80)
    for country, r in sorted(results.items()):
        if "skip" in r:
            print(f"  {country:15s}  {'skip':>8s}  {'skip':>8s}  {'skip':>10s}  "
                  f"  ({r['skip']})")
            continue
        ar1   = f"{r['ar1_accuracy']:.2%}" if r.get("ar1_accuracy") is not None else "N/A"
        uifpi = f"{r['uifpi_accuracy']:.2%}" if r.get("uifpi_accuracy") is not None else "N/A"
        combo = f"{r['uifpi_ar1_combined']:.2%}" if r.get("uifpi_ar1_combined") is not None else "N/A"
        av    = "Yes ✓" if r.get("uifpi_adds_value") else "No"
        print(f"  {country:15s}  {ar1:>8s}  {uifpi:>8s}  {combo:>10s}  {av:>10s}")
    print("=" * 80)
    n_adds = sum(1 for r in results.values() if r.get("uifpi_adds_value"))
    n_run  = sum(1 for r in results.values() if "skip" not in r)
    print(f"\n  UIFPI adds value in {n_adds}/{n_run} testable countries.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("Running UIFPI Benchmark Comparison...")

    results = {}
    for country in COUNTRY_CPI_FILES:
        print(f"  {country}...", end=" ")
        r = benchmark_country(country)
        results[country] = r
        if "skip" in r:
            print(f"skipped ({r['skip']})")
        else:
            ar1   = r.get("ar1_accuracy")
            uifpi = r.get("uifpi_accuracy")
            print(f"AR1={ar1:.2%} UIFPI={uifpi:.2%}" if ar1 and uifpi else "ok")

    print_table(results)

    out_path = os.path.join(RESULTS_DIR, "benchmark_comparison.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()

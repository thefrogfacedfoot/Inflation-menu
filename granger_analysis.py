"""
UIFPI — Granger Causality Analysis
Tests whether the UIFPI leads official CPI using Granger causality and
pass-through regression following Cavallo & Rigobon (2016).

Requires: pandas, numpy, scipy, statsmodels

Run order: after index_builder.py has produced uifpi_index.csv and
cpi_data/ contains monthly_cpi_*.json files.

Results are saved to analysis_results/granger_results.json and
analysis_results/summary.csv.
"""

import json
import os
import sqlite3
import warnings
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

# Suppress statsmodels convergence warnings — we handle them gracefully
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

try:
    from statsmodels.tsa.stattools import adfuller, grangercausalitytests
    from statsmodels.tsa.vector_ar.var_model import VAR
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools.tools import add_constant
    STATSMODELS_OK = True
except ImportError:
    STATSMODELS_OK = False

DB_PATH          = "uifpi.db"
UIFPI_CSV        = "uifpi_index.csv"
CPI_DIR          = "cpi_data"
RESULTS_DIR      = "analysis_results"
MIN_OBS          = 8     # minimum monthly observations for Granger test
MAX_LAGS         = 6
ADF_SIGNIFICANCE = 0.05

COUNTRY_CPI_FILES = {
    "Singapore":      "monthly_cpi_sg.json",
    "Malaysia":       "monthly_cpi_my.json",
    "Indonesia":      "monthly_cpi_id.json",
    "Thailand":       "monthly_cpi_th.json",
    "India":          "monthly_cpi_in.json",
    "United States":  "monthly_cpi_us.json",
    "United Kingdom": "monthly_cpi_gb.json",
    "Australia":      "monthly_cpi_au.json",
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_uifpi_series(csv_path: str = UIFPI_CSV) -> Optional[pd.DataFrame]:
    """Load UIFPI monthly index from CSV. Returns None if file missing."""
    if not os.path.exists(csv_path):
        print(f"  ⚠  {csv_path} not found — run index_builder.py first.")
        return None
    df = pd.read_csv(csv_path, parse_dates=False)
    df["period"] = pd.PeriodIndex(df["year_month"], freq="M")
    return df


def load_cpi_series(country: str) -> Optional[pd.Series]:
    """
    Load CPI time series for a country from its monthly_cpi_*.json file.
    Returns a pandas Series indexed by Period('M'), or None if unavailable.

    Annual data (month='01' only) is linearly interpolated to monthly.
    """
    fname = COUNTRY_CPI_FILES.get(country)
    if not fname:
        return None
    fpath = os.path.join(CPI_DIR, fname)
    if not os.path.exists(fpath):
        return None

    with open(fpath) as f:
        data = json.load(f)

    records = data.get("data", [])
    if not records:
        return None

    # Parse to Series indexed by period string
    s = pd.Series(
        {r["period"]: float(r["cpi"]) for r in records if r.get("cpi") is not None}
    )
    s.index = pd.PeriodIndex(s.index, freq="M")
    s = s.sort_index()

    # Detect annual-only data (all month == 01) and interpolate
    if all(p.month == 1 for p in s.index):
        # Reindex to monthly and interpolate linearly
        full_range = pd.period_range(s.index.min(), s.index.max(), freq="M")
        s = s.reindex(full_range).interpolate(method="index")

    return s


def align_series(uifpi_df: pd.DataFrame, country: str,
                 cpi_s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Extract UIFPI combined index for a country and align it with CPI
    on the overlapping date range. Returns (uifpi_series, cpi_series).
    """
    ux = uifpi_df[uifpi_df["country"] == country][["period", "uifpi_combined"]].dropna()
    ux = ux.set_index("period")["uifpi_combined"]
    ux.index = pd.PeriodIndex(ux.index, freq="M")

    common = ux.index.intersection(cpi_s.index)
    return ux.loc[common], cpi_s.loc[common]


# ── Stationarity testing ──────────────────────────────────────────────────────

def test_stationarity(series: pd.Series, name: str) -> tuple[pd.Series, bool, float]:
    """
    Run Augmented Dickey-Fuller test. If non-stationary, take first difference.
    Returns (final_series, is_stationary, p_value).
    """
    if len(series) < 5:
        return series, False, 1.0

    try:
        adf_result = adfuller(series.dropna(), autolag="AIC")
        p_val = adf_result[1]
    except Exception as e:
        print(f"    ADF failed for {name}: {e}")
        return series, False, 1.0

    if p_val <= ADF_SIGNIFICANCE:
        return series, True, p_val

    # Non-stationary: first difference
    diff = series.diff().dropna()
    try:
        adf_diff = adfuller(diff.dropna(), autolag="AIC")
        p_diff = adf_diff[1]
    except Exception:
        return diff, False, p_val

    stationary = p_diff <= ADF_SIGNIFICANCE
    return diff, stationary, p_diff


# ── Granger causality ─────────────────────────────────────────────────────────

def run_granger(country: str,
                uifpi_s: pd.Series, cpi_s: pd.Series) -> dict:
    """
    Run Granger causality test and pass-through OLS for one country.
    Returns a result dict. Handles insufficient data gracefully.
    """
    result: dict = {
        "country":                country,
        "n_obs":                  len(uifpi_s),
        "granger_significant":    False,
        "granger_p_value":        None,
        "lead_months":            None,
        "aic_lag":                None,
        "pass_through_formal":    None,
        "pass_through_informal":  None,
        "pass_through_significant": False,
        "note":                   "",
    }

    if len(uifpi_s) < MIN_OBS:
        result["note"] = (
            f"insufficient_data: need >= {MIN_OBS} months, "
            f"have {len(uifpi_s)}"
        )
        print(f"  {country}: ⚠  {result['note']}")
        return result

    print(f"  {country}: {len(uifpi_s)} observations")

    # ── Stationarity ────────────────────────────────────────────────────────
    uifpi_stat, u_ok, u_p = test_stationarity(uifpi_s, f"{country}/UIFPI")
    cpi_stat,   c_ok, c_p = test_stationarity(cpi_s,   f"{country}/CPI")

    print(f"    Stationarity — UIFPI p={u_p:.3f} ({'✓' if u_ok else '≈'}) "
          f"CPI p={c_p:.3f} ({'✓' if c_ok else '≈'})")

    if not u_ok:
        uifpi_stat = uifpi_s.diff().dropna()
        print(f"    Using differenced UIFPI")
    if not c_ok:
        cpi_stat = cpi_s.diff().dropna()
        print(f"    Using differenced CPI")

    # Align after differencing
    common = uifpi_stat.index.intersection(cpi_stat.index)
    if len(common) < MIN_OBS:
        result["note"] = "insufficient_data_after_differencing"
        print(f"    ⚠  {result['note']}")
        return result

    u_clean = uifpi_stat.loc[common].astype(float)
    c_clean = cpi_stat.loc[common].astype(float)

    # ── VAR lag selection ────────────────────────────────────────────────────
    try:
        var_data = pd.DataFrame({"uifpi": u_clean, "cpi": c_clean}).dropna()
        model    = VAR(var_data)
        lag_result = model.select_order(maxlags=min(MAX_LAGS, len(var_data) // 4))
        aic_lag  = lag_result.aic
        aic_lag  = max(1, int(aic_lag))
    except Exception as e:
        aic_lag = 2
        print(f"    VAR lag selection failed ({e}), defaulting to lag=2")

    result["aic_lag"] = aic_lag
    print(f"    AIC-selected lag: {aic_lag}")

    # ── Granger causality test ───────────────────────────────────────────────
    # grangercausalitytests tests: does column 1 (uifpi) Granger-cause column 0 (cpi)?
    try:
        gc_data = pd.DataFrame({"cpi": c_clean, "uifpi": u_clean}).dropna()
        gc_res  = grangercausalitytests(gc_data, maxlag=aic_lag, verbose=False)

        # Find the lag with the lowest F-test p-value
        best_lag = None
        best_p   = 1.0
        for lag, tests in gc_res.items():
            p = tests[0]["ssr_ftest"][1]
            if p < best_p:
                best_p   = p
                best_lag = lag

        result["granger_p_value"]   = round(best_p, 4)
        result["lead_months"]       = best_lag
        result["granger_significant"] = best_p < 0.05

        print(f"    Granger p={best_p:.4f} at lag={best_lag} "
              f"({'SIGNIFICANT ✓' if best_p < 0.05 else 'not significant'})")

    except Exception as e:
        result["note"] = f"granger_failed: {e}"
        print(f"    Granger test failed: {e}")

    # ── ADL pass-through regression ──────────────────────────────────────────
    # ΔIn(CPI_t) = α + β₁ΔIn(UIFPI_t) + Σα_i ΔIn(CPI_{t-i}) + Σβ_i ΔIn(UIFPI_{t-i})
    # Using log-differences where > 0
    try:
        log_u = np.log(uifpi_s.clip(lower=0.001)).diff().dropna()
        log_c = np.log(cpi_s.clip(lower=0.001)).diff().dropna()

        common2 = log_u.index.intersection(log_c.index)
        if len(common2) < MIN_OBS:
            raise ValueError("insufficient obs for pass-through")

        lags = min(aic_lag, 2)
        adl_df = pd.DataFrame({
            "dcpi":   log_c.loc[common2],
            "duifpi": log_u.loc[common2],
        })
        # Add lagged variables
        for k in range(1, lags + 1):
            adl_df[f"dcpi_lag{k}"]   = adl_df["dcpi"].shift(k)
            adl_df[f"duifpi_lag{k}"] = adl_df["duifpi"].shift(k)

        # Month dummies (seasonal adjustment)
        adl_df["month"] = [p.month for p in adl_df.index]
        month_dummies = pd.get_dummies(adl_df["month"], prefix="m", drop_first=True)
        adl_df = pd.concat([adl_df.drop(columns="month"), month_dummies], axis=1)
        adl_df = adl_df.dropna()

        if len(adl_df) < MIN_OBS:
            raise ValueError("insufficient obs after lagging")

        y = adl_df["dcpi"].values
        X = add_constant(adl_df.drop(columns="dcpi").values)

        ols = OLS(y, X).fit()

        # coef index 1 = duifpi (contemporaneous)
        pt_coef = ols.params[1]
        pt_pval = ols.pvalues[1]

        result["pass_through_formal"]       = round(float(pt_coef), 4)
        result["pass_through_significant"]  = pt_pval < 0.05
        result["r_squared"]                 = round(float(ols.rsquared), 4)

        print(f"    Pass-through coef={pt_coef:.3f} p={pt_pval:.3f} "
              f"R²={ols.rsquared:.3f}")

    except Exception as e:
        print(f"    Pass-through regression failed: {e}")

    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def run(uifpi_csv: str = UIFPI_CSV, cpi_dir: str = CPI_DIR) -> None:
    """Run Granger and pass-through analysis for all available countries."""
    if not STATSMODELS_OK:
        print("✗  statsmodels not installed.")
        print("   Run: pip install statsmodels pandas numpy scipy")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("\nGranger Causality Analysis")
    print("─" * 60)

    # Load UIFPI
    uifpi_df = load_uifpi_series(uifpi_csv)
    if uifpi_df is None or uifpi_df.empty:
        print("No UIFPI data available — run index_builder.py first.")
        return

    print(f"Loaded UIFPI for {uifpi_df['country'].nunique()} countries")

    all_results: list[dict] = []

    for country in sorted(uifpi_df["country"].unique()):
        print(f"\n[{country}]")

        cpi_s = load_cpi_series(country)
        if cpi_s is None or cpi_s.empty:
            print(f"  ⚠  No CPI data found for {country}")
            all_results.append({
                "country": country, "note": "no_cpi_data",
                "granger_significant": False,
            })
            continue

        uifpi_s, cpi_aligned = align_series(uifpi_df, country, cpi_s)

        if uifpi_s.empty:
            print(f"  ⚠  No overlapping UIFPI + CPI dates for {country}")
            all_results.append({
                "country": country, "note": "no_overlap",
                "granger_significant": False,
            })
            continue

        result = run_granger(country, uifpi_s, cpi_aligned)
        all_results.append(result)

    # ── Save full JSON results ───────────────────────────────────────────────
    results_by_country = {r["country"]: {k: v for k, v in r.items()
                                          if k != "country"}
                          for r in all_results}
    json_path = os.path.join(RESULTS_DIR, "granger_results.json")
    with open(json_path, "w") as f:
        json.dump(results_by_country, f, indent=2)
    print(f"\n✓  Full results saved to {json_path}")

    # ── Print summary table ──────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("Summary Table")
    print(f"{'='*80}")
    hdr = (f"{'Country':<20} {'n_obs':>5} {'Granger p':>10} {'Lead mo':>8} "
           f"{'Pass-thru':>10} {'Sig?':>5}")
    print(hdr)
    print("-" * 80)
    for r in sorted(all_results, key=lambda x: x["country"]):
        gp   = f"{r['granger_p_value']:.3f}"  if r.get("granger_p_value")  else "—"
        lead = f"{r['lead_months']}"           if r.get("lead_months")      else "—"
        pt   = f"{r['pass_through_formal']:.3f}" if r.get("pass_through_formal") else "—"
        sig  = "✓" if r.get("granger_significant") else "✗"
        note = r.get("note", "")
        n    = r.get("n_obs", 0)
        print(f"  {r['country']:<20} {n:>5} {gp:>10} {lead:>8} "
              f"{pt:>10} {sig:>5}  {note}")
    print()

    # ── Save summary CSV ─────────────────────────────────────────────────────
    summary_rows = []
    for r in all_results:
        summary_rows.append({
            "country":            r.get("country"),
            "n_obs":              r.get("n_obs", 0),
            "granger_p_value":    r.get("granger_p_value"),
            "lead_months":        r.get("lead_months"),
            "aic_lag":            r.get("aic_lag"),
            "granger_significant":r.get("granger_significant"),
            "pass_through":       r.get("pass_through_formal"),
            "pass_through_sig":   r.get("pass_through_significant"),
            "r_squared":          r.get("r_squared"),
            "note":               r.get("note", ""),
        })
    import csv
    csv_path = os.path.join(RESULTS_DIR, "summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"✓  Summary CSV saved to {csv_path}")


if __name__ == "__main__":
    run()

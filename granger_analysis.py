"""
UIFPI — Granger Causality Analysis
Tests whether the UIFPI leads official CPI using Granger causality and
pass-through regression following Cavallo & Rigobon (2016).

Data sources (in priority order):
  1. uifpi_index table + monthly_cpi table from uifpi.db  (DB-first)
  2. uifpi_index.csv  +  cpi_data/monthly_cpi_*.json       (legacy fallback)

Usage:
    python granger_analysis.py [--min-obs 8] [--max-lags 6]
"""

import argparse
import csv
import json
import os
import sqlite3
import warnings
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

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

DB_PATH     = "uifpi.db"
UIFPI_CSV   = "uifpi_index.csv"
CPI_DIR     = "cpi_data"
RESULTS_DIR = "analysis_results"

# Default thresholds — can be overridden via CLI
DEFAULT_MIN_OBS  = 8    # lower than ideal 24; reflects current data collection stage
DEFAULT_MAX_LAGS = 4
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

COUNTRY_TO_CODE = {
    "Singapore": "SG", "Malaysia": "MY", "Indonesia": "ID",
    "Thailand": "TH", "India": "IN", "United States": "US",
    "United Kingdom": "GB", "Australia": "AU",
    "Vietnam": "VN", "United Arab Emirates": "AE",
}


# ─────────────────────────────────────────────────────────────────────────────
# Data loading — DB-first
# ─────────────────────────────────────────────────────────────────────────────

def load_uifpi_from_db() -> Optional[pd.DataFrame]:
    """Load uifpi_index table from DB. Returns None if empty."""
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT country, year_month, uifpi_combined FROM uifpi_index "
        "WHERE uifpi_combined IS NOT NULL ORDER BY country, year_month",
        conn,
    )
    conn.close()
    if df.empty:
        return None
    df["period"] = pd.PeriodIndex(df["year_month"], freq="M")
    return df


def load_uifpi_from_csv() -> Optional[pd.DataFrame]:
    """Fallback: load UIFPI from uifpi_index.csv."""
    if not os.path.exists(UIFPI_CSV):
        return None
    df = pd.read_csv(UIFPI_CSV)
    df = df.dropna(subset=["uifpi_combined"])
    if df.empty:
        return None
    df["period"] = pd.PeriodIndex(df["year_month"], freq="M")
    return df


def load_uifpi() -> Optional[pd.DataFrame]:
    df = load_uifpi_from_db()
    if df is not None and not df.empty:
        print(f"UIFPI loaded from DB: {len(df)} rows, "
              f"{df['country'].nunique()} countries")
        return df
    df = load_uifpi_from_csv()
    if df is not None and not df.empty:
        print(f"UIFPI loaded from CSV: {len(df)} rows, "
              f"{df['country'].nunique()} countries")
        return df
    return None


def load_cpi_from_db(country: str) -> Optional[pd.Series]:
    """Load CPI series for a country from monthly_cpi table."""
    code = COUNTRY_TO_CODE.get(country)
    if not code:
        return None
    if not os.path.exists(DB_PATH):
        return None
    conn  = sqlite3.connect(DB_PATH)
    cur   = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='monthly_cpi'"
    )
    if not cur.fetchone():
        conn.close()
        return None
    df = pd.read_sql_query(
        "SELECT year_month, cpi_value FROM monthly_cpi "
        "WHERE country_code=? AND cpi_value IS NOT NULL "
        "ORDER BY year_month",
        conn, params=(code,),
    )
    conn.close()
    if df.empty:
        return None
    s       = pd.Series(df["cpi_value"].values,
                        index=pd.PeriodIndex(df["year_month"], freq="M"))
    s       = s.sort_index()

    # If all entries are at month=01 (annual data), interpolate to monthly
    if all(p.month == 1 for p in s.index):
        full_range = pd.period_range(s.index.min(), s.index.max(), freq="M")
        s = s.reindex(full_range).interpolate(method="index")

    return s


def load_cpi_from_json(country: str) -> Optional[pd.Series]:
    """Fallback: load CPI from legacy cpi_data/monthly_cpi_*.json."""
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
    s = pd.Series(
        {r["period"]: float(r["cpi"]) for r in records if r.get("cpi") is not None}
    )
    s.index = pd.PeriodIndex(s.index, freq="M")
    s = s.sort_index()
    if all(p.month == 1 for p in s.index):
        full_range = pd.period_range(s.index.min(), s.index.max(), freq="M")
        s = s.reindex(full_range).interpolate(method="index")
    return s


def load_cpi(country: str) -> Optional[pd.Series]:
    s = load_cpi_from_db(country)
    if s is not None and len(s) > 0:
        return s
    return load_cpi_from_json(country)


# ─────────────────────────────────────────────────────────────────────────────
# Series alignment
# ─────────────────────────────────────────────────────────────────────────────

def align_series(uifpi_df: pd.DataFrame, country: str,
                 cpi_s: pd.Series) -> tuple:
    sub = uifpi_df[uifpi_df["country"] == country][["period", "uifpi_combined"]].dropna()
    if sub.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    ux = sub.set_index("period")["uifpi_combined"]
    ux.index = pd.PeriodIndex(ux.index, freq="M")
    common = ux.index.intersection(cpi_s.index)
    return ux.loc[common], cpi_s.loc[common]


# ─────────────────────────────────────────────────────────────────────────────
# Stationarity
# ─────────────────────────────────────────────────────────────────────────────

def test_stationarity(series: pd.Series) -> tuple:
    """ADF test. Returns (stationary_series, is_stationary, p_value)."""
    if len(series) < 5:
        return series.diff().dropna(), False, 1.0
    try:
        p = adfuller(series.dropna(), autolag="AIC")[1]
    except Exception:
        return series.diff().dropna(), False, 1.0
    if p <= ADF_SIGNIFICANCE:
        return series, True, p
    diff = series.diff().dropna()
    try:
        p2 = adfuller(diff.dropna(), autolag="AIC")[1]
    except Exception:
        return diff, False, p
    return diff, p2 <= ADF_SIGNIFICANCE, p2


# ─────────────────────────────────────────────────────────────────────────────
# Granger + pass-through
# ─────────────────────────────────────────────────────────────────────────────

def run_granger(country: str, uifpi_s: pd.Series, cpi_s: pd.Series,
                min_obs: int, max_lags: int) -> dict:
    result = {
        "country":                  country,
        "n_obs":                    len(uifpi_s),
        "granger_significant":      False,
        "granger_p_value":          None,
        "lead_months":              None,
        "aic_lag":                  None,
        "pass_through_formal":      None,
        "pass_through_se":          None,
        "pass_through_p_value":     None,
        "pass_through_ci_low":      None,
        "pass_through_ci_high":     None,
        "pass_through_significant": False,
        "r_squared":                None,
        "note":                     "",
    }

    if len(uifpi_s) < min_obs:
        note = f"insufficient_data (have {len(uifpi_s)}, need {min_obs})"
        result["note"] = note
        print(f"  ⚠  {note}")
        return result

    print(f"  {len(uifpi_s)} overlapping observations")

    # Stationarity
    u_stat, u_ok, u_p = test_stationarity(uifpi_s)
    c_stat, c_ok, c_p = test_stationarity(cpi_s)
    print(f"  ADF: UIFPI p={u_p:.3f} ({'stationary' if u_ok else 'differenced'}), "
          f"CPI p={c_p:.3f} ({'stationary' if c_ok else 'differenced'})")

    common = u_stat.index.intersection(c_stat.index)
    if len(common) < min_obs:
        result["note"] = f"insufficient_data_after_differencing ({len(common)} obs)"
        print(f"  ⚠  {result['note']}")
        return result

    u_clean = u_stat.loc[common].astype(float)
    c_clean = c_stat.loc[common].astype(float)

    # VAR lag selection
    aic_lag = 1
    try:
        var_data   = pd.DataFrame({"uifpi": u_clean, "cpi": c_clean}).dropna()
        max_lags_v = min(max_lags, max(1, len(var_data) // 5))
        if max_lags_v >= 1:
            model      = VAR(var_data)
            lag_result = model.select_order(maxlags=max_lags_v)
            aic_lag    = max(1, int(lag_result.aic))
    except Exception as e:
        print(f"  VAR lag selection warning: {e} — using lag=1")
    result["aic_lag"] = aic_lag
    print(f"  AIC-selected lag: {aic_lag}")

    # Granger causality test
    try:
        gc_data = pd.DataFrame({"cpi": c_clean, "uifpi": u_clean}).dropna()
        gc_res  = grangercausalitytests(gc_data, maxlag=aic_lag, verbose=False)
        best_p, best_lag, best_F, best_df_num, best_df_denom = 1.0, 1, None, None, None
        per_lag = []
        for lag, tests in gc_res.items():
            F, p, df_denom, df_num = tests[0]["ssr_ftest"]
            per_lag.append({"lag": int(lag),
                             "F": round(float(F), 4),
                             "p": round(float(p), 4),
                             "df_num": int(df_num),
                             "df_denom": int(df_denom)})
            if p < best_p:
                best_p, best_lag = p, lag
                best_F, best_df_num, best_df_denom = F, df_num, df_denom
        result["granger_p_value"]      = round(best_p, 4)
        result["granger_f_statistic"]  = round(float(best_F), 4) if best_F is not None else None
        result["granger_df_num"]       = int(best_df_num) if best_df_num is not None else None
        result["granger_df_denom"]     = int(best_df_denom) if best_df_denom is not None else None
        result["granger_per_lag"]      = per_lag
        result["lead_months"]          = best_lag
        result["granger_significant"]  = best_p < 0.05
        sig_str = "SIGNIFICANT ✓" if best_p < 0.05 else "not significant"
        print(f"  Granger: p={best_p:.4f} at lag={best_lag} ({sig_str})")
    except Exception as e:
        result["note"] += f" granger_failed:{e}"
        print(f"  Granger test error: {e}")

    # Pass-through regression: Δln(CPI) = α + β·Δln(UIFPI) + controls
    try:
        log_u = np.log(uifpi_s.clip(lower=0.001)).diff().dropna()
        log_c = np.log(cpi_s.clip(lower=0.001)).diff().dropna()
        common2 = log_u.index.intersection(log_c.index)
        if len(common2) < min_obs:
            raise ValueError(f"only {len(common2)} obs for pass-through")

        # Use no lagged variables for small samples; skip month dummies too
        lags = 0 if len(common2) < 20 else min(aic_lag, 2)
        adl = pd.DataFrame({
            "dcpi":   log_c.loc[common2].values,
            "duifpi": log_u.loc[common2].values,
        }, index=range(len(common2)))
        for k in range(1, lags + 1):
            adl[f"dcpi_lag{k}"]   = adl["dcpi"].shift(k)
            adl[f"duifpi_lag{k}"] = adl["duifpi"].shift(k)
        if lags > 0:
            months = [p.month for p in common2]
            adl["month"] = months
            dummies = pd.get_dummies(adl["month"], prefix="m", drop_first=True)
            adl = pd.concat([adl.drop(columns="month"), dummies], axis=1)
        adl = adl.dropna()
        if len(adl) < min_obs:
            raise ValueError(f"only {len(adl)} obs after lagging")
        y = adl["dcpi"].values.astype(float)
        X_raw = adl.drop(columns="dcpi").values.astype(float)
        # Require at least 3 degrees of freedom
        if len(y) - X_raw.shape[1] - 1 < 3:
            raise ValueError(
                f"insufficient DOF: n={len(y)}, k={X_raw.shape[1]+1}")
        X = add_constant(X_raw)
        fit = OLS(y, X).fit()
        ci = fit.conf_int(alpha=0.05)[1]   # 95% CI on β (the duifpi coef)
        result["pass_through_formal"]      = round(float(fit.params[1]), 4)
        result["pass_through_se"]          = round(float(fit.bse[1]), 5)
        result["pass_through_p_value"]     = round(float(fit.pvalues[1]), 4)
        result["pass_through_ci_low"]      = round(float(ci[0]), 5)
        result["pass_through_ci_high"]     = round(float(ci[1]), 5)
        result["pass_through_significant"] = float(fit.pvalues[1]) < 0.05
        result["r_squared"]                = round(float(fit.rsquared), 4)
        print(f"  Pass-through: β={fit.params[1]:.4f} "
              f"SE={fit.bse[1]:.4f} p={fit.pvalues[1]:.4f} "
              f"95%CI=[{ci[0]:.4f}, {ci[1]:.4f}] R²={fit.rsquared:.4f}")
    except Exception as e:
        print(f"  Pass-through: {e}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run(min_obs: int = DEFAULT_MIN_OBS, max_lags: int = DEFAULT_MAX_LAGS) -> None:
    if not STATSMODELS_OK:
        print("statsmodels not installed. Run: pip install statsmodels")
        return

    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("\nGranger Causality Analysis")
    print(f"  min_obs={min_obs}  max_lags={max_lags}")
    print("─" * 60)

    uifpi_df = load_uifpi()
    if uifpi_df is None or uifpi_df.empty:
        print("No UIFPI data. Run index_builder.py first.")
        return

    all_results = []

    for country in sorted(uifpi_df["country"].unique()):
        print(f"\n[{country}]")
        cpi_s = load_cpi(country)
        if cpi_s is None or cpi_s.empty:
            print(f"  No CPI data")
            all_results.append({"country": country, "n_obs": 0,
                                 "note": "no_cpi_data",
                                 "granger_significant": False})
            continue
        print(f"  CPI: {len(cpi_s)} obs  ({cpi_s.index.min()} – {cpi_s.index.max()})")

        uifpi_s, cpi_aligned = align_series(uifpi_df, country, cpi_s)
        if uifpi_s.empty:
            print(f"  No overlapping dates")
            all_results.append({"country": country, "n_obs": 0,
                                 "note": "no_overlap",
                                 "granger_significant": False})
            continue
        print(f"  UIFPI: {len(uifpi_s)} obs  ({uifpi_s.index.min()} – {uifpi_s.index.max()})")
        print(f"  Overlap: {len(uifpi_s)} months")

        result = run_granger(country, uifpi_s, cpi_aligned, min_obs, max_lags)
        all_results.append(result)

    # ── Save results ──────────────────────────────────────────────────────────
    def _to_python(v):
        """Convert numpy scalars to native Python types for JSON."""
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
        return v

    results_by_country = {
        r["country"]: {k: _to_python(v) for k, v in r.items() if k != "country"}
        for r in all_results
    }
    json_path = os.path.join(RESULTS_DIR, "granger_results.json")
    with open(json_path, "w") as f:
        json.dump(results_by_country, f, indent=2)
    print(f"\n✓ Results → {json_path}")

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("Granger Causality Summary")
    print(f"{'='*80}")
    print(f"  {'Country':<22} {'n':>5} {'Granger p':>10} {'Lead':>6} "
          f"{'β pass-thru':>12} {'R²':>6} {'Sig':>4}  Note")
    print(f"  {'─'*76}")

    for r in sorted(all_results, key=lambda x: x["country"]):
        gp   = f"{r['granger_p_value']:.3f}"    if r.get("granger_p_value") is not None else "—"
        lead = f"{r['lead_months']}"             if r.get("lead_months")     is not None else "—"
        pt   = f"{r['pass_through_formal']:.3f}" if r.get("pass_through_formal") is not None else "—"
        r2   = f"{r['r_squared']:.3f}"           if r.get("r_squared")       is not None else "—"
        sig  = "✓" if r.get("granger_significant") else "✗"
        note = r.get("note", "")[:35]
        n    = r.get("n_obs", 0)
        print(f"  {r['country']:<22} {n:>5} {gp:>10} {lead:>6} "
              f"{pt:>12} {r2:>6} {sig:>4}  {note}")

    n_sig = sum(1 for r in all_results if r.get("granger_significant"))
    print(f"\n  Countries with significant Granger causality: "
          f"{n_sig} / {len(all_results)}")
    print(f"  (threshold: p < 0.05, min {min_obs} overlapping observations)")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    fields = ["country", "n_obs", "granger_p_value", "lead_months",
              "aic_lag", "granger_significant", "pass_through_formal",
              "pass_through_significant", "r_squared", "note"]
    csv_path = os.path.join(RESULTS_DIR, "summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: r.get(k, "") for k in fields})
    print(f"✓ Summary CSV → {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="UIFPI Granger causality analysis")
    parser.add_argument("--min-obs",  type=int, default=DEFAULT_MIN_OBS,
                        help=f"Min overlapping months for Granger (default {DEFAULT_MIN_OBS})")
    parser.add_argument("--max-lags", type=int, default=DEFAULT_MAX_LAGS,
                        help=f"Max VAR lags (default {DEFAULT_MAX_LAGS})")
    args = parser.parse_args()
    run(min_obs=args.min_obs, max_lags=args.max_lags)


if __name__ == "__main__":
    main()

"""
UICPI — Permutation test for the US lag-1 Granger F-statistic.

The headline finding (UIFPI Granger-causes CPI at 1-month lead, F=6.03,
p=0.021, n=31) rests on F-distribution asymptotics at a small sample size.
This script replaces the analytic null with an empirical one: hold the CPI
series fixed, permute the (stationarity-transformed) menu series, and
recompute the lag-1 Granger F many times under three permutation schemes:

  shuffle  — full random permutation (destroys all temporal structure;
             classic exchangeability null)
  block    — circular moving-block permutation, block length 5 (preserves
             short-run autocorrelation within blocks; more conservative)
  rotate   — all n-1 exact circular shifts (preserves the entire
             autocorrelation structure; only n-1 draws available)

Empirical p = (1 + #{F_null >= F_obs}) / (N + 1).

Also verifies the Granger sign convention by reproducing the statsmodels
lag-1 F with a manual OLS of CPI(t) on [CPI(t-1), UIFPI(t-1)], and prints
sample month-pairs so the menu(t-1) -> CPI(t) orientation is visible.

Reuses granger_analysis's own loaders so the data path is identical to the
headline result. Run after granger_analysis.py. Outputs:
  analysis_results/permutation_test.json
  analysis_results/permutation_test.png
"""
import json
import os

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests

from granger_analysis import (
    RESULTS_DIR, align_series, load_cpi, load_uifpi, test_stationarity,
)

COUNTRY   = "United States"
N_PERM    = 1000
BLOCK_LEN = 5
SEED      = 42


def lag1_granger_F(u: pd.Series, c: pd.Series) -> float:
    """Lag-1 Granger F for u -> c, via the same statsmodels call and
    column order ({cpi, uifpi}) as granger_analysis.run_granger."""
    gc_data = pd.DataFrame({"cpi": c, "uifpi": u}).dropna()
    res = grangercausalitytests(gc_data, maxlag=1, verbose=False)
    F, _p, _df_denom, _df_num = res[1][0]["ssr_ftest"]
    return float(F)


def manual_lag1_check(u: pd.Series, c: pd.Series) -> dict:
    """Reproduce the lag-1 F by explicit OLS so the orientation is
    beyond doubt: unrestricted CPI(t) ~ 1 + CPI(t-1) + UIFPI(t-1)
    vs restricted CPI(t) ~ 1 + CPI(t-1)."""
    d = pd.DataFrame({"cpi": c, "uifpi": u}).dropna()
    y    = d["cpi"].iloc[1:].to_numpy()
    c_l1 = d["cpi"].iloc[:-1].to_numpy()
    u_l1 = d["uifpi"].iloc[:-1].to_numpy()
    n    = len(y)

    def ssr(X):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        return float(resid @ resid)

    ones  = np.ones(n)
    ssr_u = ssr(np.column_stack([ones, c_l1, u_l1]))
    ssr_r = ssr(np.column_stack([ones, c_l1]))
    F     = ((ssr_r - ssr_u) / 1) / (ssr_u / (n - 3))

    # Reversed direction for contrast: UIFPI(t) ~ 1 + UIFPI(t-1) + CPI(t-1)
    y_r    = d["uifpi"].iloc[1:].to_numpy()
    ssr_u2 = None
    def ssr2(X):
        beta, *_ = np.linalg.lstsq(X, y_r, rcond=None)
        resid = y_r - X @ beta
        return float(resid @ resid)
    ssr_u2 = ssr2(np.column_stack([ones, u_l1, c_l1]))
    ssr_r2 = ssr2(np.column_stack([ones, u_l1]))
    F_rev  = ((ssr_r2 - ssr_u2) / 1) / (ssr_u2 / (n - 3))

    # Sample month-pairs: the row for month t regresses CPI(t) on the
    # PREVIOUS month's menu value.
    pairs = []
    idx = d.index
    for i in [1, len(d) // 2, len(d) - 1]:
        pairs.append({
            "cpi_month":   str(idx[i]),
            "cpi_value":   round(float(d["cpi"].iloc[i]), 4),
            "menu_month":  str(idx[i - 1]),
            "menu_value":  round(float(d["uifpi"].iloc[i - 1]), 4),
        })
    return {"F_manual": F, "F_reversed": F_rev, "n_regression_rows": n,
            "pairs": pairs}


def null_distributions(u: pd.Series, c: pd.Series, F_obs: float) -> dict:
    rng    = np.random.default_rng(SEED)
    vals   = u.to_numpy()
    n      = len(vals)
    out    = {}

    def perm_F(perm_vals) -> float:
        return lag1_granger_F(pd.Series(perm_vals, index=u.index), c)

    # Scheme A — full random shuffle
    fs = []
    for _ in range(N_PERM):
        try:
            fs.append(perm_F(rng.permutation(vals)))
        except Exception:
            continue
    out["shuffle"] = fs

    # Scheme B — circular moving-block permutation
    fs = []
    ext = np.concatenate([vals, vals])          # circular extension
    n_blocks = int(np.ceil(n / BLOCK_LEN))
    for _ in range(N_PERM):
        starts = rng.integers(0, n, size=n_blocks)
        perm = np.concatenate([ext[s:s + BLOCK_LEN] for s in starts])[:n]
        try:
            fs.append(perm_F(perm))
        except Exception:
            continue
    out["block"] = fs

    # Scheme C — all exact circular shifts (n-1 draws)
    fs = []
    for k in range(1, n):
        try:
            fs.append(perm_F(np.roll(vals, k)))
        except Exception:
            continue
    out["rotate"] = fs

    summary = {}
    for name, fs in out.items():
        fs_arr = np.asarray(fs)
        p_emp = (1 + int((fs_arr >= F_obs).sum())) / (len(fs_arr) + 1)
        summary[name] = {
            "n_draws":     len(fs_arr),
            "p_empirical": round(p_emp, 4),
            "null_median": round(float(np.median(fs_arr)), 4),
            "null_q95":    round(float(np.quantile(fs_arr, 0.95)), 4),
            "null_max":    round(float(fs_arr.max()), 4),
        }
    return out, summary


def make_figure(nulls: dict, summary: dict, F_obs: float, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURFACE, BAR, INK, INK2 = "#fcfcfb", "#2a78d6", "#0b0b0b", "#52514e"
    panels = [("shuffle", "Full shuffle null"),
              ("block",   f"Circular block null (b={BLOCK_LEN})")]

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True, dpi=200)
    fig.patch.set_facecolor(SURFACE)
    xmax = max(F_obs * 1.15, max(max(nulls[k]) for k, _ in panels))
    bins = np.linspace(0, xmax, 36)

    for ax, (key, title) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        ax.hist(nulls[key], bins=bins, color=BAR, edgecolor=SURFACE,
                linewidth=0.4, zorder=2)
        ax.axvline(F_obs, color=INK, linestyle=(0, (4, 3)), linewidth=1.4,
                   zorder=3)
        p = summary[key]["p_empirical"]
        ax.text(F_obs, ax.get_ylim()[1] * 0.97,
                f" observed F = {F_obs:.2f}\n empirical p = {p:.3f}",
                ha="left", va="top", fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=10, color=INK, loc="left", pad=8)
        ax.set_xlabel("Lag-1 Granger F under permuted menu series",
                      fontsize=8.5, color=INK2)
        ax.tick_params(colors=INK2, labelsize=8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#d8d7d2")
        ax.grid(axis="y", color="#eceae5", linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)
    axes[0].set_ylabel(f"Count of {N_PERM} permutations",
                       fontsize=8.5, color=INK2)
    fig.suptitle("US menu-price index → CPI: permutation null vs "
                 "observed lag-1 Granger F", fontsize=11, color=INK,
                 x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    print(f"Figure written: {path}")


def main() -> None:
    uifpi_df = load_uifpi()
    if uifpi_df is None:
        raise SystemExit("No UIFPI data found (DB or CSV)")
    cpi_s = load_cpi(COUNTRY)
    if cpi_s is None:
        raise SystemExit(f"No CPI data for {COUNTRY}")

    u_raw, c_raw = align_series(uifpi_df, COUNTRY, cpi_s)
    print(f"{COUNTRY}: {len(u_raw)} aligned observations "
          f"({u_raw.index.min()} .. {u_raw.index.max()})")

    u_stat, u_ok, u_p = test_stationarity(u_raw)
    c_stat, c_ok, c_p = test_stationarity(c_raw)
    print(f"ADF: UIFPI p={u_p:.3f} ({'level' if u_ok else 'differenced'}), "
          f"CPI p={c_p:.3f} ({'level' if c_ok else 'differenced'})")

    common  = u_stat.index.intersection(c_stat.index)
    u_clean = u_stat.loc[common].astype(float)
    c_clean = c_stat.loc[common].astype(float)

    F_obs = lag1_granger_F(u_clean, c_clean)
    print(f"\nObserved lag-1 Granger F (statsmodels, headline pipeline): "
          f"{F_obs:.4f}")

    print("\n── Sign-convention check ──")
    chk = manual_lag1_check(u_clean, c_clean)
    print(f"Manual OLS  CPI(t) ~ CPI(t-1) + MENU(t-1):  F = "
          f"{chk['F_manual']:.4f}  (should match statsmodels above)")
    print(f"Reversed    MENU(t) ~ MENU(t-1) + CPI(t-1): F = "
          f"{chk['F_reversed']:.4f}  (different => orientation is real)")
    print("Sample regression rows (menu leads by one month):")
    for p in chk["pairs"]:
        print(f"  CPI({p['cpi_month']}) regressed on MENU({p['menu_month']})"
              f"  [cpi={p['cpi_value']}, menu_lag={p['menu_value']}]")

    print(f"\n── Permutation null ({N_PERM} draws per scheme, seed={SEED}) ──")
    nulls, summary = null_distributions(u_clean, c_clean, F_obs)
    for name, s in summary.items():
        print(f"{name:8s} n={s['n_draws']:4d}  empirical p={s['p_empirical']:.4f}"
              f"  null median={s['null_median']:.2f}"
              f"  q95={s['null_q95']:.2f}  max={s['null_max']:.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = {
        "country": COUNTRY,
        "F_observed": round(F_obs, 4),
        "F_manual_check": round(chk["F_manual"], 4),
        "F_reversed_direction": round(chk["F_reversed"], 4),
        "n_regression_rows": chk["n_regression_rows"],
        "sample_pairs": chk["pairs"],
        "n_permutations": N_PERM,
        "block_length": BLOCK_LEN,
        "seed": SEED,
        "schemes": summary,
    }
    json_path = os.path.join(RESULTS_DIR, "permutation_test.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults written: {json_path}")

    make_figure(nulls, summary, F_obs,
                os.path.join(RESULTS_DIR, "permutation_test.png"))


if __name__ == "__main__":
    main()

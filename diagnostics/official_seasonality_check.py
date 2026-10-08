#!/usr/bin/env python3
"""Seasonality diagnostic on the registered OFFICIAL NSA restaurant-CPI series only
(no menu data, no index values). For each of US, GB, SG, MY: fetch the primary
series, take Δlog on its longest contiguous run of months, fit
    Δlog CPI_t = const + 11 month dummies + AR(1..3)
by OLS on the full available history, and report the Ljung-Box(12) p-value on the
residuals (model df = 3) and the residual autocorrelation at lag 12.
Prints statistics only (no levels). "full" is the user-requested full-history fit; "last 60"
is a supplementary fit on the last 60 months of the same run (closer to the n of the confirmatory windows).

Usage: python3 diagnostics/official_seasonality_check.py [--out FILE]
"""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import official_cpi_prereg as o  # noqa: E402

warnings.filterwarnings("ignore")


def longest_run_months(obs):
    """Longest run of consecutive calendar months in {YYYY-MM: value}."""
    ords = sorted(int(k[:4]) * 12 + int(k[5:7]) - 1 for k in obs)
    best, cur_start, prev, best_len, cur = None, ords[0], ords[0], 1, 1
    best = (ords[0], 1)
    for a in ords[1:]:
        if a == prev + 1:
            cur += 1
        else:
            cur_start, cur = a, 1
        prev = a
        if cur > best[1]:
            best = (cur_start, cur)
    return best


def main():
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.stattools import acf
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = ["official series seasonality check: Δlog on longest contiguous run; const + 11 month dummies + AR(1..3); "
             "Ljung-Box(12) with model_df=3; residual ACF at lag 12", ""]
    lines.append(f"{'country':<8}{'series':<14}{'fit':<10}{'months':>7}{'window':>24}{'LB(12) p':>11}{'resid ACF(12)':>15}{'+-2/sqrt(T)':>13}")
    for spec in o.SERIES:
        if spec["role"] != "primary":
            continue
        obs = o.parse(spec, o.fetch(spec["url"]))
        start, n = longest_run_months(obs)
        months = [f"{(start + i) // 12:04d}-{(start + i) % 12 + 1:02d}" for i in range(n)]
        for label, keep in (("full", None), ("last 60", 60)):
            mm_ = months if keep is None else months[-keep:]
            lv = np.array([obs[m] for m in mm_])
            y = np.diff(np.log(lv))
            moy = np.array([int(m[5:7]) for m in mm_[1:]])
            p = 3
            T = len(y) - p
            cols = [np.ones(T)] + [(moy[p:] == mm).astype(float) for mm in range(2, 13)]
            cols += [y[p - j: len(y) - j] for j in range(1, p + 1)]
            Z = np.column_stack(cols)
            beta, *_ = np.linalg.lstsq(Z, y[p:], rcond=None)
            res = y[p:] - Z @ beta
            lb = float(acorr_ljungbox(res, lags=[12], model_df=p)["lb_pvalue"].iloc[0])
            r12 = float(acf(res, nlags=12, fft=False)[12])
            lines.append(f"{spec['country']:<8}{spec['series_id']:<14}{label:<10}{len(mm_):>7}{mm_[0] + '..' + mm_[-1]:>24}"
                         f"{lb:>11.4f}{r12:>15.4f}{2 / np.sqrt(T):>13.4f}")
        lines.append(f"         (longest contiguous run of {spec['series_id']}: {n} months, {months[0]}..{months[-1]}; "
                     f"series spans {min(obs)}..{max(obs)})")
    print("\n".join(lines))
    if a.out:
        Path(a.out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

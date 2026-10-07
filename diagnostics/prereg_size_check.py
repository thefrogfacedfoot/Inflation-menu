#!/usr/bin/env python3
"""Size check for the pre-registered tests (docs/preregistration.md §5.2, §9 item 1).

SIMULATED data only. Under a true null (the lagged index does not enter the CPI
equation) it reports the rejection rate at 5% of
  * the country-level Freedman-Lane block-permutation test,
  * the asymptotic F test (for reference),
  * the panel Dumitrescu-Hurlin test (bootstrap p, Z-tilde and W-bar),
at n = 36 and n = 100 levels, for the primary scheme and, with --recursive, the
registered fallback. A scheme must have its rate inside [0.03, 0.07] at both n,
else the fallback replaces it (§5.2).

DGP per country: seasonal means (12 month effects, sd 0.5), AR(1) y (0.4) and x
(0.5) with contemporaneous innovation correlation 0.3 (allowed under
noncausality); panel countries share a common AR(1) factor loading 0.6 on both
x and y (cross-sectional dependence). x never enters y's equation.

Usage: python3 diagnostics/prereg_size_check.py --reps 2000 --seed 20261008 [--recursive] [--out FILE]
"""
import argparse
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import prereg_analysis as pa  # noqa: E402

warnings.filterwarnings("ignore")
ALPHA = 0.05


def gen_country(rng, n, common=None, load=0.6):
    """Levels for index and CPI (n months from 2018-01) under the null."""
    mu_y, mu_x = rng.normal(0, 0.5, 12), rng.normal(0, 0.5, 12)
    L = np.linalg.cholesky(np.array([[1.0, 0.3], [0.3, 1.0]]))
    e = rng.normal(size=(n, 2)) @ L.T
    y = np.zeros(n)
    x = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.4 * y[t - 1] + e[t, 0]
        x[t] = 0.5 * x[t - 1] + e[t, 1]
    moy = (np.arange(n) + 0) % 12
    y = y + mu_y[moy] + (load * common if common is not None else 0)
    x = x + mu_x[moy] + (load * common if common is not None else 0)
    idx = pd.period_range("2018-01", periods=n, freq="M")
    d_i, d_c = x[1:], y[1:]            # first difference of log level = these draws
    li = pd.Series(100 * np.exp(np.concatenate([[0], np.cumsum(d_i)]) * 0.01), index=idx)
    lc = pd.Series(100 * np.exp(np.concatenate([[0], np.cumsum(d_c)]) * 0.01), index=idx)
    return li, lc


def one_country(args):
    n, seed, B, scheme = args
    rng = np.random.default_rng(seed)
    li, lc = gen_country(rng, n)
    pr = pa.prepare("S", li, lc)
    p = pa.select_lag(pr.y, pr.x, pr.moy)["p"]
    f = pa.granger_fit(pr.y, pr.x, pr.moy, p, lb=False)
    b = pa.block_length(f.T)
    starts = rng.integers(0, f.T, size=(B, int(np.ceil(f.T / b))))
    idx = pa.circular_blocks(starts, b, f.T, f.T)
    Fn = pa.null_F_freedman_lane(f, idx) if scheme == "freedman_lane" else pa.null_F_recursive(f, idx, 11)
    return f.p_asym < ALPHA, pa.perm_p(f.F, Fn) < ALPHA


def one_panel(args):
    n, seed, B, scheme, N = args
    rng = np.random.default_rng(seed)
    fac = np.zeros(n)
    for t in range(1, n):
        fac[t] = 0.5 * fac[t - 1] + rng.normal()
    preps = [pa.prepare(f"C{i}", *gen_country(rng, n, common=fac)) for i in range(N)]
    r = pa.panel_test(preps, B=B, seed=int(rng.integers(1 << 31)), scheme=scheme)
    return r["p_boot_Ztilde"] < ALPHA, r["p_boot_Wbar"] < ALPHA, r["p_asym_Ztilde"] < ALPHA


def rate(flags):
    a = np.asarray(flags, float)
    return a.mean(), 1.96 * np.sqrt(a.mean() * (1 - a.mean()) / len(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--B-country", type=int, default=9999)
    ap.add_argument("--B-panel", type=int, default=1999)
    ap.add_argument("--panel-N", type=int, default=4)
    ap.add_argument("--recursive", action="store_true", help="also check the registered fallback (slower, smaller B)")
    ap.add_argument("--B-recursive", type=int, default=499)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = [f"size check: reps={a.reps} seed={a.seed} alpha={ALPHA} B_country={a.B_country} "
             f"B_panel={a.B_panel} panel_N={a.panel_N}", ""]
    t0 = time.time()
    schemes = [("freedman_lane", a.B_country, a.B_panel)]
    if a.recursive:
        schemes.append(("recursive", a.B_recursive, a.B_recursive))
    with ProcessPoolExecutor() as ex:
        for scheme, Bc, Bp in schemes:
            for n in (36, 100):
                seeds = [a.seed + 1000 * n + i for i in range(a.reps)]
                res = list(ex.map(one_country, [(n, s, Bc, scheme) for s in seeds], chunksize=20))
                asym, perm = zip(*res)
                (ra, ea), (rp, ep) = rate(asym), rate(perm)
                lines.append(f"{scheme:14s} country n={n:3d} B={Bc:5d}: perm reject {rp:.4f} (±{ep:.4f}); "
                             f"asymptotic-F reject {ra:.4f} (±{ea:.4f})")
                print(lines[-1], flush=True)
                res = list(ex.map(one_panel, [(n, s + 7, Bp, scheme, a.panel_N) for s in seeds], chunksize=10))
                z, w, zasym = zip(*res)
                (rz, ez), (rw, ew), (rza, eza) = rate(z), rate(w), rate(zasym)
                lines.append(f"{scheme:14s} panel   n={n:3d} B={Bp:5d} N={a.panel_N}: Z-tilde bootstrap reject {rz:.4f} (±{ez:.4f}); "
                             f"W-bar bootstrap {rw:.4f} (±{ew:.4f}); asymptotic Z-tilde (not used) {rza:.4f} (±{eza:.4f})")
                print(lines[-1], flush=True)
    lines += ["", f"elapsed {time.time() - t0:.0f}s", "target interval for a primary scheme: [0.03, 0.07]"]
    if a.out:
        Path(a.out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

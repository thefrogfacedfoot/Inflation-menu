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

DGPs (--dgp), per country: 12 deterministic month effects, AR y and x with
contemporaneous innovation correlation 0.3 (allowed under noncausality). Panel
countries share an i.i.d. COMMON SHOCK (loading 0.6) added to both innovations,
which is cross-sectional dependence with the null still true. (An earlier
version put a serially correlated common factor into the levels; that makes
lagged x informative about y, i.e. a false null, and is not used.) x never
enters y's equation.
  base          month-effect sd 0.5, AR(y)=0.4, AR(x)=0.5
  persistent    AR(y)=0.9 (high-persistence CPI), AR(x)=0.5
  seasonal_ar12 stochastic seasonality that month dummies do NOT absorb:
                AR(y)=0.4 and AR(x)=0.5 plus a lag-12 term of 0.5 in both
(Deterministic month effects of any size are absorbed exactly by the 11
dummies, so a "bigger month effect" DGP is identical to base and tests nothing.)

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


DGPS = {"base": dict(sd=0.5, phi_y=0.4, phi_x=0.5, ar12=0.0),
        "persistent": dict(sd=0.5, phi_y=0.9, phi_x=0.5, ar12=0.0),
        "seasonal_ar12": dict(sd=0.5, phi_y=0.4, phi_x=0.5, ar12=0.5)}


def gen_country(rng, n, common=None, load=0.6, dgp="base"):
    """Levels for index and CPI (n months from 2018-01) under the null.
    common: optional i.i.d. N(0,1) array added (times load) to both innovations."""
    g = DGPS[dgp]
    mu_y, mu_x = rng.normal(0, g["sd"], 12), rng.normal(0, g["sd"], 12)
    L = np.linalg.cholesky(np.array([[1.0, 0.3], [0.3, 1.0]]))
    e = rng.normal(size=(n, 2)) @ L.T
    if common is not None:
        e = e + load * common[:, None]
    y = np.zeros(n)
    x = np.zeros(n)
    for t in range(1, n):
        y[t] = g["phi_y"] * y[t - 1] + (g["ar12"] * y[t - 12] if t >= 12 else 0.0) + e[t, 0]
        x[t] = g["phi_x"] * x[t - 1] + (g["ar12"] * x[t - 12] if t >= 12 else 0.0) + e[t, 1]
    moy = np.arange(n) % 12
    y = y + mu_y[moy]
    x = x + mu_x[moy]
    idx = pd.period_range("2018-01", periods=n, freq="M")
    li = pd.Series(100 * np.exp(np.concatenate([[0], np.cumsum(x[1:])]) * 0.01), index=idx)
    lc = pd.Series(100 * np.exp(np.concatenate([[0], np.cumsum(y[1:])]) * 0.01), index=idx)
    return li, lc


PRE = 15          # pre-window official months simulated for Option C (>= 12 needed)


def gen_window(rng, n, dgp, common=None, seasonal_lag=False):
    """Index over n months; official CPI over the same window (+ PRE earlier months for Option C)."""
    if not seasonal_lag:
        return gen_country(rng, n, common=common, dgp=dgp)
    li, lc = gen_country(rng, n + PRE, common=common, dgp=dgp)
    return li.iloc[PRE:], lc


def one_country(args):
    n, seed, B, scheme, dgp, sl = args
    rng = np.random.default_rng(seed)
    li, lc = gen_window(rng, n, dgp, seasonal_lag=sl)
    pr = pa.prepare("S", li, lc)
    yp = pr.ypre if sl else None
    p = pa.select_lag(pr.y, pr.x, pr.moy, True, yp)["p"]
    f = pa.granger_fit(pr.y, pr.x, pr.moy, p, lb=False, ypre=yp)
    b = pa.block_length(f.T)
    starts = rng.integers(0, f.T, size=(B, int(np.ceil(f.T / b))))
    idx = pa.circular_blocks(starts, b, f.T, f.T)
    Fn = pa.null_F_freedman_lane(f, idx) if scheme == "freedman_lane" else pa.null_F_recursive(f, idx, 11)
    return f.p_asym < ALPHA, pa.perm_p(f.F, Fn) < ALPHA


def one_panel(args):
    n, seed, B, scheme, N, dgp, sl = args
    rng = np.random.default_rng(seed)
    fac = rng.normal(size=n + (PRE if sl else 0))     # i.i.d. common shock
    preps = [pa.prepare(f"C{i}", *gen_window(rng, n, dgp, common=fac, seasonal_lag=sl)) for i in range(N)]
    r = pa.panel_test(preps, B=B, seed=int(rng.integers(1 << 31)), scheme=scheme, seasonal_lag=sl)
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
    ap.add_argument("--recursive-only", action="store_true", help="check only the recursive scheme")
    ap.add_argument("--B-recursive", type=int, default=499)
    ap.add_argument("--dgp", default="base", choices=sorted(DGPS))
    ap.add_argument("--seasonal-lag", action="store_true",
                    help="Option C (proposed amendment): own seasonal lag y(t-12) in the CPI equation, "
                         "from simulated pre-window official history")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = [f"size check{' (Option C: y(t-12) in the CPI equation)' if a.seasonal_lag else ''}: dgp={a.dgp} reps={a.reps} seed={a.seed} alpha={ALPHA} B_country={a.B_country} "
             f"B_panel={a.B_panel} panel_N={a.panel_N}", ""]
    t0 = time.time()
    schemes = [] if a.recursive_only else [("freedman_lane", a.B_country, a.B_panel)]
    if a.recursive or a.recursive_only:
        schemes.append(("recursive", a.B_recursive, a.B_recursive))
    with ProcessPoolExecutor() as ex:
        for scheme, Bc, Bp in schemes:
            for n in (36, 100):
                seeds = [a.seed + 1000 * n + i for i in range(a.reps)]
                res = list(ex.map(one_country, [(n, s, Bc, scheme, a.dgp, a.seasonal_lag) for s in seeds], chunksize=20))
                asym, perm = zip(*res)
                (ra, ea), (rp, ep) = rate(asym), rate(perm)
                lines.append(f"{scheme:14s} country n={n:3d} B={Bc:5d}: perm reject {rp:.4f} (±{ep:.4f}); "
                             f"asymptotic-F reject {ra:.4f} (±{ea:.4f})")
                print(lines[-1], flush=True)
                res = list(ex.map(one_panel, [(n, s + 7, Bp, scheme, a.panel_N, a.dgp, a.seasonal_lag) for s in seeds], chunksize=10))
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

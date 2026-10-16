#!/usr/bin/env python3
"""H3 intersection-union test (IUT) vs h = 2 only, on synthetic data (prereg revision 3).

IUT: H3 is rejected only if BOTH the h = 2 and the h = 1 hawker-contrast tests reject, each at
alpha = 0.0167 with the always-calibrated critical value (§5.5, D2-b). Gate: the h = 2 gate
c_cal - q10 <= |Delta| (§5.3, D1-b). Both horizons are computed from the same simulated series.

Outputs (analysis/simulation/output/prereg_v3/):
  iut_power_no_bump.csv   power at rho = 1 and size, phi in {0, 0.6, 0.9}
  iut_cny_scenarios.csv   size (rho = 0) and power (rho = 1) under the A3 CNY bump scenarios
Seeds: SeedSequence([20261016, 21, 5, k]) (no-bump, k = phi index) and [20261016, 21, 6, k] (scenarios).

Usage: python3 analysis/simulation/prereg_v3_iut.py [--reps 20000]
"""
import argparse
import csv
import math

import numpy as np

import placebo_mc as pm
import prereg_v3_checks as v3

OUT = v3.OUT
DELTA = math.log(1.08 / 1.07)
R_GRID = np.geomspace(1.5, 20, 160)


def both(sp2, sp1, t2, t1, x, r):
    d2 = v3.decide(sp2, t2, x, shift=r)
    d1 = v3.decide(sp1, t1, x, shift=r)
    rej2 = d2["Za"] > d2["c_alt"]
    rej1 = d1["Za"] > d1["c_alt"]
    gate = (d2["c_alt"] - np.quantile(d2["Zp"], 0.10, axis=1))  # in sigma units; passes iff <= |Delta|/sigma
    return rej2, rej2 & rej1, gate, d2, d1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    sp2, sp1 = [s for s in v3.specs() if s.code in (21, 22)]
    t2, t1 = v3.calibration_table(sp2), v3.calibration_table(sp1)

    rows, r50_phi0 = [], None
    for k, phi in enumerate((0.0, 0.6, 0.9)):
        rng = np.random.default_rng(np.random.SeedSequence([v3.BASE_SEED, 21, 5, k]))
        x = pm.simulate_x(rng, a.reps, sp2.lay.length, phi)
        size2, sizeI, gate, d2, d1 = both(sp2, sp1, t2, t1, x, 0.0)
        # power at rho = 1 for every r = |Delta|/sigma: Za shifts by r at both horizons
        D2 = d2["c_alt"] - d2["Za"]
        D1 = d1["c_alt"] - d1["Za"]
        pw2, pwI, cond2, condI, ppass = [], [], [], [], []
        for r in R_GRID:
            r2, r1 = D2 < r, D1 < r
            ps = gate <= r
            pw2.append(r2.mean()); pwI.append((r2 & r1).mean()); ppass.append(ps.mean())
            cond2.append(r2[ps].mean() if ps.sum() >= 500 else np.nan)
            condI.append((r2 & r1)[ps].mean() if ps.sum() >= 500 else np.nan)
        pw2, pwI, cond2, condI, ppass = map(np.array, (pw2, pwI, cond2, condI, ppass))
        k50 = int(np.argmin(abs(ppass - 0.5)))
        if phi == 0.0:
            r50_phi0 = float(R_GRID[k50])
        rows.append({"phi": phi, "N_h2": sp2.N, "N_h1": sp1.N,
                     "size_h2_only": round(float(size2.mean()), 5), "size_IUT": round(float(sizeI.mean()), 5),
                     "r_gate_pass_50pct": round(float(R_GRID[k50]), 2),
                     "sigma_at_that_r_logpts": round(DELTA / float(R_GRID[k50]), 5),
                     "power_rho1_h2_only_at_r50": round(float(pw2[k50]), 3),
                     "power_rho1_IUT_at_r50": round(float(pwI[k50]), 3),
                     "min_P(reject|gate passes)_h2_only": round(float(np.nanmin(cond2)), 3),
                     "min_P(reject|gate passes)_IUT": round(float(np.nanmin(condI)), 3),
                     "reps": a.reps})
    v3.write_csv(OUT / "iut_power_no_bump.csv", rows)

    # CNY scenarios at phi = 0 and sigma at the h = 2 gate's 50% point
    sigma = DELTA / r50_phi0
    srows = []
    k = 0
    for timing in ("CNY month", "run-up (CNY-15d)"):
        for permanent in (False, True):
            for b in (-0.01, -0.005, -0.0025, 0.0, 0.0025, 0.005, 0.01):
                rng = np.random.default_rng(np.random.SeedSequence([v3.BASE_SEED, 21, 6, k])); k += 1
                bump = v3.cny_bump_vector(sp2, b, timing, permanent)
                x = pm.simulate_x(rng, a.reps, sp2.lay.length, 0.0) + bump / sigma
                s2, sI, _, _, _ = both(sp2, sp1, t2, t1, x, 0.0)
                p2, pI, _, _, _ = both(sp2, sp1, t2, t1, x, DELTA / sigma)
                srows.append({"timing": timing, "bump": "permanent" if permanent else "temporary (1 month)",
                              "hawker_bump_logpts": b, "sigma_logpts": round(sigma, 5),
                              "size_h2_only": round(float(s2.mean()), 5), "size_IUT": round(float(sI.mean()), 5),
                              "power_rho1_h2_only": round(float(p2.mean()), 3), "power_rho1_IUT": round(float(pI.mean()), 3),
                              "reps": a.reps})
    v3.write_csv(OUT / "iut_cny_scenarios.csv", srows)
    print("done")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Size and power under misspecified noise, SYNTHETIC DATA ONLY (calendar labels only).

Every calibrated critical value assumes Gaussian AR(1) noise. Here the noise is something else,
and four tests are compared on the same draws:
  ours_registered  prereg §5.5 (Kendall phi_hat + raw 75-point table)
  ours_revised     method_fixes.py (indirect-inference phi_hat + smoothed dense table)
  conformal        CWZ window-sum statistic (benchmark_mc.py)
  conformal_lvl    CWZ level-gap statistic (benchmark_mc.py)
  rank             uncalibrated rank test (prereg-v2), as a distribution-free reference

Cells: UK-E3, UK-E4, UK-E1 (h = 2), H3 hawker contrast h = 2 and h = 1, dish arm h = 2, and the
H3 IUT (h = 2 and h = 1 on the same draws).

DGPs (stochastic part scaled to marginal sd 1, so r = |Delta|/sigma keeps its meaning):
  ref     Gaussian AR(1), phi = 0.3 (inside the calibration model; reference)
  ar2     Gaussian AR(2), (0.5, 0.3); lag-1 autocorrelation 0.71
  sar12   Gaussian (1 - 0.3B)(1 - 0.5B^12) seasonal AR
  t3      AR(1) phi = 0.3 with t(3) innovations (scaled to unit variance)
  spike   AR(1) phi = 0.3 plus N(0, 2) added to x at the event month: Var(x_e) = 3
  meanbrk AR(1) phi = 0.3 plus +0.5 sd added to every x from the middle month of the series on
          (a break in the drift; a level-break in the inflation rate)
  lvlstep AR(1) phi = 0.3 plus a one-off +5 sd step in the LEVEL at the middle month of the series
          (first retained month at or after the midpoint)

Requires output/method_fixes/tables.csv (run method_fixes.py first).
Seeds: SeedSequence([20261026, group, dgp_index]).
Usage: python3 analysis/simulation/misspec_mc.py [--reps 20000]
"""
import argparse
import math
import time

import numpy as np

import benchmark_mc as bm
import method_fixes as mfx
import placebo_mc as pm
import prereg_v3_checks as v3

ALPHA = pm.ALPHA
SEED = 20261026
CELLS = (11, 12, 13, 21, 22, 23)
METHODS = ("ours_registered", "ours_revised", "conformal", "conformal_lvl", "rank")
R_POWER = (3.0, 4.7622, 6.0, 7.5595)
SHIFTS = np.array([0.0] + sorted({rho * r for r in R_POWER for rho in (0.5, 1.0)}))
OUT = bm.OUT.parent / "misspec"
SAR = [0.3] + [0.0] * 10 + [0.5, -0.15]
DGPS = {
    "ref": dict(ar=[0.3], label="Gaussian AR(1) 0.3 (reference)"),
    "ar2": dict(ar=[0.5, 0.3], label="Gaussian AR(2) (0.5, 0.3)"),
    "sar12": dict(ar=SAR, label="seasonal AR (1-0.3B)(1-0.5B^12)"),
    "t3": dict(ar=[0.3], t3=True, label="AR(1) 0.3, t(3) innovations"),
    "spike": dict(ar=[0.3], spike=True, label="AR(1) 0.3, Var(x) x3 in event month"),
    "meanbrk": dict(ar=[0.3], meanbrk=0.5, label="AR(1) 0.3, +0.5 sd drift break at mid-sample"),
    "lvlstep": dict(ar=[0.3], lvlstep=5.0, label="AR(1) 0.3, +5 sd level step at mid-sample"),
}


def ar_sd(a, K=5000):
    psi = np.zeros(K)
    psi[0] = 1.0
    for k in range(1, K):
        psi[k] = sum(a[j] * psi[k - 1 - j] for j in range(len(a)) if k - 1 - j >= 0)
    return math.sqrt((psi ** 2).sum())


def simulate(rng, R, sp, d, burn=300):
    a = d["ar"]
    L = sp.lay.length + burn
    z = rng.standard_t(3, (R, L)) / math.sqrt(3) if d.get("t3") else rng.standard_normal((R, L))
    e = np.zeros((R, L))
    for t in range(len(a), L):
        e[:, t] = sum(a[j] * e[:, t - 1 - j] for j in range(len(a)) if a[j]) + z[:, t]
    x = e[:, burn:] / ar_sd(a)
    ev = sp.lay.anchors[0] + 1
    mid = sp.lay.length // 2
    if d.get("spike"):
        x[:, ev] += math.sqrt(2) * rng.standard_normal(R)
    if d.get("meanbrk"):
        x[:, mid:] += d["meanbrk"]
    if d.get("lvlstep"):
        t = mid
        while not sp.xok[t]:
            t += 1
        x[:, t] += d["lvlstep"]
    return x


def margins(sp, tb, confs, x):
    C, Za, Zp, _ = mfx.variants(sp, tb, x, 0.0)
    out = {"ours_registered": (Za - C["registered"])[None, :] + SHIFTS[:, None],
           "ours_revised": (Za - C["revised"])[None, :] + SHIFTS[:, None]}
    out["rank"] = (Za - pm.crit_value(Zp, pm.kcrit(sp.N)))[None, :] + SHIFTS[:, None]
    out["conformal"] = confs[0].margins(x, SHIFTS)
    out["conformal_lvl"] = confs[1].margins(x, SHIFTS)
    return out


def rows_for(cell, dgp, M, reps):
    size, power = [], []
    for m in METHODS:
        rej = M[m] > 0
        q = np.quantile(M[m][0], 1 - ALPHA)
        rate = float(rej[0].mean())
        s = math.sqrt(max(rate * (1 - rate), 1e-12) / reps)
        size.append({"cell": cell, "dgp": dgp, "dgp_label": DGPS[dgp]["label"], "method": m, "size": round(rate, 5),
                     "mc_se": round(s, 5), "over_rejects": rate - 2 * s > ALPHA, "reps": reps})
        for rho in (0.5, 1.0):
            for r in R_POWER:
                i = int(np.argmin(abs(SHIFTS - rho * r)))
                power.append({"cell": cell, "dgp": dgp, "method": m, "rho": rho, "r": r,
                              "power": round(float(rej[i].mean()), 5),
                              "power_size_adj": round(float((M[m][i] > q).mean()), 5)})
    return size, power


def holds_summary(size):
    out = []
    for dgp in DGPS:
        for m in METHODS:
            v = [s for s in size if s["dgp"] == dgp and s["method"] == m]
            bad = [s["cell"] for s in v if s["over_rejects"]]
            out.append({"dgp": dgp, "dgp_label": DGPS[dgp]["label"], "method": m,
                        "cells_holding_size": f"{len(v) - len(bad)}/{len(v)}",
                        "max_size": max(s["size"] for s in v), "min_size": min(s["size"] for s in v),
                        "over_rejecting_cells": "; ".join(bad)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sps = {sp.code: sp for sp in v3.specs() if sp.code in CELLS}
    tabs = {c: mfx.Tables.load(sp) for c, sp in sps.items()}
    confs = {c: (bm.Conformal(sp), bm.Conformal(sp, level=True)) for c, sp in sps.items()}
    size, power = [], []
    for k, (dgp, d) in enumerate(DGPS.items()):
        keep = {}
        for c, sp in sps.items():
            group = 21 if c == 22 else c
            x = simulate(np.random.default_rng(np.random.SeedSequence([SEED, group, k])), a.reps, sp, d)
            M = margins(sp, tabs[c], confs[c], x)
            s, p = rows_for(sp.name, dgp, M, a.reps)
            size += s
            power += p
            if c in (21, 22):
                keep[c] = M
        s, p = rows_for("SG-E1 hawker IUT h=2 & h=1 (H3)", dgp, {m: np.minimum(keep[21][m], keep[22][m]) for m in METHODS}, a.reps)
        size += s
        power += p
        print(f"  {dgp} done ({time.time() - t0:.0f}s)")
    v3.write_csv(OUT / "size.csv", size)
    v3.write_csv(OUT / "power.csv", power)
    v3.write_csv(OUT / "holds_size_summary.csv", holds_summary(size))
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} seed={SEED} alpha={ALPHA} numpy={np.__version__} elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

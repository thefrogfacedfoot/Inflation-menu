#!/usr/bin/env python3
"""Numerical checks behind docs/math_claims.md, SYNTHETIC DATA ONLY (calendar labels only).

C1  phi_hat_bias.csv   bias of the §5.5 phi_hat (calendar-month demeaned, no-intercept LS on
                       the retained pairs) and of the Kendall-corrected phi_hat + (1 + 3 phi_hat)/n,
                       against the Kendall approximation E[phi_hat] - phi ~ -(1 + 3 phi)/n.
C2  u_variance.csv     EXACT (no Monte Carlo) covariance of (U_event, U_placebo) under stationary
                       AR(1) monthly changes: Sigma_U = W Gamma_T W'. Reports how far the event's
                       variance and the placebo variances/correlations are from equal, which is
                       what exchangeability of the rank test needs.
C3  q10_bound.csv      P(U_event <= q10(placebo)) under the null against its exchangeable-case
                       bounds [(j+1)/(N+1), (j+2)/(N+1)], j = floor(0.1 (N - 1)) (numpy linear
                       quantile). This probability is the slack term of the gate's power bound.

Seeds: SeedSequence([20261024, code, 9, phi_index]).
Usage: python3 analysis/simulation/claims_checks.py [--reps 20000]
"""
import argparse
import math

import numpy as np

import benchmark_mc as bm
import placebo_mc as pm
import prereg_v3_checks as v3

OUT = bm.OUT.parent / "claims"


def gamma_T(nA, h, phi):
    """Cov(T_m, T_m') for T_m = x_{m+1} + ... + x_{m+h}, x stationary AR(1) with unit variance."""
    lags = np.arange(-(nA + h), nA + h + 1)
    gx = phi ** np.abs(lags) if phi != 0 else (lags == 0).astype(float)
    g = np.array([sum(gx[(d + i - j) + nA + h] for i in range(h) for j in range(h)) for d in range(nA)])
    k = np.abs(np.arange(nA)[:, None] - np.arange(nA)[None, :])
    return g[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sets = bm.settings()
    bias, var, q10 = [], [], []
    for sp, _ in sets:
        n = int(sp.pair.sum())
        W = sp.lay.W
        for pi, phi in enumerate(pm.PHIS):
            S = W @ gamma_T(W.shape[1], sp.h, phi) @ W.T
            v = np.diag(S)
            C = S / np.sqrt(np.outer(v, v))
            P = C[1:, 1:][~np.eye(len(v) - 1, dtype=bool)]
            var.append({"setting": sp.name, "h": sp.h, "N": sp.N, "event_neighbours": sp.nb, "phi": phi,
                        "var_event": round(float(v[0]), 5),
                        "var_placebo_min": round(float(v[1:].min()), 5),
                        "var_placebo_median": round(float(np.median(v[1:])), 5),
                        "var_placebo_max": round(float(v[1:].max()), 5),
                        "event_over_median_placebo": round(float(v[0] / np.median(v[1:])), 4),
                        "corr_event_placebo_maxabs": round(float(np.abs(C[0, 1:]).max()), 4),
                        "corr_placebo_pairs_min": round(float(P.min()), 4),
                        "corr_placebo_pairs_max": round(float(P.max()), 4)})
            if phi < 0:
                continue
            rng = np.random.default_rng(np.random.SeedSequence([bm.BASE_SEED, sp.code, 9, pi]))
            x = pm.simulate_x(rng, a.reps, sp.lay.length, phi)
            ph = sp.phi_hat(x)
            bc = ph + (1 + 3 * ph) / n
            bias.append({"setting": sp.name, "h": sp.h, "n_pairs": n, "phi": phi,
                         "mean_phi_hat": round(float(ph.mean()), 4), "bias_phi_hat": round(float(ph.mean() - phi), 4),
                         "kendall_predicted_bias": round(-(1 + 3 * phi) / n, 4),
                         "mean_phi_hat_bc": round(float(bc.mean()), 4), "bias_phi_hat_bc": round(float(bc.mean() - phi), 4),
                         "sd_phi_hat": round(float(ph.std()), 4), "mc_se_mean": round(float(ph.std() / math.sqrt(a.reps)), 4),
                         "reps": a.reps})
            Z = sp.lay.tstar(x)
            p = float((Z[:, 0] <= np.quantile(Z[:, 1:], 0.10, axis=1)).mean())
            j = math.floor(0.10 * (sp.N - 1))
            lo, hi = (j + 1) / (sp.N + 1), (j + 2) / (sp.N + 1)
            q10.append({"setting": sp.name, "h": sp.h, "N": sp.N, "event_neighbours": sp.nb, "phi": phi,
                        "P_event_le_q10": round(p, 5), "mc_se": round(math.sqrt(p * (1 - p) / a.reps), 5),
                        "exchangeable_lower": round(lo, 5), "exchangeable_upper": round(hi, 5),
                        "above_upper_by_2se": p - 2 * math.sqrt(p * (1 - p) / a.reps) > hi, "reps": a.reps})
    v3.write_csv(OUT / "phi_hat_bias.csv", bias)
    v3.write_csv(OUT / "u_variance.csv", var)
    v3.write_csv(OUT / "q10_bound.csv", q10)
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} base_seed={bm.BASE_SEED} numpy={np.__version__}\n")
    print("done ->", OUT)


if __name__ == "__main__":
    main()

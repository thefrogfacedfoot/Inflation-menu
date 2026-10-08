#!/usr/bin/env python3
"""Simulated minimum detectable effect (MDE) for the pre-registered Granger test.

Simulation only: no project data, no index values. Pure standard library.

Design (docs/preregistration.md, section 3): n = 36 monthly levels -> 35 first
differences; a VAR(p) equation has T = 35 - p observations and a constant, 11
month dummies, p own lags and p lags of the tested regressor (residual df =
T - (12 + 2p)). Regressors are iid N(0,1), errors iid N(0,1). The tested
block's effect is spread equally over its p lags. Effect size is the
population partial R^2 of the block, f2 / (1 + f2) with f2 = sum(beta^2).
The test is the joint F test of the p lag coefficients at alpha = 0.05.

Usage: python3 diagnostics/mde_simulation.py [reps] [seed]
Prints power per partial R^2 and the interpolated MDE at 80% power per lag.
"""
import math
import random
import sys

# 5% critical values of F(p, residual df) for T = 35 - p (standard tables).
CRIT = {1: 4.351, 2: 3.592, 3: 3.344}
R2_GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70]


def rss(X, y):
    n, k = len(X), len(X[0])
    A = [[sum(X[r][i] * X[r][j] for r in range(n)) for j in range(k)] for i in range(k)]
    b = [sum(X[r][i] * y[r] for r in range(n)) for i in range(k)]
    for i in range(k):
        piv = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        b[i], b[piv] = b[piv], b[i]
        for r in range(i + 1, k):
            f = A[r][i] / A[i][i]
            for c in range(i, k):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    beta = [0.0] * k
    for i in range(k - 1, -1, -1):
        beta[i] = (b[i] - sum(A[i][j] * beta[j] for j in range(i + 1, k))) / A[i][i]
    return sum((y[r] - sum(X[r][i] * beta[i] for i in range(k))) ** 2 for r in range(n))


def power(p, r2, reps, rng):
    T = 35 - p
    f2 = r2 / (1 - r2)
    beta = math.sqrt(f2 / p)
    hits = 0
    for _ in range(reps):
        X0, X1, y = [], [], []
        for t in range(T):
            dummies = [1.0 if t % 12 == m else 0.0 for m in range(11)]
            own = [rng.gauss(0, 1) for _ in range(p)]
            lag = [rng.gauss(0, 1) for _ in range(p)]
            base = [1.0] + dummies + own
            X0.append(base)
            X1.append(base + lag)
            y.append(beta * sum(lag) + rng.gauss(0, 1))
        r0, r1 = rss(X0, y), rss(X1, y)
        df2 = T - len(X1[0])
        hits += ((r0 - r1) / p) / (r1 / df2) > CRIT[p]
    return hits / reps, T - (12 + 2 * p)


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261007
    rng = random.Random(seed)
    print(f"reps={reps} seed={seed} alpha=0.05")
    for p in (1, 2, 3):
        pts = []
        for r2 in R2_GRID:
            pw, df2 = power(p, r2, reps, rng)
            pts.append((r2, pw))
            print(f"lag {p} residual_df {df2} partial_R2 {r2:.2f} power {pw:.3f}")
        mde = None
        for (a, pa), (b, pb) in zip(pts, pts[1:]):
            if pa < 0.8 <= pb:
                mde = a + (0.8 - pa) * (b - a) / (pb - pa)
                break
        print(f"lag {p} SIMULATED MDE at 80% power: partial R2 = {mde:.3f}\n" if mde else f"lag {p}: 80% not bracketed\n")


if __name__ == "__main__":
    main()

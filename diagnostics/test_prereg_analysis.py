#!/usr/bin/env python3
"""Unit tests for prereg_analysis.py. SIMULATED data only; never reads project data.

Run: python3 diagnostics/test_prereg_analysis.py   (needs numpy/pandas/scipy/statsmodels)
"""
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import prereg_analysis as pa  # noqa: E402

warnings.filterwarnings("ignore")
rng = np.random.default_rng(11)


def sim_levels(n, start="2018-01", seed=0, gap_at=None, scale=0.01):
    r = np.random.default_rng(seed)
    d = r.normal(size=(2, n))
    for t in range(1, n):
        d[0, t] += 0.4 * d[0, t - 1]
        d[1, t] += 0.4 * d[1, t - 1]
    idx = pd.period_range(start, periods=n, freq="M")
    li = pd.Series(100 * np.exp(np.cumsum(d[0]) * scale), index=idx)
    lc = pd.Series(100 * np.exp(np.cumsum(d[1]) * scale), index=idx)
    if gap_at is not None:
        li = li.drop(idx[gap_at])
    return li, lc


# ── transform / alignment ──
s = pd.Series([100.0, 101, 102, 104], index=pd.PeriodIndex(["2020-01", "2020-02", "2020-04", "2020-05"], freq="M"))
d = pa.log_diff(s)
assert abs(d["2020-02"] - np.log(101 / 100)) < 1e-15 and np.isnan(d["2020-03"]) and np.isnan(d["2020-04"]), "no diff across a missing month"
assert abs(d["2020-05"] - np.log(104 / 102)) < 1e-15

v = pd.Series([True, True, False, True, True, False], index=pd.period_range("2020-01", periods=6, freq="M"))
st, ln = pa.longest_run(v)
assert (str(st), ln) == ("2020-01", 2), "tie -> earliest run"

li, lc = sim_levels(60, gap_at=20)            # index missing month 20 -> longest run is 39 months (21..59)
pr = pa.prepare("T", li, lc)
assert pr.n == 39 and str(pr.months[0]) == "2019-10", (pr.n, pr.months[0])
assert len(pr.x) == pr.n - 1 and len(pr.y) == pr.n - 1

# ── registered degrees of freedom: n=36 levels -> T=35-p; params 1+11+2p ──
li, lc = sim_levels(36, seed=1)
pr = pa.prepare("T", li, lc)
assert pr.n == 36
for p, df in ((1, 20), (2, 17), (3, 14)):
    f = pa.granger_fit(pr.y, pr.x, pr.moy, p, lb=False)
    assert f.T == 35 - p and f.df2 == df, (p, f.T, f.df2)

# ── F matches statsmodels' Granger test when dummies are off ──
from statsmodels.tsa.stattools import grangercausalitytests  # noqa: E402
for p in (1, 2, 3):
    f = pa.granger_fit(pr.y, pr.x, pr.moy, p, dummies=False, lb=False)
    sm = grangercausalitytests(np.column_stack([pr.y, pr.x]), maxlag=p, verbose=False)[p][0]["ssr_ftest"]
    assert abs(f.F - sm[0]) < 1e-8 and abs(f.p_asym - sm[1]) < 1e-10, (p, f.F, sm)
    assert abs(f.W - p * sm[0]) < 1e-7          # per-country DH Wald = K * F

# ── Freedman-Lane F* equals brute-force OLS on y* = yhat_r + e* ──
f = pa.granger_fit(pr.y, pr.x, pr.moy, 2, lb=False)
idx = pa.circular_blocks(rng.integers(0, f.T, size=(5, math.ceil(f.T / 4))), 4, f.T, f.T)
assert idx.shape == (5, f.T) and idx.min() >= 0 and idx.max() < f.T
Fs = pa.null_F_freedman_lane(f, idx)
for b in range(5):
    ys = f.yhat_r + f.e_r[idx[b]]
    eu = ys - f.Zu @ np.linalg.lstsq(f.Zu, ys, rcond=None)[0]
    er = ys - f.Zr @ np.linalg.lstsq(f.Zr, ys, rcond=None)[0]
    brute = ((er @ er - eu @ eu) / f.p) / ((eu @ eu) / f.df2)
    assert abs(Fs[b] - brute) < 1e-8 * max(1, brute), (b, Fs[b], brute)

# ── blocks: circular wrap, lengths ──
st = np.array([[8, 0]])
assert list(pa.circular_blocks(st, 3, 6, 10)[0]) == [8, 9, 0, 0, 1, 2]
assert [pa.block_length(T) for T in (10, 27, 28, 64, 65, 97, 500)] == [3, 3, 4, 4, 5, 5, 6]

# ── recursive fallback: matches a hand-rolled recursion for one draw ──
f1 = pa.granger_fit(pr.y, pr.x, pr.moy, 1, lb=False)
idx1 = pa.circular_blocks(rng.integers(0, f1.T, size=(1, math.ceil(f1.T / 3))), 3, f1.T, f1.T)
Fr = pa.null_F_recursive(f1, idx1, 11)[0]
br = np.linalg.lstsq(f1.Zr, f1.Y, rcond=None)[0]
ystar = [pr.y[0]]                                   # observed pre-sample value (p=1)
for t in range(f1.T):
    ystar.append(f1.Zr[t, :12] @ br[:12] + br[12] * ystar[-1] + f1.e_r[idx1[0, t]])
ys = np.array(ystar)
Yb = ys[1:]
Zr_b = np.column_stack([f1.Zu[:, :12], ys[:-1]])
Zu_b = np.column_stack([Zr_b, f1.Zu[:, 13:]])
eu = Yb - Zu_b @ np.linalg.lstsq(Zu_b, Yb, rcond=None)[0]
er = Yb - Zr_b @ np.linalg.lstsq(Zr_b, Yb, rcond=None)[0]
assert abs(Fr - ((er @ er - eu @ eu) / 1) / ((eu @ eu) / f1.df2)) < 1e-8

# ── multiplicity ──
from statsmodels.stats.multitest import multipletests  # noqa: E402
pv = rng.uniform(size=9)
assert np.allclose(pa.bh_qvalues(pv), multipletests(pv, method="fdr_bh")[1])
Fnull = rng.chisquare(3, size=(999, 1))
assert abs(pa.romano_wolf([5.0], Fnull)[0] - pa.perm_p(5.0, Fnull[:, 0])) < 1e-12, "K=1: RW = perm p"
Fnull = rng.chisquare(3, size=(999, 3))
rw = pa.romano_wolf([9.0, 4.0, 1.0], Fnull)
pp = [pa.perm_p(v, Fnull[:, i]) for i, v in enumerate([9.0, 4.0, 1.0])]
assert all(rw[i] >= pp[i] - 1e-12 for i in range(3)) and rw[0] <= rw[1] <= rw[2], (rw, pp)

# ── Dumitrescu-Hurlin statistics (formulas of DH 2012, restated independently) ──
W = np.array([3.1, 1.2, 5.0, 0.7]); T, K, N = 34, 2, 4
Wb = W.mean()
zbar = math.sqrt(N / (2 * K)) * (Wb - K)
zt = math.sqrt(N / (2 * K) * (T - 2 * K - 5) / (T - K - 3)) * ((T - 2 * K - 3) / (T - 2 * K - 1) * Wb - K)
o = pa.dh_stats(W, T, K)
assert abs(o["Wbar"][0] - Wb) < 1e-12 and abs(o["Zbar"][0] - zbar) < 1e-12 and abs(o["Ztilde"][0] - zt) < 1e-12
assert abs(pa.dh_stats(np.full(4, 2.0), 10_000, 2)["Ztilde"][0]) < 0.05, "W-bar = K -> Z ~ 0"

# ── D8 decision ──
dp = pa.decide_primary
assert dp(0) == "stop" and dp(1) == "country_single" and dp(2) == "country_rw" and dp(3) == "country_rw"
assert dp(4, 40) == "panel" and dp(5, 36) == "panel" and dp(4, 35) == "stop" and dp(4, None) == "stop"

# ── end to end on simulated panels (small B) ──
preps = [pa.prepare(f"C{i}", *sim_levels(48, seed=10 + i)) for i in range(4)]
fam = pa.country_family(preps, B=499, seed=1)
inc = [r for r in fam["rows"] if r["included"]]
assert len(inc) >= 1 and all(0 < r["p_perm"] <= 1 and r["p_rw"] >= r["p_perm"] - 1e-12 for r in inc)
assert all(r["lag"] in (1, 2, 3) and r["df2"] == r["T"] - (12 + 2 * r["lag"]) for r in inc)
pt = pa.panel_test(preps, B=499, seed=2)
assert pt["status"] == "ok" and pt["N"] == 4 and 0 < pt["p_boot_Ztilde"] <= 1
short = [pa.prepare("S", *sim_levels(30, seed=5))] + preps[:3]
assert pa.panel_test(short, B=99)["status"] == "stop", "common window < 36 must stop"
small = pa.country_family([pa.prepare("S", *sim_levels(30, seed=5))], B=99)
assert small["rows"][0]["included"] is False and "n=30" in small["rows"][0]["reason"]
print("ok: all prereg_analysis tests passed")

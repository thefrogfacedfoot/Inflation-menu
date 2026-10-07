#!/usr/bin/env python3
"""Export a SIMULATED balanced panel for cross-checking the DH statistics against an existing implementation.

Writes dh_check_panel.csv (id, t, y, x) with no month dummies, and prints this
module's W-bar, Z-bar and Z-tilde for lag K. In Stata:
    insheet using dh_check_panel.csv, clear
    xtset id t
    xtgcause y x, lags(K)
and compare W-bar, Z-bar, Z-bar tilde. (Stata not available here. The same CSV was checked against R plm::pgrangertest
with diagnostics/dh_check_pgrangertest.R: exact agreement, see that file.)

Usage: python3 diagnostics/dh_export_for_xtgcause.py [K] [out.csv]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import prereg_analysis as pa  # noqa: E402

K = int(sys.argv[1]) if len(sys.argv) > 1 else 2
out = sys.argv[2] if len(sys.argv) > 2 else "dh_check_panel.csv"
rng = np.random.default_rng(12345)
N, T = 6, 60
rows, Ws = ["id,t,y,x"], []
for i in range(1, N + 1):
    e = rng.normal(size=(T, 2))
    y, x = np.zeros(T), np.zeros(T)
    for t in range(1, T):
        y[t] = 0.4 * y[t - 1] + 0.15 * (i % 3) * x[t - 1] + e[t, 0]
        x[t] = 0.5 * x[t - 1] + e[t, 1]
    rows += [f"{i},{t + 1},{y[t]:.10f},{x[t]:.10f}" for t in range(T)]
    moy = (np.arange(T) % 12) + 1
    f = pa.granger_fit(y, x, moy, K, dummies=False, lb=False)
    Ws.append(f.W)
Path(out).write_text("\n".join(rows) + "\n")
o = pa.dh_stats(np.array(Ws), T - K, K)
print(f"wrote {out}; K={K} N={N} T_eff={T - K}")
print(f"W-bar={o['Wbar'][0]:.6f}  Z-bar={o['Zbar'][0]:.6f}  Z-tilde={o['Ztilde'][0]:.6f}")

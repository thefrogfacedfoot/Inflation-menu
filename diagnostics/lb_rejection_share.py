#!/usr/bin/env python3
"""Share of SIMULATED series on which the registered Ljung-Box(12) diagnostic rejects at 5%.

SIMULATED data only. For each DGP in prereg_size_check.DGPS and each n, simulate
single-country series under the null, run the registered pipeline (BIC lag
selection, VAR with constant + 11 dummies, Granger fit) and record the
Ljung-Box(12) p-values on the y equation's and x equation's residuals
(model df = 2p, as in prereg_analysis.granger_fit).

Usage: python3 diagnostics/lb_rejection_share.py --reps 2000 --seed 20261008 [--out FILE]
"""
import argparse
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prereg_analysis as pa  # noqa: E402
import prereg_size_check as sc  # noqa: E402

warnings.filterwarnings("ignore")


def one(args):
    n, seed, dgp = args
    rng = np.random.default_rng(seed)
    li, lc = sc.gen_country(rng, n, dgp=dgp)
    pr = pa.prepare("S", li, lc)
    p = pa.select_lag(pr.y, pr.x, pr.moy)["p"]
    f = pa.granger_fit(pr.y, pr.x, pr.moy, p)
    return f.lb_p_y < 0.05, f.lb_p_x < 0.05


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = [f"Ljung-Box(12) rejection share at 5%, simulated null series, reps={a.reps} seed={a.seed}", "",
             f"{'DGP':<15}{'n':>5}{'y-equation':>13}{'x-equation':>12}{'either':>9}"]
    with ProcessPoolExecutor() as ex:
        for dgp in sc.DGPS:
            for n in (36, 100):
                res = list(ex.map(one, [(n, a.seed + 1000 * n + i, dgp) for i in range(a.reps)], chunksize=20))
                ry = np.mean([r[0] for r in res]); rx = np.mean([r[1] for r in res])
                re = np.mean([r[0] or r[1] for r in res])
                lines.append(f"{dgp:<15}{n:>5}{ry:>13.4f}{rx:>12.4f}{re:>9.4f}")
                print(lines[-1], flush=True)
    if a.out:
        Path(a.out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

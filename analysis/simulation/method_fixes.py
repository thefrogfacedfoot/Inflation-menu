#!/usr/bin/env python3
"""Candidate fixes to the §5.5 calibrated test, SYNTHETIC DATA ONLY (calendar labels only).
Nothing here changes the registered procedure; it evaluates what a revision would change.

Fixes
  II      indirect-inference phi_hat: binding function b(phi) = E[phi_hat | phi] under M(phi) on the
          event's layout (the same draws as the dense table below), made nondecreasing, and
          phi_II = b^{-1}(phi_hat) by linear interpolation, clipped to [-0.50, 0.98].
          Registered alternative: Kendall, phi_hat + (1 + 3 phi_hat)/n.
  smooth  critical value t*(phi) on a dense grid (-0.50, -0.49, ..., 0.98; 149 points) with
          R_DENSE = 50,000 runs per point, smoothed by a local-linear Gaussian-kernel fit whose
          bandwidth minimises leave-one-out CV over {0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3}.
          Registered alternative: raw 75-point table, R = 20,000 (prereg_v3_checks.calibration_table).

Rule variants (critical value c = median + t* x IQR of placebo U):
  registered  Kendall phi + raw 75-point table   (prereg §5.5, D2-b)
  K+smooth    Kendall phi + smoothed table
  II+raw      II phi      + raw 75-point table
  revised     II phi      + smoothed table
  oracle+raw / oracle+smooth   true phi (infeasible; isolates phi estimation error)
  registered_altseed  Kendall + raw 75-point table rebuilt with another seed (only in the
              over-rejection diagnosis; isolates calibration-table noise)

Outputs (output/method_fixes/):
  tables.csv                 per layout and phi: raw 75-pt t*, dense raw t*, smoothed t*, b(phi), bandwidth
  phi_bias.csv               bias and RMSE of the Kendall and II phi estimates, true phi incl. off-grid
  size.csv                   size of every variant, 23 layouts x 8 true phi
  gate_conditional_size.csv  null P(reject | gate passes) on a grid of r = |Delta|/sigma (registered, revised;
                             the H3 IUT conditional on the h = 2 gate)
  gate_conditional_summary.csv  per cell: largest conditional size over r with >= 500 passing runs
  overreject_cells.csv       the five cells where the registered test over-rejected in the benchmark,
                             re-run with 100,000 fresh runs under every variant
  figures/

Seeds: dense tables SeedSequence([20261025, code, 11, k]); alt-seed raw tables [20261025, code, 12, k];
size draws [20261025, group, 13, i]; diagnosis draws [20261025, code, 14, i].
Usage: python3 analysis/simulation/method_fixes.py [--reps 20000]   (R_DENSE env var, default 50000)
"""
import argparse
import csv
import math
import os
import time

import numpy as np

import benchmark_mc as bm
import placebo_mc as pm
import prereg_v3_checks as v3

ALPHA = pm.ALPHA
SEED = 20261025
R_DENSE = int(os.environ.get("R_DENSE", 50000))
CHUNK = 25000
PHI_DENSE = np.round(np.arange(-0.50, 0.9801, 0.01), 2)
BWS = (0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3)
PHI_TRUE = (-0.5, 0.0, 0.3, 0.6, 0.8, 0.9, 0.95, 0.97)
R_GATE = np.geomspace(1.5, 20, 40)
OUT = bm.OUT.parent / "method_fixes"
OVERREJECT = [("generic N=60 edge h=1", 0.6), ("SG-E1 hawker contrast h=2 (H3)", 0.9),
              ("generic N=75 edge h=1", 0.97), ("generic N=160 edge h=1", 0.97), ("generic N=75 edge h=2", 0.97)]


# ---------------------------------------------------------------- tables
def dense_table(sp):
    """Raw dense t*(phi) and binding function b(phi) = mean phi_hat, from the same draws."""
    t_raw, bind = np.empty(len(PHI_DENSE)), np.empty(len(PHI_DENSE))
    for k, phi in enumerate(PHI_DENSE):
        rng = np.random.default_rng(np.random.SeedSequence([SEED, sp.code, 11, k]))
        ts, ph = [], []
        for _ in range(R_DENSE // CHUNK or 1):
            x = pm.simulate_x(rng, min(CHUNK, R_DENSE), sp.lay.length, float(phi))
            Z = sp.lay.tstar(x)
            ts.append(v3.tstat(Z[:, 0], Z[:, 1:])[0])
            ph.append(sp.phi_hat(x))
        t_raw[k] = np.quantile(np.concatenate(ts), 1 - ALPHA)
        bind[k] = np.concatenate(ph).mean()
    return t_raw, bind


def raw_table(sp, seed_block):
    """75-point table as prereg §5.5 but with seeds [SEED, code, seed_block, k] (alt-seed check)."""
    out = np.empty(len(v3.PHI_GRID))
    for k, phi in enumerate(v3.PHI_GRID):
        rng = np.random.default_rng(np.random.SeedSequence([SEED, sp.code, seed_block, k]))
        Z = sp.lay.tstar(pm.simulate_x(rng, v3.R_CAL, sp.lay.length, float(phi)))
        out[k] = np.quantile(v3.tstat(Z[:, 0], Z[:, 1:])[0], 1 - ALPHA)
    return out


def local_linear(x, y, bw):
    """Hat matrix of a local-linear Gaussian-kernel smoother evaluated at x."""
    H = np.empty((len(x), len(x)))
    for i, x0 in enumerate(x):
        w = np.exp(-0.5 * ((x - x0) / bw) ** 2)
        X = np.column_stack([np.ones_like(x), x - x0])
        H[i] = np.linalg.solve(X.T @ (w[:, None] * X), (X * w[:, None]).T)[0]
    return H


def smooth(x, y):
    best = None
    for bw in BWS:
        H = local_linear(x, y, bw)
        cv = float(np.mean(((y - H @ y) / (1 - np.diag(H))) ** 2))
        if best is None or cv < best[0]:
            best = (cv, bw, H @ y)
    return best[2], best[1]


class Tables:
    def __init__(self, sp, rows=None):
        """Build the tables, or load them from tables.csv rows of this layout (misspec_mc.py)."""
        self.n = int(sp.pair.sum())
        if rows is None:
            self.reg = v3.calibration_table(sp)
            self.raw, b = dense_table(sp)
            self.smooth, self.bw = smooth(PHI_DENSE, self.raw)
            self.bind = np.maximum.accumulate(b)
            return
        col = lambda c: np.array([float(r[c]) for r in rows])
        self.reg = col("t_registered_75pt")[[r["t_registered_is_gridpoint"] == "True" for r in rows]]
        self.raw, self.smooth, self.bind = col("t_dense_raw"), col("t_smoothed"), col("binding_mean_phi_hat")
        self.bw = float(rows[0]["bandwidth"])

    @staticmethod
    def load(sp):
        with open(OUT / "tables.csv") as f:
            rows = [r for r in csv.DictReader(f) if int(r["code"]) == sp.code]
        return Tables(sp, rows)

    def phi_k(self, ph):
        return ph + (1 + 3 * ph) / self.n

    def phi_ii(self, ph):
        return np.clip(np.interp(ph, self.bind, PHI_DENSE), PHI_DENSE[0], PHI_DENSE[-1])

    def t_raw75(self, phi, table=None):
        return v3.tstar_at(self.reg if table is None else table, phi)

    def t_smooth(self, phi):
        return np.interp(np.clip(phi, PHI_DENSE[0], PHI_DENSE[-1]), PHI_DENSE, self.smooth)


def variants(sp, tb, x, phi_true, alt=None):
    """variant -> (critical value c, U_a, placebo U); all variants share the draws."""
    Z = sp.lay.tstar(x)
    Za, Zp = Z[:, 0], Z[:, 1:]
    _, med, iqr = v3.tstat(Za, Zp)
    ph = sp.phi_hat(x)
    pk, pi = tb.phi_k(ph), tb.phi_ii(ph)
    po = np.full(len(x), phi_true)
    out = {"registered": tb.t_raw75(pk), "K+smooth": tb.t_smooth(pk), "II+raw": tb.t_raw75(pi),
           "revised": tb.t_smooth(pi), "oracle+raw": tb.t_raw75(po), "oracle+smooth": tb.t_smooth(po)}
    if alt is not None:
        out["registered_altseed"] = tb.t_raw75(pk, alt)
    return {k: med + v * iqr for k, v in out.items()}, Za, Zp, ph


# ---------------------------------------------------------------- studies
def se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / n)


def gate_rows(name, phi, rule, rej, G, reps):
    rows = []
    for r in R_GATE:
        ps = G <= r
        n = int(ps.sum())
        cs = float(rej[ps].mean()) if n >= 500 else None
        rows.append({"setting": name, "phi": phi, "rule": rule, "delta_over_sigma": round(float(r), 4),
                     "p_gate_pass": round(float(ps.mean()), 5), "n_pass": n,
                     "size_given_pass": "" if cs is None else round(cs, 5),
                     "se": "" if cs is None else round(se(cs, n), 5),
                     "over_rejects": "" if cs is None else cs - 2 * se(cs, n) > ALPHA, "reps": reps})
    return rows


def main_studies(sets, tabs, reps):
    size, bias, gate = [], [], []
    for i, phi in enumerate(PHI_TRUE):
        keep = {}
        for sp, group in sets:
            tb = tabs[sp.code]
            rng = np.random.default_rng(np.random.SeedSequence([SEED, group, 13, i]))
            x = pm.simulate_x(rng, reps, sp.lay.length, phi)
            C, Za, Zp, ph = variants(sp, tb, x, phi)
            for v, c in C.items():
                rate = float((Za > c).mean())
                size.append({"setting": sp.name, "h": sp.h, "N": sp.N, "event_neighbours": sp.nb, "phi": phi,
                             "variant": v, "size": round(rate, 5), "mc_se": round(se(rate, reps), 5),
                             "over_rejects": rate - 2 * se(rate, reps) > ALPHA, "reps": reps})
            for est, p in (("kendall (registered)", tb.phi_k(ph)), ("indirect inference", tb.phi_ii(ph))):
                bias.append({"setting": sp.name, "h": sp.h, "n_pairs": tb.n, "phi": phi, "estimator": est,
                             "mean": round(float(p.mean()), 4), "bias": round(float(p.mean() - phi), 4),
                             "rmse": round(float(np.sqrt(((p - phi) ** 2).mean())), 4),
                             "mc_se_mean": round(float(p.std() / math.sqrt(reps)), 4), "reps": reps})
            q10 = np.quantile(Zp, 0.10, axis=1)
            for rule in ("registered", "revised"):
                rej, G = Za > C[rule], C[rule] - q10
                gate += gate_rows(sp.name, phi, rule, rej, G, reps)
                if sp.code in (21, 22):
                    keep[(sp.code, rule)] = (rej, G)
        for rule in ("registered", "revised"):
            (r2, G2), (r1, _) = keep[(21, rule)], keep[(22, rule)]
            gate += gate_rows("SG-E1 hawker IUT h=2 & h=1 (H3), h=2 gate", phi, rule, r2 & r1, G2, reps)
        print(f"  phi={phi} done")
    return size, bias, gate


def gate_summary(gate):
    out = []
    keys = sorted({(g["setting"], g["phi"], g["rule"]) for g in gate})
    for k in keys:
        g = [x for x in gate if (x["setting"], x["phi"], x["rule"]) == k and x["size_given_pass"] != ""]
        if not g:
            continue
        m = max(g, key=lambda x: x["size_given_pass"])
        out.append({"setting": k[0], "phi": k[1], "rule": k[2], "max_size_given_pass": m["size_given_pass"],
                    "se": m["se"], "at_delta_over_sigma": m["delta_over_sigma"], "p_gate_pass_there": m["p_gate_pass"],
                    "over_rejects_anywhere": any(x["over_rejects"] for x in g),
                    "r_range_checked": f"{g[0]['delta_over_sigma']}-{g[-1]['delta_over_sigma']}"})
    return out


def overreject_study(sets, tabs, reps):
    rows = []
    byname = {sp.name: sp for sp, _ in sets}
    for i, (name, phi) in enumerate(OVERREJECT):
        sp = byname[name]
        tb = tabs[sp.code]
        alt = raw_table(sp, 12)
        rng = np.random.default_rng(np.random.SeedSequence([SEED, sp.code, 14, i]))
        acc = {}
        for _ in range(reps // CHUNK):
            x = pm.simulate_x(rng, CHUNK, sp.lay.length, phi)
            C, Za, _, ph = variants(sp, tb, x, phi, alt)
            for v, c in C.items():
                acc.setdefault(v, []).append(Za > c)
            acc.setdefault("_ph", []).append(ph)
        ph = np.concatenate(acc.pop("_ph"))
        for v, r in acc.items():
            rate = float(np.concatenate(r).mean())
            rows.append({"setting": name, "phi": phi, "variant": v, "size": round(rate, 5),
                         "mc_se": round(se(rate, reps), 5), "over_rejects": rate - 2 * se(rate, reps) > ALPHA,
                         "phi_k_mean": round(float(tb.phi_k(ph).mean()), 4),
                         "phi_ii_mean": round(float(tb.phi_ii(ph).mean()), 4),
                         "t_raw75_at_true_phi": round(float(tb.t_raw75(phi)), 4),
                         "t_altseed_at_true_phi": round(float(v3.tstar_at(alt, phi)), 4),
                         "t_smooth_at_true_phi": round(float(tb.t_smooth(phi)), 4), "reps": reps})
    return rows


# ---------------------------------------------------------------- figures
def figures(sets, tabs, bias, size):
    import make_figures as mf  # sets the Agg backend and rcParams
    import matplotlib.pyplot as plt  # noqa: E402

    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    def save(fig, stem):
        fig.savefig(fig_dir / f"{stem}.svg")
        fig.savefig(fig_dir / f"{stem}.png", dpi=300)
        plt.close(fig)

    reg = [(sp, tabs[sp.code]) for sp, _ in sets if sp.code < 30]
    fig, axs = plt.subplots(2, 4, figsize=(2.6 * mf.W, 2.4 * mf.H), sharex=True, layout="constrained")
    for ax, (sp, tb) in zip(axs.flat, reg):
        ax.plot(PHI_DENSE, tb.raw, ".", ms=1.5, color=mf.OKABE[2], label="dense raw (R = 50,000)")
        ax.plot(v3.PHI_GRID, tb.reg, "-", lw=0.7, color=mf.OKABE[1], label="registered 75-pt (R = 20,000)")
        ax.plot(PHI_DENSE, tb.smooth, "-", color=mf.OKABE[0], label=f"smoothed")
        ax.set_title(f"{sp.name}, bw = {tb.bw}", fontsize=6)
        ax.set_xlabel("φ")
    for ax in axs[:, 0]:
        ax.set_ylabel("t*(φ)")
    axs.flat[-1].axis("off")
    axs.flat[0].legend(frameon=False, fontsize=5.5, loc="lower left")
    save(fig, "critical_value_raw_vs_smoothed")

    for name, stem in (("SG-E1 hawker contrast h=2 (H3)", "phi_bias_h3_hawker_h2"), ("UK-E3 (H1)", "phi_bias_uk_e3"),
                       ("generic N=60 edge h=1", "phi_bias_generic_n60_edge_h1")):
        fig, ax = plt.subplots(figsize=(mf.W, mf.H))
        for j, est in enumerate(("kendall (registered)", "indirect inference")):
            v = [b for b in bias if b["setting"] == name and b["estimator"] == est]
            ax.plot([b["phi"] for b in v], [b["bias"] for b in v], color=mf.OKABE[j + 1], ls=mf.STYLES[j],
                    marker="o", ms=2.5, label=est)
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_xlabel("True AR(1) coefficient, φ")
        ax.set_ylabel("Mean bias of corrected φ̂")
        ax.legend(frameon=False)
        save(fig, stem)

    for name, stem in (("SG-E1 hawker contrast h=2 (H3)", "size_variants_h3_hawker_h2"), ("UK-E1 (H1)", "size_variants_uk_e1"),
                       ("generic N=75 edge h=2", "size_variants_generic_n75_edge_h2")):
        fig, ax = plt.subplots(figsize=(mf.W, mf.H))
        for j, var in enumerate(("registered", "revised", "oracle+smooth")):
            v = [s for s in size if s["setting"] == name and s["variant"] == var]
            ax.errorbar([s["phi"] for s in v], [100 * s["size"] for s in v], yerr=[200 * s["mc_se"] for s in v],
                        color=mf.OKABE[j], ls=mf.STYLES[j], marker="o", ms=2.5, capsize=1.5, label=var)
        ax.axhline(100 * ALPHA, color="grey", lw=0.8)
        ax.set_xlabel("True AR(1) coefficient, φ")
        ax.set_ylabel("Rejection rate under null (%)")
        ax.legend(frameon=False)
        save(fig, stem)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sets = bm.settings()
    tabs = {}
    for sp, _ in sets:
        tabs[sp.code] = Tables(sp)
        print(f"  tables {sp.name}: bw={tabs[sp.code].bw} ({time.time() - t0:.0f}s)")
    v3.write_csv(OUT / "tables.csv", [
        {"setting": sp.name, "code": sp.code, "phi": float(p),
         "t_registered_75pt": round(float(np.interp(p, v3.PHI_GRID, tabs[sp.code].reg)), 7),
         "t_registered_is_gridpoint": bool(np.isclose(v3.PHI_GRID, p).any()),
         "t_dense_raw": round(float(tabs[sp.code].raw[k]), 7), "t_smoothed": round(float(tabs[sp.code].smooth[k]), 7),
         "binding_mean_phi_hat": round(float(tabs[sp.code].bind[k]), 7), "bandwidth": tabs[sp.code].bw,
         "n_pairs": tabs[sp.code].n}
        for sp, _ in sets for k, p in enumerate(PHI_DENSE)])
    size, bias, gate = main_studies(sets, tabs, a.reps)
    v3.write_csv(OUT / "size.csv", size)
    v3.write_csv(OUT / "phi_bias.csv", bias)
    v3.write_csv(OUT / "gate_conditional_size.csv", gate)
    v3.write_csv(OUT / "gate_conditional_summary.csv", gate_summary(gate))
    v3.write_csv(OUT / "overreject_cells.csv", overreject_study(sets, tabs, 100000))
    figures(sets, tabs, bias, size)
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} R_dense={R_DENSE} R_cal={v3.R_CAL} seed={SEED} alpha={ALPHA} "
                f"numpy={np.__version__} elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

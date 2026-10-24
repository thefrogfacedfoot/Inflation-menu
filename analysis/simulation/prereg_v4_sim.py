#!/usr/bin/env python3
"""End-to-end simulation of the proposed prereg revision 4, SYNTHETIC DATA ONLY (calendar labels
and CNY dates only; no outcome value is read).

Procedures compared on the same draws
  v3      registered revision 3: calibrated test (Kendall phi_hat, 75-point Gaussian table) and the
          placebo-only gate (c - q10(placebo)) / |Delta| <= 1.
  H1-v4   level-gap conformal test (benchmark_mc.Conformal(level=True)) with the SYMMETRIC gate:
          all n cyclic-shift statistics S_j, observed one included; K = floor(alpha n) - 1 (the test
          rejects iff S_obs is among the top K+1). c_pool = (K+2)-th largest of all S_j: it equals the
          test's critical value (the (K+1)-th largest of the other S_j) whenever the test rejects, and
          is never above it, so a large true effect cannot push the gate shut. (The (K+1)-th largest
          would be S_obs itself whenever the test rejects; at K = 0 the gate would then fail exactly
          when the effect is large.) Gate passes iff (c_pool - q_p(all S_j)) / h <= |Delta|/sigma
          (a step s moves S_obs by about h*s).
  H3-v4a  placebo rank test on U (no calibration) with the symmetric gate over the N+1 values
          {U_a} u {U_m}: c_pool = (K+2)-th largest pooled, K = floor(alpha(N+1)) - 1 (same reason);
          gate passes iff c_pool - q_p(pooled) <= |Delta|/sigma.
  H3-v4b  residual-bootstrap-calibrated test with a symmetric gate. Per dataset: x demeaned by calendar
          month over phi_hat's months; phi_b = Kendall-corrected phi_hat clipped to [-0.5, 0.98];
          residuals e_t = x~_t - phi_b x~_{t-1} over phi_hat's pairs, centred; B = 999 series
          x*_t = phi_b x*_{t-1} + e*_t (e* iid from the residuals, 50-month burn-in) on the layout;
          t*_boot = linear quantile at 1 - alpha of tau* = (U*_a - med)/IQR; reject iff
          tau_obs > t*_boot. Gate: c_pool = med_pool + t*_boot IQR_pool, passes iff
          c_pool - q_p(pooled) <= |Delta|/sigma.
H3 is decided by the IUT (both h = 2 and h = 1 reject), gated on the h = 2 gate, for every
procedure. Gate quantile p in {0.10 (proposed), 0.05 (alternative)}.

Cells (shared draws per series): UK series -> E3, E4, E1 (H1) and E2 (secondary, H1 rules);
SG hawker series -> h = 2 and h = 1 and the IUT (H3); dish arm h = 2 (secondary, H3 rules).
DGPs: Gaussian AR(1) phi in {-0.5, 0, 0.3, 0.6, 0.9, 0.97}; misspec_mc DGPs ar2, sar12, t3,
meanbrk, lvlstep, and spike (variance x3 at every tested event month; expected failure).

Reported (output/prereg_v4/):
  size.csv           unconditional size, and size conditional on the gate at pass rates 10/50/90%
                     (r set at the 10/50/90% quantile of the null gate statistic, so the pass
                     rate is exact)
  power.csv          by rho in {0.5, 1} and r = |Delta|/sigma: P(reject), P(gate passes),
                     P(gate passes and reject) (= P(confirmatory rejection)), P(reject | pass)
  gate_guarantee.csv min over r of P(reject at rho = 1 | gate passes) (>= 500 passing runs;
                     >= 200 for v4b), p = 0.10 and 0.05
  cny.csv            H3 under the A3 CNY scenarios
The bootstrap procedure runs on the first REPS_BOOT runs of the same draws (nested simulation).

Seeds: draws SeedSequence([20261027, group, dgp_index]); bootstrap [20261027, code, dgp_index, 99];
CNY draws [20261027, group, 50 + scenario_index].
Usage: python3 analysis/simulation/prereg_v4_sim.py [--reps 20000] [--reps-boot 6000] [--B 999]
  (the full run was split: --tag base --only <AR(1) DGPs> --skip-cny; --tag mis --only <misspec> --skip-cny;
   --tag cny --only-cny; --tag dish --dish-iut; then --merge base,mis,cny,dish)
"""
import argparse
import math
import time

import numpy as np

import benchmark_mc as bm
import method_fixes as mfx
import misspec_mc as ms
import placebo_mc as pm
import prereg_v3_checks as v3

ALPHA = pm.ALPHA
SEED = 20261027
PS = (0.10, 0.05)
R_GRID = 1.5 * 2 ** (np.arange(16) / 4)  # r = |Delta|/sigma, 1.5 ... 20.2
SHIFTS = np.concatenate([[0.0], 1.5 * 2 ** (np.arange(-4, 16) / 4)])  # rho = 0.5 uses r / 2
PASS_RATES = (0.10, 0.50, 0.90)
OUT = bm.OUT.parent / "prereg_v4"
GROUPS = {"UK": (11, (11, 12, 13, 14)), "SG hawker": (21, (21, 22)), "SG dish": (23, (23,))}
H1_CODES, H3_CODES = (11, 12, 13, 14), (21, 22, 23)
DGPS = {f"AR(1) {phi}": dict(ar=[phi], label=f"Gaussian AR(1) phi = {phi}") for phi in pm.PHIS}
DGPS.update({k: v for k, v in ms.DGPS.items() if k != "ref"})


def shift_index(s):
    return int(np.argmin(abs(SHIFTS - s)))


def simulate(rng, R, sps, d):
    """misspec_mc.simulate on the group's first layout; the variance spike goes on every tested
    event month of the group."""
    head = sps[0]
    x = ms.simulate(rng, R, head, {k: v for k, v in d.items() if k != "spike"})
    if d.get("spike"):
        for sp in sps:
            x[:, sp.lay.anchors[0] + 1] += math.sqrt(2) * rng.standard_normal(R)
    return x


# ---------------------------------------------------------------- bootstrap critical value
def boot_tcrit(sp, x, B, rng, chunk=20, burn=50):
    out = np.empty(len(x))
    n = int(sp.pair.sum())
    cm = sp.cm
    tpair = np.where(sp.pair)[0]
    for i0 in range(0, len(x), chunk):
        xc = x[i0:i0 + chunk]
        xt = xc.copy()
        for k in range(12):
            cols = (cm == k) & sp.xok
            if cols.any():
                xt[:, cm == k] -= xt[:, cols].mean(axis=1, keepdims=True)
        ph = sp.phi_hat(xc)
        phb = np.clip(ph + (1 + 3 * ph) / n, -0.5, 0.98)
        e = xt[:, tpair] - phb[:, None] * xt[:, tpair - 1]
        e -= e.mean(axis=1, keepdims=True)
        m = len(xc)
        L = sp.lay.length + burn
        idx = rng.integers(0, e.shape[1], size=(m, B, L))
        eps = np.take_along_axis(e[:, None, :].repeat(B, axis=1), idx, axis=2).reshape(m * B, L)
        phr = np.repeat(phb, B)
        xs = np.empty_like(eps)
        xs[:, 0] = eps[:, 0]
        for t in range(1, L):
            xs[:, t] = phr * xs[:, t - 1] + eps[:, t]
        Z = sp.lay.tstar(xs[:, burn:])
        tau = v3.tstat(Z[:, 0], Z[:, 1:])[0].reshape(m, B)
        out[i0:i0 + m] = np.quantile(tau, 1 - ALPHA, axis=1)
    return out


# ---------------------------------------------------------------- per-spec rejections and gates
def tstar_methods(sp, tb, x, tboot=None):
    """v3, v4a (rank) and, if tboot given, v4b (bootstrap) on the T* statistic.
    Returns method -> (rej[shift, run], {p: G[shift, run]})."""
    C, Za, Zp, _ = mfx.variants(sp, tb, x, 0.0)
    K = pm.kcrit(sp.N)
    c_rank = pm.crit_value(Zp, K)
    out = {}
    q10 = np.quantile(Zp, 0.10, axis=1)
    q05 = np.quantile(Zp, 0.05, axis=1)
    c3 = C["registered"]
    rej = Za[None, :] + SHIFTS[:, None] > c3[None, :]
    out["v3"] = (rej, {0.10: np.repeat((c3 - q10)[None, :], len(SHIFTS), 0),
                       0.05: np.repeat((c3 - q05)[None, :], len(SHIFTS), 0)})
    if tboot is not None:
        Za, Zp, c_rank = Za[:len(tboot)], Zp[:len(tboot)], c_rank[:len(tboot)]
        _, med, iqr = v3.tstat(Za, Zp)
        cb = med + tboot * iqr
    G4a = {p: np.empty((len(SHIFTS), len(Za))) for p in PS}
    G4b = {p: np.empty((len(SHIFTS), len(Za))) for p in PS}
    for k, s in enumerate(SHIFTS):
        P = np.concatenate([(Za + s)[:, None], Zp], axis=1)
        q = np.quantile(P, [0.05, 0.10, 0.25, 0.5, 0.75], axis=1)
        cp = pm.crit_value(P, K + 1)
        for p, qp in ((0.05, q[0]), (0.10, q[1])):
            G4a[p][k] = cp - qp
            if tboot is not None:
                G4b[p][k] = q[3] + tboot * (q[4] - q[2]) - qp
    out["v4a_rank"] = (Za[None, :] + SHIFTS[:, None] > c_rank[None, :], G4a)
    if tboot is not None:
        out["v4b_boot"] = (Za[None, :] + SHIFTS[:, None] > cb[None, :], G4b)
    return out


def conformal_method(sp, conf, x):
    rej = np.empty((len(SHIFTS), len(x)), bool)
    G = {p: np.empty((len(SHIFTS), len(x))) for p in PS}
    Kc = conf.K
    for k, s in enumerate(SHIFTS):
        S = conf.shift_stats(x, s)
        rej[k] = S[:, conf.w0] > pm.crit_value(np.delete(S, conf.w0, axis=1), Kc)
        cp = pm.crit_value(S, Kc + 1)
        for p in PS:
            G[p][k] = (cp - np.quantile(S, p, axis=1)) / sp.h
    return {"v4_conformal_lvl": (rej, G)}


# ---------------------------------------------------------------- summaries
def se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / max(n, 1))


def summarize(cell, dgp, method, rej, G, nmin):
    reps = rej.shape[1]
    size_rows, power_rows, guar_rows = [], [], []
    s0 = float(rej[0].mean())
    row = {"cell": cell, "dgp": dgp, "method": method, "size": round(s0, 5), "mc_se": round(se(s0, reps), 5),
           "over_rejects": s0 - 2 * se(s0, reps) > ALPHA, "reps": reps}
    for p in PS:
        for pr in PASS_RATES:
            r = float(np.quantile(G[p][0], pr))
            ps = G[p][0] <= r
            n = int(ps.sum())
            cs = float(rej[0][ps].mean())
            tag = f"p{int(p * 100):02d}_pass{int(pr * 100)}"
            row[f"cond_size_{tag}"] = round(cs, 5)
            row[f"cond_se_{tag}"] = round(se(cs, n), 5)
            row[f"cond_over_{tag}"] = cs - 2 * se(cs, n) > ALPHA
            row[f"r_at_{tag}"] = round(r, 3)
    size_rows.append(row)
    for p in PS:
        worst = None
        for rho in (0.5, 1.0):
            for r in R_GRID:
                k = shift_index(rho * r)
                ps = G[p][k] <= r
                n = int(ps.sum())
                pr = float(rej[k].mean())
                prp = float(rej[k][ps].mean()) if n else float("nan")
                power_rows.append({"cell": cell, "dgp": dgp, "method": method, "gate_p": p, "rho": rho,
                                   "r": round(float(r), 4), "power": round(pr, 5),
                                   "p_gate_pass": round(float(ps.mean()), 5),
                                   "p_pass_and_reject": round(float((ps & rej[k]).mean()), 5),
                                   "power_given_pass": round(prp, 5) if n >= nmin else "", "n_pass": n})
                if rho == 1.0 and n >= nmin and (worst is None or prp < worst[0]):
                    worst = (prp, r, float(ps.mean()), n)
        guar_rows.append({"cell": cell, "dgp": dgp, "method": method, "gate_p": p,
                          "min_power_given_pass_rho1": round(worst[0], 4) if worst else "",
                          "se": round(se(worst[0], worst[3]), 4) if worst else "",
                          "at_r": round(float(worst[1]), 3) if worst else "",
                          "p_gate_pass_there": round(worst[2], 4) if worst else "",
                          "meets_0.80": (worst[0] >= 0.80) if worst else "", "n_min": nmin})
    return size_rows, power_rows, guar_rows


# ---------------------------------------------------------------- main study
def run_dgp(k, dgp, d, sps, tabs, confs, reps, reps_boot, B, results):
    for gname, (group, codes) in GROUPS.items():
        g_sps = [sps[c] for c in codes]
        x = simulate(np.random.default_rng(np.random.SeedSequence([SEED, group, k])), reps, g_sps, d)
        per = {}
        for c in codes:
            sp = sps[c]
            if c in H1_CODES:
                M = tstar_methods(sp, tabs[c], x)
                M.pop("v4a_rank")
                M.update(conformal_method(sp, confs[c], x))
            else:
                tb = boot_tcrit(sp, x[:reps_boot], B, np.random.default_rng(np.random.SeedSequence([SEED, c, k, 99])))
                M = tstar_methods(sp, tabs[c], x, None)
                Mb = tstar_methods(sp, tabs[c], x[:reps_boot], tb)
                M["v4b_boot"] = Mb["v4b_boot"]
            per[c] = M
            for m, (rej, G) in M.items():
                out = summarize(sp.name, dgp, m, rej, G, 200 if m == "v4b_boot" else 500)
                for i, key in enumerate(("size", "power", "guarantee")):
                    results[key] += out[i]
        if gname == "SG hawker":
            for m in per[21]:
                r2, G2 = per[21][m]
                r1, _ = per[22][m]
                n = min(r2.shape[1], r1.shape[1])
                out = summarize("SG-E1 hawker IUT h=2 & h=1 (H3)", dgp, m, r2[:, :n] & r1[:, :n],
                                {p: G2[p][:, :n] for p in PS}, 200 if m == "v4b_boot" else 500)
                for i, key in enumerate(("size", "power", "guarantee")):
                    results[key] += out[i]


def dish_iut(sps, reps, results):
    """Secondary H3-dish arm under the H3 rule: rank test + symmetric gate at h = 2 and h = 1 on the
    same dish draws, IUT gated on h = 2 (v4a only; the h = 1 dish layout has no registered table).
    Draws: the same seeds as the "SG dish" group in run_dgp, so the h = 2 rows reproduce."""
    sp2 = sps[23]
    sp1 = v3.Spec(24, "SG-E1 dish arm h=1 (secondary)", pm.months((2015, 1), (2026, 8)), pm.SG_EVENTS,
                  pm.idx(2023, 1), 1, sp2.delta)
    for k, dgp in enumerate(DGPS):
        x = simulate(np.random.default_rng(np.random.SeedSequence([SEED, 23, k])), reps, [sp2], DGPS[dgp])
        per = {}
        for sp in (sp2, sp1):
            Z = sp.lay.tstar(x)
            Za, Zp = Z[:, 0], Z[:, 1:]
            K = pm.kcrit(sp.N)
            rej = Za[None, :] + SHIFTS[:, None] > pm.crit_value(Zp, K)[None, :]
            G = {p: np.empty((len(SHIFTS), reps)) for p in PS}
            for i, s in enumerate(SHIFTS):
                P = np.concatenate([(Za + s)[:, None], Zp], axis=1)
                cp = pm.crit_value(P, K + 1)
                for p in PS:
                    G[p][i] = cp - np.quantile(P, p, axis=1)
            per[sp.code] = (rej, G)
        cells = (("SG-E1 dish arm h=1 (secondary)", per[24][0], per[24][1]),
                 ("SG-E1 dish IUT h=2 & h=1 (secondary)", per[23][0] & per[24][0], per[23][1]))
        for name, rej, G in cells:
            out = summarize(name, dgp, "v4a_rank", rej, G, 500)
            for i, key in enumerate(("size", "power", "guarantee")):
                results[key] += out[i]
        print(f"  dish {dgp} done", flush=True)


def cny_study(sps, tabs, reps, reps_boot, B):
    rows = []
    sp2, sp1 = sps[21], sps[22]
    k = 0
    for permanent in (False, True):
        for sigma in (0.002, 0.004):
            for b in (-0.01, -0.005, 0.0, 0.005, 0.01):
                k += 1
                rng = np.random.default_rng(np.random.SeedSequence([SEED, 21, 50 + k]))
                x = pm.simulate_x(rng, reps, sp2.lay.length, 0.0)
                x = x + v3.cny_bump_vector(sp2, b, "CNY month", permanent) / sigma
                r = sp2.delta / sigma
                per = {}
                for sp in (sp2, sp1):
                    tb = boot_tcrit(sp, x[:reps_boot], B, np.random.default_rng(np.random.SeedSequence([SEED, sp.code, 50 + k, 99])))
                    M = tstar_methods(sp, tabs[sp.code], x, None)
                    M["v4b_boot"] = tstar_methods(sp, tabs[sp.code], x[:reps_boot], tb)["v4b_boot"]
                    per[sp.code] = M
                for m in per[21]:
                    r2, G2 = per[21][m]
                    r1, _ = per[22][m]
                    n = min(r2.shape[1], r1.shape[1])
                    for arm, rej in (("h=2", r2[:, :n]), ("IUT", r2[:, :n] & r1[:, :n])):
                        row = {"arm": arm, "bump": "permanent" if permanent else "temporary (1 month)",
                               "hawker_bump_logpts": b, "sigma_logpts": sigma, "r": round(r, 3), "method": m}
                        for rho in (0.0, 0.5, 1.0):
                            i = shift_index(rho * r) if rho else 0
                            ps = G2[0.10][i, :n] <= r
                            row[f"reject_rho{rho}"] = round(float(rej[i].mean()), 5)
                            row[f"pass_rho{rho}"] = round(float(ps.mean()), 5)
                            row[f"pass_and_reject_rho{rho}"] = round(float((ps & rej[i]).mean()), 5)
                            row[f"reject_given_pass_rho{rho}"] = round(float(rej[i][ps].mean()), 5) if ps.sum() >= 100 else ""
                        row["size_over"] = row["reject_rho0.0"] - 2 * se(row["reject_rho0.0"], n) > ALPHA
                        row["reps"] = n
                        rows.append(row)
    return rows


def merge(tags):
    import csv
    for stem in ("size", "power", "gate_guarantee", "cny", "run_info"):
        parts = [OUT / f"{stem}_{t}.{'txt' if stem == 'run_info' else 'csv'}" for t in tags]
        parts = [p for p in parts if p.exists()]
        if not parts:
            continue
        if stem == "run_info":
            (OUT / "run_info.txt").write_text("".join(f"[{p.stem}] " + p.read_text() for p in parts))
        else:
            rows = []
            for p in parts:
                with open(p) as f:
                    rows += list(csv.DictReader(f))
            v3.write_csv(OUT / f"{stem}.csv", rows)
        for p in parts:
            p.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--reps-boot", type=int, default=6000)
    ap.add_argument("--B", type=int, default=999)
    ap.add_argument("--only", default="", help="comma-separated DGP keys (default: all)")
    ap.add_argument("--skip-cny", action="store_true")
    ap.add_argument("--only-cny", action="store_true")
    ap.add_argument("--dish-iut", action="store_true", help="run only the secondary dish-arm IUT (v4a)")
    ap.add_argument("--reps-boot-cny", type=int, default=2000)
    ap.add_argument("--tag", default="", help="suffix for output files (parallel runs; merge with --merge)")
    ap.add_argument("--merge", default="", help="comma-separated tags to concatenate into the untagged files")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.merge:
        merge(a.merge.split(","))
        return
    t0 = time.time()
    sfx = f"_{a.tag}" if a.tag else ""
    sps = {sp.code: sp for sp in v3.specs()}
    tabs = {c: mfx.Tables.load(sp) for c, sp in sps.items()}
    confs = {c: bm.Conformal(sps[c], level=True) for c in H1_CODES}
    results = {"size": [], "power": [], "guarantee": []}
    keys = [] if a.only_cny else [k for k in DGPS if not a.only or k in a.only.split(",")]
    if a.dish_iut:
        dish_iut(sps, a.reps, results)
        keys, a.skip_cny = ["dish IUT"], True
    for k, dgp in enumerate(DGPS):
        if dgp in keys and not a.dish_iut:
            run_dgp(k, dgp, DGPS[dgp], sps, tabs, confs, a.reps, a.reps_boot, a.B, results)
            print(f"  {dgp} done ({time.time() - t0:.0f}s)", flush=True)
    if keys:
        v3.write_csv(OUT / f"size{sfx}.csv", results["size"])
        v3.write_csv(OUT / f"power{sfx}.csv", results["power"])
        v3.write_csv(OUT / f"gate_guarantee{sfx}.csv", results["guarantee"])
    if not a.skip_cny:
        v3.write_csv(OUT / f"cny{sfx}.csv", cny_study(sps, tabs, a.reps, a.reps_boot_cny, a.B))
    with open(OUT / f"run_info{sfx}.txt", "w") as f:
        f.write(f"reps={a.reps} reps_boot={a.reps_boot} reps_boot_cny={a.reps_boot_cny} B={a.B} seed={SEED} "
                f"alpha={ALPHA} dgps={keys} cny={not a.skip_cny} numpy={np.__version__} "
                f"elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

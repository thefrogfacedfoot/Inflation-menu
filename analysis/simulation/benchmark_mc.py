#!/usr/bin/env python3
"""Benchmark study, SYNTHETIC DATA ONLY: the registered calibrated test against three
alternatives on the same DGP grid as placebo_mc.py / prereg_v3_checks.py. The only real inputs
are calendar labels, event dates and CNY dates. No outcome value is read.

Methods (one-sided in the direction of Delta, alpha = 0.0167, Delta > 0 without loss of generality):
  ours       always-calibrated test, prereg §5.5 (D2-b): v3.decide(...)["c_alt"]
  rank       uncalibrated placebo rank test, prereg §5.2 (prereg-v2): v3.decide(...)["c_rank"]
  hac        OLS of the monthly change x_t on calendar-month dummies + an event-window dummy
             (1 for t = e, ..., e+h-1); z-test of the dummy coefficient with a Newey-West
             (Bartlett) HAC variance, lag L = floor(4 (n/100)^(2/9)), N(0, 1) critical value.
  conformal  Chernozhukov, Wuthrich & Zhu (2021, JASA), moving-block (cyclic-shift) permutations.
             Counterfactual model fitted under H0 on all retained months: x_t on calendar-month
             dummies + x_{t-1}. Statistic: sum of the residuals in the event window (q = 1, signed,
             one-sided). p = share of the n cyclic shifts with window sum >= the observed one
             (identity included); reject iff p <= alpha.
  conformal_lvl  as conformal, but the statistic targets a permanent level shift: the sum over the
             window of observed-minus-counterfactual LEVELS, the counterfactual being the multi-step
             AR(1) forecast from the month before the window. In residuals this is the weighted
             window sum sum_l w_l u_{k+l}, w_l = sum_{i=l}^{h-1} (h-i) phi^(i-l) (phi from the
             same null fit), so it stays a function of the cyclically shifted residuals. A step s at
             x_e gives h*s in expectation; the plain window sum gives s(1 - phi) at h = 2.
             At h = 1 both statistics are identical.
Sample for hac and conformal: the months phi_hat uses (every event window and, for UK, the EOHO
changes excluded) plus the tested event window. Gaps are skipped: lags use calendar distance
for hac and the compressed sequence for conformal's shifts. The gate (§5.3) is not applied.

DGP (as placebo_mc.py): Gaussian AR(1) monthly changes, marginal sd 1 (sigma units), phi in
{-0.5, 0, 0.3, 0.6, 0.9, 0.97}; layouts: generic N in {60, 75, 126, 160} x event centred / in the
first year x h in {1, 2}, and the seven registered calendar layouts of prereg_v3_checks.specs().
A pass-through rho adds rho * |Delta| / sigma to x at the event month; power is reported on a grid
of r = |Delta| / sigma at rho in {0.5, 1}. CNY: the A3 bump scenarios on the hawker and dish arms.
All four methods see the same draws in every cell (common random numbers), so differences against
`ours` have a paired MC SE.

Every margin below is "statistic minus critical value": a method rejects iff margin > 0. The
size-adjusted power uses the cell's null 1 - alpha quantile of the margin as critical value
(infeasible in practice; it isolates power from size distortion).

Seeds: draws SeedSequence([20261024, group, block, k]); calibration tables as prereg §5.5
(SeedSequence([20261016, code, 1, grid_index])), generic layouts use codes 31-46.

Usage: python3 analysis/simulation/benchmark_mc.py [--reps 20000]
Writes CSVs to analysis/simulation/output/benchmark/; figures: benchmark_figures.py.
"""
import argparse
import csv
import math
import time
from statistics import NormalDist

import numpy as np

import placebo_mc as pm
import prereg_v3_checks as v3

ALPHA = pm.ALPHA
BASE_SEED = 20261024
PHIS = pm.PHIS
SHIFTS = np.concatenate([[0.0], 0.75 * 2 ** (np.arange(16) / 3)])  # 0, 0.75 ... 24 (sigma units)
R_VALUES = SHIFTS[4:]  # r = |Delta| / sigma, 1.5 ... 24; rho = 0.5 uses SHIFTS[k - 3]
RHOS = (0.5, 1.0)
METHODS = ("ours", "rank", "hac", "conformal", "conformal_lvl")
OUT = v3.OUT.parent / "benchmark"
Z_CRIT = NormalDist().inv_cdf(1 - ALPHA)


# ---------------------------------------------------------------- settings
def generic_spec(code, n_target, h, position):
    """prereg_v3_checks.Spec for the generic layouts of placebo_mc.generic_layout."""
    start = pm.idx(2000, 1)
    for length in range(40, 600):
        e = start + 6 if position == "edge" else start + length // 2
        try:
            sp = v3.Spec(code, f"generic N={n_target} {position} h={h}", range(start, start + length),
                         [e], e, h, 1.0)
        except ValueError:
            continue
        if sp.N == n_target:
            return sp
    raise RuntimeError(f"no length gives N={n_target} ({position}, h={h})")


def settings():
    """(spec, draw group). Specs sharing a group are evaluated on identical draws."""
    out = [(sp, 21 if sp.code == 22 else sp.code) for sp in v3.specs()]
    code = 31
    for h in (1, 2):
        for pos in ("middle", "edge"):
            for n in pm.N_TARGETS:
                out.append((generic_spec(code, n, h, pos), code))
                code += 1
    return out


# ---------------------------------------------------------------- methods
class Sample:
    """Months used by hac and conformal: phi_hat's months plus the tested event window."""

    def __init__(self, sp):
        a = sp.lay.anchors[0]
        self.window = list(range(a + 1, a + 1 + sp.h))
        self.t = np.array(sorted(set(np.where(sp.xok)[0]) | set(self.window)))
        self.e = self.window[0]  # x index that carries the step
        self.cm = sp.cm[self.t]


def month_dummies(cm):
    return np.stack([(cm == k).astype(float) for k in np.unique(cm)], axis=1)


class HAC:
    def __init__(self, sp):
        s = Sample(sp)
        self.t = s.t
        n = len(s.t)
        X = np.column_stack([month_dummies(s.cm), np.isin(s.t, s.window).astype(float)])
        P = np.linalg.solve(X.T @ X, X.T)
        self.g = P[-1]  # dummy coefficient = y @ g
        self.M = np.eye(n) - X @ P  # residual maker (symmetric)
        self.L = int(4 * (n / 100) ** (2 / 9))
        lag = np.abs(s.t[:, None] - s.t[None, :])
        self.Om = np.where(lag <= self.L, 1 - lag / (self.L + 1), 0.0)
        self.pe = int(np.where(s.t == s.e)[0][0])

    def margins(self, x, shifts):
        y = x[:, self.t]
        b0, u0 = y @ self.g, y @ self.M
        out = np.empty((len(shifts), len(x)))
        for k, s in enumerate(shifts):  # the step is linear in y: update instead of refitting
            v = (u0 + s * self.M[self.pe]) * self.g
            out[k] = (b0 + s * self.g[self.pe]) / np.sqrt(((v @ self.Om) * v).sum(axis=1)) - Z_CRIT
        return out


class Conformal:
    def __init__(self, sp, level=False):
        self.level = level
        s = Sample(sp)
        have = set(s.t)
        keep = np.array([t - 1 in have for t in s.t])
        if not all(keep[np.isin(s.t, s.window)]):
            raise ValueError(f"{sp.name}: event window lacks a lag")
        self.rows = s.t[keep]
        self.e = s.e
        self.h = sp.h
        n = len(self.rows)
        D = month_dummies(s.cm[keep])
        self.Dm = np.eye(n) - D @ np.linalg.solve(D.T @ D, D.T)  # within-calendar-month demeaning
        self.w0 = int(np.where(self.rows == s.e)[0][0])
        self.n = n
        self.K = math.floor(ALPHA * n) - 1

    def margins(self, x, shifts):
        out = np.empty((len(shifts), len(x)))
        for k, s in enumerate(shifts):
            xs = x.copy()
            xs[:, self.e] += s
            y, l = xs[:, self.rows] @ self.Dm, xs[:, self.rows - 1] @ self.Dm  # Frisch-Waugh
            b = (l * y).sum(axis=1) / (l * l).sum(axis=1)
            u = y - b[:, None] * l
            S = np.zeros_like(u)  # S[:, j] = weighted sum of u over the window starting at j (cyclic)
            for j in range(self.h):
                w = sum((self.h - i) * b ** (i - j) for i in range(j, self.h)) if self.level else 1.0
                S += np.reshape(w, (-1, 1)) * np.roll(u, -j, axis=1)
            out[k] = S[:, self.w0] - pm.crit_value(np.delete(S, self.w0, axis=1), self.K)
        return out


def evaluate(sp, table, hac, conf, conf_lvl, x, shifts):
    """method -> (len(shifts), reps) margins; a method rejects iff margin > 0."""
    d = v3.decide(sp, table, x)
    return {"ours": (d["Za"] - d["c_alt"])[None, :] + shifts[:, None],
            "rank": (d["Za"] - d["c_rank"])[None, :] + shifts[:, None],
            "hac": hac.margins(x, shifts),
            "conformal": conf.margins(x, shifts),
            "conformal_lvl": conf_lvl.margins(x, shifts)}


# ---------------------------------------------------------------- summaries
def se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / n)


def over(rate, n):
    return rate - 2 * se(rate, n) > ALPHA


def cell_rows(name, h, N, nb, phi, M):
    """Size and power rows for one (setting, phi) cell; M: method -> margins on SHIFTS."""
    reps = M["ours"].shape[1]
    size, power = [], []
    rej = {m: M[m] > 0 for m in METHODS}
    q = {m: np.quantile(M[m][0], 1 - ALPHA) for m in METHODS}
    rej_sa = {m: M[m] > q[m] for m in METHODS}
    for m in METHODS:
        rate = float(rej[m][0].mean())
        size.append({"setting": name, "h": h, "N": N, "event_neighbours": nb, "phi": phi, "method": m,
                     "size": round(rate, 5), "mc_se": round(se(rate, reps), 5), "over_rejects": over(rate, reps),
                     "reps": reps})
        for rho in RHOS:
            for k, r in enumerate(R_VALUES):
                i = k + 4 if rho == 1.0 else k + 1
                pw, pws = float(rej[m][i].mean()), float(rej_sa[m][i].mean())
                dif = rej[m][i].astype(int) - rej["ours"][i]
                difs = rej_sa[m][i].astype(int) - rej_sa["ours"][i]
                power.append({"setting": name, "h": h, "N": N, "phi": phi, "method": m, "rho": rho,
                              "r": round(float(r), 4), "power": round(pw, 5),
                              "power_minus_ours": round(float(dif.mean()), 5),
                              "se_diff": round(float(dif.std() / math.sqrt(reps)), 5),
                              "power_size_adj": round(pws, 5),
                              "power_size_adj_minus_ours": round(float(difs.mean()), 5),
                              "se_diff_size_adj": round(float(difs.std() / math.sqrt(reps)), 5)})
    return size, power


def flags(size_rows, power_rows):
    """Settings where a benchmark beats ours. Kinds:
    size        ours over-rejects (rate - 2 SE > alpha) and the benchmark does not
    power       benchmark does not over-reject and its power exceeds ours by > 2 paired SE
    power_sa    size-adjusted power exceeds ours by > 2 paired SE"""
    out = []
    S = {(r["setting"], r["phi"], r["method"]): r for r in size_rows}
    for (setting, phi, m), r in S.items():
        if m == "ours":
            continue
        o = S[(setting, phi, "ours")]
        if o["over_rejects"] and not r["over_rejects"]:
            out.append({"setting": setting, "phi": phi, "benchmark": m, "kind": "size", "rho": "", "r": "",
                        "benchmark_value": r["size"], "ours_value": o["size"], "diff": round(r["size"] - o["size"], 5)})
        P = [p for p in power_rows if p["setting"] == setting and p["phi"] == phi and p["method"] == m]
        for kind, col, scol, ok in (("power", "power", "se_diff", not r["over_rejects"]),
                                    ("power_sa", "power_size_adj", "se_diff_size_adj", True)):
            if not ok:
                continue
            dcol = col + "_minus_ours"
            hits = [p for p in P if p[dcol] > 2 * p[scol] and p[dcol] > 0]
            if hits:
                b = max(hits, key=lambda p: p[dcol])
                out.append({"setting": setting, "phi": phi, "benchmark": m, "kind": kind, "rho": b["rho"], "r": b["r"],
                            "benchmark_value": b[col], "ours_value": round(b[col] - b[dcol], 5), "diff": b[dcol]})
    return out


def summary_rows(size_rows, power_rows):
    """One row per (setting, phi): sizes, and power at r80 (first r where ours has >= 0.8 at rho = 1)."""
    out = []
    keys = sorted({(r["setting"], r["phi"]) for r in size_rows}, key=lambda k: (k[0], k[1]))
    for setting, phi in keys:
        S = {r["method"]: r for r in size_rows if r["setting"] == setting and r["phi"] == phi}
        P = [p for p in power_rows if p["setting"] == setting and p["phi"] == phi]
        ours1 = [p for p in P if p["method"] == "ours" and p["rho"] == 1.0]
        hit = [p["r"] for p in ours1 if p["power"] >= 0.8]
        r80 = hit[0] if hit else None
        row = {"setting": setting, "phi": phi, "N": S["ours"]["N"], "event_neighbours": S["ours"]["event_neighbours"]}
        for m in METHODS:
            row[f"size_{m}"] = S[m]["size"]
        row["r80_ours"] = r80 if r80 is not None else ""
        for rho in RHOS:
            for m in METHODS:
                v = [p for p in P if p["method"] == m and p["rho"] == rho and p["r"] == r80]
                row[f"power_rho{rho}_{m}"] = v[0]["power"] if v else ""
                row[f"power_sa_rho{rho}_{m}"] = v[0]["power_size_adj"] if v else ""
        out.append(row)
    return out


# ---------------------------------------------------------------- studies
def draws(group, block, k, reps, length, phi):
    rng = np.random.default_rng(np.random.SeedSequence([BASE_SEED, group, block, k]))
    return pm.simulate_x(rng, reps, length, phi)


def main_study(sets, tables, tools, reps):
    size_rows, power_rows = [], []
    for pi, phi in enumerate(PHIS):
        iut = {}
        for sp, group in sets:
            x = draws(group, 1, pi, reps, sp.lay.length, phi)
            M = evaluate(sp, tables[sp.code], *tools[sp.code], x, SHIFTS)
            s, p = cell_rows(sp.name, sp.h, sp.N, sp.nb, phi, M)
            size_rows += s
            power_rows += p
            if sp.code in (21, 22):
                iut[sp.code] = M
        # H3 decision rule: reject iff both horizons reject, i.e. min margin > 0
        M = {m: np.minimum(iut[21][m], iut[22][m]) for m in METHODS}
        s, p = cell_rows("SG-E1 hawker IUT h=2 & h=1 (H3)", "2&1", "74/81", "5/5", phi, M)
        size_rows += s
        power_rows += p
        print(f"  phi={phi} done")
    return size_rows, power_rows


def cny_study(sets, tables, tools, reps):
    rows = []
    sps = {sp.code: (sp, g) for sp, g in sets if sp.code in (21, 22, 23)}
    for timing in ("CNY month", "run-up (CNY-15d)"):
        for permanent in (False, True):
            for sigma in (0.002, 0.004):
                for b in (-0.01, -0.005, -0.0025, 0.0, 0.0025, 0.005, 0.01):
                    res = {}
                    for code, (sp, group) in sps.items():
                        shifts = np.array([0.0, 0.5, 1.0]) * sp.delta / sigma
                        x = draws(group, 2, int(sigma * 1e4), reps, sp.lay.length, 0.0)
                        x = x + v3.cny_bump_vector(sp, b, timing, permanent) / sigma
                        res[code] = evaluate(sp, tables[code], *tools[code], x, shifts)
                    res["IUT"] = {m: np.minimum(res[21][m], res[22][m]) for m in METHODS}
                    for code, M in res.items():
                        arm = "SG-E1 hawker IUT h=2 & h=1 (H3)" if code == "IUT" else sps[code][0].name
                        for m in METHODS:
                            rj = M[m] > 0
                            rate = float(rj[0].mean())
                            rows.append({"arm": arm, "timing": timing,
                                         "bump": "permanent" if permanent else "temporary (1 month)",
                                         "hawker_bump_logpts": b, "sigma_contrast_logpts": sigma, "method": m,
                                         "size": round(rate, 5), "over_rejects": over(rate, reps),
                                         "power_rho0.5": round(float(rj[1].mean()), 5),
                                         "power_rho1": round(float(rj[2].mean()), 5), "reps": reps})
    return rows


def cny_flags(rows):
    """As flags(): size (ours over-rejects, benchmark does not) and power at rho = 1 / 0.5 when
    the benchmark does not over-reject (difference > 2 SE, independent-sample SE as a bound)."""
    out = []
    key = lambda r: (r["arm"], r["timing"], r["bump"], r["hawker_bump_logpts"], r["sigma_contrast_logpts"])
    O = {key(r): r for r in rows if r["method"] == "ours"}
    for r in rows:
        if r["method"] == "ours":
            continue
        o, n = O[key(r)], r["reps"]
        base = {"arm": r["arm"], "timing": r["timing"], "bump": r["bump"], "hawker_bump_logpts": r["hawker_bump_logpts"],
                "sigma_contrast_logpts": r["sigma_contrast_logpts"], "benchmark": r["method"]}
        if o["over_rejects"] and not r["over_rejects"]:
            out.append({**base, "kind": "size", "benchmark_value": r["size"], "ours_value": o["size"]})
        if not r["over_rejects"]:
            for col in ("power_rho0.5", "power_rho1"):
                d = r[col] - o[col]
                if d > 2 * math.sqrt(se(r[col], n) ** 2 + se(o[col], n) ** 2):
                    out.append({**base, "kind": col, "benchmark_value": r[col], "ours_value": o[col]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sets = settings()
    tables = {sp.code: v3.calibration_table(sp) for sp, _ in sets}
    tools = {sp.code: (HAC(sp), Conformal(sp), Conformal(sp, level=True)) for sp, _ in sets}
    print(f"calibration done {time.time() - t0:.0f}s")
    v3.write_csv(OUT / "settings.csv", [{"setting": sp.name, "code": sp.code, "h": sp.h, "N": sp.N,
                                         "event_neighbours": sp.nb, "series_months": sp.lay.length,
                                         "hac_n": len(tools[sp.code][0].t), "hac_lag": tools[sp.code][0].L,
                                         "conformal_n_shifts": tools[sp.code][1].n,
                                         "conformal_min_p": round(1 / tools[sp.code][1].n, 5)} for sp, _ in sets])
    size_rows, power_rows = main_study(sets, tables, tools, a.reps)
    v3.write_csv(OUT / "size.csv", size_rows)
    v3.write_csv(OUT / "power.csv", power_rows)
    v3.write_csv(OUT / "summary.csv", summary_rows(size_rows, power_rows))
    fl = flags(size_rows, power_rows)
    v3.write_csv(OUT / "flags.csv", fl or [{"setting": "", "note": "no flags"}])
    cr = cny_study(sets, tables, tools, a.reps)
    v3.write_csv(OUT / "cny.csv", cr)
    cf = cny_flags(cr)
    v3.write_csv(OUT / "cny_flags.csv", cf or [{"arm": "", "note": "no flags"}])
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} R_cal={v3.R_CAL} base_seed={BASE_SEED} calib_seed={v3.BASE_SEED} alpha={ALPHA} "
                f"numpy={np.__version__} elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}; {len(fl)} flags, {len(cf)} CNY flags")


if __name__ == "__main__":
    main()

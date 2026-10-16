#!/usr/bin/env python3
"""Synthetic-data checks behind prereg revision 3 (docs/preregistration_v2.md §5.3, §5.5, §9.4).
SYNTHETIC DATA ONLY: the only real inputs are calendar labels, event dates and CNY dates.

A1  MDE gate variants vs power at rho = 1 (the gate is meant to imply >= 80% power).
A2  Size-control rule: phi_hat from placebo-window monthly changes; if phi_hat >= 0.9, or the
    event has < 4 same-month neighbours, or N < 75 at h = 2, the event is tested with a
    simulation-calibrated critical value instead of the rank order statistic. Size before/after.
A3  Chinese-New-Year-like moving bump in the hawker arm of the H3 contrast: bias of rho_hat and
    size of H3 at h = 2 and h = 1.

Calibration procedure (registered in §5.5; implemented by `calibration_table` + `tstar_at`):
  statistic   t = (U_a - median(U_placebo)) / IQR(U_placebo)   (numpy linear quantiles)
  null model  Gaussian AR(1) monthly changes, marginal sd 1, on the event's exact calendar layout
  grid        phi = -0.50, -0.48, ..., 0.98 (75 points); R = 20,000 runs per point
  seeds       numpy SeedSequence([20261016, layout_code, 1, grid_index])
  critical    t*(phi) = numpy quantile (linear) of t at 1 - 0.0167
  lookup      linear interpolation in phi; phi_hat clipped to [-0.50, 0.98]
  decision    reject iff t_obs > t*(phi_hat); equivalent critical value on U:
              c = median + t* x IQR

Usage: python3 analysis/simulation/prereg_v3_checks.py [--reps 20000]
"""
import argparse
import csv
import math
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np

import placebo_mc as pm

ALPHA = pm.ALPHA
BASE_SEED = 20261016
R_CAL = int(__import__("os").environ.get("R_CAL", 20000))
PHI_GRID = np.round(np.arange(-0.50, 0.981, 0.02), 2)
OUT = Path(__file__).resolve().parent / "output" / "prereg_v3"
CNY = {2015: date(2015, 2, 19), 2016: date(2016, 2, 8), 2017: date(2017, 1, 28), 2018: date(2018, 2, 16),
       2019: date(2019, 2, 5), 2020: date(2020, 1, 25), 2021: date(2021, 2, 12), 2022: date(2022, 2, 1),
       2023: date(2023, 1, 22), 2024: date(2024, 2, 10), 2025: date(2025, 1, 29), 2026: date(2026, 2, 17)}


# ---------------------------------------------------------------- layouts with phi_hat masks
class Spec:
    def __init__(self, code, name, present, events, tested, h, delta, eoho=False):
        self.code, self.name, self.h, self.delta = code, name, h, delta
        self.lay = pm.Layout(name, present, events, [tested], h, eoho=eoho)
        s, L = self.lay.start, self.lay.length
        P = {m - s for m in present}
        bad = set()
        for e in events:  # changes inside any event window are masked (x_t for t in [e, e+h-1])
            for t in range(e - s, e - s + h):
                bad.add(t)
        if eoho:
            bad |= {pm.idx(2020, 8) - s, pm.idx(2020, 9) - s}
        ok = np.array([t >= 1 and t in P and (t - 1) in P and t not in bad for t in range(L)])
        self.xok = ok
        self.pair = np.array([t >= 2 and ok[t] and ok[t - 1] for t in range(L)])
        self.cm = (np.arange(L) + s) % 12
        self.N = self.lay.N
        self.nb = self.lay.n_neigh_event[0]
        self.triggered_static = self.nb < 4 or (h == 2 and self.N < 75)

    def phi_hat(self, x):
        xt = x.copy()
        for k in range(12):
            cols = (self.cm == k) & self.xok
            if cols.any():
                xt[:, self.cm == k] -= xt[:, cols].mean(axis=1, keepdims=True)
        t = np.where(self.pair)[0]
        num = (xt[:, t] * xt[:, t - 1]).sum(axis=1)
        den = (xt[:, t - 1] ** 2).sum(axis=1)
        return num / den


def specs(h_sg=2):
    uk = pm.uk_months()
    ev = list(pm.UK_EVENTS.values())
    sg_ev = pm.SG_EVENTS
    lg = math.log
    return [
        Spec(11, "UK-E3 (H1)", uk, ev, pm.UK_EVENTS["E3"], 2, lg(1.125 / 1.05), eoho=True),
        Spec(12, "UK-E4 (H1)", uk, ev, pm.UK_EVENTS["E4"], 2, lg(1.20 / 1.125), eoho=True),
        Spec(13, "UK-E1 (H1)", uk, ev, pm.UK_EVENTS["E1"], 2, lg(1.20 / 1.175), eoho=True),
        Spec(14, "UK-E2 (H2/secondary)", uk, ev, pm.UK_EVENTS["E2"], 2, abs(lg(1.05 / 1.20)), eoho=True),
        Spec(21, "SG-E1 hawker contrast h=2 (H3)", pm.months((2019, 1), (2026, 8)), sg_ev, pm.idx(2023, 1), 2, lg(1.08 / 1.07)),
        Spec(22, "SG-E1 hawker contrast h=1 (secondary)", pm.months((2019, 1), (2026, 8)), sg_ev, pm.idx(2023, 1), 1, lg(1.08 / 1.07)),
        Spec(23, "SG-E1 dish arm h=2 (secondary)", pm.months((2015, 1), (2026, 8)), sg_ev, pm.idx(2023, 1), 2, lg(1.08 / 1.07)),
    ]


# ---------------------------------------------------------------- calibration
def tstat(Za, Zp):
    q25, med, q75 = np.quantile(Zp, [0.25, 0.5, 0.75], axis=1)
    return (Za - med) / (q75 - q25), med, q75 - q25


def calibration_table(sp):
    out = np.empty(len(PHI_GRID))
    for k, phi in enumerate(PHI_GRID):
        rng = np.random.default_rng(np.random.SeedSequence([BASE_SEED, sp.code, 1, k]))
        x = pm.simulate_x(rng, R_CAL, sp.lay.length, float(phi))
        Z = sp.lay.tstar(x)
        t, _, _ = tstat(Z[:, 0], Z[:, 1:])
        out[k] = np.quantile(t, 1 - ALPHA)
    return out


def tstar_at(table, phi_hat):
    return np.interp(np.clip(phi_hat, PHI_GRID[0], PHI_GRID[-1]), PHI_GRID, table)


def decide(sp, table, x, shift=0.0):
    """Returns dict of per-run arrays: rank critical value, rule critical value, triggered, Za, Zp."""
    Z = sp.lay.tstar(x)
    Za, Zp = Z[:, 0] + shift, Z[:, 1:]
    K = pm.kcrit(sp.N)
    c_rank = pm.crit_value(Zp, K)
    ph = sp.phi_hat(x)
    trig = (ph >= 0.9) | sp.triggered_static
    _, med, iqr = tstat(Za, Zp)
    c_cal = med + tstar_at(table, ph) * iqr
    c_rule = np.where(trig, c_cal, c_rank)
    # alternative (not the rule WC specified): calibrate every event, Kendall bias-corrected phi_hat
    n = int(sp.pair.sum())
    c_alt = med + tstar_at(table, ph + (1 + 3 * ph) / n) * iqr
    return dict(Za=Za, Zp=Zp, c_rank=c_rank, c_rule=c_rule, c_alt=c_alt, trig=trig, phi_hat=ph)


# ---------------------------------------------------------------- studies
PHIS_SIZE = (0.0, 0.3, 0.6, 0.9, 0.97)


def size_study(sps, tables, reps):
    rows = []
    for sp in sps:
        for i, phi in enumerate(PHIS_SIZE):
            rng = np.random.default_rng(np.random.SeedSequence([BASE_SEED, sp.code, 2, i]))
            x = pm.simulate_x(rng, reps, sp.lay.length, phi)
            d = decide(sp, tables[sp.code], x)
            before = float((d["Za"] > d["c_rank"]).mean())
            after = float((d["Za"] > d["c_rule"]).mean())
            alt = float((d["Za"] > d["c_alt"]).mean())
            se = lambda p: math.sqrt(max(p * (1 - p), 1e-12) / reps)
            rows.append({"setting": sp.name, "h": sp.h, "N": sp.N, "event_neighbours": sp.nb, "phi_true": phi,
                         "phi_hat_mean": round(float(d["phi_hat"].mean()), 3),
                         "share_triggered": round(float(d["trig"].mean()), 4),
                         "size_before_rank_test": round(before, 5), "se_before": round(se(before), 5),
                         "size_after_rule": round(after, 5), "se_after": round(se(after), 5),
                         "size_alt_always_calibrated_bc": round(alt, 5), "se_alt": round(se(alt), 5), "reps": reps})
    return rows


R_GRID = np.geomspace(1.5, 20, 160)


def gate_study(sps, tables, reps):
    rows, summ = [], []
    for sp in sps:
        for i, phi in enumerate((0.0, 0.6, 0.9)):
            rng = np.random.default_rng(np.random.SeedSequence([BASE_SEED, sp.code, 3, i]))
            x = pm.simulate_x(rng, reps, sp.lay.length, phi)
            d = decide(sp, tables[sp.code], x)
            Zp, Za = d["Zp"], d["Za"]
            q = lambda p: np.quantile(Zp, p, axis=1)
            q20 = q(0.20)
            variants = {
                "v2 registered: q95-q20 (rank test)": (q(0.95) - q20, d["c_rank"]),
                "A1 literal: q(1-a)-q20 (rank test)": (q(1 - ALPHA) - q20, d["c_rank"]),
                "A1 order stat: c_rank-q20 (rank test)": (d["c_rank"] - q20, d["c_rank"]),
                "A1+A2: c_used-q20 (rule test)": (d["c_rule"] - q20, d["c_rule"]),
                "A1+A2 calibrated: c_used-q15 (rule test)": (d["c_rule"] - q(0.15), d["c_rule"]),
                "A1+A2 calibrated: c_used-q10 (rule test)": (d["c_rule"] - q(0.10), d["c_rule"]),
                "A1+A2 calibrated: c_used-q05 (rule test)": (d["c_rule"] - q(0.05), d["c_rule"]),
                "REGISTERED D1-b+D2-b: c_cal-q10 (always-calibrated test)": (d["c_alt"] - q(0.10), d["c_alt"]),
                "D1-a+D2-b: c_cal-q20 (always-calibrated test)": (d["c_alt"] - q20, d["c_alt"]),
            }
            for vname, (G, c) in variants.items():
                D = c - Za  # reject iff r > D
                ppass, pw, cond = [], [], []
                for r in R_GRID:
                    ps = G <= r
                    rej = D < r
                    ppass.append(ps.mean()); pw.append(rej.mean())
                    cond.append(rej[ps].mean() if ps.sum() >= 500 else np.nan)
                ppass, pw, cond = map(np.array, (ppass, pw, cond))
                k50 = int(np.argmin(abs(ppass - 0.5)))
                k80 = int(np.argmax(pw >= 0.8)) if (pw >= 0.8).any() else None
                summ.append({"setting": sp.name, "phi": phi, "variant": vname,
                             "r_gate_pass_50pct": round(float(R_GRID[k50]), 2),
                             "power_rho1_at_that_r": round(float(pw[k50]), 3),
                             "r_power_80pct": round(float(R_GRID[k80]), 2) if k80 is not None else "",
                             "min_P(reject|gate passes)": round(float(np.nanmin(cond)), 3),
                             "P(gate passes) at r_power_80pct": round(float(ppass[k80]), 3) if k80 is not None else "",
                             "reps": reps})
                for r, a, b, c_ in zip(R_GRID, ppass, pw, cond):
                    rows.append({"setting": sp.name, "phi": phi, "variant": vname, "delta_over_sigma": round(float(r), 4),
                                 "p_gate_pass": round(float(a), 5), "power_rho1": round(float(b), 5),
                                 "power_given_pass": "" if np.isnan(c_) else round(float(c_), 5)})
    return summ, rows


def cny_bump_vector(sp, b, timing, permanent):
    """Bump on the H3 contrast D = restaurant - hawker: hawker level +b => D level -b."""
    s, L = sp.lay.start, sp.lay.length
    v = np.zeros(L)
    for y, d in CNY.items():
        dd = d - timedelta(days=15) if timing == "run-up (CNY-15d)" else d
        t = pm.idx(dd.year, dd.month) - s
        if 0 <= t < L:
            v[t] -= b
            if not permanent and t + 1 < L:
                v[t + 1] += b
    return v


def cny_study(tables, reps):
    rows = []
    sps = [sp for sp in specs() if sp.code in (21, 22, 23)]
    for sp in sps:
        for timing in ("CNY month", "run-up (CNY-15d)"):
            for permanent in (False, True):
                for sigma in (0.002, 0.004):
                    rng = np.random.default_rng(np.random.SeedSequence([BASE_SEED, sp.code, 4, int(sigma * 1e4)]))
                    x0 = pm.simulate_x(rng, reps, sp.lay.length, 0.0)
                    for b in (-0.01, -0.005, -0.0025, 0.0, 0.0025, 0.005, 0.01):
                        bump = cny_bump_vector(sp, b, timing, permanent)
                        x = x0 + bump / sigma  # work in sigma units
                        d = decide(sp, tables[sp.code], x)
                        # exact deterministic bias of T*_a from the bump (log points)
                        c = np.cumsum(bump)
                        T = c[sp.h:] - c[:-sp.h]
                        bias_T = float((sp.lay.W @ T)[0])
                        rows.append({"arm": sp.name, "timing": timing, "bump": "permanent" if permanent else "temporary (1 month)",
                                     "hawker_bump_logpts": b, "sigma_contrast_logpts": sigma,
                                     "bias_Tstar_logpts": round(bias_T, 6),
                                     "bias_rho_hat": round(bias_T / sp.delta, 3),
                                     "size_rank_test": round(float((d["Za"] > d["c_rank"]).mean()), 5),
                                     "size_rule_test": round(float((d["Za"] > d["c_rule"]).mean()), 5),
                                     "reps": reps})
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sps = specs()
    tables = {sp.code: calibration_table(sp) for sp in sps}
    write_csv(OUT / "calibration_tables.csv",
              [{"setting": sp.name, "phi": float(p), "t_crit": round(float(v), 5)}
               for sp in sps for p, v in zip(PHI_GRID, tables[sp.code])])
    write_csv(OUT / "a2_size_before_after.csv", size_study(sps, tables, a.reps))
    summ, rows = gate_study(sps, tables, a.reps)
    write_csv(OUT / "a1_gate_summary.csv", summ)
    write_csv(OUT / "a1_gate_curves.csv", rows)
    write_csv(OUT / "a3_cny_bump.csv", cny_study(tables, a.reps))
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} R_cal={R_CAL} base_seed={BASE_SEED} alpha={ALPHA} numpy={np.__version__} "
                f"elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

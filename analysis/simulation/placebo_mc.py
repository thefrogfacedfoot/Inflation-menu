#!/usr/bin/env python3
"""EXPLORATORY METHODS WORK. Monte Carlo study of the placebo-in-time test of
docs/preregistration_v2.md (tag prereg-v2), on SYNTHETIC data only. No ONS,
SingStat or project value is read; the only real inputs are calendar labels
(which months exist, event dates), the same labels as
diagnostics/tax_feasibility/p0_eligibility_counts.py uses.

Test as registered (§4, §5.1-5.4):
  T_m  = L_{m+h} - L_m                                    (L = log level)
  base-eligible anchor: L observed at m and m+h, no event month in [m, m+h],
                        (UK) 2020-08 is neither m nor m+h
  eligible: >= 3 base-eligible same-calendar-month neighbours m +- 12, 24, 36
  T*_m = T_m - mean(T over those neighbours)
  U_m  = sign(Delta) * T*_m;  p = (1 + #{placebo U_m >= U_a}) / (N + 1)
  reject at alpha = 0.0167 (the registered number)
  gate: MDE_rho = (q95 - q20 of placebo T*) / |Delta| <= 1 and N + 1 >= 1/alpha

Model: monthly log changes x_t = s_{month(t)} + e_t, e_t stationary AR(1)
with coefficient phi and marginal sd sigma (innovation sd sigma*sqrt(1-phi^2)).
A pass-through rho adds a level step rho*Delta in the event month.

Two exact reductions make one null simulation per (layout, phi, h) enough:
  * T* is linear in x and removes any per-calendar-month constant exactly, so
    the seasonal means drop out (checked numerically, not assumed: the size
    table includes s != 0 with identical draws).
  * The step only enters windows containing the event month; those anchors are
    never placebos or neighbours, so it shifts U_a by exactly rho*|Delta|.
    Everything scales with sigma, so with Z = U/sigma:
      reject  <=>  Z_a + rho*|Delta|/sigma > c,  c = (K+1)-th largest placebo Z,
      K = floor(alpha*(N+1)) - 1  (K < 0: the test can never reject).
    Power at any (rho, Delta, sigma) is the ECDF of D = c - Z_a at rho*|Delta|/sigma.

Usage: python3 analysis/simulation/placebo_mc.py [--reps 20000] [--seed 20261015]
Writes CSVs and SVG + 300-dpi PNG figures to analysis/simulation/output/.
"""
import argparse
import csv
import math
import time
from pathlib import Path

import numpy as np

ALPHA = 0.0167
PHIS = (-0.5, 0.0, 0.3, 0.6, 0.9, 0.97)
N_TARGETS = (60, 75, 126, 160)
POWER_PHIS = (0.0, 0.6, 0.9)
RHOS = (0.25, 0.5, 0.75, 1.0)
STEPS = {  # name: |Delta| in log points (prereg §2)
    "SG GST 2023 ln(1.08/1.07)": math.log(1.08 / 1.07),
    "SG GST 2024 ln(1.09/1.08)": math.log(1.09 / 1.08),
    "UK-E1 2011 (+0.0211)": math.log(1.20 / 1.175),
    "UK-E2 2020 (-0.1335)": abs(math.log(1.05 / 1.20)),
    "UK-E3 2021 (+0.0690)": math.log(1.125 / 1.05),
    "UK-E4 2022 (+0.0645)": math.log(1.20 / 1.125),
}
SIGMA_GRID = np.geomspace(0.0002, 0.2, 76)  # marginal sd of the monthly log change
OUT = Path(__file__).resolve().parent / "output"
ROOT = Path(__file__).resolve().parents[2]


def idx(y, m):
    return y * 12 + (m - 1)


# ---------------------------------------------------------------- layouts
class Layout:
    """Calendar layout: which levels are observed, event months, and the
    resulting anchor sets and demeaning matrix for a horizon h."""

    def __init__(self, name, present, events, tested, h, eoho=False):
        self.name, self.h = name, h
        self.start = min(present)
        self.length = max(present) - self.start + 1  # simulated span (levels)
        P = {m - self.start for m in present}
        ev = [e - self.start for e in events]
        eo = idx(2020, 8) - self.start if eoho else None

        def base(m):
            if m not in P or (m + h) not in P:
                return False
            if any(m <= e <= m + h for e in ev):
                return False
            return not (eo is not None and eo in (m, m + h))

        B = sorted(m for m in P if base(m))
        Bs = set(B)
        nb = {m: [m + 12 * k for k in (-3, -2, -1, 1, 2, 3) if (m + 12 * k) in Bs] for m in B}
        self.placebo = [m for m in B if len(nb[m]) >= 3]
        # tested event anchors: a = month before the effective month
        self.anchors = []
        for e in tested:
            a = e - self.start - 1
            ok = a in P and (a + h) in P
            n_a = [a + 12 * k for k in (-3, -2, -1, 1, 2, 3) if (a + 12 * k) in Bs]
            if not ok or len(n_a) < 3:
                raise ValueError(f"{name}: event anchor {a} not evaluable")
            nb[a] = n_a
            self.anchors.append(a)
        self.N = len(self.placebo)
        self.n_neigh_event = [len(nb[a]) for a in self.anchors]
        rows = self.anchors + self.placebo
        # T*_rows = W @ T_all, T_all indexed by anchor month 0..length-1-h
        nA = self.length - h
        W = np.zeros((len(rows), nA))
        for i, m in enumerate(rows):
            W[i, m] += 1.0
            for j in nb[m]:
                W[i, j] -= 1.0 / len(nb[m])
        self.W = W

    def tstar(self, x):
        """x: (R, length) monthly changes, x[:, t] = L_t - L_{t-1} (x[:, 0] unused).
        Returns (R, n_events + N) demeaned statistics, events first."""
        c = np.cumsum(x, axis=1)
        T = c[:, self.h:] - c[:, :-self.h]  # T_m = sum x_{m+1..m+h}
        return T @ self.W.T


def generic_layout(n_target, h, position):
    """Contiguous series, one event; length chosen so N == n_target exactly.
    position 'middle': event anchor has 6 neighbours; 'edge': in the first year,
    3 neighbours (as UK-E1, anchor 2010-12 in a series starting 2010-01)."""
    base_year = 2000
    for length in range(40, 600):
        start = idx(base_year, 1)
        present = range(start, start + length)
        if position == "edge":
            e = start + 6
        else:
            e = start + length // 2
        try:
            lay = Layout(f"generic N={n_target} {position}", present, [e], [e], h)
        except ValueError:
            continue
        if lay.N == n_target:
            return lay
    raise RuntimeError(f"no length gives N={n_target} ({position}, h={h})")


def uk_months():
    path = ROOT / "diagnostics/tax_feasibility/ons_catering_monthly_counts.csv"
    with open(path) as f:
        r = csv.reader(f)
        hdr = next(r)
        col = hdr.index("month") if "month" in hdr else 0
        out = set()
        for row in r:  # month labels only
            s = row[col].replace("-", "")[:6]
            out.add(idx(int(s[:4]), int(s[4:6])))
    return out


def months(a, b):
    return set(range(idx(*a), idx(*b) + 1))


UK_EVENTS = {"E1": idx(2011, 1), "E2": idx(2020, 7), "E3": idx(2021, 10), "E4": idx(2022, 4)}
SG_EVENTS = [idx(2007, 7), idx(2023, 1), idx(2024, 1)]


def calendar_layouts(h):
    uk = uk_months()
    return [
        Layout("UK catering calendar, UK-E3", uk, list(UK_EVENTS.values()), [UK_EVENTS["E3"]], h, eoho=True),
        Layout("UK catering calendar, UK-E1", uk, list(UK_EVENTS.values()), [UK_EVENTS["E1"]], h, eoho=True),
        Layout("SG hawker 2019-01..2026-08, SG-E1", months((2019, 1), (2026, 8)), SG_EVENTS, [idx(2023, 1)], h),
        Layout("SG dishes 2015-01..2026-08, SG-E1", months((2015, 1), (2026, 8)), SG_EVENTS, [idx(2023, 1)], h),
    ]


# ---------------------------------------------------------------- simulation
def simulate_x(rng, R, length, phi, seas_amp=0.0):
    """Stationary AR(1) monthly changes, marginal sd 1, plus fixed seasonal means."""
    e = np.empty((R, length))
    e[:, 0] = rng.standard_normal(R)
    innov = math.sqrt(1.0 - phi * phi)
    z = rng.standard_normal((R, length))
    for t in range(1, length):
        e[:, t] = phi * e[:, t - 1] + innov * z[:, t]
    if seas_amp:
        s = seas_amp * np.sin(2 * np.pi * np.arange(12) / 12 + 0.7)
        e = e + s[np.arange(length) % 12]
    return e


def kcrit(N, alpha=ALPHA):
    return math.floor(alpha * (N + 1)) - 1


def crit_value(Zp, K):
    """(K+1)-th largest placebo value per row; +inf if the test cannot reject."""
    if K < 0:
        return np.full(Zp.shape[0], np.inf)
    return -np.partition(-Zp, K, axis=1)[:, K]


def rank_p(Za, Zp):
    return (1 + (Zp >= Za[:, None]).sum(axis=1)) / (Zp.shape[1] + 1)


def seed_for(base, *keys):
    return np.random.default_rng(np.random.SeedSequence([base] + [int(k) for k in keys]))


def run_cell(lay, phi, reps, seed, key, seas_amp=0.0):
    rng = seed_for(seed, *key)
    x = simulate_x(rng, reps, lay.length, phi, seas_amp)
    Z = lay.tstar(x)
    nev = len(lay.anchors)
    return Z[:, :nev], Z[:, nev:]


# ---------------------------------------------------------------- studies
def size_study(reps, seed):
    rows, keep = [], {}
    li = 0
    for h in (1, 2):
        lays = [generic_layout(n, h, pos) for pos in ("middle", "edge") for n in N_TARGETS]
        lays += calendar_layouts(h)
        for lay in lays:
            li += 1
            for pi, phi in enumerate(PHIS):
                for seas in (0.0, 2.0):
                    # same key for seas 0 and 2: identical draws, so any difference is the seasonal term
                    Za, Zp = run_cell(lay, phi, reps, seed, (1, li, pi), seas)
                    Za = Za[:, 0]
                    p = rank_p(Za, Zp)
                    rate = float((p <= ALPHA).mean())
                    K = kcrit(lay.N)
                    rows.append({
                        "layout": lay.name, "h": h, "phi": phi, "seasonal_amp_sd": seas,
                        "N": lay.N, "event_neighbours": lay.n_neigh_event[0],
                        "min_p": round(1 / (lay.N + 1), 5),
                        "exact_size_if_exchangeable": round(max(K + 1, 0) / (lay.N + 1), 5),
                        "reject_rate": round(rate, 5),
                        "mc_se": round(math.sqrt(rate * (1 - rate) / reps), 5),
                        "over_rejects": rate - 2 * math.sqrt(rate * (1 - rate) / reps) > ALPHA,
                        "reps": reps,
                    })
                    if seas == 0.0:
                        keep[(lay.name, h, phi)] = (lay, Za, Zp)
    return rows, keep


def power_and_gate(keep):
    """Power curves, gate-vs-power, from the stored null draws (h = 2, primary)."""
    prow, grow = [], []
    for (name, h, phi), (lay, Za, Zp) in keep.items():
        if h != 2 or phi not in POWER_PHIS or "edge" in name:
            continue
        K = kcrit(lay.N)
        D = np.sort(crit_value(Zp, K) - Za)  # reject iff rho|Delta|/sigma > D
        G = np.quantile(Zp, 0.95, axis=1) - np.quantile(Zp, 0.20, axis=1)  # gate stat, sigma = 1
        for step, delta in STEPS.items():
            for rho in RHOS:
                xs = rho * delta / SIGMA_GRID
                pw = np.searchsorted(D, xs, side="left") / len(D)
                for s, v in zip(SIGMA_GRID, pw):
                    prow.append({"layout": name, "h": h, "phi": phi, "N": lay.N, "step": step,
                                 "delta": round(delta, 5), "rho": rho, "sigma": round(float(s), 6),
                                 "power": round(float(v), 5)})
        # gate vs power at rho = 1, in units r = |Delta| / sigma (step-free)
        for r in np.geomspace(0.5, 40, 161):
            passed = G <= r
            rej = (D < r)
            pp = float(passed.mean())
            grow.append({"layout": name, "h": h, "phi": phi, "N": lay.N,
                         "delta_over_sigma": round(float(r), 4),
                         "p_gate_pass": round(pp, 5),
                         "power_rho1": round(float(rej.mean()), 5),
                         "power_rho1_given_pass": round(float(rej[passed].mean()), 5) if passed.sum() >= 200 else "",
                         "n_pass": int(passed.sum())})
    return prow, grow


def multiplicity_study(reps, seed):
    """H1 on the UK calendar: E3, E4, E1 share one series and one placebo pool."""
    uk = uk_months()
    lay = Layout("UK catering calendar, H1", uk, list(UK_EVENTS.values()),
                 [UK_EVENTS["E3"], UK_EVENTS["E4"], UK_EVENTS["E1"]], 2, eoho=True)
    deltas = np.array([STEPS["UK-E3 2021 (+0.0690)"], STEPS["UK-E4 2022 (+0.0645)"], STEPS["UK-E1 2011 (+0.0211)"]])
    rows = []
    scen = {
        "global null": (0, 0, 0),
        "E3 only true (rho=1)": (1, 0, 0),
        "E1 only true (rho=1)": (0, 0, 1),
        "E3+E4 true (rho=1)": (1, 1, 0),
        "all true (rho=1)": (1, 1, 1),
        "all true (rho=0.5)": (0.5, 0.5, 0.5),
    }
    for pi, phi in enumerate((0.0, 0.6)):
        Za, Zp = run_cell(lay, phi, reps, seed, (3, pi))
        for sigma in (0.005, 0.01, 0.02):
            for sname, rho in scen.items():
                rho = np.array(rho, float)
                U = Za + rho * deltas / sigma
                p = np.stack([rank_p(U[:, k], Zp) for k in range(3)], axis=1)
                true_null = rho == 0
                rej = {}
                a3 = ALPHA / 3
                rej["fixed-sequence E3>E4>E1"] = np.cumprod(p <= ALPHA, axis=1).astype(bool)
                rej["Bonferroni"] = p <= a3
                order = np.argsort(p, axis=1)
                ps = np.take_along_axis(p, order, 1)
                step_ok = np.cumprod(ps <= ALPHA / np.array([3, 2, 1]), axis=1).astype(bool)
                holm = np.zeros_like(step_ok)
                np.put_along_axis(holm, order, step_ok, 1)
                rej["Holm"] = holm
                for proc, R in rej.items():
                    rows.append({
                        "procedure": proc, "phi": phi, "sigma": sigma, "scenario": sname,
                        "N": lay.N, "min_p": round(1 / (lay.N + 1), 5),
                        "FWER": round(float(R[:, true_null].any(axis=1).mean()), 5) if true_null.any() else "",
                        "P_reject_E3": round(float(R[:, 0].mean()), 5),
                        "P_reject_E4": round(float(R[:, 1].mean()), 5),
                        "P_reject_E1": round(float(R[:, 2].mean()), 5),
                        "P_any_false_null_rejected": round(float(R[:, ~true_null].any(axis=1).mean()), 5) if (~true_null).any() else "",
                        "reps": reps,
                    })
    return rows, lay


def resolution_table():
    rows = []
    for N in list(range(55, 66)) + [74, 75, 126, 160, 171, 178, 179, 180]:
        K = kcrit(N)
        rows.append({"N": N, "min_p": round(1 / (N + 1), 5), "alpha": ALPHA,
                     "can_reject": K >= 0, "max_placebo_exceedances_K": K,
                     "exact_size_if_exchangeable": round(max(K + 1, 0) / (N + 1), 5),
                     "bonferroni_alpha_over_3_can_reject": math.floor(ALPHA / 3 * (N + 1)) >= 1})
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261015)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    t0 = time.time()
    write_csv(OUT / "resolution.csv", resolution_table())
    size_rows, keep = size_study(a.reps, a.seed)
    write_csv(OUT / "size.csv", size_rows)
    prow, grow = power_and_gate(keep)
    write_csv(OUT / "power_curves.csv", prow)
    write_csv(OUT / "gate_vs_power.csv", grow)
    mrows, _ = multiplicity_study(a.reps, a.seed)
    write_csv(OUT / "multiplicity.csv", mrows)
    with open(OUT / "run_info.txt", "w") as f:
        f.write(f"reps={a.reps} seed={a.seed} alpha={ALPHA} numpy={np.__version__} elapsed_s={time.time() - t0:.0f}\n")
    print(f"done in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()

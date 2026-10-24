#!/usr/bin/env python3
"""P0 informativeness gate, prereg revision 4 (docs/preregistration_v2.md §5.3, §4, §8).

Run ONLY after the OSF deposit (§10). Before that it may be run on synthetic series only
(test_p0_invariance.py).

What it does, per registered test:
  * builds the event's calendar layout from the months present in the input series;
  * computes the pooled values the test compares, event included:
      rank tests (H3 components, H3-dish, SG-E2):  {U_a} u {U_m : m placebo}, U = sign(Delta) T*
      conformal tests (H1 events, UK-E2):           all n level-gap window statistics sign(Delta) S_j
  * gate statistic G = c_pool - q05(pooled), c_pool = (K+2)-th largest pooled value
    (K = floor(alpha (N+1)) - 1 for rank tests, floor(alpha n) - 1 for conformal tests),
    divided by h for conformal tests; MDE_rho = G / |Delta|;
  * resolution rule (N+1 >= 1/alpha; n >= 1/alpha) and, for conformal tests, the gap rule (not
    testable if a month within +-2 of the event month is missing from the retained sequence).

What it outputs (JSON): only N or n, the gap check, G, MDE_rho and the pass/fail decision. These are
symmetric functions of the pooled values (or calendar facts). It NEVER outputs U_a, S_obs, a rank or
a p-value. `p0_gate_from_pooled` takes the event's position only so that test_p0_invariance.py can
check that the output does not depend on it.

Inputs: CSVs with columns month (YYYY-MM) and log_level, already constructed as in §3:
  --uk        log of the chained matched Jevons index of treated catering items (UK, §3.1)
  --sg-hawker log(restaurants and fast food) - log(Hawker Centres)            (SG, §3.2, H3)
  --sg-dish   log level of the dish-arm contrast                              (SG, §3.2, H3-dish)
Months absent from a CSV are treated as unobserved. SG-E0 is not configured here: its control
series definition is an open VERIFY item (§9.3) and it never enters the confirmatory family.

Usage: python3 analysis/prereg_v4/p0_gate.py --uk UK.csv --sg-hawker H.csv --sg-dish D.csv --out p0_output.json
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "simulation"))
import benchmark_mc as bm  # noqa: E402
import placebo_mc as pm  # noqa: E402
import prereg_v3_checks as v3  # noqa: E402

ALPHA = 0.0167
Q_GATE = 0.05
MDE_MAX = 1.0
GAP_WINDOW = 2
OUTPUT_KEYS = {"test", "family", "kind", "series", "event", "h", "delta", "N_or_n", "resolution_ok",
               "gap_ok", "gate_stat", "mde_rho", "informative", "note"}

UK_DELTA = {"E1": math.log(1.20 / 1.175), "E2": math.log(1.05 / 1.20), "E3": math.log(1.125 / 1.05),
            "E4": math.log(1.20 / 1.125)}
SG_DELTA = {"SG-E1": math.log(1.08 / 1.07), "SG-E2": math.log(1.09 / 1.08)}
SG_EVENT = {"SG-E1": pm.idx(2023, 1), "SG-E2": pm.idx(2024, 1)}

# (test id, family, kind, series key, event, h); H3 and H3-dish are decided on the h = 2 gate (§5.3)
REGISTERED = [
    ("H1-E3", "H1", "conformal", "uk", "E3", 2),
    ("H1-E4", "H1", "conformal", "uk", "E4", 2),
    ("H1-E1", "H1", "conformal", "uk", "E1", 2),
    ("UK-E2", "secondary (H1 rules)", "conformal", "uk", "E2", 2),
    ("H3 h=2 (gate)", "H3", "rank", "sg_hawker", "SG-E1", 2),
    ("H3 h=1", "H3", "rank", "sg_hawker", "SG-E1", 1),
    ("H3-dish h=2 (gate)", "secondary (H3 rules)", "rank", "sg_dish", "SG-E1", 2),
    ("H3-dish h=1", "secondary (H3 rules)", "rank", "sg_dish", "SG-E1", 1),
    ("SG-E2 hawker h=2", "secondary", "rank", "sg_hawker", "SG-E2", 2),
    ("SG-E2 hawker h=1", "secondary", "rank", "sg_hawker", "SG-E2", 1),
    ("SG-E2 dish h=2", "secondary", "rank", "sg_dish", "SG-E2", 2),
    ("SG-E2 dish h=1", "secondary", "rank", "sg_dish", "SG-E2", 1),
]


def read_series(path):
    """{month index: log level}."""
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            y, m = row["month"].split("-")
            out[pm.idx(int(y), int(m))] = float(row["log_level"])
    return out


def p0_gate_from_pooled(pooled, event_pos, kind, delta, h):
    """The gate. Depends on the multiset `pooled` only; `event_pos` is accepted and ignored so the
    invariance test can vary it."""
    del event_pos
    v = np.asarray(pooled, float)
    n = len(v)
    K = math.floor(ALPHA * n) - 1  # n = N + 1 for rank tests, n = number of shifts for conformal
    c_pool = float(-np.partition(-v, K + 1)[K + 1]) if K + 1 < n else float("nan")
    g = (c_pool - float(np.quantile(v, Q_GATE))) / (h if kind == "conformal" else 1)
    mde = g / abs(delta)
    return {"N_or_n": n - 1 if kind == "rank" else n, "resolution_ok": n * ALPHA >= 1 - 1e-12,
            "gate_stat": g, "mde_rho": mde}


def build(kind, series, event_month, h, events, eoho, delta):
    """Spec, pooled values (sign(Delta)-adjusted, event first for rank tests) and event position."""
    present = set(series)
    sp = v3.Spec(0, "p0", present, events, event_month, h, abs(delta), eoho=eoho)
    s0, L = sp.lay.start, sp.lay.length
    lev = np.full(L, np.nan)
    for m, val in series.items():
        if s0 <= m < s0 + L:
            lev[m - s0] = val
    sign = 1.0 if delta > 0 else -1.0
    if kind == "rank":
        T = lev[h:] - lev[:-h]  # T_m = L_{m+h} - L_m, m = 0 .. L-h-1
        used = np.abs(sp.lay.W).sum(axis=0) > 0
        if not np.isfinite(T[used]).all():
            raise ValueError("a T used by the layout is missing")
        U = sign * (sp.lay.W @ np.where(used, T, 0.0))
        return sp, U, 0, None
    # gap rule first (§4 item 2): the retained sequence is phi_hat's months plus the event window, a
    # month counting only if its predecessor is retained too (as in benchmark_mc.Conformal)
    a_ = sp.lay.anchors[0]
    window = [t for t in range(a_ + 1, a_ + 1 + h) if t in range(L) and np.isfinite(lev[t]) and np.isfinite(lev[t - 1])]
    sample = set(np.where(sp.xok)[0].tolist()) | set(window)
    rows = {t for t in sample if t - 1 in sample}
    e = a_ + 1
    if not all(t in rows for t in range(e - GAP_WINDOW, e + GAP_WINDOW + 1)):
        return sp, None, None, False
    x = np.full(L, np.nan)
    x[1:] = lev[1:] - lev[:-1]
    conf = bm.Conformal(sp, level=True)
    assert set(conf.rows.tolist()) == rows
    xs = np.where(np.isfinite(x), x, 0.0)[None, :]  # only retained rows (finite) enter the fit
    if not np.isfinite(x[conf.rows]).all() or not np.isfinite(x[conf.rows - 1]).all():
        raise ValueError("a retained month is missing")
    S = sign * conf.shift_stats(xs, 0.0)[0]
    return sp, S, conf.w0, True


def run(series_by_key):
    out = []
    for test, family, kind, key, ev, h in REGISTERED:
        row = {"test": test, "family": family, "kind": kind, "series": key, "event": ev, "h": h}
        if key not in series_by_key:
            out.append({**row, "note": "series not supplied"})
            continue
        if key == "uk":
            events, eoho, e, delta = list(pm.UK_EVENTS.values()), True, pm.UK_EVENTS[ev], UK_DELTA[ev]
        else:
            events, eoho, e, delta = pm.SG_EVENTS, False, SG_EVENT[ev], SG_DELTA[ev]
        row["delta"] = round(delta, 6)
        try:
            sp, pooled, pos, gap_ok = build(kind, series_by_key[key], e, h, events, eoho, delta)
        except ValueError as err:
            out.append({**row, "informative": False, "note": f"not evaluable: {err}"})
            continue
        if gap_ok is False:
            out.append({**row, "gap_ok": False, "informative": False,
                        "note": "not testable: gap within +-2 months of the event month (§4)"})
            continue
        g = p0_gate_from_pooled(pooled, pos, kind, delta, h)
        gap_ok = True
        informative = bool(g["resolution_ok"] and gap_ok and g["mde_rho"] <= MDE_MAX)
        out.append({**row, "N_or_n": g["N_or_n"], "resolution_ok": bool(g["resolution_ok"]), "gap_ok": gap_ok,
                    "gate_stat": round(g["gate_stat"], 8), "mde_rho": round(g["mde_rho"], 6),
                    "informative": informative, "note": ""})
    for r in out:
        assert set(r) <= OUTPUT_KEYS, set(r) - OUTPUT_KEYS
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uk")
    ap.add_argument("--sg-hawker")
    ap.add_argument("--sg-dish")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    series = {k: read_series(p) for k, p in (("uk", a.uk), ("sg_hawker", a.sg_hawker), ("sg_dish", a.sg_dish)) if p}
    res = run(series)
    with open(a.out, "w") as f:
        json.dump({"alpha": ALPHA, "q_gate": Q_GATE, "mde_max": MDE_MAX, "tests": res}, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()

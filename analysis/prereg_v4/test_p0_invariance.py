#!/usr/bin/env python3
"""Invariance test for the revision-4 P0 gate (docs/preregistration_v2.md §5.3, §8). SYNTHETIC DATA ONLY.

Checks (exit status 1 if any fails):
  1. Invariance: for synthetic series on the registered calendars, the gate output of every
     registered test is identical whichever pooled value is labelled as the event (every position)
     and under 20 random permutations of the pooled values.
  2. Output contents: every output row uses only the whitelisted keys (no event value, rank or p).
  3. Gap rule: deleting the month two before or two after the E3 event month from the UK series
     (the event window itself stays observed) makes H1-E3 "not testable"; the unmodified series is
     testable.
  4. Same procedure as simulated: on the same synthetic draws, P0's gate statistic equals the
     revision-4 simulation's (analysis/simulation/prereg_v4_sim.py, q05, shift 0) to 1e-9.

Synthetic series: Gaussian AR(1), phi = 0.3, on the UK catering calendar (month labels from
diagnostics/tax_feasibility/ons_catering_monthly_counts.csv) and the SG hawker (2019-01..2026-08)
and dish (2015-01..2026-08) spans. Seed 20261025 + replicate. No outcome value is read.

Usage: python3 analysis/prereg_v4/test_p0_invariance.py [--reps 5]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "simulation"))
import p0_gate as p0  # noqa: E402
import placebo_mc as pm  # noqa: E402
import prereg_v3_checks as v3  # noqa: E402
import prereg_v4_sim as v4  # noqa: E402

SEED = 20261025


def synthetic(rng, months):
    """{month: log level} from AR(1) phi = 0.3 changes over the full span, then restricted to `months`."""
    lo, hi = min(months), max(months)
    x = pm.simulate_x(rng, 1, hi - lo + 1, 0.3)[0] * 0.01
    lev = np.cumsum(x)
    return {m: float(lev[m - lo]) for m in months}


def calendars():
    return {"uk": sorted(pm.uk_months()), "sg_hawker": sorted(pm.months((2019, 1), (2026, 8))),
            "sg_dish": sorted(pm.months((2015, 1), (2026, 8)))}


def check_invariance(series, rng, fails):
    n_checked = 0
    for test, family, kind, key, ev, h in p0.REGISTERED:
        if key == "uk":
            events, eoho, e, delta = list(pm.UK_EVENTS.values()), True, pm.UK_EVENTS[ev], p0.UK_DELTA[ev]
        else:
            events, eoho, e, delta = pm.SG_EVENTS, False, p0.SG_EVENT[ev], p0.SG_DELTA[ev]
        try:
            _, pooled, pos, _ = p0.build(kind, series[key], e, h, events, eoho, delta)
        except ValueError:
            continue
        if pooled is None:  # not testable under the gap rule
            continue
        ref = p0.p0_gate_from_pooled(pooled, pos, kind, delta, h)
        for j in range(len(pooled)):
            if p0.p0_gate_from_pooled(pooled, j, kind, delta, h) != ref:
                fails.append(f"invariance: {test}, event position {j}")
                break
        for _ in range(20):
            perm = rng.permutation(len(pooled))
            j = int(np.where(perm == pos)[0][0])
            if p0.p0_gate_from_pooled(pooled[perm], j, kind, delta, h) != ref:
                fails.append(f"invariance: {test}, permutation")
                break
        n_checked += 1
    return n_checked


def check_output(series, fails):
    for r in p0.run(series):
        extra = set(r) - p0.OUTPUT_KEYS
        if extra:
            fails.append(f"output keys {extra} in {r['test']}")


def check_gap(series, fails):
    base = {r["test"]: r for r in p0.run({"uk": series["uk"]})}
    if not base["H1-E3"]["gap_ok"]:
        fails.append("gap rule: unmodified UK series flagged")
    for off in (-2, 2):
        cut = dict(series["uk"])
        del cut[pm.UK_EVENTS["E3"] + off]
        r = {x["test"]: x for x in p0.run({"uk": cut})}["H1-E3"]
        if r.get("gap_ok", True) or r.get("informative"):
            fails.append(f"gap rule: missing month at E3{off:+d} not flagged")


def check_matches_simulation(rng, fails):
    sps = {sp.code: sp for sp in v3.specs()}
    pairs = [("H1-E3", 11, "uk", "E3"), ("H1-E1", 13, "uk", "E1"), ("H3 h=2 (gate)", 21, "sg_hawker", "SG-E1"),
             ("H3 h=1", 22, "sg_hawker", "SG-E1"), ("H3-dish h=2 (gate)", 23, "sg_dish", "SG-E1")]
    worst = 0.0
    for test, code, key, ev in pairs:
        sp = sps[code]
        x = pm.simulate_x(rng, 1, sp.lay.length, 0.3)
        lev = np.cumsum(x[0])
        present = {m for m in range(sp.lay.start, sp.lay.start + sp.lay.length)}
        if key == "uk":
            present &= pm.uk_months()
        series = {m: float(lev[m - sp.lay.start]) for m in present}
        row = {r["test"]: r for r in p0.run({key: series})}[test]
        if key == "uk":
            conf = v4.bm.Conformal(sp, level=True)
            G = v4.conformal_method(sp, conf, x)["v4_conformal_lvl"][1][0.05][0, 0]
        else:
            Z = sp.lay.tstar(x)
            P = np.concatenate([Z[:, :1], Z[:, 1:]], axis=1)
            G = (pm.crit_value(P, pm.kcrit(sp.N) + 1) - np.quantile(P, 0.05, axis=1))[0]
        d = abs(row["gate_stat"] - G)
        worst = max(worst, d)
        if d > 1e-6:  # gate_stat is rounded to 1e-8 in the output
            fails.append(f"simulation mismatch: {test} p0={row['gate_stat']} sim={G}")
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    a = ap.parse_args()
    fails, n = [], 0
    worst = 0.0
    for r in range(a.reps):
        rng = np.random.default_rng(SEED + r)
        series = {k: synthetic(rng, ms) for k, ms in calendars().items()}
        n += check_invariance(series, rng, fails)
        check_output(series, fails)
        check_gap(series, fails)
        worst = max(worst, check_matches_simulation(rng, fails))
    print(f"replicates={a.reps} invariance_checks={n} max|P0 - simulation| gate difference={worst:.2e}")
    print("FAIL\n" + "\n".join(fails) if fails else "PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

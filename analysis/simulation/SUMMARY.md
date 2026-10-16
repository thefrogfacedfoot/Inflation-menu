# Placebo-in-time test: Monte Carlo size and power (EXPLORATORY METHODS WORK)

**Status.** Exploratory methods work. This is **not** part of the preregistered analysis (`docs/preregistration_v2.md`, tag `prereg-v2`) and changes nothing in it. Only synthetic data is used. The only real inputs are calendar labels (which months exist, and the event dates), the same ones `diagnostics/tax_feasibility/p0_eligibility_counts.py` uses. No ONS, SingStat or project outcome value was read.

The existing `diagnostics/prereg_size_check.py` and `diagnostics/mde_simulation.py` simulate the **v1** Granger tests. They do not cover the v2 placebo rank test, so this module is new. It reuses their conventions: a fixed seed, a CLI, and plain CSV output.

## Reproduce

```
python3 -m venv .venv-sim && .venv-sim/bin/pip install -r analysis/simulation/requirements.txt
.venv-sim/bin/python analysis/simulation/placebo_mc.py --reps 50000 --seed 20261015   # about 40 s
.venv-sim/bin/python analysis/simulation/make_figures.py
```

Outputs go in `analysis/simulation/output/`:
- `size.csv`, `power_curves.csv`, `gate_vs_power.csv`, `multiplicity.csv`, `resolution.csv`, `run_info.txt`
- `figures/*.svg` and `figures/*.png` (300 dpi)

## What is simulated

The test is implemented as registered (§4, §5):
- The statistic is T_m = L_{m+h} − L_m.
- A base-eligible anchor needs L observed at m and m+h, and no event month in [m, m+h]. For the UK, 2020-08 is never an anchor or endpoint.
- An anchor is eligible if it has at least 3 base-eligible same-month neighbours at ±12, 24 or 36 months.
- T* = T minus the mean of those neighbours.
- p = (1 + #{U_m ≥ U_a}) / (N + 1), with rejection at α = 0.0167.
- The gate is (q95 − q20 of placebo T*) / |Δ| ≤ 1.

Model for the monthly log change: x_t = s_{month} + e_t. Here e_t is a stationary AR(1) with coefficient φ ∈ {−0.5, 0, 0.3, 0.6, 0.9, 0.97}. **σ is the marginal SD of the monthly log change**, not the innovation SD. For the H3 contrast, σ means the SD of the monthly change of the contrast series.

A pass-through ρ adds a level step of ρΔ in the event month. Two exact reductions are used, and the code docstring explains both:
1. The neighbour demeaning removes the seasonal means exactly. This was confirmed numerically: `size.csv` rows with seasonal amplitude 0 and 2 SD use identical draws, and every one of them has the same rejection rate.
2. The step shifts the event statistic by exactly ρ|Δ|, so all power curves come from one null simulation per (layout, φ, h).

Layouts:
- **Generic contiguous series** sized so that N is exactly 60, 75, 126 or 160. In one version the event is centred: 6 neighbours, except N = 60, which has only 4 because the series is too short. In the other the event sits in the first year (3 neighbours).
- **Real calendars:**
  - UK catering months: 191 present, E1–E4 excluded, EOHO.
  - SG Hawker Centres: 2019-01 to 2026-08.
  - SG dish arm: 2015-01 to 2026-08.

  At h = 2 these reproduce the registered N exactly (UK 171, hawker 74, dishes 126).

Runs used 50,000 replications per cell and seed 20261015. The Monte Carlo SE of a rate near 0.0167 is about 0.0006.

## Findings

### Size (null ρ = 0), `size.csv`, `figures/size_vs_persistence_h2.*`

1. **The test can never reach exactly 0.0167.** Its exact size under exchangeability is (K+1)/(N+1) with K = ⌊0.0167(N+1)⌋ − 1:
   - 0.0164 at N = 60
   - 0.0132 at N = 75
   - 0.0157 at N = 126
   - 0.0124 at N = 160
   - 0.0116 at N = 171
2. **Over-rejection is defined as a simulated rate more than 2 SE above 0.0167.** It happens in three situations:
   - **When the event anchor has fewer neighbours than most placebo anchors (3 instead of 5–6).**
     - Generic edge layouts, h = 2, φ = 0: 0.0197 at N = 60, 0.0171 at N = 75 (not flagged), 0.0199 at N = 126, 0.0177 at N = 160 (not flagged).
     - These rise with φ, to 0.0247 at N = 60 and 0.0251 at N = 126 when φ = 0.97.
     - **UK-E1 is in this situation.** Its anchor is 2010-12 in a series that starts in 2010-01, so it has 3 neighbours. It over-rejects at φ ≥ 0.9 (0.0188, 0.0247). At φ ≤ 0.6 it stays below 0.0167 (0.0139–0.0155), because its exact size at N = 171 is 0.0116.
   - **With high persistence of the monthly change (φ ≥ 0.9), on every real SG calendar layout at h = 2.**
     - SG hawker SG-E1 (N = 74, 5 neighbours): 0.0227 at φ = 0.9 and 0.0281 at φ = 0.97, against an exact size of 0.0133.
     - SG dishes (N = 126): 0.0224 and 0.0255.
   - **With small N and moderate persistence at h = 2.** At N = 60 (4 neighbours) the rate is 0.0198 at φ = 0.3 and 0.0221 at φ = 0.6.
3. **Where it does not over-reject.**
   - Centred events with N ≥ 126 and φ ≤ 0.6, which includes the UK-E3 calendar at all φ: 0.0097–0.0119 at h = 2.
   - Negative φ.
   - Seasonal means of any size.
4. **h = 1 compared with h = 2.** The pattern is the same, and the size distortion is smaller at h = 1 for centred events.

### Resolution limit, `resolution.csv`

5. The smallest attainable p is 1/(N+1). At α = 0.0167 the test can reject only if N ≥ 59: 1/60 = 0.01667 ≤ 0.0167. N = 55–58 can never reject. All registered primary pools meet this: hawker 74, dishes 126, UK 171.
6. At α/3 = 0.00557 (Bonferroni or Holm's first step inside H1) the test needs N ≥ 179. **The UK pool of N = 171 is below that, so Bonferroni and Holm on E3/E4/E1 can never reject.** The registered N is an upper bound, set before the 500-relative rule is applied.

### Power, `power_curves.csv`, `figures/power_*.*`

7. The largest marginal σ (log points × 100) that still gives ≥ 80% power at α = 0.0167, at h = 2. The table uses φ = 0; the CSV has φ = 0.6 and 0.9. The σ grid has about 10% steps, so each value is resolved to roughly 10%.

| Step | |Δ| | Layout (N) | ρ = 0.25 | ρ = 0.5 | ρ = 0.75 | ρ = 1 |
|---|---|---|---|---|---|---|
| SG GST 2023, ln(1.08/1.07) | 0.0093 | SG hawker (74) | 0.042 | 0.087 | 0.126 | 0.166 |
| SG GST 2024, ln(1.09/1.08) | 0.0092 | SG hawker (74) | 0.042 | 0.087 | 0.126 | 0.166 |
| UK-E1 | 0.0211 | UK calendar, E1 anchor (171) | 0.096 | 0.200 | 0.289 | 0.381 |
| UK-E2 | 0.1335 | UK calendar, E3 anchor (171) | 0.60 | 1.26 | 1.82 | 2.64 |
| UK-E3 | 0.0690 | UK calendar, E3 anchor (171) | 0.32 | 0.66 | 0.96 | 1.26 |
| UK-E4 | 0.0645 | UK calendar, E3 anchor (171) | 0.32 | 0.60 | 0.96 | 1.26 |

   For φ = 0.6 or 0.9 the thresholds are 10–25% lower. The UK-E2 and UK-E4 rows use the E3 anchor layout because their placebo pool and N are the same. The E4 anchor has 5 neighbours rather than 6, because 2019-03 is missing.

### MDE gate and power, `gate_vs_power.csv`, `figures/gate_vs_power_sg_hawker.*`

8. **Passing the gate (q95 − q20 ≤ |Δ|) does not imply ≥ 80% power at ρ = 1.** Results by layout, with r = |Δ|/σ:

| Layout (N) | φ | r where the gate passes in 50% of datasets | Power at ρ = 1 at that r | r needed for 80% power | Lowest power among datasets that pass |
|---|---|---|---|---|---|
| SG hawker (74) | 0 | 3.8 | 0.52 | 5.3 | 0.25 |
| SG hawker (74) | 0.9 | 4.7 | 0.63 | 6.0 | 0.24 |
| UK-E3 calendar (171) | 0 | 3.9 | 0.55 | 5.1 | 0.37 |
| SG dishes (126) | 0 | 3.8 | 0.57 | 5.0 | 0.37 |

   The last column is the minimum over r of P(reject | gate passes), taken where at least 200 datasets pass.

   Every layout and φ in `gate_vs_power.csv` shows the same thing: power is 0.51–0.65 where the gate passes half the time.

   **Why.** The gate uses q95. The rank test at α = 0.0167 needs the event to exceed the (K+1)-th largest placebo value, which is about q98.3 or higher. So the §5.2 sentence "guarantees only that full pass-through (ρ = 1) would be detected with 80% power" does not hold in these simulations.

### Multiplicity inside H1, `multiplicity.csv`, `figures/multiplicity_uk_h1_sigma1pct.*`

The UK calendar is used, with one shared placebo pool (N = 171), h = 2 and α = 0.0167.

9. **Fixed sequence E3 → E4 → E1.**
   - FWER is 0.0100 under the global null (φ = 0) and 0.0112 (φ = 0.6), both at or below 0.0167.
   - With only E3 true, FWER is 0.0050–0.0122. With E3 and E4 true it is 0.0025–0.0161.
   - Power to reject E3 at σ = 1.0 (log points × 100), φ = 0: 0.975 at ρ = 1 and 0.185 at ρ = 0.5.
   - Power to reject E3 at σ = 2.0: 0.442 at ρ = 1 and 0.013 at ρ = 0.5.
   - At σ = 0.5, P(reject E1 | all ρ = 1) = 0.62.
10. **Holm and Bonferroni at α = 0.0167 have FWER 0 and power 0 in every scenario.** This follows directly from finding 6, because no attainable p reaches 0.00557. This matches the reason given for the fixed sequence in prereg §5.4.

## Not covered

- A CNY-like moving-holiday shock. This is listed in prereg §9.4 as part of the simulation required before the confirmatory run.
- Gaps from the 500-relative rule.
- Placebo-inversion CI coverage.
- Cross-series dependence for the H3 contrast. Here σ is simply the SD of the contrast's own monthly change.
- Non-Gaussian or heteroskedastic noise (for example, COVID-period variance).
- **Ambiguity noted, not resolved:** §4 says neighbours are "eligible non-event anchors". Here they are base-eligible anchors, matching `p0_eligibility_counts.py`. §5.3 also does not specify a quantile definition; numpy's default linear interpolation is used for q95 and q20.

## Follow-up for prereg revision 3 (`prereg_v3_checks.py`, 2026-10-16)

Synthetic data only, run with `--reps 20000` in about 75 s. Outputs are in `output/prereg_v3/`:
- `a1_gate_summary.csv` and `a1_gate_curves.csv`: gate variants compared with power at ρ = 1.
- `a2_size_before_after.csv` and `calibration_tables.csv`: the size-control rule and its calibrated critical values.
- `a3_cny_bump.csv`: the CNY-like bump in the H3 hawker arm.

The findings and the two open decisions (D1 and D2) are written into `docs/preregistration_v2.md` §5.3, §5.5 and §9 item 4.

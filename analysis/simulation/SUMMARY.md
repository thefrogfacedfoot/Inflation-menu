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

`prereg_v3_iut.py` checks the H3 intersection-union test, which rejects only if both h = 2 and h = 1 reject. It reports size and power at ρ = 1 against using h = 2 alone, with and without the CNY bump scenarios. It takes about 17 s and writes `iut_power_no_bump.csv` and `iut_cny_scenarios.csv`. The registered gate and size rule (D1-b and D2-b) appear in `a1_gate_summary.csv` under the variant "REGISTERED D1-b+D2-b" and in the `size_alt_always_calibrated_bc` column.

## Benchmark study (`benchmark_mc.py`, 2026-10-24)

Synthetic data only, like everything above. No outcome value was read and the prereg is unchanged. The run used `--reps 20000` with R_cal = 20,000 and took about 5.5 min. The method definitions, seeds and implementation choices are in the module docstring. The claims these results bear on are listed in `docs/math_claims.md`.

```
.venv-sim/bin/python analysis/simulation/benchmark_mc.py --reps 20000
.venv-sim/bin/python analysis/simulation/benchmark_figures.py
.venv-sim/bin/python analysis/simulation/claims_checks.py --reps 20000   # output/claims/, about 12 s
```

**What is compared.** Five methods are run on the same draws in every cell. The fifth was added in the second pass; the first four's results reproduced exactly in that re-run (576/576 size cells):
- **ours**: the registered always-calibrated test (D2-b).
- **rank**: the uncalibrated rank test (prereg-v2).
- **hac**: an OLS event-dummy z-test with Newey-West errors.
- **conformal**: Chernozhukov, Wüthrich & Zhu (2021) with an AR(1) + calendar-month counterfactual and cyclic shifts. The statistic is the window sum of residuals.
- **conformal_lvl**: the same, with a level-gap statistic. It sums observed-minus-forecast levels over the window, which is the weighted residual sum Σ w_l u_{e+l} (`docs/math_claims.md` H3).

**The grid** is 23 layouts × 6 φ, at ρ ∈ {0.5, 1} on a grid of r = |Δ|/σ:
- the 7 registered layouts;
- 16 generic layouts (N ∈ {60, 75, 126, 160}, centred or first-year event, h ∈ {1, 2});
- H3 decided by the IUT, for every method;
- the A3 CNY scenarios.

The gate is not applied.

**Outputs in `output/benchmark/`:**
- `settings.csv`, `size.csv`, `power.csv` (raw and size-adjusted power, each method's difference from ours, paired MC SE);
- `summary.csv` (sizes, and power at r80, the first r on the grid where ours has ≥ 0.8 at ρ = 1);
- `flags.csv`, `cny.csv`, `cny_flags.csv`;
- `figures/`.

**Flag definitions (`flags.csv`).** A flag is raised in three cases:
- `size`: ours over-rejects (rate − 2 SE > α) and the benchmark does not.
- `power`: the benchmark does not over-reject, and its power exceeds ours by more than 2 paired SE at some (ρ, r).
- `power_sa`: the same comparison for size-adjusted power.

Each row reports the (ρ, r) with the largest difference.

**Size** across the 138 non-IUT cells, with the number of over-rejecting cells:

| Method | Size range | Over-rejecting cells |
|---|---|---|
| ours | 0.0131–0.0213 | 5 / 138 (generic N = 60 edge h = 1 at φ = 0.6; H3 hawker h = 2 at φ = 0.9, 0.0189; three generic edge layouts at φ = 0.97, 0.0201–0.0213) |
| rank | 0.0089–0.0271 | 32 / 138 |
| hac | 0.120–0.333 | 138 / 138 |
| conformal | 0.0082–0.0178 | 0 / 138 |

**Where a benchmark beats ours.** The first pass had 255 flags. With conformal_lvl there are 534, plus 295 CNY flags. On the registered layouts:

0. **Conformal level-gap, at h = 2: it beats ours, plainly.**
   - Its size is 0.0087–0.0174 and it never over-rejects in the 138 cells.
   - It has higher power than ours at h = 2 on every registered layout, at every φ, and in the H3 IUT. At r80 and ρ = 1, for example:
     - H3 hawker h = 2: 0.967 against 0.934 at φ = 0, and 1.000 against 0.879 at φ = 0.9;
     - UK-E1 at φ = 0: 0.995 against 0.924.
   - At ρ = 0.5 the gaps are larger: UK-E1 0.578 against 0.370, and H3 IUT 0.417 against 0.347, both at φ = 0.
   - Ours is ahead only at saturation (1.00 against 0.99, the K = 0 ceiling).
   - Two trade-offs:
     - It is not protected against a permanent CNY step (`cny.csv`: size 0.052, or 0.048 under the IUT, at a −1-point permanent step, against 0.013 for ours).
     - Under t(3) noise, ours keeps a power edge (`output/misspec/`).

1. **Conformal at h = 1 with persistent noise.**
   - SG hawker h = 1 (secondary): at φ = 0.97, ρ = 0.5, r = 2.4, power is 0.956 for conformal against 0.368 for ours. This setting is flagged at φ ∈ {−0.5, 0.6, 0.9, 0.97}.
   - In the generic h = 1 layouts the gap is up to +0.74 (φ = 0.97).
   - Mechanism: the AR(1) counterfactual pre-whitens. At high φ a pulse in x_e is many innovation SDs, while T* compares the event with neighbours a year apart and gains nothing from that predictability.
   - The DGP is exactly AR(1), which favours this benchmark. Misspecified noise is not tested.
2. **Conformal at φ = −0.5**, on every registered h = 2 layout. For example, UK-E1 at ρ = 0.5, r = 4.8 has raw power 0.642 against 0.441 for ours.
3. **Rank test after size adjustment, at high φ** (median gain 0.04, largest 0.21 in the generic edge layouts at φ = 0.97). Calibrating with the median/IQR τ costs some power compared with the raw order statistic. On the registered layouts the raw rank test is flagged mostly where it is also oversized, and so excluded from `power`.
4. **HAC after size adjustment**: only generic N = 160 edge h = 1, by about +0.02 to +0.04. Its raw size is never valid.

**Where ours wins.** At h = 2 with φ ≥ 0.3, conformal's power collapses:
- H3 hawker h = 2 at r80: 0.195, 0.032, 0.001 at φ = 0.3, 0.6, 0.9, against 0.85–0.91 for ours.
- The window sum of AR residuals is about s(1 − φ̂), so the pulse cancels.
- Even at φ = 0, conformal plateaus near 0.57. With n ≈ 87 shifts, K = 0, so the observed window must beat every other shift, including the overlapping shift one month earlier, which also contains the pulse.

For the H3 IUT, ours has power 0.80–0.96 at r80 against at most 0.47 for conformal at φ ≥ 0, and 0.87 at φ = −0.5.

**CNY (`cny_flags.csv`, 77 flags).**
- Under a +1-point temporary hawker bump, ours at h = 2 has size 0.265 and conformal 0.005. Conformal's h = 2 window sum is insensitive to a one-month pulse, for the reason in "Where ours wins". Under the IUT, ours is already ≤ 0.0001 in that scenario.
- HAC is flagged on `power_rho*` only where the bump biases it against rejection. Its no-bump size is about 0.2, so these flags do not make HAC a usable test.

**Not covered in the first pass:** misspecified noise (now in `misspec_mc.py`), a level-shift conformal statistic (now `conformal_lvl`), and size given that the gate passes (now in `method_fixes.py`). Still not covered: q = 2 conformal statistics, and conformal with a counterfactual model other than AR(1) plus calendar-month dummies.

## Method fixes (`method_fixes.py`, 2026-10-24)

Synthetic data only. The run used `--reps 20000` with R_DENSE = 50,000 and took about 20 min. Outputs are in `output/method_fixes/`. The definitions are in the docstring. The claims affected are C2, C3, C4, C6, D3 and D4 in `docs/math_claims.md`.

```
.venv-sim/bin/python analysis/simulation/method_fixes.py --reps 20000
.venv-sim/bin/python analysis/simulation/misspec_mc.py --reps 20000   # needs method_fixes' tables.csv; about 30 s
```

- **(a) Indirect-inference φ̂** (`phi_bias.csv`, `figures/phi_bias_*`).
  - Bias on the registered layouts:
    - Kendall: +0.004 to +0.014 for φ ∈ [0, 0.9].
    - Indirect inference: −0.001 to +0.002 over the same range.
  - Indirect inference is worse at the ends of the grid because of clipping: −0.006 to −0.016 at φ = 0.97, +0.027 to +0.042 at φ = −0.5.
  - RMSE is unchanged.
  - Effect on size: at most 0.0005.
- **(b) Smoothed critical value** (`tables.csv`, `figures/critical_value_raw_vs_smoothed.*`).
  - Dense grid: 149 points, 50,000 runs each, local-linear fit with the bandwidth chosen by leave-one-out cross-validation.
  - The curve is smooth on [−0.5, 0.9] and changes sharply above 0.9.
  - The registered 75-point table is within 0.04–0.06 of the smoothed curve.
- **Size across φ** (`size.csv`, 23 layouts × 8 true φ, `figures/size_variants_*`).
  - Registered rule: 0.0106–0.0201, over-rejecting in 10 of 184 cells.
  - Revised rule (a + b): 0.0114–0.0197, over-rejecting in 8 of 184.
  - True φ with the smoothed table: 1 of 184, which is consistent with chance (about 4 expected).
  - On the 7 registered layouts: the registered rule over-rejects in 2 cells (0.0191 each), the revised rule in 1 (0.0187).
- **(c) Size conditional on the gate** (`gate_conditional_size.csv`).
  - It is above α wherever the gate is informative: 0.021–0.032 when the gate passes half the time, and up to 0.060 when it passes 10% of the time.
  - H3 IUT: 0.009 (φ = 0) and 0.017 (φ = 0.9) at a 50% pass rate.
  - Neither (a) nor (b) changes this.
- **(d) The five cells** (`overreject_cells.csv`, 100,000 runs each):
  - one is sampling chance;
  - H3 hawker h = 2 at φ = 0.9 is the spread of φ̂ (about +0.001, which no fix removes);
  - the three φ = 0.97 edge cells are table under-reading plus low φ̂ near the 0.98 clip. Smoothing removes about a third of their excess; indirect inference removes none.

## Misspecification (`misspec_mc.py`, 2026-10-24)

Seven cells: UK-E3, E4, E1, H3 hawker h = 2 and h = 1, the dish arm, and the H3 IUT. Seven DGPs, 20,000 runs. Methods: ours (registered), ours (revised), both conformal variants, and the rank test as a distribution-free reference. The table gives the cells holding size, out of 7 (`holds_size_summary.csv`):

| DGP | ours reg / rev | conformal | conformal_lvl | rank |
|---|---|---|---|---|
| Gaussian AR(1) 0.3 (reference) | 7 / 7 | 7 | 7 | 7 |
| Gaussian AR(2) (0.5, 0.3) | 7 / 7 | 7 | 7 | 5 |
| seasonal AR (1−0.3B)(1−0.5B¹²) | 2 / 3 | 7 | 7 | 5 |
| t(3) innovations | 1 / 1 (size 0.030–0.035) | 7 | 7 | 7 |
| Var(x_e) × 3 in the event month | 0 / 0 | 1 | 0 | 0 |
| +0.5 SD drift break at mid-sample | 5 / 5 (hawker h = 2: 0.033) | 4 | 5 | 4 |
| +5 SD level step at mid-sample | 7 / 7 | 7 | 7 | 7 |

The event-month variance spike defeats every method. That is expected, because no placebo can reveal a variance change that occurs only in the event month. The calibrated test's weak points are heavy tails and seasonal persistence, both of which come from its Gaussian AR(1) calibration. Size-adjusted power is in `power.csv`.

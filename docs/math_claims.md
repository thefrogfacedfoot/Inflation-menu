# Mathematical claims inventory

This file lists every mathematical claim that the placebo-in-time method relies on (prereg rev. 3, tag `prereg-v3`, §4–§5.5 and §9 item 4). For each claim it gives the statement, the assumptions, its status, the supporting files and a reference where one exists. It contains no proofs. Every simulation file named here uses synthetic data only.

**Status labels**
- **Known result**: a published theorem applies as stated. The reference is given.
- **Provable**: elementary, but no published statement in this form was found. A proof still has to be written.
- **Simulation only**: no proof is claimed. The evidence is Monte Carlo under the stated DGP.
- **Open**: neither proved nor simulated.

Paths are relative to `analysis/simulation/`. Abbreviations:
- `v3/` = `output/prereg_v3/`
- `bm/` = `output/benchmark/`
- `cl/` = `output/claims/`
- `mf/` = `output/method_fixes/`
- `ms/` = `output/misspec/`

## Status changes, second pass (2026-10-24)

The second pass added three studies: `method_fixes.py`, `misspec_mc.py`, and the level-gap conformal variant in `benchmark_mc.py`. Their results changed these entries:

| Claim | Before | Now |
|---|---|---|
| C2, continuity of t*(φ) | Open | Simulation only. The dense table supports a continuous t*(φ) that changes sharply for φ ≥ 0.9. |
| C4, size given the gate passes | Open | Simulation only, and **it fails**: about 0.025 where the gate passes half the time, and 0.03–0.06 where it passes 10% of the time. |
| C5, other noise models | Open | Simulation only. The calibrated test **fails** under t(3) noise, seasonal AR and a drift break. |
| C6, the five over-rejecting cells | (new) | Simulation only. Explained. |
| D2, residual bias | Simulation only | Unchanged. The indirect-inference alternative (D4) was added. |
| D4, indirect-inference φ̂ | (new) | Simulation only. |
| F3, CNY | Simulation only | Unchanged. Evidence for the level-gap variant was added. |
| H2, conformal validity | Simulation only | Unchanged. It now covers both variants. |
| H3, the level-gap statistic | (new) | Provable (algebra), plus simulation. |
| B4, a symmetric gate gives exact conditional size | (new) | Provable (theorem candidate). Its application is Simulation only (`output/prereg_v4/`). |
| C7, residual-bootstrap calibration | (new) | Simulation only. **Fails** conditional size. |
| E5, power guarantee under the symmetric gate | (new) | Simulation only. Fails at q₁₀; holds at q₀₅ on the Gaussian grid for φ ≥ 0. |

## 0. Notation

| Symbol | Meaning |
|---|---|
| L_t, x_t = L_t − L_{t−1} | Monthly log level and monthly log change. t runs over the observed months 𝒫. |
| h ∈ {1, 2} | Horizon. T_m = L_{m+h} − L_m = x_{m+1} + … + x_{m+h}. |
| 𝓔, e, a = e − 1 | Set of event months, the tested event and its anchor. |
| B | Base-eligible anchors: m, m+h ∈ 𝒫, no e′ ∈ 𝓔 with m ≤ e′ ≤ m+h, and for the UK 2020-08 ∉ {m, m+h}. |
| 𝒩(m), k_m | Neighbours: {m + 12d : d = ±1, ±2, ±3} ∩ B, and their count. |
| 𝒜, N | Placebo anchors {m ∈ B : k_m ≥ 3} and their number. |
| T*_m, U_m | T*_m = T_m − k_m⁻¹ Σ_{j∈𝒩(m)} T_j. U_m = sgn(Δ) T*_m. The vector (U_a, U_m : m ∈ 𝒜) is written U = W·T. |
| α, K | α = 0.0167. K = ⌊α(N+1)⌋ − 1. |
| Rank test | p = (1 + #{m ∈ 𝒜 : U_m ≥ U_a}) / (N+1). Reject iff p ≤ α, equivalently U_a > c_rank = the (K+1)-th largest placebo U. |
| Calibrated test | τ = (U_a − med) / IQR over 𝒜, using numpy linear quantiles (Hyndman–Fan type 7). Reject iff τ > t̂*(φ̂_bc), equivalently U_a > c = med + t̂*·IQR. |
| φ̂, n, φ̂_bc | φ̂ = Σ x̃_t x̃_{t−1} / Σ x̃²_{t−1} over the n retained pairs, where x̃ is x demeaned by calendar month and event windows (and the UK EOHO changes) are excluded. φ̂_bc = φ̂ + (1 + 3φ̂)/n. |
| t̂*(φ) | Empirical 1 − α quantile of τ from R = 20,000 draws of model M(φ) on the event's layout, at 75 grid points φ ∈ {−0.50, −0.48, …, 0.98}, linearly interpolated. |
| Gate | (c − q₁₀)/|Δ| ≤ 1, where q₁₀ is the placebo 10th percentile (type 7). |
| M(φ) | The null model: x_t = s_{month(t)} + σ ε_t, where ε is a stationary Gaussian AR(1) with unit variance and coefficient φ. |
| Alternative | Pass-through ρ: x_e is replaced by x_e + ρΔ, a level step of ρΔ at e. |

## A. Algebraic properties of the statistic

**A1. Seasonal invariance.**
- Statement: U is unchanged if any calendar-month-periodic sequence s_{month(t)} is added to x.
- Assumptions: every neighbour offset is a multiple of 12. This holds for any h.
- Status: Provable (linear algebra).
- Evidence: `output/size.csv`. Rows with seasonal amplitude 0 and 2 SD use identical draws and give identical rates.
- Reference: none.

**A2. Location-shift reduction.**
- Statement: under the alternative, U_a increases by exactly ρ|Δ| and every placebo U_m is unchanged. So c_rank, med, IQR, q₁₀ and φ̂ are unchanged, and the rejection probability of either test is nondecreasing in ρ|Δ|/σ.
- Assumptions:
  - The step enters only x_e.
  - No placebo or neighbour window contains e. Base eligibility guarantees this.
  - The event window is excluded from φ̂.
- Status: Provable.
- Evidence: power is computed this way in `placebo_mc.py` and `prereg_v3_checks.py`. `benchmark_mc.py` recomputes the HAC and conformal benchmarks at each shift instead.
- Reference: none.

**A3. Scale invariance.**
- Statement: the rank decision, τ, φ̂, the gate ratio and both critical values (in U units) are equivariant or invariant under x → λx with λ > 0, together with Δ → λΔ. So under M(φ):
  - size depends only on (layout, h, φ);
  - power depends only on (layout, h, φ, ρ|Δ|/σ).
- Assumptions: model M(φ). A1 removes s.
- Status: Provable.
- Evidence: every simulation works in σ units.
- Reference: none.

## B. Placebo rank test (prereg §5.2, uncalibrated)

**B1. Resolution.**
- Statement: p ≥ 1/(N+1). The test can reject only if N + 1 ≥ 1/α, that is K ≥ 0, which means N ≥ 59 at α = 0.0167.
- Status: Provable (arithmetic).
- Evidence: `output/resolution.csv`.

**B2. Exact size under exchangeability.**
- Statement: if (U_a, U_m : m ∈ 𝒜) is exchangeable with a continuous joint law, then P(p ≤ α) = (K+1)/(N+1) ≤ α.
  - Example values: 0.0116 at N = 171, 0.0133 at N = 74, 0.0157 at N = 126.
- Status: Known result.
- Evidence: `output/size.csv`, column `exact_size_if_exchangeable`.
- References: Lehmann & Romano (2005), Thm 15.2.1; Hemerik & Goeman (2018).

**B3. The statistic is not exchangeable, even under i.i.d. noise.**
- Statement: under M(φ), Cov(U) = W Γ_T(φ) Wᵀ, where Γ_T is the autocovariance matrix of T.
- At φ = 0 and h ≤ 12:
  - Var(U_m) = hσ²(1 + 1/k_m), so the variance depends on the neighbour count.
  - Placebo-pair correlations are not all equal. The exact range is −0.40 to 0.50 on the UK calendar at h = 2, coming from shared neighbours and from windows that overlap when h = 2.
- At φ ≠ 0, Var(U_m) also depends on the set of neighbour offsets, through Γ_T at lags 12d. Neighbours on one side only (edge events) differ from symmetric neighbours.
- So B2's hypothesis fails for every registered layout, and the rank test's size is **simulation only**.
- Assumptions: model M(φ).
- Status:
  - The covariance formula and the failure of exchangeability: Provable.
  - The size consequences: Simulation only.
- Evidence:
  - `cl/u_variance.csv` (exact, no Monte Carlo). Var(U_event)/median placebo variance is 1.07 at φ = 0, 1.24 at φ = 0.9 and 1.51 at φ = 0.97 for the 3-neighbour UK-E1 event.
  - Size: `output/size.csv`, `v3/a2_size_before_after.csv` and `bm/size.csv`. For example, UK-E1 has size 0.0266 at φ = 0.97 and the H3 hawker test at h = 2 has 0.0267.
- Reference: Barber, Candès, Ramdas & Tibshirani (2023) bound the excess error by the average total-variation distance between U and U with the event swapped for placebo i. This bound has not been computed here (**Open**).

## B4. Symmetric gate: exact conditional size (theorem candidate for revision 4)

**Setting.**
- Data X takes values in a space 𝒳, and 𝒢 is a finite group acting on 𝒳.
- T : 𝒳 → ℝ is the test statistic.
- The randomization distribution is the multiset 𝒯(X) = {T(gX) : g ∈ 𝒢}.
- The p-value is p(X) = |𝒢|⁻¹ · #{g ∈ 𝒢 : T(gX) ≥ T(X)}.
- A gate is a map γ : 𝒳 → {0, 1}.

**Assumptions.**
- (A) *Randomization hypothesis:* under H0, gX has the same law as X for every g ∈ 𝒢.
- (B) *Invariant gate:* γ(gX) = γ(X) for every g ∈ 𝒢 and every X. A sufficient condition is that γ depends on X only through 𝒯(X), because 𝒯(gX) = 𝒯(X) when 𝒢 is a group.
- (C) *For equality only:* almost surely, 𝒯(X) has m distinct values, each with multiplicity |𝒢|/m.

**Claim.** Under H0, (A) and (B), whenever P(γ(X) = 1) > 0:
- P(p(X) ≤ α | γ(X) = 1) ≤ α;
- under (C) as well, P(p(X) ≤ α | γ(X) = 1) = ⌊αm⌋/m, the same as the unconditional size.

**Suggested route (not a proof).** Under (A), X has the same law as g*X, where g* is uniform on 𝒢 and independent of X (Hemerik & Goeman 2018, the step in Lehmann & Romano Thm 15.2.1). Condition on X. Under (B) the gate is constant over the orbit, and the p-value of g*X is uniform on the grid {1/m, …, 1}.

**Instances.**
1. *Placebo rank test (H3-v4a).*
   - X = (U_a, U_1, …, U_N), 𝒢 = all permutations of the N + 1 coordinates, T(X) = X₀, m = N + 1.
   - (A) is exchangeability, the B2 hypothesis.
   - The revision-4 gate uses the (K+2)-th largest of the N + 1 pooled values minus their q_p. It is a symmetric function, so (B) holds.
   - **(A) fails for the registered statistic (B3),** so the theorem gives exactness only for an idealised exchangeable U. The real conditional size is Simulation only.
2. *Conformal test (H1-v4), CWZ cyclic shifts.*
   - X = the residual vector u, 𝒢 = cyclic rotations (m = n), T = the window statistic at the event position. The revision-4 gate is a function of {S_j}, so (B) holds.
   - (A) holds for oracle residuals that are i.i.d., or more generally whose law is invariant under rotation.
   - With estimated residuals, (A) holds exactly only if the counterfactual estimator is invariant under rotating the data (CWZ). The estimator used here (calendar-month dummies plus an AR(1) lag on the compressed series) is not, so it holds approximately at best. Real conditional size: Simulation only.
3. *Not covered:* the calibrated test and the bootstrap test (H3-v4b). Their critical values depend on φ̂ and on the non-event months, not only on 𝒯(X), so (B) does not reduce them to (A).

**Why the gate uses the (K+2)-th largest pooled value.** Take any symmetric gate. The (K+1)-th largest pooled value is the observed statistic itself whenever the test rejects. With K = 0 (H3 hawker, N = 74) it would make the gate fail exactly when the true effect is large. The (K+2)-th largest equals the test's critical value whenever the test rejects, and is never above it otherwise. That is a design property, not part of the theorem.

**Status.**
- The claim: **Provable (theorem candidate; WC to prove).**
- Its application to the registered statistics: Simulation only.
- References: Lehmann & Romano (2005), Ch. 15; Hemerik & Goeman (2018); Chernozhukov, Wüthrich & Zhu (2021).
- Evidence: `output/prereg_v4/size.csv`, columns `cond_size_*`. Gate pass rates 10/50/90% and gate quantiles q₁₀ and q₀₅, on the Gaussian AR(1) grid plus AR(2), seasonal AR, t(3), drift break and level step.
  - Both instances behave as the theorem predicts even though (A) holds only approximately: conditional size is close to unconditional size.
    - Conformal (H1-v4, UK): unconditional 0.004–0.019, conditional 0.003–0.019.
    - Rank test under the H3 IUT: unconditional 0.000–0.016, conditional 0.000–0.018.
  - Where (A) fails, the conditional size inherits the unconditional failure but does not add to it. The rank test alone on H3 hawker h = 2 at φ = 0.9 is 0.025 unconditionally and 0.027 at every pass rate.
  - The variance spike breaks (A) at the event and every procedure fails, as expected.

## C. Calibrated test (prereg §5.5, D2-b)

**C1. Known φ.**
- Statement: if φ is known and on the grid, the size given the table is 1 − F_φ(t̂*(φ)), where F_φ is the CDF of τ under M(φ). Over table draws this has mean ≈ α and SD ≈ √(α(1 − α)/R) ≈ 0.0009. This follows from the Beta law of the empirical-quantile coverage.
- Assumptions:
  - M(φ) is the true model.
  - The table draws are independent of the data.
- Status: Known result (order statistics).
- Evidence: none needed beyond the reference.
- Reference: David & Nagaraja (2003), §2.

**C2. Interpolation off the grid.** *(Status changed in the second pass.)*
- Statement: size error from linear interpolation → 0 as the grid spacing → 0, provided the true 1 − α quantile t*(φ) is continuous in φ.
- Assumptions:
  - M(φ).
  - For each φ, τ has a continuous law with a positive density at t*(φ).
- Status:
  - Continuity of t*(φ): **Simulation only** (was Open). A proof would follow from the law of τ being continuous in φ, since τ is a continuous function of a Gaussian vector whose covariance is continuous in φ. That proof has not been written.
  - The finite-grid error: Simulation only.
- Evidence:
  - `v3/calibration_tables.csv` (75 points, R = 20,000) is a noisy, non-monotone function of φ: about half of the 74 consecutive differences are negative.
  - `mf/tables.csv` and `mf/figures/critical_value_raw_vs_smoothed.*` (149 points, R = 50,000) give a smooth fit. The bandwidth is chosen by leave-one-out cross-validation from 0.03–0.3. The residual SD of the dense raw points around the fit is 0.010–0.012, which is about the expected Monte Carlo error of a 98.3% quantile, so no structure is left in the residuals.
  - The fitted curve is flat to gently sloped on [−0.5, 0.9]. It changes sharply on [0.9, 0.98]:
    - up to 1.86 for UK-E1, the 3-neighbour layout;
    - down to 1.53–1.61 for UK-E4 and the hawker h = 1 and h = 2 layouts.
  - The registered 75-point table differs from the smoothed curve by at most 0.041–0.061 per layout.
- Consequence: a continuous t*(φ) is supported, but its steep part sits where φ̂ is least precise (see C6).

**C3. Plug-in (local Monte Carlo) validity.**
- Statement: if φ̂_bc → φ in probability and t*(·) is continuous at φ, the size → α as the series length → ∞.
- Assumptions:
  - M(φ) holds.
  - The layout grows so that N → ∞.
- Status: Known result in this form (asymptotic only).
- References: Dufour (2006) on local Monte Carlo tests; Beran (1988).
- Finite-sample size is **Simulation only**:
  - `v3/a2_size_before_after.csv`: 0.0155–0.0188 on the registered layouts.
  - `bm/size.csv`: all 23 layouts × 6 φ, including φ = −0.5.
  - `mf/size.csv`: 23 layouts × 8 true φ including the off-grid values 0.8 and 0.95, 20,000 runs. Size of the registered rule is 0.0106–0.0201 and it over-rejects in 10 of 184 cells. About 4 of 184 would be flagged by chance at the 2-SE rule. On the 7 registered layouts it over-rejects in 2 cells: H3 hawker h = 2 at φ = 0.3 (0.0191) and UK-E3 at φ = 0.6 (0.0191).

**C4. Size conditional on the gate.** *(Status changed in the second pass: the claim fails.)*
- Statement: the confirmatory decision is made only for events that pass the gate, so the relevant error rate is P(reject | pass, ρ = 0). The gate passes when c − q₁₀ ≤ |Δ|. That event favours datasets whose placebo spread (IQR, median − q₁₀) is small relative to σ. Since τ = (U_a − med)/IQR, a small IQR inflates τ. **So the conditional size exceeds the unconditional size, and the excess is largest where the gate rarely passes.**
- Size given the gate passes (null; φ ∈ {0, 0.9}; 20,000 runs; the 7 registered layouts):

| Share of datasets where the gate passes | Size given pass, registered rule |
|---|---|
| about 0.9 | 0.017–0.021 |
| about 0.5 | 0.021–0.032 |
| about 0.25 | 0.026–0.039 |
| about 0.1 | 0.032–0.060 |

  For the H3 IUT, conditional on the h = 2 gate:
  - φ = 0: 0.006, 0.009 and 0.015 at pass rates of 0.9, 0.5 and 0.1.
  - φ = 0.9: 0.012, 0.017 and 0.030.

  The revised rule (C6, D4) gives the same pattern within Monte Carlo error. Smoothing the table and changing the φ̂ correction do not touch this mechanism.
- Assumptions: M(φ). Same r grid as E3. Cells with ≥ 500 passing runs.
- Status: **Simulation only, and the claim that the registered test has size α among informative events fails** (was Open).
- Evidence:
  - `mf/gate_conditional_size.csv` (the full curves over r);
  - `mf/gate_conditional_summary.csv`. Its column `max_size_given_pass` is a maximum over 40 noisy estimates and is biased upward; read the curves.
- Remedy (revision-4 proposal): the symmetric gate of B4. With the conformal and rank tests the conditional excess disappears; see B4 for the evidence. With a calibrated critical value it does not (C7).

**C5. Robustness to the noise model.** *(Status changed in the second pass.)*
- Statement: C1–C4 assume Gaussian AR(1) noise. Under other noise the calibrated critical value is wrong by an amount that depends on the DGP.
- Simulation: `ms/size.csv` and `ms/holds_size_summary.csv`. There are 7 cells: UK-E3, E4, E1, H3 hawker h = 2 and h = 1, the dish arm, and the H3 IUT. Each uses 20,000 runs. The noise is scaled to marginal SD 1.

| Noise | Registered calibrated test: cells holding size, size range | Distribution-free comparators |
|---|---|---|
| Gaussian AR(1) 0.3 (reference) | 7/7, 0.006–0.017 | |
| Gaussian AR(2) (0.5, 0.3) | 7/7, 0.009–0.018 | |
| Seasonal AR (1−0.3B)(1−0.5B¹²) | **2/7**, 0.009–0.025 | both conformal variants 7/7 |
| t(3) innovations, AR(1) 0.3 | **1/7**, 0.018–0.035; only the IUT holds | rank test 7/7; both conformal variants 7/7 |
| Var(x_e) × 3 in the event month | 0/7, 0.036–0.090 | every method fails |
| +0.5 SD drift break at mid-sample | 5/7; H3 hawker h = 2 at 0.033 and h = 1 at 0.029; IUT holds | the break date falls two months before SG-E1, so the event's neighbours straddle it |
| +5 SD level step at mid-sample | 7/7 | |

  The revised rule behaves the same in every row.
- Status: **Simulation only** (was Open).
- Conclusion: the Gaussian assumption in the calibration is a real weakness. Under t(3) noise the uncalibrated rank test holds size where the calibrated test does not.

**C7. Residual-bootstrap calibration (new; considered for H3 in revision 4, not recommended).**
- Statement: replace the Gaussian AR(1) null model of §5.5 with a residual bootstrap.
  1. Fit AR(1) at the Kendall-corrected φ̂ to the calendar-month-demeaned changes.
  2. Draw B = 999 series with i.i.d. resampled centred residuals.
  3. Take t* = the 1 − α quantile of τ*.
  4. Combine with the symmetric gate.
- The intended consequences: size α without assuming Gaussian innovations, and no conditional excess.
- Result: the bootstrap fixes the heavy-tail failure of C5. Under t(3), size at h = 2 is 0.022, against 0.033 for v3. **But it does not remove the conditional excess.** On H3 hawker h = 2 the conditional size at a 50% pass rate is 0.028–0.033 on the Gaussian grid. Under the IUT it reaches 0.023 at φ = 0.9 and 0.032 under the drift break at a 10% pass rate.
- The mechanism is the same as in C4. The critical value med + t*·IQR still scales with the placebo IQR, so B4's condition (B) does not hold.
- Status: Simulation only (nested simulation: 6,000 outer runs, B = 999).
- Evidence: `output/prereg_v4/size.csv`, method `v4b_boot`.

## D. φ̂ and its bias correction

**D1. Bias of φ̂.**
- Statement for the textbook case: for a stationary AR(1) with one unknown mean, E[φ̂] − φ = −(1 + 3φ)/n + O(n⁻²). This is a Known result: Kendall (1954); Marriott & Pope (1954); general formulas in Shaman & Stine (1988).
- The §5.5 estimator is not that case. It removes 12 calendar-month means, has no intercept and uses pairs with gaps. **For this estimator the Kendall formula is not a known result.**
- Simulation: `cl/phi_hat_bias.csv`, 20,000 runs, MC SE ≤ 0.001. The leading bias term is absent at φ = 0 and grows with φ:

| Layout | n | φ = 0 | φ = 0.6 | φ = 0.9 | φ = 0.97 |
|---|---|---|---|---|---|
| UK-E3 | 172 | −0.0003 | −0.0095 | −0.0172 | −0.0223 |
| H3 hawker, h = 2 | 84 | −0.0006 | −0.0189 | −0.0375 | −0.0499 |

  Kendall's prediction for the hawker layout is −0.0119, −0.0333, −0.0440 and −0.0465.
- Status:
  - "No −1/n term at φ = 0 under calendar-month demeaning": Provable (conjecture). The numerator has mean 0 because x_t and x_{t−1} fall in different calendar months.
  - The rest: Simulation only.

**D2. The bias-corrected φ̂_bc.**
- Statement: the residual bias of φ̂_bc is positive for φ ≤ 0.6 (+0.005 to +0.014) and within ±0.006 for φ ∈ [0.9, 0.97] on the registered layouts.
- Status: Simulation only.
- Evidence: `cl/phi_hat_bias.csv`.

**D3. Effect of the φ̂ bias on size.**
- Statement: the effect is bounded by how much t̂* moves over the range of φ̂_bc. By C2 that is small except near the top of the grid.
- Status: Simulation only.
- Evidence:
  - `v3/a2_size_before_after.csv`, column `size_alt_always_calibrated_bc`;
  - `mf/size.csv`, where variant `II+raw` against `registered` isolates the correction.
- Over the 184 cells, replacing Kendall by indirect inference (D4) changes size by at most 0.0005. Over-rejecting cells go from 10 to 9.

**D4. Indirect-inference correction (new).**
- Statement: let b(φ) = E_φ[φ̂] on the event's layout under M(φ), estimated from the dense calibration draws and made nondecreasing. φ̂_II = b⁻¹(φ̂) is mean-unbiased to first order wherever b is strictly increasing and φ is in the interior of the grid.
- Assumptions: M(φ); b continuous and strictly increasing; φ in the interior of [−0.5, 0.98].
- Status:
  - Provable (standard indirect inference). References: Gouriéroux, Monfort & Renault (1993); MacKinnon & Smith (1998).
  - The finite-sample numbers below: Simulation only.
- Bias on the registered layouts:

| Correction | φ ∈ [0, 0.9] | φ = 0.97 | φ = −0.5 |
|---|---|---|---|
| Kendall (registered) | +0.004 to +0.014 | −0.004 to +0.000 | +0.004 to +0.011 |
| Indirect inference | −0.001 to +0.002 | −0.006 to −0.016 | +0.027 to +0.042 |

  The errors at both ends come from clipping at the ends of the grid. RMSE is essentially the same for both corrections, because φ̂'s SD (0.03–0.12) dominates its bias.
- Evidence:
  - `mf/phi_bias.csv` (23 layouts × 8 φ);
  - `mf/figures/phi_bias_*.{svg,png}`.

**C6. The five cells where the registered test over-rejected in the benchmark (new).**
- Each cell was re-run with 100,000 fresh runs under each rule variant; the MC SE is about 0.0004. Results are in `mf/overreject_cells.csv`:
  - **Generic N = 60 edge h = 1, φ = 0.6: sampling chance.** Registered size is 0.0173, not over-rejecting.
  - **H3 hawker h = 2, φ = 0.9: φ̂ variance.** Registered 0.0178, alternative table seed 0.0180, revised 0.0178, oracle φ 0.0159–0.0169. The mean of φ̂_II is 0.900, so bias is not the cause. The test uses the critical value at φ̂, which varies from run to run, rather than at the true φ. Neither fix removes this, but the excess is only about 0.001.
  - **Generic N = 75 / 160 edge h = 1 and N = 75 edge h = 2, φ = 0.97: steep t*(φ) plus low φ̂ near the upper bound.**

| Variant | Size |
|---|---|
| Registered | 0.0195–0.0205 |
| True φ, raw 75-point table | 0.0177–0.0183 |
| True φ, smoothed table | 0.0165–0.0168 |
| Revised (II + smoothed) | 0.0183–0.0194 |

    The raw table under-reads t* at 0.97 by 0.02–0.04. φ̂_II then averages 0.95–0.96 instead of 0.97 because of clipping at 0.98. Smoothing removes about a third of the excess over α; II removes none of it.
- So fix (b) fixes the table-noise part of the 0.97 cells. Fix (a) fixes no cell. What remains is the spread of φ̂ in the region where t* is steep. A conservative plug-in (for example the upper end of a confidence set for φ, as in Dufour's maximised MC test) or a grid that extends past 0.98 are the candidate remedies. Neither was simulated.
- Status: Simulation only.

## E. Informativeness gate (prereg §5.3, D1-b)

**E1. Deterministic power bound.**
- Statement: at ρ = 1, "the gate passes and U_a⁰ > q_p" implies rejection, where U_a⁰ is the null part of U_a. Therefore
  - P(reject ∩ pass) ≥ P(pass) − P(U_a⁰ ≤ q_p), and
  - P(reject | pass) ≥ 1 − P(U_a⁰ ≤ q_p)/P(pass).
- Assumptions:
  - A2 (location shift).
  - The gate and the test use the same c.
- Status: Provable (elementary).

**E2. The slack term under exchangeability.**
- Statement: with type-7 quantiles and j = ⌊p(N − 1)⌋, (j+1)/(N+1) ≤ P(U_a⁰ ≤ q_p) ≤ (j+2)/(N+1). For p = 0.10 this gives:
  - 0.105–0.110 at N = 171;
  - 0.107–0.120 at N = 74.
- Assumptions: exchangeable and continuous, which is the B2 hypothesis.
- Status: Provable (order statistics).
- Evidence and failure under B3: `cl/q10_bound.csv`. The upper bound is exceeded for 3-neighbour events and at high φ: UK-E1 reaches 0.136 at φ = 0.97, and H3 hawker at h = 2 reaches 0.124 and 0.133 at φ = 0.9 and 0.97. Centred events fall below the lower bound; UK-E3 is about 0.097.
- Reference: Hyndman & Fan (1996) for the quantile definition.

**E3. The registered "≥ 80% power at ρ = 1 given the gate passes".**
- Statement: min over |Δ|/σ of P(reject at ρ = 1 | pass) is 0.821–0.908 on the registered layouts at φ ∈ {0, 0.6, 0.9}. For the H3 IUT, conditional on the h = 2 gate, it is 0.865–0.892.
- E1 and E2 do **not** imply this. With P(U ≤ q₁₀) ≈ 0.12, the E1 bound reaches 0.8 only when P(pass) ≥ 0.6, and it is vacuous where the gate rarely passes.
- Assumptions: M(φ); grid of r = |Δ|/σ ∈ [1.5, 20]; cells with ≥ 500 passing datasets.
- Status: Simulation only.
- Evidence: `v3/a1_gate_summary.csv`, `v3/a1_gate_curves.csv`, `v3/iut_power_no_bump.csv`.

**E4. Why q₁₀ rather than q₂₀ (the finite-sample correction).**
- Statement: the heuristic "power ≥ 1 − p" is the limit in which P(pass) → 1 and the B2 hypothesis holds. In finite samples three things lower it:
  1. the discreteness term in E2, up to 2/(N+1) above p;
  2. conditioning on the gate passing (E1);
  3. non-exchangeability (B3).
- p = 0.10 was chosen because the simulated minimum in E3 was 0.746 with p = 0.20 and 0.786 with p = 0.15.
- Status: Simulation only.
- Evidence: `v3/a1_gate_summary.csv`, which covers the variants q05–q20.

**E5. Power guarantee under the symmetric gate (new).**
- Statement: with the symmetric gate, does P(reject at ρ = 1 | gate passes) ≥ 0.80 hold for every r?
- The deterministic bound E1 no longer applies. The gate's c_pool is at most the test's critical value, with equality only when the test rejects, so a passing gate does not imply that the test's own c − q_p ≤ |Δ|.
- Simulation: `output/prereg_v4/gate_guarantee.csv`, minimum over r with at least 500 passing runs (200 for the bootstrap).

| Gate quantile | H1-v4 conformal (UK E1–E4) | H3 IUT, rank test | H3-dish IUT |
|---|---|---|---|
| q₁₀ | 0.61–0.90 | 0.64–0.88 | 0.74–0.89 |
| q₀₅, Gaussian AR(1), φ ∈ [0, 0.97] | 0.819–0.897 | 0.815–0.917 | 0.857–0.937 |
| q₀₅, φ = −0.5 | (within the 0.819–0.897 range) | 0.693 | 0.748 |

- **So the guarantee fails at q₁₀, and q₀₅ is the corrected condition for φ ≥ 0.** v3's own guarantee at φ = −0.5 is 0.665, so the negative-φ shortfall is not new. Under misspecified noise q₀₅ gives 0.59–0.88 for H1-v4 and 0.78–0.93 for the H3 IUT. As in revision 3, it is a Gaussian AR(1) claim.
- Status: Simulation only.

## F. H3 intersection-union test (prereg §5.4)

**F1. Level of the IUT.**
- Statement: let H0 = H0⁽²⁾ ∪ H0⁽¹⁾. If the h = 2 test is level α for H0⁽²⁾ and the h = 1 test is level α for H0⁽¹⁾, then "reject iff both reject" is level α for H0. No assumption about the dependence between the two tests is needed.
- When both horizons test the same point null ρ = 0, this reduces to P(both reject) ≤ min(size₂, size₁).
- Status: Known result (Berger 1982).
- Caveat: the component levels are themselves Simulation only (C3), so the IUT's level is too.
- Evidence: `v3/iut_power_no_bump.csv` (0.0048–0.0133); the `bm/size.csv` rows `SG-E1 hawker IUT h=2 & h=1 (H3)`.

**F2. CNY biases have opposite signs at the two horizons.**
- Statement: take a temporary hawker bump of +b in the CNY month that reverts the next month, a Jan-CNY event year, and π_Feb = the share of neighbour years whose CNY falls in February. Then the bias of T*_a for the hawker level is
  - +b·π_Feb at h = 1;
  - −b·π_Feb at h = 2.
- For the SG-E1 anchor, π_Feb = 3/5, and the contrast series' bias has the opposite sign.
- A permanent step of size b is removed exactly at h = 2, but not at h = 1.
- Assumptions: b is the same every year and the bump sits in the calendar month of CNY. The run-up variant uses the CNY − 15 d month instead.
- Status: Provable (arithmetic on W).
- Evidence: `v3/a3_cny_bump.csv`, column `bias_Tstar_logpts` (exact).

**F3. IUT size under CNY bumps.**
- Statement: if the bump shifted only U_a, F1 + F2 + A2 would give size ≤ α at ρ = 0 for any sign of b, because one component's null holds with a nonpositive shift.
- The bump does not do that: it also enters every CNY-exposed placebo window. So c and the placebo distribution move, and F1 does not apply directly.
- Status: Simulation only.
- Evidence: `v3/iut_cny_scenarios.csv`, `bm/cny.csv`.
- Second pass, `bm/cny.csv`, method `conformal_lvl`: the level-gap conformal statistic is **not** protected against a permanent CNY step. Its calendar-month dummies cannot absorb a step that moves between January and February. At σ = 0.2 log points:
  - with a −1-point permanent hawker step, size is 0.052 at h = 2 and 0.048 under the IUT;
  - the registered test gives 0.013 in the same scenario.

  This is F2's exact removal of a permanent step at work, and it is the main robustness argument for the registered statistic in H3.

## G. H1 multiplicity

**G1. Fixed-sequence testing.**
- Statement: testing E3 → E4 → E1 in a fixed order, each at α and stopping at the first non-rejection, controls the FWER at α in the strong sense, provided each test is level α.
- Status: Known result. References: Maurer, Hothorn & Lehmacher (1995); Westfall & Krishen (2001); the closed-testing principle of Marcus, Peritz & Gabriel (1976).
- Caveat: the component levels are Simulation only (C3).
- Evidence: `output/multiplicity.csv`.

**G2. Holm and Bonferroni cannot reject at N = 171.**
- Statement: since ⌊(α/3)(N+1)⌋ = 0 at N = 171, Holm and Bonferroni over three events have no attainable p at the first step.
- Status: Provable (arithmetic, B1).
- Evidence: `output/resolution.csv`, `output/multiplicity.csv`.

## H. Claims about the benchmarks (benchmark study, `benchmark_mc.py`)

**H1. Why the OLS event-dummy test with HAC errors over-rejects.**
- Statement: take h = 1 and φ = 0. The dummy's OLS coefficient is x_e − mean(x over the other same-calendar-month months). Its residual at e is exactly 0. So the HAC variance estimates only the variance of the subtracted mean, ≈ σ²/n_month, instead of σ²(1 + 1/n_month). The z-statistic is inflated by about √(n_month + 1), and the size → P(Z > z_{1−α}/√(n_month + 1)), which is far above α.
- Assumptions: Bartlett-kernel HAC with a fixed lag and a single event.
- Status: Provable (approximate). This is the single-treated-period problem documented by Conley & Taber (2011).
- Evidence: `bm/size.csv`, method `hac`.

**H2. Validity of conformal inference with moving-block permutations.**
- Statement: Chernozhukov, Wüthrich & Zhu (2021) give two results.
  - Exact finite-sample validity when the counterfactual residuals are exchangeable under the permutation group and the estimator is invariant to it.
  - Approximate validity under stationarity, weak dependence and a consistent counterfactual estimator.
- This implementation departs from their setting in four ways:
  1. a signed sum as the statistic (q = 1, one-sided);
  2. an event window that is not at the end of the series;
  3. gaps compressed before the cyclic shifts;
  4. a counterfactual model with calendar-month dummies plus an AR(1) lag.
- Status:
  - CWZ's theorems: Known result.
  - The validity of this adaptation: Simulation only.
- Evidence:
  - `bm/size.csv`, methods `conformal` and `conformal_lvl`. Neither over-rejects in any of the 138 cells; the size ranges are 0.008–0.018 and 0.009–0.017.
  - `ms/holds_size_summary.csv`: both hold size under AR(2), seasonal AR, t(3) and a level step.
  - Both fail under the event-month variance spike; the window-sum variant holds only for the IUT.
  - Both fail marginally under the drift break (0.019–0.020): the window-sum variant for UK-E3, UK-E4 and the dish arm, the level-gap variant for UK-E3 and the dish arm.

**H3. The level-gap conformal statistic (new).**
- Statement: let ũ be the residuals of the null fit x̃_t = φ̂ x̃_{t−1} + u_t. The sum over the h window months of observed-minus-forecast levels, with forecasts made from the month before the window, equals Σ_{l=0}^{h−1} w_l u_{e+l}, where w_l = Σ_{i=l}^{h−1} (h − i) φ̂^{i−l}.
  - A level step s at e then contributes h·s.
  - The plain window sum contributes s(1 − φ̂) at h = 2.
  - At h = 1 the two statistics coincide.
- So the level-gap statistic is a function of the cyclically shifted residuals, and CWZ's permutation argument covers it as it covers H2.
- Status: Provable (algebra).
- Evidence: `bm/power.csv`, `bm/summary.csv`, `bm/flags.csv`.
  - It beats the registered test at h = 2 on every registered layout at every φ. Across the 8 registered settings (7 layouts plus the IUT) × 6 φ, 46 of 48 have a size-valid power win of more than 2 paired SE. The two exceptions are the hawker h = 1 contrast at φ = 0 and 0.3, where both conformal statistics are identical and weaker at ρ = 0.5. For example, H3 hawker h = 2 at φ = 0, ρ = 0.5, r = 6: 0.46 against 0.37.
  - The only cases where ours is significantly ahead are at saturation (1.00 against 0.99), from the K = 0 resolution ceiling.
  - Under t(3) noise the registered test keeps a power edge at h = 1 and in the IUT (size-adjusted 0.81 against 0.76 for the IUT at r = 4.8).

## References

- Barber, R. F., Candès, E. J., Ramdas, A. & Tibshirani, R. J. (2023). Conformal prediction beyond exchangeability. *Annals of Statistics* 51(2), 816–845.
- Beran, R. (1988). Prepivoting test statistics: a bootstrap view of asymptotic refinements. *JASA* 83(403), 687–697.
- Berger, R. L. (1982). Multiparameter hypothesis testing and acceptance sampling. *Technometrics* 24(4), 295–300.
- Chernozhukov, V., Wüthrich, K. & Zhu, Y. (2021). An exact and robust conformal inference method for counterfactual and synthetic controls. *JASA* 116(536), 1849–1864.
- Conley, T. G. & Taber, C. R. (2011). Inference with "difference in differences" with a small number of policy changes. *Review of Economics and Statistics* 93(1), 113–125.
- David, H. A. & Nagaraja, H. N. (2003). *Order Statistics*, 3rd ed. Wiley.
- Dufour, J.-M. (2006). Monte Carlo tests with nuisance parameters: a general approach to finite-sample inference and nonstandard asymptotics. *Journal of Econometrics* 133(2), 443–477.
- Hemerik, J. & Goeman, J. (2018). Exact testing with random permutations. *TEST* 27(4), 811–825.
- Gouriéroux, C., Monfort, A. & Renault, E. (1993). Indirect inference. *Journal of Applied Econometrics* 8(S1), S85–S118.
- Hyndman, R. J. & Fan, Y. (1996). Sample quantiles in statistical packages. *American Statistician* 50(4), 361–365.
- Kendall, M. G. (1954). Note on bias in the estimation of autocorrelation. *Biometrika* 41(3/4), 403–404.
- Lehmann, E. L. & Romano, J. P. (2005). *Testing Statistical Hypotheses*, 3rd ed. Springer.
- Marcus, R., Peritz, E. & Gabriel, K. R. (1976). On closed testing procedures with special reference to ordered analysis of variance. *Biometrika* 63(3), 655–660.
- Marriott, F. H. C. & Pope, J. A. (1954). Bias in the estimation of autocorrelations. *Biometrika* 41(3/4), 390–402.
- MacKinnon, J. G. & Smith, A. A. (1998). Approximate bias correction in econometrics. *Journal of Econometrics* 85(2), 205–230.
- Maurer, W., Hothorn, L. A. & Lehmacher, W. (1995). Multiple comparisons in drug clinical trials and preclinical assays: a-priori ordered hypotheses. In J. Vollmar (ed.), *Biometrie in der chemisch-pharmazeutischen Industrie* 6, 3–18. Fischer.
- Newey, W. K. & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica* 55(3), 703–708.
- Newey, W. K. & West, K. D. (1994). Automatic lag selection in covariance matrix estimation. *Review of Economic Studies* 61(4), 631–653.
- Shaman, P. & Stine, R. A. (1988). The bias of autoregressive coefficient estimators. *JASA* 83(403), 842–848.
- Westfall, P. H. & Krishen, A. (2001). Optimally weighted, fixed sequence and gatekeeper multiple testing procedures. *Journal of Statistical Planning and Inference* 99(1), 25–40.

Check the bibliographic details (volume and page numbers) against the originals before citing. They were written from memory and have not been looked up.

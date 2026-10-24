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

## C. Calibrated test (prereg §5.5, D2-b)

**C1. Known φ.**
- Statement: if φ is known and on the grid, the size given the table is 1 − F_φ(t̂*(φ)), where F_φ is the CDF of τ under M(φ). Over table draws this has mean ≈ α and SD ≈ √(α(1 − α)/R) ≈ 0.0009. This follows from the Beta law of the empirical-quantile coverage.
- Assumptions:
  - M(φ) is the true model.
  - The table draws are independent of the data.
- Status: Known result (order statistics).
- Evidence: none needed beyond the reference.
- Reference: David & Nagaraja (2003), §2.

**C2. Interpolation off the grid.**
- Statement: size error from linear interpolation → 0 as the grid spacing → 0, provided the true 1 − α quantile t*(φ) is continuous in φ.
- Status:
  - Continuity of t*(φ): Open.
  - The finite-grid error: Simulation only.
- Evidence: `v3/calibration_tables.csv`. t̂*(φ) varies only between 1.52 and 1.85 across the grid, and its grid-to-grid Monte Carlo jitter is of the same order as its trend for φ ≤ 0.9: in each table about half of the 74 consecutive differences are negative. The interpolated table is therefore a noisy, non-monotone function of φ.

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

**C4. Size conditional on the gate.**
- Statement: the registered decision is made only for events that pass the gate. The gate depends on placebo values and on φ̂, which are not independent of U_a when φ ≠ 0. So the size *given the gate passes* can differ from the unconditional size in C3.
- Status: Open. It has not been simulated.

**C5. Robustness to the noise model.**
- Statement: C1–C4 assume Gaussian AR(1) noise. Heavy tails, heteroskedasticity (for example COVID-period variance) and AR(p) with p > 1 are not covered.
- Status: Open.

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
- Evidence: `v3/a2_size_before_after.csv`, column `size_alt_always_calibrated_bc`.

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
- Evidence: `bm/size.csv`, method `conformal`.

## References

- Barber, R. F., Candès, E. J., Ramdas, A. & Tibshirani, R. J. (2023). Conformal prediction beyond exchangeability. *Annals of Statistics* 51(2), 816–845.
- Beran, R. (1988). Prepivoting test statistics: a bootstrap view of asymptotic refinements. *JASA* 83(403), 687–697.
- Berger, R. L. (1982). Multiparameter hypothesis testing and acceptance sampling. *Technometrics* 24(4), 295–300.
- Chernozhukov, V., Wüthrich, K. & Zhu, Y. (2021). An exact and robust conformal inference method for counterfactual and synthetic controls. *JASA* 116(536), 1849–1864.
- Conley, T. G. & Taber, C. R. (2011). Inference with "difference in differences" with a small number of policy changes. *Review of Economics and Statistics* 93(1), 113–125.
- David, H. A. & Nagaraja, H. N. (2003). *Order Statistics*, 3rd ed. Wiley.
- Dufour, J.-M. (2006). Monte Carlo tests with nuisance parameters: a general approach to finite-sample inference and nonstandard asymptotics. *Journal of Econometrics* 133(2), 443–477.
- Hemerik, J. & Goeman, J. (2018). Exact testing with random permutations. *TEST* 27(4), 811–825.
- Hyndman, R. J. & Fan, Y. (1996). Sample quantiles in statistical packages. *American Statistician* 50(4), 361–365.
- Kendall, M. G. (1954). Note on bias in the estimation of autocorrelation. *Biometrika* 41(3/4), 403–404.
- Lehmann, E. L. & Romano, J. P. (2005). *Testing Statistical Hypotheses*, 3rd ed. Springer.
- Marcus, R., Peritz, E. & Gabriel, K. R. (1976). On closed testing procedures with special reference to ordered analysis of variance. *Biometrika* 63(3), 655–660.
- Marriott, F. H. C. & Pope, J. A. (1954). Bias in the estimation of autocorrelations. *Biometrika* 41(3/4), 390–402.
- Maurer, W., Hothorn, L. A. & Lehmacher, W. (1995). Multiple comparisons in drug clinical trials and preclinical assays: a-priori ordered hypotheses. In J. Vollmar (ed.), *Biometrie in der chemisch-pharmazeutischen Industrie* 6, 3–18. Fischer.
- Newey, W. K. & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica* 55(3), 703–708.
- Newey, W. K. & West, K. D. (1994). Automatic lag selection in covariance matrix estimation. *Review of Economic Studies* 61(4), 631–653.
- Shaman, P. & Stine, R. A. (1988). The bias of autoregressive coefficient estimators. *JASA* 83(403), 842–848.
- Westfall, P. H. & Krishen, A. (2001). Optimally weighted, fixed sequence and gatekeeper multiple testing procedures. *Journal of Statistical Planning and Inference* 99(1), 25–40.

Check the bibliographic details (volume and page numbers) against the originals before citing. They were written from memory and have not been looked up.

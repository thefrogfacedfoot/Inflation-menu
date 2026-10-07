#!/usr/bin/env python3
"""Pre-registered Granger analysis (docs/preregistration.md, registered at bd859403).

A NEW module: granger_analysis.py is untouched so earlier results stay
reproducible. Nothing here reads uifpi.db or any project data; every function
takes arrays/Series. Section numbers below refer to the registration.

Pipeline per country (§4):
  levels -> calendar-true Δlog (a difference exists only if BOTH months exist)
  -> D5 longest contiguous run of valid months (n = levels in the run, ties:
     earliest) -> ADF+KPSS gate (D3; failure => exploratory, no 2nd diff)
  -> VAR(p) with constant + 11 month dummies (NSA both sides), p chosen by BIC
     in {1,2,3} on a common sample (D4) -> Granger exclusion F test
  -> Ljung-Box(12) on both equations' residuals (DIAGNOSTIC ONLY).
Inference (§5): Freedman-Lane circular-block permutation (restricted-model
residual blocks, regressors held fixed), b = clip(ceil(T**(1/3)), 3, 6) with T
the regression observations; Romano-Wolf (minP stepdown on permutation
p-values) and Benjamini-Hochberg across the declared family, on a common
calendar index. Panel (§6): Dumitrescu-Hurlin Z-tilde / W-bar on the common
calendar window with a cross-sectionally dependent bootstrap (the same
calendar blocks applied jointly to every country); N_PANEL = 4 rule (D8).
Fallback (§5.2): recursive restricted-model block bootstrap, used only if the
size check falls outside [0.03, 0.07]; it IS now the primary scheme (see
PRIMARY_SCHEME).

Choices the registration leaves open (flagged in the PR): ties in D5 go to the
earliest run; the BIC is the Gaussian system criterion ln|Σ| + k ln(T)/T on a
common sample (rows lost to the maximum lag are dropped for every p); the
Romano-Wolf statistic is the permutation p-value (minP) because F statistics
with different df are not comparable across countries; per-country block
lengths share the draw's random block starts.
"""
import math
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

N_MIN = 36           # D2: minimum levels in the run
MAX_LAG = 3          # D4
N_PANEL = 4          # D8
ALPHA = 0.05
B_DEFAULT = 9999
LB_LAGS = 12

# §5.2 size-check switch. The Freedman-Lane scheme's null rejection rate at 5%
# was 0.074 at n=36 (country level; outside [0.03, 0.07]), so the registered
# fallback, the recursive restricted-model block bootstrap, is the primary
# scheme for country-level AND panel tests. Evidence:
# diagnostics/prereg_size_check_results.txt (2,000 reps, seed 20261008).
# Set to "freedman_lane" only to reproduce the failed check.
PRIMARY_SCHEME = "recursive"


# ── Transform and alignment (§4.1, §4.4, §4.5, D5) ─────────────────────────
def log_diff(levels: pd.Series) -> pd.Series:
    """Calendar-true Δlog. Index: monthly PeriodIndex. A value at month t exists
    only if levels exist at t AND t-1; missing months are never filled."""
    s = levels.astype(float).copy()
    s.index = pd.PeriodIndex(s.index, freq="M")
    s = s[~s.index.duplicated()].sort_index()
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    full[full <= 0] = np.nan
    return np.log(full).diff()


def longest_run(valid: pd.Series):
    """Longest run of consecutive True months (D5). Returns (start Period, length);
    ties go to the earliest run; (None, 0) if no True."""
    best_start, best_len, cur_start, cur_len = None, 0, None, 0
    for per, ok in valid.items():
        if ok:
            if cur_len == 0:
                cur_start = per
            cur_len += 1
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
        else:
            cur_len = 0
    return best_start, best_len


@dataclass
class Prepared:
    name: str
    months: pd.PeriodIndex          # months of the run (levels)
    x: np.ndarray                   # Δlog index, length n-1 (month i+1 of the run)
    y: np.ndarray                   # Δlog CPI
    moy: np.ndarray                 # calendar month (1-12) of each difference
    n: int                          # levels in the run


def prepare(name: str, index_levels: pd.Series, cpi_levels: pd.Series) -> Prepared:
    """Align on calendar months and keep the D5 longest contiguous run where both
    series have a valid (positive) observation."""
    a = index_levels.copy()
    a.index = pd.PeriodIndex(a.index, freq="M")
    c = cpi_levels.copy()
    c.index = pd.PeriodIndex(c.index, freq="M")
    both = pd.concat([a.rename("i"), c.rename("c")], axis=1)
    both = both.reindex(pd.period_range(both.index.min(), both.index.max(), freq="M"))
    valid = (both["i"] > 0) & (both["c"] > 0)
    start, n = longest_run(valid)
    if n == 0:
        return Prepared(name, pd.PeriodIndex([], freq="M"), np.array([]), np.array([]), np.array([], int), 0)
    months = pd.period_range(start, periods=n, freq="M")
    run = both.loc[months]
    x = np.diff(np.log(run["i"].values))
    y = np.diff(np.log(run["c"].values))
    moy = np.array([m.month for m in months[1:]])
    return Prepared(name, months, x, y, moy, n)


# ── Stationarity gate (§4.2, D3) ───────────────────────────────────────────
def stationarity(series: np.ndarray) -> dict:
    from statsmodels.tsa.stattools import adfuller, kpss
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_p = float(adfuller(series, regression="c", autolag="AIC")[1])
        kpss_p = float(kpss(series, regression="c", nlags="auto")[1])
    return {"adf_p": adf_p, "kpss_p": kpss_p, "stationary": adf_p < ALPHA and kpss_p > ALPHA}


# ── Design and OLS pieces (§4.3, §4.6) ─────────────────────────────────────
def build_design(y, x, moy, p, dummies=True, row_start=None):
    """Rows t = row_start..len-1 (default p). Columns of the restricted design:
    const, 11 month dummies (Feb..Dec), y lags 1..p; unrestricted adds x lags
    1..p. A lag never spans a missing month because the run is contiguous."""
    r0 = p if row_start is None else row_start
    T = len(y) - r0
    cols = [np.ones(T)]
    if dummies:
        for m in range(2, 13):
            cols.append((moy[r0:] == m).astype(float))
    ylags = [y[r0 - j: len(y) - j] for j in range(1, p + 1)]
    xlags = [x[r0 - j: len(x) - j] for j in range(1, p + 1)]
    Zr = np.column_stack(cols + ylags)
    Zu = np.column_stack(cols + ylags + xlags)
    return y[r0:], Zr, Zu


def _proj_resid(Z):
    """(I - H) for design Z (T x k); asserts full column rank."""
    Q, R = np.linalg.qr(Z)
    if np.linalg.matrix_rank(R, tol=1e-9) < Z.shape[1]:
        raise ValueError("rank-deficient design (e.g. a calendar month missing from the run)")
    return np.eye(Z.shape[0]) - Q @ Q.T


def _ols(Z, Y):
    beta, *_ = np.linalg.lstsq(Z, Y, rcond=None)
    return beta, Y - Z @ beta


def select_lag(y, x, moy, dummies=True) -> dict:
    """BIC on the unrestricted bivariate VAR(p) (equations for y and x, same
    regressors), p in 1..MAX_LAG, common sample; ties -> smaller p (D4)."""
    out = {}
    r0 = MAX_LAG
    for p in range(1, MAX_LAG + 1):
        _, Zr, Zu = build_design(y, x, moy, p, dummies, row_start=r0)
        Yx = x[r0:]
        Yy = y[r0:]
        T = len(Yy)
        res = np.column_stack([_ols(Zu, Yy)[1], _ols(Zu, Yx)[1]])
        sig = res.T @ res / T
        k_total = 2 * Zu.shape[1]
        out[p] = float(np.log(np.linalg.det(sig)) + k_total * np.log(T) / T)
    best = 1
    for p in range(2, MAX_LAG + 1):
        if out[p] < out[best]:
            best = p
    return {"bic": out, "p": best}


@dataclass
class Fit:
    p: int
    T: int
    df2: int
    F: float
    W: float
    p_asym: float
    Mu: np.ndarray = field(repr=False)
    Mr: np.ndarray = field(repr=False)
    e_r: np.ndarray = field(repr=False)     # restricted residuals
    yhat_r: np.ndarray = field(repr=False)
    Zr: np.ndarray = field(repr=False)
    Zu: np.ndarray = field(repr=False)
    Y: np.ndarray = field(repr=False)
    lb_p_y: float = float("nan")
    lb_p_x: float = float("nan")


def granger_fit(y, x, moy, p, dummies=True, row_start=None, lb=True) -> Fit:
    Y, Zr, Zu = build_design(y, x, moy, p, dummies, row_start)
    T = len(Y)
    k_u = Zu.shape[1]
    df2 = T - k_u
    _, e_u = _ols(Zu, Y)
    br, e_r = _ols(Zr, Y)
    rss_u, rss_r = float(e_u @ e_u), float(e_r @ e_r)
    F = ((rss_r - rss_u) / p) / (rss_u / df2)
    fit = Fit(p=p, T=T, df2=df2, F=F, W=F * p, p_asym=float(stats.f.sf(F, p, df2)),
              Mu=_proj_resid(Zu), Mr=_proj_resid(Zr), e_r=e_r, yhat_r=Zr @ br, Zr=Zr, Zu=Zu, Y=Y)
    if lb:
        from statsmodels.stats.diagnostic import acorr_ljungbox
        x_target = x[len(x) - T:]
        e_x = _ols(Zu, x_target)[1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit.lb_p_y = float(acorr_ljungbox(e_u, lags=[LB_LAGS], model_df=2 * p)["lb_pvalue"].iloc[0])
            fit.lb_p_x = float(acorr_ljungbox(e_x, lags=[LB_LAGS], model_df=2 * p)["lb_pvalue"].iloc[0])
    return fit


# ── Resampling (§5.2) ──────────────────────────────────────────────────────
def block_length(T: int) -> int:
    return int(min(6, max(3, math.ceil(T ** (1 / 3)))))


def circular_blocks(starts: np.ndarray, b: int, length: int, modulus: int) -> np.ndarray:
    """(B, length) source indices from circular blocks of length b on a circle of
    `modulus` positions; starts has shape (B, >= ceil(length/b))."""
    nb = math.ceil(length / b)
    idx = (starts[:, :nb, None] + np.arange(b)[None, None, :]) % modulus
    return idx.reshape(starts.shape[0], nb * b)[:, :length]


def null_F_freedman_lane(fit: Fit, idx: np.ndarray) -> np.ndarray:
    """F* for each row of idx (B, T): e* = e_r[idx]; y* = yhat_r + e*. Because
    yhat_r lies in both column spaces, both RSS depend on e* only; regressors are
    held at their observed values."""
    E = fit.e_r[idx].T                                  # T x B
    ru = ((fit.Mu @ E) ** 2).sum(0)
    rr = ((fit.Mr @ E) ** 2).sum(0)
    return ((rr - ru) / fit.p) / (ru / fit.df2)


def null_F_recursive(fit: Fit, idx: np.ndarray, n_dummy_cols: int) -> np.ndarray:
    """Registered fallback: recursive restricted-model block bootstrap. y* is
    regenerated recursively from the restricted model (const, dummies, own lags)
    with resampled residual blocks, started from the observed first p values;
    F* is recomputed from the unrestricted model on y* and ITS lags (x lags fixed)."""
    p, T = fit.p, fit.T
    Zr, Zu = fit.Zr, fit.Zu
    beta_r, *_ = np.linalg.lstsq(Zr, fit.Y, rcond=None)
    base = Zr[:, :1 + n_dummy_cols] @ beta_r[:1 + n_dummy_cols]       # const + dummy part
    phi = beta_r[1 + n_dummy_cols:]                                   # own-lag coefficients
    B = idx.shape[0]
    ystar = np.zeros((B, T + p))
    # the p observed values preceding the first row
    # recover observed y for the p pre-sample rows from the first row's lag columns
    first_lags = Zr[0, 1 + n_dummy_cols: 1 + n_dummy_cols + p]       # y_{p-1}.. y_0 order = lag1..lagp
    for j in range(p):
        ystar[:, p - 1 - j] = first_lags[j]
    E = fit.e_r[idx]
    for t in range(T):
        pred = base[t] + sum(phi[j] * ystar[:, p + t - 1 - j] for j in range(p)) + E[:, t]
        ystar[:, p + t] = pred
    Y = ystar[:, p:]
    k_common = 1 + n_dummy_cols
    xl = Zu[:, k_common + p:]
    out = np.empty(B)
    for b in range(B):
        yl = np.column_stack([ystar[b, p - 1 - j: p - 1 - j + T] for j in range(p)])
        Zr_b = np.column_stack([Zu[:, :k_common], yl])
        Zu_b = np.column_stack([Zr_b, xl])
        e_u = Y[b] - Zu_b @ np.linalg.lstsq(Zu_b, Y[b], rcond=None)[0]
        e_r = Y[b] - Zr_b @ np.linalg.lstsq(Zr_b, Y[b], rcond=None)[0]
        ru, rr = e_u @ e_u, e_r @ e_r
        out[b] = ((rr - ru) / p) / (ru / fit.df2)
    return out


def perm_p(F_obs: float, F_null: np.ndarray) -> float:
    return float((1 + np.sum(F_null >= F_obs)) / (len(F_null) + 1))


# ── Multiplicity (§5.3) ────────────────────────────────────────────────────
def bh_qvalues(pvals) -> np.ndarray:
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for rank_from_top, i in enumerate(order[::-1]):
        rank = m - rank_from_top
        prev = min(prev, p[i] * m / rank)
        q[i] = prev
    return q


def romano_wolf(F_obs, F_null) -> np.ndarray:
    """minP stepdown. F_obs: (K,), F_null: (B, K) draws from the SAME joint
    resamples. Statistic per country = its permutation p-value (comparable across
    different df). Returns RW-adjusted p-values (monotone, stepdown)."""
    F_obs = np.asarray(F_obs, float)
    B, K = F_null.shape
    p_obs = np.array([perm_p(F_obs[k], F_null[:, k]) for k in range(K)])
    # rank-based null p-values: p*_{b,k} = (1 + #{b' : F*_{b'k} >= F*_{bk}}) / (B + 1)
    p_star = np.empty((B, K))
    for k in range(K):
        srt = np.sort(F_null[:, k])
        p_star[:, k] = (1 + (B - np.searchsorted(srt, F_null[:, k], side="left"))) / (B + 1)
    order = np.argsort(p_obs)
    adj = np.empty(K)
    running = 0.0
    for step, k in enumerate(order):
        remaining = order[step:]
        a = (1 + np.sum(p_star[:, remaining].min(axis=1) <= p_obs[k])) / (B + 1)
        running = max(running, a)
        adj[k] = running
    return np.minimum(adj, 1.0)


# ── Panel (§6, D7, D8) ─────────────────────────────────────────────────────
def dh_stats(W: np.ndarray, T: int, K: int) -> dict:
    """Dumitrescu-Hurlin (2012): W-bar, Z-bar, Z-tilde from per-country Wald stats.
    Accepts W of shape (N,) or (B, N); returns arrays over the leading axis."""
    W = np.atleast_2d(W)
    N = W.shape[1]
    Wbar = W.mean(axis=1)
    Zbar = math.sqrt(N / (2 * K)) * (Wbar - K)
    Zt = math.sqrt(N / (2 * K) * (T - 2 * K - 5) / (T - K - 3)) * \
        ((T - 2 * K - 3) / (T - 2 * K - 1) * Wbar - K)
    return {"Wbar": Wbar, "Zbar": Zbar, "Ztilde": Zt}


def decide_primary(n_included: int, common_window_levels: int = None) -> str:
    """D8: which test is the primary confirmatory one.
    'panel'        N >= N_PANEL and common window >= N_MIN levels
    'country_rw'   N = 2 or 3 (Romano-Wolf), DH exploratory
    'country_single' N = 1
    'stop'         N = 0, or N >= N_PANEL but the common window < N_MIN
                   (cannot run as registered: stop and report)."""
    if n_included == 0:
        return "stop"
    if n_included >= N_PANEL:
        if common_window_levels is None or common_window_levels < N_MIN:
            return "stop"
        return "panel"
    return "country_rw" if n_included >= 2 else "country_single"


def pooled_bic_lag(preps: list, dummies=True) -> int:
    """Common lag for the panel: BIC summed over countries (pooled criterion)."""
    tot = {p: 0.0 for p in range(1, MAX_LAG + 1)}
    for pr in preps:
        s = select_lag(pr.y, pr.x, pr.moy, dummies)["bic"]
        for p in tot:
            tot[p] += s[p]
    best = 1
    for p in range(2, MAX_LAG + 1):
        if tot[p] < tot[best]:
            best = p
    return best


def common_window(preps: list):
    """Intersection of the countries' run months (all are intervals), as a
    PeriodIndex of levels months."""
    lo = max(pr.months[0] for pr in preps)
    hi = min(pr.months[-1] for pr in preps)
    if hi < lo:
        return pd.PeriodIndex([], freq="M")
    return pd.period_range(lo, hi, freq="M")


def restrict(pr: Prepared, window: pd.PeriodIndex) -> Prepared:
    """Cut a prepared run to a window (levels months)."""
    i0 = int(np.where(pr.months == window[0])[0][0])
    i1 = int(np.where(pr.months == window[-1])[0][0])
    # differences are indexed by months[1:], so level month i maps to diff i-1
    sl = slice(i0, i1)          # diffs for months i0+1..i1
    return Prepared(pr.name, window, pr.x[sl], pr.y[sl], pr.moy[sl], len(window))


def panel_test(preps: list, B: int = B_DEFAULT, seed: int = 20261008, dummies=True,
               scheme: str = None) -> dict:
    """Primary DH panel test on the common calendar window with a cross-sectionally
    dependent bootstrap: ONE set of calendar blocks per draw, applied jointly to
    every country's restricted residuals."""
    scheme = scheme or PRIMARY_SCHEME
    win = common_window(preps)
    if len(win) < N_MIN:
        return {"status": "stop", "reason": f"common window {len(win)} < {N_MIN} levels"}
    cut = [restrict(pr, win) for pr in preps]
    p = pooled_bic_lag(cut, dummies)
    fits = [granger_fit(c.y, c.x, c.moy, p, dummies, lb=False) for c in cut]
    T = fits[0].T
    W = np.array([f.W for f in fits])
    obs = dh_stats(W, T, p)
    rng = np.random.default_rng(seed)
    b = block_length(T)
    starts = rng.integers(0, T, size=(B, math.ceil(T / b)))
    idx = circular_blocks(starts, b, T, T)
    n_dum = 11 if dummies else 0
    Wstar = np.empty((B, len(fits)))
    for i, f in enumerate(fits):
        Fs = null_F_freedman_lane(f, idx) if scheme == "freedman_lane" else null_F_recursive(f, idx, n_dum)
        Wstar[:, i] = Fs * p
    nul = dh_stats(Wstar, T, p)
    out = {"status": "ok", "N": len(fits), "window": (str(win[0]), str(win[-1])), "levels": len(win),
           "T": T, "lag": p, "block": b, "scheme": scheme, "B": B}
    for key in ("Wbar", "Zbar", "Ztilde"):
        out[key] = float(obs[key][0])
        out[f"p_boot_{key}"] = float((1 + np.sum(nul[key] >= obs[key][0])) / (B + 1))
    out["p_asym_Ztilde"] = float(stats.norm.sf(out["Ztilde"]))     # reported, never used for decisions
    return out


# ── Country-level family (§3, §5) ──────────────────────────────────────────
def country_family(preps: list, B: int = B_DEFAULT, seed: int = 20261008, dummies=True,
                   scheme: str = None) -> dict:
    """Inclusion by rule (n >= N_MIN, ADF+KPSS pass), then per-country F, raw p,
    Freedman-Lane permutation p on shared calendar draws, Romano-Wolf and BH."""
    scheme = scheme or PRIMARY_SCHEME
    rows, included = [], []
    for pr in preps:
        row = {"country": pr.name, "n": pr.n, "included": False, "reason": None}
        if pr.n < N_MIN:
            row["reason"] = f"n={pr.n} < {N_MIN}"
        else:
            sx, sy = stationarity(pr.x), stationarity(pr.y)
            row.update(adf_p_x=sx["adf_p"], kpss_p_x=sx["kpss_p"], adf_p_y=sy["adf_p"], kpss_p_y=sy["kpss_p"])
            if not (sx["stationary"] and sy["stationary"]):
                row["reason"] = "ADF+KPSS fail: exploratory (no second difference)"
            else:
                row["included"] = True
                included.append(pr)
        rows.append(row)
    if not included:
        return {"rows": rows, "included": []}
    # global calendar for joint draws
    ords = [(pr.months[0].ordinal, pr.months[-1].ordinal) for pr in included]
    g0, g1 = min(o[0] for o in ords), max(o[1] for o in ords)
    G = g1 - g0 + 1
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, G, size=(B, math.ceil(G / 3)))
    fits, Fnull = [], np.empty((B, len(included)))
    n_dum = 11 if dummies else 0
    for k, pr in enumerate(included):
        p = select_lag(pr.y, pr.x, pr.moy, dummies)["p"]
        f = granger_fit(pr.y, pr.x, pr.moy, p, dummies)
        b = block_length(f.T)
        # global positions of this country's regression rows
        pos0 = pr.months[p + 1].ordinal - g0           # first row is diff index p -> level month p+1
        src = circular_blocks(starts, b, G, G)[:, (pos0 + np.arange(f.T)) % G]
        idx = ((src - pos0) % G) % f.T
        Fnull[:, k] = null_F_freedman_lane(f, idx) if scheme == "freedman_lane" else null_F_recursive(f, idx, n_dum)
        fits.append((pr, f, b))
    Fobs = np.array([f.F for _, f, _ in fits])
    pperm = np.array([perm_p(Fobs[k], Fnull[:, k]) for k in range(len(fits))])
    prw = romano_wolf(Fobs, Fnull)
    qbh = bh_qvalues(pperm)
    by_name = {r["country"]: r for r in rows}
    for k, (pr, f, b) in enumerate(fits):
        by_name[pr.name].update(window=(str(pr.months[0]), str(pr.months[-1])), lag=f.p, T=f.T, df2=f.df2,
                                F=f.F, p_raw=f.p_asym, p_perm=float(pperm[k]), p_rw=float(prw[k]),
                                q_bh=float(qbh[k]), block=b, lb12_p_y=f.lb_p_y, lb12_p_x=f.lb_p_x,
                                scheme=scheme, B=B)
    return {"rows": rows, "included": [pr.name for pr in included], "G": G}

#!/usr/bin/env python3
"""Figures for analysis/simulation/output/benchmark/*.csv (written by benchmark_mc.py).
Same style as make_figures.py: no titles, A4 half-width, Okabe-Ito, SVG + 300-dpi PNG.

Usage: python3 analysis/simulation/benchmark_figures.py
"""
import csv

import make_figures as mf  # sets the Agg backend and rcParams

import matplotlib.pyplot as plt  # noqa: E402

OUT = mf.OUT / "benchmark"
FIG = OUT / "figures"
METHODS = {"ours": "calibrated (ours)", "rank": "rank (uncalibrated)", "hac": "OLS + HAC",
           "conformal": "conformal (CWZ), window sum", "conformal_lvl": "conformal (CWZ), level gap"}
COLOR = {m: mf.OKABE[i] for i, m in enumerate(METHODS)}
LS = dict(zip(METHODS, mf.STYLES + [(0, (5, 1, 1, 1, 1, 1))]))
H3 = "SG-E1 hawker contrast h=2 (H3)"
IUT = "SG-E1 hawker IUT h=2 & h=1 (H3)"


def rows(name):
    with open(OUT / name) as f:
        return list(csv.DictReader(f))


def save(fig, stem):
    fig.savefig(FIG / f"{stem}.svg")
    fig.savefig(FIG / f"{stem}.png", dpi=300)
    plt.close(fig)


def fig_size(setting, stem):
    r = [x for x in rows("size.csv") if x["setting"] == setting]
    fig, ax = plt.subplots(figsize=(mf.W, mf.H))
    for m, lab in METHODS.items():
        v = [x for x in r if x["method"] == m]
        ax.errorbar([float(x["phi"]) for x in v], [100 * max(float(x["size"]), 1e-4) for x in v],
                    yerr=[200 * float(x["mc_se"]) for x in v], color=COLOR[m], ls=LS[m], marker="o", ms=2.5,
                    capsize=1.5, label=lab)
    ax.axhline(100 * mf.ALPHA, color="grey", lw=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("AR(1) coefficient of monthly log change, φ")
    ax.set_ylabel("Rejection rate under null (%, log scale)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save(fig, stem)


def fig_power(setting, phi, col, stem):
    r = [x for x in rows("power.csv") if x["setting"] == setting and x["phi"] == phi]
    fig, ax = plt.subplots(figsize=(mf.W, mf.H))
    for m, lab in METHODS.items():
        for rho, lw in (("1.0", 1.2), ("0.5", 0.7)):
            v = [x for x in r if x["method"] == m and x["rho"] == rho]
            ax.plot([float(x["r"]) for x in v], [100 * float(x[col]) for x in v], color=COLOR[m], ls=LS[m], lw=lw,
                    label=f"{lab}, ρ = {rho}")
    ax.axhline(80, color="grey", lw=0.8)
    ax.set_xscale("log")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Step size relative to noise, |Δ| / σ (ratio)")
    ax.set_ylabel(("Size-adjusted power" if col == "power_size_adj" else "Power") + " (%)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=5.5)
    save(fig, stem)


def fig_cny(arm, stem):
    r = [x for x in rows("cny.csv") if x["arm"] == arm and x["timing"] == "CNY month"
         and x["bump"] == "temporary (1 month)" and x["sigma_contrast_logpts"] == "0.002"]
    fig, ax = plt.subplots(figsize=(mf.W, mf.H))
    for m, lab in METHODS.items():
        v = [x for x in r if x["method"] == m]
        ax.plot([100 * float(x["hawker_bump_logpts"]) for x in v], [100 * max(float(x["size"]), 1e-4) for x in v],
                color=COLOR[m], ls=LS[m], marker="o", ms=2.5, label=lab)
    ax.axhline(100 * mf.ALPHA, color="grey", lw=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("Temporary hawker CNY bump, b (log points × 100)")
    ax.set_ylabel("Rejection rate under null (%, log scale)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save(fig, stem)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    fig_size(H3, "size_h3_hawker_h2")
    fig_size("UK-E1 (H1)", "size_uk_e1")
    fig_size("generic N=60 edge h=2", "size_generic_n60_edge_h2")
    for phi in ("0.0", "0.9"):
        tag = phi.replace(".", "")
        fig_power(H3, phi, "power", f"power_h3_hawker_h2_phi{tag}")
        fig_power(H3, phi, "power_size_adj", f"power_sa_h3_hawker_h2_phi{tag}")
        fig_power(IUT, phi, "power_size_adj", f"power_sa_h3_iut_phi{tag}")
    fig_cny(H3, "cny_temporary_size_h3_h2")
    fig_cny(IUT, "cny_temporary_size_h3_iut")
    print("figures ->", FIG)


if __name__ == "__main__":
    main()

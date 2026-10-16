#!/usr/bin/env python3
"""EXPLORATORY METHODS WORK. Figures for analysis/simulation/output/*.csv
(written by placebo_mc.py). No titles; sized for A4 half-width (3.35 in);
Okabe-Ito colours; SVG and 300-dpi PNG.

Usage: python3 analysis/simulation/make_figures.py
"""
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
FIG = OUT / "figures"
OKABE = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7", "#F0E442"]
STYLES = ["-", "--", "-.", ":"]
W, H = 3.35, 2.5
ALPHA = 0.0167

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 6.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.2,
    "svg.fonttype": "none", "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def rows(name):
    with open(OUT / name) as f:
        return list(csv.DictReader(f))


def save(fig, stem):
    fig.savefig(FIG / f"{stem}.svg")
    fig.savefig(FIG / f"{stem}.png", dpi=300)
    plt.close(fig)


def fig_size():
    r = [x for x in rows("size.csv") if x["h"] == "2" and x["seasonal_amp_sd"] == "0.0"]
    pick = {"generic N=75 middle": "generic, N=75", "generic N=160 middle": "generic, N=160",
            "generic N=75 edge": "generic edge, N=75", "generic N=160 edge": "generic edge, N=160",
            "SG hawker 2019-01..2026-08, SG-E1": "SG hawker calendar, N=74",
            "UK catering calendar, UK-E1": "UK calendar E1, N=171"}
    fig, ax = plt.subplots(figsize=(W, H))
    for i, (name, short) in enumerate(pick.items()):
        v = [x for x in r if x["layout"] == name]
        phi = [float(x["phi"]) for x in v]
        y = [100 * float(x["reject_rate"]) for x in v]
        e = [200 * float(x["mc_se"]) for x in v]
        nb = v[0]["event_neighbours"]
        ax.errorbar(phi, y, yerr=e, color=OKABE[i], ls=STYLES[i % 4], marker="o", ms=2.5, capsize=1.5,
                    label=f"{short} ({nb} nbrs)")
    ax.axhline(100 * ALPHA, color="grey", lw=0.8)
    ax.set_xlabel("AR(1) coefficient of monthly log change, φ")
    ax.set_ylabel("Rejection rate under null (%)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    save(fig, "size_vs_persistence_h2")


def fig_power():
    r = rows("power_curves.csv")
    which = {
        "SG GST 2023 ln(1.08/1.07)": "SG hawker 2019-01..2026-08, SG-E1",
        "SG GST 2024 ln(1.09/1.08)": "SG hawker 2019-01..2026-08, SG-E1",
        "UK-E1 2011 (+0.0211)": "UK catering calendar, UK-E1",
        "UK-E2 2020 (-0.1335)": "UK catering calendar, UK-E3",
        "UK-E3 2021 (+0.0690)": "UK catering calendar, UK-E3",
        "UK-E4 2022 (+0.0645)": "UK catering calendar, UK-E3",
    }
    g = defaultdict(list)
    for x in r:
        if x["phi"] == "0.0" and which.get(x["step"]) == x["layout"]:
            g[(x["step"], x["rho"])].append(x)
    for step in which:
        fig, ax = plt.subplots(figsize=(W, H))
        for i, rho in enumerate(("0.25", "0.5", "0.75", "1.0")):
            v = g[(step, rho)]
            ax.plot([100 * float(x["sigma"]) for x in v], [100 * float(x["power"]) for x in v],
                    color=OKABE[i + 1], ls=STYLES[i], label=f"ρ = {rho}")
        ax.axhline(80, color="grey", lw=0.8)
        ax.set_xscale("log")
        ax.set_xlabel("SD of monthly log change, σ (log points × 100)")
        ax.set_ylabel("Power at α = 0.0167 (%)")
        ax.set_ylim(0, 100)
        d = 100 * float(v[0]["delta"])
        ax.set_xlim(d / 40, d)
        ax.legend(frameon=False, loc="upper right")
        stem = "power_" + step.split(" (")[0].split(" ln")[0].replace(" ", "_").replace("-", "")
        save(fig, stem)


def fig_gate():
    r = [x for x in rows("gate_vs_power.csv") if x["layout"] == "SG hawker 2019-01..2026-08, SG-E1"]
    fig, ax = plt.subplots(figsize=(W, H))
    for i, phi in enumerate(("0.0", "0.9")):
        v = [x for x in r if x["phi"] == phi]
        xs = [float(x["delta_over_sigma"]) for x in v]
        c = OKABE[4 if i == 0 else 5]
        ax.plot(xs, [100 * float(x["p_gate_pass"]) for x in v], color=c, ls="-", label=f"P(gate passes), φ = {phi}")
        ax.plot(xs, [100 * float(x["power_rho1"]) for x in v], color=c, ls="--", label=f"Power at ρ = 1, φ = {phi}")
    ax.axhline(80, color="grey", lw=0.8)
    ax.set_xlim(2, 9)
    ax.set_xlabel("Step size relative to noise, |Δ| / σ (ratio)")
    ax.set_ylabel("Probability (%)")
    ax.legend(frameon=False, loc="lower right")
    save(fig, "gate_vs_power_sg_hawker")


def fig_multiplicity():
    r = [x for x in rows("multiplicity.csv") if x["phi"] == "0.0" and x["sigma"] == "0.01"]
    procs = ["fixed-sequence E3>E4>E1", "Holm", "Bonferroni"]
    scen = [("global null", "FWER", "FWER, global null"),
            ("E3 only true (rho=1)", "FWER", "FWER, only E3 true"),
            ("all true (rho=1)", "P_reject_E3", "P(reject E3), all ρ = 1"),
            ("all true (rho=0.5)", "P_reject_E3", "P(reject E3), all ρ = 0.5")]
    fig, ax = plt.subplots(figsize=(W, H))
    bw = 0.26
    for j, p in enumerate(procs):
        ys = []
        for s, col, _ in scen:
            x = next(x for x in r if x["procedure"] == p and x["scenario"] == s)
            ys.append(100 * float(x[col]))
        xs = [i + (j - 1) * bw for i in range(len(scen))]
        ax.bar(xs, ys, bw, color=OKABE[j + 1], label=p)
        for x, y in zip(xs, ys):
            ax.text(x, y + 1.5, f"{y:.1f}", ha="center", va="bottom", fontsize=5.5, rotation=90)
    ax.set_xticks(range(len(scen)))
    ax.set_xticklabels([s[2] for s in scen], rotation=20, ha="right")
    ax.set_ylim(0, 125)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("Probability (%)")
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=5.5)
    save(fig, "multiplicity_uk_h1_sigma1pct")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    fig_size()
    fig_power()
    fig_gate()
    fig_multiplicity()
    print("figures ->", FIG)


if __name__ == "__main__":
    main()

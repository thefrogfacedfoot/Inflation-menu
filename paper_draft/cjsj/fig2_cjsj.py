"""Column-width (3.3in) variant of fig2_lead_times for the CJSJ submission.
Same data and colour/hatch logic as generate_figures.fig2_lead_times(); only the
geometry, font (Times New Roman 8pt everywhere) and the UICPI title differ.
Run from the repo root (needs matplotlib, pandas, numpy and Times New Roman installed):
    python3 paper_draft/cjsj/fig2_cjsj.py paper_draft/cjsj/fig2_lead_times_cjsj.png"""
import sys, os
sys.path.insert(0, os.getcwd())
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import generate_figures as gf

OUT = sys.argv[1]
plt.rcParams.update({
    "font.family": "Times New Roman",
    "font.size": 8,
    "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8,
})

granger = gf.granger_results_calendar_true()
countries, lead_times, p_values, not_validated = [], [], [], []
for c in gf.COUNTRIES:
    r = granger.get(c, {})
    countries.append(c)
    lt, pv = r.get("lead_months"), r.get("granger_p_value")
    lead_times.append(lt if lt is not None else 0)
    p_values.append(pv if pv is not None else 1.0)
    ps, pb = r.get("permutation_p_shuffle"), r.get("permutation_p_block")
    not_validated.append(max(pv, ps, pb) >= 0.05 if (pv is not None and ps is not None and pb is not None) else False)

colours, hatches = [], []
for pv, nv in zip(p_values, not_validated):
    if nv:            colours.append("#FFC107"); hatches.append("//")
    elif pv < 0.05:   colours.append("#4CAF50"); hatches.append(None)
    elif pv < 0.10:   colours.append("#FFC107"); hatches.append(None)
    else:             colours.append("#F44336"); hatches.append(None)

fig, ax = plt.subplots(figsize=(3.3, 2.5))
x = np.arange(len(countries))
bars = ax.bar(x, lead_times, color=colours, edgecolor="white", linewidth=0.5)
for bar, h in zip(bars, hatches):
    if h:
        bar.set_hatch(h); bar.set_edgecolor("#7A5C00")

for i, (lt, pv, nv) in enumerate(zip(lead_times, p_values, not_validated)):
    if pv >= 1.0 - 1e-9:
        ax.text(x[i], 0.08, "insuff.\ndata", ha="center", va="bottom", color="grey", fontsize=8)
    elif nv:
        ax.text(x[i], lt + 0.08, "not validated\n(perm. p ≥ .05)", ha="center", va="bottom", color="#7A5C00", fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels(countries, rotation=40, ha="right", rotation_mode="anchor")
ax.set_ylabel("Lead time (months)")
ax.set_title("Granger causality by country: UICPI → official CPI\n(calendar-true spec, United States)", fontweight="bold")
ax.set_ylim(0, 4.6)
ax.set_yticks([0, 1, 2, 3, 4])

legend_elements = [
    mpatches.Patch(facecolor="#4CAF50", label="p < 0.05, permutation-confirmed"),
    mpatches.Patch(facecolor="#FFC107", hatch="//", edgecolor="#7A5C00", label="Analytic p < 0.05, not confirmed\nby permutation (not validated)"),
    mpatches.Patch(facecolor="#FFC107", label="p < 0.10 (marginal)"),
    mpatches.Patch(facecolor="#F44336", label="Not significant"),
]
ax.legend(handles=legend_elements, loc="upper right", frameon=True, borderpad=0.3, labelspacing=0.25, handlelength=1.2)
ax.grid(axis="y", alpha=0.3)

fig.tight_layout(pad=0.3)
fig.savefig(OUT, dpi=400, bbox_inches="tight", pad_inches=0.03)
print("saved", OUT)

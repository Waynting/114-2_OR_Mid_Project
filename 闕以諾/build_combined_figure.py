"""Build a single 2x4 figure combining heuristic and greedy gap histograms,
for the compact in-report figure."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")

df = pd.read_csv(os.path.join(RES, "raw_enriched.csv"))
nice = {
    "S1_baseline": "S1 baseline",
    "S2_skewed_levels": "S2 skewed",
    "S3_imbalanced_flow": "S3 imbalanced",
    "S4_high_demand": "S4 high demand",
}
order = ["S1_baseline", "S2_skewed_levels", "S3_imbalanced_flow", "S4_high_demand"]

fig, axes = plt.subplots(2, 4, figsize=(11.5, 4.6), sharey="row")
for col, scen in enumerate(order):
    sub = df[df.scenario == scen]
    ax = axes[0, col]
    ax.hist(sub["heur_gap_rel"] * 100, bins=10, range=(0, 5),
            color="#3a7", edgecolor="black")
    ax.set_title(nice[scen], fontsize=10)
    if col == 0:
        ax.set_ylabel("heuristic\n# instances", fontsize=9)
    ax.set_xlim(0, 5)

    ax = axes[1, col]
    ax.hist(sub["greedy_gap_rel"] * 100, bins=10,
            color="#d55", edgecolor="black")
    ax.set_xlabel("relative gap (%)", fontsize=9)
    if col == 0:
        ax.set_ylabel("greedy\n# instances", fontsize=9)

fig.suptitle("Per-instance relative gap to optimal (100 instances)",
             fontsize=11)
fig.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(HERE, "problem4_gaps.png")
fig.savefig(out, dpi=150, bbox_inches="tight")
print("wrote", out)

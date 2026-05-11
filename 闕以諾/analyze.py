"""
Problem 4 — post-processing across all three experimental blocks.

Reads results/raw_all.csv (produced by run_experiment.py) and emits
    results/summary.csv       per-scenario aggregates (mean AND std)
    results/summary.tex       LaTeX-ready table for the main report
    results/hist_blockA.png
    results/hist_blockBC.png  combined histograms for Blocks B and C
    results/hist_heur_vs_greedy.png

We track three gap metrics, all reported with mean ± std (as required by the
project handout):

    Gap-to-opt  (Block A only)
        = (π_opt − π_heur) / (π_opt − L),   L = −2·ΣR_k
        worst-case-normalised, so 0 = optimal, 1 = reject-all.

    Gap-to-UB  (all blocks)
        = (π_UB − π_heur) / (π_UB − L)
        upper-bound version of the same metric; the LP UB is loose at
        supply-tight scales, so this number is only directly meaningful
        for Block A and a loose upper bound elsewhere.

    Share-vs-greedy  (all blocks)
        = (π_heur − π_greedy) / max(π_UB − π_greedy, 1)
        fraction of the "greedy → LP-UB" interval captured by the heuristic;
        robust even when the UB is loose, because both numerator and
        denominator use the same loose UB.

We also report:
    raw profits (mean ± std), acceptance rate, upgrade rate, runtime.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")

NICE = {
    "S1_baseline": "S1 baseline",
    "S2_skewed_levels": "S2 skewed",
    "S3_imbalanced_flow": "S3 imbalanced",
    "S4_high_demand": "S4 high demand",
    "M1_baseline": "M1 baseline",
    "M2_skewed_levels": "M2 skewed",
    "M3_imbalanced_flow": "M3 imbalanced",
    "M4_high_demand": "M4 high demand",
    "L1_baseline": "L1 baseline",
    "L2_skewed_levels": "L2 skewed",
    "L3_imbalanced_flow": "L3 imbalanced",
    "L4_high_demand": "L4 high demand",
}
BLOCK_LABEL = {"A": "Small (Tier 1)", "B": "Medium (Tier 2)", "C": "Large (Tier 3)"}


def _gap_to_ref(ref, plan, rev_total):
    L = -2.0 * rev_total
    denom = ref - L
    if denom <= 0:
        return np.nan
    return (ref - plan) / denom


def _share_vs_greedy(heur, greedy, ub):
    denom = ub - greedy
    if denom <= 0:
        return np.nan
    return (heur - greedy) / denom


def main():
    df = pd.read_csv(os.path.join(RES, "raw_all.csv"))

    # gaps
    df["gap_to_opt_rel"] = df.apply(
        lambda r: _gap_to_ref(r["opt_profit"], r["heur_profit"], r["rev_total"])
        if pd.notna(r["opt_profit"]) else np.nan,
        axis=1,
    )
    df["gap_to_opt_greedy_rel"] = df.apply(
        lambda r: _gap_to_ref(r["opt_profit"], r["greedy_profit"], r["rev_total"])
        if pd.notna(r["opt_profit"]) else np.nan,
        axis=1,
    )
    df["gap_to_ub_rel"] = df.apply(
        lambda r: _gap_to_ref(r["ub_profit"], r["heur_profit"], r["rev_total"]), axis=1
    )
    df["gap_to_ub_greedy_rel"] = df.apply(
        lambda r: _gap_to_ref(r["ub_profit"], r["greedy_profit"], r["rev_total"]), axis=1
    )
    df["share_vs_greedy"] = df.apply(
        lambda r: _share_vs_greedy(r["heur_profit"], r["greedy_profit"], r["ub_profit"]),
        axis=1,
    )
    df["heur_minus_greedy"] = df["heur_profit"] - df["greedy_profit"]
    df["heur_accept_rate"] = df["n_accepted_h"] / df["n_K"]
    df["heur_upgrade_rate"] = df["n_upgrades_h"] / df["n_accepted_h"].replace(0, np.nan)

    df.to_csv(os.path.join(RES, "raw_enriched.csv"), index=False)

    # ------------- per-scenario aggregate table (mean ± std) -------------
    rows = []
    for (block, scen), sub in df.groupby(["block", "scenario"]):
        rows.append({
            "block": block,
            "scenario": scen,
            "n_inst": len(sub),
            "tier_used": int(sub["tier_used"].mode().iloc[0]),
            "mean_heur_profit": sub["heur_profit"].mean(),
            "std_heur_profit": sub["heur_profit"].std(ddof=1),
            "mean_greedy_profit": sub["greedy_profit"].mean(),
            "std_greedy_profit": sub["greedy_profit"].std(ddof=1),
            "mean_ub_profit": sub["ub_profit"].mean(),
            "n_heur_opt_match": int(((sub["opt_profit"] == sub["heur_profit"]) &
                                    sub["opt_profit"].notna()).sum()),
            "mean_gap_to_opt_pct": sub["gap_to_opt_rel"].mean() * 100,
            "std_gap_to_opt_pct": sub["gap_to_opt_rel"].std(ddof=1) * 100,
            "mean_gap_to_opt_greedy_pct": sub["gap_to_opt_greedy_rel"].mean() * 100,
            "std_gap_to_opt_greedy_pct": sub["gap_to_opt_greedy_rel"].std(ddof=1) * 100,
            "mean_gap_to_ub_pct": sub["gap_to_ub_rel"].mean() * 100,
            "std_gap_to_ub_pct": sub["gap_to_ub_rel"].std(ddof=1) * 100,
            "mean_gap_to_ub_greedy_pct": sub["gap_to_ub_greedy_rel"].mean() * 100,
            "std_gap_to_ub_greedy_pct": sub["gap_to_ub_greedy_rel"].std(ddof=1) * 100,
            "mean_share_vs_greedy_pct": sub["share_vs_greedy"].mean() * 100,
            "std_share_vs_greedy_pct": sub["share_vs_greedy"].std(ddof=1) * 100,
            "mean_heur_minus_greedy": sub["heur_minus_greedy"].mean(),
            "std_heur_minus_greedy": sub["heur_minus_greedy"].std(ddof=1),
            "mean_heur_runtime_s": sub["heur_runtime"].mean(),
            "mean_heur_accept_rate_pct": sub["heur_accept_rate"].mean() * 100,
            "mean_heur_upgrade_rate_pct": sub["heur_upgrade_rate"].mean() * 100,
        })
    summary = pd.DataFrame(rows).sort_values(["block", "scenario"]).reset_index(drop=True)
    summary.to_csv(os.path.join(RES, "summary.csv"), index=False)
    print(summary.to_string(index=False))

    # ------------- LaTeX-ready table for the main report -------------
    # Block A: heur gap to OPT + greedy gap to OPT  (the meaningful metrics)
    # Blocks B/C: gap to UB + share-vs-greedy  (UB is loose; share-vs-greedy is robust)
    tex = []
    tex.append("% auto-generated by analyze.py")
    tex.append("\\begin{tabular}{l l r r r r r}")
    tex.append("\\toprule")
    tex.append(
        "Block & Scenario & N & Tier "
        "& Heur $\\pm$ std (gap, \\%) & Greedy $\\pm$ std (gap, \\%) & Share vs.\\ greedy (\\%) \\\\"
    )
    tex.append("\\midrule")
    for _, r in summary.iterrows():
        bl = BLOCK_LABEL[r["block"]]
        sc = NICE.get(r["scenario"], r["scenario"])
        if r["block"] == "A":
            # gaps measured against TRUE optimal
            h_mu, h_sd = r["mean_gap_to_opt_pct"], r["std_gap_to_opt_pct"]
            g_mu, g_sd = r["mean_gap_to_opt_greedy_pct"], r["std_gap_to_opt_greedy_pct"]
            note = ""
        else:
            # gaps measured against LP UB (loose); share-vs-greedy is the robust metric
            h_mu, h_sd = r["mean_gap_to_ub_pct"], r["std_gap_to_ub_pct"]
            g_mu, g_sd = r["mean_gap_to_ub_greedy_pct"], r["std_gap_to_ub_greedy_pct"]
            note = ""
        share_mu, share_sd = r["mean_share_vs_greedy_pct"], r["std_share_vs_greedy_pct"]
        tex.append(
            f"{bl} & {sc} & {int(r['n_inst'])} & {int(r['tier_used'])} & "
            f"{h_mu:.2f} $\\pm$ {h_sd:.2f} & "
            f"{g_mu:.2f} $\\pm$ {g_sd:.2f} & "
            f"{share_mu:.1f} $\\pm$ {share_sd:.1f}{note} \\\\"
        )
        if r["scenario"].endswith("high_demand") and r["block"] != "C":
            tex.append("\\midrule")
    tex.append("\\bottomrule")
    tex.append("\\end{tabular}")
    with open(os.path.join(RES, "summary.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(tex) + "\n")

    # ------------- histograms -------------
    _plot_block_A(df)
    _plot_block_BC(df)
    _plot_share(df)

    print(f"\nWrote {RES}/summary.csv, summary.tex, and 3 figures.")


def _plot_block_A(df):
    """Per-instance gap-to-optimal for Block A (the only block where it's defined)."""
    sub = df[df["block"] == "A"]
    fig, axes = plt.subplots(2, 4, figsize=(11.5, 4.6), sharey="row")
    order = ["S1_baseline", "S2_skewed_levels", "S3_imbalanced_flow", "S4_high_demand"]
    for col, scen in enumerate(order):
        s = sub[sub.scenario == scen]
        ax = axes[0, col]
        ax.hist(s["gap_to_opt_rel"] * 100, bins=10, range=(0, 5),
                color="#3a7", edgecolor="black")
        ax.set_title(NICE[scen], fontsize=10)
        ax.set_xlim(0, 5)
        if col == 0:
            ax.set_ylabel("heuristic\n# instances", fontsize=9)
        ax = axes[1, col]
        ax.hist(s["gap_to_opt_greedy_rel"] * 100, bins=10,
                color="#d55", edgecolor="black")
        ax.set_xlabel("gap to optimal (%)", fontsize=9)
        if col == 0:
            ax.set_ylabel("greedy\n# instances", fontsize=9)
    fig.suptitle("Block A — Small instances (Tier 1): gap to MIP optimum, 100 inst.",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(RES, "hist_blockA.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_block_BC(df):
    """For Blocks B and C, plot share-vs-greedy (robust to LP UB looseness)."""
    sub = df[df["block"].isin(["B", "C"])]
    fig, axes = plt.subplots(2, 4, figsize=(11.5, 4.6), sharey="row")
    medium_order = ["M1_baseline", "M2_skewed_levels", "M3_imbalanced_flow", "M4_high_demand"]
    large_order = ["L1_baseline", "L2_skewed_levels", "L3_imbalanced_flow", "L4_high_demand"]

    for col, scen in enumerate(medium_order):
        s = sub[sub.scenario == scen]
        ax = axes[0, col]
        ax.hist(s["share_vs_greedy"] * 100, bins=12, color="#46a", edgecolor="black")
        ax.set_title(NICE[scen], fontsize=10)
        if col == 0:
            ax.set_ylabel("Block B (Tier 2)\n# instances", fontsize=9)

    for col, scen in enumerate(large_order):
        s = sub[sub.scenario == scen]
        ax = axes[1, col]
        ax.hist(s["share_vs_greedy"] * 100, bins=12, color="#a64", edgecolor="black")
        ax.set_xlabel("share of greedy→UB interval (%)", fontsize=9)
        ax.set_title(NICE[scen], fontsize=10)
        if col == 0:
            ax.set_ylabel("Block C (Tier 3)\n# instances", fontsize=9)

    fig.suptitle("Blocks B & C — share of greedy→LP-UB interval captured by heuristic",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(RES, "hist_blockBC.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_share(df):
    """One figure: heur−greedy in NT$ across all 260 instances, broken out by block."""
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
    for ax, block, label in zip(axes, ["A", "B", "C"], list(BLOCK_LABEL.values())):
        s = df[df.block == block]
        ax.hist(s["heur_minus_greedy"], bins=15, color="#36a", edgecolor="black")
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("π_heur − π_greedy (NT$)")
        ax.axvline(0, color="red", linestyle="--", linewidth=1)
    axes[0].set_ylabel("# instances")
    fig.suptitle("Per-instance profit improvement of heuristic over naive greedy",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(os.path.join(RES, "hist_heur_vs_greedy.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

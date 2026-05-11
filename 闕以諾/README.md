# Problem 4 — Numerical experiments (闕以諾)

This folder contains a complete, self-contained solution to Problem 4
of the 114-2 OR Midterm Project. Nothing outside this folder is
modified; the experiment pulls the team's heuristic (林子宸's
`algorithm_module.py`) and feasibility checker (`find_obj_value.py`) at
import time via a `sys.path` shim.

## Layout

| File | Purpose |
|------|---------|
| `instance_generator.py` | Random instance generator + the four scenario presets (S1 baseline, S2 skewed levels, S3 imbalanced flow, S4 high demand). |
| `optimal_solver.py` | Stand-alone path-flow MILP, returns the optimal profit + recovered plan. |
| `simple_heuristic.py` | Naive same-station-first greedy benchmark. |
| `heuristic_wrapper.py` | Imports 林子宸's `heuristic_algorithm` and `find_obj_value` without modifying the original files. |
| `run_experiment.py` | Generates 25 instances × 4 scenarios, runs heuristic / optimal / greedy, writes `results/raw.csv`. |
| `analyze.py` | Builds `results/summary.csv`, `results/summary.tex`, and three histograms. |
| `problem4_report.tex` | The Problem 4 write-up alone (stand-alone document). |
| `the_report.tex` | **Full team report** — a copy of `../midtermProject_formulation.tex` with the Problem 4 placeholder replaced by the experimental writeup. Compile this to produce `the_report.pdf`. |
| `OR_flowchart.png` | Copied from `顧懷允/` so `the_report.tex` is self-contained. |
| `problem4_gaps.png` | Combined 2×4 histogram embedded in the Problem 4 section. |
| `summary_for_main.tex` | Compact summary table `\input{}`-ed by `the_report.tex`. |
| `build_combined_figure.py` | Builds `problem4_gaps.png` from `results/raw_enriched.csv`. |
| `instances/` | The 100 generated `.txt` instance files. |
| `results/` | All experiment outputs (CSVs, LaTeX table, PNG histograms). |

## Reproducing

```powershell
python run_experiment.py        # ~1 min, writes results/raw.csv
python analyze.py               # builds summary + per-scenario histograms
python build_combined_figure.py # builds the 2x4 figure used in the_report
```

Seeds are fixed in `run_experiment.py` (`BASE_SEED = 20260511`). The
exact same `raw.csv` will be produced on any machine.

## Compiling the full report

Everything `the_report.tex` needs is in this folder (the original
`midtermProject_formulation.tex` is **not** modified — `the_report.tex` is
a copy with the Problem 4 section filled in). From `闕以諾/`:

```powershell
xelatex the_report.tex   # (or pdflatex; uses tabularray, booktabs, tikz)
```

That produces `the_report.pdf`.

## Headline numbers

100 instances, 25 per scenario:

* Heuristic matches the proven optimum on **100/100** instances.
  Mean gap = 0.00 %, mean runtime ≤ 0.05 s.
* Naive greedy mean relative gap: **8.6 %** (S2) to **19.3 %** (S4).
* In the supply-constrained S4 scenario the greedy averages a
  **negative** profit (NT$ −27,676), whereas the heuristic still earns
  NT$ 9,524.

Full table and histograms are in `results/`.

"""
Problem 4 — multi-block experiment driver.

Three "blocks" of scenarios, each designed to fire one tier of the heuristic:

    Block A — Small  (Tier 1 fires): n_S=4,  n_C=6,   n_K=18–28
    Block B — Medium (Tier 2 fires): n_S=8,  n_C=20,  n_K=200–300
    Block C — Large  (Tier 3 fires): n_S=20, n_C=200, n_K=7000–10000

For each instance we record:

    heur_profit   — our 3-tier algorithm (林子宸's algorithm_module.py)
    greedy_profit — naive same-station-first greedy (lower-bound check)
    opt_profit    — exact Gurobi MIP optimum (Block A only; restricted licence
                    cannot build the MIP at medium/large scales)
    ub_profit     — LP-relaxation upper bound (time-bucket × level-threshold;
                    always computable, provably valid, but loose at tight scales)

Output: results/raw_<block>.csv, one row per instance.
"""
from __future__ import annotations

import os
import time

import pandas as pd

from instance_generator import (
    SCENARIOS_SMALL,
    SCENARIOS_MEDIUM,
    SCENARIOS_LARGE,
    generate_instance,
    write_instance,
)
import optimal_solver
import simple_heuristic
import relaxed_ub
from heuristic_wrapper import heuristic_algorithm, find_obj_value


HERE = os.path.dirname(os.path.abspath(__file__))
INST_DIR = os.path.join(HERE, "instances")
RES_DIR = os.path.join(HERE, "results")
BASE_SEED = 20260511


# Per-block instance count.  Block C is capped lower because each instance
# generates a 7000–10000-order file that the heuristic must crunch.
N_PER_BLOCK = {"A": 25, "B": 25, "C": 15}


def _count_upgrades(inst: dict, assignment) -> int:
    car_lvl = {c[0]: c[1] for c in inst["cars"]}
    cnt = 0
    for k_idx, cid in enumerate(assignment):
        if cid == -1:
            continue
        if car_lvl[cid] > inst["orders"][k_idx][1]:
            cnt += 1
    return cnt


def _tier_used(n_K, n_C) -> int:
    if n_K > 6000 or n_C * n_K > 600_000:
        return 3
    if n_K > 160 or n_C * n_K * n_K > 700_000:
        return 2
    return 1


def run_one(path: str, run_optimal: bool) -> dict:
    inst = optimal_solver.parse(path)
    rev_total = sum(o[6] for o in inst["orders"])

    # heuristic
    t0 = time.time()
    h_assign, h_reloc = heuristic_algorithm(path)
    h_t = time.time() - t0
    h_ok, h_profit = find_obj_value(path, h_assign, h_reloc)

    # naive greedy
    t0 = time.time()
    s_assign, s_reloc = simple_heuristic.solve(path)
    s_t = time.time() - t0
    s_ok, s_profit = find_obj_value(path, s_assign, s_reloc)

    # LP upper bound
    t0 = time.time()
    ub_res = relaxed_ub.compute_upper_bound(inst)
    ub_t = time.time() - t0

    # exact MIP (Block A only)
    if run_optimal:
        res = optimal_solver.solve(path, time_limit=60)
        opt_profit = res["profit"]
        opt_t = res["runtime"]
        opt_status = res["status"]
    else:
        opt_profit = None
        opt_t = None
        opt_status = "skipped"

    return dict(
        instance=os.path.basename(path),
        n_K=inst["n_K"], n_C=inst["n_C"], n_S=inst["n_S"], n_D=inst["n_D"], B=inst["B"],
        tier_used=_tier_used(inst["n_K"], inst["n_C"]),
        rev_total=rev_total,
        heur_profit=h_profit, heur_runtime=h_t, heur_feasible=h_ok,
        greedy_profit=s_profit, greedy_runtime=s_t, greedy_feasible=s_ok,
        ub_profit=ub_res["ub_profit"], ub_runtime=ub_t, ub_status=ub_res["status"],
        opt_profit=opt_profit, opt_runtime=opt_t, opt_status=opt_status,
        n_accepted_h=sum(1 for a in h_assign if a != -1),
        n_accepted_g=sum(1 for a in s_assign if a != -1),
        n_upgrades_h=_count_upgrades(inst, h_assign),
        n_upgrades_g=_count_upgrades(inst, s_assign),
    )


def run_block(scenarios, block_letter: str, run_optimal: bool):
    n = N_PER_BLOCK[block_letter]
    rows = []
    for scen_idx, scen_fn in enumerate(scenarios):
        params = scen_fn()
        print(f"\n=== Block {block_letter} | Scenario: {params.name} "
              f"(n_S={params.n_S} n_C={params.n_C} n_K={params.n_K} n_D={params.n_D}) ===")
        for i in range(n):
            seed = BASE_SEED + ord(block_letter) * 10_000 + scen_idx * 1000 + i
            inst = generate_instance(params, seed=seed)
            inst_name = f"{params.name}_{i:02d}.txt"
            path = os.path.join(INST_DIR, inst_name)
            write_instance(inst, path)

            t0 = time.time()
            res = run_one(path, run_optimal=run_optimal)
            wall = time.time() - t0
            res["scenario"] = params.name
            res["block"] = block_letter
            res["seed"] = seed
            rows.append(res)
            opt_str = f"opt={res['opt_profit']:>8}" if run_optimal else "opt=  (skip)"
            print(f"  [{i + 1:02d}/{n}] heur={res['heur_profit']:>10} "
                  f"{opt_str} ub={res['ub_profit']:>10.0f} greedy={res['greedy_profit']:>10} "
                  f"({wall:.1f}s)")
    df = pd.DataFrame(rows)
    out = os.path.join(RES_DIR, f"raw_{block_letter}.csv")
    df.to_csv(out, index=False)
    print(f"Wrote {out}")
    return df


def main():
    os.makedirs(INST_DIR, exist_ok=True)
    os.makedirs(RES_DIR, exist_ok=True)

    # Block A: small, exact MIP available
    dfA = run_block(SCENARIOS_SMALL, "A", run_optimal=True)
    # Block B: medium, MIP infeasible under free licence
    dfB = run_block(SCENARIOS_MEDIUM, "B", run_optimal=False)
    # Block C: large, MIP infeasible at any licence
    dfC = run_block(SCENARIOS_LARGE, "C", run_optimal=False)

    all_df = pd.concat([dfA, dfB, dfC], ignore_index=True)
    all_df.to_csv(os.path.join(RES_DIR, "raw_all.csv"), index=False)
    print(f"\nWrote {RES_DIR}/raw_all.csv  (total {len(all_df)} instances)")


if __name__ == "__main__":
    main()

"""
Problem 4 — random instance generator for the IEDO car-rental problem.

Generates instance files in exactly the format described in Section 3 of the
project handout, so that they are interchangeable with instance01.txt..instance05.txt.

Public entry point:
    generate_instance(params, seed) -> dict (instance in-memory)
    write_instance(instance, path)  -> writes a .txt file
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

BASE_DT = datetime(2023, 1, 1, 0, 0)


def _fmt_time(minutes: int) -> str:
    return (BASE_DT + timedelta(minutes=minutes)).strftime("%Y/%m/%d %H:%M")


@dataclass
class ScenarioParams:
    """Parameters controlling instance generation."""
    name: str
    n_S: int = 5
    n_C: int = 12
    n_L: int = 3
    n_K: int = 25
    n_D: int = 4
    B: int = 2000

    # car distribution: list of fractions per level, len == n_L; sums to 1
    car_level_dist: tuple = (1 / 3, 1 / 3, 1 / 3)
    # initial-station distribution: 'uniform' or list of fractions len == n_S
    car_station_dist: str = "uniform"

    # hourly rates per level
    rates: tuple = (200, 300, 500)

    # order-level distribution: probabilities per level (len == n_L)
    order_level_dist: tuple = (1 / 3, 1 / 3, 1 / 3)

    # station-group description for imbalanced flows.
    # If None, both pickup and return stations are uniform.
    # Else a dict with:
    #   'groups': list of list-of-station-ids (1-indexed)
    #   'pickup_group_probs': probabilities for each group
    #   'return_group_probs': probabilities for each group
    station_flow: dict | None = None

    # rental duration in hours; pick from this list uniformly
    rental_hours_choices: tuple = (1, 2, 3, 4, 6, 8, 12, 24, 36, 48)

    # moving-time matrix: random multiples of 30 in this range
    move_time_min: int = 30
    move_time_max: int = 180


def _choose_with_probs(rng: random.Random, items, probs):
    r = rng.random()
    cum = 0.0
    for x, p in zip(items, probs):
        cum += p
        if r <= cum:
            return x
    return items[-1]


def generate_instance(params: ScenarioParams, seed: int) -> dict:
    rng = random.Random(seed)

    n_S, n_C, n_L, n_K, n_D, B = (
        params.n_S, params.n_C, params.n_L, params.n_K, params.n_D, params.B
    )

    # ---- cars ----
    # split n_C into per-level counts according to car_level_dist
    levels = list(range(1, n_L + 1))
    raw_counts = [int(round(p * n_C)) for p in params.car_level_dist]
    diff = n_C - sum(raw_counts)
    raw_counts[0] += diff  # tiny correction
    cars = []
    cid = 1
    for lvl, cnt in zip(levels, raw_counts):
        for _ in range(cnt):
            init_station = rng.randint(1, n_S)
            cars.append((cid, lvl, init_station))
            cid += 1
    # in case raw_counts had to be corrected, ensure we have exactly n_C
    cars = cars[:n_C]
    while len(cars) < n_C:
        lvl = rng.choice(levels)
        cars.append((len(cars) + 1, lvl, rng.randint(1, n_S)))

    # ---- hourly rates ----
    rates = list(params.rates[:n_L])
    while len(rates) < n_L:
        rates.append(rates[-1] + 100)

    # ---- moving time matrix (symmetric, T_ii = 0, multiples of 30) ----
    move = [[0] * (n_S + 1) for _ in range(n_S + 1)]
    for i in range(1, n_S + 1):
        for j in range(i + 1, n_S + 1):
            k_min = params.move_time_min // 30
            k_max = params.move_time_max // 30
            v = 30 * rng.randint(k_min, k_max)
            move[i][j] = v
            move[j][i] = v

    # ---- orders ----
    # Pickup time uniform within first (n_D - 1) days (so the rental fits).
    # Actually: pick pickup in first n_D days, then rental hours from rental_hours_choices,
    # but capped so return <= n_D * 1440.
    horizon_minutes = n_D * 1440
    orders = []

    # set up flow groups if any
    if params.station_flow is not None:
        groups = params.station_flow["groups"]
        p_pick = params.station_flow["pickup_group_probs"]
        p_ret = params.station_flow["return_group_probs"]

    for kid in range(1, n_K + 1):
        # car level requested
        lvl = _choose_with_probs(rng, levels, params.order_level_dist)

        # pick-up / return stations
        if params.station_flow is None:
            ps = rng.randint(1, n_S)
            rs = rng.randint(1, n_S)
        else:
            pg = _choose_with_probs(rng, groups, p_pick)
            rg = _choose_with_probs(rng, groups, p_ret)
            ps = rng.choice(pg)
            rs = rng.choice(rg)

        # rental hours: keep retrying until the order fits the horizon
        for _ in range(20):
            rent_h = rng.choice(params.rental_hours_choices)
            # pickup is a half-hour multiple in [0, horizon - 60*rent_h]
            max_pickup_min = horizon_minutes - 60 * rent_h
            if max_pickup_min < 0:
                continue
            pickup_slot = rng.randint(0, max_pickup_min // 30)
            pt = 30 * pickup_slot
            rt = pt + 60 * rent_h
            break
        else:
            # fallback to smallest rental
            rent_h = 1
            pt = 0
            rt = 60
        orders.append((kid, lvl, ps, rs, pt, rt))

    return {
        "params": params,
        "n_S": n_S, "n_C": n_C, "n_L": n_L, "n_K": n_K, "n_D": n_D, "B": B,
        "cars": cars,
        "rates": rates,
        "orders": orders,
        "move": move,
    }


def write_instance(inst: dict, path: str) -> None:
    lines = []
    lines.append("n_S,n_C,n_L,n_K,n_D,B")
    lines.append(f"{inst['n_S']},{inst['n_C']},{inst['n_L']},{inst['n_K']},{inst['n_D']},{inst['B']}")
    lines.append("==========")
    lines.append("Car ID,Level,Initial station")
    for cid, lvl, st in inst["cars"]:
        lines.append(f"{cid},{lvl},{st}")
    lines.append("==========")
    lines.append("Car level,Hour rate")
    for lvl, rate in enumerate(inst["rates"], start=1):
        lines.append(f"{lvl},{rate}")
    lines.append("==========")
    lines.append("Order ID,Level,Pick-up station,Return station,Pick-up time,Return time")
    for kid, lvl, ps, rs, pt, rt in inst["orders"]:
        lines.append(f"{kid},{lvl},{ps},{rs},{_fmt_time(pt)},{_fmt_time(rt)}")
    lines.append("==========")
    lines.append("From,To,Moving time")
    for i in range(1, inst["n_S"] + 1):
        for j in range(1, inst["n_S"] + 1):
            lines.append(f"{i},{j},{inst['move'][i][j]}")
    lines.append("==========")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ----- Scenario presets used in the experiment -----
# Sizes are chosen so the MIP benchmark stays within the Gurobi
# free-license variable/constraint limits while still producing
# tension (so neither benchmark trivially accepts every order).
def baseline() -> ScenarioParams:
    return ScenarioParams(
        name="S1_baseline",
        n_S=4, n_C=6, n_L=3, n_K=18, n_D=3, B=900,
        car_level_dist=(1 / 3, 1 / 3, 1 / 3),
        order_level_dist=(1 / 3, 1 / 3, 1 / 3),
        rates=(200, 300, 500),
        rental_hours_choices=(2, 3, 4, 6, 8, 12, 18, 24),
        move_time_min=30, move_time_max=150,
    )


def scenario_skewed_levels() -> ScenarioParams:
    p = baseline()
    p.name = "S2_skewed_levels"
    p.order_level_dist = (0.6, 0.3, 0.1)
    return p


def scenario_imbalanced_flow() -> ScenarioParams:
    p = baseline()
    p.name = "S3_imbalanced_flow"
    # split 4 stations into 2 groups: {1,2} (city centre) and {3,4} (suburbs)
    p.station_flow = {
        "groups": [[1, 2], [3, 4]],
        "pickup_group_probs": (0.7, 0.3),
        "return_group_probs": (0.2, 0.8),
    }
    return p


def scenario_high_demand() -> ScenarioParams:
    p = baseline()
    p.name = "S4_high_demand"
    p.n_K = 28  # ~50% more orders, same fleet — forces rejections
    return p


# =========================================================================
# Tier 2 (medium) scenarios — designed to skip the heuristic's Tier 1 MIP
# (which triggers on n_K > 160 OR n_C * n_K^2 > 700,000) but to stay within
# Tier 2's insertion-heuristic regime (n_K <= 6000 AND n_C * n_K <= 600,000).
# =========================================================================
def medium_baseline() -> ScenarioParams:
    return ScenarioParams(
        name="M1_baseline",
        n_S=8, n_C=20, n_L=3, n_K=200, n_D=5, B=4000,
        car_level_dist=(1 / 3, 1 / 3, 1 / 3),
        order_level_dist=(1 / 3, 1 / 3, 1 / 3),
        rates=(200, 300, 500),
        rental_hours_choices=(2, 3, 4, 6, 8, 12, 18, 24),
        move_time_min=30, move_time_max=180,
    )


def medium_skewed_levels() -> ScenarioParams:
    p = medium_baseline()
    p.name = "M2_skewed_levels"
    p.order_level_dist = (0.6, 0.3, 0.1)
    return p


def medium_imbalanced_flow() -> ScenarioParams:
    p = medium_baseline()
    p.name = "M3_imbalanced_flow"
    p.station_flow = {
        "groups": [[1, 2, 3, 4], [5, 6, 7, 8]],
        "pickup_group_probs": (0.7, 0.3),
        "return_group_probs": (0.2, 0.8),
    }
    return p


def medium_high_demand() -> ScenarioParams:
    p = medium_baseline()
    p.name = "M4_high_demand"
    p.n_K = 300  # 50% more orders
    return p


# =========================================================================
# Tier 3 (large) scenarios — n_K > 6000 forces both Tier 1 and Tier 2 to
# fall through to the heap-based chronological greedy.
# =========================================================================
def large_baseline() -> ScenarioParams:
    return ScenarioParams(
        name="L1_baseline",
        n_S=20, n_C=200, n_L=3, n_K=7000, n_D=10, B=20000,
        car_level_dist=(1 / 3, 1 / 3, 1 / 3),
        order_level_dist=(1 / 3, 1 / 3, 1 / 3),
        rates=(200, 300, 500),
        rental_hours_choices=(2, 3, 4, 6, 8, 12, 18, 24),
        move_time_min=30, move_time_max=180,
    )


def large_skewed_levels() -> ScenarioParams:
    p = large_baseline()
    p.name = "L2_skewed_levels"
    p.order_level_dist = (0.6, 0.3, 0.1)
    return p


def large_imbalanced_flow() -> ScenarioParams:
    p = large_baseline()
    p.name = "L3_imbalanced_flow"
    p.station_flow = {
        "groups": [list(range(1, 11)), list(range(11, 21))],
        "pickup_group_probs": (0.7, 0.3),
        "return_group_probs": (0.2, 0.8),
    }
    return p


def large_high_demand() -> ScenarioParams:
    p = large_baseline()
    p.name = "L4_high_demand"
    p.n_K = 10000
    return p


SCENARIOS_SMALL = [
    baseline,
    scenario_skewed_levels,
    scenario_imbalanced_flow,
    scenario_high_demand,
]
SCENARIOS_MEDIUM = [
    medium_baseline,
    medium_skewed_levels,
    medium_imbalanced_flow,
    medium_high_demand,
]
SCENARIOS_LARGE = [
    large_baseline,
    large_skewed_levels,
    large_imbalanced_flow,
    large_high_demand,
]

# Back-compat alias used by the original Tier-1-only driver.
SCENARIOS = SCENARIOS_SMALL


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "instances")
    os.makedirs(out_dir, exist_ok=True)
    for scen_fn in SCENARIOS:
        params = scen_fn()
        for i in range(3):
            inst = generate_instance(params, seed=1000 + i)
            path = os.path.join(out_dir, f"{params.name}_{i:02d}.txt")
            write_instance(inst, path)
            print(f"wrote {path}")

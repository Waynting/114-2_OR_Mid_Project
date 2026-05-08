"""
Problem 1 — IEDO car-rental relocation+upgrade planning.

MIP formulation: per-car path/sequencing.
Solves instance05.txt with Gurobi. Expected optimal objective = 106,800.

Run:
    /Users/waynliu/.venvs/OR/bin/python problem1_solve.py
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
INSTANCE_PATH = Path(
    "/Users/waynliu/Documents/NTU/台大/大二下/OR/114-2_OR_Mid_Project/"
    "Material_from_cool/OR114-2_midtermProject_data/data/instance05.txt"
)
SOLUTION_TXT = HERE / "problem1_solution.txt"

# Time origin: 2023/01/01 00:00.
T_ORIGIN = datetime(2023, 1, 1, 0, 0)


def to_minutes(ts: str) -> int:
    """Convert 'YYYY/MM/DD HH:MM' to minutes since T_ORIGIN."""
    dt = datetime.strptime(ts, "%Y/%m/%d %H:%M")
    delta = dt - T_ORIGIN
    return int(delta.total_seconds() // 60)


def fmt_time(minutes: int) -> str:
    """Inverse of to_minutes — for human-readable output."""
    from datetime import timedelta
    dt = T_ORIGIN + timedelta(minutes=minutes)
    return dt.strftime("%Y/%m/%d %H:%M")


# ---------------------------------------------------------------------------
# Instance dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Car:
    cid: int
    level: int
    init_station: int


@dataclass
class Order:
    kid: int
    level: int
    pickup_station: int
    return_station: int
    pickup_time: int   # minutes
    return_time: int   # minutes
    revenue: float


@dataclass
class Instance:
    n_S: int
    n_C: int
    n_L: int
    n_K: int
    n_D: int
    B: int
    cars: list[Car]
    rates: dict[int, float]      # level -> hourly rate
    orders: list[Order]
    T: dict[tuple[int, int], int]  # (i,j) -> minutes


def parse_instance(path: Path) -> Instance:
    """Parse the 5-section instance file."""
    text = path.read_text(encoding="utf-8")
    sections = [s.strip() for s in text.split("==========")]
    # Section 0: header
    header_lines = [ln for ln in sections[0].splitlines() if ln.strip()]
    # header_lines[0] is the column-name row, [1] is values
    nS, nC, nL, nK, nD, B = (int(x) for x in header_lines[1].split(","))

    # Section 1: cars
    car_lines = [ln for ln in sections[1].splitlines() if ln.strip()][1:]
    cars: list[Car] = []
    for ln in car_lines:
        cid, lvl, init = (int(x) for x in ln.split(","))
        cars.append(Car(cid=cid, level=lvl, init_station=init))

    # Section 2: hour rates
    rate_lines = [ln for ln in sections[2].splitlines() if ln.strip()][1:]
    rates: dict[int, float] = {}
    for ln in rate_lines:
        lvl, rate = ln.split(",")
        rates[int(lvl)] = float(rate)

    # Section 3: orders
    order_lines = [ln for ln in sections[3].splitlines() if ln.strip()][1:]
    orders: list[Order] = []
    for ln in order_lines:
        parts = ln.split(",")
        kid = int(parts[0])
        lvl = int(parts[1])
        ps = int(parts[2])
        rs = int(parts[3])
        pt = to_minutes(parts[4].strip())
        rt = to_minutes(parts[5].strip())
        # Hours rented: H_k = (return - pickup) in hours.
        H = (rt - pt) / 60.0
        rev = rates[lvl] * H
        orders.append(
            Order(
                kid=kid,
                level=lvl,
                pickup_station=ps,
                return_station=rs,
                pickup_time=pt,
                return_time=rt,
                revenue=rev,
            )
        )

    # Section 4: moving times
    t_lines = [ln for ln in sections[4].splitlines() if ln.strip()][1:]
    T: dict[tuple[int, int], int] = {}
    for ln in t_lines:
        i, j, m = (int(x) for x in ln.split(","))
        T[(i, j)] = m

    return Instance(
        n_S=nS, n_C=nC, n_L=nL, n_K=nK, n_D=nD, B=B,
        cars=cars, rates=rates, orders=orders, T=T,
    )


# ---------------------------------------------------------------------------
# Feasibility helpers
# ---------------------------------------------------------------------------
PICKUP_LEAD = 30           # car must be ready 30 min before pickup
READY_BUFFER_AFTER_RET = 4 * 60  # 1h late buffer + 3h cleaning = 240 min


def car_can_serve(car: Car, order: Order) -> bool:
    """Level rule: car-level L can serve order-level L or L-1 (one-step upgrade)."""
    return order.level == car.level or order.level + 1 == car.level


def source_arc_feasible(car: Car, order: Order, T: dict) -> bool:
    """Car at init station at time 0; can it serve `order` directly?

    Per the problem statement, all cars are considered ready at the very
    beginning of the planning horizon ("may be picked up by a consumer right
    away at the beginning moment").  So if the car's initial station already
    matches the pick-up station (T = 0), the order is feasible regardless of
    the pick-up time.  Otherwise an employee must drive the car from
    init_station to pickup_station; the earliest possible arrival is `travel`
    minutes after time 0, and the car must be ready 30 minutes before pickup.
    """
    travel = T[(car.init_station, order.pickup_station)]
    if travel == 0:
        return True
    return travel <= order.pickup_time - PICKUP_LEAD


def chain_feasible(prev: Order, nxt: Order, T: dict) -> bool:
    """After serving `prev`, can the same car serve `nxt` next?

    Car becomes ready at prev.return_station at prev.return_time + 240.
    Then travels T(ret_prev, pick_nxt) minutes to reach pickup station.
    Must arrive at least PICKUP_LEAD min before nxt.pickup_time.
    """
    travel = T[(prev.return_station, nxt.pickup_station)]
    ready = prev.return_time + READY_BUFFER_AFTER_RET
    return ready + travel <= nxt.pickup_time - PICKUP_LEAD


def relocation_minutes_source(car: Car, order: Order, T: dict) -> int:
    """Travel minutes when going from car's init station to order's pickup station."""
    return T[(car.init_station, order.pickup_station)]


def relocation_minutes_chain(prev: Order, nxt: Order, T: dict) -> int:
    """Travel minutes when going from prev's return station to nxt's pickup station."""
    return T[(prev.return_station, nxt.pickup_station)]


# ---------------------------------------------------------------------------
# MIP build & solve
# ---------------------------------------------------------------------------
def solve(inst: Instance):
    m = gp.Model("IEDO_problem1")
    m.setParam("OutputFlag", 1)
    m.setParam("TimeLimit", 300)

    K = inst.orders
    C = inst.cars
    T = inst.T
    nK = len(K)
    nC = len(C)

    # Decision variables ----------------------------------------------------
    # x_source[c, k]   : car c starts the day by going to and serving order k
    # x_chain[c, i, j] : car c serves order i then immediately serves order j
    # x_sink[c, k]     : car c finishes after serving order k (so the path ends there)
    # y[k]             : order k is accepted

    x_source: dict[tuple[int, int], gp.Var] = {}
    x_chain: dict[tuple[int, int, int], gp.Var] = {}
    x_sink: dict[tuple[int, int], gp.Var] = {}

    for c in C:
        for ki, k in enumerate(K):
            if not car_can_serve(c, k):
                continue
            if source_arc_feasible(c, k, T):
                x_source[(c.cid, k.kid)] = m.addVar(
                    vtype=GRB.BINARY, name=f"src_c{c.cid}_k{k.kid}"
                )
            x_sink[(c.cid, k.kid)] = m.addVar(
                vtype=GRB.BINARY, name=f"snk_c{c.cid}_k{k.kid}"
            )
            for kj, knext in enumerate(K):
                if knext.kid == k.kid:
                    continue
                if not car_can_serve(c, knext):
                    continue
                if chain_feasible(k, knext, T):
                    x_chain[(c.cid, k.kid, knext.kid)] = m.addVar(
                        vtype=GRB.BINARY,
                        name=f"chn_c{c.cid}_k{k.kid}_k{knext.kid}",
                    )

    y = {k.kid: m.addVar(vtype=GRB.BINARY, name=f"y_k{k.kid}") for k in K}

    m.update()

    # Constraints -----------------------------------------------------------
    # 1) Each car leaves its source at most once (a car serves at most one
    #    "first" order).  Equivalently: out-degree of source ≤ 1.
    #    Path can be empty (car sits at home).
    for c in C:
        out_src = [x_source[(c.cid, k.kid)] for k in K
                   if (c.cid, k.kid) in x_source]
        if out_src:
            m.addConstr(gp.quicksum(out_src) <= 1, name=f"src_out_c{c.cid}")

    # 2) Flow conservation at each (car, order) node:
    #    incoming (source + chain in) = outgoing (chain out + sink) = served-by-c
    #    Define z[c,k] = whether car c serves order k = sum of incoming arcs.
    z: dict[tuple[int, int], gp.LinExpr] = {}
    for c in C:
        for k in K:
            if not car_can_serve(c, k):
                continue
            in_terms: list[gp.Var] = []
            if (c.cid, k.kid) in x_source:
                in_terms.append(x_source[(c.cid, k.kid)])
            for kprev in K:
                if kprev.kid == k.kid:
                    continue
                if (c.cid, kprev.kid, k.kid) in x_chain:
                    in_terms.append(x_chain[(c.cid, kprev.kid, k.kid)])

            out_terms: list[gp.Var] = []
            if (c.cid, k.kid) in x_sink:
                out_terms.append(x_sink[(c.cid, k.kid)])
            for knext in K:
                if knext.kid == k.kid:
                    continue
                if (c.cid, k.kid, knext.kid) in x_chain:
                    out_terms.append(x_chain[(c.cid, k.kid, knext.kid)])

            in_expr = gp.quicksum(in_terms) if in_terms else gp.LinExpr(0.0)
            out_expr = gp.quicksum(out_terms) if out_terms else gp.LinExpr(0.0)
            m.addConstr(in_expr == out_expr, name=f"flow_c{c.cid}_k{k.kid}")
            z[(c.cid, k.kid)] = in_expr  # served-by-c indicator (LinExpr 0/1)

    # 3) Each order served at most once across all cars; tied to acceptance y.
    for k in K:
        served = [z[(c.cid, k.kid)] for c in C if (c.cid, k.kid) in z]
        if served:
            m.addConstr(gp.quicksum(served) == y[k.kid], name=f"acc_k{k.kid}")
        else:
            m.addConstr(y[k.kid] == 0, name=f"acc_k{k.kid}_none")

    # 4) Relocation budget: sum of travel minutes on every selected arc ≤ B.
    reloc_terms: list[gp.LinExpr] = []
    for (cid, kid), var in x_source.items():
        car = next(c for c in C if c.cid == cid)
        order = next(k for k in K if k.kid == kid)
        t = relocation_minutes_source(car, order, T)
        if t > 0:
            reloc_terms.append(t * var)
    for (cid, ki, kj), var in x_chain.items():
        ki_o = next(k for k in K if k.kid == ki)
        kj_o = next(k for k in K if k.kid == kj)
        t = relocation_minutes_chain(ki_o, kj_o, T)
        if t > 0:
            reloc_terms.append(t * var)
    if reloc_terms:
        m.addConstr(gp.quicksum(reloc_terms) <= inst.B, name="budget")

    # Objective -------------------------------------------------------------
    # profit = sum_k R_k * y_k - sum_k 2 R_k * (1 - y_k)
    #        = sum_k 3 R_k * y_k - 2 sum_k R_k
    rev_total = sum(k.revenue for k in K)
    profit = gp.quicksum(3.0 * k.revenue * y[k.kid] for k in K) - 2.0 * rev_total
    m.setObjective(profit, GRB.MAXIMIZE)

    m.optimize()

    if m.Status not in (GRB.OPTIMAL, GRB.SUBOPTIMAL, GRB.TIME_LIMIT):
        raise RuntimeError(f"Gurobi did not find a solution. Status={m.Status}")
    if m.SolCount == 0:
        raise RuntimeError("No feasible solution found.")

    return m, x_source, x_chain, x_sink, y, z


# ---------------------------------------------------------------------------
# Plan recovery
# ---------------------------------------------------------------------------
def recover_plan(inst, x_source, x_chain, x_sink, y):
    K = inst.orders
    C = inst.cars
    T = inst.T
    by_kid = {k.kid: k for k in K}
    by_cid = {c.cid: c for c in C}

    car_routes: dict[int, list[int]] = {c.cid: [] for c in C}
    for c in C:
        # find source arc, if any
        first = None
        for k in K:
            v = x_source.get((c.cid, k.kid))
            if v is not None and v.X > 0.5:
                first = k.kid
                break
        if first is None:
            continue
        seq = [first]
        cur = first
        while True:
            nxt = None
            for k in K:
                v = x_chain.get((c.cid, cur, k.kid))
                if v is not None and v.X > 0.5:
                    nxt = k.kid
                    break
            if nxt is None:
                break
            seq.append(nxt)
            cur = nxt
        car_routes[c.cid] = seq

    accepted: list[int] = sorted(kid for kid in y if y[kid].X > 0.5)
    rejected: list[int] = sorted(kid for kid in y if y[kid].X <= 0.5)

    # Determine upgrade per accepted order: served by car of higher level.
    served_by: dict[int, int] = {}
    upgraded: dict[int, bool] = {}
    for cid, seq in car_routes.items():
        for kid in seq:
            served_by[kid] = cid
    for kid in accepted:
        car = by_cid[served_by[kid]]
        order = by_kid[kid]
        upgraded[kid] = car.level > order.level

    # Build relocation list (only entries with travel time > 0).
    relocations: list[dict] = []
    for cid, seq in car_routes.items():
        if not seq:
            continue
        car = by_cid[cid]
        # Source -> first
        first_o = by_kid[seq[0]]
        t_src = T[(car.init_station, first_o.pickup_station)]
        if t_src > 0:
            depart = max(0, first_o.pickup_time - PICKUP_LEAD - t_src)
            relocations.append({
                "car": cid,
                "from_station": car.init_station,
                "to_station": first_o.pickup_station,
                "depart_minute": depart,
                "arrive_minute": depart + t_src,
                "duration": t_src,
                "context": f"initial position -> serve order {first_o.kid}",
            })
        # chain pieces
        for prev_kid, next_kid in zip(seq, seq[1:]):
            prev_o = by_kid[prev_kid]
            next_o = by_kid[next_kid]
            t = T[(prev_o.return_station, next_o.pickup_station)]
            if t > 0:
                ready = prev_o.return_time + READY_BUFFER_AFTER_RET
                depart = max(ready, next_o.pickup_time - PICKUP_LEAD - t)
                relocations.append({
                    "car": cid,
                    "from_station": prev_o.return_station,
                    "to_station": next_o.pickup_station,
                    "depart_minute": depart,
                    "arrive_minute": depart + t,
                    "duration": t,
                    "context": (
                        f"after order {prev_o.kid} -> serve order {next_o.kid}"
                    ),
                })
    total_reloc = sum(r["duration"] for r in relocations)
    return car_routes, accepted, rejected, served_by, upgraded, relocations, total_reloc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    inst = parse_instance(INSTANCE_PATH)
    print(f"Parsed instance: n_S={inst.n_S}, n_C={inst.n_C}, n_L={inst.n_L}, "
          f"n_K={inst.n_K}, n_D={inst.n_D}, B={inst.B}")
    print("Hour rates:", inst.rates)
    rev_total = sum(k.revenue for k in inst.orders)
    print(f"Sum of all order revenues = {rev_total:.2f}; "
          f"compensation if all rejected = {2*rev_total:.2f}")
    print()

    m, x_source, x_chain, x_sink, y, z = solve(inst)
    obj = m.ObjVal
    print(f"\nOptimal objective (profit) = {obj:.2f}")

    routes, accepted, rejected, served_by, upgraded, relocs, total_reloc = (
        recover_plan(inst, x_source, x_chain, x_sink, y)
    )

    # Validation: profit = 3*revenue_accepted - 2*revenue_total
    rev_accepted = sum(o.revenue for o in inst.orders if o.kid in accepted)
    expected = 3.0 * rev_accepted - 2.0 * rev_total
    print(f"Sanity: 3*rev_accepted - 2*rev_total = "
          f"3*{rev_accepted:.2f} - 2*{rev_total:.2f} = {expected:.2f}")

    print("\nAccepted orders:", accepted)
    print("Rejected orders:", rejected)
    print(f"Total relocation minutes used: {total_reloc} / {inst.B}")
    print()

    print("=== Per-car schedules ===")
    for c in inst.cars:
        seq = routes[c.cid]
        if not seq:
            print(f"Car {c.cid} (level {c.level}, init st. {c.init_station}): idle (no orders)")
            continue
        parts = []
        for kid in seq:
            o = next(k for k in inst.orders if k.kid == kid)
            tag = " (upgrade)" if upgraded[kid] else ""
            parts.append(
                f"order {kid}{tag} [pick {o.pickup_station} {fmt_time(o.pickup_time)}"
                f" -> ret {o.return_station} {fmt_time(o.return_time)}]"
            )
        print(f"Car {c.cid} (level {c.level}, init st. {c.init_station}): "
              + " -> ".join(parts))

    print("\n=== Relocation list ===")
    if not relocs:
        print("(no relocations)")
    for r in relocs:
        print(f"  Car {r['car']}: st.{r['from_station']} -> st.{r['to_station']} "
              f"depart {fmt_time(r['depart_minute'])} arrive {fmt_time(r['arrive_minute'])} "
              f"({r['duration']} min) — {r['context']}")

    # ------------------------------------------------------------------
    # Save solution file
    # ------------------------------------------------------------------
    summary: dict = {
        "instance": "instance05.txt",
        "objective_value": obj,
        "revenue_total": rev_total,
        "revenue_accepted": rev_accepted,
        "compensation_paid": 2.0 * sum(o.revenue for o in inst.orders if o.kid in rejected),
        "B_minutes_budget": inst.B,
        "B_minutes_used": total_reloc,
        "accepted_orders": accepted,
        "rejected_orders": rejected,
        "served_by": {str(k): v for k, v in served_by.items()},
        "upgraded": {str(k): v for k, v in upgraded.items()},
        "car_routes": {str(c): routes[c] for c in routes},
        "relocations": [
            {
                **r,
                "depart_time": fmt_time(r["depart_minute"]),
                "arrive_time": fmt_time(r["arrive_minute"]),
            }
            for r in relocs
        ],
        "orders": [
            {
                "kid": o.kid,
                "level": o.level,
                "pickup_station": o.pickup_station,
                "return_station": o.return_station,
                "pickup_time": fmt_time(o.pickup_time),
                "return_time": fmt_time(o.return_time),
                "revenue": o.revenue,
            }
            for o in inst.orders
        ],
    }

    with SOLUTION_TXT.open("w", encoding="utf-8") as f:
        f.write("# Problem 1 — IEDO car-rental relocation+upgrade plan\n")
        f.write("# Instance: instance05.txt\n")
        f.write(f"# Optimal objective (profit): {obj:.2f}\n")
        f.write(f"# Revenue earned (accepted): {rev_accepted:.2f}\n")
        f.write(f"# Compensation paid (rejected x 2): "
                f"{2.0 * sum(o.revenue for o in inst.orders if o.kid in rejected):.2f}\n")
        f.write(f"# Net profit = revenue - compensation = "
                f"{rev_accepted - 2.0 * sum(o.revenue for o in inst.orders if o.kid in rejected):.2f}\n")
        f.write(f"# Relocation budget B = {inst.B} min, used = {total_reloc} min\n")
        f.write("\n# JSON summary follows:\n")
        f.write(json.dumps(summary, indent=2, ensure_ascii=False))
        f.write("\n")
    print(f"\nSolution summary written to: {SOLUTION_TXT}")
    return summary


if __name__ == "__main__":
    main()

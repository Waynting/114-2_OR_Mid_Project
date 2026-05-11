"""
Problem 4 — exact MIP benchmark.

Solves the same path-flow MILP used in Problem 1, but as a self-contained
module that just reads an instance and returns (assignment, relocation, profit, gap, runtime).

Profit accounting follows the problem statement:
    profit = sum_{accepted} R_k  -  2 * sum_{rejected} R_k
           = 3 * sum_{accepted} R_k  -  2 * sum_all R_k
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import gurobipy as gp
from gurobipy import GRB

BASE_DT = datetime(2023, 1, 1, 0, 0)
PICKUP_LEAD = 30
READY_AFTER_RETURN = 240  # 1 h late buffer + 3 h cleaning


def _to_min(s: str) -> int:
    dt = datetime.strptime(s, "%Y/%m/%d %H:%M")
    delta = dt - BASE_DT
    return delta.days * 1440 + delta.seconds // 60


def _fmt(m: int) -> str:
    return (BASE_DT + timedelta(minutes=m)).strftime("%Y/%m/%d %H:%M")


def _read_sections(path):
    sections = []
    section = []
    with open(path, "r", encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("="):
                if section:
                    sections.append(section)
                    section = []
            else:
                section.append([v.strip() for v in line.split(",")])
    if section:
        sections.append(section)
    return sections


def parse(path):
    sec = _read_sections(path)
    g = sec[0][1]
    n_S, n_C, n_L, n_K, n_D, B = (int(g[i]) for i in range(6))

    cars = []  # (cid, lvl, init_st)
    for row in sec[1][1:]:
        cars.append((int(row[0]), int(row[1]), int(row[2])))

    rates = {}
    for row in sec[2][1:]:
        rates[int(row[0])] = int(row[1])

    orders = []  # (kid, lvl, ps, rs, pt, rt, rev)
    for row in sec[3][1:]:
        kid, lvl = int(row[0]), int(row[1])
        ps, rs = int(row[2]), int(row[3])
        pt, rt = _to_min(row[4]), _to_min(row[5])
        rent_h = (rt - pt) // 60
        rev = rates[lvl] * rent_h
        orders.append((kid, lvl, ps, rs, pt, rt, rev))

    T = {}
    for row in sec[4][1:]:
        T[(int(row[0]), int(row[1]))] = int(row[2])

    return dict(n_S=n_S, n_C=n_C, n_L=n_L, n_K=n_K, n_D=n_D, B=B,
                cars=cars, rates=rates, orders=orders, T=T)


def _can_serve(car_lvl, order_lvl):
    """Order asking for level l can be served by level l or l+1 cars."""
    return car_lvl == order_lvl or car_lvl == order_lvl + 1


def _source_ok(car, order, T):
    # all cars are ready at t=0 at their initial station, so the only constraint
    # is reach pickup_station 30 min before pickup_time
    _, _, init_st = car
    _, _, ps, _, pt, _, _ = order
    travel = T[(init_st, ps)]
    if pt == 0:
        return travel == 0
    return travel <= pt - PICKUP_LEAD


def _chain_ok(prev_o, next_o, T):
    _, _, _, rs_prev, _, rt_prev, _ = prev_o
    _, _, ps_next, _, pt_next, _, _ = next_o
    travel = T[(rs_prev, ps_next)]
    ready = rt_prev + READY_AFTER_RETURN
    if pt_next == 0:
        return False  # can't chain into a t=0 order
    return ready + travel <= pt_next - PICKUP_LEAD


def solve(path, time_limit=60, verbose=False):
    """Returns dict with profit, assignment, relocation, gap, runtime, status."""
    inst = parse(path)
    cars = inst["cars"]
    orders = inst["orders"]
    T = inst["T"]
    B = inst["B"]
    n_K = inst["n_K"]

    by_kid = {o[0]: o for o in orders}
    by_cid = {c[0]: c for c in cars}

    tic = time.time()
    m = gp.Model()
    m.setParam("OutputFlag", 1 if verbose else 0)
    m.setParam("TimeLimit", time_limit)
    m.setParam("MIPGap", 1e-6)

    x_src = {}   # (cid, kid)
    x_chn = {}   # (cid, kid_prev, kid_next)
    for c in cars:
        cid, clvl, _ = c
        for k in orders:
            kid, klvl = k[0], k[1]
            if not _can_serve(clvl, klvl):
                continue
            if _source_ok(c, k, T):
                x_src[(cid, kid)] = m.addVar(vtype=GRB.BINARY)
            for k2 in orders:
                kid2, klvl2 = k2[0], k2[1]
                if kid2 == kid or not _can_serve(clvl, klvl2):
                    continue
                if _chain_ok(k, k2, T):
                    x_chn[(cid, kid, kid2)] = m.addVar(vtype=GRB.BINARY)

    y = {k[0]: m.addVar(vtype=GRB.BINARY) for k in orders}
    m.update()

    # at most one outgoing source arc per car
    for c in cars:
        cid = c[0]
        out_src = [v for (ci, kid), v in x_src.items() if ci == cid]
        if out_src:
            m.addConstr(gp.quicksum(out_src) <= 1)

    # flow conservation: incoming = outgoing per (car, order)
    # incoming = source + chain-in ; outgoing = chain-out
    # served-by-c indicator is the incoming sum
    z = {}  # (cid, kid) -> LinExpr
    for c in cars:
        cid, clvl, _ = c
        for k in orders:
            kid, klvl = k[0], k[1]
            if not _can_serve(clvl, klvl):
                continue
            in_terms = []
            if (cid, kid) in x_src:
                in_terms.append(x_src[(cid, kid)])
            for k2 in orders:
                if k2[0] != kid and (cid, k2[0], kid) in x_chn:
                    in_terms.append(x_chn[(cid, k2[0], kid)])
            out_terms = []
            for k2 in orders:
                if k2[0] != kid and (cid, kid, k2[0]) in x_chn:
                    out_terms.append(x_chn[(cid, kid, k2[0])])
            in_expr = gp.quicksum(in_terms) if in_terms else gp.LinExpr(0.0)
            out_expr = gp.quicksum(out_terms) if out_terms else gp.LinExpr(0.0)
            # outgoing <= incoming (cannot leave order without entering it)
            m.addConstr(out_expr <= in_expr)
            z[(cid, kid)] = in_expr

    # accept y_k iff exactly one car visits it
    for k in orders:
        kid = k[0]
        terms = [z[(c[0], kid)] for c in cars if (c[0], kid) in z]
        if terms:
            m.addConstr(gp.quicksum(terms) == y[kid])
        else:
            m.addConstr(y[kid] == 0)

    # relocation budget
    reloc = []
    for (cid, kid), v in x_src.items():
        car = by_cid[cid]; o = by_kid[kid]
        t = T[(car[2], o[2])]
        if t > 0:
            reloc.append(t * v)
    for (cid, ki, kj), v in x_chn.items():
        oi = by_kid[ki]; oj = by_kid[kj]
        t = T[(oi[3], oj[2])]
        if t > 0:
            reloc.append(t * v)
    if reloc:
        m.addConstr(gp.quicksum(reloc) <= B)

    # objective: maximize  3 * sum(R_k * y_k)  - 2 * sum(R_k)  (constant dropped)
    rev_total = sum(o[6] for o in orders)
    m.setObjective(gp.quicksum(3 * o[6] * y[o[0]] for o in orders), GRB.MAXIMIZE)
    m.optimize()
    toc = time.time()

    if m.SolCount == 0:
        return dict(profit=None, assignment=None, relocation=None,
                    gap=None, runtime=toc - tic, status="no_solution",
                    rev_total=rev_total)

    # recover plan
    assignment = [-1] * n_K
    car_routes = {c[0]: [] for c in cars}
    for c in cars:
        cid = c[0]
        first = None
        for k in orders:
            v = x_src.get((cid, k[0]))
            if v is not None and v.X > 0.5:
                first = k[0]
                break
        if first is None:
            continue
        seq = [first]
        cur = first
        while True:
            nxt = None
            for k in orders:
                v = x_chn.get((cid, cur, k[0]))
                if v is not None and v.X > 0.5:
                    nxt = k[0]
                    break
            if nxt is None:
                break
            seq.append(nxt)
            cur = nxt
        car_routes[cid] = seq
        for kid in seq:
            assignment[kid - 1] = cid

    relocation = []
    for cid, seq in car_routes.items():
        if not seq:
            continue
        car = by_cid[cid]
        prev_st = car[2]
        prev_ready = 0
        for kid in seq:
            o = by_kid[kid]
            ps = o[2]
            if T[(prev_st, ps)] > 0:
                relocation.append([cid, prev_st, ps, _fmt(prev_ready)])
            prev_st = o[3]
            prev_ready = o[5] + READY_AFTER_RETURN

    # profit
    rev_accepted = sum(by_kid[kid][6] for kid in range(1, n_K + 1)
                       if assignment[kid - 1] != -1)
    rev_rejected = rev_total - rev_accepted
    profit = rev_accepted - 2 * rev_rejected

    gap = m.MIPGap if m.Status != GRB.OPTIMAL else 0.0
    status_str = {GRB.OPTIMAL: "optimal", GRB.TIME_LIMIT: "time_limit"}.get(m.Status, str(m.Status))
    return dict(profit=profit, assignment=assignment, relocation=relocation,
                gap=gap, runtime=toc - tic, status=status_str,
                rev_total=rev_total, rev_accepted=rev_accepted,
                upper_bound=(m.ObjBound - 2 * rev_total))


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "instances/S1_baseline_00.txt"
    r = solve(p, time_limit=60, verbose=True)
    print({k: v for k, v in r.items() if k not in ("assignment", "relocation")})

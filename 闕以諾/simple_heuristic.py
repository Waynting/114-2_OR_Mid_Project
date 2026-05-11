"""
Problem 4 — simple "first-come, first-served" greedy benchmark.

Acts as the deliberately-naive lower-bound baseline against which the proposed
3-tier heuristic should look good.

Steps:
    1. Sort orders by pickup time.
    2. For each order, try every eligible car (correct level or one-up) in ID order
       and pick the first one that can legally serve it WITHOUT relocation
       (same station and ready in time).
    3. If none, try the same loop allowing relocation, picking the first feasible car
       whose move fits the remaining budget.
    4. Otherwise reject.

This is the kind of policy you would write in an afternoon and ship; it should
clearly underperform the 3-tier heuristic.
"""
from __future__ import annotations

from datetime import datetime, timedelta

BASE_DT = datetime(2023, 1, 1, 0, 0)
PICKUP_LEAD = 30
READY_AFTER_RETURN = 240


def _to_min(s):
    dt = datetime.strptime(s, "%Y/%m/%d %H:%M")
    d = dt - BASE_DT
    return d.days * 1440 + d.seconds // 60


def _fmt(m):
    return (BASE_DT + timedelta(minutes=m)).strftime("%Y/%m/%d %H:%M")


def _parse(path):
    secs, cur = [], []
    with open(path, "r", encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("="):
                if cur:
                    secs.append(cur); cur = []
            else:
                cur.append([v.strip() for v in line.split(",")])
    if cur:
        secs.append(cur)
    g = secs[0][1]
    n_S, n_C, n_L, n_K, n_D, B = (int(g[i]) for i in range(6))
    cars = {int(r[0]): (int(r[1]), int(r[2])) for r in secs[1][1:]}
    rates = {int(r[0]): int(r[1]) for r in secs[2][1:]}
    orders = []
    for r in secs[3][1:]:
        kid, lvl = int(r[0]), int(r[1])
        ps, rs = int(r[2]), int(r[3])
        pt, rt = _to_min(r[4]), _to_min(r[5])
        orders.append((kid, lvl, ps, rs, pt, rt))
    move = {}
    for r in secs[4][1:]:
        move[(int(r[0]), int(r[1]))] = int(r[2])
    return n_S, n_C, n_L, n_K, B, cars, rates, orders, move


def solve(path):
    n_S, n_C, n_L, n_K, B, cars, rates, orders, move = _parse(path)

    # car state: (current_station, ready_time)
    state = {cid: (init, 0) for cid, (lvl, init) in cars.items()}
    cid_order = sorted(cars.keys())

    assignment = [-1] * n_K
    relocation = []
    used = 0

    for kid, lvl, ps, rs, pt, rt in sorted(orders, key=lambda o: o[4]):
        deadline = 0 if pt == 0 else pt - PICKUP_LEAD
        chosen = None

        # pass 1: same station, no relocation
        for cid in cid_order:
            clvl, _ = cars[cid]
            if not (clvl == lvl or clvl == lvl + 1):
                continue
            cst, cready = state[cid]
            if cst != ps:
                continue
            if cready > deadline:
                continue
            chosen = (cid, 0, cst)
            break

        # pass 2: allow relocation
        if chosen is None and used < B:
            for cid in cid_order:
                clvl, _ = cars[cid]
                if not (clvl == lvl or clvl == lvl + 1):
                    continue
                cst, cready = state[cid]
                if cst == ps:
                    continue  # already covered above
                mv = move.get((cst, ps), 10 ** 9)
                if mv == 0:
                    continue
                if used + mv > B:
                    continue
                if cready + mv > deadline:
                    continue
                chosen = (cid, mv, cst)
                break

        if chosen is None:
            continue

        cid, mv, prev_st = chosen
        if mv > 0:
            cst, cready = state[cid]
            relocation.append([cid, prev_st, ps, _fmt(cready)])
            used += mv
        assignment[kid - 1] = cid
        state[cid] = (rs, rt + READY_AFTER_RETURN)

    return assignment, relocation


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    a, r = solve(p)
    print("assigned:", sum(1 for x in a if x != -1), "/", len(a))
    print("relocs:", len(r))

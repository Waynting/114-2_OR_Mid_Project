"""
Problem 4 — relaxed-LP upper bound on the optimal profit.

Used for medium / large instances where the path-flow MILP cannot be built
within the Gurobi free-licence size limits.

We use the following provably-valid relaxation, parameterised by a time
discretisation grid of 30-minute buckets:

    Variables  y_k in [0, 1]                                   (acceptance fraction)
    Constraints for each (bucket t, level threshold L = 1..n_L):
        sum_{k : order k active at bucket t and level(k) >= L} y_k
            <= sum_{c >= L} n_C(level = c)
    Objective: max sum_k 3 * R_k * y_k    (constant -2 * sum R_k dropped)

Why it's a valid upper bound (sketch):
    * In any feasible integer plan, at any time t, each car serves at most one
      active order.  A car at level c can serve only orders at levels c-1 or c,
      so a car at level >= L can only serve orders at level >= L-1 >= L-1.
      In particular, every order at level >= L that is "active" at time t
      occupies a distinct car at level >= L, which gives the inequality.
    * Cleaning, relocation, and lead-time are dropped (cars are assumed
      continuously available), so the LP is a relaxation; its optimum upper-
      bounds the original MILP optimum.

The LP has n_K variables and O(n_buckets * n_L) constraints, both small even
when n_K is 10,000.  HiGHS solves it in well under a second.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix


def compute_upper_bound(instance: dict) -> dict:
    """Return {'ub_profit': ..., 'rev_total': ..., 'lp_obj': ..., 'status': str}.

    `instance` should match the dict produced by `optimal_solver.parse`:
        keys: n_S, n_C, n_L, n_K, n_D, B, cars (list of (cid,lvl,init)),
              orders (list of (kid,lvl,ps,rs,pt,rt,rev)), rates, T
    """
    n_L = instance["n_L"]
    n_K = instance["n_K"]
    n_D = instance["n_D"]
    cars = instance["cars"]
    orders = instance["orders"]

    # cars at level >= L  (capacity of an LP constraint indexed by L)
    n_cars_by_level = [0] * (n_L + 2)
    for _, lvl, _ in cars:
        n_cars_by_level[lvl] += 1
    cap_at_or_above = [0] * (n_L + 2)
    for L in range(n_L, 0, -1):
        cap_at_or_above[L] = cap_at_or_above[L + 1] + n_cars_by_level[L]

    # revenue array
    R = np.array([o[6] for o in orders], dtype=float)
    rev_total = R.sum()

    # 30-minute buckets across the planning horizon
    bucket_size = 30
    horizon = n_D * 1440
    n_buckets = horizon // bucket_size

    # For each order, the half-open bucket range [b_start, b_end) where it is "active".
    # We treat the rental as occupying the car from pickup_time up to return_time + 240
    # (i.e. through cleaning); however, the LP UB itself does NOT need to model the
    # cleaning window — it is enough that the *rental* period blocks the car.
    # We pick the rental interval [pt, rt) since that is the period during which
    # the order is in service and consumes a car.
    b_start = np.empty(n_K, dtype=np.int64)
    b_end = np.empty(n_K, dtype=np.int64)
    levels = np.empty(n_K, dtype=np.int64)
    for i, o in enumerate(orders):
        _, lvl, _, _, pt, rt, _ = o
        b_start[i] = pt // bucket_size
        b_end[i] = (rt + bucket_size - 1) // bucket_size  # ceil
        levels[i] = lvl

    # Build sparse A_ub.
    # For each (t, L), the set of orders active at t with level >= L gives a row.
    rows = []
    cols = []
    data = []
    b = []
    row = 0

    # Pre-bucket orders by level for speed (level threshold loop wants level >= L)
    for L in range(1, n_L + 1):
        cap = cap_at_or_above[L]
        mask_lvl = levels >= L
        idx_at_lvl = np.where(mask_lvl)[0]
        if idx_at_lvl.size == 0:
            continue
        # active[t] is the set of k_idx with b_start[k]<=t<b_end[k]
        # Use a sweep: collect events (b_start, +k) and (b_end, -k), then per bucket
        # we'd track the active set. But simpler: iterate buckets and use binary
        # search on sorted starts/ends.
        starts = b_start[idx_at_lvl]
        ends = b_end[idx_at_lvl]
        # For each bucket t, active = {k : starts[k] <= t and ends[k] > t}
        # Use np.argsort for sweep.
        order_start = np.argsort(starts, kind="stable")
        order_end = np.argsort(ends, kind="stable")
        starts_sorted = starts[order_start]
        ends_sorted = ends[order_end]
        # incremental sweep
        active = set()
        i_start = 0
        i_end = 0
        for t in range(n_buckets):
            while i_start < len(starts_sorted) and starts_sorted[i_start] <= t:
                active.add(idx_at_lvl[order_start[i_start]])
                i_start += 1
            while i_end < len(ends_sorted) and ends_sorted[i_end] <= t:
                active.discard(idx_at_lvl[order_end[i_end]])
                i_end += 1
            if not active:
                continue
            if cap < 0:
                continue
            # only emit a binding constraint when active count > cap (others are slack)
            # we still emit them all — HiGHS will simplify
            if len(active) <= cap:
                continue
            for k_idx in active:
                rows.append(row)
                cols.append(k_idx)
                data.append(1.0)
            b.append(cap)
            row += 1

    if row == 0:
        # No binding constraint -> LP optimum is to accept everything.
        lp_obj = 3.0 * rev_total
        ub_profit = lp_obj - 2.0 * rev_total
        return dict(ub_profit=ub_profit, rev_total=rev_total,
                    lp_obj=lp_obj, status="trivial", n_constraints=0)

    A = csr_matrix((data, (rows, cols)), shape=(row, n_K))
    bv = np.array(b, dtype=float)

    c = -3.0 * R  # maximize 3*R*y  =>  minimize -3*R*y
    res = linprog(c, A_ub=A, b_ub=bv, bounds=[(0.0, 1.0)] * n_K, method="highs")
    if not res.success:
        return dict(ub_profit=None, rev_total=rev_total,
                    lp_obj=None, status="lp_failed:" + res.message,
                    n_constraints=row)
    lp_obj = -res.fun
    ub_profit = lp_obj - 2.0 * rev_total
    return dict(ub_profit=ub_profit, rev_total=rev_total,
                lp_obj=lp_obj, status="ok", n_constraints=row)


if __name__ == "__main__":
    import sys
    import optimal_solver
    inst = optimal_solver.parse(sys.argv[1])
    r = compute_upper_bound(inst)
    print(r)

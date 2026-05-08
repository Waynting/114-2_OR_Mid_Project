"""
find_obj_value: 自寫的可行性檢查 + profit 計算工具。

助教的 grading_program.py 提供了 hook（被註解的那一行），但 find_obj_value
本身要由我們自己寫，這樣才能在交件前看到實際 profit、找出 infeasibility 的成因
並據此改進演算法。

呼叫方式：
    feasibility, profit = find_obj_value(file_path, assignment, relocation)
    feasibility, profit = find_obj_value(file_path, assignment, relocation, verbose=True)
        # verbose=True 會在違反任何條件時印出哪一個 constraint 出問題

回傳：
    feasibility (bool)：解是否完全可行
    profit (int)：總 profit = Σ accepted_R − 2 × Σ rejected_R
                  即使 feasibility=False 也會回傳該數值，方便比對哪些訂單被拒。
"""

from datetime import datetime


def _time_to_minutes(s, base=datetime(2023, 1, 1, 0, 0)):
    dt = datetime.strptime(s, '%Y/%m/%d %H:%M')
    delta = dt - base
    return delta.days * 1440 + delta.seconds // 60


def _read_sections(path):
    sections = []
    section = []
    with open(path, 'r') as fp:
        for raw in fp:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('='):
                if section:
                    sections.append(section)
                    section = []
            else:
                section.append([v.strip() for v in line.split(',')])
    if section:
        sections.append(section)
    return sections


def find_obj_value(file_path, assignment, relocation, verbose=False):
    def fail(msg):
        if verbose:
            print(f"[INFEASIBLE] {msg}")
        return False

    sections = _read_sections(file_path)

    general = sections[0][1]
    n_s = int(general[0])
    n_c = int(general[1])
    n_l = int(general[2])
    n_k = int(general[3])
    moving_budget = int(general[5])

    cars = {}
    for row in sections[1][1:]:
        cars[int(row[0])] = (int(row[1]), int(row[2]))

    rates = {}
    for row in sections[2][1:]:
        rates[int(row[0])] = int(row[1])

    orders = {}
    for row in sections[3][1:]:
        oid = int(row[0])
        level = int(row[1])
        pickup_st = int(row[2])
        return_st = int(row[3])
        pt = _time_to_minutes(row[4])
        rt = _time_to_minutes(row[5])
        rent_hours = (rt - pt) // 60
        revenue = rates[level] * rent_hours
        orders[oid] = {
            'level': level,
            'pickup_st': pickup_st,
            'return_st': return_st,
            'pickup_time': pt,
            'return_time': rt,
            'revenue': revenue,
        }

    moving_time = {}
    for row in sections[4][1:]:
        moving_time[(int(row[0]), int(row[1]))] = int(row[2])

    # 計算 profit（不論可行與否都算，方便 debug）
    accepted_revenue = 0
    rejected_revenue = 0
    for k in range(1, n_k + 1):
        if assignment[k - 1] == -1:
            rejected_revenue += orders[k]['revenue']
        else:
            accepted_revenue += orders[k]['revenue']
    profit = accepted_revenue - 2 * rejected_revenue

    # ---------- 可行性檢查 ----------
    if len(assignment) != n_k:
        return fail(f"assignment length {len(assignment)} != n_k {n_k}"), profit

    # 每台車的 timeline events
    car_events = {cid: [] for cid in cars}

    # 訂單事件 + level 檢查
    for k in range(1, n_k + 1):
        car_id = assignment[k - 1]
        if car_id == -1:
            continue
        if car_id not in cars:
            return fail(f"order {k} assigned to non-existent car {car_id}"), profit
        order = orders[k]
        car_level = cars[car_id][0]
        if car_level != order['level'] and car_level != order['level'] + 1:
            return fail(
                f"order {k} (level {order['level']}) cannot be served by "
                f"car {car_id} (level {car_level}); only level l or l+1 allowed"
            ), profit
        car_events[car_id].append({
            'type': 'order',
            'order_id': k,
            'start': order['pickup_time'],
            'end_ready': order['return_time'] + 240,  # 還車 + 1hr buffer + 3hr clean
            'from_st': order['pickup_st'],
            'to_st': order['return_st'],
            'deadline': max(0, order['pickup_time'] - 30),
        })

    # 移車事件 + budget 檢查
    total_relocation_time = 0
    for idx, r in enumerate(relocation):
        if len(r) < 4:
            return fail(f"relocation[{idx}] has fewer than 4 fields: {r}"), profit
        car_id, from_st, to_st, time_str = r[0], r[1], r[2], r[3]
        if car_id not in cars:
            return fail(f"relocation[{idx}]: car {car_id} does not exist"), profit
        if (from_st, to_st) not in moving_time:
            return fail(f"relocation[{idx}]: invalid station pair ({from_st}, {to_st})"), profit
        try:
            start_time = _time_to_minutes(time_str)
        except (ValueError, TypeError):
            return fail(f"relocation[{idx}]: bad time string {time_str!r}"), profit
        move_min = moving_time[(from_st, to_st)]
        if move_min == 0 and from_st != to_st:
            return fail(f"relocation[{idx}]: zero-time move between distinct stations"), profit
        total_relocation_time += move_min
        car_events[car_id].append({
            'type': 'relocate',
            'start': start_time,
            'end_ready': start_time + move_min,
            'from_st': from_st,
            'to_st': to_st,
        })

    if total_relocation_time > moving_budget:
        return fail(
            f"total relocation time {total_relocation_time} exceeds budget {moving_budget}"
        ), profit

    # 模擬每台車的時間線
    for car_id, (level, init_st) in cars.items():
        events = sorted(car_events[car_id], key=lambda e: e['start'])
        cur_st = init_st
        cur_ready = 0
        for ev in events:
            if ev['type'] == 'order':
                if cur_st != ev['from_st']:
                    return fail(
                        f"car {car_id} order {ev['order_id']}: car at station "
                        f"{cur_st} but pickup is at {ev['from_st']}"
                    ), profit
                if cur_ready > ev['deadline']:
                    return fail(
                        f"car {car_id} order {ev['order_id']}: car ready at "
                        f"minute {cur_ready} but must be ready by {ev['deadline']} "
                        f"(pickup_time - 30)"
                    ), profit
                cur_st = ev['to_st']
                cur_ready = ev['end_ready']
            else:  # relocate
                if cur_st != ev['from_st']:
                    return fail(
                        f"car {car_id} relocate: car at station {cur_st} but "
                        f"trying to move from {ev['from_st']}"
                    ), profit
                if cur_ready > ev['start']:
                    return fail(
                        f"car {car_id} relocate: car ready at minute {cur_ready} "
                        f"but relocation starts at {ev['start']}"
                    ), profit
                cur_st = ev['to_st']
                cur_ready = ev['end_ready']

    return True, profit

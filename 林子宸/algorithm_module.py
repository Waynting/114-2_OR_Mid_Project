from MTP_lib import *


# -----------------------------------------------------------------------------
# 手寫的最小堆（min-heap）工具。
#
# 在最後的大型 greedy 演算法中，我們會把「同一個站點、同一個車輛等級」的車
# 放在同一個 heap 裡。heap 裡的元素格式是：
#     (ready_time, car_id)
# Python 比較 tuple 時會先比較第一個元素，所以 heap[0] 會是最早 ready 的車。
# 這樣可以快速找到某個 station / level 下最早可用的車，而不用每次掃過所有車。
# -----------------------------------------------------------------------------
def heap_push(heap, item):
    # 把新的 item 放進 heap，並一路往上調整，直到滿足 min-heap 性質。
    heap.append(item)
    i = len(heap) - 1
    while i > 0:
        parent = (i - 1) // 2
        if heap[parent] <= item:
            break
        heap[i] = heap[parent]
        i = parent
    heap[i] = item


def heap_pop(heap):
    # 取出 heap 中最小的 item，也就是目前最早 ready 的車。
    root = heap[0]
    last = heap.pop()
    if heap:
        # 把最後一個元素放回 heap，並一路往下調整，恢復 min-heap 性質。
        i = 0
        n = len(heap)
        while True:
            child = 2 * i + 1
            if child >= n:
                break
            right = child + 1
            if right < n and heap[right] < heap[child]:
                child = right
            if heap[child] >= last:
                break
            heap[i] = heap[child]
            i = child
        heap[i] = last
    return root


def heuristic_algorithm(file_path):
    '''
    針對租車排程問題設計的混合式 heuristic。

    整體分成三層：
    1. 小型測資：嘗試用限時 path-flow MIP 求較高品質的解。
    2. 中型測資：使用「高收益優先」的插入式 heuristic。
    3. 大型測資：使用速度較快的 heap-based chronological greedy 當保底。

    回傳格式：
    - assignment：assignment[k - 1] 代表 order k 指派給哪台車；若為 -1，代表拒絕該訂單。
    - relocation：每一列代表一次移車，格式依照助教提供的檢查程式需求輸出。
    '''

    # -------------------------------------------------------------------------
    # 讀取 instance 檔案。
    #
    # 題目的 txt 檔分成五個區塊：
    # 1. general parameters
    # 2. cars
    # 3. hourly rates
    # 4. orders
    # 5. moving time
    # 每個區塊用一行「==========」分隔。這個函數會把檔案切成 sections。
    # -------------------------------------------------------------------------
    def read_sections(path):
        sections = []
        section = []
        fp = open(path, 'r')
        for raw in fp:
            line = raw.strip()
            if len(line) == 0:
                continue
            if line.startswith('='):
                if section:
                    sections.append(section)
                    section = []
            else:
                section.append([value.strip() for value in line.split(',')])
        fp.close()
        if section:
            sections.append(section)
        return sections

    # 題目中的規劃期間從 2023/01/01 00:00 開始。
    # 後續排程只需要比較時間早晚，因此全部轉成「距離起點的分鐘數」。
    base_dt = datetime(2023, 1, 1, 0, 0)
    time_cache = {}

    def time_to_minutes(time_string):
        # 將 'YYYY/MM/DD hh:mm' 轉成從 base_dt 起算的分鐘數。
        # 用 cache 避免同一個時間字串被重複轉換，提升大型測資速度。
        value = time_cache.get(time_string)
        if value is not None:
            return value
        dt = datetime(int(time_string[0:4]), int(time_string[5:7]), int(time_string[8:10]),
                      int(time_string[11:13]), int(time_string[14:16]))
        delta = dt - base_dt
        value = delta.days * 1440 + delta.seconds // 60
        time_cache[time_string] = value
        return value

    def minutes_to_time(value):
        # 將分鐘數轉回作業要求的時間字串格式，主要用在 relocation 的輸出。
        return (base_dt + timedelta(minutes=value)).strftime('%Y/%m/%d %H:%M')

    def deadline_of(pickup_time):
        # 題目規定車子必須在取車前 30 分鐘就 ready。
        # 若 pickup_time 剛好是 0，代表規劃期一開始就取車；題目說所有車一開始都 ready，
        # 因此 deadline 保持為 0。
        if pickup_time == 0:
            return 0
        return pickup_time - 30

    sections = read_sections(file_path)

    # -------------------------------------------------------------------------
    # 解析 general parameters。
    # n_s：站點數
    # n_c：車輛數
    # n_l：車輛等級數
    # n_k：訂單數
    # moving_budget：總移車時間上限 B
    # -------------------------------------------------------------------------
    general = sections[0][1]
    n_s = int(general[0])
    n_c = int(general[1])
    n_l = int(general[2])
    n_k = int(general[3])
    moving_budget = int(general[5])

    # 每台車記成 (car_id, car_level, initial_station)。
    cars = []
    for row in sections[1][1:]:
        cars.append((int(row[0]), int(row[1]), int(row[2])))

    # rates[l] 表示 level l 車的 hourly rate。
    rates = [0] * (n_l + 2)
    for row in sections[2][1:]:
        rates[int(row[0])] = int(row[1])

    # 每張訂單整理成：
    # (order_id, requested_level, pickup_station, return_station,
    #  pickup_time, return_time, revenue)
    # orders_by_id 用 1-indexed 的方式儲存，方便用 order ID 直接查找。
    orders_by_id = [None] * (n_k + 1)
    orders = []
    for row in sections[3][1:]:
        order_id = int(row[0])
        level = int(row[1])
        pickup_station = int(row[2])
        return_station = int(row[3])
        pickup_time = time_to_minutes(row[4])
        return_time = time_to_minutes(row[5])
        rent_hours = (return_time - pickup_time) // 60
        revenue = rates[level] * rent_hours
        data = (order_id, level, pickup_station, return_station, pickup_time, return_time, revenue)
        orders_by_id[order_id] = data
        orders.append(data)

    # moving_time[i][j] 表示從 station i 移到 station j 需要幾分鐘。
    # 用矩陣儲存可以讓後面的 feasibility check 變成 O(1) 查詢。
    moving_time = [[0] * (n_s + 1) for _ in range(n_s + 1)]
    for row in sections[4][1:]:
        s1 = int(row[0])
        s2 = int(row[1])
        moving_time[s1][s2] = int(row[2])

    # -------------------------------------------------------------------------
    # 第一層：小型測資使用限時 path-flow MIP。
    #
    # 這個模型的核心是建立「可行銜接 arc」：
    #   (car, 0, j)：某台車的第一張訂單是 j
    #   (car, i, j)：某台車服務完訂單 i 後，接著服務訂單 j
    #
    # 好處是它比 greedy 更能整體考慮路徑；缺點是 arc 數量大約是 O(n_c * n_k^2)，
    # 所以只適合小測資。
    # -------------------------------------------------------------------------
    def solve_path_model():
        # 測資太大時直接跳過 MIP，避免在三分鐘限制內花太多時間建模或求解。
        if n_k > 160 or n_c * n_k * n_k > 700000:
            return None

        try:
            model = Model()
            model.Params.OutputFlag = 0
            model.Params.TimeLimit = 20
            model.Params.MIPFocus = 1
        except:
            # 若 Gurobi 無法建立模型，就安全地 fallback 到後面的 heuristic。
            return None

        x = {}             # x[(car_id, prev_order, next_order)] = 1 表示選擇這條銜接 arc。
        start_vars = {}    # 每台車可以作為第一張訂單的 arc。
        in_vars = {}       # 對某台車而言，進入某張訂單的 arc。
        out_vars = {}      # 對某台車而言，從某張訂單離開的 arc。
        order_in = {}      # 不分車，所有進入某張訂單的 arc。
        budget_terms = []  # 被選中 arc 對 relocation budget 的消耗。

        # 先建立各種容器，方便後續加 constraint。
        for car_id, car_level, initial_station in cars:
            start_vars[car_id] = []
            for order in orders:
                order_id = order[0]
                in_vars[(car_id, order_id)] = []
                out_vars[(car_id, order_id)] = []

        for order in orders:
            order_in[order[0]] = []

        # 建立所有時間與等級上可行的 arc。
        for car_id, car_level, initial_station in cars:
            # 從車子的初始站點到第一張訂單。
            for order_j in orders:
                j = order_j[0]
                level_j = order_j[1]
                pickup_j = order_j[2]
                pickup_time_j = order_j[4]

                # 等級限制：level l 訂單只能由 level l 或 level l+1 的車服務。
                if car_level == level_j or car_level == level_j + 1:
                    move_minutes = moving_time[initial_station][pickup_j]
                    # 第一張訂單也必須在 pickup 前 30 分鐘抵達取車站。
                    if move_minutes <= deadline_of(pickup_time_j):
                        var = model.addVar(vtype=GRB.BINARY)
                        x[(car_id, 0, j)] = var
                        start_vars[car_id].append(var)
                        in_vars[(car_id, j)].append(var)
                        order_in[j].append(var)
                        if move_minutes > 0:
                            budget_terms.append(move_minutes * var)

            # 從某張訂單 i 接到下一張訂單 j。
            for order_i in orders:
                i = order_i[0]
                level_i = order_i[1]
                return_station_i = order_i[3]

                # 還車後需保留 1 小時晚還 buffer + 3 小時清潔，所以 240 分鐘後才 ready。
                ready_i = order_i[5] + 240

                # 如果這台車本來就不能服務 order_i，就不能讓它出現在 order_i 後方的路徑裡。
                if not (car_level == level_i or car_level == level_i + 1):
                    continue

                for order_j in orders:
                    j = order_j[0]
                    if i == j:
                        continue
                    level_j = order_j[1]
                    pickup_j = order_j[2]
                    pickup_time_j = order_j[4]

                    if not (car_level == level_j or car_level == level_j + 1):
                        continue

                    move_minutes = moving_time[return_station_i][pickup_j]
                    # 檢查：完成 i、清潔、移車之後，是否能在 j 的 pickup 前 30 分鐘 ready。
                    if ready_i + move_minutes <= deadline_of(pickup_time_j):
                        var = model.addVar(vtype=GRB.BINARY)
                        x[(car_id, i, j)] = var
                        out_vars[(car_id, i)].append(var)
                        in_vars[(car_id, j)].append(var)
                        order_in[j].append(var)
                        if move_minutes > 0:
                            budget_terms.append(move_minutes * var)

        # y[order_id] 表示該訂單是否被接受。
        # 若有且只有一條 incoming arc 被選到，該訂單就被接受。
        y = {}
        for order in orders:
            order_id = order[0]
            y[order_id] = model.addVar(vtype=GRB.BINARY)
            model.addConstr(y[order_id] == quicksum(order_in[order_id]))

        for car_id, _, _ in cars:
            # 每台車最多只能有一條起始路徑。
            model.addConstr(quicksum(start_vars[car_id]) <= 1)
            for order in orders:
                order_id = order[0]
                # flow conservation：車子只有在進入某張訂單後，才可以從該訂單接到下一張。
                model.addConstr(quicksum(out_vars[(car_id, order_id)])
                                <= quicksum(in_vars[(car_id, order_id)]))

        # 所有移車時間總和不得超過 B。
        model.addConstr(quicksum(budget_terms) <= moving_budget)

        # 題目 profit = accepted_R - 2 * rejected_R。
        # 因為 total_R 固定，所以最大化 profit 等價於最大化 accepted revenue。
        model.setObjective(quicksum(order[6] * y[order[0]] for order in orders), GRB.MAXIMIZE)

        try:
            model.optimize()
        except:
            return None

        if model.SolCount <= 0:
            return None

        # 將 MIP 選到的 arc 轉回 assignment。
        assignment = [-1] * n_k
        successor = {}
        for car_id, _, _ in cars:
            successor[car_id] = {}

        for key, var in x.items():
            if var.X > 0.5:
                car_id, previous_order, next_order = key
                successor[car_id][previous_order] = next_order
                assignment[next_order - 1] = car_id

        # 根據每台車的路徑重建 relocation list。
        relocation = []
        for car_id, _, initial_station in cars:
            previous_order = 0
            while previous_order in successor[car_id]:
                next_order = successor[car_id][previous_order]
                order_j = orders_by_id[next_order]
                if previous_order == 0:
                    start_station = initial_station
                    start_time = 0
                else:
                    order_i = orders_by_id[previous_order]
                    start_station = order_i[3]
                    start_time = order_i[5] + 240

                end_station = order_j[2]
                if moving_time[start_station][end_station] > 0:
                    relocation.append([car_id, start_station, end_station, minutes_to_time(start_time)])
                previous_order = next_order

        return assignment, relocation

    # 優先嘗試 MIP；若測資太大或求解失敗，則進入中型 heuristic。
    mip_solution = solve_path_model()
    if mip_solution is not None:
        return mip_solution

    # -------------------------------------------------------------------------
    # 第二層：中型測資使用「高收益優先」的插入式 heuristic。
    #
    # 核心想法：
    # - 先處理 revenue 高的訂單，因為拒絕高收益訂單對 objective 傷害較大。
    # - 對每張訂單，嘗試插入某台車既有 schedule 的合適位置。
    # - 因為每台車的 schedule 依 pickup time 排序，所以只需要檢查插入位置前後兩段銜接。
    # -------------------------------------------------------------------------
    def solve_insertion_heuristic():
        # 測資太大就跳過。這層通常會對每張訂單掃過多台候選車，規模約為 O(n_c * n_k)。
        if n_k > 6000 or n_c * n_k > 600000:
            return None

        car_info = {}
        cars_by_level = [[] for _ in range(n_l + 2)]
        for car_id, car_level, initial_station in cars:
            car_info[car_id] = (car_level, initial_station)
            cars_by_level[car_level].append(car_id)

        # schedules[car_id] 儲存該車已接受的訂單，並維持按 pickup time 排序。
        schedules = {}
        for car_id, _, _ in cars:
            schedules[car_id] = []

        def find_insert_position(schedule, pickup_time):
            # 二分搜尋：找到新訂單應插入的位置，使 schedule 仍維持時間順序。
            left = 0
            right = len(schedule)
            while left < right:
                mid = (left + right) // 2
                if orders_by_id[schedule[mid]][4] <= pickup_time:
                    left = mid + 1
                else:
                    right = mid
            return left

        assignment = [-1] * n_k
        used_budget = 0

        # 高收益訂單優先；收益相同時，取車時間較早者優先。
        value_order = sorted(orders, key=lambda order: (-order[6], order[4]))

        for order in value_order:
            order_id = order[0]
            requested_level = order[1]
            pickup_station = order[2]
            return_station = order[3]
            pickup_time = order[4]
            return_time = order[5]

            # 只考慮同級車與高一級車，符合題目的免費升級限制。
            candidate_cars = []
            candidate_cars.extend(cars_by_level[requested_level])
            if requested_level + 1 <= n_l:
                candidate_cars.extend(cars_by_level[requested_level + 1])

            best = None
            for car_id in candidate_cars:
                car_level, initial_station = car_info[car_id]
                schedule = schedules[car_id]
                position = find_insert_position(schedule, pickup_time)

                # 找出插入位置前一張訂單；若沒有前一張，車就從初始站點出發。
                if position > 0:
                    previous_order = orders_by_id[schedule[position - 1]]
                    previous_station = previous_order[3]
                    previous_ready = previous_order[5] + 240
                else:
                    previous_station = initial_station
                    previous_ready = 0

                # 檢查 previous -> new order 是否接得上。
                first_move = moving_time[previous_station][pickup_station]
                if previous_ready + first_move > deadline_of(pickup_time):
                    continue

                # 若後面還有下一張訂單，還要檢查 new order -> next 是否接得上，
                # 以免插入新訂單後破壞原本 schedule 的可行性。
                if position < len(schedule):
                    next_order = orders_by_id[schedule[position]]
                    second_move = moving_time[return_station][next_order[2]]
                    if return_time + 240 + second_move > deadline_of(next_order[4]):
                        continue
                    old_move = moving_time[previous_station][next_order[2]]
                    new_move = first_move + second_move
                else:
                    old_move = 0
                    new_move = first_move

                # 插入前原本是 previous -> next；插入後變成 previous -> new -> next。
                # 因此 relocation budget 只需要計算 moving time 的增量。
                extra_budget = new_move - old_move
                if used_budget + extra_budget <= moving_budget:
                    # score 越小越好：優先少用 relocation、避免 upgrade、並盡量分散到不同車。
                    score = (max(extra_budget, 0), extra_budget,
                             car_level - requested_level, len(schedule), car_id)
                    if best is None or score < best[0]:
                        best = (score, car_id, position, extra_budget)

            # 若找到可行插入位置，就接受該訂單並更新該車 schedule。
            if best is not None:
                _, car_id, position, extra_budget = best
                schedules[car_id].insert(position, order_id)
                assignment[order_id - 1] = car_id
                used_budget += extra_budget

        # 根據最後的 schedules 重新建立 relocation list。
        # 不在插入過程中直接記錄 relocation，是因為後續插入可能改變原路徑。
        relocation = []
        for car_id, _, initial_station in cars:
            previous_station = initial_station
            previous_ready = 0
            for order_id in schedules[car_id]:
                order = orders_by_id[order_id]
                pickup_station = order[2]
                if moving_time[previous_station][pickup_station] > 0:
                    relocation.append([car_id, previous_station, pickup_station,
                                       minutes_to_time(previous_ready)])
                previous_station = order[3]
                previous_ready = order[5] + 240

        return assignment, relocation

    # 嘗試中型 insertion heuristic；若測資仍太大，就進入最後的 greedy fallback。
    insertion_solution = solve_insertion_heuristic()
    if insertion_solution is not None:
        return insertion_solution

    # -------------------------------------------------------------------------
    # 第三層：大型測資使用 heap-based chronological greedy。
    #
    # 核心想法：
    # - 依 pickup time 由早到晚處理訂單。
    # - 每個 station / level 維護一個 heap，快速找出最早 ready 的車。
    # - 優先使用同站車；若同站沒有，再從附近站點 relocation。
    # - 這一層犧牲部分解品質，換取速度與穩定可行性。
    # -------------------------------------------------------------------------

    # car_heap[station][level] 儲存目前或未來會在該 station、該 level ready 的車。
    car_heap = [[[] for _ in range(n_l + 2)] for _ in range(n_s + 1)]
    for car_id, level, station in cars:
        heap_push(car_heap[station][level], (0, car_id))

    # 依取車時間排序；同時間下，收益高的訂單優先。
    sorted_orders = []
    for order in orders:
        sorted_orders.append((order[4], -order[6], order[5], order[0],
                              order[1], order[2], order[3]))
    sorted_orders.sort()

    # 預先為每個目的站點建立「附近來源站點」清單。
    # 若站點很多，就只掃最近的一部分站點，避免每張訂單都掃全部 station。
    nearest_stations = [[] for _ in range(n_s + 1)]
    if moving_budget > 0:
        scan_limit = n_s - 1
        if n_s > 40:
            scan_limit = min(n_s - 1, max(20, int(math.sqrt(n_s)) * 4))
        for destination in range(1, n_s + 1):
            candidates = []
            for source in range(1, n_s + 1):
                if source != destination:
                    candidates.append((moving_time[source][destination], source))
            candidates.sort()
            nearest_stations[destination] = [source for _, source in candidates[:scan_limit]]

    assignment = [-1] * n_k
    relocation = []
    remaining_budget = moving_budget

    for order in sorted_orders:
        pickup_time = order[0]
        return_time = order[2]
        order_id = order[3]
        requested_level = order[4]
        pickup_station = order[5]
        return_station = order[6]

        latest_ready = deadline_of(pickup_time)

        # 先找同級車，再找高一級車；這樣可以保留高等級車給真正需要的訂單。
        eligible_levels = [requested_level]
        if requested_level + 1 <= n_l:
            eligible_levels.append(requested_level + 1)

        chosen = None

        # 第一優先：取車站當地就有可用車，不需要消耗 relocation budget。
        for level in eligible_levels:
            heap = car_heap[pickup_station][level]
            if heap and heap[0][0] <= latest_ready:
                ready_time, car_id = heap_pop(heap)
                chosen = (car_id, level, ready_time)
                break

        # 第二優先：若同站沒有可用車，才考慮從附近站點移車過來。
        # 必須同時滿足時間可行與 remaining_budget 足夠。
        if chosen is None and remaining_budget > 0:
            best = None
            for level in eligible_levels:
                for start_station in nearest_stations[pickup_station]:
                    move_minutes = moving_time[start_station][pickup_station]
                    if move_minutes > remaining_budget:
                        continue
                    heap = car_heap[start_station][level]
                    if heap and heap[0][0] + move_minutes <= latest_ready:
                        ready_time, car_id = heap[0]
                        # relocation 時優先選移動時間短的車；再用 ready_time 等欄位打破平手。
                        score = (move_minutes, ready_time, level, start_station, car_id)
                        if best is None or score < best[0]:
                            best = (score, level, start_station)
                # 若同級車已經找到可行 relocation，就不再看高一級車。
                if best is not None:
                    break

            if best is not None:
                level = best[1]
                start_station = best[2]
                ready_time, car_id = heap_pop(car_heap[start_station][level])
                move_minutes = moving_time[start_station][pickup_station]
                remaining_budget -= move_minutes
                relocation.append([car_id, start_station, pickup_station, minutes_to_time(ready_time)])
                chosen = (car_id, level, ready_time)

        # 若找到車，就接受訂單；否則 assignment 維持 -1，代表拒絕。
        if chosen is not None:
            car_id = chosen[0]
            car_level = chosen[1]
            assignment[order_id - 1] = car_id

            # 完成訂單後：return_time + 1 小時晚還 buffer + 3 小時清潔 = return_time + 240。
            next_ready_time = return_time + 240
            heap_push(car_heap[return_station][car_level], (next_ready_time, car_id))

    return assignment, relocation

# 作業研究期中專案 — Problem 1

本資料夾收錄 **Problem 1**(用 Gurobi 解 instance 5)的程式、輸出與報告。

---

## 環境需求

| 項目 | 版本 / 說明 |
|------|------|
| Python | 3.12 以上(實測 3.14 也可) |
| Gurobi Optimizer | 13.0.1(需有效授權,個人學術版即可) |
| `gurobipy` | 與 Gurobi 主程式同版本 |

題目允許的其他套件(本程式僅用到標準庫 + gurobipy):`math`、`numpy`、`pandas`、`time`、`datetime`、`os`、`itertools`。

### 安裝(若你還沒有環境)

```bash
# 1. 建立 venv
python3.12 -m venv ~/.venvs/OR
source ~/.venvs/OR/bin/activate

# 2. 安裝 gurobipy
pip install gurobipy

# 3. 確認授權(把 gurobi.lic 放到 ~/ 即可)
python -c "import gurobipy; print(gurobipy.gurobi.version())"
# 預期輸出:(13, 0, 1)
```

> **本機既有環境提醒:**
> - 已可直接使用的 venv:`/Users/waynliu/.venvs/OR/bin/python`
> - 原本指定的 `OR/OR114-1` venv shebang 指向已不存在的 `HW1/OR114-1/...`,目前不可用。要修復就重建一次。

---

## 資料夾內容

| 檔案 | 說明 |
|------|------|
| `problem1_solve.py` | Problem 1 的 MIP 模型與求解程式 |
| `problem1_solution.txt` | 求解後的純文字 + JSON 摘要(訂單分派、搬車路線) |
| `problem1_report.md` | **要交出去的業務語言報告**(營運主管能直接讀懂) |
| `README.md` | 你正在看的這份檔案 |

題目解釋整理放在上一層的 `../OR114-2_期中專案_問題解釋.md`。

---

## 如何執行 Problem 1

從專案根目錄(或任何位置)執行:

```bash
/Users/waynliu/.venvs/OR/bin/python "/Users/waynliu/Documents/NTU/台大/大二下/OR/114-2_OR_Mid_Project/劉威廷/Problem1/problem1_solve.py"
```

或先 `cd` 進來再跑:

```bash
cd "/Users/waynliu/Documents/NTU/台大/大二下/OR/114-2_OR_Mid_Project/劉威廷/Problem1"
/Users/waynliu/.venvs/OR/bin/python problem1_solve.py
```

### 預期輸出(節錄)

```
Optimal objective (profit) = 106800.00
Sanity: 3*rev_accepted - 2*rev_total = 3*117000.00 - 2*122100.00 = 106800.00

Accepted orders: [3, 4, 5, 6, 7, 8, 9, 10]
Rejected orders: [1, 2]
Total relocation minutes used: 1080 / 1200
```

求解時間 < 0.05 秒(Gurobi 在 6 站 / 6 車 / 10 單的小規模 instance 上幾乎瞬解)。

### 輸入路徑

程式內已寫死讀 `instance05.txt` 的絕對路徑:

```
Material_from_cool/OR114-2_midtermProject_data/data/instance05.txt
```

若要解別的 instance,改 `problem1_solve.py` 開頭的 `INSTANCE_PATH` 變數即可。

---

## 模型概念(一句話版)

把每台車視為一條路徑:`source → 訂單a → 訂單b → … → sink`,
- 二元變數 `x[c,i,j]` = 車 c 在做完訂單 i 後接著做訂單 j(或起始 / 結束)
- 二元變數 `y[k]` = 訂單 k 是否被接受
- 限制:每訂單最多被一台車做、每車流量守恆、總搬車時間 ≤ B、訂單之間時間窗可行
- 目標:`max  Σ R_k·y_k − Σ 2R_k·(1−y_k)`

詳細推導與報告內容請看 `problem1_report.md`。

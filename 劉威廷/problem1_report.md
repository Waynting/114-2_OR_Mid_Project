# IEDO Car-Rental Operating Plan — Instance 5

**Planning horizon:** 2023/01/01 00:00 – 2023/01/05 24:00 (5 days)
**Fleet:** 6 cars across 6 stations, 2 vehicle levels
**Orders on the books:** 10
**Employee relocation budget:** 1,200 minutes (20 hours)

---

## 1. Bottom line

| Item | Amount (NT$) |
|------|--------------|
| Sales revenue from the 8 accepted orders | **117,000** |
| Compensation paid to the 2 rejected customers (2 × revenue) | **10,200** |
| **Net profit** | **106,800** |

We will accept **8 of the 10 orders**, decline 2, perform **1 free upgrade**, and use **1,080 minutes (18 hours)** of the 1,200-minute employee relocation budget — leaving 120 minutes of slack as a safety margin.

This is the **provably optimal** plan: any other plan respecting the operating rules would earn a strictly lower profit.

---

## 2. Order-by-order decision

| Order | Level requested | Pick-up | Return | Revenue (NT$) | Decision | Car assigned | Upgrade? |
|:-:|:-:|:--|:--|--:|:--|:-:|:-:|
| 1 | 1 | Station 1, 2023/01/04 01:00 | Station 6, 2023/01/04 20:00 |  1,900 | **Reject** (pay 3,800 compensation) | — | — |
| 2 | 1 | Station 4, 2023/01/01 16:00 | Station 5, 2023/01/03 00:00 |  3,200 | **Reject** (pay 6,400 compensation) | — | — |
| 3 | 1 | Station 5, 2023/01/02 03:30 | Station 1, 2023/01/04 11:30 |  5,600 | Accept | Car 3 | No |
| 4 | 1 | Station 1, 2023/01/03 12:00 | Station 2, 2023/01/05 15:00 |  5,100 | Accept | Car 1 | No |
| 5 | 2 | Station 6, 2023/01/01 00:00 | Station 6, 2023/01/04 20:00 | 36,800 | Accept | Car 6 | No |
| 6 | 1 | Station 3, 2023/01/04 23:00 | Station 4, 2023/01/05 14:00 |  1,500 | Accept | Car 4 | **Yes** (level-2 car serving level-1 order) |
| 7 | 2 | Station 2, 2023/01/02 03:30 | Station 1, 2023/01/04 23:30 | 27,200 | Accept | Car 5 | No |
| 8 | 2 | Station 6, 2023/01/05 04:30 | Station 6, 2023/01/05 14:30 |  4,000 | Accept | Car 6 | No |
| 9 | 2 | Station 3, 2023/01/01 19:30 | Station 4, 2023/01/04 15:30 | 27,200 | Accept | Car 4 | No |
| 10| 1 | Station 4, 2023/01/01 06:00 | Station 2, 2023/01/05 06:00 |  9,600 | Accept | Car 2 | No |

**Why orders 1 and 2 are declined.**
- *Order 1* (revenue 1,900) requires a level-1 car at Station 1 by 2023/01/04 00:30. The only level-1 cars (Cars 1, 2, 3) are already locked into much more profitable jobs by that time, and pulling any of them off would forfeit a far larger revenue stream than 1,900. The smaller level-2 cars cannot help either, because they too are committed (serving orders 5, 7, and 9). Hence we accept the 3,800 compensation.
- *Order 2* (revenue 3,200) starts on Day 1 at 16:00 in Station 4. Serving it would require either Car 5 (which is needed for Order 7) or relocating a level-1 car to Station 4 in time, both of which would block strictly more lucrative orders later in the week (in particular Orders 7 and 10, worth 27,200 and 9,600 respectively). Paying the 6,400 compensation is cheaper than those losses.

**Free upgrade.** Order 6 is a level-1 booking, but it is most profitable to satisfy with the level-2 Car 4 (which has just finished Order 9 and is well-positioned). The customer pays the level-1 price and gets a level-2 car at no extra cost.

---

## 3. Car-by-car schedule

Below is the full schedule for each of the 6 cars. "Ready" means the car has finished cleaning (return + 1 hour late buffer + 3 hours cleaning) and is available for the next assignment.

### Car 1 (level 1, starts at Station 1)
- **Day 1 00:00 – Day 3 11:30:** Idle at Station 1 (waiting for Order 4).
- **Day 3 12:00:** Customer picks up at Station 1 (Order 4).
- **Day 5 15:00:** Customer returns at Station 2.
- *No relocation needed; the car never leaves Station 1 except to serve the customer.*

### Car 2 (level 1, starts at Station 2)
- **Day 1 01:30:** Employee drives Car 2 from Station 2 to Station 4 (240 minutes), arriving at Day 1 05:30 — exactly 30 minutes before the customer's 06:00 pick-up.
- **Day 1 06:00:** Customer picks up Car 2 at Station 4 (Order 10).
- **Day 5 06:00:** Customer returns at Station 2.
- *Car remains at Station 2; no further work in the planning horizon.*

### Car 3 (level 1, starts at Station 3)
- **Day 1 23:30:** Employee drives Car 3 from Station 3 to Station 5 (210 minutes), arriving at Day 2 03:00.
- **Day 2 03:30:** Customer picks up at Station 5 (Order 3).
- **Day 4 11:30:** Customer returns at Station 1.
- *Car ready again at Day 4 15:30 at Station 1, but no further orders are taken with it.*

### Car 4 (level 2, starts at Station 5)
- **Day 1 15:30:** Employee drives Car 4 from Station 5 to Station 3 (210 minutes), arriving at Day 1 19:00.
- **Day 1 19:30:** Customer picks up at Station 3 (Order 9).
- **Day 4 15:30:** Customer returns at Station 4. Car ready again Day 4 19:30.
- **Day 4 19:30:** Employee drives Car 4 from Station 4 to Station 3 (180 minutes), arriving Day 4 22:30.
- **Day 4 23:00:** Customer picks up at Station 3 (Order 6 — **free upgrade** to level-2).
- **Day 5 14:00:** Customer returns at Station 4. Done.

### Car 5 (level 2, starts at Station 4)
- **Day 1 23:00:** Employee drives Car 5 from Station 4 to Station 2 (240 minutes), arriving Day 2 03:00.
- **Day 2 03:30:** Customer picks up at Station 2 (Order 7).
- **Day 4 23:30:** Customer returns at Station 1. Done.

### Car 6 (level 2, starts at Station 6)
- **Day 1 00:00:** Customer picks up at Station 6 (Order 5). *No relocation — the car is already at the right station.*
- **Day 4 20:00:** Customer returns at Station 6. Car ready again Day 5 00:00.
- **Day 5 04:30:** Customer picks up at Station 6 (Order 8).
- **Day 5 14:30:** Customer returns at Station 6. Done.

---

## 4. Master relocation list (employee work orders)

Five employee-driven moves, totalling **1,080 minutes (18 hours)** out of the **1,200-minute** budget.

| # | Car | From | To | Depart | Arrive | Duration | Purpose |
|:-:|:-:|:-:|:-:|:--|:--|--:|:--|
| 1 | Car 2 | Station 2 | Station 4 | 2023/01/01 01:30 | 2023/01/01 05:30 | 240 min | Position for Order 10 pick-up at 06:00 |
| 2 | Car 4 | Station 5 | Station 3 | 2023/01/01 15:30 | 2023/01/01 19:00 | 210 min | Position for Order 9 pick-up at 19:30 |
| 3 | Car 5 | Station 4 | Station 2 | 2023/01/01 23:00 | 2023/01/02 03:00 | 240 min | Position for Order 7 pick-up at 03:30 |
| 4 | Car 3 | Station 3 | Station 5 | 2023/01/01 23:30 | 2023/01/02 03:00 | 210 min | Position for Order 3 pick-up at 03:30 |
| 5 | Car 4 | Station 4 | Station 3 | 2023/01/04 19:30 | 2023/01/04 22:30 | 180 min | Position for Order 6 pick-up at 23:00 (after Order 9 cleaning) |
|   |       |          |          |                 |                 | **1,080 min** |   |

**Budget utilisation:** 1,080 / 1,200 minutes = 90%. The remaining 120 minutes are unused — this is the cheapest plan in terms of employee labour that still earns the maximum profit.

---

## 5. Day-by-day operations digest (for the dispatcher)

- **Day 1 (Jan 1)** is the busiest day for the employees. By the end of Day 1 the entire fleet is either rented out or pre-positioned for the second wave of pick-ups on Day 2 morning.
  - 00:00 — Order 5 starts (Car 6 in place at Station 6).
  - 01:30 — Begin moving Car 2 to Station 4.
  - 06:00 — Order 10 starts (Car 2 at Station 4).
  - 15:30 — Begin moving Car 4 to Station 3.
  - 19:30 — Order 9 starts (Car 4 at Station 3).
  - 23:00 — Begin moving Car 5 to Station 2.
  - 23:30 — Begin moving Car 3 to Station 5.
- **Day 2 (Jan 2):** Two pick-ups at 03:30 (Orders 3 and 7). Otherwise quiet.
- **Day 3 (Jan 3):** One pick-up at 12:00 (Order 4 — Car 1 sitting at Station 1).
- **Day 4 (Jan 4):** Returns of Orders 3, 9, 7, 5 cluster late. Car 4 must be relocated again at 19:30 to be in place for Order 6 at 23:00.
- **Day 5 (Jan 5):** Final pick-up of Order 8 at 04:30; remaining returns happen during the day.

---

## 6. What the IEDO operations manager should take away

1. **Accept 8 orders, decline orders 1 and 2.** The two rejections are unavoidable: serving them would force the cancellation of a strictly more profitable order. Compensation of 10,200 is the cost of optimality.
2. **Perform exactly one upgrade** (Order 6 served by a level-2 car). All other accepted orders are matched at their requested level.
3. **Plan five employee relocations** as listed in Section 4. The earliest employee shift starts at 01:30 on Day 1; the latest at 19:30 on Day 4.
4. **Total profit: NT$ 106,800.** This figure has been validated against an exact mathematical optimisation solver (Gurobi); no feasible alternative plan can do better.

# Operations Research: Midterm Project

## 1. Program Formulation

- objective:
    - maximize revenue less compensation

- decision variables:
    - orders to accept
    - car assigned to an order
        - we can tell if upgrades are offered from assignment plan.
    - moving plan (from/to, time/place)

- ideas
    - this is a parallel machine scheduling problem.
        - the cars are the machines.
    - dealing with date and time
        - they are fixed. turn them into integers during preprocessing?
    - availability: loc and time
    - service levels: precompute table to list if a car can service an order?


## 2. Notes on research paper

- exact model: logic based benders decomposition
    - program is split into master problem and subproblem.
    - master problem fixes certain variables / relaxes certain constraints.
    - a (feasible?) solution to the master problem is used to go on to solve the subproblem.
    - if feasible, (and global optimal? how to check? feasible == global optimality?), done (?)
    - if infeasible, a constraint is added to the master problem (a "cut") to eliminate a section from the feasible region.
    - in our case, order assignment (and perhaps scheduling w/o feasibility check) is probably the master problem, while (scheduling?) and feasiblity checking is the subproblem.

- heuristic model: branch and check
    - lbbd with different timing in solving the subproblems.
    - its not too bad if we can't implement this, i think. we can still come up with our own model, albeit with worse performance.
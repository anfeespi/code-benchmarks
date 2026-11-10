Write a Python function:

    def min_pruning_cost(parent, demand, cap, cut_cost, critical, root_cap, penalty)

A radial power feeder is a rooted tree with `n` nodes labeled `0 .. n-1`; node 0 is the
substation (the root). For every node `v >= 1`, `parent[v]` is its parent; `parent[0]` is
`-1`. Labels carry no ordering: a parent may have a LARGER label than its child. The input
is guaranteed to be a valid tree rooted at 0. All list arguments have length `n`.

- `demand[v]` (int >= 0) is the load drawn by node `v`.
- For `v >= 1`, the line between `v` and `parent[v]` (call it "line v") has capacity
  `cap[v]` (int >= 0) and costs `cut_cost[v]` (int >= 0) to cut. `cap[0]` and
  `cut_cost[0]` are ignored.
- `critical[v]` is a bool.

The operator chooses a set of lines to CUT. A node is RETAINED if the path from it to the
root uses no cut line (the root is always retained); every other node is LOST. The LOAD of
a retained node `v` is the sum of `demand` over all retained nodes in `v`'s subtree,
including `v` itself. A plan is FEASIBLE if and only if:
1. every critical node is retained;
2. for every retained node `v >= 1`: LOAD(v) <= cap[v];
3. LOAD(0) <= root_cap.

The COST of a plan is the sum of `cut_cost` over all cut lines plus `penalty` (int >= 0)
multiplied by the total `demand` of all LOST nodes (a cut loses the entire subtree below
it).

Return the minimum cost over all feasible plans as an int, or `None` if no plan is
feasible. Cutting nothing is a plan like any other (cost 0 if feasible).

Input domain: `1 <= n <= 250`, `0 <= demand[v] <= 5`, `0 <= cap[v] <= 1250`,
`0 <= root_cap <= 1250`, `cut_cost[v]` and `penalty` in `[0, 10**6]`. The tree may be a
path of length 250.

Performance requirement: inputs at the top of the domain must finish within a few seconds;
enumerating subsets of lines is far too slow.

Examples:
- min_pruning_cost([-1, 0, 1, 1], [0, 2, 3, 4], [0, 6, 9, 9], [0, 50, 7, 1], [False] * 4, 100, 2) == 9
  # uncut, LOAD(1) = 2+3+4 = 9 > 6. Cutting line 3 costs 1 + 2*4 = 9 (LOAD(1) becomes 5);
  # cutting line 2 instead costs 7 + 2*3 = 13; cutting line 1 costs 50 + 2*9 = 68
- min_pruning_cost([-1, 0, 1, 1], [0, 2, 3, 4], [0, 6, 9, 9], [0, 50, 7, 1], [False, False, False, True], 100, 2) == 13
  # node 3 is critical, so line 3 cannot be cut (nor line 1)
- min_pruning_cost([-1, 0, 1, 1], [0, 2, 3, 4], [0, 6, 9, 9], [0, 50, 7, 1], [False, False, True, True], 100, 2) is None
- min_pruning_cost([-1, 2, 0], [1, 4, 0], [0, 3, 10], [0, 1, 100], [False] * 3, 5, 10) == 41
  # node 1 hangs below node 2; its own demand 4 exceeds cap[1] = 3, so line 1 or line 2
  # must be cut: 1 + 10*4 = 41 versus 100 + 10*4 = 140

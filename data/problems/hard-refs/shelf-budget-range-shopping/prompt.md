Write a Python function:

    def budget_purchases(prices: list[int], queries: list[tuple[int, int, int]]) -> list[tuple[int, int]]

A shelf holds `n` items in a row; `prices[i]` is the price of the item at position `i`
(0-based). Every price is an int with `1 <= price <= 10**9`; prices may repeat.

Each query `(l, r, budget)` (with `0 <= l <= r < n` and `budget` an int, `budget >= 0`)
describes an independent shopping spree restricted to the items at positions `l..r`
inclusive. Each item can be bought at most once. The shopper wants to buy as MANY items
as possible whose total price is at most `budget`. For the query, report a tuple
`(count, spent)` where:
- `count` is the maximum number of items from positions `l..r` that can be bought with a
  total price `<= budget`;
- `spent` is the smallest possible total price of buying `count` items from positions
  `l..r` (0 when `count == 0`).

Return a list with one `(count, spent)` tuple per query, in query order. Queries do not
affect each other or the shelf. If `queries` is empty, return [] (even if `prices` is
also empty).

Input domain: `0 <= n <= 100,000`, up to 100,000 queries, `0 <= budget <= 10**15`.

Performance requirement: the function is called with n = 100,000 prices and 100,000
queries whose ranges are typically tens of thousands of items wide; it must finish in a
few seconds. Sorting or scanning each query's range is far too slow.

Examples:
- budget_purchases([5, 1, 4, 2, 8, 3], [(0, 5, 6), (2, 4, 5), (4, 4, 7), (0, 5, 100)])
    == [(3, 6), (1, 2), (0, 0), (6, 23)]
  # positions 0..5 sorted by price: 1, 2, 3, 4, 5, 8; 1 + 2 + 3 = 6 fits a budget of 6
  # positions 2..4 hold 4, 2, 8: only the 2 fits a budget of 5
- budget_purchases([3, 3, 3], [(0, 2, 8), (1, 1, 2)]) == [(2, 6), (0, 0)]

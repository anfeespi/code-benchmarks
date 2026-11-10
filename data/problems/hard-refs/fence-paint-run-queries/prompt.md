Write a Python function:

    def fence_report(colors: list[int], operations: list[tuple]) -> list[tuple[int, int]]

A fence has `n = len(colors)` planks at positions `0 .. n-1`; `colors[i]` is the initial
color of plank `i` (an int; colors are compared with `==` only). Process `operations` in
order. Each operation is one of:

- `("paint", l, r, c)`: repaint every plank at positions `l..r` (inclusive) with color
  `c` (an int). Planks outside `l..r` keep their colors.
- `("query", l, r)`: report on the CURRENT colors of planks `l..r` (inclusive). Split that
  stretch into maximal RUNS: maximal blocks of consecutive planks inside `l..r` that all
  have the same color (a run is cut at `l` and `r` even if the same color continues
  outside the stretch). Report the tuple `(number_of_runs, length_of_longest_run)`.

All operations satisfy `0 <= l <= r < n`. Return a list with one
`(number_of_runs, length_of_longest_run)` tuple per `"query"` operation, in the order the
queries appear. `"paint"` operations produce no output. If there are no queries, return [].
`colors` may be empty only when `operations` is empty.

Input domain: `n <= 200,000`, up to 100,000 operations, colors are ints in
`[0, 10**9]`.

Performance requirement: the function is called with n = 200,000 planks and 100,000
operations mixing short repaints with queries that each cover more than half of the
fence; it must finish in a few seconds. Updating or rescanning planks one by one per
operation (or walking all color blocks inside a queried stretch) is far too slow.

Examples:
- fence_report([1, 1, 2, 2, 2, 3],
               [("query", 0, 5), ("paint", 1, 3, 3), ("query", 0, 5), ("query", 2, 5),
                ("paint", 4, 4, 3), ("query", 1, 5)])
    == [(3, 3), (4, 3), (3, 2), (1, 5)]
  # after painting 1..3 with 3 the fence is [1, 3, 3, 3, 2, 3]; after painting plank 4
  # with 3 it is [1, 3, 3, 3, 3, 3], so planks 1..5 form a single run of length 5
- fence_report([7, 7, 7], [("query", 1, 1), ("query", 0, 2)]) == [(1, 1), (1, 3)]

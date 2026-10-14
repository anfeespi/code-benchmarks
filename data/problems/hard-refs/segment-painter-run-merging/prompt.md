Write a Python function:

    def run_ops(ops: list[tuple]) -> list

It simulates a "painter" over the integer number line. Every integer position is either
UNPAINTED or painted with exactly one label (a non-empty str). Initially every position
is unpainted. `ops` is a list of operations, processed in order; EVERY operation appends
exactly one value to the returned list:

- ("paint", l, r, label): if l >= r, nothing changes and the output is 0. Otherwise every
  integer position p with l <= p < r becomes painted with `label`. Output: the number of
  positions in [l, r) whose state actually changed (positions that were unpainted or held
  a different label; positions that already held `label` do not count).
- ("erase", l, r): if l >= r, nothing changes and the output is 0. Otherwise every
  position p with l <= p < r becomes unpainted. Output: the number of positions in
  [l, r) that were painted before this operation.
- ("at", p): output the label at position p, or None if p is unpainted.
- ("runs",): output the number of RUNS. A run is a maximal set of consecutive integer
  positions p, p+1, ..., q that are all painted with the same label. Two painted
  positions that are adjacent but carry different labels are in different runs; an
  unpainted position always separates runs. Unpainted positions form no runs.
- ("total", label): output how many positions are currently painted with `label`
  (0 if none; `label` may never have been used).
- ("next_change", p): let state(x) be the label at x, or None if unpainted. Output the
  smallest integer q > p with state(q) != state(p), or None if no such q exists (that is,
  p is unpainted and no position greater than p is painted).

Input domain: all coordinates l, r, p are ints in [-10**9, 10**9]; `ops` has at most
200,000 operations; operation names and argument types are always valid as described.

Performance requirement: the function is called with 200,000 operations whose painted
regions fragment into tens of thousands of simultaneous runs over coordinates up to 10**9,
and must finish in a few seconds. Storing one entry per painted position, or rescanning
every run on each operation, is far too slow.

Examples:
- run_ops([("paint", 0, 5, "x"), ("paint", 5, 8, "x"), ("runs",), ("paint", 2, 6, "y"),
           ("runs",), ("total", "x"), ("next_change", 0), ("next_change", 6), ("next_change", 8)])
  == [5, 3, 1, 4, 3, 4, 2, 8, None]
  # [0,8) is one "x" run; painting y over [2,6) changes 4 positions and leaves x|y|x
- run_ops([("paint", 1, 4, "a"), ("paint", 0, 6, "a"), ("erase", 3, 10), ("at", 2),
           ("at", 3), ("erase", 5, 5), ("next_change", -7), ("runs",)])
  == [3, 3, 3, 'a', None, 0, 0, 1]
  # the second paint only changes positions 0, 4 and 5; the erase clears 3, 4, 5

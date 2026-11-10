Write a Python function:

    def count_records(levels: list[int], margin: int, queries: list[tuple[int, int]]) -> list[int]

`levels` is a list of tide-gauge readings (ints, possibly negative) taken at positions
`0 .. n-1`. `margin` is an int with `margin >= 0`.

A query `(l, r)` (0-based, inclusive, `0 <= l <= r < n`) asks how many RECORDS occur when
the window `levels[l..r]` is scanned from left to right under these rules:
- `levels[l]` is always a record, and the CURRENT RECORD becomes `levels[l]`.
- For each later position `i` (`l < i <= r`), in order: if
  `levels[i] >= CURRENT RECORD + margin`, then position `i` is a record and the CURRENT
  RECORD becomes `levels[i]`; otherwise nothing happens.
Note that with `margin == 0` a reading EQUAL to the current record is a new record.

Return a list with one int per query, in query order: the number of records in that
window. Each query is independent (every window starts its own scan). If `queries` is
empty, return [] (even if `levels` is also empty).

Input domain: `0 <= n <= 200,000`, readings in `[-10**9, 10**9]`, `0 <= margin <= 10**9`,
up to 200,000 queries; all queries satisfy `0 <= l <= r < n`.

Performance requirement: the function is called with n = 200,000 readings and 200,000
queries whose windows are typically tens of thousands of positions long; it must finish
in a few seconds. Scanning each window, or anything else proportional to the total
length of all windows, is far too slow.

Examples:
- count_records([3, 1, 4, 1, 5, 9, 2, 6], 2, [(0, 7), (1, 3), (2, 6), (5, 5)]) == [3, 2, 2, 1]
  # window 0..7: records at values 3, 5 (5 >= 3 + 2) and 9 (9 >= 5 + 2); 4 is not (4 < 5)
- count_records([2, 2, 1, 2], 0, [(0, 3), (2, 3)]) == [3, 2]
  # margin 0: each 2 equals the current record 2, so both later 2s are records
- count_records([5], 7, []) == []

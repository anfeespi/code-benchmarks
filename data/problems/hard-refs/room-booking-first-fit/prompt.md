Write a Python function:

    def run_ops(ops: list[tuple]) -> list

It simulates the calendar of a single meeting room on an integer time line. A booking is
a half-open interval [s, e) of integers with s < e; it occupies the times s, s+1, ...,
e-1. Bookings in the calendar never overlap, but they may touch ([1, 3) and [3, 5) can
coexist). The calendar starts empty. `ops` is processed in order and EVERY operation
appends exactly one value to the returned list:

- ("book", s, e): if s >= e, output the string "INVALID" and change nothing. Otherwise,
  if [s, e) overlaps any existing booking (shares at least one occupied time), output
  the string "CONFLICT" and change nothing. Otherwise add the booking and output True.
- ("cancel", s): if a booking starting exactly at time s exists, remove it and output its
  length e - s; otherwise output 0 and change nothing.
- ("first_fit", t, d): d >= 1. Output the smallest integer x >= t such that [x, x + d)
  overlaps no existing booking. (Time is unbounded to the right, so x always exists; it
  may be larger than every input value.) The calendar is not changed.
- ("free_between", a, b): output the number of integer times in [a, b) that are not
  occupied by any booking (0 if a >= b). The calendar is not changed.

Input domain: at most 200,000 operations; s, e, t, a, b are ints in [0, 10**9];
d is an int in [1, 10**9]; operation names always have the arity shown.

Performance requirement: the function is called with 200,000 operations where the
calendar holds tens of thousands of bookings separated by many small gaps, and
first_fit queries must skip over thousands of too-small gaps; it must finish in a few
seconds. Walking booking by booking (or gap by gap) for each query is far too slow.

Examples:
- run_ops([("book", 0, 4), ("book", 4, 6), ("book", 8, 9), ("book", 5, 7),
           ("first_fit", 0, 2), ("first_fit", 0, 3), ("first_fit", 5, 1), ("free_between", 2, 12)])
  == [True, True, True, "CONFLICT", 6, 9, 6, 5]
  # gaps are [6, 8) and [9, inf); a gap of length 3 first appears at 9
- run_ops([("book", 3, 3), ("book", 10, 20), ("cancel", 11), ("first_fit", 12, 5),
           ("cancel", 10), ("first_fit", 12, 5), ("free_between", 0, 5), ("free_between", 7, 7)])
  == ["INVALID", True, 0, 20, 10, 12, 5, 0]

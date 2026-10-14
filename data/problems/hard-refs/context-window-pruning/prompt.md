Write a Python function:

    def best_context(messages, budget, max_gap, bonus)

A chat assistant must prune its conversation history to fit a context window.
`messages` is a list of tuples `(length, value, pinned)` in chronological order (index
`0 .. n-1`), where `length` is an int `>= 0`, `value` is an int (may be negative) and
`pinned` is a bool.

Choose a set S of message indices to KEEP (every other message is dropped). S is VALID
if and only if all of the following hold:
1. Every pinned message is kept.
2. The total `length` of the kept messages is `<= budget`.
3. No more than `max_gap` CONSECUTIVE messages are dropped anywhere. This includes the run
   of dropped messages before the first kept message and the run after the last kept
   message (if nothing is kept, the whole list is one dropped run of length n).

The SCORE of S is the sum of `value` over kept messages, plus `bonus` for every index `i`
such that both `i` and `i + 1` are kept (each adjacent kept pair earns the bonus once;
three consecutive kept messages earn it twice). `bonus` is an int and may be negative.

Return the maximum SCORE over all valid S, as an int, or `None` if no valid S exists.
Note that the empty set may be valid (score 0) and that keeping a negative-value message
can be forced by the rules. `best_context([], b, g, x)` returns 0 for any valid b, g.

Raise `ValueError` if `budget < 0` or `max_gap < 0` (checked before anything else).

Input domain: `0 <= len(messages) <= 120`, `0 <= budget <= 400`, lengths in [0, 400],
values and bonus in [-10**6, 10**6], `0 <= max_gap <= 120`.

Performance requirement: inputs at the top of the domain must finish within a few seconds;
enumerating subsets is far too slow.

Examples:
- best_context([(3, 5, False), (4, 6, False), (2, -1, False), (5, 8, False)], 10, 1, 2) == 14
  # e.g. keep {0, 1, 2}: lengths 3+4+2 = 9, values 5+6-1 = 10, two adjacent pairs -> +4
  # (keeping all four would need length 14 > 10)
- best_context([(1, -5, False), (1, -5, False), (1, -5, False)], 3, 1, 0) == -5
  # keeping only the middle message leaves dropped runs of length 1 on both sides
- best_context([(1, 1, False), (9, 4, True)], 5, 3, 0) is None
  # the pinned message alone exceeds the budget

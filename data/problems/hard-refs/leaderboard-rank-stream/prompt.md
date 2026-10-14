Write a Python function:

    def leaderboard_ranks(submissions: list[tuple[str, int]]) -> list[int]

`submissions` is a chronological list of score submissions; submission number `i`
(0-based, its position in the list) is a tuple `(player, score)` where `player` is a
non-empty str and `score` is an int (possibly negative).

Leaderboard rules, applied after each submission in order:
- A player is on the leaderboard from their first submission onward.
- A player's BEST is the maximum score among their submissions so far.
- A player's BEST TIME is the index of the earliest submission that achieved their current
  BEST. A later submission with a score EQUAL to the current BEST does not change the BEST
  TIME; a strictly higher score sets a new BEST and its index becomes the new BEST TIME.
  A lower score changes nothing.
- Players are ordered by BEST descending, then by BEST TIME ascending (whoever reached that
  score first ranks higher). Because BEST TIMEs are distinct, this is a strict total order.
- A player's RANK is 1 + the number of players ordered before them.

Return a list with one int per submission: element `i` is the RANK of the player who made
submission `i`, measured immediately after submission `i` has been applied (later
submissions do not affect it). An empty input returns [].

Input domain: up to 200,000 submissions, up to 200,000 distinct players, scores in
[-10**9, 10**9].

Performance requirement: the function is called with 200,000 submissions spread over
~100,000 distinct players and must finish in a few seconds. Rescanning or re-sorting all
players for every submission is far too slow.

Examples:
- leaderboard_ranks([("ann", 10), ("bob", 12), ("ann", 12), ("cat", 5)]) == [1, 1, 2, 3]
  # after ("ann", 12): ann and bob both have BEST 12, bob reached it first (index 1 < 2)
- leaderboard_ranks([("a", 5), ("b", 7), ("a", 3), ("a", 9)]) == [1, 1, 2, 1]
  # ("a", 3) does not change a's BEST of 5, so a is still behind b
- leaderboard_ranks([("x", -4), ("y", -4), ("x", -4)]) == [1, 2, 1]
  # x's repeated -4 keeps BEST TIME 0, so x stays ahead of y

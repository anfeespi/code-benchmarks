Write a Python function:

    def fastest_delivery(n, roads, stations, capacity, swap_time, max_swaps, s, t)

An electric courier drives on a road network with `n` junctions labeled `0 .. n-1`.

- `roads` is a list of DIRECTED roads `(u, v, minutes, energy)`: driving from `u` to `v`
  takes `minutes` (int >= 0) and changes the battery by `-energy`. `energy` is an int in
  `[-capacity, capacity]`: positive means the road consumes charge, negative means it is a
  downhill road that regenerates charge, 0 means neutral. Parallel roads and self-loops
  may appear.
- The battery charge is always an integer in `[0, capacity]`. The courier starts at `s`
  with a FULL battery (`charge == capacity`) at minute 0.
- A road with `energy > 0` may only be driven if the current charge is `>= energy`
  (arriving with exactly 0 is fine). After driving any road the new charge is
  `min(capacity, charge - energy)`: regeneration beyond `capacity` is lost.
- `stations` is a list of junction ids (duplicates possible) that have a swap station.
  While standing at a station junction the courier may perform a SWAP at any time: it
  takes `swap_time` minutes (int >= 0) and sets the charge to `capacity`. Swapping is
  allowed at `s` if `s` is a station, and is allowed even when the battery is already
  full. A route may contain at most `max_swaps` swaps IN TOTAL (int >= 0).
- A route is any sequence of road drives and swaps (junctions and roads may be revisited).
  Its cost is the pair `(total_minutes, number_of_swaps)`, where total_minutes is the sum
  of the minutes of every drive plus `swap_time` for every swap.

Return the lexicographically smallest cost pair `(total_minutes, number_of_swaps)` over all
valid routes that end at `t` (i.e. first minimize minutes, then, among routes with that
minimum, minimize swaps), as a tuple of two ints. If no valid route reaches `t`, return
`None`. If `s == t`, return `(0, 0)`.

Input domain: `1 <= n <= 200`, `len(roads) <= 1500`, `0 <= capacity <= 40`,
`0 <= max_swaps <= 6`, minutes and swap_time up to 10**6, `0 <= s, t < n`.

Performance requirement: inputs at the top of the domain must finish within a few seconds.

Examples:
- fastest_delivery(4, [(0, 1, 1, 3), (1, 3, 1, 3), (0, 2, 5, 1), (2, 3, 5, 1)], [1], 3, 2, 1, 0, 3) == (4, 1)
  # 0->1 drains the battery, swap at 1 (2 minutes), 1->3: 1 + 2 + 1 = 4 minutes, 1 swap
- fastest_delivery(4, [(0, 1, 1, 3), (1, 3, 1, 3), (0, 2, 5, 1), (2, 3, 5, 1)], [1], 3, 2, 0, 0, 3) == (10, 0)
  # no swaps allowed: only 0->2->3 works
- fastest_delivery(4, [(0, 1, 1, 4), (1, 2, 1, 1), (0, 2, 5, 1), (2, 3, 1, 4)], [1, 2], 4, 1, 1, 0, 3) == (7, 1)
  # reaching 2 fastest (0->1, swap, 1->2 at minute 3) spends the only swap and 2->3 needs
  # a full battery; the answer drives 0->2 (5 min), swaps at 2 (1 min), then 2->3 (1 min)
- fastest_delivery(4, [(0, 1, 1, 4), (1, 2, 1, -5), (2, 3, 1, 5)], [], 5, 9, 0, 0, 3) == (3, 0)
  # charge 5 -> 1 -> min(5, 6) = 5 -> 0

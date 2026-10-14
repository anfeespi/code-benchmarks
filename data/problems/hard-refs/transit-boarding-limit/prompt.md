Write a Python function:

    def earliest_arrival(connections, transfer, source, target, start_time, max_boardings)

A rail timetable is given as a list of elementary CONNECTIONS. Each connection is a tuple
`(trip_id, from_station, to_station, dep, arr)` of ints: a vehicle of trip `trip_id`
leaves `from_station` at time `dep` and reaches `to_station` at time `arr`, with
`0 <= dep < arr` and `from_station != to_station`. Stations are ints in
`[0, len(transfer))`.

Guarantees about trips: the connections of one trip may appear anywhere in the list and
in any order, but when sorted by `dep` they form a chain: each connection departs from the
station where the previous one arrived, and no earlier than the previous one's `arr`.
A trip may visit the same station more than once.

Travel rules:
- The traveler starts at `source` at time `start_time` and may wait anywhere for any time.
- BOARDING: the traveler may board a trip at connection `c` if they are at `c`'s
  `from_station` and READY there no later than `c.dep` (ready time `<= dep`). Once on
  board they ride `c` and may stay seated through any number of subsequent connections of
  the same trip, then ALIGHT at the `to_station` of the last connection ridden, at its
  `arr` time. Staying seated never requires extra time.
- READY time: at `source` the traveler is ready at `start_time` (no transfer time
  needed for the first boarding). After alighting at station `x` at time `a`, they are
  ready at `x` at time `a + transfer[x]` (`transfer[x] >= 0` is the minimum change time
  at `x`). This applies to every later boarding at `x`, including boarding the same trip
  again or boarding at `x == source`.
- Every boarding counts, and a journey may contain at most `max_boardings` boardings.
- The journey reaches `target` at the moment the traveler alights there (the transfer
  time is NOT added to the arrival). Passing through `target` while staying seated does not
  count as reaching it, but the traveler may always choose to alight there.

Return the earliest time at which `target` can be reached, as an int, or `None` if it
cannot be reached. If `source == target`, return `start_time` (even when
`max_boardings == 0`).

Input domain: up to 60,000 connections, up to 5,000 stations, times up to 10**9,
`0 <= max_boardings <= 10**9`.

Performance requirement: the function must finish in a few seconds on inputs at the top of
the domain, including timetables where the best journey needs thousands of boardings and
`max_boardings` is huge, mixed with tens of thousands of unrelated connections.
Enumerating journeys is far too slow, and so is rescanning the whole timetable once per
boarding.

Examples:
- earliest_arrival([(1, 0, 1, 0, 5), (1, 1, 2, 6, 9), (2, 1, 2, 5, 7)], [0, 2, 0], 0, 2, 0, 2) == 9
  # alighting at 1 at time 5 makes the traveler ready only at 7, too late for trip 2
  # (dep 5); staying seated on trip 1 reaches station 2 at 9
- earliest_arrival([(1, 0, 1, 0, 5), (1, 1, 2, 6, 9), (2, 1, 2, 5, 7)], [0, 0, 0], 0, 2, 0, 2) == 7
- earliest_arrival([(10, 0, 1, 0, 2), (11, 1, 2, 3, 4), (12, 0, 2, 0, 10)], [0, 0, 0], 0, 2, 0, 1) == 10
  # with a single boarding only trip 12 works; with max_boardings=2 the answer is 4

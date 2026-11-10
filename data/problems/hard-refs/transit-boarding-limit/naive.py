def earliest_arrival(connections, transfer, source, target, start_time, max_boardings):
    # correct round-based scan, but every round rescans the whole timetable: O(rounds * C)
    if source == target:
        return start_time
    by_trip = {}
    for c in connections:
        by_trip.setdefault(c[0], []).append(c)
    trips = [sorted(v, key=lambda c: c[3]) for v in by_trip.values()]
    INF = float("inf")
    ready = {source: start_time}
    best = INF
    rounds = 0
    changed = True
    while changed and rounds < max_boardings:
        rounds += 1
        arrivals = {}
        for trip in trips:
            on = False
            for _, frm, to, dep, arr in trip:
                if not on and ready.get(frm, INF) <= dep:
                    on = True
                if on and arr < arrivals.get(to, INF):
                    arrivals[to] = arr
        changed = False
        for x, a in arrivals.items():
            best = min(best, a) if x == target else best
            if a + transfer[x] < ready.get(x, INF):
                ready[x] = a + transfer[x]
                changed = True
    return None if best == INF else best

def earliest_arrival(connections, transfer, source, target, start_time, max_boardings):
    if source == target:
        return start_time
    by_trip = {}
    for c in connections:
        by_trip.setdefault(c[0], []).append(c)
    trips = [sorted(v, key=lambda c: c[3]) for v in by_trip.values()]
    station_trips = {}
    for ti, trip in enumerate(trips):
        for c in trip:
            station_trips.setdefault(c[1], set()).add(ti)
    INF = float("inf")
    ready = {source: start_time}  # earliest time one can board at a station (fewer boardings than this round)
    best = INF
    marked = {source}
    rounds = 0
    while marked and rounds < max_boardings:
        rounds += 1
        to_scan = set()
        for x in marked:
            to_scan |= station_trips.get(x, set())
        arrivals = {}
        for ti in to_scan:
            on = False
            for _, frm, to, dep, arr in trips[ti]:
                if not on:
                    r = ready.get(frm)
                    if r is not None and r <= dep:
                        on = True
                if on and arr < arrivals.get(to, INF):
                    arrivals[to] = arr
        marked = set()
        for x, a in arrivals.items():
            if x == target and a < best:
                best = a
            rr = a + transfer[x]
            if rr < ready.get(x, INF):
                ready[x] = rr
                marked.add(x)
    return None if best == INF else best

def earliest_arrival(connections, transfer, source, target, start_time, max_boardings):
    # explore every (station, ready time, boardings used) state reachable by explicit rides
    if source == target:
        return start_time
    trips = {}
    for c in connections:
        trips.setdefault(c[0], []).append(c)
    trips = [sorted(v, key=lambda c: c[3]) for v in trips.values()]
    best = None
    seen = set()
    stack = [(source, start_time, 0)]
    while stack:
        state = stack.pop()
        if state in seen:
            continue
        seen.add(state)
        x, ready, used = state
        if used >= max_boardings:
            continue
        for trip in trips:
            for i, c in enumerate(trip):
                if c[1] != x or c[3] < ready:
                    continue
                for ride in trip[i:]:  # stay seated through ride, then alight at its end
                    to, arr = ride[2], ride[4]
                    if to == target and (best is None or arr < best):
                        best = arr
                    stack.append((to, arr + transfer[to], used + 1))
    return best

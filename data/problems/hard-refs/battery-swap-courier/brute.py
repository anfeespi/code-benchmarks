def fastest_delivery(n, roads, stations, capacity, swap_time, max_swaps, s, t):
    # fixpoint relaxation over explicit states (node, charge, swaps used) -> least minutes
    if s == t:
        return (0, 0)
    st = set(stations)
    best = {(s, capacity, 0): 0}
    changed = True
    while changed:
        changed = False
        for (v, c, k), d in list(best.items()):
            moves = []
            if v in st and k < max_swaps:
                moves.append(((v, capacity, k + 1), d + swap_time))
            for u, w, minutes, energy in roads:
                if u == v and c >= energy:
                    moves.append(((w, min(capacity, c - energy), k), d + minutes))
            for key, nd in moves:
                if key not in best or nd < best[key]:
                    best[key] = nd
                    changed = True
    cands = [(d, k) for (v, c, k), d in best.items() if v == t]
    return min(cands) if cands else None

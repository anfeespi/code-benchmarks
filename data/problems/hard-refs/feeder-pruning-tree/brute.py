from itertools import product


def min_pruning_cost(parent, demand, cap, cut_cost, critical, root_cap, penalty):
    n = len(parent)
    best = None
    for cuts in product((False, True), repeat=n - 1):
        is_cut = (False,) + cuts  # is_cut[v]: edge (v, parent[v]) removed
        retained = [False] * n
        for v in range(n):
            # walk up to the root; retained iff no cut edge on the way
            u, ok = v, True
            while u != 0:
                if is_cut[u]:
                    ok = False
                    break
                u = parent[u]
            retained[v] = ok
        if any(critical[v] and not retained[v] for v in range(n)):
            continue
        load = [0] * n
        for v in range(n):
            if retained[v]:
                u = v
                while True:
                    load[u] += demand[v]
                    if u == 0:
                        break
                    u = parent[u]
        if load[0] > root_cap:
            continue
        if any(retained[v] and load[v] > cap[v] for v in range(1, n)):
            continue
        cost = sum(cut_cost[v] for v in range(1, n) if is_cut[v])
        cost += penalty * sum(demand[v] for v in range(n) if not retained[v])
        if best is None or cost < best:
            best = cost
    return best

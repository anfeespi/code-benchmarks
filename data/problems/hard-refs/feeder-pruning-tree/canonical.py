def min_pruning_cost(parent, demand, cap, cut_cost, critical, root_cap, penalty):
    n = len(parent)
    children = [[] for _ in range(n)]
    for v in range(1, n):
        children[parent[v]].append(v)
    order = []
    stack = [0]
    while stack:
        v = stack.pop()
        order.append(v)
        stack.extend(children[v])
    INF = float("inf")
    subdem = [0] * n
    has_crit = [False] * n
    f = [None] * n
    for v in reversed(order):
        subdem[v] = demand[v] + sum(subdem[c] for c in children[v])
        has_crit[v] = critical[v] or any(has_crit[c] for c in children[v])
        limit = root_cap if v == 0 else cap[v]
        if demand[v] > limit:
            f[v] = []  # v cannot be retained at all
            continue
        cur = [INF] * (demand[v] + 1)
        cur[demand[v]] = 0
        for c in children[v]:
            g = f[c][:cap[c] + 1]
            cut = INF if has_crit[c] else cut_cost[c] + penalty * subdem[c]
            size = min(limit + 1, len(cur) + max(len(g) - 1, 0))
            nxt = [INF] * size
            for x, a in enumerate(cur):
                if a == INF:
                    continue
                if a + cut < nxt[x]:
                    nxt[x] = a + cut
                for y, b in enumerate(g):
                    if x + y >= size:
                        break
                    if b != INF and a + b < nxt[x + y]:
                        nxt[x + y] = a + b
            cur = nxt
        f[v] = cur
    best = min(f[0], default=INF)
    return None if best == INF else best

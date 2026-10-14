from bisect import bisect_left


def count_records(levels, margin, queries):
    n = len(levels)
    if not queries:
        return []
    # nxt[i] = first j > i with levels[j] >= levels[i] + margin (n if none). The current
    # record value is always levels[last record index], so records form a chain via nxt.
    vals = sorted(set(levels))
    m = len(vals)
    INF = n
    tree = [INF] * (m + 1)  # prefix-min BIT over reversed value ranks
    nxt = [n] * n
    for i in range(n - 1, -1, -1):
        k = bisect_left(vals, levels[i] + margin)  # ranks >= k qualify
        p = m - k  # reversed prefix length
        best = INF
        while p > 0:
            if tree[p] < best:
                best = tree[p]
            p -= p & -p
        nxt[i] = best
        p = m - bisect_left(vals, levels[i])  # reversed position (1-based) of levels[i]
        while p <= m:
            if tree[p] > i:
                tree[p] = i
            p += p & -p
    # forest rooted at sentinel n; the root-to-node path holds decreasing indices
    children = [[] for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        children[nxt[i]].append(i)
    by_l = [[] for _ in range(n)]
    for qi, (l, r) in enumerate(queries):
        by_l[l].append((qi, r))
    out = [0] * len(queries)
    path = []  # negated indices of the current root-to-node path (ascending)
    stack = [(c, False) for c in children[n]]
    while stack:
        node, done = stack.pop()
        if done:
            path.pop()
            continue
        path.append(-node)
        for qi, r in by_l[node]:
            out[qi] = len(path) - bisect_left(path, -r)
        stack.append((node, True))
        for c in children[node]:
            stack.append((c, False))
    return out

def budget_purchases(prices, queries):
    if not queries:
        return []
    vals = sorted(set(prices))
    m = len(vals)
    rank = {v: i for i, v in enumerate(vals)}
    # persistent segment tree over value ranks; version k holds prices[0:k]
    L, R, C, S = [0], [0], [0], [0]
    roots = [0]
    for v in prices:
        pos = rank[v]
        old = roots[-1]
        new = len(L)
        L.append(L[old]); R.append(R[old]); C.append(C[old] + 1); S.append(S[old] + v)
        roots.append(new)
        lo, hi = 0, m - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            idx = len(L)
            if pos <= mid:
                old = L[old]
                L[new] = idx
                hi = mid
            else:
                old = R[old]
                R[new] = idx
                lo = mid + 1
            L.append(L[old]); R.append(R[old]); C.append(C[old] + 1); S.append(S[old] + v)
            new = idx
    out = []
    for l, r, budget in queries:
        a, b = roots[r + 1], roots[l]
        k = spent = 0
        lo, hi = 0, m - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            la, lb = L[a], L[b]
            ls = S[la] - S[lb]
            if ls <= budget:
                budget -= ls
                spent += ls
                k += C[la] - C[lb]
                a, b = R[a], R[b]
                lo = mid + 1
            else:
                a, b = la, lb
                hi = mid
        c = C[a] - C[b]
        if c:
            v = vals[lo]
            t = min(c, budget // v)
            k += t
            spent += t * v
        out.append((k, spent))
    return out
